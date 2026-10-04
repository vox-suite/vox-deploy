#!/usr/bin/env python3
"""Read-only authentication probe for the existing deployment database."""
import importlib.util
import os
from pathlib import Path
import subprocess
import ssl
import sys
import tempfile
from urllib.parse import unquote, urlsplit
from urllib.request import urlopen

# Supabase Studio's official custom-content.json identifies this production CA.
# https://github.com/supabase/supabase/blob/177ef0cdd66b6025465c00f4742cee6ee1c69e10/apps/studio/hooks/custom-content/custom-content.json
SUPABASE_CA_URL = "https://supabase-downloads.s3-ap-southeast-1.amazonaws.com/prod/ssl/prod-ca-2021.crt"

spec = importlib.util.spec_from_file_location(
    "vm_configuration", Path(__file__).with_name("protected-vm-config.py")
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


def probe(environment):
    with tempfile.TemporaryDirectory(prefix="vox-database-probe-") as directory:
        command = ["docker", "run", "--rm", "--network", "host"]
        if environment["PGHOST"].endswith((".supabase.com", ".supabase.co")):
            # Scope the vendor CA to this one client; do not change host trust.
            with urlopen(SUPABASE_CA_URL, timeout=15) as response:
                certificate = response.read(32769)
            if len(certificate) > 32768:
                raise RuntimeError("Supabase CA response is invalid; probe refused.")
            ssl.create_default_context().load_verify_locations(cadata=certificate.decode("ascii"))
            certificate_path = Path(directory) / "supabase-root.crt"
            certificate_path.write_bytes(certificate)
            os.chmod(certificate_path, 0o600)
            command.extend(["--mount", f"type=bind,src={certificate_path},dst=/run/vox-supabase-root.crt,readonly"])
            environment = {**environment, "PGSSLROOTCERT": "/run/vox-supabase-root.crt"}
        for key in environment:
            command.extend(["--env", key])
        command.extend(["postgres:18", "psql", "-X", "-tA", "-v", "ON_ERROR_STOP=1", "-c", "SELECT 1"])
        result = subprocess.run(command, env={**os.environ, **environment}, capture_output=True, timeout=120)
        if result.returncode or result.stdout.strip() != b"1":
            for marker, description in (
                (b"password authentication failed", "password authentication failed"),
                (b"certificate verify failed", "certificate verification failed"),
                (b"timeout expired", "connection timed out"),
                (b"Tenant or user not found", "database tenant or user not found"),
            ):
                if marker in result.stderr:
                    raise RuntimeError("Fresh database probe: " + description + "; no configuration changed.")
            raise RuntimeError("Fresh database connection probe failed; no configuration changed.")


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
        # Official client, one SELECT, no retained container or configuration.
        probe(environment)
        print("PASS: fresh authenticated database connection and SELECT 1.")
    except (RuntimeError, OSError, ValueError, subprocess.TimeoutExpired) as error:
        print(str(error) if isinstance(error, RuntimeError) else "Database probe failed; no configuration changed.", file=sys.stderr)
        sys.exit(1)
