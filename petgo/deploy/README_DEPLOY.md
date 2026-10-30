# Deploy PetGo MVP — EC2

## Arquitetura (instância única, R10)

```
Internet → Nginx (443/80) → socket Unix → Gunicorn/Flask → MySQL (127.0.0.1)
                                                          → Worker Python (systemd)
                                         → S3 (mídia / backups, via IAM role)
```

## Checklist pré-produção

- [ ] EC2 `t3.small` (2 vCPU / 2 GiB) ou maior, conforme carga medida
- [ ] EBS criptografado (AES-256), montado em `/` ou volume dedicado
- [ ] Security Group: 443 aberto, 80 somente para redirect; **3306 e 5000 fechados externamente**
- [ ] IAM role na instância com `s3:PutObject` / `s3:GetObject` nos buckets `petgo-media-*` e `petgo-backups-*`; sem chave estática
- [ ] Certificado TLS via Let's Encrypt (`certbot --nginx -d seu-dominio.com.br`)
- [ ] MySQL 8.x com `bind-address = 127.0.0.1`
- [ ] Usuário `petgo` MySQL com privilégios mínimos de runtime (não `SUPER`)
- [ ] Arquivo `/etc/petgo/petgo.env` fora do repositório, permissão `600`, owner `petgo`
- [ ] `DEBUG=False`, `APP_ENV=production` no env
- [ ] `SECRET_KEY` gerada com `python -c "import secrets; print(secrets.token_hex(32))"`
- [ ] `VOUCHER_ENCRYPTION_KEY` gerada com `python -c "import secrets,base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"`
- [ ] Rotação de logs: `/etc/logrotate.d/petgo` configurado
- [ ] Cron de backup: `0 2 * * * /opt/petgo/deploy/backup.sh`
- [ ] Restauração testada via `deploy/restore_test.sh` **antes do aceite**

## Ordem de execução no primeiro deploy

```bash
# 1. Provisionar (root)
sudo bash deploy/provision_ec2.sh

# 2. Criar arquivo de segredos (fora do repo)
sudo mkdir -p /etc/petgo
sudo cp .env.example /etc/petgo/petgo.env
sudo nano /etc/petgo/petgo.env   # preencher TODOS os valores
sudo chmod 600 /etc/petgo/petgo.env
sudo chown petgo:petgo /etc/petgo/petgo.env

# 3. Deploy do código
export APP_REPO=https://github.com/org/petgo.git
bash deploy/deploy_app.sh

# 4. Instalar units systemd
sudo cp deploy/petgo-app.service    /etc/systemd/system/
sudo cp deploy/petgo-worker.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable petgo-app petgo-worker
sudo systemctl start  petgo-app petgo-worker

# 5. Nginx
sudo cp deploy/nginx.conf /etc/nginx/sites-available/petgo
sudo ln -sf /etc/nginx/sites-available/petgo /etc/nginx/sites-enabled/petgo
sudo nginx -t
sudo systemctl reload nginx

# 6. Criar administrador
cd /opt/petgo && source venv/bin/activate
APP_ENV=production python deploy/create_admin.py

# 7. Seed de demonstração (hackathon)
APP_ENV=production python deploy/seed_demo.py

# 8. Verificar healthcheck
curl -s https://seu-dominio.com.br/health/ready
```

## Rollback de código (sem migração destrutiva)

```bash
cd /opt/petgo
git checkout TAG_ANTERIOR
source venv/bin/activate
pip install -r requirements.txt
flask --app wsgi:app db downgrade -1   # só se a migração for reversível
systemctl restart petgo-app petgo-worker
```

> ⚠ Rollback de código **não** desfaz migrações destrutivas.
> Sempre usar alterações compatíveis e ter backup antes do deploy.

## Limitações conhecidas (R10)

- Instância única = ponto único de falha; indisponibilidade afeta app e banco.
- Evolução futura: MySQL → RDS Multi-AZ, app → múltiplas instâncias atrás de ALB.
- RPO ~24h e RTO alvo ~4h devem ser medidos, não prometidos sem teste documentado.
