"""Seed de demonstração para o hackathon PetGo MVP.

REGRAS DE SEGURANÇA:
  - Só roda em APP_ENV != 'production', OU quando --force-demo for passado.
  - Nunca dispara e-mails reais (SMTP_HOST vazio em testes).
  - Não promete patrocínio real; parceiro é claramente fictício.
  - Não republica seed se já existir (idempotente por e-mail/CNPJ).

Uso:
    cd /opt/petgo && source venv/bin/activate
    python deploy/seed_demo.py           # development/testing
    python deploy/seed_demo.py --force-demo  # demo em produção (hackathon)

Fluxo demonstrável após seed:
  1. Login como admin  → painel admin → aprovar ONG e parceiro
  2. Login como ONG    → assumir resgate do pet em risco → submeter evidência
  3. Login como admin  → confirmar resgate + aprovar risco → 25/40 pts
  4. Login como pessoa → solicitar adoção → confirmar entrega/recebimento
  5. Login como usuário → trocar benefício → parceiro usa voucher
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

# Garante que o script funciona a partir da raiz do projeto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FORCE_DEMO = "--force-demo" in sys.argv
APP_ENV = os.getenv("APP_ENV", "development")

if APP_ENV == "production" and not FORCE_DEMO:
    print(
        "AVISO: seed não roda em produção sem --force-demo. "
        "Use apenas para demonstração do hackathon.",
        file=sys.stderr,
    )
    sys.exit(1)

from dotenv import load_dotenv
load_dotenv(override=False)

# Desabilita SMTP no seed para não disparar e-mails reais
os.environ["SMTP_HOST"] = ""

from app import create_app, db
from app.auth.models import User, AuthToken
from app.organizations.models import Ngo, NgoMember
from app.pets.models import Pet, PetEvent
from app.rescues.models import Rescue
from app.adoptions.models import AdoptionRequest
from app.gamification.models import Wallet, PointAward, PointEntry
from app.gamification.service import (
    credit_publication, settle_outcome, get_or_create_wallet
)
from app.rewards.models import Partner, PartnerMember, Reward
from app.notifications.models import OutboxEvent


def _get_or_create_user(session, email, name, city="São Paulo", state="SP",
                         is_admin=False, password="Demo@2026!") -> User:
    u = session.query(User).filter_by(email_normalized=email).first()
    if u:
        print(f"  [skip] Usuário já existe: {email}")
        return u
    u = User(
        name=name,
        email_normalized=email,
        city=city, state=state,
        is_admin=is_admin,
        email_verified_at=datetime.now(timezone.utc),
        email_opt_in=True,
        interested_in_adoption=True,
    )
    u.set_password(password)
    session.add(u)
    session.flush()
    print(f"  [ok] Usuário criado: {email} (id={u.id})")
    return u


def _get_or_create_ngo(session, cnpj, name, contact_email, user_id) -> Ngo:
    ngo = session.query(Ngo).filter_by(cnpj_normalized=cnpj).first()
    if ngo:
        print(f"  [skip] ONG já existe: {name}")
        return ngo
    ngo = Ngo(
        name=name,
        cnpj_normalized=cnpj,
        contact_email=contact_email,
        city="São Paulo", state="SP",
        verification_status="APPROVED",
        verified_at=datetime.now(timezone.utc),
    )
    session.add(ngo)
    session.flush()

    existing_member = session.query(NgoMember).filter_by(
        ngo_id=ngo.id, user_id=user_id
    ).first()
    if not existing_member:
        session.add(NgoMember(ngo_id=ngo.id, user_id=user_id, active=True, role="ADMIN"))

    print(f"  [ok] ONG criada: {name} (id={ngo.id})")
    return ngo


def _credit_wallet(session, user_id, amount, reason):
    w = get_or_create_wallet(user_id=user_id)
    key = f"seed:wallet:{w.id}:{reason.replace(' ', '_')[:40]}"
    existing = session.query(PointEntry).filter_by(entry_key=key).first()
    if existing:
        return
    entry = PointEntry(
        wallet_id=w.id,
        amount=amount,
        kind="CORRECTION",
        reason=reason,
        entry_key=key,
    )
    session.add(entry)
    w.balance += amount


def run_seed() -> None:
    app = create_app(APP_ENV)

    with app.app_context():
        print("\n=== PetGo Demo Seed ===\n")

        # ------------------------------------------------------------------ #
        # 1. Usuários                                                          #
        # ------------------------------------------------------------------ #
        print("-- Usuários --")
        admin = _get_or_create_user(
            db.session, "admin@petgo.demo", "Admin PetGo",
            is_admin=True
        )
        ong_rep = _get_or_create_user(
            db.session, "ong@petgo.demo", "Maria ONG",
        )
        adotante = _get_or_create_user(
            db.session, "adotante@petgo.demo", "Carlos Adotante",
        )
        publicador = _get_or_create_user(
            db.session, "publicador@petgo.demo", "João Publicador",
        )
        parceiro_rep = _get_or_create_user(
            db.session, "parceiro@petgo.demo", "Ana Parceira",
        )
        db.session.flush()

        # ------------------------------------------------------------------ #
        # 2. ONG aprovada                                                      #
        # ------------------------------------------------------------------ #
        print("\n-- ONG --")
        ngo = _get_or_create_ngo(
            db.session,
            cnpj="11222333000181",
            name="ONG Patinhas Felizes (Demo)",
            contact_email="ong@petgo.demo",
            user_id=ong_rep.id,
        )

        # ------------------------------------------------------------------ #
        # 3. Parceiro e benefícios                                             #
        # ------------------------------------------------------------------ #
        print("\n-- Parceiro --")
        existing_partner = db.session.query(Partner).filter_by(
            contact_email="parceiro@petgo.demo"
        ).first()
        if existing_partner:
            partner = existing_partner
            print(f"  [skip] Parceiro já existe: {partner.name}")
        else:
            partner = Partner(
                name="PetShop Demo (fictício — sem patrocínio real)",
                contact_email="parceiro@petgo.demo",
                status="ACTIVE",
                terms="Desconto demonstrativo válido somente durante o hackathon. Sem valor real.",
            )
            db.session.add(partner)
            db.session.flush()

            pm = db.session.query(PartnerMember).filter_by(
                partner_id=partner.id, user_id=parceiro_rep.id
            ).first()
            if not pm:
                db.session.add(PartnerMember(
                    partner_id=partner.id, user_id=parceiro_rep.id, active=True
                ))

            print(f"  [ok] Parceiro criado: {partner.name} (id={partner.id})")

        # Benefícios
        if db.session.query(Reward).filter_by(partner_id=partner.id).count() == 0:
            r1 = Reward(
                partner_id=partner.id,
                name="Ração Premium 1kg",
                description="Troque pontos por um saco de ração premium. Retirada na loja física fictícia.",
                cost_points=15,
                stock=50,
                eligibility="BOTH",
                fulfillment_terms="Retirada em até 30 dias mediante apresentação do voucher.",
                voucher_lifetime_days=30,
                active=True,
            )
            r2 = Reward(
                partner_id=partner.id,
                name="Consulta veterinária gratuita",
                description="Voucher para uma consulta de rotina. Parceiro fictício para demonstração.",
                cost_points=40,
                stock=10,
                eligibility="PERSON",
                fulfillment_terms="Agendar pelo telefone apresentando o código do voucher.",
                voucher_lifetime_days=60,
                active=True,
            )
            db.session.add_all([r1, r2])
            db.session.flush()
            print(f"  [ok] Benefícios criados: '{r1.name}', '{r2.name}'")
        else:
            print("  [skip] Benefícios já existem")

        # ------------------------------------------------------------------ #
        # 4. Pet em situação de risco (fluxo completo)                        #
        # ------------------------------------------------------------------ #
        print("\n-- Pet em risco --")
        existing_pet = db.session.query(Pet).filter_by(
            publisher_user_id=publicador.id,
            description="Cão encontrado próximo à Av. Paulista, circulando entre veículos. Precisa de resgate urgente. (Demo)"
        ).first()

        if existing_pet:
            pet_risco = existing_pet
            print(f"  [skip] Pet em risco já existe (id={pet_risco.id})")
        else:
            pet_risco = Pet(
                publisher_user_id=publicador.id,
                responsible_user_id=publicador.id,
                species="DOG",
                size="MEDIUM",
                help_type="RESCUE",
                status="NEEDS_RESCUE",
                description="Cão encontrado próximo à Av. Paulista, circulando entre veículos. Precisa de resgate urgente. (Demo)",
                city="São Paulo",
                state="SP",
                private_location={"latitude": -23.5613, "longitude": -46.6565},
                risk_status="PENDING",
                risk_details="Animal entre veículos em avenida de alto fluxo, risco de atropelamento iminente.",
            )
            db.session.add(pet_risco)
            db.session.flush()

            ev_pub = PetEvent(
                pet_id=pet_risco.id,
                event_type="PUBLICATION",
                actor_user_id=publicador.id,
                to_status="NEEDS_RESCUE",
            )
            db.session.add(ev_pub)
            db.session.flush()

            # +5 pontos ao publicador
            credit_publication(pet_risco, ev_pub, publicador.id)
            print(f"  [ok] Pet em risco criado (id={pet_risco.id}) — publicador +5 pts")

        # ------------------------------------------------------------------ #
        # 5. Pet normal sem ONG (adoção direta — variante)                    #
        # ------------------------------------------------------------------ #
        print("\n-- Pet normal (adoção direta) --")
        existing_normal = db.session.query(Pet).filter_by(
            publisher_user_id=publicador.id,
            status="AVAILABLE",
        ).first()

        if existing_normal:
            pet_normal = existing_normal
            print(f"  [skip] Pet normal já existe (id={pet_normal.id})")
        else:
            pet_normal = Pet(
                publisher_user_id=publicador.id,
                responsible_user_id=publicador.id,
                species="CAT",
                size="SMALL",
                sex="F",
                age_months=6,
                help_type="ADOPTION",
                status="AVAILABLE",
                description="Gatinha jovem, vacinada, castrada, muito dócil. Precisa de lar. (Demo)",
                city="São Paulo",
                state="SP",
                risk_status="NONE",
            )
            db.session.add(pet_normal)
            db.session.flush()

            ev_pub2 = PetEvent(
                pet_id=pet_normal.id,
                event_type="PUBLICATION",
                actor_user_id=publicador.id,
                to_status="AVAILABLE",
            )
            db.session.add(ev_pub2)
            db.session.flush()
            credit_publication(pet_normal, ev_pub2, publicador.id)
            print(f"  [ok] Pet normal criado (id={pet_normal.id}) — publicador +5 pts")

        # ------------------------------------------------------------------ #
        # 6. Crédito extra para demonstração de troca                         #
        # ------------------------------------------------------------------ #
        print("\n-- Créditos demonstrativos --")
        _credit_wallet(db.session, publicador.id, 50,
                       "Crédito extra demonstrativo para troca de benefício")
        _credit_wallet(db.session, adotante.id, 30,
                       "Crédito extra demonstrativo para adotante")
        print("  [ok] Créditos demonstrativos adicionados")

        # ------------------------------------------------------------------ #
        # 7. Commit final                                                      #
        # ------------------------------------------------------------------ #
        db.session.commit()

        # ------------------------------------------------------------------ #
        # Resumo                                                               #
        # ------------------------------------------------------------------ #
        print("\n=== Seed concluído ===")
        print(f"""
