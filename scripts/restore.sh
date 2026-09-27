#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# Vox Self-Hosted Restore Script
#
# Restores PostgreSQL durable state from backup archive.
# ==============================================================================

if [ "$#" -lt 1 ]; then
    echo "Usage: $0 <backup-file.sql.gz>"
    exit 1
fi

BACKUP_FILE="$1"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "Error: Backup file not found: $BACKUP_FILE"
    exit 1
fi

echo "Restoring Vox Platform V1 state from: ${BACKUP_FILE}"

if ! command -v docker >/dev/null 2>&1; then
    echo "Docker Compose is required for a real restore" >&2
    exit 1
fi

gzip -t "$BACKUP_FILE"
if [ "$(docker compose -f compose.self-hosted.yml exec -T postgres \
    psql -At -v ON_ERROR_STOP=1 -U "${POSTGRES_USER:-vox}" -d "${POSTGRES_DB:-vox}" \
    -c "SELECT to_regclass('public.users') IS NOT NULL")" != "f" ]; then
    echo "Restore requires a fresh database; existing Core tables were found" >&2
    exit 1
fi
# pg_dump includes grants and RLS policies but not cluster-wide roles. The
# fresh target must have the non-login roles used by Core before replay.
docker compose -f compose.self-hosted.yml exec -T postgres \
    psql -v ON_ERROR_STOP=1 -U "${POSTGRES_USER:-vox}" -d "${POSTGRES_DB:-vox}" <<'SQL'
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'anon') THEN CREATE ROLE anon NOLOGIN; END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'authenticated') THEN CREATE ROLE authenticated NOLOGIN; END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'service_role') THEN CREATE ROLE service_role NOLOGIN; END IF;
END
$$;
SQL
gunzip -c "$BACKUP_FILE" | docker compose -f compose.self-hosted.yml exec -T postgres \
    psql -v ON_ERROR_STOP=1 -U "${POSTGRES_USER:-vox}" -d "${POSTGRES_DB:-vox}"
echo "Database restore completed. Running integrity checks..."
docker compose -f compose.self-hosted.yml exec -T postgres \
    psql -v ON_ERROR_STOP=1 -U "${POSTGRES_USER:-vox}" -d "${POSTGRES_DB:-vox}" -c \
    "SELECT 'spans_count' AS check, count(*) FROM spans UNION ALL SELECT 'jobs_count', count(*) FROM jobs UNION ALL SELECT 'audit_events_count', count(*) FROM audit_events;"

echo "Restore successfully completed."
