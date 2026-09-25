# Vox v1 verification run — 2026-09-24

**Decision: release blocked.** This is a local candidate verification record, not a public v1 attestation. The approved release method and required external dossier are in [`vox-deploy/docs/v1-release-verification.md`](v1-release-verification.md). The 242-item traceability inventory is [`vox-deploy/docs/v1-traceability.json`](v1-traceability.json); every item remains unverified until a named assertion or accountable review is attached to a real gate log.

## Source baseline

| Repository | Baseline before fixes | Committed candidate |
| --- | --- | --- |
| vox-core | `9961cd3606cf91b748411623d3b58b538bb806f1` | `8d47a040e341f9f96242cff5d209290a33b96447` |
| vox-web | `7aafa8501c93732c8353044d8275d6c35c998e19` | `3d8a957510fd9682612ebc106ebb7dbb356a9bf0` |
| vox-bridge | `029193d77a823eb247e95d3c1f5dfc999f78da97` | `e186a3fd436c4428db2ddf203a8820987c703dc2` |
| agents | `a10c703dce166aea19ab94e4bf1b727368e38ded` | unchanged |
| vox-deploy | `afe912b389b0804bedca76d859ea5c4a536c667f` | release evidence commit on `main`; exact SHA is recorded by the external attestation |

The existing manifest was stale and did not contain built image digests. The release verifier now requires an external attestation of final clean commits and digest-pinned running images. No image digest was available locally.

## Local results

| Check | Result | Scope |
| --- | --- | --- |
| Core unit tests | 45 passed | Local unit behavior |
| Core ignored integration targets | 39 target runs passed | Fresh PostgreSQL 17 database per target; Redis-only target excluded |
| Core clippy | Passed with warnings denied | All targets |
| Web tests | 77 passed, 1 skipped | Fixture and component tests; no browser against real Core |
| Web lint/build | Build passed; lint has 0 errors, 10 warnings | Production compilation only |
| Bridge channel acceptance | 10 passed | Local fixtures and loopback |
| Portable agent tests | 10 passed | Python unittest portable tests |
| Deploy tests | Passed | Static contracts and fail-closed release gate, not live Compose |

The PostgreSQL integration matrix exposed real defects before fixes: legacy connection disconnect referenced a nonexistent column; status reads were empty; privacy export used nonexistent columns and the wrong execution link; audit events lacked task transitions and context filtering; spend and quota policies were discarded; concurrent conversation completion queued duplicate summaries; scheduled retries dispatched duplicate external actions. Candidate fixes now pass the affected local suites. The Redis-only tests require a running isolated Redis instance. The prior voice and RLS test fixtures also referenced removed schema and were updated to exercise the current contract.

## Latency and cache decision

No p50 or p95 platform result is reported because there is no running reference stack, external model/speech provider, or browser playback trace here. Core now logs agent preparation and first text without raw prompts; Bridge logs correlated voice turn timing without transcript or sentence content. The latency evidence gate requires a 4 vCPU, 8 GB Linux run with 100 warm and 30 cold turns per text and voice journey, stage timings, quality/safety verdicts, and the four PRD endpoint budgets. Its synthetic unit test verifies only that the gate rejects over-budget data.

Keep task, grant, connection, approval, proposal, and policy reads authoritative at execution time. A discovery or presentation cache may be introduced only after a measured bottleneck, with declaration/availability version keys and invalidation evidence. No new authority cache is part of this candidate.

## Hard gates still missing

- Docker Compose clean install, upgrade, failed rollout, PostgreSQL backup/restore, Redis outage, and image digest evidence. Docker is unavailable here.
- Independent Feno host acceptance. The referenced repository and executable host suite are absent.
- Real Web browser journeys against Core/PostgreSQL/Redis and a second host through public interfaces.
- Live authorized connected read and approved consequential write. [`vox-core/docs/provider-feasibility.md`](https://github.com/vox-suite/vox-core/blob/main/docs/provider-feasibility.md) keeps Uber read and Expedia booking conditional on provider access and review; branded handoffs must remain labelled incomplete.
- Legal/license, security, accessibility, usability, and operator sign-offs.
- Full text and voice latency and answer-quality measurements on pinned artifacts.
- Production webhook secret custody, delivery/retry, and audit sink proof. Core status and audit issues remain open.

The release tracker is [`vox-deploy#3`](https://github.com/vox-suite/vox-deploy/issues/3). Candidate source fixes are tracked in the existing Core issues for [context migration](https://github.com/vox-suite/vox-core/issues/4), [execution policy](https://github.com/vox-suite/vox-core/issues/14), [execution](https://github.com/vox-suite/vox-core/issues/15), [status](https://github.com/vox-suite/vox-core/issues/25), [audit](https://github.com/vox-suite/vox-core/issues/28), [privacy/export](https://github.com/vox-suite/vox-core/issues/29), and [security conformance](https://github.com/vox-suite/vox-core/issues/30).

## Later E25 candidate, same release decision

Core [PR #67](https://github.com/vox-suite/vox-core/pull/67), merged as
`b36721feb477e033eb3b0b0a20f7e5b482a60a8b`, adds an encrypted webhook
secret store, transactional status outbox,
signed delivery with bounded retry, replay recording for verified provider
events, and nonpublic destination rejection. Deploy
[PR #6](https://github.com/vox-suite/vox-deploy/pull/6)
passes the optional custody key only to Core API and worker services. Fresh
PostgreSQL status, RLS, and migration tests, the Core non-ignored suite,
formatting, Clippy, and Deploy static tests passed locally. A controlled public
HTTPS receiver verified four synthetic signed hints across retry, service
recreation, secret rotation, and duplicate lease recovery. This is webhook
transport evidence, not a running Linux reference-stack or production-provider
proof. E25 and E52 remain open for their consumer and release gates.
