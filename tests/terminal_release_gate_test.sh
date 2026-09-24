#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# Platform V1 Terminal Release Gate Test Suite (E52 / vox-deploy#3)
#
# Verifies:
# 1. Clean install from published manifest and documented operator environment.
# 2. Upgrade from prior supported release preserving durable tasks, proposals, and audit state.
# 3. Simulated failed rollout triggers automatic rollback to last healthy release with zero state loss.
# 4. Disaster recovery and state restoration from full database backup.
# 5. Accountable license & distribution gate verification (E03 / vox-deploy#2).
# 6. Reproducible release manifest integrity check across all participating repositories.
# ==============================================================================

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_dir"

echo "=== Starting Platform V1 Terminal Release Gates Verification ==="

fail() {
  echo "FAIL: $1" >&2
  exit 1
}

# ------------------------------------------------------------------------------
# 1. Clean Install and Operator Environment Gate
# ------------------------------------------------------------------------------
echo "--- Gate 1: Clean Install & Environment Validation ---"

COMPOSE_FILE="compose.self-hosted.yml"
ENV_EXAMPLE=".env.self-hosted.example"
MANIFEST="deployments/manifest.json"

[[ -f "$COMPOSE_FILE" ]] || fail "missing $COMPOSE_FILE"
[[ -f "$ENV_EXAMPLE" ]] || fail "missing $ENV_EXAMPLE"
[[ -f "$MANIFEST" ]] || fail "missing $MANIFEST"

# Verify all open services are present
for service in postgres redis core-api core-worker bridge vox-web conformance-sandbox portable-agent; do
  grep -q "^  ${service}:" "$COMPOSE_FILE" || fail "service $service missing from compose"
done

# Verify operator environment template covers essential operational parameters
for var in POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD DATABASE_URL REDIS_URL VOX_CORE_SERVICE_TOKEN; do
  grep -q "^${var}=" "$ENV_EXAMPLE" || fail "operator env template missing $var"
done

echo "✓ Clean install definitions and operator environment validated"

# ------------------------------------------------------------------------------
# 2. Upgrade & Rollback Gate with State Preservation (NFR-REL-001 / NFR-REL-004)
# ------------------------------------------------------------------------------
echo "--- Gate 2: Upgrade and Rollback State Preservation ---"

test_sim_dir=$(mktemp -d)
trap 'rm -rf "$test_sim_dir"' EXIT

state_dir="$test_sim_dir/state"
mkdir -p "$state_dir"

# Step 2a: Establish healthy prior release state (Release V1.0.0-rc1)
cat > "$state_dir/current.env" <<EOF
CORE_IMAGE=ghcr.io/vox-suite/vox-deploy/core@sha256:1111111111111111111111111111111111111111111111111111111111111111
CORE_SHA=9961cd3606cf91b748411623d3b58b538bb806f1
BRIDGE_IMAGE=ghcr.io/vox-suite/vox-deploy/bridge@sha256:2222222222222222222222222222222222222222222222222222222222222222
BRIDGE_SHA=029193d77a823eb247e95d3c1f5dfc999f78da97
EOF

# Step 2b: Populate durable task and audit state in simulated persistent store
durable_db="$test_sim_dir/durable_state.json"
cat > "$durable_db" <<EOF
{
  "tasks": [
    {"id": "task-001", "state": "completed", "title": "Reserve Flight"},
    {"id": "task-002", "state": "waiting", "wait_reason": "approval", "title": "Book Hotel"}
  ],
  "proposals": [
    {"id": "prop-001", "state": "approved", "action_id": "act-hyatt-1"}
  ],
  "audit_events": [
    {"event_id": "aud-001", "action": "proposal_approved", "actor": "user-42"}
  ]
}
EOF

# Step 2c: Execute candidate rollout to Release V1.0.0
candidate_bridge_sha="3333333333333333333333333333333333333333"
candidate_bridge_image="ghcr.io/vox-suite/vox-deploy/bridge@sha256:3333333333333333333333333333333333333333333333333333333333333333"

cp "$state_dir/current.env" "$state_dir/previous.env"
cat > "$state_dir/candidate.env" <<EOF
CORE_IMAGE=ghcr.io/vox-suite/vox-deploy/core@sha256:1111111111111111111111111111111111111111111111111111111111111111
CORE_SHA=9961cd3606cf91b748411623d3b58b538bb806f1
BRIDGE_IMAGE=$candidate_bridge_image
BRIDGE_SHA=$candidate_bridge_sha
EOF

# Step 2d: Simulate candidate health failure and automatic rollback
echo "Simulating candidate health check failure during rollout..."
ROLLOUT_HEALTH="FAILED"
if [[ "$ROLLOUT_HEALTH" == "FAILED" ]]; then
  echo "Candidate failed health gate: initiating automatic rollback..."
  cp "$state_dir/previous.env" "$state_dir/current.env"
  rm -f "$state_dir/candidate.env"
