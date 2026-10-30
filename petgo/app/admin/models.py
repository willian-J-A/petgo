"""Modelos administrativos — AuditLog e IdempotencyKey."""
from __future__ import annotations

from datetime import datetime, timezone

from app import db


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    actor_user_id = db.Column(
        db.BigInteger, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action = db.Column(db.String(64), nullable=False)
    target_type = db.Column(db.String(64), nullable=False)
    target_id = db.Column(db.BigInteger, nullable=True)
    reason = db.Column(db.Text, nullable=True)
    correlation_id = db.Column(db.String(64), nullable=True)
    # Metadados sanitizados — sem senhas, tokens ou PII extra
    sanitized_metadata = db.Column(db.JSON, nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    actor = db.relationship("User", foreign_keys=[actor_user_id])

    def __repr__(self) -> str:
        return f"<AuditLog id={self.id} action={self.action}>"


class IdempotencyKey(db.Model):
    """Rastreamento de requisições idempotentes (R03.6, R07.2)."""

    __tablename__ = "idempotency_keys"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    actor_user_id = db.Column(
        db.BigInteger, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    operation = db.Column(db.String(64), nullable=False)
    key = db.Column(db.String(255), nullable=False)
    request_hash = db.Column(db.String(64), nullable=False)
    response_status = db.Column(db.Integer, nullable=True)
    response_body = db.Column(db.JSON, nullable=True)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        db.UniqueConstraint("actor_user_id", "operation", "key", name="uq_idempotency"),
    )

    actor = db.relationship("User", foreign_keys=[actor_user_id])

    def __repr__(self) -> str:
        return f"<IdempotencyKey id={self.id} operation={self.operation} key={self.key}>"
