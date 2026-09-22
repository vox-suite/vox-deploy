#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source-path=SCRIPTDIR
source "$script_dir/release.sh"

vox_root=${VOX_ROOT:-/opt/vox}
state_dir=${VOX_STATE_DIR:-$vox_root/state}
env_file=${VOX_ENV_FILE:-/etc/vox.env}
compose_file=${VOX_COMPOSE_FILE:-$vox_root/compose.prod.yml}
public_health_url=${VOX_PUBLIC_HEALTH_URL:-https://api.voxagent.in/health}
current_release=$state_dir/current.env
previous_release=$state_dir/previous.env
candidate_release=$state_dir/candidate.env
rollback_needed=0
systemd_was_active=0
docker_config=

usage() {
  echo "usage: deploy-vox.sh (--request-file FILE | --component core|bridge --sha SHA --image IMAGE --ghcr-user USER | --core-sha SHA --core-image IMAGE --bridge-sha SHA --bridge-image IMAGE --ghcr-user USER) --ghcr-token-file FILE" >&2
  exit 2
}

component=
sha=
image=
core_sha=
core_image=
bridge_sha=
bridge_image=
ghcr_user=
ghcr_token_file=
request_file=

while [[ $# -gt 0 ]]; do
  case $1 in
    --component) component=${2-}; shift 2 ;;
    --sha) sha=${2-}; shift 2 ;;
    --image) image=${2-}; shift 2 ;;
    --core-sha) core_sha=${2-}; shift 2 ;;
    --core-image) core_image=${2-}; shift 2 ;;
    --bridge-sha) bridge_sha=${2-}; shift 2 ;;
    --bridge-image) bridge_image=${2-}; shift 2 ;;
    --ghcr-user) ghcr_user=${2-}; shift 2 ;;
    --ghcr-token-file) ghcr_token_file=${2-}; shift 2 ;;
    --request-file) request_file=${2-}; shift 2 ;;
    *) usage ;;
  esac
done

if [[ -n $request_file ]]; then
  [[ -f $request_file ]] || usage
  [[ -z $component && -z $sha && -z $image && -z $core_sha && -z $core_image && -z $bridge_sha && -z $bridge_image && -z $ghcr_user ]] || usage
  while IFS='=' read -r key value; do
    case $key in
      COMPONENT) [[ -z $component ]] || usage; component=$value ;;
      SHA) [[ -z $sha ]] || usage; sha=$value ;;
      IMAGE) [[ -z $image ]] || usage; image=$value ;;
      CORE_SHA) [[ -z $core_sha ]] || usage; core_sha=$value ;;
      CORE_IMAGE) [[ -z $core_image ]] || usage; core_image=$value ;;
      BRIDGE_SHA) [[ -z $bridge_sha ]] || usage; bridge_sha=$value ;;
      BRIDGE_IMAGE) [[ -z $bridge_image ]] || usage; bridge_image=$value ;;
      GHCR_USER) [[ -z $ghcr_user ]] || usage; ghcr_user=$value ;;
      *) usage ;;
    esac
  done <"$request_file"
fi

[[ -n $ghcr_user && -s $ghcr_token_file ]] || usage
[[ $ghcr_user =~ ^[A-Za-z0-9][A-Za-z0-9-]{0,38}$ ]] || usage
if [[ -n $component || -n $sha || -n $image ]]; then
  [[ -n $component && -n $sha && -n $image ]] || usage
  [[ -z $core_sha && -z $core_image && -z $bridge_sha && -z $bridge_image ]] || usage
  validate_component "$component" || usage
  validate_sha "$sha" || usage
  validate_image "$component" "$image" || usage
  deploy_mode=component
else
  [[ -n $core_sha && -n $core_image && -n $bridge_sha && -n $bridge_image ]] || usage
  validate_sha "$core_sha" || usage
  validate_image core "$core_image" || usage
  validate_sha "$bridge_sha" || usage
  validate_image bridge "$bridge_image" || usage
  deploy_mode=full
fi

