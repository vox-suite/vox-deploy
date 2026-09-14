#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

ruby -ryaml -e '
  ci = YAML.load_file(ARGV[0])
  deploy = YAML.load_file(ARGV[1])
  deploy_on = deploy["on"] || deploy[true]
  raise "missing repository dispatch" unless deploy_on.fetch("repository_dispatch").fetch("types") == ["component_published"]
  raise "missing manual dispatch" unless deploy_on.key?("workflow_dispatch")
  raise "wrong permissions" unless deploy.fetch("permissions") == {"contents" => "read", "packages" => "read"}
  concurrency = deploy.fetch("concurrency")
  raise "wrong concurrency group" unless concurrency.fetch("group") == "production"
  raise "deployment cancellation enabled" unless concurrency.fetch("cancel-in-progress") == false
  job = deploy.fetch("jobs").fetch("deploy")
  raise "missing production environment" unless job.fetch("environment") == "production"
  step_names = job.fetch("steps").map { |step| step["name"] }.compact
  raise "credentials removed before release summary" unless step_names.index("Record release") < step_names.index("Remove runner credentials")
  raise "CI has no shell test" unless ci.fetch("jobs").values.any? { |value| value.fetch("steps").any? { |step| step["run"]&.include?("tests/run.sh") } }
' "$repo_dir/.github/workflows/ci.yml" "$repo_dir/.github/workflows/deploy.yml"

grep -q 'VOX_DEPLOY_REQUEST' "$repo_dir/.github/workflows/deploy.yml"
grep -q 'rm -f /tmp/vox-release-request /tmp/vox-ghcr-token' "$repo_dir/.github/workflows/deploy.yml"
if grep -Eq 'ssh .*\$\{\{ *secrets\.' "$repo_dir/.github/workflows/deploy.yml"; then
  echo "secret interpolation found in SSH arguments" >&2
  exit 1
fi

for key in SERVER_HOST SERVER_USER SSH_PRIVATE_KEY; do
  grep -q "$key" "$repo_dir/README.md"
done
if grep -q 'GHCR_PULL_TOKEN' "$repo_dir/README.md"; then
  echo "README requires a persistent GHCR token" >&2
  exit 1
fi
grep -q '/etc/vox.env' "$repo_dir/README.md"
grep -q 'workflow_dispatch' "$repo_dir/README.md"

echo "workflow tests passed"
