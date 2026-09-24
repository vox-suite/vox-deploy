#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# Vox Self-Hosted Backup Script
#
# Dumps PostgreSQL durable state and records backup metadata.
# ==============================================================================

BACKUP_DIR="${BACKUP_DIR:-./backups}"
mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date -u +"%Y%m%d_%H%M%SZ")
BACKUP_FILE="${BACKUP_DIR}/vox_backup_${TIMESTAMP}.sql.gz"
METADATA_FILE="${BACKUP_DIR}/vox_backup_${TIMESTAMP}.json"
trap 'rm -f "$BACKUP_FILE" "$METADATA_FILE"' ERR

echo "Creating Vox Platform V1 backup at: ${BACKUP_FILE}"

if ! command -v docker >/dev/null 2>&1; then
    echo "Docker Compose is required for a real backup" >&2
    exit 1
fi

docker compose -f compose.self-hosted.yml exec -T postgres \
    pg_dump -U "${POSTGRES_USER:-vox}" "${POSTGRES_DB:-vox}" | gzip > "$BACKUP_FILE"
gzip -t "$BACKUP_FILE"

cat <<EOF > "$METADATA_FILE"
{
  "timestamp": "${TIMESTAMP}",
  "backup_file": "${BACKUP_FILE}",
  "type": "full-durable-state",
  "databases": ["postgres"]
}
EOF

echo "Backup complete: ${BACKUP_FILE}"
trap - ERR
