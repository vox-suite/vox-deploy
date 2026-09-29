#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_dir"

bash tests/release_test.sh
bash tests/compose_test.sh
bash tests/deploy_test.sh
bash tests/workflow_test.sh
bash tests/self_hosted_stack_test.sh
bash tests/license_readiness_test.sh
bash tests/terminal_release_gate_test.sh
python3 tests/latency_gate_test.py
python3 tests/github_oauth_config_test.py
python3 tests/github_oauth_vm_test.py
if command -v shellcheck >/dev/null 2>&1; then
    shellcheck -x -P scripts scripts/*.sh tests/*.sh tests/fakes/command
fi

echo "all tests passed"
