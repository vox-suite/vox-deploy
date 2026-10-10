# Server email extraction implementation plan

Goal: run Gmail fetching, relevance classification and financial extraction on Core, without a local model dependency.

Architecture: a shared bounded Gemini extractor produces validated timeline events from email/PDF text. Core fetches historical Gmail pages on explicit user action and imports selected provider IDs through the same ingestion path as live mail. Clients display server results and never supply authoritative extracted facts or provider attachments.

Constraints: no new code comments or tests; preserve existing visual components; never automatically backfill on connection; fail closed on ambiguous facts; preserve password-input Updates; validate amounts/dates against source evidence; no production deployment or data rewrite in this task.

- [x] Add shared structured server extraction with time/concurrency/input/output bounds and provenance validation.
- [x] Separate PDF text decoding from semantic extraction; remove regex financial extraction and ingest multiple validated facts.
- [x] Replace device-access/history upload APIs with authenticated server page/import APIs; share live ingestion, filtering and pause checks.
- [x] Remove Ollama/LiteRT email classification, model selectors and device attachment fetching on desktop/Android.
- [x] Update generated contracts and product documentation; run Rust, desktop and Android checks and targeted synthetic verification.

Review focus: refunds/repayments versus spending; Indian monetary grouping; prompt injection in email; missing dates or invented evidence; provider/model failure without silent raw-data fallback or cursor advancement.

Implementation record: Core, desktop and Android changes are local. Financial regex extraction and local Gmail model requirements were removed. The API and worker need GEMINI_API_KEY; VOX_DOCUMENT_MODEL optionally overrides the existing model default. Historical pages are limited to three messages with bounded concurrency; imports accept provider IDs and re-fetch authoritative data. Pub/Sub acknowledges after durably coalescing a pending history ID; workers process it. PDF extraction releases database locks and fences result writes by job generation.

Verification: Core strict Clippy and existing tests, desktop production build/lint, Tauri cargo check and Android Kotlin compilation. An external synthetic probe accepted full Indian amounts, refunds, repayments and credit income, and rejected amount truncation and refund/repayment spending flags. No live provider/model call, production deployment, existing timeline rewrite or new test file was performed.
