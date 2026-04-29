#!/usr/bin/env bash
# Script de backup diario AnCo (Fase 7).
#
# Roda dentro do container web:
#   docker compose -f infra/docker-compose.yml exec web bash /app/infra/backup/run.sh
#
# Em prod, agendar via cron do host (a cada dia as 03:00):
#   0 3 * * * cd /srv/anco && docker compose exec -T web bash /app/infra/backup/run.sh >> /var/log/anco-backup.log 2>&1

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/var/backups/anco}"

echo "=== AnCo backup $(date -u +%FT%TZ) ==="

# 1. Cria dump local
python manage.py backup_db --output "$BACKUP_DIR"

# 2. Sincronia com S3 (opcional, pula se variaveis nao configuradas)
if [ -n "${BACKUP_S3_BUCKET:-}" ] && command -v aws >/dev/null 2>&1; then
    echo "Sincronizando com s3://$BACKUP_S3_BUCKET ..."
    aws s3 sync "$BACKUP_DIR" "s3://$BACKUP_S3_BUCKET/backups/" \
        --endpoint-url "${BACKUP_S3_ENDPOINT:-https://s3.amazonaws.com}" \
        --exclude "*" --include "anco-*.dump" \
        --no-progress
    echo "Sincronia OK."
else
    echo "BACKUP_S3_BUCKET nao definido ou awscli nao instalado — pulando sincronia remota."
fi

echo "=== Backup concluido ==="
