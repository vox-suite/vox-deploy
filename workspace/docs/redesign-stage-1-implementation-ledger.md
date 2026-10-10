# Vox redesign implementation ledger

## Current status
Implementation is in progress. Earlier completion statements in this ledger were premature. Local compilation, database checks, deployment, and live behavior are separate evidence levels.

## Implemented and locally checked
- Six fresh baseline migrations replace the historical migration chain. All six applied successfully to a disposable pgvector PostgreSQL 16 database. Managed Supabase auth and storage were not changed.
- Canonical timeline groups, versioned event types, events, evidence, unified updates and job action routes are wired into Core.
- Published event type definitions are immutable. User type creation is serialized and rejects external JSON Schema references and oversized/deep schemas.
- Pulse measurements derive from published analytics definitions. SQL handles arithmetic, currencies remain separate, refunds reduce spending, cumulative gaming observations are excluded, averages combine sums and counts, and distribution queries use raw values.
- Chart creation is serialized per user and supports idempotency. Keyset order matches the pagination cursor. Daily aggregates carry timezone, currency, dimension and data revision; corrections invalidate cached revisions. Aggregates are built on demand, with worker cleanup of old revisions. This trades simpler correctness for more cold-query work.
- Gmail requires exact signed OIDC audience, verified service-account email and RS256. Message persistence is atomic and failed processing retains the cursor. Subject keywords no longer become visits/orders. Body extraction requires explicit financial facts; uncertainty appears in Updates.
- Shared object storage is required outside explicit development. Reads are bounded, owned canonical references are enforced, and deletion failures remain retryable. Passwords expire after 15 minutes. Attachment retention preserves evidence metadata.
- Finance deduplication separates directions and currencies, requires explicit references and preserves duplicate evidence. Settlement requires explicit references.
- Desktop Timeline uses canonical event APIs and group tabs; Updates supports read/dismiss/retry/password input; Pulse supports measurement selection, preview and save with existing visual components. Legacy chart board and composer entry points are removed.
- Android no longer requests READ_SMS or schedules SMS workers. Timeline uses canonical event/count APIs with group tabs. Updates and measurement-first Pulse are implemented using existing Compose visual components. Kotlin compilation passed before the latest Pulse refinements; recheck required.
- Shared OpenAPI generates desktop types and Kotlin timeline/update models through scripts/generate-redesign-contracts.py.
- Core binaries passed cargo check after agent timeline tools and Pulse query tools were added. Further edits need the final check.

## Still required before rollout
- Validate seeded content schemas and every ingestion path; review connector provenance, cancellation, duplicates, Takeout limits/coverage and correction semantics.
- Verify the implemented desktop Ollama and Android LiteRT-LM historical Gmail review flows with real accounts and local models. Device-only classification and selected-message upload are wired; actual model/device validation remains pending. Manual Takeout ZIP/JSON upload is wired on both clients.
- Retire remaining legacy chart/query and goal paths, including Spaces and external integration references.
- Finish job failure handling, attachment refetch and user-action state verification.
- Add coverage-aware analytics presentation, resource limits and verify large annual data. No scalability claim is based on the earlier 1,000-row benchmark.
- Review existing name tool/Redis writes and voice latency instrumentation, then verify greeting/turn behavior with real sessions.
- Complete Core, Bridge, Connections, desktop and Android builds; run local API, SQL and manual UI checks without adding tests or code comments.
- Reset only the verified application schema in Supabase after implementation verification, apply the fresh baseline and deploy API/worker/Bridge via Railway. Nothing has been reset or deployed in this direct implementation run.
- Build/open the native desktop and verify authenticated flows. Record deployed revisions and runtime evidence separately.

## Constraints and decisions
- Preserve pre-existing dirty changes and tests. No implementation subagents are used.
- Retain spans solely for execution/Spaces tasks; canonical observed timeline and Pulse use timeline_events.
- No commit or push was requested.
- Synthetic data is permitted only in an owned disposable local database for explicit verification and must never be presented as real user data.

## Latest verification
- Actual SQLx startup applied the corrected runtime-compatible six-file baseline to the disposable redesign_api database. Authenticated groups (6), published event types (19), timeline query, Updates list, and Pulse canvas returned HTTP 200. Valid typed ingestion returned 201; a string amount returned 400. Pulse preview computed INR 123.45 from one explicitly synthetic transaction and reported partial coverage.
- A separate synthetic one-million-event monthly SQL aggregate completed in 376 ms locally; this is not a production scalability result.
- Financial normalization now preserves source dedupe keys and uses a separately indexed content fingerprint. Live database notifications and desktop refresh subscriptions are implemented and need fresh-baseline runtime verification.

