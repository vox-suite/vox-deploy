#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_dir"

# Unit checks for fail-closed behavior. Passing these does not constitute a
# terminal release rehearsal or satisfy any external/provider gate.
python3 -c 'import ast, pathlib; ast.parse(pathlib.Path("scripts/verify-v1-evidence.py").read_text())'

if VOX_RELEASE_EVIDENCE=/nonexistent python3 scripts/verify-v1-evidence.py >/dev/null 2>&1; then
  echo "release verifier accepted missing evidence" >&2
  exit 1
fi
if SECOND_HOST_REPO=/nonexistent SECOND_HOST_SHA=1111111111111111111111111111111111111111 \
  VOX_CORE_URL=http://127.0.0.1:3001 bash scripts/second-host-acceptance-check.sh >/dev/null 2>&1; then
  echo "reference-host gate accepted a missing host" >&2
  exit 1
fi
if VOX_RELEASE_EVIDENCE=/nonexistent bash scripts/verify-platform-v1-release.sh >/dev/null 2>&1; then
  echo "terminal release gate accepted missing prerequisites" >&2
  exit 1
fi

echo "release gate fail-closed checks passed (release evidence remains required)"
