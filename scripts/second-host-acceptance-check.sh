#!/usr/bin/env bash
set -euo pipefail

# The reference host must be a separate checkout with its own executable
# public-boundary acceptance suite. An absent host is a release blocker.
: "${SECOND_HOST_REPO:?Set SECOND_HOST_REPO to the independent reference-host checkout}"
: "${SECOND_HOST_SHA:?Set SECOND_HOST_SHA to the tested 40-character commit}"
: "${VOX_CORE_URL:?Set VOX_CORE_URL to the running Core API}"

[[ $SECOND_HOST_SHA =~ ^[0-9a-f]{40}$ ]] || {
  echo "SECOND_HOST_SHA must be a 40-character commit" >&2
  exit 1
}
git -C "$SECOND_HOST_REPO" rev-parse --is-inside-work-tree >/dev/null 2>&1 || {
  echo "Independent reference-host Git checkout is missing" >&2
  exit 1
}
[[ $(git -C "$SECOND_HOST_REPO" rev-parse HEAD) == "$SECOND_HOST_SHA" ]] || {
  echo "Reference-host checkout does not match SECOND_HOST_SHA" >&2
  exit 1
}
[[ -x $SECOND_HOST_REPO/scripts/acceptance.sh ]] || {
  echo "Reference host must supply executable scripts/acceptance.sh" >&2
  exit 1
}
curl --fail --silent --show-error "$VOX_CORE_URL/health/ready" >/dev/null
"$SECOND_HOST_REPO/scripts/acceptance.sh"
