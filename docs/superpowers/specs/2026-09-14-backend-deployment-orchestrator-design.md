# Vox Backend Deployment Orchestrator Design

## Purpose

`vox-deploy` is the single production release authority for the Vox backend. It receives successful image-publication events from `vox-core` and `vox-bridge`, deploys an exact pair of immutable image versions to the existing server, verifies the complete backend, and restores the last healthy release when verification fails.

`vox-web` is excluded because Vercel owns its deployment lifecycle.

## Repositories and responsibilities

- `vox-core` tests Core, builds one Linux ARM64 image containing `vox-core-api` and `vox-core-worker`, publishes `ghcr.io/vox-suite/vox-core:<git-sha>`, and dispatches the published SHA to `vox-deploy`.
- `vox-bridge` tests Bridge, publishes `ghcr.io/vox-suite/vox-bridge:<git-sha>`, and dispatches the published SHA to `vox-deploy`. Its existing direct systemd deployment is removed after the orchestrator is ready.
- `vox-deploy` owns the production Compose definition, deployment script, release manifests, health gates, rollback, and the GitHub Actions workflow that reaches the server.

Source repositories never deploy production directly. Image tags use the full Git commit SHA and deployment uses the resulting image digest; `latest` is never deployed.

## Event and release model

Each source repository sends a `repository_dispatch` event only after its tests, lint, release build, and image publication succeed. The payload contains:

- `component`: `core` or `bridge`
- `sha`: the 40-character source commit SHA
- `image`: the expected GHCR repository pinned to the published `sha256` digest

The orchestrator serializes production runs with the GitHub Actions `production` concurrency group and a server-side `flock`. An event updates only its component in the candidate release. The other component remains pinned to the currently deployed healthy SHA. A manual workflow accepts explicit Core and Bridge SHAs for coordinated releases and rollback.

The server stores the active release in `/opt/vox/state/current.env` and the previous healthy release in `/opt/vox/state/previous.env`. These files contain image coordinates and commit SHAs, not credentials.

## Production topology

Caddy remains a host service and proxies `api.voxagent.in` to `127.0.0.1:3000`.

Docker Compose runs:

- `redis`: Redis 8 with AOF persistence in a named volume and no published port.
- `core-api`: the Core image running `vox-core-api`, bound only to host loopback at `127.0.0.1:3001`, with a readiness health check. This lets the systemd Bridge reach Core during the first cutover without exposing Core publicly.
- `core-worker`: the same Core image running `vox-core-worker`, with no published port and exactly one replica.
- `bridge`: the Bridge image, publishing only `127.0.0.1:3000:3000`.

Core API, Core Worker, Bridge, and Redis share one private Compose network. Supabase PostgreSQL remains external and authoritative. Redis contains only rebuildable projections.

## Configuration and secrets

The server owns `/etc/vox.env` as root with mode `0600`. The deployment workflow never prints or replaces this file. It must contain:

- `DATABASE_URL`
- `VOX_CORE_SERVICE_TOKEN`
- `GEMINI_API_KEY`
- `EXA_API_KEY`
- `GOOGLE_MAPS_API_KEY`
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_FROM_NUMBER`
- `ASSEMBLYAI_API_KEY`
- `SARVAM_API_KEY`

Optional model and voice selections keep their application defaults. Compose supplies internal URLs such as `REDIS_URL`, `VOX_CORE_URL`, and `VOX_BRIDGE_URL` so operators cannot accidentally point containers at localhost.

GitHub stores server SSH credentials and the source-to-orchestrator dispatch credential as encrypted repository secrets. The orchestrator uses its short-lived `GITHUB_TOKEN` with explicit read access to both GHCR packages. Secret values are passed through temporary mode-`0600` files, consumed through standard input where supported, and removed before the workflow finishes.

## Deployment algorithm

1. Acquire `/var/lock/vox-deploy.lock` without waiting. A concurrent deployment exits without changing production.
2. Validate the candidate component, both 40-character SHAs, image names, required commands, `/etc/vox.env` ownership and mode, and all required non-empty configuration keys.
3. Confirm the server can connect to the configured Supabase PostgreSQL endpoint before changing containers.
4. Authenticate to GHCR with an ephemeral Docker configuration and pull every candidate image before touching the running release.
5. Render the candidate release file atomically and validate the Compose model.
6. Start Redis and Core API. Core applies its backward-compatible migrations during startup. Wait for Redis and Core readiness.
7. On the first container deployment, leave the systemd Bridge running until Core is ready, stop and disable `vox-bridge.service`, then start the Bridge container. On later deployments, Compose replaces the Bridge container normally.
8. Wait for local Bridge health, then start Core Worker.
9. Verify Redis health, Core readiness, Bridge health, worker running state, and `https://api.voxagent.in/health`.
10. Atomically promote the candidate release to `current.env`, retain the former current release as `previous.env`, and prune only unused images older than the retained releases.

The worker starts last so it cannot dispatch autonomous calls through an unhealthy Bridge.

## Failure and rollback

No failure before the Bridge cutover affects the existing live Bridge.

After a failed first cutover, the script removes the failed Bridge container and restarts `vox-bridge.service`. After a failed later deployment, it restores the previous image pair and runs Compose again. It rechecks Core, Bridge, and Worker before declaring rollback successful.

The script never deletes PostgreSQL data, the Redis volume, `/etc/vox.env`, or release history. Database migrations use expand-and-contract changes so the previous application image remains compatible after migration. A migration that requires destructive contraction is a separate, explicitly approved production operation.

## Verification

Repository checks cover payload validation, release merging, configuration validation, Compose rendering, first-cutover behavior, normal deployment, and rollback using command fakes in an isolated temporary directory. Shell files pass `shellcheck`; Compose passes `docker compose config`; workflows parse as YAML.

Production success requires all GitHub Actions jobs to pass, all container health gates to pass, the public endpoint to return `ok`, and the deployed release file to contain the requested component SHA. This does not by itself prove the voice-provider path; the first production cutover also requires one incoming call and one event-driven outbound call before the systemd fallback is retired permanently.

## Initial rollout

The first orchestrated deployment is manual with explicit known-good Core and Bridge SHAs. Automatic `repository_dispatch` triggers are enabled only after that release passes the real-call checks. Until then, source repositories publish images but do not initiate production deployment.
