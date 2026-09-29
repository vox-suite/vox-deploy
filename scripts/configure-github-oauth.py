#!/usr/bin/env python3
"""Merge one approved App credential into GSM without exposing secret values."""
import json
import os
import re
import subprocess
import sys

SECRET_NAME = "VOX_MCP_OAUTH_CLIENTS"
CLIENT_ID = "Iv23liz7tKHVAjCoBD2W"


def merged_configuration(existing, secret):
    if not isinstance(existing, dict) or any(
        not isinstance(value, dict) for value in existing.values()
    ):
        raise RuntimeError("Existing OAuth configuration is invalid; left unchanged.")
    if not re.fullmatch(r"[A-Za-z0-9_-]{20,256}", secret):
        raise RuntimeError("The supplied App client secret is missing or invalid.")
    return {
        **existing,
        "api.githubcopilot.com": {
            "issuer": "https://github.com/login/oauth",
            "client_id": CLIENT_ID,
            "client_secret": secret,
            "token_endpoint_auth_method": "client_secret_post",
            "scopes": [],
            "send_resource": True,
        },
    }


def configure(project, secret, run=subprocess.run):
    if not re.fullmatch(r"[a-z][a-z0-9-]{4,61}[a-z0-9]", project):
        raise RuntimeError("GCP_PROJECT_ID is missing or invalid.")
    # Validate before any remote mutation.
    merged_configuration({}, secret)
    args = ["--project=" + project, "--quiet"]
    described = run(
        ["gcloud", "secrets", "describe", SECRET_NAME, *args],
        capture_output=True, check=False,
    )
    exists = described.returncode == 0
    if not exists and b"NOT_FOUND" not in described.stderr:
        raise RuntimeError("Cannot inspect GSM secret; configuration left unchanged.")
    existing = {}
    if exists:
        current = run(
            ["gcloud", "secrets", "versions", "access", "latest",
             "--secret=" + SECRET_NAME, *args],
            capture_output=True, check=False,
        )
        if current.returncode:
            raise RuntimeError("Cannot read existing OAuth configuration; left unchanged.")
        try:
            existing = json.loads(current.stdout)
        except (ValueError, UnicodeError):
            raise RuntimeError("Existing OAuth JSON is invalid; left unchanged.") from None
    merged = merged_configuration(existing, secret)
    if merged == existing:
        print("GitHub OAuth configuration already matches; no version added.")
        return
    payload = json.dumps(merged, separators=(",", ":")).encode()
    if exists:
        command = ["gcloud", "secrets", "versions", "add", SECRET_NAME,
                   "--data-file=-", *args]
    else:
        command = ["gcloud", "secrets", "create", SECRET_NAME,
                   "--replication-policy=automatic", "--data-file=-", *args]
    result = run(command, input=payload, capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError("GSM configuration write failed; temporary transfer secret retained.")
    print("Configured GitHub OAuth in GSM; other provider entries preserved.")


if __name__ == "__main__":
    try:
        configure(
            os.environ.get("GCP_PROJECT_ID", ""),
            os.environ.pop("VOX_GITHUB_OAUTH_CLIENT_SECRET", ""),
        )
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
