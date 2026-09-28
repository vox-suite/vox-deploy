#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
test_dir=$(mktemp -d)
trap 'rm -rf "$test_dir"' EXIT

cat >"$test_dir/vox.env" <<'EOF'
DATABASE_URL=postgresql://example.invalid/postgres
VOX_AUTH_TOKEN=test-token
GEMINI_API_KEY=test-gemini
EXA_API_KEY=test-exa
GOOGLE_MAPS_API_KEY=test-maps
TWILIO_ACCOUNT_SID=test-sid
TWILIO_AUTH_TOKEN=test-auth
TWILIO_FROM_NUMBER=+10000000000
ASSEMBLYAI_API_KEY=test-assembly
SARVAM_API_KEY=test-sarvam
EOF

digest_core=$(printf 'a%.0s' {1..64})
digest_bridge=$(printf 'b%.0s' {1..64})
export CORE_IMAGE="ghcr.io/vox-suite/vox-deploy/core@sha256:$digest_core"
export BRIDGE_IMAGE="ghcr.io/vox-suite/vox-deploy/bridge@sha256:$digest_bridge"
export VOX_ENV_FILE="$test_dir/vox.env"

if ! command -v docker >/dev/null 2>&1; then
    echo "docker command not available; skipping live compose schema check"
    exit 0
fi

docker compose -f "$repo_dir/compose.prod.yml" config --format json >"$test_dir/compose.json"

jq -e '.name == "vox"' "$test_dir/compose.json" >/dev/null
jq -e '.services.redis.command == ["redis-server", "--appendonly", "yes", "--appendfsync", "everysec"]' "$test_dir/compose.json" >/dev/null
jq -e '.services.redis.volumes[0].source == "redis-data"' "$test_dir/compose.json" >/dev/null
jq -e '.services.bridge.ports == [{"mode":"ingress","target":3000,"published":"3000","protocol":"tcp","host_ip":"127.0.0.1"}]' "$test_dir/compose.json" >/dev/null
jq -e '.services["core-api"].ports == [{"mode":"ingress","target":3001,"published":"3001","protocol":"tcp","host_ip":"127.0.0.1"}]' "$test_dir/compose.json" >/dev/null
jq -e '.services["core-worker"].ports == null' "$test_dir/compose.json" >/dev/null
jq -e '.services["core-api"].environment.REDIS_URL == "redis://redis:6379"' "$test_dir/compose.json" >/dev/null
jq -e '.services.bridge.environment.VOX_CORE_URL == "http://core-api:3001"' "$test_dir/compose.json" >/dev/null
jq -e '.services["core-worker"].environment.VOX_BRIDGE_URL == "http://bridge:3000"' "$test_dir/compose.json" >/dev/null
jq -e '.services["core-api"].healthcheck.test == ["CMD", "curl", "--fail", "http://localhost:3001/health/ready"]' "$test_dir/compose.json" >/dev/null
jq -e '.services.bridge.healthcheck.test == ["CMD", "curl", "--fail", "http://localhost:3000/health/ready"]' "$test_dir/compose.json" >/dev/null

echo "compose tests passed"
