"""Runner de deploy AWS (instância EC2 Windows).

- Carrega variaveis de .env.aws
- Usa SQLite (as migracoes Alembic sao especificas de MySQL; aqui criamos
  o schema direto via SQLAlchemy create_all para o MVP/demo)
- Serve a aplicacao com waitress (WSGI de producao compativel com Windows;
  gunicorn nao roda em Windows) em 0.0.0.0:PORT
"""
from __future__ import annotations

import os

from dotenv import load_dotenv

# Carrega o arquivo de ambiente especifico do deploy AWS
load_dotenv(".env.aws", override=True)

import sqlite_compat  # noqa: E402,F401  (registra BigInteger->INTEGER no SQLite)
from app import create_app, db  # noqa: E402

app = create_app(os.getenv("APP_ENV", "production"))


def init_db() -> None:
    """Cria todas as tabelas no SQLite caso ainda nao existam."""
    with app.app_context():
        # Garante que todos os modelos estao registrados
        from app import models  # noqa: F401
        db.create_all()
        print("DB_INIT_OK")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "initdb":
        init_db()
        raise SystemExit(0)

    # Garante schema antes de servir
    init_db()

    from waitress import serve

    port = int(os.getenv("PORT", "8080"))
    print(f"SERVING on 0.0.0.0:{port}")
    serve(app, host="0.0.0.0", port=port, threads=8)
