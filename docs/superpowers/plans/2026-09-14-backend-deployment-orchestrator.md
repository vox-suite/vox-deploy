# Vox Backend Deployment Orchestrator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a private `vox-deploy` repository that receives tested Core and Bridge image events and atomically deploys or rolls back the complete Vox backend on the existing ARM64 server.

**Architecture:** Core and Bridge publish immutable GHCR images from their own CI. `vox-deploy` merges an incoming component SHA with the last healthy release, uploads a production Compose model and deployment engine, and performs a serialized health-gated rollout over SSH.

**Tech Stack:** Bash 5, Docker Compose v2, GitHub Actions, GHCR, Redis 8, Rust ARM64 containers, systemd, Caddy, Supabase PostgreSQL

**Spec:** `docs/superpowers/specs/2026-09-14-backend-deployment-orchestrator-design.md`

## Global Constraints

- `vox-web` remains deployed by Vercel and is not referenced by this repository.
- Production image tags use full 40-character Git SHAs and releases pin their published `sha256` digests; never deploy `latest`.
- Caddy remains on the host and proxies Bridge at `127.0.0.1:3000`.
- `/etc/vox.env` is root-owned mode `0600` and is never printed or overwritten by deployment.
- PostgreSQL and the Redis volume are never deleted by deployment or rollback.
- Core Worker starts only after Core API and Bridge are healthy.
- The first rollout can return to `vox-bridge.service`; later rollbacks restore the previous Compose image pair.

---

### Task 1: Release contract

**Files:**
- Create: `scripts/release.sh`
- Create: `tests/release_test.sh`

**Interfaces:**
- Consumes: `component`, `sha`, `current.env`, and fixed GHCR image names.
- Produces: `validate_component`, `validate_sha`, and `write_candidate_release COMPONENT SHA CURRENT OUTPUT`.

- [ ] **Step 1: Write the failing release tests**

Test literal valid and invalid component names, SHA lengths and characters, first-release requirements, and preservation of the unchanged component. Assert an exact candidate file:

```text
CORE_IMAGE=ghcr.io/vox-suite/vox-core@sha256:core-digest
CORE_SHA=1111111111111111111111111111111111111111
BRIDGE_IMAGE=ghcr.io/vox-suite/vox-bridge@sha256:bridge-digest
BRIDGE_SHA=2222222222222222222222222222222222222222
```

- [ ] **Step 2: Verify the tests fail**

Run: `bash tests/release_test.sh`

Expected: failure because `scripts/release.sh` does not exist.

- [ ] **Step 3: Implement the release functions**

Use Bash pattern validation, write to `mktemp` in the output directory, set mode `0600`, and rename atomically. Parse only the four allowed assignment names; never `source` an untrusted dispatch payload.

- [ ] **Step 4: Verify and commit**

Run: `bash tests/release_test.sh && shellcheck scripts/release.sh tests/release_test.sh`

Commit: `feat: add immutable release contract`

### Task 2: Production Compose model

**Files:**
- Create: `compose.prod.yml`
- Create: `tests/compose_test.sh`

**Interfaces:**
- Consumes: `/etc/vox.env`, `CORE_IMAGE`, and `BRIDGE_IMAGE`.
- Produces: services `redis`, `core-api`, `core-worker`, and `bridge` in project `vox`.

- [ ] **Step 1: Write the failing Compose contract test**

Render with literal image digests and a temporary environment file. Assert that only `127.0.0.1:3000:3000` is published, Redis has AOF plus a named volume, Core API and Bridge have health checks, Worker has no port, and internal URLs equal `redis://redis:6379`, `http://core-api:3001`, and `http://bridge:3000`.

- [ ] **Step 2: Verify the test fails**

Run: `bash tests/compose_test.sh`

Expected: failure because `compose.prod.yml` does not exist.

- [ ] **Step 3: Implement the Compose model**

