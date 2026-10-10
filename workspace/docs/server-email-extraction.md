# Server email and financial extraction

Gmail and financial document processing now run on Core. Desktop and Android do not need Ollama or a LiteRT email model, and do not receive Gmail OAuth access tokens for historical review.

| Flow | Processing |
| --- | --- |
| New mail | Signed Pub/Sub notification persists the maximum pending history ID; the worker polls pending work every 10 seconds, with five-minute failure backoff and periodic reconciliation. |
| Historical review | An explicit client request supplies dates and an optional provider page token. Core fetches up to three messages, classifies them concurrently, and returns candidates. No automatic historical backfill is added. |
| Historical import | The client sends selected provider message IDs. Core re-fetches and extracts authoritative source data, then uses the same idempotent ingestion path as live mail. |
| PDF | Server decoding and password resolution precede Gemini extraction. Multiple validated events can be created from a document. Password-required and parse/review outcomes remain in Updates. |

Financial regex extraction has been removed. Regex remains for OTP redaction, which does not extract financial facts.

The server requires its existing `GEMINI_API_KEY`. Optional `VOX_DOCUMENT_MODEL` overrides the existing default Gemini model. Both API and worker processes need this configuration. Model content telemetry is disabled for document extraction; completion logs record duration and event counts rather than document text.

Extraction is bounded to four concurrent model calls per process, a 10-second capacity wait, a 45-second provider deadline, 200,000 input/output bytes and 100 events. Historical requests have a separate two-request concurrency limit. Oversized or uncertain documents require review rather than silent truncation or default spending classifications.

Every accepted event requires source evidence and an explicit observed date/time. Financial events also require a complete amount token, matching numeric value, explicit currency evidence, and valid direction/spending semantics. Indian and Western digit grouping are supported. Refunds, bills, statements, transfers, repayments and credit income cannot be counted as purchases by their validated semantics.

PDF object reads, decoding and model calls no longer hold database transactions. Saving results reacquires locks and checks the job owner, lease generation and expiry. Gmail ingestion checks pause/authorization before extraction and rechecks the credential generation under a connection lock before saving.

The model can still make semantic mistakes despite evidence checks; validation is not proof that every classification is correct. Unsupported or insufficiently certain results are withheld from the timeline. Existing incorrectly extracted timeline events are not automatically rewritten by this change.

Local verification passed: strict Core Clippy, existing Core tests, desktop production build and lint, Tauri cargo check, Android Kotlin compilation, API contract consistency and a synthetic financial validation probe. Database-dependent tests remain ignored without their isolated fixtures. No live Gmail/Gemini call or production deployment was performed.
