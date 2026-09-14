#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_dir"

bash tests/release_test.sh
bash tests/compose_test.sh
bash tests/deploy_test.sh
bash tests/config_status_test.sh
bash tests/merge_env_test.sh
bash tests/workflow_test.sh
shellcheck -x -P scripts scripts/*.sh tests/*.sh tests/fakes/command

echo "all tests passed"
