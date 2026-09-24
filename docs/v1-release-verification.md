# Platform V1 release verification

The checked-in test suite verifies code and fail-closed gate behavior. It does **not** certify a public release. Run the terminal gate on a disposable Linux rehearsal host with Docker Compose, exact built image digests, PostgreSQL 17, Redis 7, and sibling checkouts of all seven repositories, including `feno-extension` and `vox-contracts`. Record the host's CPU, RAM, OS, Docker version, model, and external provider versions. The single-user reference load is one active user and one request in flight; no capacity claim follows from it.

## Evidence dossier

Generate `docs/v1-traceability.json` with `python3 scripts/generate-v1-traceability.py`. It contains all P0 requirements, NFRs, AS-001–AS-020, and six PRD release gates. Candidate test paths are leads only; every item begins `unverified`.

Keep the final attestation and logs **outside** the repository. Set `VOX_RELEASE_EVIDENCE` to a JSON object with:

- `source_commits`: exact 40-character commits for `vox-core`, `vox-web`, `vox-bridge`, `agents`, `vox-deploy`, `feno-extension`, and `vox-contracts`. The last two must be pinned even though they do not produce a stack image. `vox-deploy` is pinned in the external attestation because its manifest cannot contain its own final commit.
- `images`: digest-pinned local image references for `core-api`, `core-worker`, `bridge`, `vox-web`, `portable-agent`, and `conformance-sandbox`. Shared images may have the same digest.
- `gates`: one object for each gate named in `scripts/verify-v1-evidence.py`. Each object needs `result: "pass"`, a timestamp, the exact command or review method, a relative log path, and the log's SHA-256. The `single-user-latency` gate also needs `run_json`, a relative path to measured timing data accepted by `scripts/check-single-user-latency.py`.
- `requirements`: one object per traceability ID. Each needs `result: "pass"`, a named test assertion or accountable reviewer decision, and the corresponding evidence gate. A candidate test filename is insufficient.

The gate verifies local source revisions, clean checkouts, locally present image digests, digest-pinned Compose configuration, running services, log hashes, requirement coverage, and the independent host's live acceptance command. Run `bash scripts/verify-platform-v1-release.sh` only after the actual rehearsals. `tests/run.sh` checks that this gate fails when prerequisites are missing.

Current candidate blockers: [Core status delivery](https://github.com/vox-suite/vox-core/issues/25), [Core privacy/export recheck](https://github.com/vox-suite/vox-core/issues/29), [legal/license evidence](https://github.com/vox-suite/vox-deploy/issues/2), and the [release gate](https://github.com/vox-suite/vox-deploy/issues/3). The independent Feno host, Docker rehearsal, live provider authorizations, accessibility/usability reviews, and measured latency evidence are not available in this workspace. Passing local suites are recorded as component evidence only.

## Required live rehearsals

1. **Product and authority:** Run Web browser journeys against real Core, PostgreSQL, and Redis. Prove identity, connection, discovery, grant, task/agent response, exact approval, execution, reconnect, reminder, extension, privacy/export, and handoff. Exercise AS-001–AS-020, including forged/replayed assertions, revocation, duplicate delivery, timeouts, and unknown outcomes.
2. **Second host:** Use a separate Git checkout and host credential. Set `FENO_HOST_REPO`, `FENO_HOST_SHA`, and `VOX_CORE_URL`; its executable `scripts/acceptance.sh` must drive public Core identity, connection, task, approval, and status flows. The absent `vox-suite/feno-extension` repository currently blocks this proof.
3. **Recovery:** On a disposable stack, create real pending tasks, proposals, attempts, and audit records. Back up PostgreSQL with `scripts/backup.sh`, verify the archive, restore into a clean database with `scripts/restore.sh`, and compare identifiers, states, counts, and approval consumption. Rehearse a compatible upgrade and an intentionally failed image rollout; prove the prior images recover without replaying an external effect. Capture commands, image digests, pre/post queries, and logs.
4. **Providers and reviews:** Obtain live authorized connected-read and consequential-write results from their selected production-capable providers; capture custody, region, payment, reconciliation, and support evidence. Keep other branded capabilities disabled or labelled handoff. Record separate named legal/license, accessibility, usability, security, and operator sign-offs.
5. **Latency:** On the documented 4 vCPU/8 GB Linux host, collect at least 100 warm and 30 cold text and voice turns. Record p50/p95 and failures for request-to-model-dispatch, model first token, first streamed text, full answer, final speech input to first meaningful audio, Core discovery/status/policy, and notification creation. Exclude provider time from platform budgets and publish it separately. Check PRD NFR-PER-001–005 plus 250 ms p95 pre-model and 100 ms p95 token relay budgets without reducing answer quality or authority checks.

The latency JSON uses `metadata`, `failures`, `samples`, and `endpoint_samples`. Each sample carries a correlated `trace_id`, channel, warm/cold label, answer-quality and safety verdicts, and stage timings. The platform budgets apply to `platform_pre_model_ms` and `platform_token_relay_ms`; `provider_model_ms`, speech finalization, TTS, and full response remain separately reported. Gather timings from the real text and voice journeys on the pinned stack; the synthetic unit test for the gate is not benchmark evidence. Record the machine configuration and provider/model versions with the raw results.

Do not mark E52 complete on the strength of fixture, mock-provider, or simulated restore tests. A closed issue is historical tracker state; release acceptance requires this dossier and accountable review.
