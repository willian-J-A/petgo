"""Rotas de carteira — Task 8."""
from __future__ import annotations

from flask import Blueprint, abort, jsonify, request
from flask_login import current_user, login_required

from app import db
from app.gamification import service
from app.gamification.models import Wallet
from app.organizations.service import get_ngo_or_404, is_active_member

bp = Blueprint("gamification", __name__)


@bp.get("/me/wallet")
@login_required
def my_wallet():
    return jsonify(service.get_user_wallet(current_user.id)), 200


@bp.get("/me/wallet/entries")
@login_required
def my_wallet_entries():
    w = db.session.query(Wallet).filter_by(user_id=current_user.id).first()
    if not w:
        return jsonify({"items": [], "page": 1, "page_size": 20, "total": 0}), 200
    page = request.args.get("page", 1, type=int)
    return jsonify(service.get_wallet_entries(w.id, page)), 200


@bp.get("/ngos/<int:ngo_id>/wallet")
@login_required
def ngo_wallet(ngo_id: int):
    ngo = get_ngo_or_404(ngo_id)
    if not current_user.is_admin and not is_active_member(current_user.id, ngo_id):
        abort(403)
    return jsonify(service.get_ngo_wallet(ngo_id)), 200


@bp.get("/ngos/<int:ngo_id>/wallet/entries")
@login_required
def ngo_wallet_entries(ngo_id: int):
    ngo = get_ngo_or_404(ngo_id)
    if not current_user.is_admin and not is_active_member(current_user.id, ngo_id):
        abort(403)
    w = db.session.query(Wallet).filter_by(ngo_id=ngo_id).first()
    if not w:
        return jsonify({"items": [], "page": 1, "page_size": 20, "total": 0}), 200
    page = request.args.get("page", 1, type=int)
    return jsonify(service.get_wallet_entries(w.id, page)), 200
