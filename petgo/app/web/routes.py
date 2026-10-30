"""Rotas web Jinja2 — Task 11 completa."""
from __future__ import annotations

from flask import Blueprint, abort, redirect, render_template, request, url_for
from flask_login import current_user, login_required

bp = Blueprint("web", __name__)


# --------------------------------------------------------------------------- #
# Públicas                                                                     #
# --------------------------------------------------------------------------- #

@bp.get("/")
def index():
    """Tela inicial estilo dashboard (mockup PetGo)."""
    from datetime import datetime, timezone

    from app import db
    from app.organizations.models import Ngo
    from app.pets.models import Pet
    from app.rescues.models import Rescue

    def _pet_card(p):
        loc = p.private_location or {}
        return {
            "id": p.id,
            "name": loc.get("name", "Animalzinho"),
            "species": p.species,
            "sex": p.sex,
            "age_months": p.age_months,
            "tags": loc.get("tags", []),
        }

    def _humanize(dt):
        if not dt:
            return ""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - dt
        secs = int(delta.total_seconds())
        if secs < 3600:
            return f"há {max(1, secs // 60)} min"
        if secs < 86400:
            return f"há {secs // 3600} horas"
        return f"há {secs // 86400} dia(s)"

    featured = (
        db.session.query(Pet)
        .filter(Pet.status == "AVAILABLE", Pet.deleted_at.is_(None))
        .order_by(Pet.created_at.desc())
        .limit(4)
        .all()
    )
    occurrences = (
        db.session.query(Pet)
        .filter(Pet.status == "NEEDS_RESCUE", Pet.deleted_at.is_(None))
        .order_by(Pet.created_at.desc())
        .limit(3)
        .all()
    )
    partners = (
        db.session.query(Ngo)
        .filter(Ngo.verification_status == "APPROVED")
        .order_by(Ngo.name)
        .limit(4)
        .all()
    )

    stats = {
        "adoption": db.session.query(Pet).filter(
            Pet.status == "AVAILABLE", Pet.deleted_at.is_(None)).count(),
        "rescues_month": db.session.query(Rescue).filter(
            Rescue.status == "CONFIRMED").count()
        or db.session.query(Pet).filter(Pet.status == "SHELTERED").count(),
        "occurrences": db.session.query(Pet).filter(
            Pet.status == "NEEDS_RESCUE", Pet.deleted_at.is_(None)).count(),
        "partners": db.session.query(Ngo).filter(
            Ngo.verification_status == "APPROVED").count(),
    }

    occ_cards = []
    for p in occurrences:
        loc = p.private_location or {}
        tags = loc.get("tags", [])
        occ_cards.append({
            "id": p.id,
            "title": p.description.split(",")[0].split(".")[0],
            "place": tags[0] if tags else p.city,
            "distance": tags[1] if len(tags) > 1 else "",
            "when": _humanize(p.created_at),
            "species": p.species,
        })

    user_name = (
        current_user.name.split()[0]
        if current_user.is_authenticated else "visitante"
    )

    # Acoes recentes (demonstrativas, estilo timeline do mockup)
    actions = [
        {"icon": "❤", "title": "Solicitação de adoção enviada",
         "sub": "Luna", "date": "28 de out"},
        {"icon": "✓", "title": "Ocorrência registrada",
         "sub": "Gato ferido - Jardim Paulista", "date": "27 de out"},
        {"icon": "🐾", "title": "Voluntariado confirmado",
         "sub": "Evento de vacinação", "date": "25 de out"},
    ]

    return render_template(
        "home.html",
        user_name=user_name,
        stats=stats,
        featured=[_pet_card(p) for p in featured],
        occurrences=occ_cards,
        partners=[{"id": n.id, "name": n.name,
                   "place": f"{n.city} - {n.state}"} for n in partners],
        actions=actions,
    )


@bp.get("/resgates")
def rescue_list():
    from app.pets.service import list_rescue_pets
    items, total, page, page_size = list_rescue_pets(request.args.to_dict())
    return render_template("pets/rescue_list.html", items=items, total=total,
                           page=page, page_size=page_size)


@bp.get("/adocoes")
def adoption_list():
    from app.pets.service import list_adoption_pets
    items, total, page, page_size = list_adoption_pets(request.args.to_dict())
    return render_template("pets/adoption_list.html", items=items, total=total,
                           page=page, page_size=page_size)


@bp.get("/pets/<int:pet_id>")
def pet_detail(pet_id: int):
    from app.pets.service import get_pet_or_404, pet_private_dto, pet_public_dto
    pet = get_pet_or_404(pet_id)
    if current_user.is_authenticated and (
        current_user.is_admin
        or current_user.id == pet.responsible_user_id
        or current_user.id == pet.publisher_user_id
    ):
        dto = pet_private_dto(pet)
    else:
        dto = pet_public_dto(pet)
    return render_template("pets/detail.html", pet=dto)


