#!/usr/bin/env python3
"""Create a pending requirement matrix; candidates are leads, never proof."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1].parent
prd = (ROOT / "docs/PRD.md").read_text()

tests = {
    "DEP": ["vox-core/tests/host_trust.rs", "vox-deploy/tests/self_hosted_stack_test.sh"],
    "ID": ["vox-core/tests/user_context.rs", "vox-web/tests/consumer-auth-postgres.test.ts"],
    "AGT": ["agents/tests/test_portable_agent_acceptance.py", "vox-core/tests/agent_registry.rs"],
    "INT": ["vox-core/tests/integration_registry.rs"],
    "EXT": ["vox-core/tests/remote_extensions.rs"],
    "CON": ["vox-core/tests/connections.rs"],
    "GRT": ["vox-core/tests/capability_grants.rs"],
    "TSK": ["vox-core/tests/durable_tasks.rs"],
    "TOL": ["vox-core/tests/protocol_adapters.rs"],
    "APR": ["vox-core/tests/approvals.rs"],
    "PAY": ["vox-core/tests/execution_policy.rs"],
    "EXE": ["vox-core/tests/consequential_write.rs"],
    "HND": ["vox-core/tests/provider_capability_proofs.rs"],
    "PRF": ["vox-core/tests/preferences.rs", "vox-web/tests/privacy-controls.test.ts"],
    "REM": ["vox-core/tests/reminders.rs", "vox-bridge/tests/notifications_delivery_test.rs"],
    "EVT": ["vox-core/tests/status_updates.rs"],
    "GLB": ["vox-web/tests/a11y-localization.test.ts"],
    "AUD": ["vox-core/tests/audit.rs"],
    "DAT": ["vox-core/tests/privacy_lifecycle.rs"],
    "PRT": ["vox-core/tests/privacy_lifecycle.rs"],
    "OSS": ["vox-deploy/tests/self_hosted_stack_test.sh"],
    "SEC": ["vox-core/tests/release_conformance_test.rs"],
    "REL": ["vox-core/tests/durable_tasks.rs"],
    "PRI": ["vox-core/tests/privacy_lifecycle.rs"],
    "OPS": ["vox-core/tests/health.rs"],
    "ACC": ["vox-web/tests/browser/app.spec.ts"],
    "PER": [],
}
scenario_tests = {
    1: ["vox-core/tests/capability_grants.rs"],
    2: ["vox-core/tests/capability_grants.rs", "vox-core/tests/approvals.rs"],
    3: ["vox-core/tests/approvals.rs"],
    4: ["vox-core/tests/approvals.rs"],
    5: ["vox-core/tests/consequential_write.rs"],
    6: ["vox-core/tests/consequential_write.rs"],
    7: ["vox-core/tests/durable_tasks.rs"],
    8: ["vox-core/tests/remote_extensions.rs"],
    9: ["vox-core/tests/capability_grants.rs"],
    10: ["vox-core/tests/user_context.rs"],
    11: ["vox-core/tests/connections.rs", "vox-core/tests/capability_grants.rs"],
    12: ["vox-core/tests/remote_extensions.rs"],
    13: ["vox-core/tests/provider_capability_proofs.rs"],
    14: ["vox-core/tests/reminders.rs"],
    15: ["agents/tests/test_portable_agent_acceptance.py"],
    16: ["vox-core/tests/remote_extensions.rs"],
    17: ["vox-core/tests/privacy_lifecycle.rs"],
    18: ["vox-core/tests/status_updates.rs"],
    19: ["vox-core/tests/execution_policy.rs"],
    20: ["vox-core/tests/provider_capability_proofs.rs"],
}
release_tests = {
    1: ["vox-web/tests/product-acceptance.test.ts"],
    2: ["vox-core/tests/remote_extensions.rs"],
    3: ["vox-core/tests/release_conformance_test.rs"],
    4: ["vox-core/tests/durable_tasks.rs"],
    5: ["vox-deploy/tests/self_hosted_stack_test.sh"],
    6: ["vox-core/tests/provider_capability_proofs.rs"],
}

ids = set(re.findall(r"\bFR-[A-Z]+-\d{3} \(P0\)", prd))
ids = {item.split(" ", 1)[0] for item in ids}
ids.update(re.findall(r"\bNFR-[A-Z]+-\d{3}\b", prd))
ids.update(re.findall(r"^### (AS-\d{3}):", prd, re.MULTILINE))
ids.update(f"RELEASE-19.{number}" for number in range(1, 7))

rows = {}
for requirement in sorted(ids):
    family = requirement.split("-")[1] if requirement.startswith(("FR-", "NFR-")) else ""
    proposed = tests.get(family, [])
    if requirement.startswith("AS-"):
        proposed = scenario_tests[int(requirement[-3:])]
    elif requirement.startswith("RELEASE-19."):
        proposed = release_tests[int(requirement[-1])]
    candidates = [path for path in proposed if (ROOT / path).is_file()]
    rows[requirement] = {
        "status": "unverified",
        "candidate_test_files": candidates,
        "required_evidence": "Named assertion and passing real-run log; human/provider sign-off where applicable",
    }

print(json.dumps({"source": "docs/PRD.md", "requirements": rows}, indent=2))
