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
 │ PostgreSQL 18│            │  Redis 8.2   │
 │ (State Store)│            │(Queues/Cache)│
 └──────────────┘            └──────────────┘
```

### Components
1. **`postgres` (PostgreSQL 18)**: Durable persistence with `pgvector` for tasks, conversations, connections, grants, audit events, and user preferences (`pgvector/pgvector:pg18`). Its dedicated `postgres-data-pg18` volume mounts at `/var/lib/postgresql`, the PostgreSQL 18 image's data parent.
2. **`redis` (Redis 8.2 LTS)**: Distributed locking, job queues, and transient session caching.
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
nvim .env.self-hosted
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
The restore script checks counts for spans, jobs, and audit events. Compare these counts and representative identifiers with the source database before allowing application writes.

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
PostgreSQL 18 cannot start on a PostgreSQL 17 data directory. The Compose image also changed its data mount from `/var/lib/postgresql/data` to `/var/lib/postgresql`. The reference stack therefore uses a **new** `postgres-data-pg18` volume and leaves the old `postgres-data` volume untouched. Perform this procedure during an outage, before any PG18 application writes. A database already running PG18 with the former mount must also be backed up from its running container before changing Compose; its data may be in an anonymous Docker volume.

1. **While the old database is still running, stop application writers and take a logical backup using the old Compose revision**:
   ```bash
   bash scripts/backup.sh
   gzip -t backups/vox_backup_<timestamp>.sql.gz
   ```
   Keep the backup outside the Docker host as well. Record the current span, job, and audit row counts for comparison after restore.
2. **Stop the old stack, without removing its volumes**:
   ```bash
   docker compose -f compose.self-hosted.yml down
   ```
   Do not use `down -v`. Retain the old Compose revision for a PG17 rollback.
3. **Check out this revision with `pgvector/pgvector:pg18` and the dedicated `postgres-data-pg18:/var/lib/postgresql` mount. Start the new database and restore the logical backup**:
   ```bash
   docker compose -f compose.self-hosted.yml up -d postgres
   docker compose -f compose.self-hosted.yml exec -T postgres \
     psql -U "${POSTGRES_USER:-vox}" -d "${POSTGRES_DB:-vox}" -Atc 'SHOW server_version_num'
   bash scripts/restore.sh backups/vox_backup_<timestamp>.sql.gz
   ```
   Confirm the server version begins with `18`, the `vector` extension exists, and the restored span, job, and audit counts match the recorded counts. If restore fails, leave application writers stopped and investigate before retrying against a fresh PG18 database.
4. **Start all platform services**:
   ```bash
   docker compose -f compose.self-hosted.yml up -d
   ```
   Retain the PG17 volume and backup until the new stack has passed operational checks. A rollback to PG17 is safe only before writes occur on PG18; later writes require an explicit reverse migration or restore plan.

### Cache & Queue Engine Upgrade (Redis 7 to Redis 8.2 LTS)
Redis 8.2 LTS introduces single-allocation memory optimizations (25–37% RAM reduction) and backward-compatible RDB/AOF ingestion. However, persistence format changes in Redis 8.2 are a one-way ratchet:
1. **Take a snapshot backup of Redis 7**:
   ```bash
   docker compose -f compose.self-hosted.yml exec -T redis redis-cli bgsave
   docker run --rm -v vox-self-hosted_redis-data:/data:ro -v $(pwd)/backups:/backup alpine tar -czf /backup/redis-v7-backup.tar.gz -C /data .
   ```
2. **Update `compose.self-hosted.yml` to Redis 8.2 LTS**:
   Ensure `image: redis:8.2-alpine` is configured.
3. **Recreate the Redis container**:
   ```bash
   docker compose -f compose.self-hosted.yml up -d --no-deps redis
   ```
4. **Verify Redis health**:
   ```bash
   docker compose -f compose.self-hosted.yml exec -T redis redis-cli ping
   ```

### Rollback (NFR-REL-004)
If a rollout fails:
1. Re-deploy the previously verified commit SHAs recorded in `manifest.json`.
2. Existing PostgreSQL durable task states and Redis data are preserved.
3. For a PG18 cutover failure before any PG18 writes, restore the old Compose revision, which still mounts the preserved `postgres-data` volume at `/var/lib/postgresql/data`. Do not attach the PG18 volume to PG17 or claim that writes made after cutover are present on PG17.
4. For Redis rollbacks, restore the volume from `redis-v7-backup.tar.gz` before starting `redis:7-alpine`, ensuring older engine versions do not encounter v8 RDB/AOF formats.
