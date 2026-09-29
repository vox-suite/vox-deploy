#!/usr/bin/env python3
"""Configure the reference VM's GitHub App through protected stdin."""
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile

spec = importlib.util.spec_from_file_location(
    "github_oauth", Path(__file__).with_name("configure-github-oauth.py")
)
oauth = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oauth)


def protected_text(path):
    try:
        info = path.lstat()
    except FileNotFoundError:
        return ""
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o600:
        raise RuntimeError("Configuration must be a regular owner-only file; left unchanged.")
    return path.read_text()


def env_value(text, name):
    matches = re.findall(r"^[ \t]*(?:export[ \t]+)?" + re.escape(name) + r"[ \t]*=[ \t]*(.*)$", text, re.MULTILINE)
    if len(matches) > 1:
        raise RuntimeError("Duplicate configuration entries; left unchanged.")
    if not matches:
        return None
    value = matches[0].strip()
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1]
    if value.startswith('"') and value.endswith('"'):
        try:
            return json.loads(value)
        except ValueError:
            raise RuntimeError("Invalid quoted configuration; left unchanged.") from None
    return value


def merge_text(base, local, secret):
    key = env_value(local, "VOX_CREDENTIAL_KEY")
    if key is None:
        key = env_value(base, "VOX_CREDENTIAL_KEY")
    if not key:
        raise RuntimeError("Persistent credential encryption key is missing; left unchanged.")
    raw = env_value(local, oauth.SECRET_NAME)
    if raw is None:
        raw = env_value(base, oauth.SECRET_NAME)
    try:
        existing = json.loads(raw) if raw else {}
    except ValueError:
        raise RuntimeError("Existing OAuth JSON is invalid; left unchanged.") from None
    merged = oauth.merged_configuration(existing, secret)
    if merged == existing and env_value(local, oauth.SECRET_NAME) is not None:
        return local
    # Single quotes stop Compose interpolation; JSON escapes avoid embedded
    # dotenv quote delimiters without changing the provider values.
    payload = json.dumps(merged, separators=(",", ":")).replace("'", "\\u0027")
    entry = oauth.SECRET_NAME + "='" + payload + "'\n"
    lines = local.splitlines(keepends=True)
    replaced = False
    for index, line in enumerate(lines):
        if re.match(r"^[ \t]*(?:export[ \t]+)?" + oauth.SECRET_NAME + r"[ \t]*=", line):
            lines[index] = entry
            replaced = True
    if not replaced:
        if lines and not lines[-1].endswith("\n"):
            lines[-1] += "\n"
        lines.append(entry)
    return "".join(lines)


def update_configuration(base_path, local_path, transform):
    # Keep cooperating updates serialized, and never follow a lock symlink.
    lock = os.open(str(local_path) + ".lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(lock, "w") as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o600:
            raise RuntimeError("Configuration lock is not owner-only; left unchanged.")
        fcntl.flock(handle, fcntl.LOCK_EX)
        base, local = protected_text(base_path), protected_text(local_path)
        updated = transform(base, local)
        if updated == local:
            return False
        fd, temporary = tempfile.mkstemp(prefix=".vox-local-env-", dir=local_path.parent)
        try:
            with os.fdopen(fd, "w") as output:
                output.write(updated)
                output.flush()
                os.fsync(output.fileno())
            if protected_text(base_path) != base or protected_text(local_path) != local:
                raise RuntimeError("Configuration changed concurrently; left unchanged.")
            os.replace(temporary, local_path)
            directory = os.open(local_path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return True


def configure(base_path, local_path, secret):
    changed = update_configuration(base_path, local_path, lambda base, local: merge_text(base, local, secret))
    print("GitHub OAuth stored in the protected local configuration; recreate Core to activate."
          if changed else "GitHub OAuth configuration already matches; no file changed.")


if __name__ == "__main__":
    try:
        if os.geteuid() != 0:
            raise RuntimeError("Run through sudo on the deployment VM.")
        base_path, local_path = Path("/etc/vox.env"), Path("/etc/vox.local.env")
        if sys.argv[1:] == ["--inspect"]:
            base, local = protected_text(base_path), protected_text(local_path)
            for name in ("VOX_CREDENTIAL_KEY", oauth.SECRET_NAME):
                value = env_value(local, name)
                if value is None:
                    value = env_value(base, name)
                print(name + ": " + ("set" if value else "absent"))
        elif sys.argv[1:] == ["--apply"]:
            secret = sys.stdin.read(258)
            if len(secret.strip()) > 256:
                raise RuntimeError("The supplied App client secret is invalid.")
            configure(base_path, local_path, secret.strip())
        else:
            raise RuntimeError("Choose --inspect or --apply.")
    except (RuntimeError, OSError, UnicodeError) as error:
        # Never render OS errors, payloads or tracebacks containing configuration.
        print(str(error) if isinstance(error, RuntimeError) else "Protected configuration operation failed.", file=sys.stderr)
        sys.exit(1)