@bp.get("/cadastro")
def register():
    if current_user.is_authenticated:
        return redirect(url_for("web.dashboard"))
    return render_template("auth/register.html")


@bp.get("/entrar")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("web.dashboard"))
    return render_template("auth/login.html")


@bp.get("/termos")
def terms():
    return render_template("terms.html")


@bp.get("/beneficios")
def rewards_list():
    from app import db
    from app.gamification.models import Wallet
    from app.rewards.service import list_rewards
    data = list_rewards()
    wallet = {"balance": 0, "wallet_id": None}
    if current_user.is_authenticated:
        w = db.session.query(Wallet).filter_by(user_id=current_user.id).first()
        if w:
            wallet = {"balance": w.balance, "wallet_id": w.id}
    return render_template("rewards.html", rewards=data["items"], wallet=wallet)


# --------------------------------------------------------------------------- #
# Autenticadas — pessoal                                                       #
# --------------------------------------------------------------------------- #

@bp.get("/minha-conta")
@login_required
def dashboard():
    from app import db
    from app.adoptions.service import list_my_adoptions
    from app.gamification.service import get_user_wallet
    from app.gamification.models import Wallet
    from app.organizations.models import NgoMember
    from app.rewards.models import Redemption

    wallet = get_user_wallet(current_user.id)
    adoptions = list_my_adoptions(current_user)

    # Vouchers pessoais
    w = db.session.query(Wallet).filter_by(user_id=current_user.id).first()
    redemptions = []
    if w:
        redemptions = (
            db.session.query(Redemption)
            .filter_by(wallet_id=w.id)
            .order_by(Redemption.id.desc())
            .limit(5)
            .all()
        )
        redemptions = [{"id": r.id, "status": r.status} for r in redemptions]

    # ONGs vinculadas
    ngo_memberships = (
        db.session.query(NgoMember)
        .filter_by(user_id=current_user.id, active=True)
        .all()
    )

    return render_template(
        "dashboard.html",
        wallet=wallet,
        adoptions=adoptions,
        redemptions=redemptions,
        ngo_memberships=ngo_memberships,
    )


