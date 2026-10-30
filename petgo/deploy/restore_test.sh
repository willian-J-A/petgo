#!/usr/bin/env bash
# deploy/restore_test.sh
# Restauração de backup em banco isolado — deve ser executada antes do aceite (R10).
# Uso: bash restore_test.sh s3://petgo-backups/mysql/daily/petgo_20261029_020000.sql.gz
#
set -euo pipefail

BACKUP_S3="${1:-}"
RESTORE_DB="petgo_restore_test"

if [[ -z "$BACKUP_S3" ]]; then
  echo "Uso: $0 s3://bucket/path/backup.sql.gz" >&2
  exit 1
fi

echo "==> Baixando backup: ${BACKUP_S3}"
TMP_FILE="/tmp/restore_$(date +%s).sql.gz"
aws s3 cp "${BACKUP_S3}" "${TMP_FILE}" --sse aws:kms

echo "==> Criando banco de restauração: ${RESTORE_DB}"
mysql -u root -p -e "DROP DATABASE IF EXISTS ${RESTORE_DB}; CREATE DATABASE ${RESTORE_DB} CHARACTER SET utf8mb4;"

echo "==> Restaurando"
zcat "${TMP_FILE}" | mysql -u root -p "${RESTORE_DB}"

echo "==> Verificando integridade básica"
TABLE_COUNT=$(mysql -u root -p -N -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='${RESTORE_DB}';")
echo "  Tabelas encontradas: ${TABLE_COUNT}"

WALLET_COUNT=$(mysql -u root -p -N -e "SELECT COUNT(*) FROM ${RESTORE_DB}.wallets;")
ENTRY_COUNT=$(mysql -u root -p -N -e "SELECT COUNT(*) FROM ${RESTORE_DB}.point_entries;")
echo "  Carteiras: ${WALLET_COUNT}  Lançamentos: ${ENTRY_COUNT}"

# Reconciliação de saldos
echo "==> Reconciliando saldos vs extrato"
mysql -u root -p "${RESTORE_DB}" <<'SQL'
SELECT
    w.id AS wallet_id,
    w.balance AS stored_balance,
    COALESCE(SUM(e.amount), 0) AS computed_balance,
    w.balance - COALESCE(SUM(e.amount), 0) AS diff
FROM wallets w
LEFT JOIN point_entries e ON e.wallet_id = w.id
GROUP BY w.id
HAVING diff != 0;
SQL

echo "==> Limpando banco de restauração"
mysql -u root -p -e "DROP DATABASE IF EXISTS ${RESTORE_DB};"
rm -f "${TMP_FILE}"

echo "==> Restauração testada com sucesso. RTO deve ser medido pelo tempo total deste script."
