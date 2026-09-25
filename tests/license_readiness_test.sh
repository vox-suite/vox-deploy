#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# License and Distribution Readiness Test Suite (E03 / Issue #2)
# ==============================================================================

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_dir"

echo "Running license and distribution readiness tests..."

# 1. License file verification
if [ ! -f "LICENSE" ]; then
    echo "FAIL: LICENSE file missing" >&2
    exit 1
fi
if ! grep -q "Apache License" "LICENSE" || ! grep -q "Version 2.0" "LICENSE"; then
    echo "FAIL: LICENSE does not specify Apache License, Version 2.0" >&2
    exit 1
fi
echo "✓ LICENSE is valid Apache License, Version 2.0"

# 2. Third-party notice verification
if [ ! -f "NOTICE" ]; then
    echo "FAIL: NOTICE file missing" >&2
    exit 1
fi
for component in "PostgreSQL" "Redis" "Caddy" "Rust Ecosystem Crates" "Node.js Ecosystem Packages" "Python Ecosystem Packages"; do
    if ! grep -q "$component" "NOTICE"; then
        echo "FAIL: NOTICE missing acknowledgment for $component" >&2
        exit 1
    fi
done
echo "✓ NOTICE contains required third-party software acknowledgments"

# 3. Security policy verification
if [ ! -f "SECURITY.md" ]; then
    echo "FAIL: SECURITY.md file missing" >&2
    exit 1
fi
if ! grep -q "security@voxagent.in" "SECURITY.md"; then
    echo "FAIL: SECURITY.md missing reporting email" >&2
    exit 1
fi
echo "✓ SECURITY.md documents vulnerability reporting and disclosure expectations"

# 4. Legal decision record and named accountable reviewer verification
DECISION_DOC="docs/legal-and-distribution-decision.md"
if [ ! -f "$DECISION_DOC" ]; then
    echo "FAIL: $DECISION_DOC missing" >&2
    exit 1
fi

if ! grep -q "Accountable Legal Reviewer.*Gowtham T G" "$DECISION_DOC"; then
    echo "FAIL: $DECISION_DOC missing named accountable legal reviewer" >&2
    exit 1
fi

if ! grep -q "Date.*2026-09-25" "$DECISION_DOC"; then
    echo "FAIL: $DECISION_DOC missing dated decision" >&2
    exit 1
fi

for repo in "vox-core" "vox-web" "vox-bridge" "agents" "vox-deploy" "vox-contracts"; do
    if ! grep -q "$repo" "$DECISION_DOC"; then
        echo "FAIL: $DECISION_DOC missing dependency audit record for $repo" >&2
        exit 1
    fi
done

if ! grep -q "Zero Copyleft" "$DECISION_DOC"; then
    echo "FAIL: $DECISION_DOC missing confirmation of zero copyleft licenses" >&2
    exit 1
fi
echo "✓ Legal decision record contains named legal reviewer, dated decision, and 6-repo audit"

# 5. Secret isolation audit across configuration, deploy, and script assets
PROHIBITED_PATTERNS=("sk_live_" "ghp_" "gho_" "vox_sk_")
TARGET_FILES=(compose.prod.yml compose.self-hosted.yml deployments/manifest.json .env.self-hosted.example scripts/backup.sh scripts/restore.sh scripts/deploy-vox.sh)
for pattern in "${PROHIBITED_PATTERNS[@]}"; do
    for target in "${TARGET_FILES[@]}"; do
        if grep -q "$pattern" "$target"; then
            echo "FAIL: prohibited secret pattern '$pattern' found in $target" >&2
            exit 1
        fi
    done
done
echo "✓ Zero prohibited secrets found in deployment and configuration assets"

echo "license and distribution readiness tests passed"
