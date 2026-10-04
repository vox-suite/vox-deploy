import fcntl
import json
import os
from pathlib import Path
import re
import stat
import tempfile

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


