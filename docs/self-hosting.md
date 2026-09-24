# Vox Platform V1 — Self-Hosted Reference Stack Guide

This document describes the clean installation, operation, verification, and disaster recovery of the Vox Platform V1 open self-hostable reference stack, satisfying the acceptance criteria for [`vox-deploy#1`](https://github.com/vox-suite/vox-deploy/issues/1) (**E47**).

---

## 1. Architectural Overview

The self-hosted reference stack packages the full platform without any proprietary Vox-hosted dependencies:

```
                          ┌───────────────────────────┐
                          │   Caddy (TLS & Ingress)   │
                          └─────────────┬─────────────┘
                                        │
           ┌────────────────────────────┼───────────────────────────┐
           │ :3002                      │ :3001                     │ :3000
           ▼                            ▼                           ▼
    ┌───────────────┐           ┌───────────────┐           ┌───────────────┐
    │    vox-web    │           │   core-api    │◄──────────│  vox-bridge   │
    │  (Web Host)   │           │ (Coordinator) │           │ (Twilio/WA)   │
    └───────────────┘           └───────┬───────┘           └───────────────┘
                                        │
                      ┌─────────────────┴─────────────────┐
                      │                                   │
                      ▼                                   ▼
             ┌─────────────────┐                 ┌─────────────────┐
             │   core-worker   │                 │ portable-agent  │
             │ (Async Tasks)   │                 │ (Agent Package) │
             └────────┬────────┘                 └─────────────────┘
                      │
        ┌─────────────┴─────────────┐
        ▼                           ▼
 ┌──────────────┐            ┌──────────────┐
 │ PostgreSQL 17│            │   Redis 7    │
 │ (State Store)│            │(Queues/Cache)│
 └──────────────┘            └──────────────┘
```

### Components
1. **`postgres` (PostgreSQL 17)**: Durable persistence for tasks, conversations, connections, grants, audit events, and user preferences.
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

## 5. Upgrade and Rollback

### Supported Upgrade
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

### Rollback
If a rollout fails:
1. Re-deploy the previously verified commit SHAs recorded in `manifest.json`.
2. Existing PostgreSQL durable task states and Redis data are preserved.
