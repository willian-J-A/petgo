"""Rotas de resgates — Task 6."""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.rescues import service

bp = Blueprint("rescues", __name__)


@bp.post("/pets/<int:pet_id>/rescues")
@login_required
def assume_rescue(pet_id: int):
    data = request.get_json(silent=True) or {}
    dto = service.assume_rescue(current_user, pet_id, data)
    return jsonify(dto), 201


@bp.post("/rescues/<int:rescue_id>/submit")
@login_required
def submit_evidence(rescue_id: int):
    data = request.get_json(silent=True) or {}
    dto = service.submit_evidence(current_user, rescue_id, data)
    return jsonify(dto), 200


@bp.post("/rescues/<int:rescue_id>/confirm")
@login_required
def confirm_rescue(rescue_id: int):
    data = request.get_json(silent=True) or {}
    dto = service.confirm_rescue(current_user, rescue_id, data)
    return jsonify(dto), 200


@bp.post("/rescues/<int:rescue_id>/cancel")
@login_required
def cancel_rescue(rescue_id: int):
    dto = service.cancel_rescue(current_user, rescue_id)
    return jsonify(dto), 200
