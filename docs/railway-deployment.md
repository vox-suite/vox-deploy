# Active Railway deployment

## Verified configuration — 2026-10-02

The official Railway CLI completed the approved transfer of the existing
`VOX_CREDENTIAL_KEY` and GitHub `VOX_MCP_OAUTH_CLIENTS` from owner-only VM files
to Core API and worker through stdin. Values were neither displayed nor committed.
Read-back checks confirmed both keys present, valid OAuth JSON and matching
selected values across the two services. The encryption key was preserved.
Updates used `--skip-deploys`. Subsequent redeployments of the already reviewed
Core revision `e4b05ee6718a53a28bf28f4f0c2604350927a980` succeeded: API
`db301cb9-da61-49e2-8256-c3f08783d901` and worker
`20d7ad6a-abb9-41e8-bc72-01b744adf5c0`. This proves deployment activation,
not a successful external connector or worker/model journey.

Wait for CI is enabled for Core API, worker, Bridge and Caddy. Each has an active code
checks workflow. Core API and Bridge use `/health/ready` with a 120-second startup
timeout. The worker does not serve HTTP and has no HTTP healthcheck. Edge PR 2
adds production-image Caddy routing checks, including WebSocket forwarding and
private endpoint/probe rejection. Edge PR 4 makes the manual secret-sync workflow
require an exact environment and explicit secret allowlist; unreadable selections
prevent writes and partial writes fail honestly. No live secret-sync operation
was performed as part of those changes.

A fresh PostgreSQL connection using protected Railway configuration and the
official Supabase CA passed `verify-full` TLS validation. Both database identity
and `SUPABASE_URL` match the Vox project. No database password reset or Google
service-account repair was necessary.

The reviewed private identity-pin migration was applied through the official
Supabase CLI after a dry run selecting only
`20261001174921_consumer_session_identity_pins.sql`. The dashboard confirms
`vox_auth.custom_access_token_hook` is registered and Enabled. The migration
includes MFA continuity and explicit least-privilege grants. Live sign-in, MFA
and refresh proof remain release gates for the strict Web/native adapters. Native clients must
use exchange-issued opaque Vox sessions. Keep held Web changes separate from
automatic production deployment until these gates pass.

Read-only live privilege checks confirmed the Auth role's required read/insert
access, immutable pins, enabled row security and an invoker hook. Browser-facing
and service roles cannot access the private pin schema. Core API now has the
existing public `SUPABASE_PUBLISHABLE_KEY` for fresh-user verification; this
configuration used `--skip-deploys` and does not prove the held native adapter is
deployed. The worker does not need this public Auth API key.

Vox Web remains on Vercel, in a team inaccessible to the connected operator.
The account owner must verify Web's public Supabase configuration, matching
Core-issued host credential pair, domain and exact OAuth callbacks, then rebuild
the approved revision and exercise live sign-in. Railway backend work does not
establish Web deployment readiness. Keep its authentication and delegation UI
release stack held pending those checks.

Current evidence and remaining connector certification are tracked in
[Deploy issue 19](https://github.com/vox-suite/vox-deploy/issues/19#issuecomment-5944836304).
The observations below are historical; they do not override this checkpoint.

Observed 2026-09-30 through the operator's signed-in project dashboard.

- Project: `00945ffa-7a84-4615-87e1-f37022b106ce`.
- Production environment: `5d93ef9e-01d6-43e0-93ad-aaba101db6e9`.
- Core API: `f57eb9c3-3cf0-495b-b956-0f42a5634632`.
- Core worker: `ea0fa725-45c7-4239-a99f-2c9804b28761`.
- Bridge: `7e55f3a0-dd8f-4b59-bdb8-972ffb9cffec`.
- Redis: `cd005786-226c-47d5-a694-d3bf9b5223f9`, with persistent volume.
- Caddy: `460d4fa7-e25b-43ac-8115-d2a5e13f1d5f`, serving `api.voxagent.in`.

All five displayed Online. Core API and worker displayed PR 110 active; API deployment details bind to commit `e946cb1114ff0834cbd35af97e095c92de7033ec`, deployment `19793f27-160c-41a0-bd5c-18cda54430af`. Bridge displayed PR 13 active. These observations prove source selection and process deployment, not complete connector certification.

The public `/health` returns `ok` from Caddy. It is gateway liveness, not a database probe. Public `/health/ready` returns 404. API startup accessed the migrations table and listened on port 8080; that is fresh database startup evidence, not continuing readiness. API settings did not show a configured healthcheck, and Wait for CI was off. Configure API `/health/ready`, Bridge `/health/ready`, and CI gating before treating automatic deployments as a verified release pipeline. Worker readiness requires its own evidence rather than assigning it an HTTP check it does not serve.

## Connector configuration

Core API variable names did not include `VOX_CREDENTIAL_KEY` or `VOX_MCP_OAUTH_CLIENTS` at initial inspection. The operator approved transferring the existing key and registered GitHub OAuth client configuration from the protected prior VM files into the Railway Core services. Preserve the encryption key: replacing it would make existing encrypted tokens unreadable. No database password reset is inferred from the old VM's failed login.

Bridge lists its host credential ID, audience and secret. Variable names alone do not prove that the host registration matches Core or that an authenticated conversation succeeds. Keep host signing credentials private to Bridge; keep OAuth clients and connection encryption keys private to Core. The shared variable set currently includes broad provider/database secrets across services; reduce each service's recipients deliberately after verifying its real dependencies.

Track completion and current evidence in [Deploy issue 19](https://github.com/vox-suite/vox-deploy/issues/19). Web PR 33 remains held until current host/runtime configuration is verified. Actual GitHub install, consent, inventory, granted read, denied second actor/context, refresh and revoke tests remain required. No reviewed package may be presented as ready merely because its code deployed.

## Retirement and recovery

The five VM/GSM GitHub Actions operational entry points have been retired. Railway owns hosted releases; Compose and protected-file helpers remain for standalone operation and recovery. Historical VM evidence does not establish current Railway readiness. Do not delete the old encryption key, backups or infrastructure while credential custody and live cutover are unverified.

Before rollback, check database migration compatibility. Reverting a Railway deployment does not revert PostgreSQL migrations and must not activate an incompatible old binary. Preserve exact source revisions and sanitized retained health, worker, host-boundary and connector evidence for every accepted release.