Credenciais de demonstração (senha padrão: Demo@2026!)
  Admin:      admin@petgo.demo
  ONG Rep:    ong@petgo.demo       (ONG Patinhas Felizes — APPROVED)
  Publicador: publicador@petgo.demo
  Adotante:   adotante@petgo.demo
  Parceiro:   parceiro@petgo.demo

Fluxo para demonstrar:
  1. Login admin → /admin → confirmar ONG (já aprovada) e parceiro (já ativo)
  2. Login ong@petgo.demo → POST /api/v1/pets/{pet_risco.id}/rescues
  3. Login ong rep → POST /api/v1/rescues/<id>/submit (evidence_media_id obrigatório)
  4. Login admin → POST /api/v1/rescues/<id>/confirm
  5. Login admin → POST /api/v1/admin/pets/{pet_risco.id}/risk-decision {{decision: APPROVED}}
     → publicador deve ter 25 pts total, ONG 40 pts
  6. Login adotante → solicitar adoção do pet normal → confirmar entrega/recebimento
     → publicador +10 pts (total 70 no demo)
  7. Login publicador → GET /api/v1/me/wallet → ver extrato
  8. Login publicador → trocar benefício → ver voucher
  9. Login parceiro → POST /api/v1/vouchers/consume → confirmar uso único

AVISO: parceiro é fictício. Não anunciar patrocínio real.
""")


if __name__ == "__main__":
    run_seed()
