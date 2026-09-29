# Vox Deploy

`vox-deploy` is the production release authority for the Vox backend. It deploys immutable Core and Bridge images with Redis through Docker Compose, verifies the complete backend, and restores the last healthy release when a rollout fails. Vox Web remains on Vercel.

## GitHub configuration

Create a protected `production` environment and add these encrypted secrets:

- `SERVER_HOST`: production server host.
- `SERVER_USER`: SSH user with passwordless sudo for the deployment commands.
- `SSH_PRIVATE_KEY`: private key accepted by the production server.
- `SOURCE_REPO_TOKEN`: token with read access to the private Core and Bridge repositories.

The deployment repository checks out the exact Core and Bridge commits, builds both ARM64 images, and publishes them under its own GHCR namespace. Its short-lived `GITHUB_TOKEN` publishes the images and pulls them on the server; no permanent server registry credential or cross-repository package permission is needed.

Core and Bridge each need `VOX_DEPLOY_DISPATCH_TOKEN`, scoped to send repository dispatches to this private repository. Keep the `VOX_AUTO_DEPLOY` repository variable set to `false` until the first manual release passes real incoming and outbound call checks.

## Server bootstrap

The production release provisions Bridge as a registered `vox-bridge` host app after the new Core has migrated and passed readiness. Core issues a host signing credential once; the release stores it in root-owned mode-0600 `/etc/vox.bridge.env`, which only Bridge loads. Later releases reuse it and do not register another credential. Back up this protected file alongside `/etc/vox.local.env`. If host registration or protected storage fails, rollout stops. A failed rollout after Core migrations keeps the migration-compatible Core running while restoring the previous Bridge image; migration history must never be rolled back by running an older Core binary.

Install Docker Engine, the Compose plugin, Caddy, `curl`, and `flock`. Create the production configuration without placing values in this repository:

```sh
sudo install -o root -g root -m 600 /dev/null /etc/vox.env
sudoedit /etc/vox.env
```

The file requires non-empty values for:

```text
DATABASE_URL
VOX_AUTH_TOKEN
GEMINI_API_KEY
EXA_API_KEY
GOOGLE_MAPS_API_KEY
TWILIO_ACCOUNT_SID
TWILIO_AUTH_TOKEN
TWILIO_FROM_NUMBER
ASSEMBLYAI_API_KEY
SARVAM_API_KEY
SUPABASE_URL
```

Optional:

```text
SUPABASE_JWT_SECRET
VOX_CREDENTIAL_KEY
VOX_MCP_OAUTH_CLIENTS
```

`VOX_CREDENTIAL_KEY` (32-byte hex) encrypts connected-app OAuth tokens; without it, connecting apps is unavailable. Never rotate it in place: tokens encrypted with the old key become unreadable and users must reconnect. It may live in Secret Manager (create it with the `generate-secret` workflow, which needs `secretmanager.secrets.create`) or be generated on the server into `/etc/vox.local.env`, which Core services also load and which `sync-secrets-from-gsm` never overwrites:

```sh
sudo sh -c 'umask 077; [ -s /etc/vox.local.env ] || printf "VOX_CREDENTIAL_KEY=%s\n" "$(openssl rand -hex 32)" > /etc/vox.local.env'
```

Back up `/etc/vox.local.env` with the database: losing it disconnects every app. `VOX_MCP_OAUTH_CLIENTS` is a JSON map from MCP endpoint host to an OAuth client, for apps without dynamic client registration, for example `{"mcp-gateway-external-pilot.spotify.net": {"client_id": "..."}}`.

For the registered Vox Connections GitHub App, use [GitHub MCP setup](docs/github-mcp-setup.md). It records the exact callback, least-privilege app permissions, token authentication configuration, secure credential custody, and live release gates.

`SUPABASE_URL` is required for desktop and other clients that exchange Supabase sessions via `/v1/auth/exchange` and `/v1/me`. Core verifies access tokens against `{SUPABASE_URL}/auth/v1/.well-known/jwks.json` (ES256 signing keys). Keep `SUPABASE_JWT_SECRET` only if you still issue legacy HS256 tokens. Caddy routes `/v1/*` to Core and `/bridge/*` to Bridge.

The deployment supplies all internal service URLs. Do not put `REDIS_URL`, `VOX_CORE_URL`, or `VOX_BRIDGE_URL` in `/etc/vox.env`.

## First production release

Run the `deploy-production` workflow through `workflow_dispatch`. Supply the full tested Core and Bridge commit SHAs and set `deploy` to `true`. Vox Deploy builds both images, pins their registry digests, and rolls them out as one backend release. Leave `deploy` at its safe default of `false` to verify checkout and image publication without touching production.

The first release starts Redis and Core before stopping `vox-bridge.service`. If containerized Bridge fails, deployment automatically restarts the systemd service. After deployment passes, make one incoming call and trigger one autonomous outbound call before enabling automatic dispatch.

## Automatic releases

Set `VOX_AUTO_DEPLOY=true` in Core and Bridge after the first release is accepted. Each successful component validation then sends `component_ready`. Vox Deploy pairs that exact commit with the current main commit of the other backend repository, builds both images, and deploys the complete Compose model.

## Rollback

Use `workflow_dispatch` with the Core and Bridge SHAs recorded by the last healthy workflow. The deployment rebuilds those exact revisions, while the server retains `/opt/vox/state/previous.env` for automatic rollback. Deployment never removes `/etc/vox.env`, PostgreSQL data, or the Redis volume.

## Local verification

```sh
tests/run.sh
```

## Library defaults

Every backend rollout runs `vox-core-defaults` after Core migrations. It publishes six curated, declarative skills for each configured deployment by immutable content digest. Rerunning it does not install skills, enable them for agents, or create new versions when content is unchanged. Operator registration also seeds defaults for a newly created deployment. Core's `Cargo.lock` pins the exact Connections and Shared Git revisions used in the image. Starter service apps remain unpublished until real OAuth configuration and live provider evidence exist.
