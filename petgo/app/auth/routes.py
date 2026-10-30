"""Rotas de autenticação — Task 3."""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.auth import service

bp = Blueprint("auth", __name__)


@bp.post("/users")
def register():
    data = request.get_json(silent=True) or {}
    user = service.register_user(data)
    return jsonify(service.user_dto(user)), 201


@bp.post("/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    user = service.login(data)
    return jsonify(service.user_dto(user)), 200


@bp.post("/auth/logout")
@login_required
def logout():
    service.logout()
    return "", 204


@bp.post("/auth/verify-email")
def verify_email():
    data = request.get_json(silent=True) or {}
    service.verify_email(data.get("token", ""))
    return jsonify({"message": "E-mail verificado com sucesso."}), 200


@bp.post("/auth/forgot-password")
def forgot_password():
    data = request.get_json(silent=True) or {}
    service.forgot_password(data)
    return jsonify({"message": "Se o e-mail existir, você receberá instruções em breve."}), 202


@bp.post("/auth/reset-password")
def reset_password():
    data = request.get_json(silent=True) or {}
    service.reset_password(data)
    return jsonify({"message": "Senha redefinida com sucesso."}), 200


@bp.get("/me")
@login_required
def get_me():
    return jsonify(service.user_dto(current_user)), 200


@bp.patch("/me")
@login_required
def update_me():
    data = request.get_json(silent=True) or {}
    user = service.update_profile(current_user, data)
    return jsonify(service.user_dto(user)), 200
