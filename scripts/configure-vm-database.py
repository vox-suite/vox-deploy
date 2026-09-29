#!/usr/bin/env python3
"""Activate an approved database password only after a fresh verified login."""
import importlib.util
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import quote, urlsplit, urlunsplit

spec = importlib.util.spec_from_file_location(
    "database_probe", Path(__file__).with_name("check-vm-database.py")
)
database = importlib.util.module_from_spec(spec)
spec.loader.exec_module(database)
vm = database.vm


def current_database(base, local):
    value = vm.env_value(local, "DATABASE_URL")
    if value is None:
        value = vm.env_value(base, "DATABASE_URL")
    if not value:
        raise RuntimeError("Existing database configuration is missing; left unchanged.")
    return value


def candidate_url(current, password):
    if not password or len(password) > 256 or any(ord(c) < 33 or ord(c) > 126 for c in password):
        raise RuntimeError("Supplied database password is invalid; left unchanged.")
    parsed = urlsplit(current)
    if (parsed.scheme not in ("postgres", "postgresql") or parsed.fragment
            or any(c in parsed.query for c in "'\r\n")
            or parsed.hostname != "aws-0-ap-northeast-1.pooler.supabase.com"
            or parsed.port != 5432 or parsed.username != "postgres.fdnwhzrojorrspvulsgk"
            or parsed.path != "/postgres"):
        raise RuntimeError("Existing database is not the approved reference target; left unchanged.")
    # Percent encoding also prevents dotenv quote delimiters and interpolation.
    netloc = parsed.username + ":" + quote(password, safe="") + "@" + parsed.hostname + ":5432"
    return urlunsplit(parsed._replace(netloc=netloc))


def configure(base_path, local_path, password):
    def transform(base, local):
        current = current_database(base, local)
        candidate = candidate_url(current, password)
        # Verification occurs under the same lock as the protected atomic write.
        # A bad password, TLS failure or changed file leaves configuration intact.
        database.probe(database.connection_environment(candidate, current))
        if vm.env_value(local, "DATABASE_URL") == candidate:
            return local
        entry = "DATABASE_URL='" + candidate + "'\n"
        lines = local.splitlines(keepends=True)
        replaced = False
        for index, line in enumerate(lines):
            if re.match(r"^[ \t]*(?:export[ \t]+)?DATABASE_URL[ \t]*=", line):
                lines[index] = entry
                replaced = True
        if not replaced:
            if lines and not lines[-1].endswith("\n"):
                lines[-1] += "\n"
            lines.append(entry)
        return "".join(lines)

    changed = vm.update_configuration(base_path, local_path, transform)
    print("PASS: fresh verified database login; protected local configuration updated."
          if changed else "PASS: fresh verified database login; configuration already matches.")


if __name__ == "__main__":
    try:
        if os.geteuid() != 0 or sys.argv[1:] != ["--apply"]:
            raise RuntimeError("Run through sudo on the reference VM with --apply.")
        password = sys.stdin.read(258)
        # Clipboard sources sometimes terminate the value with one newline.
        if password.endswith("\n"):
            password = password[:-1]
        configure(Path("/etc/vox.env"), Path("/etc/vox.local.env"), password)
    except (RuntimeError, OSError, ValueError, subprocess.TimeoutExpired) as error:
        print(str(error) if isinstance(error, RuntimeError)
              else "Protected database configuration failed; inspect configuration before continuing.", file=sys.stderr)
        sys.exit(1)
