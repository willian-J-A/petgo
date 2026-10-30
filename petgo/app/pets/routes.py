"""Rotas de pets — Task 5."""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.pets import service

bp = Blueprint("pets", __name__)


@bp.post("/pets")
@login_required
def create_pet():
    idem_key = request.headers.get("Idempotency-Key")
    data = request.get_json(silent=True) or {}
    dto = service.create_pet(current_user, data, idem_key)
    return jsonify(dto), 201


@bp.get("/pets")
def list_pets():
    """Lista de resgate (NEEDS_RESCUE, IN_RESCUE)."""
    items, total, page, page_size = service.list_rescue_pets(request.args.to_dict())
    return jsonify({"items": items, "page": page, "page_size": page_size, "total": total}), 200


@bp.get("/pets/adoption")
def list_adoption_pets():
    """Lista de adoção (AVAILABLE)."""
    items, total, page, page_size = service.list_adoption_pets(request.args.to_dict())
    return jsonify({"items": items, "page": page, "page_size": page_size, "total": total}), 200


@bp.get("/pets/<int:pet_id>")
def get_pet(pet_id: int):
    pet = service.get_pet_or_404(pet_id)
    if current_user.is_authenticated and (
        current_user.is_admin
        or current_user.id == pet.responsible_user_id
        or current_user.id == pet.publisher_user_id
    ):
        return jsonify(service.pet_private_dto(pet)), 200
    return jsonify(service.pet_public_dto(pet)), 200


@bp.patch("/pets/<int:pet_id>")
@login_required
def update_pet(pet_id: int):
    data = request.get_json(silent=True) or {}
    dto = service.update_pet(current_user, pet_id, data)
    return jsonify(dto), 200


@bp.delete("/pets/<int:pet_id>")
@login_required
def delete_pet(pet_id: int):
    service.delete_pet(current_user, pet_id)
    return "", 204


@bp.post("/pets/<int:pet_id>/availability")
@login_required
def mark_available(pet_id: int):
    dto = service.mark_available(current_user, pet_id)
    return jsonify(dto), 200


@bp.post("/pets/<int:pet_id>/risk")
@login_required
def report_risk(pet_id: int):
    data = request.get_json(silent=True) or {}
    dto = service.report_risk(current_user, pet_id, data)
    return jsonify(dto), 200


@bp.post("/media")
@login_required
def upload_media():
    """Registra metadados de mídia já enviada ao S3 (storage_key obtido via presigned URL)."""
    data = request.get_json(silent=True) or {}
    media = service.register_media(
        current_user,
        storage_key=data.get("storage_key", ""),
        content_type=data.get("content_type", ""),
        size_bytes=data.get("size_bytes", 0),
        purpose=data.get("purpose", "PHOTO"),
    )
    return jsonify({"id": media.id, "storage_key": media.storage_key}), 201