Use `image: ${CORE_IMAGE:?}` for both Core services, `image: ${BRIDGE_IMAGE:?}` for Bridge, `env_file: /etc/vox.env`, `restart: unless-stopped`, health-conditioned dependencies, and a pinned Redis 8 Alpine image digest.

- [ ] **Step 4: Verify and commit**

Run: `bash tests/compose_test.sh && docker compose -f compose.prod.yml config --quiet`

Commit: `feat: add production backend topology`

### Task 3: Health-gated deployment engine

**Files:**
- Create: `scripts/deploy-vox.sh`
- Create: `tests/deploy_test.sh`
- Create: `tests/fakes/command`

**Interfaces:**
- Consumes: `--component`, `--sha`, `--image`, `--ghcr-user`, `--ghcr-token-file`; `/opt/vox/state/current.env`; `/etc/vox.env`.
- Produces: updated `current.env`, retained `previous.env`, healthy Compose services, and nonzero exit on rejected input or failed rollout.

- [ ] **Step 1: Write failing integration scenarios**

Use a temporary root and command-log fake. Cover: invalid input changes nothing; missing config fails before systemd; image pull fails before systemd; first rollout orders Core before stopping systemd and Worker last; failed first Bridge health restarts systemd; normal rollout preserves the unchanged image; failed normal rollout restores the previous release.

- [ ] **Step 2: Verify the tests fail**

Run: `bash tests/deploy_test.sh`

Expected: failure because `scripts/deploy-vox.sh` does not exist.

- [ ] **Step 3: Implement validation and preflight**

Require Bash strict mode, acquire `flock -n 9`, validate command availability, validate root ownership and numeric mode `600` outside tests, and check every required key by name without printing values. Test PostgreSQL reachability with the Core image before pulling down any live service.

- [ ] **Step 4: Implement rollout and rollback traps**

Pull candidate images into an ephemeral `DOCKER_CONFIG`, start `redis core-api`, poll health with bounded attempts, cut over Bridge, start Worker, verify the public endpoint, then promote state. Install an `EXIT` trap after cutover begins; it restores Compose or systemd based on whether `current.env` exists.

- [ ] **Step 5: Verify and commit**

Run: `bash tests/deploy_test.sh && shellcheck scripts/deploy-vox.sh tests/deploy_test.sh tests/fakes/command`

Commit: `feat: add rollback-safe deployment engine`

### Task 4: Orchestrator workflows

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `.github/workflows/deploy.yml`
- Create: `tests/workflow_test.sh`
- Create: `README.md`

**Interfaces:**
- Consumes: `repository_dispatch` type `component_published` and manual `core_sha` plus `bridge_sha`; GitHub production environment secrets.
- Produces: one serialized SSH invocation of `deploy-vox.sh` and a GitHub deployment summary containing only repository names and SHAs.

- [ ] **Step 1: Write failing workflow contract tests**

Parse both YAML files and assert exact triggers, `contents: read`, production environment, `concurrency.group: production`, `cancel-in-progress: false`, payload validation, temporary credential cleanup, and no secret interpolation in SSH command arguments.

- [ ] **Step 2: Verify the tests fail**

Run: `bash tests/workflow_test.sh`

Expected: failure because the workflows do not exist.

- [ ] **Step 3: Implement CI and deployment workflows**

CI runs all shell tests, ShellCheck, and Compose rendering. Deploy resolves event or manual inputs, copies only the Compose file, scripts, and a mode-`0600` GHCR token file, invokes the server script, removes temporary files in an `always()` step, and writes the deployed SHAs to the job summary.

- [ ] **Step 4: Document bootstrap and recovery**

README commands must create `/opt/vox`, install `/etc/vox.env` with exact required key names, describe repository secrets `SERVER_HOST`, `SERVER_USER`, `SSH_PRIVATE_KEY`, `GHCR_PULL_TOKEN`, and `GHCR_USER`, and show manual first deployment and explicit rollback inputs without containing credential examples.

- [ ] **Step 5: Verify and commit**

Run: `bash tests/workflow_test.sh && bash tests/release_test.sh && bash tests/compose_test.sh && bash tests/deploy_test.sh`

