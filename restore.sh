#!/usr/bin/env bash
# set -euo pipefail
# echo 'NOT IMPLEMENTED: write the PostgreSQL restore script and prove recovery.' >&2
# exit 2


set -euo pipefail

PROJECT="barq-assessment"
DB_USER="barq_app"
DB_NAME="barq_tasks"

if [ $# -ne 1 ]; then
    echo "Usage: $0 <path-to-backup-file>" >&2
    exit 2
fi

BACKUP_FILE="$1"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "FAIL: Backup file not found: ${BACKUP_FILE}" >&2
    exit 1
fi

echo "Restoring PostgreSQL database '${DB_NAME}' from ${BACKUP_FILE}..."

docker compose -p "$PROJECT" exec -T postgres \
    pg_restore -U "$DB_USER" -d "$DB_NAME" --clean --if-exists < "$BACKUP_FILE"

echo "Restore command completed. Verifying record count..."
RECORD_COUNT=$(docker compose -p "$PROJECT" exec -T postgres \
    psql -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM records;" | tr -d ' ')

echo "PASS: Restore completed. Records table now has ${RECORD_COUNT} row(s)."
exit 0
