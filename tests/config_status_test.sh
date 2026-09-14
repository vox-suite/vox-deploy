#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
test_dir=$(mktemp -d)
trap 'rm -rf "$test_dir"' EXIT

current_env="$test_dir/current.env"
legacy_env="$test_dir/legacy.env"
output="$test_dir/output"

printf '%s\n' \
  'DATABASE_URL=fake-current-database-secret' \
  'GEMINI_API_KEY=fake-current-gemini-secret' \
  'EMPTY_KEY=' >"$current_env"
printf '%s\n' \
  'GEMINI_API_KEY=fake-legacy-gemini-secret' \
  'TWILIO_AUTH_TOKEN=fake-legacy-twilio-secret' >"$legacy_env"

bash "$repo_dir/scripts/config-status.sh" "$current_env" "$legacy_env" \
  DATABASE_URL VOX_CORE_SERVICE_TOKEN GEMINI_API_KEY TWILIO_AUTH_TOKEN EMPTY_KEY >"$output"

cat >"$test_dir/expected" <<'EOF'
DATABASE_URL current=SET legacy=MISSING
VOX_CORE_SERVICE_TOKEN current=MISSING legacy=MISSING
GEMINI_API_KEY current=SET legacy=SET
TWILIO_AUTH_TOKEN current=MISSING legacy=SET
EMPTY_KEY current=MISSING legacy=MISSING
EOF

diff -u "$test_dir/expected" "$output"
if grep -q 'fake-' "$output"; then
  echo "configuration status exposed a secret value" >&2
  exit 1
fi

echo "configuration status tests passed"
