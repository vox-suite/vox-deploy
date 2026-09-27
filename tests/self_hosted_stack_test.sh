#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# Self-Hosted Reference Stack Test Suite (E47)
# ==============================================================================

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_dir"

echo "Running self-hosted reference stack validation tests..."

# 1. Compose file syntax and service definitions
COMPOSE_FILE="compose.self-hosted.yml"
if [ ! -f "$COMPOSE_FILE" ]; then
    echo "FAIL: $COMPOSE_FILE not found"
    exit 1
fi

REQUIRED_SERVICES=("postgres" "redis" "core-api" "core-worker" "bridge" "vox-web" "conformance-sandbox" "portable-agent")
for s in "${REQUIRED_SERVICES[@]}"; do
    if ! grep -q "^  ${s}:" "$COMPOSE_FILE"; then
        echo "FAIL: required service '${s}' missing from $COMPOSE_FILE"
        exit 1
    fi
done
echo "✓ compose.self-hosted.yml defines all required open services"

# Core's baseline migration executes CREATE EXTENSION vector. The reference
# PostgreSQL service must include pgvector before any Core process starts.
if ! grep -Eq '^[[:space:]]+image: pgvector/pgvector:pg18([[:space:]]|$)' "$COMPOSE_FILE"; then
    echo "FAIL: PostgreSQL 18 reference image must include pgvector" >&2
    exit 1
fi
echo "✓ PostgreSQL reference image includes pgvector"
if ! grep -Eq '^[[:space:]]+- postgres-data-pg18:/var/lib/postgresql([[:space:]]|$)' "$COMPOSE_FILE"; then
    echo "FAIL: PostgreSQL 18 data must use its own volume at /var/lib/postgresql" >&2
    exit 1
fi
if grep -Eq 'postgres-data:/var/lib/postgresql/data' "$COMPOSE_FILE"; then
    echo "FAIL: PostgreSQL 17 data volume cannot be mounted into PostgreSQL 18" >&2
    exit 1
fi
echo "✓ PostgreSQL 18 data has a dedicated volume at the supported mount path"
if ! grep -q "FROM spans" scripts/restore.sh || ! grep -q "FROM jobs" scripts/restore.sh; then
    echo "FAIL: restore integrity checks must use the current Core schema" >&2
    exit 1
fi
for role in anon authenticated service_role; do
    if ! grep -q "CREATE ROLE $role NOLOGIN" scripts/restore.sh; then
        echo "FAIL: restore must bootstrap the $role role before replaying pg_dump" >&2
        exit 1
    fi
done

# Redis 8.2 LTS reference image check
if ! grep -Eq '^[[:space:]]+image: redis:8.2-alpine([[:space:]]|$)' "$COMPOSE_FILE"; then
    echo "FAIL: Redis reference image must be redis:8.2-alpine" >&2
    exit 1
fi
echo "✓ Redis reference image is redis:8.2-alpine"

# 2. Manifest integrity check
MANIFEST="deployments/manifest.json"
if [ ! -f "$MANIFEST" ]; then
    echo "FAIL: $MANIFEST not found"
    exit 1
fi

REQUIRED_REPOS=("vox-core" "vox-bridge" "vox-web" "vox-deploy" "agents" "vox-contracts")
for r in "${REQUIRED_REPOS[@]}"; do
    if ! grep -q "\"${r}\"" "$MANIFEST"; then
        echo "FAIL: repository '${r}' missing from $MANIFEST"
        exit 1
    fi
done

for r in "vox-core" "vox-bridge" "vox-web" "agents" "vox-contracts"; do
    commit=$(python3 -c "import json; print(json.load(open('$MANIFEST'))['repositories']['$r']['commit'])")
    if [[ ! "$commit" =~ ^[0-9a-f]{40}$ ]]; then
        echo "FAIL: repository '$r' does not have a 40-character git commit in $MANIFEST"
        exit 1
    fi
done
echo "✓ deployments/manifest.json contains all six Vox repository entries with valid pinned commits"

# Check database versions in manifest
postgres_version=$(python3 -c "import json; print(next(d['version'] for d in json.load(open('$MANIFEST'))['stack']['databases'] if d['engine'] == 'postgresql'))")
if [ "$postgres_version" != "pg18" ]; then
    echo "FAIL: PostgreSQL version in $MANIFEST must match the pg18 image, got $postgres_version" >&2
    exit 1
fi
echo "✓ deployments/manifest.json specifies PostgreSQL pg18"
redis_version=$(python3 -c "import json; print(next(d['version'] for d in json.load(open('$MANIFEST'))['stack']['databases'] if d['engine'] == 'redis'))")
if [ "$redis_version" != "8.2-alpine" ]; then
    echo "FAIL: Redis version in $MANIFEST must be 8.2-alpine, got $redis_version" >&2
    exit 1
fi
echo "✓ deployments/manifest.json specifies Redis 8.2-alpine"

# 3. Secret isolation check: ensure no secrets are hardcoded in compose or manifest
PROHIBITED_STRINGS=("sk_live_" "ghp_" "supersecret")
for p in "${PROHIBITED_STRINGS[@]}"; do
    if grep -q "$p" "$COMPOSE_FILE" "$MANIFEST"; then
        echo "FAIL: prohibited secret pattern '$p' found in repository files"
        exit 1
    fi
done
echo "✓ Secret isolation check passed (no credentials in source files)"

# 4. Environment template check
if [ ! -f ".env.self-hosted.example" ]; then
    echo "FAIL: .env.self-hosted.example not found"
    exit 1
fi
echo "✓ .env.self-hosted.example exists"

# 5. Real backup/restore and independent-host acceptance are terminal gates.
# Their presence is checked here; running them requires a disposable live stack.
for script in backup.sh restore.sh second-host-acceptance-check.sh verify-platform-v1-release.sh; do
    test -f "scripts/$script" || { echo "FAIL: missing scripts/$script" >&2; exit 1; }
done
echo "✓ Release rehearsal scripts present; live evidence is still required"

echo "self-hosted stack tests passed"
