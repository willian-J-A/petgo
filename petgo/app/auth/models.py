"""Modelos de autenticação — Users e AuthTokens."""
from __future__ import annotations

import secrets
from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app import db, login_manager


class User(UserMixin, db.Model):
    """Conta de usuário pessoa."""

    __tablename__ = "users"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    name = db.Column(db.String(120), nullable=False)
    email_normalized = db.Column(db.String(254), nullable=False, unique=True)
    password_hash = db.Column(db.String(256), nullable=False)
    email_verified_at = db.Column(db.DateTime(timezone=True), nullable=True)
    city = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(2), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    interested_in_adoption = db.Column(db.Boolean, default=False, nullable=False)
    species_preferences = db.Column(db.JSON, default=list, nullable=False)
    email_opt_in = db.Column(db.Boolean, default=True, nullable=False)
    all_locations = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relacionamentos
    auth_tokens = db.relationship(
        "AuthToken", back_populates="user", lazy="dynamic", cascade="all, delete-orphan"
    )

    @staticmethod
    def normalize_email(email: str) -> str:
        return email.strip().lower()

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password, method="scrypt")

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def email_verified(self) -> bool:
        return self.email_verified_at is not None

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email_normalized}>"


class AuthToken(db.Model):
    """Tokens de uso único para verificação de e-mail e recuperação de senha."""

    __tablename__ = "auth_tokens"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    user_id = db.Column(
        db.BigInteger, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # Hash armazenado — token puro nunca é persistido
    token_hash = db.Column(db.String(128), nullable=False, unique=True)
    purpose = db.Column(
        db.String(32), nullable=False
    )  # "email_verification" | "password_reset"
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    used_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user = db.relationship("User", back_populates="auth_tokens")

    @classmethod
    def generate(cls, user_id: int, purpose: str, ttl_seconds: int = 86400) -> str:
        """Cria um token, persiste o hash e devolve o token puro (uma vez)."""
        import hashlib
        from datetime import timedelta

        raw = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw.encode()).hexdigest()
        obj = cls(
            user_id=user_id,
            token_hash=token_hash,
            purpose=purpose,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds),
        )
        db.session.add(obj)
        return raw

    def __repr__(self) -> str:
        return f"<AuthToken id={self.id} purpose={self.purpose}>"


@login_manager.user_loader
def load_user(user_id: str) -> User | None:
    return db.session.get(User, int(user_id))
