#!/usr/bin/env bash
set -euo pipefail

[[ $# -ge 3 ]] || {
  echo "usage: config-status.sh CURRENT_ENV LEGACY_ENV KEY..." >&2
  exit 2
}

current_env=$1
legacy_env=$2
shift 2

status_for() {
  local file=$1
  local key=$2
  if [[ -f $file ]] && grep -Eq "^${key}=.+$" "$file"; then
    printf SET
  else
    printf MISSING
  fi
}

for key in "$@"; do
  [[ $key =~ ^[A-Z][A-Z0-9_]*$ ]] || {
    echo "invalid configuration key" >&2
    exit 2
  }
  printf '%s current=%s legacy=%s\n' \
    "$key" "$(status_for "$current_env" "$key")" "$(status_for "$legacy_env" "$key")"
done
