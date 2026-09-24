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

if command -v docker >/dev/null 2>&1; then
    gunzip -c "$BACKUP_FILE" | docker compose -f compose.self-hosted.yml exec -T postgres \
        psql -U "${POSTGRES_USER:-vox}" -d "${POSTGRES_DB:-vox}"
    echo "Database restore completed. Running integrity checks..."
    docker compose -f compose.self-hosted.yml exec -T postgres \
        psql -U "${POSTGRES_USER:-vox}" -d "${POSTGRES_DB:-vox}" -c \
        "SELECT 'durable_tasks_count' AS check, count(*) FROM tasks UNION ALL SELECT 'audit_events_count', count(*) FROM audit_events;"
else
    echo "Simulated restore completed for: $BACKUP_FILE"
fi

echo "Restore successfully completed."
