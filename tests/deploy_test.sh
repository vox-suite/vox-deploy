#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
test_root=$(mktemp -d)
trap 'rm -rf "$test_root"' EXIT

for command in docker curl systemctl flock; do
  ln -s "$repo_dir/tests/fakes/command" "$test_root/$command"
done

sha_core=1111111111111111111111111111111111111111
sha_bridge=2222222222222222222222222222222222222222
sha_bridge_next=3333333333333333333333333333333333333333
image_core="ghcr.io/vox-suite/vox-core@sha256:$(printf 'a%.0s' {1..64})"
image_bridge="ghcr.io/vox-suite/vox-bridge@sha256:$(printf 'b%.0s' {1..64})"
image_bridge_next="ghcr.io/vox-suite/vox-bridge@sha256:$(printf 'c%.0s' {1..64})"

fail() {
  echo "FAIL: $1" >&2
  exit 1
}

setup_case() {
  case_dir=$(mktemp -d "$test_root/case.XXXXXX")
  mkdir -p "$case_dir/root/state"
  command_log="$case_dir/commands.log"
  : >"$command_log"
  token_file="$case_dir/ghcr-token"
  printf 'test-token\n' >"$token_file"
  chmod 600 "$token_file"
  env_file="$case_dir/vox.env"
  cat >"$env_file" <<'EOF'
DATABASE_URL=postgresql://example.invalid/postgres
VOX_CORE_SERVICE_TOKEN=test-token
GEMINI_API_KEY=test-gemini
EXA_API_KEY=test-exa
GOOGLE_MAPS_API_KEY=test-maps
TWILIO_ACCOUNT_SID=test-sid
TWILIO_AUTH_TOKEN=test-auth
TWILIO_FROM_NUMBER=+10000000000
ASSEMBLYAI_API_KEY=test-assembly
SARVAM_API_KEY=test-sarvam
EOF
  chmod 600 "$env_file"
}

deploy() {
  PATH="$test_root:$PATH" \
    VOX_ROOT="$case_dir/root" \
    VOX_STATE_DIR="$case_dir/root/state" \
    VOX_ENV_FILE="$env_file" \
    VOX_COMPOSE_FILE="$repo_dir/compose.prod.yml" \
    VOX_COMMAND_LOG="$command_log" \
    VOX_SKIP_FILE_SECURITY_CHECK=1 \
    VOX_PUBLIC_HEALTH_URL=https://api.voxagent.in/health \
    "$repo_dir/scripts/deploy-vox.sh" "$@"
}

deploy_full() {
  deploy \
    --core-sha "$sha_core" \
    --core-image "$image_core" \
    --bridge-sha "$sha_bridge" \
    --bridge-image "$image_bridge" \
    --ghcr-user vox-deploy \
    --ghcr-token-file "$token_file"
}

setup_case
if deploy --component invalid --sha "$sha_core" --image "$image_core" --ghcr-user user --ghcr-token-file "$token_file"; then
  fail "invalid component was accepted"
fi
[[ ! -s $command_log ]] || fail "invalid input ran external commands"

setup_case
sed -i.bak '/^DATABASE_URL=/d' "$env_file"
if deploy_full; then
  fail "missing configuration was accepted"
fi
! grep -q '^systemctl ' "$command_log" || fail "missing config touched systemd"

setup_case
if VOX_FAKE_FAILURE=pull deploy_full; then
  fail "failed pull was accepted"
fi
! grep -q '^systemctl stop' "$command_log" || fail "pull failure stopped systemd"

setup_case
VOX_SYSTEMD_ACTIVE=1 deploy_full
core_line=$(grep -n 'compose.*up -d --wait.*redis core-api' "$command_log" | cut -d: -f1)
stop_line=$(grep -n '^systemctl stop vox-bridge.service' "$command_log" | cut -d: -f1)
bridge_line=$(grep -n 'compose.*up -d --wait.*bridge' "$command_log" | head -1 | cut -d: -f1)
worker_line=$(grep -n 'compose.*up -d.*core-worker' "$command_log" | cut -d: -f1)
[[ $core_line -lt $stop_line && $stop_line -lt $bridge_line && $bridge_line -lt $worker_line ]] || fail "first rollout order was unsafe"
grep -q "CORE_SHA=$sha_core" "$case_dir/root/state/current.env" || fail "Core release was not promoted"
grep -q "BRIDGE_SHA=$sha_bridge" "$case_dir/root/state/current.env" || fail "Bridge release was not promoted"

setup_case
request_file="$case_dir/request.env"
cat >"$request_file" <<EOF
CORE_SHA=$sha_core
CORE_IMAGE=$image_core
BRIDGE_SHA=$sha_bridge
BRIDGE_IMAGE=$image_bridge
GHCR_USER=vox-deploy
EOF
VOX_SYSTEMD_ACTIVE=1 deploy --request-file "$request_file" --ghcr-token-file "$token_file"
grep -q "CORE_SHA=$sha_core" "$case_dir/root/state/current.env" || fail "request file was not deployed"

setup_case
if VOX_SYSTEMD_ACTIVE=1 VOX_FAKE_FAILURE=bridge-health deploy_full; then
  fail "failed first Bridge rollout was accepted"
fi
grep -q '^systemctl restart vox-bridge.service' "$command_log" || fail "systemd Bridge was not restored"

setup_case
source "$repo_dir/scripts/release.sh"
write_full_release "$sha_core" "$image_core" "$sha_bridge" "$image_bridge" "$case_dir/root/state/current.env"
VOX_SYSTEMD_ACTIVE=0 deploy \
  --component bridge \
  --sha "$sha_bridge_next" \
  --image "$image_bridge_next" \
  --ghcr-user vox-deploy \
  --ghcr-token-file "$token_file"
grep -q "CORE_SHA=$sha_core" "$case_dir/root/state/current.env" || fail "unchanged Core was not preserved"
grep -q "BRIDGE_SHA=$sha_bridge_next" "$case_dir/root/state/current.env" || fail "new Bridge was not promoted"
grep -q "BRIDGE_SHA=$sha_bridge" "$case_dir/root/state/previous.env" || fail "previous release was not retained"

setup_case
write_full_release "$sha_core" "$image_core" "$sha_bridge" "$image_bridge" "$case_dir/root/state/current.env"
if VOX_SYSTEMD_ACTIVE=0 VOX_FAKE_FAILURE=public-health deploy \
  --component bridge \
  --sha "$sha_bridge_next" \
  --image "$image_bridge_next" \
  --ghcr-user vox-deploy \
  --ghcr-token-file "$token_file"; then
  fail "failed public health check was accepted"
fi
grep -q "BRIDGE_IMAGE=$image_bridge" "$case_dir/root/state/current.env" || fail "previous release was not restored"
rollback_count=$(grep -c 'compose.*up -d --wait.*redis core-api bridge' "$command_log")
[[ $rollback_count -eq 1 ]] || fail "Compose rollback did not run exactly once"

echo "deployment tests passed"
