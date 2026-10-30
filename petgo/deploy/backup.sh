#!/usr/bin/env bash
# deploy/backup.sh
# Backup lógico diário MySQL → S3 privado com criptografia (R10).
# Instalar como cron: 0 2 * * * /opt/petgo/deploy/backup.sh >> /var/log/petgo/backup.log 2>&1
#
# Retenção proposta: 7 diários + 4 semanais.
# RPO ~24h, RTO alvo ~4h (a ser medido na restauração de teste).
#
set -euo pipefail

source /etc/petgo/petgo.env

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DAY_OF_WEEK=$(date +%u)  # 1=seg…7=dom
BACKUP_FILE="/tmp/petgo_${TIMESTAMP}.sql.gz"
MEDIA_ARCHIVE="/tmp/petgo_media_${TIMESTAMP}.tar.gz"

echo "[${TIMESTAMP}] Iniciando backup"

# 1. Dump MySQL
mysqldump \
    --host=127.0.0.1 \
    --user=petgo \
    --password="${MYSQL_PASSWORD}" \
    --single-transaction \
    --quick \
    --routines \
    --triggers \
    petgo | gzip > "${BACKUP_FILE}"

echo "  MySQL dump: ${BACKUP_FILE}"

# 2. IAM role fornece credenciais — sem chave estática (R10)
S3_PREFIX="s3://${BACKUP_BUCKET}"

# Diário
aws s3 cp "${BACKUP_FILE}" \
    "${S3_PREFIX}/mysql/daily/petgo_${TIMESTAMP}.sql.gz" \
    --sse aws:kms

# Semanal (domingo)
if [[ "$DAY_OF_WEEK" == "7" ]]; then
    aws s3 cp "${BACKUP_FILE}" \
        "${S3_PREFIX}/mysql/weekly/petgo_${TIMESTAMP}.sql.gz" \
        --sse aws:kms
    echo "  Backup semanal enviado."
fi

# 3. Mídia S3 → já replicada; registra inventário
echo "  Mídia gerenciada no bucket S3: ${MEDIA_BUCKET}"

# 4. Limpeza de arquivos temporários
rm -f "${BACKUP_FILE}" "${MEDIA_ARCHIVE}"

echo "[${TIMESTAMP}] Backup concluído."
