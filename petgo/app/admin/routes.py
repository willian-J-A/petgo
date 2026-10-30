"""Rotas administrativas — Task 11."""
from __future__ import annotations

from functools import wraps

from flask import Blueprint, abort, jsonify, request
from flask_login import current_user, login_required

bp = Blueprint("admin", __name__)


def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated


# ---- ONGs ----

@bp.post("/ngos/<int:ngo_id>/decision")
@admin_required
def ngo_decision(ngo_id: int):
    from app.organizations.service import admin_approve_ngo
    data = request.get_json(silent=True) or {}
    ngo = admin_approve_ngo(
        current_user,
        ngo_id,
        decision=data.get("decision", ""),
        reason=data.get("reason"),
    )
    from app.organizations.service import ngo_public_dto
    return jsonify(ngo_public_dto(ngo)), 200


# ---- Risco ----

@bp.post("/pets/<int:pet_id>/risk-decision")
@admin_required
def risk_decision(pet_id: int):
    from app.rescues.service import admin_risk_decision
    data = request.get_json(silent=True) or {}
    dto = admin_risk_decision(
        current_user,
        pet_id,
        decision=data.get("decision", ""),
        reason=data.get("reason", ""),
    )
    return jsonify(dto), 200


# ---- Parceiros ----

@bp.post("/partners")
@admin_required
def create_partner():
    from app import db
    from app.rewards.models import Partner
    from marshmallow import Schema, fields

    class PartnerSchema(Schema):
        name = fields.Str(required=True)
        contact_email = fields.Email(required=True)
        terms = fields.Str(load_default=None)

    data = request.get_json(silent=True) or {}
    clean = PartnerSchema().load(data)
    p = Partner(name=clean["name"], contact_email=clean["contact_email"],
                terms=clean.get("terms"), status="PENDING")
    db.session.add(p)
    db.session.commit()
    return jsonify({"id": p.id, "name": p.name, "status": p.status}), 201


@bp.post("/partners/<int:partner_id>/decision")
@admin_required
def partner_decision(partner_id: int):
    from app import db
    from app.rewards.models import Partner
    data = request.get_json(silent=True) or {}
    decision = data.get("decision", "")
    p = db.session.get(Partner, partner_id)
    if not p:
        abort(404)
    if decision not in ("ACTIVE", "SUSPENDED"):
        abort(422)
    p.status = decision
    db.session.commit()
    return jsonify({"id": p.id, "status": p.status}), 200


# ---- Prêmios ----

@bp.post("/partners/<int:partner_id>/rewards")
@login_required
def create_reward(partner_id: int):
    """Parceiro correspondente ou admin pode criar prêmio."""
    from app import db
    from app.rewards.models import Partner, Reward
    from app.organizations.service import is_active_member
    from marshmallow import Schema, fields as mf, validate

    p = db.session.get(Partner, partner_id)
    if not p:
        abort(404)
    if not current_user.is_admin:
        # Verifica se é membro do parceiro
        from app.rewards.models import PartnerMember
        member = db.session.query(PartnerMember).filter_by(
            partner_id=partner_id, user_id=current_user.id, active=True
        ).first()
        if not member:
            abort(403)

    class RewardSchema(Schema):
        name = mf.Str(required=True)
        description = mf.Str(load_default=None)
        cost_points = mf.Int(required=True, validate=validate.Range(min=1))
        stock = mf.Int(required=True, validate=validate.Range(min=0))
        eligibility = mf.Str(load_default="BOTH")
        fulfillment_terms = mf.Str(load_default=None)
        voucher_lifetime_days = mf.Int(load_default=30)

    data = request.get_json(silent=True) or {}
    from marshmallow import ValidationError
    try:
        clean = RewardSchema().load(data)
    except ValidationError as e:
        return jsonify({"error": {"code": "VALIDATION_ERROR", "message": str(e.messages)}}), 422

    r = Reward(partner_id=partner_id, **clean)
    db.session.add(r)
    db.session.commit()
    from app.rewards.service import reward_dto
    return jsonify(reward_dto(r)), 201


# ---- Awards / Estorno ----

@bp.post("/awards/<int:award_id>/reverse")
@admin_required
def reverse_award(award_id: int):
    from app.gamification.service import reverse_award as svc_reverse
    data = request.get_json(silent=True) or {}
    reason = data.get("reason", "")
    award = svc_reverse(current_user, award_id, reason)
    return jsonify({"id": award.id, "status": award.status}), 200


# ---- Cancelamento de voucher ----

@bp.post("/redemptions/<int:redemption_id>/cancel")
@admin_required
def cancel_redemption(redemption_id: int):
    from app.rewards.service import cancel_redemption as svc_cancel
    data = request.get_json(silent=True) or {}
    dto = svc_cancel(current_user, redemption_id, data.get("reason", ""))
    return jsonify(dto), 200
