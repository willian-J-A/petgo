"""Seed de demonstracao (deploy AWS / SQLite) com os dados do mockup.

Cria usuarios (incluindo Joao), ONGs parceiras, pets em destaque
(Luna, Simba, Thor, Nina), ocorrencias/resgates recentes, carteiras e
acoes recentes para a tela inicial parecer o mockup.

Idempotente: nao duplica se ja existir (checa por e-mail / cnpj / descricao).

Uso:
    .\\venv_aws\\Scripts\\python.exe seed_aws.py
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

load_dotenv(".env.aws", override=True)
os.environ["SMTP_HOST"] = ""  # nunca dispara e-mail no seed

import sqlite_compat  # noqa: E402,F401  (registra BigInteger->INTEGER no SQLite)
from app import create_app, db  # noqa: E402
from app.auth.models import User  # noqa: E402
from app.organizations.models import Ngo, NgoMember  # noqa: E402
from app.pets.models import Pet, PetEvent  # noqa: E402
from app.rescues.models import Rescue  # noqa: E402
from app.gamification.models import Wallet, PointEntry  # noqa: E402

app = create_app(os.getenv("APP_ENV", "production"))

NOW = datetime.now(timezone.utc)


def ago(**kw) -> datetime:
    return NOW - timedelta(**kw)


def get_user(email, name, city="Ribeirão Preto", state="SP",
             is_admin=False, password="Demo@2026!") -> User:
    u = db.session.query(User).filter_by(email_normalized=email).first()
    if u:
        return u
    u = User(
        name=name, email_normalized=email, city=city, state=state,
        is_admin=is_admin, email_verified_at=NOW, email_opt_in=True,
        interested_in_adoption=True,
    )
    u.set_password(password)
    db.session.add(u)
    db.session.flush()
    return u


def get_ngo(cnpj, name, city="Ribeirão Preto", state="SP",
            status="APPROVED") -> Ngo:
    n = db.session.query(Ngo).filter_by(cnpj_normalized=cnpj).first()
    if n:
        return n
    n = Ngo(
        name=name, cnpj_normalized=cnpj,
        contact_email=f"contato@{cnpj}.demo",
        city=city, state=state,
        verification_status=status, verified_at=NOW,
    )
    db.session.add(n)
    db.session.flush()
    return n


def get_wallet(user_id=None, ngo_id=None, balance=0) -> Wallet:
    q = db.session.query(Wallet)
    w = (q.filter_by(user_id=user_id).first() if user_id
         else q.filter_by(ngo_id=ngo_id).first())
    if w:
        return w
    w = Wallet(user_id=user_id, ngo_id=ngo_id, balance=balance)
    db.session.add(w)
    db.session.flush()
    return w


def make_pet(publisher, *, species, sex, age_months, size, status, help_type,
             description, city, state, tags, name, risk_status="NONE",
             created=None, ngo=None, rescued_at=None) -> Pet:
    existing = db.session.query(Pet).filter_by(description=description).first()
    if existing:
        return existing
    pet = Pet(
        publisher_user_id=publisher.id,
        responsible_user_id=(None if ngo else publisher.id),
        responsible_ngo_id=(ngo.id if ngo else None),
        species=species, sex=sex, age_months=age_months, size=size,
        help_type=help_type, status=status, description=description,
        city=city, state=state, risk_status=risk_status,
        rescued_at=rescued_at,
        private_location={"name": name, "tags": tags},
        created_at=created or NOW,
    )
    db.session.add(pet)
    db.session.flush()
    db.session.add(PetEvent(
        pet_id=pet.id, event_type="PUBLICATION",
        actor_user_id=publisher.id, to_status=status,
        created_at=created or NOW,
    ))
    db.session.flush()
    return pet


def run():
    with app.app_context():
        print("=== Seed AWS (mockup) ===")

        # ---- Usuarios -------------------------------------------------- #
        admin = get_user("admin@petgo.demo", "Admin PetGo", is_admin=True)
        joao = get_user("joao@petgo.demo", "João Silva")
        maria = get_user("maria@petgo.demo", "Maria Souza")
        carlos = get_user("carlos@petgo.demo", "Carlos Lima")

        # ---- ONGs parceiras (iguais ao mockup) ------------------------- #
        patas = get_ngo("11111111000111", "Patas RP")
        amigos = get_ngo("22222222000122", "Amigos de 4 Patas")
        vida = get_ngo("33333333000133", "Instituto Vida Animal")
        esperanca = get_ngo("44444444000144", "Projeto Esperança")
        ngos = [patas, amigos, vida, esperanca]

        for n in ngos:
            m = db.session.query(NgoMember).filter_by(
                ngo_id=n.id, user_id=maria.id).first()
            if not m:
                db.session.add(NgoMember(
                    ngo_id=n.id, user_id=maria.id, active=True, role="ADMIN"))
            get_wallet(ngo_id=n.id, balance=40)

        # ---- Pets em destaque (iguais ao mockup) ----------------------- #
        make_pet(
            joao, name="Luna", species="DOG", sex="F", age_months=12,
            size="MEDIUM", status="AVAILABLE", help_type="ADOPTION",
            description="Luna é uma cadela dócil, vacinação em dia, pronta para adoção.",
            city="Ribeirão Preto", state="SP",
            tags=["Dócil", "Vacinação em dia"], created=ago(days=6),
        )
        make_pet(
            maria, name="Simba", species="CAT", sex="M", age_months=8,
            size="SMALL", status="AVAILABLE", help_type="ADOPTION",
            description="Simba é um gato brincalhão, precisa de castração, muito sociável.",
            city="Ribeirão Preto", state="SP",
            tags=["Brincalhão", "Castração"], created=ago(days=5),
        )
        make_pet(
            carlos, name="Thor", species="DOG", sex="M", age_months=24,
            size="LARGE", status="AVAILABLE", help_type="ADOPTION",
            description="Thor é um cão calmo, vacinação em dia, ótimo com crianças.",
            city="Ribeirão Preto", state="SP",
            tags=["Calmo", "Vacinação em dia"], created=ago(days=4),
        )
        make_pet(
            joao, name="Nina", species="CAT", sex="F", age_months=12,
            size="SMALL", status="AVAILABLE", help_type="ADOPTION",
            description="Nina é uma gata dócil e independente, ideal para apartamento.",
            city="Ribeirão Preto", state="SP",
            tags=["Dócil", "Independente"], created=ago(days=3),
        )

        # ---- Ocorrencias proximas (resgates) --------------------------- #
        occ1 = make_pet(
            joao, name="Rex", species="DOG", sex="M", age_months=None,
            size="MEDIUM", status="NEEDS_RESCUE", help_type="RESCUE",
            description="Cachorro em situação de rua na Vila Seixas, precisa de resgate.",
            city="Ribeirão Preto", state="SP",
            tags=["Vila Seixas", "1.2 km"], risk_status="PENDING",
            created=ago(hours=2),
        )
        occ2 = make_pet(
            maria, name="Miau", species="CAT", sex=None, age_months=None,
            size="SMALL", status="NEEDS_RESCUE", help_type="RESCUE",
            description="Gato ferido no Jardim Paulista, necessita atendimento veterinário.",
            city="Ribeirão Preto", state="SP",
            tags=["Jardim Paulista", "3.6 km"], risk_status="PENDING",
            created=ago(hours=5),
        )
        occ3 = make_pet(
            carlos, name="Ninhada", species="DOG", sex=None, age_months=1,
            size="SMALL", status="NEEDS_RESCUE", help_type="RESCUE",
            description="Ninhada abandonada em Ribeirão Preto, filhotes precisam de acolhimento.",
            city="Ribeirão Preto", state="SP",
            tags=["Ribeirão Preto", "4.1 km"], risk_status="NONE",
            created=ago(days=1),
        )

        # Resgate ja confirmado (para estatistica "resgates este mês")
        rescued = make_pet(
            maria, name="Belinha", species="DOG", sex="F", age_months=18,
            size="MEDIUM", status="SHELTERED", help_type="RESCUE",
            description="Belinha foi resgatada e está abrigada na Patas RP, aguardando adoção.",
            city="Ribeirão Preto", state="SP", ngo=patas,
            tags=["Resgatada"], created=ago(days=10), rescued_at=ago(days=9),
        )
        if not db.session.query(Rescue).filter_by(pet_id=rescued.id).first():
            db.session.add(Rescue(
                pet_id=rescued.id, ngo_id=patas.id, executor_user_id=maria.id,
                status="CONFIRMED", confirmed_by=admin.id, confirmed_at=ago(days=9),
            ))

        # ---- Carteira do Joao + acoes recentes ------------------------- #
        wj = get_wallet(user_id=joao.id, balance=70)
        key = f"seed:joao:{wj.id}"
        if not db.session.query(PointEntry).filter_by(entry_key=key).first():
            db.session.add(PointEntry(
                wallet_id=wj.id, amount=70, kind="CORRECTION",
                reason="Créditos de demonstração", entry_key=key,
            ))
        get_wallet(user_id=maria.id, balance=25)
        get_wallet(user_id=carlos.id, balance=15)

        db.session.commit()

        total = db.session.query(Pet).count()
        print(f"  pets={total} ngos={len(ngos)}")
        print("""
Credenciais (senha: Demo@2026!)
  Admin:   admin@petgo.demo
  Usuário: joao@petgo.demo   (tela inicial "Olá, João!")
  ONG rep: maria@petgo.demo
""")
        print("=== Seed concluído ===")


if __name__ == "__main__":
    run()
