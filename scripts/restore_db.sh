#!/bin/bash
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-./backups}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-postgres}"
DB_NAME="${DB_NAME:-fastapi_db}"

if [ -z "${1:-}" ]; then
    BACKUP_FILE=$(ls -t "$BACKUP_DIR"/fastapi_db_*.sql.gz 2>/dev/null | head -1)
    if [ -z "$BACKUP_FILE" ]; then
        echo "No backup file found in $BACKUP_DIR"
        echo "Usage: $0 <backup_file.sql.gz>"
        exit 1
    fi
    echo "Using latest backup: $BACKUP_FILE"
else
    BACKUP_FILE="$1"
    if [ ! -f "$BACKUP_FILE" ]; then
        echo "Backup file not found: $BACKUP_FILE"
        exit 1
    fi
fi

echo "Restoring $DB_NAME from $BACKUP_FILE ..."
echo "WARNING: This will overwrite the current database!"
read -p "Continue? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
fi

gunzip -c "$BACKUP_FILE" | PGPASSWORD="${DB_PASSWORD:-postgres}" psql \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d "$DB_NAME"

echo "Restore complete from: $BACKUP_FILE"
