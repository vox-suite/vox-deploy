#!/usr/bin/env bash
set -euo pipefail
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

ruby -ryaml -e '
  paths = Dir.glob(File.join(ARGV[0], ".github/workflows/*.{yml,yaml}"))
  raise "unexpected operational workflow" unless paths.map { |p| File.basename(p) } == ["pr-checks.yml"]
  checks = YAML.load_file(paths.fetch(0))
  triggers = checks["on"] || checks[true]
  raise "missing PR validation" unless triggers.key?("pull_request")
  raise "missing main validation" unless triggers.fetch("push").fetch("branches") == ["main"]
  raise "excess workflow permissions" unless checks.fetch("permissions") == {"contents" => "read"}
  steps = checks.fetch("jobs").fetch("deploy").fetch("steps")
  raise "missing complete verification" unless steps.any? { |step| step["run"] == "bash tests/run.sh" }
' "$repo_dir"

echo "workflow tests passed"
