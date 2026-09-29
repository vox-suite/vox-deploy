#!/usr/bin/env python3
"""Read-only authentication probe for the existing deployment database."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import unquote, urlsplit

spec = importlib.util.spec_from_file_location(
    "vm_configuration", Path(__file__).with_name("configure-github-oauth-vm.py")
)
vm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vm)


def connection_environment(candidate, current):
    proposed, existing = urlsplit(candidate), urlsplit(current)
    if (proposed.scheme not in ("postgres", "postgresql") or proposed.fragment
            or (proposed.hostname, proposed.port, proposed.username, proposed.path)
            != (existing.hostname, existing.port, existing.username, existing.path)):
        raise RuntimeError("Database candidate does not identify the existing target; probe refused.")
    if not proposed.hostname or not proposed.password or not proposed.username:
        raise RuntimeError("Database candidate is incomplete; probe refused.")
    return {
        "PGHOST": proposed.hostname, "PGPORT": str(proposed.port or 5432),
        "PGUSER": unquote(proposed.username), "PGPASSWORD": unquote(proposed.password),
        "PGDATABASE": unquote(proposed.path.lstrip("/")), "PGCONNECT_TIMEOUT": "10",
        "PGSSLMODE": "verify-full", "PGSSLROOTCERT": "system",
    }


if __name__ == "__main__":
    try:
        if os.geteuid() != 0:
            raise RuntimeError("Run through sudo on the deployment VM.")
        current = vm.env_value(vm.protected_text(Path("/etc/vox.local.env")), "DATABASE_URL")
        if current is None:
            current = vm.env_value(vm.protected_text(Path("/etc/vox.env")), "DATABASE_URL")
        candidate = sys.stdin.read(8193).strip()
        if not candidate or len(candidate) > 8192 or not current:
            raise RuntimeError("Database configuration is missing or invalid.")
        environment = connection_environment(candidate, current)
        print("Encrypted GitHub database candidate matches VM: " + str(candidate == current).lower(), flush=True)
        # Official client, one SELECT, no mounted files, no retained container.
        command = ["docker", "run", "--rm", "--network", "host"]
        for key in environment:
            command.extend(["--env", key])
        command.extend(["postgres:18", "psql", "-X", "-tA", "-v", "ON_ERROR_STOP=1", "-c", "SELECT 1"])
        result = subprocess.run(command, env={**os.environ, **environment}, capture_output=True, timeout=120)
        if result.returncode or result.stdout.strip() != b"1":
            if b"password authentication failed" in result.stderr:
                raise RuntimeError("Encrypted GitHub database candidate also fails password authentication.")
            raise RuntimeError("Fresh database connection probe failed; no configuration changed.")
        print("PASS: fresh authenticated database connection and SELECT 1.")
    except (RuntimeError, OSError, ValueError, subprocess.TimeoutExpired) as error:
        print(str(error) if isinstance(error, RuntimeError) else "Database probe failed; no configuration changed.", file=sys.stderr)
        sys.exit(1)