Commit: `feat: orchestrate production releases`

### Task 5: Core image publication

**Files:**
- Create in `../vox-core`: `.github/workflows/publish.yml`
- Create in `../vox-core`: `tests/publish_workflow.rs`

**Interfaces:**
- Consumes: Core `main`, `GITHUB_TOKEN`, `VOX_DEPLOY_DISPATCH_TOKEN`, and repository variable `VOX_AUTO_DEPLOY`.
- Produces: `ghcr.io/vox-suite/vox-core:<sha>` for Linux ARM64 and an optional `component_published` dispatch.

- [ ] **Step 1: Write a failing workflow contract test**

Assert push-to-main and manual triggers, tests plus strict Clippy before publication, ARM64 platform, full SHA tag, package write permission, digest output, and dispatch gated by `VOX_AUTO_DEPLOY == 'true'`.

- [ ] **Step 2: Verify the test fails**

Run: `cargo test --locked --test publish_workflow`

Expected: failure because `.github/workflows/publish.yml` does not exist.

- [ ] **Step 3: Implement, verify, and commit**

Run: `cargo test --locked && cargo clippy --locked --all-targets --all-features -- -D warnings`

Commit: `ci: publish Core release images`

### Task 6: Bridge image publication and legacy transition

**Files:**
- Create in `../vox-bridge`: `.github/workflows/publish.yml`
- Create in `../vox-bridge`: `tests/publish_workflow.rs`
- Modify in `../vox-bridge`: `.github/workflows/deploy.yml`

**Interfaces:**
- Consumes: Bridge `main`, `GITHUB_TOKEN`, `VOX_DEPLOY_DISPATCH_TOKEN`, and `VOX_AUTO_DEPLOY`.
- Produces: `ghcr.io/vox-suite/vox-bridge:<sha>` for Linux ARM64 and an optional dispatch.

- [ ] **Step 1: Write a failing workflow contract test**

Assert the same publication gates as Core and require the legacy systemd workflow to be manual-only, preventing future source pushes from bypassing `vox-deploy`.

- [ ] **Step 2: Verify the test fails**

Run: `cargo test --locked publish_workflow`

Expected: failure because `.github/workflows/publish.yml` does not exist and legacy deploy still triggers on push.

- [ ] **Step 3: Implement, verify, and commit**

Run: `cargo test --locked && cargo clippy --locked --all-targets --all-features -- -D warnings && cargo build --release --locked`

Commit: `ci: hand releases to Vox Deploy`

### Task 7: Repository publication and safe bootstrap

**Files:**
- Modify: GitHub repository settings and encrypted secrets only.

**Interfaces:**
- Consumes: the authenticated `vox-suite` GitHub account and existing server SSH configuration.
- Produces: private `vox-suite/vox-deploy`, source dispatch secrets, GHCR package access, and a manual first-release workflow ready to run.

- [ ] **Step 1: Publish the repository**

Create private `vox-suite/vox-deploy`, add it as `origin`, push `main`, and verify local and remote commit IDs match.

- [ ] **Step 2: Configure dispatch without exposing credentials**

Pipe the deployment API credential directly into `gh secret set VOX_DEPLOY_DISPATCH_TOKEN` for Core and Bridge. Set `VOX_AUTO_DEPLOY=false` in both repositories until the first real-call verification succeeds.

- [ ] **Step 3: Configure production environment protection**

Create the `production` environment in `vox-deploy`. Transfer server and GHCR credentials through `gh secret set` standard input only when matching local credentials are available; otherwise leave the workflow safely blocked with explicit missing-secret validation.

- [ ] **Step 4: Verify repository and workflow state**

Run all local tests, inspect GitHub workflow parsing, confirm all worktrees are clean and match `origin/main`, and confirm no automatic production deployment was triggered before `/etc/vox.env` contains the Supabase connection.

- [ ] **Step 5: Commit final documentation corrections**

Commit: `docs: finalize production bootstrap`
