#!/bin/bash
set -euo pipefail

# 服务器备份：在宿主机执行，调用 db 容器内的 pg_dump。
# 不依赖宿主机安装 PostgreSQL 客户端。
# 用法：./scripts/backup_db_docker.sh
# cron：30 3 * * * /home/ubuntu/fastapi_starter/scripts/backup_db_docker.sh >> .../backups/backup.log 2>&1

export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${PATH:-}"

BACKUP_DIR="${BACKUP_DIR:-$HOME/fastapi_starter/backups}"
DB_CONTAINER="${DB_CONTAINER:-fastapi-starter-db}"
DB_USER="${DB_USER:-postgres}"
DB_NAME="${DB_NAME:-fastapi_db}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

umask 077
mkdir -p "$BACKUP_DIR"

if docker ps >/dev/null 2>&1; then
    DOCKER=(docker)
else
    DOCKER=(sudo -n docker)
fi

if ! "${DOCKER[@]}" ps --format '{{.Names}}' | grep -qx "$DB_CONTAINER"; then
    echo "database container not running: $DB_CONTAINER" >&2
    exit 1
fi

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/fastapi_db_${TIMESTAMP}.sql.gz"
TMP_FILE="$BACKUP_DIR/.fastapi_db_${TIMESTAMP}.sql.gz.tmp"
trap 'rm -f "$TMP_FILE"' EXIT

echo "Backing up $DB_NAME from $DB_CONTAINER ..."
"${DOCKER[@]}" exec "$DB_CONTAINER" pg_dump \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    --no-owner \
    --no-acl \
    | gzip -9 > "$TMP_FILE"

gzip -t "$TMP_FILE"
mv "$TMP_FILE" "$BACKUP_FILE"
trap - EXIT

echo "Backup complete: $BACKUP_FILE ($(du -h "$BACKUP_FILE" | cut -f1))"

# 只清理本脚本生成的备份，保留日志和其他文件
find "$BACKUP_DIR" -maxdepth 1 -type f -name 'fastapi_db_*.sql.gz' \
    -mtime +"$RETENTION_DAYS" -print -delete

ls -lh "$BACKUP_DIR" | tail -5
