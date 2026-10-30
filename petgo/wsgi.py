"""Ponto de entrada WSGI para Gunicorn.

Uso em produção:
    gunicorn -w 4 -b unix:/run/petgo/gunicorn.sock wsgi:app

Não usar 'flask run' como servidor público (R10).
"""
from __future__ import annotations

import os

from dotenv import load_dotenv

# Carrega .env antes de criar a app (não sobrescreve variáveis já definidas)
load_dotenv(override=False)

from app import create_app  # noqa: E402

app = create_app(os.getenv("APP_ENV", "development"))

if __name__ == "__main__":
    # Apenas para desenvolvimento local — nunca em produção
    app.run(debug=app.debug, host="127.0.0.1", port=5000)
