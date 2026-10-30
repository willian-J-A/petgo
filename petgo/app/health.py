"""Healthcheck endpoints — sem informações sensíveis."""
from __future__ import annotations

from flask import Blueprint, jsonify

from app import db

bp = Blueprint("health", __name__)


@bp.get("/health/live")
def liveness():
    """Verifica que o processo está vivo."""
    return jsonify({"status": "ok"}), 200


@bp.get("/health/ready")
def readiness():
    """Verifica que o banco está acessível."""
    try:
        db.session.execute(db.text("SELECT 1"))
        return jsonify({"status": "ok"}), 200
    except Exception:
        return jsonify({"status": "unavailable"}), 503
