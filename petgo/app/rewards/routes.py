"""Rotas de prêmios — Task 9."""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.rewards import service

bp = Blueprint("rewards", __name__)


@bp.get("/rewards")
def list_rewards():
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("page_size", 20, type=int), 100)
    return jsonify(service.list_rewards(page, per_page)), 200


@bp.post("/rewards/<int:reward_id>/redemptions")
@login_required
def redeem(reward_id: int):
    data = request.get_json(silent=True) or {}
    data["reward_id"] = reward_id
    dto = service.redeem_reward(current_user, data)
    return jsonify(dto), 201


@bp.get("/me/redemptions")
@login_required
def my_redemptions():
    from app import db
    from app.gamification.models import Wallet
    from app.rewards.models import Redemption
    w = db.session.query(Wallet).filter_by(user_id=current_user.id).first()
    if not w:
        return jsonify({"items": []}), 200
    items = db.session.query(Redemption).filter_by(wallet_id=w.id).order_by(Redemption.id.desc()).all()
    return jsonify({"items": [service.redemption_dto(r) for r in items]}), 200


@bp.get("/ngos/<int:ngo_id>/redemptions")
@login_required
def ngo_redemptions(ngo_id: int):
    from app import db
    from app.gamification.models import Wallet
    from app.organizations.service import get_ngo_or_404, is_active_member
    from app.rewards.models import Redemption
    from flask import abort
    ngo = get_ngo_or_404(ngo_id)
    if not current_user.is_admin and not is_active_member(current_user.id, ngo_id):
        abort(403)
    w = db.session.query(Wallet).filter_by(ngo_id=ngo_id).first()
    if not w:
        return jsonify({"items": []}), 200
    items = db.session.query(Redemption).filter_by(wallet_id=w.id).order_by(Redemption.id.desc()).all()
    return jsonify({"items": [service.redemption_dto(r) for r in items]}), 200


@bp.post("/vouchers/consume")
@login_required
def consume_voucher():
    data = request.get_json(silent=True) or {}
    dto = service.consume_voucher(current_user, data)
    return jsonify(dto), 200
