"""Serviço de autenticação — registro, sessão, recuperação e perfil."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from flask import current_app
from flask_login import login_user, logout_user
from marshmallow import ValidationError

from app import db
from app.auth.models import AuthToken, User
from app.auth.schemas import (
    ForgotPasswordSchema,
    LoginSchema,
    RegisterSchema,
    ResetPasswordSchema,
    UpdateProfileSchema,
)
from app.notifications.service import enqueue_email_verification, enqueue_password_reset


class AuthError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        self.code = code
        self.message = message
        self.status = status
        super().__init__(message)


def register_user(data: dict) -> User:
    schema = RegisterSchema()
    try:
        clean = schema.load(data)
    except ValidationError as e:
        raise AuthError("VALIDATION_ERROR", str(e.messages), 422)

    email = User.normalize_email(clean["email"])
    if db.session.query(User).filter_by(email_normalized=email).first():
        raise AuthError("EMAIL_CONFLICT", "E-mail já cadastrado.", 409)

    user = User(
        name=clean["name"],
        email_normalized=email,
        city=clean["city"],
        state=clean["state"],
    )
    user.set_password(clean["password"])
    db.session.add(user)
    db.session.flush()  # obtém ID antes do commit

    raw_token = AuthToken.generate(user.id, "email_verification", ttl_seconds=86400)
    db.session.commit()

    # Enfileira e-mail fora da transação principal (outbox)
    try:
        enqueue_email_verification(user.id, raw_token)
    except Exception:
        current_app.logger.exception("Falha ao enfileirar e-mail de verificação")

    return user


def verify_email(token: str) -> None:
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    record = (
        db.session.query(AuthToken)
        .filter_by(token_hash=token_hash, purpose="email_verification")
        .first()
    )
    now = datetime.now(timezone.utc)
    if not record or record.used_at or record.expires_at < now:
        raise AuthError("INVALID_TOKEN", "Token inválido ou expirado.", 400)

    record.used_at = now
    record.user.email_verified_at = now
    db.session.commit()


def login(data: dict) -> User:
    schema = LoginSchema()
    try:
        clean = schema.load(data)
    except ValidationError as e:
        raise AuthError("VALIDATION_ERROR", str(e.messages), 422)

    email = User.normalize_email(clean["email"])
    user = db.session.query(User).filter_by(email_normalized=email).first()

    # Mensagem genérica — não revela se o e-mail existe
    generic = AuthError("INVALID_CREDENTIALS", "Credenciais inválidas.", 401)
    if not user or not user.is_active:
        raise generic
    if not user.check_password(clean["password"]):
        raise generic

    login_user(user)
    return user


def logout() -> None:
    logout_user()


def forgot_password(data: dict) -> None:
    schema = ForgotPasswordSchema()
    try:
        clean = schema.load(data)
    except ValidationError as e:
        raise AuthError("VALIDATION_ERROR", str(e.messages), 422)

    email = User.normalize_email(clean["email"])
    user = db.session.query(User).filter_by(email_normalized=email).first()
    # Não revelar se o e-mail existe — sempre retorna 202
    if user and user.is_active:
        raw_token = AuthToken.generate(user.id, "password_reset", ttl_seconds=3600)
        db.session.commit()
        try:
            enqueue_password_reset(user.id, raw_token)
        except Exception:
            current_app.logger.exception("Falha ao enfileirar e-mail de redefinição")


def reset_password(data: dict) -> None:
    schema = ResetPasswordSchema()
    try:
        clean = schema.load(data)
    except ValidationError as e:
        raise AuthError("VALIDATION_ERROR", str(e.messages), 422)

    token_hash = hashlib.sha256(clean["token"].encode()).hexdigest()
    record = (
        db.session.query(AuthToken)
        .filter_by(token_hash=token_hash, purpose="password_reset")
        .first()
    )
    now = datetime.now(timezone.utc)
    if not record or record.used_at or record.expires_at < now:
        raise AuthError("INVALID_TOKEN", "Token inválido ou expirado.", 400)

    record.used_at = now
    record.user.set_password(clean["password"])
    db.session.commit()


def update_profile(user: User, data: dict) -> User:
    schema = UpdateProfileSchema()
    try:
        clean = schema.load(data)
    except ValidationError as e:
        raise AuthError("VALIDATION_ERROR", str(e.messages), 422)

    allowed = {
        "phone", "interested_in_adoption", "species_preferences",
        "city", "state", "email_opt_in", "all_locations"
    }
    for field in allowed:
        if field in clean:
            setattr(user, field, clean[field])

    db.session.commit()
    return user


def user_dto(user: User) -> dict:
    """DTO público do usuário — sem hash de senha."""
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email_normalized,
        "email_verified": user.email_verified,
        "city": user.city,
        "state": user.state,
        "phone": user.phone,
        "interested_in_adoption": user.interested_in_adoption,
        "species_preferences": user.species_preferences,
        "email_opt_in": user.email_opt_in,
        "all_locations": user.all_locations,
        "is_admin": user.is_admin,
        "created_at": user.created_at.isoformat(),
    }
