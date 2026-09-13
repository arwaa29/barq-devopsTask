 #!/usr/bin/env bash
# set -euo pipefail
# echo 'NOT IMPLEMENTED: write the PostgreSQL backup script.' >&2
# exit 2


set -euo pipefail

PROJECT="barq-assessment"
DB_USER="barq_app"
DB_NAME="barq_tasks"
BACKUP_DIR="./backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/backup_${TIMESTAMP}.dump"

mkdir -p "$BACKUP_DIR"

echo "Backing up PostgreSQL database '${DB_NAME}' to ${BACKUP_FILE}..."

docker compose -p "$PROJECT" exec -T postgres \
    pg_dump -U "$DB_USER" -d "$DB_NAME" -F c > "$BACKUP_FILE"

if [ -s "$BACKUP_FILE" ]; then
    echo "PASS: Backup created successfully: ${BACKUP_FILE} ($(du -h "$BACKUP_FILE" | cut -f1))"
    exit 0
else
    echo "FAIL: Backup file is empty or was not created." >&2
    exit 1
fi