@bp.get("/extrato")
@login_required
def wallet_entries():
    from app import db
    from app.gamification.models import Wallet
    from app.gamification.service import get_wallet_entries

    w = db.session.query(Wallet).filter_by(user_id=current_user.id).first()
    page = request.args.get("page", 1, type=int)
    per_page = 20

    if not w:
        return render_template(
            "wallet/entries.html",
            entries=[], balance=0, page=1, total_pages=1, ngo_name=None
        )

    data = get_wallet_entries(w.id, page, per_page)
    total_pages = max(1, -(-data["total"] // per_page))
    return render_template(
        "wallet/entries.html",
        entries=data["items"],
        balance=w.balance,
        page=page,
        total_pages=total_pages,
        ngo_name=None,
    )


@bp.get("/pets/novo")
@login_required
def new_pet():
    if not current_user.email_verified:
        return redirect(url_for("web.dashboard"))
    return render_template("pets/new_pet.html")


# --------------------------------------------------------------------------- #
# Painel ONG                                                                   #
# --------------------------------------------------------------------------- #

@bp.get("/ong/<int:ngo_id>")
@login_required
def ngo_dashboard(ngo_id: int):
    from app import db
    from app.gamification.models import Wallet
    from app.organizations.models import Ngo, NgoMember
    from app.organizations.service import is_active_member
    from app.rescues.models import Rescue
    from app.rewards.models import Redemption

    if not current_user.is_admin and not is_active_member(current_user.id, ngo_id):
        abort(403)

    ngo = db.session.get(Ngo, ngo_id)
    if not ngo:
        abort(404)

    wallet_data = {"balance": 0, "wallet_id": None}
    w = db.session.query(Wallet).filter_by(ngo_id=ngo_id).first()
    if w:
        wallet_data = {"balance": w.balance, "wallet_id": w.id}

    rescues = (
        db.session.query(Rescue)
        .filter(Rescue.ngo_id == ngo_id,
                Rescue.status.in_(["ASSUMED", "PENDING_CONFIRMATION"]))
        .all()
    )
    rescues_dto = [{"pet_id": r.pet_id, "status": r.status} for r in rescues]

    members = (
        db.session.query(NgoMember)
        .filter_by(ngo_id=ngo_id)
        .all()
    )

    redemptions = []
    if w:
        items = (
            db.session.query(Redemption)
            .filter_by(wallet_id=w.id)
            .order_by(Redemption.id.desc())
            .limit(5)
            .all()
        )
        redemptions = [{"id": r.id, "status": r.status} for r in items]

    ngo_dto = {
        "id": ngo.id,
        "name": ngo.name,
        "city": ngo.city,
        "state": ngo.state,
        "verification_status": ngo.verification_status,
    }

    return render_template(
        "ngo_dashboard.html",
        ngo=ngo_dto,
        wallet=wallet_data,
        rescues=rescues_dto,
        members=members,
        redemptions=redemptions,
    )


@bp.get("/ong/<int:ngo_id>/extrato")
@login_required
def ngo_wallet_entries(ngo_id: int):
    from app import db
    from app.gamification.models import Wallet
    from app.gamification.service import get_wallet_entries
    from app.organizations.models import Ngo
    from app.organizations.service import is_active_member

    if not current_user.is_admin and not is_active_member(current_user.id, ngo_id):
        abort(403)

    ngo = db.session.get(Ngo, ngo_id)
    if not ngo:
        abort(404)

    w = db.session.query(Wallet).filter_by(ngo_id=ngo_id).first()
    page = request.args.get("page", 1, type=int)
    per_page = 20

    if not w:
        return render_template(
            "wallet/entries.html",
            entries=[], balance=0, page=1, total_pages=1, ngo_name=ngo.name
        )

    data = get_wallet_entries(w.id, page, per_page)
    total_pages = max(1, -(-data["total"] // per_page))
    return render_template(
        "wallet/entries.html",
        entries=data["items"],
        balance=w.balance,
        page=page,
        total_pages=total_pages,
        ngo_name=ngo.name,
    )


# --------------------------------------------------------------------------- #
# Painel parceiro                                                              #
# --------------------------------------------------------------------------- #

@bp.get("/parceiro/<int:partner_id>")
@login_required
def partner_dashboard(partner_id: int):
    from app import db
    from app.rewards.models import Partner, PartnerMember, Reward

    p = db.session.get(Partner, partner_id)
    if not p:
        abort(404)

    member = (
        db.session.query(PartnerMember)
        .filter_by(partner_id=partner_id, user_id=current_user.id, active=True)
        .first()
    )
    if not current_user.is_admin and not member:
        abort(403)

    rewards = db.session.query(Reward).filter_by(partner_id=partner_id).all()
    rewards_dto = [
        {"id": r.id, "name": r.name, "cost_points": r.cost_points,
         "stock": r.stock, "active": r.active}
        for r in rewards
    ]

    partner_dto = {
        "id": p.id, "name": p.name,
        "contact_email": p.contact_email, "status": p.status
    }
    return render_template(
        "partner_dashboard.html",
        partner=partner_dto,
        rewards=rewards_dto,
    )


@bp.get("/parceiro/<int:partner_id>/novo-premio")
@login_required
def new_reward(partner_id: int):
    """Redireciona para a API — formulário simples."""
    return render_template("partner_dashboard.html",
                           partner={"id": partner_id, "name": "", "contact_email": "", "status": ""},
                           rewards=[])


@bp.get("/parceiro/voucher")
@login_required
def validate_voucher():
    """Atalho para a seção de validação de voucher no painel parceiro."""
    return redirect(url_for("web.partner_dashboard", partner_id=0))


# --------------------------------------------------------------------------- #
# Painel admin                                                                 #
# --------------------------------------------------------------------------- #

@bp.get("/admin")
@login_required
def admin_panel():
    if not current_user.is_admin:
        abort(403)

    from app import db
    from app.organizations.models import Ngo
    from app.pets.models import Pet
    from app.rewards.models import Partner

    pending_ngos = (
        db.session.query(Ngo)
        .filter_by(verification_status="PENDING")
        .all()
    )
    pending_ngos_dto = [
        {"id": n.id, "name": n.name, "cnpj_normalized": n.cnpj_normalized,
         "city": n.city, "state": n.state}
        for n in pending_ngos
    ]

    risk_pets = (
        db.session.query(Pet)
        .filter_by(risk_status="PENDING")
        .filter(Pet.deleted_at.is_(None))
        .all()
    )
    risk_pets_dto = [
        {"id": p.id, "species": p.species, "city": p.city,
         "state": p.state, "risk_details": p.risk_details}
        for p in risk_pets
    ]

    pending_partners = (
        db.session.query(Partner)
        .filter_by(status="PENDING")
        .all()
    )
    pending_partners_dto = [
        {"id": p.id, "name": p.name, "contact_email": p.contact_email}
        for p in pending_partners
    ]

    return render_template(
        "admin_panel.html",
        pending_ngos=pending_ngos_dto,
        risk_pets=risk_pets_dto,
        pending_partners=pending_partners_dto,
    )
