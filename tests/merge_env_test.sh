#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
test_dir=$(mktemp -d)
trap 'rm -rf "$test_dir"' EXIT

current_env="$test_dir/current.env"
legacy_env="$test_dir/legacy.env"
output="$test_dir/output.env"

printf '%s\n' \
  'DATABASE_URL=current-database' \
  'GEMINI_API_KEY=current-gemini' \
  'UNRELATED_SETTING=preserved' >"$current_env"
printf '%s\n' \
  'DATABASE_URL=legacy-database' \
  'GEMINI_API_KEY=legacy-gemini' \
  'EXA_API_KEY=legacy-exa' \
  'EMPTY_KEY=' \
  'IGNORED_SECRET=must-not-copy' >"$legacy_env"

bash "$repo_dir/scripts/merge-env.sh" "$current_env" "$legacy_env" "$output" \
  DATABASE_URL GEMINI_API_KEY EXA_API_KEY EMPTY_KEY

grep -Fxq 'DATABASE_URL=current-database' "$output"
grep -Fxq 'GEMINI_API_KEY=current-gemini' "$output"
grep -Fxq 'EXA_API_KEY=legacy-exa' "$output"
grep -Fxq 'UNRELATED_SETTING=preserved' "$output"
if grep -q '^EMPTY_KEY=' "$output"; then
  echo "empty legacy setting was copied" >&2
  exit 1
fi
if grep -q '^IGNORED_SECRET=' "$output"; then
  echo "unrequested legacy setting was copied" >&2
  exit 1
fi
[[ $(grep -c '^DATABASE_URL=' "$output") -eq 1 ]]
[[ $(grep -c '^GEMINI_API_KEY=' "$output") -eq 1 ]]

echo "environment merge tests passed"
