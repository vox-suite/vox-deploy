# Self-Hosted Reference Stack Guide

This guide details the deployment, verification, backup, upgrade, and disaster recovery procedures for the Vox Platform V1 open reference stack (`compose.self-hosted.yml`).

---

## 1. Architecture Overview

The self-hosted reference stack runs entirely on open infrastructure without proprietary cloud services or unvetted external dependencies.

```
                           ┌──────────────┐
                           │ User / Client│
                           └──────┬───────┘
                                  │
                  ┌───────────────┴───────────────┐
                  ▼                               ▼
          ┌───────────────┐               ┌───────────────┐
          │    vox-web    │               │    bridge     │
          │ (Consumer UI) │               │(Voice/WhatsApp│
          └───────┬───────┘               └───────┬───────┘
                  │                               │
                  └───────────────┬───────────────┘
                                  ▼
                         ┌─────────────────┐
                         │    core-api     │
                         │ (Authority API) │
                         └────────┬────────┘
                                  │
                      ┌───────────┴───────────────────┐
                      │                               │
                      ▼                               ▼
             ┌─────────────────┐             ┌─────────────────┐
             │   core-worker   │             │ portable-agent  │
             │ (Async Tasks)   │             │ (Agent Package) │
             └────────┬────────┘             └─────────────────┘
                      │
        ┌─────────────┴─────────────┐
        ▼                           ▼
 ┌──────────────┐            ┌──────────────┐
 │ PostgreSQL 18│            │   Redis 7    │
 │ (State Store)│            │(Queues/Cache)│
 └──────────────┘            └──────────────┘
```

### Components
1. **`postgres` (PostgreSQL 18)**: Durable persistence with `pgvector` for tasks, conversations, connections, grants, audit events, and user preferences (`pgvector/pgvector:pg18`).
2. **`redis` (Redis 7)**: Distributed locking, job queues, and transient session caching.
3. **`core-api` (`vox-core`)**: Central platform authority exposing public REST contracts for tasks, proposals, approvals, connections, grants, privacy, and audit.
4. **`core-worker` (`vox-core`)**: Background runner for durable task execution, reminder scheduling, and transactional outcome reconciliation.
5. **`bridge` (`vox-bridge`)**: Telephony (Twilio) and messaging (WhatsApp) channel ingress and notification delivery.
6. **`vox-web` (`vox-web`)**: Modern, accessible Next.js web application for consumer authentication, journeys, and privacy management.
7. **`portable-agent` (`agents`)**: Portable, model-neutral agent runner delegating authority strictly to Core.
8. **`conformance-sandbox`**: Deterministic transactional test environment for validating provider capabilities and simulated faults without live external accounts.

---

## 2. Clean Installation

### Prerequisites
- Docker Engine 24.0+ & Docker Compose v2.20+
- 4 GB RAM, 2 vCPUs, 20 GB SSD storage
- Open ports: `80`, `443` (for web/API ingress)

### Step 1: Clone and Review Manifest
```bash
git clone https://github.com/vox-suite/vox-deploy.git
cd vox-deploy

# Inspect the verified repository revision manifest
cat deployments/manifest.json
```

### Step 2: Configure Environment
Copy the self-hosted environment template and fill in your secrets. Ensure this file is never committed or made client-readable:
```bash
cp .env.self-hosted.example .env.self-hosted
chmod 600 .env.self-hosted
vim .env.self-hosted
```

Webhook subscriptions are optional. To enable them, generate a 32-byte key
with `openssl rand -hex 32`, retain it in an operator-managed secret store,
and export the same `VOX_STATUS_WEBHOOK_KEY` into the Compose process on every
start. Keep it out of `.env.self-hosted`, which is shared with other services.
Only Core API and Core Worker receive this variable. Losing the key makes
existing subscriptions unreadable; cursor polling remains available.

### Step 3: Launch the Stack
```bash
docker compose -f compose.self-hosted.yml up -d
```

### Step 4: Verify Service Health
```bash
docker compose -f compose.self-hosted.yml ps
curl -f http://localhost:3001/health/ready
curl -f http://localhost:3000/health
```

---

## 3. Independent Second-Host Acceptance

The reference stack supports an independently implemented second host communicating exclusively over Core's public API without private internals:

```bash
bash scripts/second-host-acceptance-check.sh
```

---

## 4. Backup and Disaster Recovery

### Creating a Backup
```bash
bash scripts/backup.sh
```
This dumps the PostgreSQL durable state into `backups/vox_backup_<timestamp>.sql.gz` and records metadata.

### Restoring State
```bash
bash scripts/restore.sh backups/vox_backup_<timestamp>.sql.gz
```
The restore script verifies database integrity and proves that durable tasks, proposals, and audit records remain intact.

---

## 5. Upgrade, Database Migration, and Rollback

### Supported Application Upgrade
To upgrade to a newer verified manifest revision:
1. Pull the updated `manifest.json`.
2. Run database migrations:
   ```bash
   docker compose -f compose.self-hosted.yml run --rm core-api /usr/local/bin/vox-core-migrate
   ```
3. Restart services gracefully:
   ```bash
   docker compose -f compose.self-hosted.yml up -d --no-deps core-api core-worker bridge vox-web
   ```

### Major Database Upgrade (PostgreSQL 17 to PostgreSQL 18)
Because PostgreSQL major versions do not permit mounting an older data directory without upgrade tooling, major engine upgrades follow this migration procedure:
1. **Take a complete backup of PostgreSQL 17**:
   ```bash
   bash scripts/backup.sh
   # Verify the archive is created in backups/vox_backup_<timestamp>.sql.gz
   ```
2. **Stop the services**:
   ```bash
   docker compose -f compose.self-hosted.yml down
   ```
3. **Archive the existing PostgreSQL 17 volume**:
   ```bash
   docker volume create postgres-data-pg17-backup
   # Preserve postgres-data intact for rollback
   ```
4. **Update `compose.self-hosted.yml` to PostgreSQL 18**:
   Ensure `image: pgvector/pgvector:pg18` is configured.
5. **Start the fresh PostgreSQL 18 container and restore state**:
   ```bash
   docker compose -f compose.self-hosted.yml up -d postgres
   bash scripts/restore.sh backups/vox_backup_<timestamp>.sql.gz
   ```
6. **Start all platform services**:
   ```bash
   docker compose -f compose.self-hosted.yml up -d
   ```

### Rollback (NFR-REL-004)
If a rollout fails:
1. Re-deploy the previously verified commit SHAs recorded in `manifest.json`.
2. Existing PostgreSQL durable task states and Redis data are preserved.
3. For major database rollbacks, reverting the Compose image tag to `pgvector/pgvector:pg17` allows re-attaching the preserved `postgres-data-pg17-backup` volume immediately without data loss.
