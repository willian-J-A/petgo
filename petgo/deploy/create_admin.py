"""Script operacional para criar o primeiro administrador.

Uso (executar na EC2, nunca em produção sem senha segura):
    cd /opt/petgo
    source venv/bin/activate
    APP_ENV=production python deploy/create_admin.py

Não versionar senhas. A senha é solicitada interativamente.
"""
from __future__ import annotations

import getpass
import os
import sys

from dotenv import load_dotenv

load_dotenv("/etc/petgo/petgo.env", override=False)

from app import create_app, db
from app.auth.models import User
from datetime import datetime, timezone


def main() -> None:
    app = create_app(os.getenv("APP_ENV", "production"))

    print("=== PetGo — Criação de administrador ===")
    name = input("Nome completo: ").strip()
    email = input("E-mail: ").strip().lower()
    city = input("Cidade: ").strip()
    state = input("UF (2 letras): ").strip().upper()
    password = getpass.getpass("Senha (mín. 8 chars): ")

    if len(password) < 8:
        print("ERRO: senha muito curta.", file=sys.stderr)
        sys.exit(1)

    with app.app_context():
        existing = db.session.query(User).filter_by(email_normalized=email).first()
        if existing:
            print(f"ERRO: E-mail {email} já cadastrado.", file=sys.stderr)
            sys.exit(1)

        admin = User(
            name=name,
            email_normalized=email,
            city=city,
            state=state,
            is_admin=True,
            email_verified_at=datetime.now(timezone.utc),
        )
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        print(f"Administrador criado: id={admin.id} email={admin.email_normalized}")


if __name__ == "__main__":
    main()
