#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
source "$repo_dir/scripts/release.sh"

fail() {
  echo "FAIL: $1" >&2
  exit 1
}

assert_rejected() {
  if "$@" >/dev/null 2>&1; then
    fail "command unexpectedly succeeded: $*"
  fi
}

assert_file() {
  local expected=$1
  local actual=$2
  diff -u "$expected" "$actual" || fail "release file differed"
}

sha_core=1111111111111111111111111111111111111111
sha_bridge=2222222222222222222222222222222222222222
digest_core=$(printf 'a%.0s' {1..64})
digest_bridge=$(printf 'b%.0s' {1..64})
image_core="ghcr.io/vox-suite/vox-core@sha256:$digest_core"
image_bridge="ghcr.io/vox-suite/vox-bridge@sha256:$digest_bridge"

validate_component core
validate_component bridge
assert_rejected validate_component worker
validate_sha "$sha_core"
assert_rejected validate_sha 1234
assert_rejected validate_sha Z111111111111111111111111111111111111111
validate_image core "$image_core"
validate_image bridge "$image_bridge"
assert_rejected validate_image core "$image_bridge"
assert_rejected validate_image core ghcr.io/vox-suite/vox-core:latest

test_dir=$(mktemp -d)
trap 'rm -rf "$test_dir"' EXIT

write_full_release \
  "$sha_core" "$image_core" \
  "$sha_bridge" "$image_bridge" \
  "$test_dir/current.env"

cat >"$test_dir/expected.env" <<EOF
CORE_IMAGE=$image_core
CORE_SHA=$sha_core
BRIDGE_IMAGE=$image_bridge
BRIDGE_SHA=$sha_bridge
EOF
assert_file "$test_dir/expected.env" "$test_dir/current.env"

next_bridge_sha=3333333333333333333333333333333333333333
next_bridge_digest=$(printf 'c%.0s' {1..64})
next_bridge_image="ghcr.io/vox-suite/vox-bridge@sha256:$next_bridge_digest"
write_candidate_release \
  bridge "$next_bridge_sha" "$next_bridge_image" \
  "$test_dir/current.env" "$test_dir/candidate.env"

cat >"$test_dir/expected-candidate.env" <<EOF
CORE_IMAGE=$image_core
CORE_SHA=$sha_core
BRIDGE_IMAGE=$next_bridge_image
BRIDGE_SHA=$next_bridge_sha
EOF
assert_file "$test_dir/expected-candidate.env" "$test_dir/candidate.env"

assert_rejected write_candidate_release \
  core "$sha_core" "$image_core" \
  "$test_dir/missing.env" "$test_dir/rejected.env"

echo "release tests passed"