- Desktop production build, Android Kotlin compilation including local Gmail model limits, Bridge cargo check, and Core all-target compilation passed. Existing test fixtures were adapted to canonical chart contracts; no new tests were added or run.
- PDF parsing now runs on a blocking pool with two permits held until actual completion, 45-second caller timeout, 50 MB input and 500-page limits. Timeout cannot forcibly cancel a running parser, so permits remain held until it stops.
- Account merge now fails atomically on unique conflicts instead of deleting conflicting records. Canonical tenant constraints are deferrable for the transaction, and event type ownership transfers are restricted to the merge context. Original attachment storage namespace remains immutable across merges. These changes still require local account-link runtime verification.

- Actual authenticated local Pulse API on 1,000,001 synthetic events: annual inventory 304 ms; INR monthly annual preview cold 923.6 ms / warm 4.4 ms (900,001 records, total 45,000,123.45); USD cold 175.4 ms / warm 6.2 ms (100,000 records, total 4,995,000). Currencies remained separate. Single-process local results do not establish production concurrency.
- A synthetic account merge retained and transferred its canonical timeline event. Derived revision/cache records are invalidated before transfer, avoiding cache-key conflicts without deleting source observations.
- Railway production is linked and accessible. API and worker lack shared Supabase storage service credentials and Gmail Pub/Sub OIDC settings. Native UI automation currently reports a locked Mac; unlock was requested while source checks continue. No deployment or live reset has happened.

- Repeated evidence snapshots are hashed and deduplicated; financial duplicate evidence is merged without losing distinct provenance. Generic finance ingestion now applies the same normalization transaction used by email attachments. Updated baseline verification is pending.
- Deployment staging now includes the actual local vox-connections dependency, so Railway deploys do not silently use the old pinned connector revision. Core Dockerfiles expect the generated staging context.

## Verification after latest continuation
- Fixed Gmail optional snippet redaction and passed Core all-target compilation. Regenerated current OpenAPI, desktop types and Android models. Desktop production build, native Vox.app bundling, and Android Kotlin compilation passed after the latest changes.
- Actual SQLx startup applied all six migrations to a new disposable database with pgcrypto, uuid-ossp and vector already installed in the Supabase-style extensions namespace. Authenticated groups/types/query/Updates/Pulse calls passed; numeric validation rejected malformed amounts.
- Two synthetic financial observations with the same explicit reference resulted in one active and one superseded event. Both distinct evidence records remained on the active event.
- Generated deployment staging now removes stale source/migration subdirectories before copying, preventing deleted migrations from leaking into a later bundle.
- A PostgreSQL 17 application-schema backup completed at /tmp/vox-before-redesign-20261009.dump (private permissions); pg_restore successfully listed the archive. Remote inventory found 96 public tables and no cross-schema foreign keys into public. Database remains unchanged.
- Google Cloud topic vox-gmail-events and dedicated vox-gmail-push identity exist. Permission bindings/subscription await action-time confirmation. Storage credentials remain staged in Railway; no deployment was performed.
- Native app launch command succeeded, but computer control continues to report a locked Mac. User unlock requested. Permanent application reset also awaits explicit action-time confirmation required by computer-control policy.
- Latest API ingestion emitted the canonical vox_timeline_updated PostgreSQL notification after commit; delivery verified in a separate LISTEN connection.

## Approved rollout on October 10
- User approved Google IAM delivery permissions and permanent application reset. Dedicated Gmail publisher and Pub/Sub token-creator bindings applied; authenticated vox-gmail-live subscription is active with exact endpoint/audience. Pub/Sub API enabled.
- API and worker shared-storage service credential configuration applied. Private vox-attachments bucket created with 50 MiB storage limit.
- Old API/worker/Bridge deployments stopped. Fresh private application backup saved at /tmp/vox-before-redesign-20261010.dump. Approved application-only reset committed, preserving managed schemas and extension-member objects.
- Actual SQLx bootstrap applied all six baseline migrations and published six reviewed default skills to two deployments. Live database contains six groups, nineteen event types, zero timeline events; auth schema and existing extensions verified preserved.
- CLI server uploads: API e7b9117f-f73f-498f-8ed4-dfa1fb4e904f; worker ff074a17-768b-453e-8cc3-75dad0e020f0; Bridge 8f5a6aa7-0973-4e26-96dc-93a3833d5fd0. Builds are in progress; upload is not deployment success.
- Native Vox control now works. Restarted exact rebuilt bundle, verified onboarding and navigable shell. Authenticated server flows still await deployed services and fresh session after reset.
