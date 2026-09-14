#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
sync_workflow="$repo_dir/.github/workflows/sync-production-env.yml"
inspect_workflow="$repo_dir/.github/workflows/inspect-production.yml"

if [[ ! -f $sync_workflow ]]; then
  echo "production environment sync workflow is missing" >&2
  exit 1
fi

if [[ ! -f $inspect_workflow ]]; then
  echo "production inspection workflow is missing" >&2
  exit 1
fi

ruby -ryaml -e '
  ci = YAML.load_file(ARGV[0])
  deploy = YAML.load_file(ARGV[1])
  deploy_on = deploy["on"] || deploy[true]
  raise "missing repository dispatch" unless deploy_on.fetch("repository_dispatch").fetch("types") == ["component_ready"]
  raise "missing manual dispatch" unless deploy_on.key?("workflow_dispatch")
  manual_inputs = deploy_on.fetch("workflow_dispatch").fetch("inputs")
  raise "manual deploy is not safe by default" unless manual_inputs.fetch("deploy").fetch("default") == false
  raise "wrong permissions" unless deploy.fetch("permissions") == {"contents" => "read", "packages" => "write"}
  concurrency = deploy.fetch("concurrency")
  raise "wrong concurrency group" unless concurrency.fetch("group") == "production"
  raise "deployment cancellation enabled" unless concurrency.fetch("cancel-in-progress") == false
  job = deploy.fetch("jobs").fetch("deploy")
  raise "release build is not native ARM64" unless job.fetch("runs-on") == "ubuntu-24.04-arm"
  raise "missing production environment" unless job.fetch("environment") == "production"
  step_names = job.fetch("steps").map { |step| step["name"] }.compact
  raise "Core is not built centrally" unless step_names.include?("Build and publish Core")
  raise "Bridge is not built centrally" unless step_names.include?("Build and publish Bridge")
  deploy_step = job.fetch("steps").find { |step| step["name"] == "Deploy complete backend" }
  raise "production deploy is not explicitly gated" unless deploy_step.fetch("if").include?("inputs.deploy")
  raise "credentials removed before release summary" unless step_names.index("Record release") < step_names.index("Remove runner credentials")
  raise "CI has no shell test" unless ci.fetch("jobs").values.any? { |value| value.fetch("steps").any? { |step| step["run"]&.include?("tests/run.sh") } }
' "$repo_dir/.github/workflows/ci.yml" "$repo_dir/.github/workflows/deploy.yml"

ruby -ryaml -e '
  sync = YAML.load_file(ARGV[0])
  sync_on = sync["on"] || sync[true]
  raise "sync must be manual-only" unless sync_on.keys == ["workflow_dispatch"]
  raise "wrong sync permissions" unless sync.fetch("permissions") == {"contents" => "read"}
  job = sync.fetch("jobs").fetch("sync")
  raise "sync must use production environment" unless job.fetch("environment") == "production"
  raise "sync does not check out migration scripts" unless job.fetch("steps").any? { |step| step["uses"]&.start_with?("actions/checkout@") }
  body = job.fetch("steps").map { |step| step["run"] }.compact.join("\n")
  %w[DATABASE_URL NEXT_PUBLIC_SUPABASE_URL NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY].each do |key|
    raise "missing #{key}" unless body.include?(key)
  end
  raise "environment file is not protected" unless body.include?("install -o root -g root -m 600")
  raise "existing keys are not preserved" unless body.include?("awk")
  root_staging = "staged=" + 36.chr + "(sudo mktemp"
  raise "protected staging file is not root-owned" unless body.include?(root_staging)
  raise "runner files are not cleaned" unless body.include?("rm -f")
  derived_host = "database_host=" + "$" + "{database_url#*@}"
  raise "database host is not derived from DATABASE_URL" unless body.include?(derived_host)
' "$sync_workflow"

ruby -ryaml -e '
  inspect = YAML.load_file(ARGV[0])
  inspect_on = inspect["on"] || inspect[true]
  raise "inspection must be manual-only" unless inspect_on.keys == ["workflow_dispatch"]
  raise "wrong inspection permissions" unless inspect.fetch("permissions") == {"contents" => "read"}
  job = inspect.fetch("jobs").fetch("inspect")
  raise "inspection must use production environment" unless job.fetch("environment") == "production"
  body = job.fetch("steps").map { |step| step["run"] }.compact.join("\n")
  raise "inspection does not run the safe status script" unless body.include?("config-status.sh")
  raise "inspection does not clean remote script" unless body.include?("rm -f /tmp/vox-config-status.sh")
  runner_cleanup = "rm -f \"" + 36.chr + "VOX_SSH_KEY_FILE\""
  raise "inspection does not clean runner key" unless body.include?(runner_cleanup)
' "$inspect_workflow"

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
