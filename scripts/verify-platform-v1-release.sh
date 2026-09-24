#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_dir"

command -v docker >/dev/null || { echo "Docker Compose is required for the release gate" >&2; exit 1; }
docker compose version >/dev/null
: "${VOX_RELEASE_EVIDENCE:?Set VOX_RELEASE_EVIDENCE to the completed external attestation}"
: "${SECOND_HOST_REPO:?Set SECOND_HOST_REPO to the independent reference host}"
: "${SECOND_HOST_SHA:?Set SECOND_HOST_SHA to its tested revision}"
: "${VOX_CORE_URL:?Set VOX_CORE_URL to the running Core API}"

bash scripts/second-host-acceptance-check.sh
python3 scripts/verify-v1-evidence.py