require_configuration() {
  local key
  for key in \
    DATABASE_URL \
    VOX_AUTH_TOKEN \
    GEMINI_API_KEY \
    EXA_API_KEY \
    TWILIO_AUTH_TOKEN \
    ASSEMBLYAI_API_KEY \
    SARVAM_API_KEY; do
    grep -Eq "^${key}=.+$" "$env_file" || {
      echo "required configuration is missing: $key" >&2
      return 1
    }
  done
}

verify_file_security() {
  [[ ${VOX_SKIP_FILE_SECURITY_CHECK:-0} == 1 ]] && return 0
  local metadata
  metadata=$(stat -c '%U %a' "$env_file")
  [[ $metadata == "root 600" ]] || {
    echo "$env_file must be owned by root with mode 600" >&2
    return 1
  }
}

compose() {
  docker compose --env-file "$env_file" -f "$compose_file" "$@"
}

select_release() {
  load_release "$candidate_release"
  export CORE_IMAGE=$RELEASE_CORE_IMAGE
  export BRIDGE_IMAGE=$RELEASE_BRIDGE_IMAGE
  export VOX_ENV_FILE=$env_file
}

restore_release() {
  set +e
  echo "deployment failed; restoring the last healthy release" >&2
  if [[ -f $current_release ]]; then
    load_release "$current_release"
    export CORE_IMAGE=$RELEASE_CORE_IMAGE
    export BRIDGE_IMAGE=$RELEASE_BRIDGE_IMAGE
    compose up -d --wait redis core-api bridge
    compose up -d --build caddy
    compose up -d core-worker
  elif [[ $systemd_was_active == 1 ]]; then
    compose stop bridge core-worker caddy
    systemctl restart vox-bridge.service
  fi
  rm -f "$candidate_release"
}

on_exit() {
  local status=$?
  if [[ $status -ne 0 && $rollback_needed == 1 ]]; then
    restore_release
  fi
  [[ -z $docker_config ]] || rm -rf "$docker_config"
  exit "$status"
}
trap on_exit EXIT

mkdir -p "$vox_root" "$state_dir"
exec 9>"$vox_root/deploy.lock"
flock -n 9 || {
  echo "another Vox deployment is already running" >&2
  exit 1
}

for command in docker curl systemctl grep stat; do
  command -v "$command" >/dev/null || {
    echo "required command is unavailable: $command" >&2
    exit 1
  }
done
[[ -f $compose_file && -f $env_file ]] || {
  echo "production Compose or environment file is missing" >&2
  exit 1
}
verify_file_security
require_configuration

if [[ $deploy_mode == component ]]; then
  write_candidate_release "$component" "$sha" "$image" "$current_release" "$candidate_release"
else
  write_full_release "$core_sha" "$core_image" "$bridge_sha" "$bridge_image" "$candidate_release"
fi
select_release

docker_config=$(mktemp -d "$vox_root/.docker.XXXXXX")
chmod 700 "$docker_config"
docker --config "$docker_config" login ghcr.io --username "$ghcr_user" --password-stdin <"$ghcr_token_file"
docker --config "$docker_config" compose --env-file "$env_file" -f "$compose_file" pull
compose config --quiet

compose up -d --wait redis core-api

if systemctl is-active --quiet vox-bridge.service; then
  systemd_was_active=1
  rollback_needed=1
  systemctl stop vox-bridge.service
elif [[ -f $current_release ]]; then
  rollback_needed=1
fi

if systemctl is-active --quiet caddy.service; then
  systemctl stop caddy.service
  systemctl disable caddy.service
fi

compose up -d --wait bridge
compose up -d --build caddy
compose up -d core-worker
compose ps --status running --services | grep -Fx core-worker >/dev/null
curl --fail --silent --show-error --max-time 15 "$public_health_url" >/dev/null

if [[ -f $current_release ]]; then
  cp "$current_release" "$state_dir/.previous.env"
  chmod 600 "$state_dir/.previous.env"
  mv "$state_dir/.previous.env" "$previous_release"
fi
mv "$candidate_release" "$current_release"
chmod 600 "$current_release"
if [[ $systemd_was_active == 1 ]]; then
  systemctl disable vox-bridge.service
fi
rollback_needed=0

echo "Vox deployment completed"
