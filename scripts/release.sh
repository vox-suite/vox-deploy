#!/usr/bin/env bash

validate_component() {
  case ${1-} in
    core | bridge) return 0 ;;
    *) return 1 ;;
  esac
}

validate_sha() {
  [[ ${1-} =~ ^[0-9a-f]{40}$ ]]
}

validate_image() {
  local component=${1-}
  local image=${2-}
  validate_component "$component" || return 1
  [[ $image =~ ^ghcr\.io/vox-suite/vox-${component}@sha256:[0-9a-f]{64}$ ]]
}

load_release() {
  local release_file=$1
  RELEASE_CORE_IMAGE=
  RELEASE_CORE_SHA=
  RELEASE_BRIDGE_IMAGE=
  RELEASE_BRIDGE_SHA=
  [[ -f $release_file ]] || return 1

  local key value
  while IFS='=' read -r key value; do
    case $key in
      CORE_IMAGE) RELEASE_CORE_IMAGE=$value ;;
      CORE_SHA) RELEASE_CORE_SHA=$value ;;
      BRIDGE_IMAGE) RELEASE_BRIDGE_IMAGE=$value ;;
      BRIDGE_SHA) RELEASE_BRIDGE_SHA=$value ;;
      *) return 1 ;;
    esac
  done <"$release_file"

  validate_sha "$RELEASE_CORE_SHA" &&
    validate_image core "$RELEASE_CORE_IMAGE" &&
    validate_sha "$RELEASE_BRIDGE_SHA" &&
    validate_image bridge "$RELEASE_BRIDGE_IMAGE"
}

write_release() {
  local core_sha=$1
  local core_image=$2
  local bridge_sha=$3
  local bridge_image=$4
  local output=$5

  validate_sha "$core_sha" || return 1
  validate_image core "$core_image" || return 1
  validate_sha "$bridge_sha" || return 1
  validate_image bridge "$bridge_image" || return 1

  local output_dir temporary
  output_dir=$(dirname "$output")
  mkdir -p "$output_dir"
  temporary=$(mktemp "$output_dir/.release.XXXXXX")
  chmod 600 "$temporary"
  {
    printf 'CORE_IMAGE=%s\n' "$core_image"
    printf 'CORE_SHA=%s\n' "$core_sha"
    printf 'BRIDGE_IMAGE=%s\n' "$bridge_image"
    printf 'BRIDGE_SHA=%s\n' "$bridge_sha"
  } >"$temporary"
  mv "$temporary" "$output"
}

write_full_release() {
  write_release "$@"
}

write_candidate_release() {
  local component=$1
  local sha=$2
  local image=$3
  local current=$4
  local output=$5

  validate_component "$component" || return 1
  validate_sha "$sha" || return 1
  validate_image "$component" "$image" || return 1
  load_release "$current" || return 1

  if [[ $component == core ]]; then
    write_release \
      "$sha" "$image" \
      "$RELEASE_BRIDGE_SHA" "$RELEASE_BRIDGE_IMAGE" \
      "$output"
  else
    write_release \
      "$RELEASE_CORE_SHA" "$RELEASE_CORE_IMAGE" \
      "$sha" "$image" \
      "$output"
  fi
}
