"""Rotas de adoção — Task 7."""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.adoptions import service

bp = Blueprint("adoptions", __name__)


@bp.post("/pets/<int:pet_id>/adoptions")
@login_required
def create_adoption(pet_id: int):
    data = request.get_json(silent=True) or {}
    dto = service.create_adoption_request(current_user, pet_id, data)
    return jsonify(dto), 201


@bp.get("/me/adoptions")
@login_required
def my_adoptions():
    return jsonify({"items": service.list_my_adoptions(current_user)}), 200


@bp.get("/pets/<int:pet_id>/adoptions")
@login_required
def pet_adoptions(pet_id: int):
    return jsonify({"items": service.list_pet_adoptions(current_user, pet_id)}), 200


@bp.post("/adoptions/<int:adoption_id>/review")
@login_required
def review_adoption(adoption_id: int):
    data = request.get_json(silent=True) or {}
    decision = data.get("decision", "")
    reason = data.get("reason", "")
    dto = service.review_adoption(current_user, adoption_id, decision, reason)
    return jsonify(dto), 200


@bp.post("/adoptions/<int:adoption_id>/cancel")
@login_required
def cancel_adoption(adoption_id: int):
    dto = service.cancel_adoption(current_user, adoption_id)
    return jsonify(dto), 200


@bp.post("/adoptions/<int:adoption_id>/delivery")
@login_required
def confirm_delivery(adoption_id: int):
    dto = service.confirm_delivery(current_user, adoption_id)
    return jsonify(dto), 200


@bp.post("/adoptions/<int:adoption_id>/receipt")
@login_required
def confirm_receipt(adoption_id: int):
    dto = service.confirm_receipt(current_user, adoption_id)
    return jsonify(dto), 200
