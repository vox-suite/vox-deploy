#!/usr/bin/env python3
"""Provision the reference Bridge's durable Core host credential locally."""
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from uuid import UUID

spec = importlib.util.spec_from_file_location(
    "vm_configuration", Path(__file__).with_name("configure-github-oauth-vm.py")
)
vm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vm)
API = "http://127.0.0.1:3001"
AUDIENCE = "vox-host:production:vox-bridge"
FIELDS = ("VOX_HOST_CREDENTIAL_ID", "VOX_HOST_AUDIENCE", "VOX_HOST_SECRET")


def validate(values):
    try:
        UUID(values[0])
    except (ValueError, TypeError, AttributeError):
        raise RuntimeError("Bridge host credential ID is invalid; left unchanged.") from None
    if values[1] != AUDIENCE or not re.fullmatch(r"[0-9a-f]{64}", values[2] or ""):
        raise RuntimeError("Bridge host credential does not match the reference host; left unchanged.")


def request(path, token, body=None):
    data = json.dumps(body).encode() if body is not None else b""
    req = Request(API + path, data=data, method="POST", headers={
        "Authorization": "Bearer " + token, "Content-Type": "application/json",
    })
    with urlopen(req, timeout=15) as response:
        raw = response.read(32769)
    if len(raw) > 32768:
        raise RuntimeError("Core host response is invalid; credential values withheld.")
    return json.loads(raw) if raw else None


def configure(base_path, bridge_path):
    issued = None
    token = None
    def transform(base, local):
        nonlocal issued, token
        values = [vm.env_value(local, name) for name in FIELDS]
        if all(value is None for value in values):
            values = [vm.env_value(base, name) for name in FIELDS]
        if any(value is not None for value in values):
            if not all(values):
                raise RuntimeError("Bridge host credential is incomplete; left unchanged.")
            validate(values)
            return local
        token = vm.env_value(base, "VOX_AUTH_TOKEN")
        if not token:
            raise RuntimeError("Core bootstrap credential is missing; left unchanged.")
        result = request("/v1/host-apps", token, {
            "deployment_external_key": "production", "host_app_external_key": "vox-bridge",
            "allowed_origins": [],
        })
        credential = result["credential"]
        values = [credential["credential_id"], credential["audience"], credential["secret"]]
        issued = str(UUID(values[0]))
        validate(values)
        if local and not local.endswith("\n"):
            local += "\n"
        return local + "".join(name + "='" + value + "'\n" for name, value in zip(FIELDS, values))

    try:
        changed = vm.update_configuration(base_path, bridge_path, transform)
    except Exception:
        if issued is not None:
            try:
                stored = vm.env_value(vm.protected_text(bridge_path), FIELDS[0]) == issued
            except Exception:
                stored = False
            # A directory fsync may fail after replacement. Do not revoke a
            # credential which is already stored in its protected destination.
            try:
                if not stored:
                    request("/v1/host-app-credentials/" + issued + "/revoke", token)
            except Exception:
                raise RuntimeError("Bridge credential could not be stored or revoked; operator recovery required.") from None
        raise
    print("Bridge host credential stored in its root-only configuration."
          if changed else "Bridge host credential already configured; no credential issued.")


if __name__ == "__main__":
    try:
        if os.geteuid() != 0 or sys.argv[1:]:
            raise RuntimeError("Run through sudo on the reference VM without arguments.")
        configure(Path("/etc/vox.env"), Path("/etc/vox.bridge.env"))
    except HTTPError as error:
        # HTTP status is enough to distinguish rejected registration from
        # protected-file failure. Never print bodies, URLs, or headers.
        print("Bridge host configuration failed: Core HTTP " + str(error.code)
              + "; credential values withheld.", file=sys.stderr)
        sys.exit(1)
    except Exception as error:
        # Exception messages can embed tokens, response bodies or file values.
        print("Bridge host configuration failed: " + type(error).__name__
              + "; credential values withheld.", file=sys.stderr)
        sys.exit(1)
