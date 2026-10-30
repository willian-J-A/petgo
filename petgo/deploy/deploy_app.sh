#!/usr/bin/env bash
# deploy/deploy_app.sh
# Deploy / atualização da aplicação PetGo na EC2.
# Executar como usuário com sudo. Não executa como root diretamente.
#
# Variáveis obrigatórias (configure antes de rodar):
#   APP_REPO   — URL do repositório git
#   APP_BRANCH — branch a fazer checkout (padrão: main)
#
# Uso:
#   export APP_REPO=https://github.com/org/petgo.git
#   bash deploy/deploy_app.sh
#
set -euo pipefail

APP_USER="petgo"
APP_DIR="/opt/petgo"
APP_REPO="${APP_REPO:-}"
APP_BRANCH="${APP_BRANCH:-main}"
ENV_FILE="/etc/petgo/petgo.env"  # fora do repositório

if [[ -z "$APP_REPO" ]]; then
  echo "ERRO: defina APP_REPO antes de executar." >&2
  exit 1
fi

echo "==> Backup lógico do MySQL antes do deploy"
BACKUP_FILE="/tmp/petgo_backup_$(date +%Y%m%d_%H%M%S).sql.gz"
mysqldump -u petgo -p"$(grep DB_PASS ${ENV_FILE} | cut -d= -f2)" petgo \
    --single-transaction --quick | gzip > "${BACKUP_FILE}"
echo "    Backup: ${BACKUP_FILE}"
# Envia para S3 privado — IAM role fornece credenciais (sem chave estática)
BACKUP_BUCKET=$(grep BACKUP_BUCKET ${ENV_FILE} | cut -d= -f2)
aws s3 cp "${BACKUP_FILE}" "s3://${BACKUP_BUCKET}/mysql/${BACKUP_FILE##*/}" --sse

echo "==> Atualizando código"
if [[ -d "${APP_DIR}/.git" ]]; then
    sudo -u ${APP_USER} git -C ${APP_DIR} fetch origin
    sudo -u ${APP_USER} git -C ${APP_DIR} checkout ${APP_BRANCH}
    sudo -u ${APP_USER} git -C ${APP_DIR} pull origin ${APP_BRANCH}
else
    sudo -u ${APP_USER} git clone --branch ${APP_BRANCH} ${APP_REPO} ${APP_DIR}
fi

echo "==> Virtualenv e dependências"
sudo -u ${APP_USER} python3 -m venv ${APP_DIR}/venv
sudo -u ${APP_USER} ${APP_DIR}/venv/bin/pip install --quiet --upgrade pip
sudo -u ${APP_USER} ${APP_DIR}/venv/bin/pip install --quiet -r ${APP_DIR}/requirements.txt

echo "==> Carregando variáveis de ambiente"
set -a
source ${ENV_FILE}
set +a

echo "==> Executando migrações (explícito — nunca automático)"
sudo -u ${APP_USER} ${APP_DIR}/venv/bin/flask --app wsgi:app db upgrade

echo "==> Recarregando Gunicorn e worker"
systemctl reload petgo-app || systemctl restart petgo-app
systemctl restart petgo-worker

echo "==> Verificando healthcheck"
sleep 3
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5000/health/ready)
if [[ "$HTTP_STATUS" != "200" ]]; then
  echo "ERRO: healthcheck retornou ${HTTP_STATUS}. Verifique logs: journalctl -u petgo-app -n 50" >&2
  exit 1
fi

echo "==> Deploy concluído com sucesso."
