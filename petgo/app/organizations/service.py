"""Serviço de ONGs."""
from __future__ import annotations

import re
from datetime import datetime, timezone

from flask import abort
from marshmallow import Schema, ValidationError, fields, validate

from app import db
from app.organizations.models import Ngo, NgoMember


class NgoSchema(Schema):
    name = fields.Str(required=True, validate=validate.Length(min=2, max=200))
    cnpj = fields.Str(required=True)
    contact_email = fields.Email(required=True)
    city = fields.Str(required=True, validate=validate.Length(min=2, max=100))
    state = fields.Str(required=True, validate=validate.Length(equal=2))


class NgoError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        self.code = code
        self.message = message
        self.status = status
        super().__init__(message)


def _normalize_cnpj(raw: str) -> str:
    return re.sub(r"\D", "", raw)


def _validate_cnpj(cnpj: str) -> bool:
    """Valida dígitos verificadores do CNPJ."""
    if len(cnpj) != 14 or len(set(cnpj)) == 1:
        return False

    def calc(cnpj: str, n: int) -> int:
        weights = list(range(n, 1, -1))
        s = sum(int(cnpj[i]) * weights[i] for i in range(n - 1))
        rest = s % 11
        return 0 if rest < 2 else 11 - rest

    if calc(cnpj, 13) != int(cnpj[12]):
        return False
    if calc(cnpj, 14) != int(cnpj[13]):
        return False
    return True


def create_ngo(current_user, data: dict) -> Ngo:
    schema = NgoSchema()
    try:
        clean = schema.load(data)
    except ValidationError as e:
        raise NgoError("VALIDATION_ERROR", str(e.messages), 422)

    cnpj = _normalize_cnpj(clean["cnpj"])
    if not _validate_cnpj(cnpj):
        raise NgoError("INVALID_CNPJ", "CNPJ inválido.", 422)

    if db.session.query(Ngo).filter_by(cnpj_normalized=cnpj).first():
        raise NgoError("CNPJ_CONFLICT", "CNPJ já cadastrado.", 409)

    ngo = Ngo(
        name=clean["name"],
        cnpj_normalized=cnpj,
        contact_email=clean["contact_email"],
        city=clean["city"],
        state=clean["state"].upper(),
        verification_status="PENDING",
    )
    db.session.add(ngo)
    db.session.flush()

    member = NgoMember(ngo_id=ngo.id, user_id=current_user.id, role="ADMIN")
    db.session.add(member)
    db.session.commit()
    return ngo


def list_ngos(page: int, per_page: int):
    q = db.session.query(Ngo).filter(
        Ngo.verification_status == "APPROVED"
    ).order_by(Ngo.id)
    total = q.count()
    items = q.offset((page - 1) * per_page).limit(per_page).all()
    return items, total


def get_ngo_or_404(ngo_id: int) -> Ngo:
    ngo = db.session.get(Ngo, ngo_id)
    if not ngo:
        abort(404)
    return ngo


def ngo_public_dto(ngo: Ngo) -> dict:
    """DTO público sanitizado — sem documentos ou dados restritos."""
    return {
        "id": ngo.id,
        "name": ngo.name,
        "city": ngo.city,
        "state": ngo.state,
        "contact_email": ngo.contact_email,
        "verification_status": ngo.verification_status,
        "created_at": ngo.created_at.isoformat(),
    }


def admin_approve_ngo(admin_user, ngo_id: int, decision: str, reason: str | None = None) -> Ngo:
    ngo = get_ngo_or_404(ngo_id)
    valid = {"APPROVED", "REJECTED", "SUSPENDED"}
    if decision not in valid:
        raise NgoError("INVALID_DECISION", f"Decisão deve ser uma de: {valid}", 422)

    ngo.verification_status = decision
    ngo.verified_by = admin_user.id
    ngo.verified_at = datetime.now(timezone.utc)
    if reason:
        ngo.rejection_reason = reason

    db.session.commit()
    return ngo


def is_active_member(user_id: int, ngo_id: int) -> bool:
    return bool(
        db.session.query(NgoMember)
        .filter_by(ngo_id=ngo_id, user_id=user_id, active=True)
        .first()
    )
