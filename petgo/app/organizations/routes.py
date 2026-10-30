"""Rotas de ONGs — Task 4."""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.organizations import service

bp = Blueprint("organizations", __name__)


@bp.post("/ngos")
@login_required
def create_ngo():
    data = request.get_json(silent=True) or {}
    ngo = service.create_ngo(current_user, data)
    return jsonify(service.ngo_public_dto(ngo)), 201


@bp.get("/ngos")
def list_ngos():
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("page_size", 20, type=int), 100)
    items, total = service.list_ngos(page, per_page)
    return jsonify({
        "items": [service.ngo_public_dto(n) for n in items],
        "page": page,
        "page_size": per_page,
        "total": total,
    }), 200


@bp.get("/ngos/<int:ngo_id>")
def get_ngo(ngo_id: int):
    ngo = service.get_ngo_or_404(ngo_id)
    return jsonify(service.ngo_public_dto(ngo)), 200