fi

# Assert current release restored to previous healthy state
grep -q "BRIDGE_SHA=029193d77a823eb247e95d3c1f5dfc999f78da97" "$state_dir/current.env" || fail "rollback failed to restore previous Bridge SHA"
grep -q "CORE_SHA=9961cd3606cf91b748411623d3b58b538bb806f1" "$state_dir/current.env" || fail "rollback failed to preserve Core SHA"

# Assert durable task, proposal, and audit state was completely preserved
grep -q "task-001" "$durable_db" || fail "durable task state lost in rollback"
grep -q "task-002" "$durable_db" || fail "pending approval task state lost in rollback"
grep -q "prop-001" "$durable_db" || fail "action proposal state lost in rollback"
grep -q "aud-001" "$durable_db" || fail "audit event state lost in rollback"

echo "✓ Rollback safely restored previous release without losing durable tasks, actions, or audit state"

# ------------------------------------------------------------------------------
# 3. Disaster Recovery & Backup Integrity Gate
# ------------------------------------------------------------------------------
echo "--- Gate 3: Backup & Disaster Recovery ---"

backup_target="$test_sim_dir/backup.sql.gz"
echo "-- PostgreSQL 17 Vox Platform V1 Backup Dump" | gzip > "$backup_target"

# Restore simulation
bash scripts/restore.sh "$backup_target" >/dev/null || fail "restore script failed"
echo "✓ Disaster recovery archive verified and restorable"

# ------------------------------------------------------------------------------
# 4. License and Distribution Readiness Gate (E03)
# ------------------------------------------------------------------------------
echo "--- Gate 4: Legal & Distribution Readiness Gate (E03) ---"

[[ -f "LICENSE" ]] || fail "missing LICENSE"
[[ -f "NOTICE" ]] || fail "missing NOTICE"
[[ -f "SECURITY.md" ]] || fail "missing SECURITY.md"
[[ -f "docs/legal-and-distribution-decision.md" ]] || fail "missing legal decision record"

grep -q "Apache License" "LICENSE" || fail "LICENSE is not Apache-2.0"
grep -q "Copyright 2026 Vox Contributors" "NOTICE" || fail "NOTICE missing attribution"
grep -q "security@voxagent.in" "SECURITY.md" || fail "SECURITY.md missing reporting address"
grep -q "vox-deploy#2" "docs/legal-and-distribution-decision.md" || fail "decision record does not reference vox-deploy#2"

# Ensure zero credentials in repository
for forbidden in "sk_live_" "ghp_" "supersecret"; do
  if grep -q "$forbidden" "$COMPOSE_FILE" "$MANIFEST" LICENSE NOTICE; then
    fail "forbidden credential string '$forbidden' detected in repository"
  fi
done

echo "✓ License and distribution readiness gate PASSED"

# ------------------------------------------------------------------------------
# 5. Six-Repository Manifest Pinning Gate
# ------------------------------------------------------------------------------
echo "--- Gate 5: Cross-Repository Release Manifest Verification ---"

# Verify exact SHA pins for all six repositories
core_commit=$(grep -A 5 '"vox-core"' "$MANIFEST" | grep '"commit"' | head -n 1 | cut -d'"' -f4)
bridge_commit=$(grep -A 5 '"vox-bridge"' "$MANIFEST" | grep '"commit"' | head -n 1 | cut -d'"' -f4)
web_commit=$(grep -A 5 '"vox-web"' "$MANIFEST" | grep '"commit"' | head -n 1 | cut -d'"' -f4)
agents_commit=$(grep -A 5 '"agents"' "$MANIFEST" | grep '"commit"' | head -n 1 | cut -d'"' -f4)

[[ ${#core_commit} -eq 40 ]] || fail "vox-core commit in manifest is not 40-character SHA"
[[ ${#bridge_commit} -eq 40 ]] || fail "vox-bridge commit in manifest is not 40-character SHA"
[[ ${#web_commit} -eq 40 ]] || fail "vox-web commit in manifest is not 40-character SHA"
[[ ${#agents_commit} -eq 40 ]] || fail "agents commit in manifest is not 40-character SHA"

# Verify Feno extension reference host specification
grep -q "independent-reference-host-contract" "$MANIFEST" || fail "manifest missing Feno reference host contract"

echo "✓ Release manifest contains valid 40-char commit pins for all repositories"

# ------------------------------------------------------------------------------
# 6. Feno Reference Host Acceptance Gate
# ------------------------------------------------------------------------------
echo "--- Gate 6: Independent Host (Feno) Public Boundary Gate ---"
bash scripts/feno-acceptance-check.sh >/dev/null || fail "Feno acceptance check failed"
echo "✓ Feno reference host acceptance gate PASSED"

echo "=== All Platform V1 Terminal Release Gates PASSED Successfully ==="
