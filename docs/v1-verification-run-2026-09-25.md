# Vox Platform V1 Verification Run — 2026-09-25

**Status: Platform V1 Source Gates Closed & Merged.**  
This document records the component verification and release readiness state following the merge of all upstream platform P0 tickets into the canonical repository branches.

---

## 1. Verified Source Baseline

All six participating repositories have reached their verified Platform V1 commits on `main`:

| Repository | Verified Commit SHA | Platform Scope & Milestone | Status |
| :--- | :--- | :--- | :---: |
| `vox-core` | `a4129c128a03b772f6bcfc339ad11ae60d41dd78` | Coordination, tasks, identity context, policy, encrypted webhooks, privacy, audit, security conformance (PRs #69-#75) | :white_check_mark: MERGED |
| `vox-web` | `3d8a957510fd9682612ebc106ebb7dbb356a9bf0` | Consumer portal, standalone auth (OAuth + email OTP), privacy controls, and host UI | :white_check_mark: MERGED |
| `vox-bridge` | `e186a3fd436c4428db2ddf203a8820987c703dc2` | Voice (Twilio/LiveKit) and messaging (WhatsApp/SMS) channel gateway | :white_check_mark: MERGED |
| `agents` | `a10c703dce166aea19ab94e4bf1b727368e38ded` | Portable, model-neutral agent runner delegating authority to Core | :white_check_mark: MERGED |
| `vox-contracts` | `119f2ea7ac53ebcf2d5150a488997ec49ceaca6c` | Canonical shared PRD, execution order, and JSON schemas | :white_check_mark: MERGED |
| `vox-deploy` | Pinned in release attestation | Reference stack compose (`pgvector`), legal review, automated gate verifiers (PRs #8-#10) | :white_check_mark: MERGED |

---

## 2. Upstream Gate Closure Record

All prerequisite Platform V1 issues have completed implementation, verification, and merge:

1. **`vox-core#4` (PR #69)**: Dual `user_context_id` and `user_id` bindings, single-delivery summary jobs.
2. **`vox-core#14` (PR #70)**: Transactional policy reservations, spend/quota evaluation, and atomic rollback.
3. **`vox-core#15` (PR #71)**: Row-level locking and atomic policy evaluation in `start_attempt`; idempotent booking re-execution.
4. **`vox-core#25` (PR #72)**: External status delivery via signed webhooks with HMAC, replay prevention, and bounded retry.
5. **`vox-core#28` (PR #73)**: Pre-egress secret filtering (`safe_details`), immutable context audit scoping, operator disclosure logging.
6. **`vox-core#29` (PR #74)**: Non-secret portable export, fresh authorization for imported connections, historical action evidence preservation.
7. **`vox-core#30` (PR #75)**: Security and conformance suite, embedded credential scanner across model context and audit traces; all 4 scenarios & 39 steps passed.
8. **`vox-deploy#1` (PR #9)**: Self-hosted reference stack with `pgvector/pgvector:pg17`, manifest revision pinning, and fail-closed backup/restore scripts.
9. **`vox-deploy#2` (PR #10)**: Accountable legal review by Gowtham T G, 6-repository license audit, zero viral copyleft confirmation, and secret scan assurance.

---

## 3. Local Test and Gate Suite Results

All test suites pass locally in fail-closed configuration:

| Test Suite | Result | Scope |
| :--- | :---: | :--- |
| `tests/release_test.sh` | PASS | Component validation, SHA format, candidate image tagging |
| `tests/compose_test.sh` | PASS | Docker Compose configuration syntax and port mapping |
| `tests/deploy_test.sh` | PASS | Deployment parameter parsing, environment validation, recovery trigger |
| `tests/workflow_test.sh` | PASS | GitHub Actions workflow schema and step isolation |
| `tests/self_hosted_stack_test.sh` | PASS | Reference stack service definitions, pgvector image, 6-repo manifest, secret isolation |
| `tests/license_readiness_test.sh` | PASS | Accountable reviewer, dated decision, 6-repo license audit, zero copyleft, zero secrets |
| `tests/terminal_release_gate_test.sh` | PASS | Fail-closed verifiers reject missing evidence, unconfigured hosts, and missing prerequisites |
| `tests/latency_gate_test.py` | PASS | Synthetic budget verification and percentile validation |

---

## 4. Release Gate and Terminal Checklist

- [x] Documented clean install and upgrade procedures available in `docs/self-hosting.md`.
- [x] Failed rollout rollback mechanisms fail closed and preserve durable task/audit data (`scripts/restore.sh`).
- [x] All six repository revisions pinned to exact verified commits.
- [x] Accountable human legal review completed (`docs/legal-and-distribution-decision.md`).
- [x] Zero-credential / secret isolation audit passed across all assets.
- [x] Terminal verifier `scripts/verify-v1-evidence.py` enforces fail-closed gate semantics for external attestation dossiers.
