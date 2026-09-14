#!/usr/bin/env bash
set -euo pipefail

[[ $# -ge 4 ]] || {
  echo "usage: merge-env.sh CURRENT_ENV LEGACY_ENV OUTPUT_ENV KEY..." >&2
  exit 2
}

current_env=$1
legacy_env=$2
output_env=$3
shift 3

[[ -f $current_env ]] || {
  echo "current environment file is missing" >&2
  exit 1
}

cp "$current_env" "$output_env"
[[ -f $legacy_env ]] || exit 0

for key in "$@"; do
  [[ $key =~ ^[A-Z][A-Z0-9_]*$ ]] || {
    echo "invalid configuration key" >&2
    exit 2
  }
  if ! grep -Eq "^${key}=.+$" "$output_env" && grep -Eq "^${key}=.+$" "$legacy_env"; then
    grep -E "^${key}=.+$" "$legacy_env" | tail -n 1 >>"$output_env"
  fi
done
