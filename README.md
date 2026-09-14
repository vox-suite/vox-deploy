# Vox Deploy

`vox-deploy` is the production release authority for the Vox backend. It deploys immutable Core and Bridge images with Redis through Docker Compose, verifies the complete backend, and restores the last healthy release when a rollout fails. Vox Web remains on Vercel.

## GitHub configuration

Create a protected `production` environment and add these encrypted secrets:

- `SERVER_HOST`: production server host.
- `SERVER_USER`: SSH user with passwordless sudo for the deployment commands.
- `SSH_PRIVATE_KEY`: private key accepted by the production server.

The deployment job uses its short-lived `GITHUB_TOKEN` to pull Core and Bridge images. Grant `vox-deploy` Actions access to both GHCR packages; do not create a permanent server registry credential.

Core and Bridge each need `VOX_DEPLOY_DISPATCH_TOKEN`, scoped to send repository dispatches to this private repository. Keep the `VOX_AUTO_DEPLOY` repository variable set to `false` until the first manual release passes real incoming and outbound call checks.

## Server bootstrap

Install Docker Engine, the Compose plugin, Caddy, `curl`, and `flock`. Create the production configuration without placing values in this repository:

```sh
sudo install -o root -g root -m 600 /dev/null /etc/vox.env
sudoedit /etc/vox.env
```

The file requires non-empty values for:

```text
DATABASE_URL
VOX_CORE_SERVICE_TOKEN
GEMINI_API_KEY
EXA_API_KEY
GOOGLE_MAPS_API_KEY
TWILIO_ACCOUNT_SID
TWILIO_AUTH_TOKEN
TWILIO_FROM_NUMBER
ASSEMBLYAI_API_KEY
SARVAM_API_KEY
```

The deployment supplies all internal service URLs. Do not put `REDIS_URL`, `VOX_CORE_URL`, or `VOX_BRIDGE_URL` in `/etc/vox.env`.

## First production release

Run the `deploy-production` workflow through `workflow_dispatch`. Supply the full tested Core and Bridge commit SHAs and the corresponding `ghcr.io/vox-suite/...@sha256:...` image coordinates produced by their publication workflows.

The first release starts Redis and Core before stopping `vox-bridge.service`. If containerized Bridge fails, deployment automatically restarts the systemd service. After deployment passes, make one incoming call and trigger one autonomous outbound call before enabling automatic dispatch.

## Automatic releases

Set `VOX_AUTO_DEPLOY=true` in Core and Bridge after the first release is accepted. Each successful image publication then sends `component_published`; this workflow retains the healthy image for the unchanged component and deploys the complete Compose model.

## Rollback

Use `workflow_dispatch` with the Core and Bridge SHAs and digest-pinned image coordinates recorded by the last healthy workflow. The server also retains `/opt/vox/state/previous.env` for automatic rollback. Deployment never removes `/etc/vox.env`, PostgreSQL data, or the Redis volume.

## Local verification

```sh
tests/run.sh
```
