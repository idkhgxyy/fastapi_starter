#!/bin/bash
set -euo pipefail

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="${BACKUP_DIR:-./backups}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-postgres}"
DB_NAME="${DB_NAME:-fastapi_db}"

mkdir -p "$BACKUP_DIR"

BACKUP_FILE="$BACKUP_DIR/fastapi_db_$TIMESTAMP.sql.gz"

echo "Backing up $DB_NAME to $BACKUP_FILE ..."
PGPASSWORD="${DB_PASSWORD:-postgres}" pg_dump \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    --no-owner \
    --no-acl \
    | gzip > "$BACKUP_FILE"

echo "Backup complete: $BACKUP_FILE ($(du -h "$BACKUP_FILE" | cut -f1))"

ls -lh "$BACKUP_DIR" | tail -5
