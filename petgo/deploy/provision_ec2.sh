#!/usr/bin/env bash
# deploy/provision_ec2.sh
# Provisionamento inicial da instância EC2 Amazon Linux 2023 / Ubuntu 22.04.
# Executar UMA vez como root após lançar a instância.
# Pré-requisito: instância criada com IAM role que tem acesso a S3 (sem chave estática).
#
# Uso:
#   sudo bash provision_ec2.sh
#
set -euo pipefail

APP_USER="petgo"
APP_DIR="/opt/petgo"
PYTHON_VERSION="3.12"

echo "==> Atualizando pacotes"
if command -v apt-get &>/dev/null; then
    apt-get update -q
    apt-get install -y python${PYTHON_VERSION} python${PYTHON_VERSION}-venv \
        nginx mysql-server certbot python3-certbot-nginx \
        awscli git curl unzip
else
    dnf update -y
    dnf install -y python${PYTHON_VERSION} nginx mysql-server certbot \
        python3-certbot-nginx awscli git curl
fi

echo "==> Criando usuário de serviço sem shell"
id -u ${APP_USER} &>/dev/null || useradd --system --no-create-home --shell /usr/sbin/nologin ${APP_USER}

echo "==> Diretório da aplicação"
mkdir -p ${APP_DIR}
chown ${APP_USER}:${APP_USER} ${APP_DIR}

echo "==> Diretório do socket Gunicorn"
mkdir -p /run/petgo
chown ${APP_USER}:${APP_USER} /run/petgo

echo "==> MySQL: aceitar somente conexões locais (padrão já correto)"
# Verificar /etc/mysql/mysql.conf.d/mysqld.cnf: bind-address = 127.0.0.1

echo "==> Criando banco e usuário MySQL"
# Execute manualmente com senha segura:
# mysql -u root -p <<'SQL'
# CREATE DATABASE IF NOT EXISTS petgo CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
# CREATE USER IF NOT EXISTS 'petgo'@'127.0.0.1' IDENTIFIED BY 'TROQUE_ESTA_SENHA';
# GRANT SELECT,INSERT,UPDATE,DELETE,CREATE,ALTER,INDEX,DROP,REFERENCES ON petgo.* TO 'petgo'@'127.0.0.1';
# FLUSH PRIVILEGES;
# SQL

echo "==> Configuração concluída. Próximo passo: deploy/deploy_app.sh"
