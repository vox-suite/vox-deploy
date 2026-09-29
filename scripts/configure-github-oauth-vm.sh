#!/usr/bin/env bash
set -euo pipefail
[[ $# == 1 && ($1 == --inspect || $1 == --apply) ]]
mode=$1
[[ ${SERVER_HOST:-} == 44.201.162.243 ]]
[[ ${SERVER_USER:-} =~ ^[a-z_][a-z0-9_-]*$ ]]
test -n "${SSH_PRIVATE_KEY:-}"
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
umask 077
work_dir=$(mktemp -d /tmp/vox-github-configuration.XXXXXX)
remote_dir=
ssh_args=(-o BatchMode=yes -o ConnectTimeout=15 -o StrictHostKeyChecking=yes
  -o "UserKnownHostsFile=$repo_dir/deployments/production.known_hosts" -i "$work_dir/key")
destination="$SERVER_USER@$SERVER_HOST"
cleanup() {
  if [[ $remote_dir =~ ^/tmp/vox-github-configuration\.[a-zA-Z0-9]+$ ]]; then
    # Only the validated temporary path is expanded on the client.
    # shellcheck disable=SC2029
    ssh "${ssh_args[@]}" "$destination" "rm -rf '$remote_dir'" >/dev/null 2>&1 || true
  fi
  rm -rf "$work_dir"
}
trap cleanup EXIT
printf '%s\n' "$SSH_PRIVATE_KEY" >"$work_dir/key"
unset SSH_PRIVATE_KEY
remote_dir=$(ssh "${ssh_args[@]}" "$destination" 'umask 077; mktemp -d /tmp/vox-github-configuration.XXXXXX')
[[ $remote_dir =~ ^/tmp/vox-github-configuration\.[a-zA-Z0-9]+$ ]]
scp "${ssh_args[@]}" "$repo_dir/scripts/configure-github-oauth.py" \
  "$repo_dir/scripts/configure-github-oauth-vm.py" "$repo_dir/scripts/check-vm-database.py" "$destination:$remote_dir/"
if [[ $mode == --apply ]]; then
  # The secret is only a protected pipe's stdin, never an argument or log.
  # Only the validated temporary path is expanded on the client.
  # shellcheck disable=SC2029
  python3 -c 'import os,sys; sys.stdout.write(os.environ["VOX_GITHUB_OAUTH_CLIENT_SECRET"])' |
    ssh "${ssh_args[@]}" "$destination" "sudo -n python3 '$remote_dir/configure-github-oauth-vm.py' --apply"
else
  # shellcheck disable=SC2029
  ssh "${ssh_args[@]}" "$destination" "sudo -n python3 '$remote_dir/configure-github-oauth-vm.py' --inspect"
  if [[ -n ${DATABASE_URL:-} ]]; then
    # shellcheck disable=SC2029
    python3 -c 'import os,sys; sys.stdout.write(os.environ["DATABASE_URL"])' |
      ssh "${ssh_args[@]}" "$destination" "sudo -n python3 '$remote_dir/check-vm-database.py'"
  fi
fi
