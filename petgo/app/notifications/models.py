"""Modelos de notificações — Outbox e EmailDeliveries."""
from __future__ import annotations

from datetime import datetime, timezone

from app import db


class OutboxEvent(db.Model):
    """Evento na outbox — publicado junto à transação de negócio."""

    __tablename__ = "outbox_events"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    event_key = db.Column(db.String(255), nullable=False, unique=True)
    type = db.Column(db.String(64), nullable=False)
    payload = db.Column(db.JSON, nullable=False)
    status = db.Column(db.String(16), nullable=False, default="PENDING")
    # PENDING | PROCESSING | DONE | FAILED
    attempts = db.Column(db.Integer, nullable=False, default=0)
    next_attempt_at = db.Column(db.DateTime(timezone=True), nullable=True)
    lease_until = db.Column(db.DateTime(timezone=True), nullable=True)
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

    deliveries = db.relationship(
        "EmailDelivery", back_populates="event", lazy="dynamic"
    )

    def __repr__(self) -> str:
        return f"<OutboxEvent id={self.id} type={self.type} status={self.status}>"


class EmailDelivery(db.Model):
    """Controla entrega individual de e-mail para cada destinatário."""

    __tablename__ = "email_deliveries"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    event_id = db.Column(
        db.BigInteger,
        db.ForeignKey("outbox_events.id", ondelete="RESTRICT"),
        nullable=False,
    )
    user_id = db.Column(
        db.BigInteger, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    recipient_email_snapshot = db.Column(db.String(254), nullable=False)
    template = db.Column(db.String(64), nullable=False)
    status = db.Column(db.String(32), nullable=False, default="PENDING")
    # PENDING | PROCESSING | ACCEPTED_BY_PROVIDER | FAILED | CANCELLED
    attempts = db.Column(db.Integer, nullable=False, default=0)
    provider_id = db.Column(db.String(128), nullable=True)
    next_attempt_at = db.Column(db.DateTime(timezone=True), nullable=True)
    lease_until = db.Column(db.DateTime(timezone=True), nullable=True)
    sanitized_error = db.Column(db.Text, nullable=True)
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

    __table_args__ = (
        db.UniqueConstraint(
            "event_id", "user_id", "template", name="uq_email_delivery"
        ),
        db.Index("ix_email_deliveries_status_next", "status", "next_attempt_at"),
    )

    event = db.relationship("OutboxEvent", back_populates="deliveries")
    user = db.relationship("User")

    def __repr__(self) -> str:
        return f"<EmailDelivery id={self.id} user={self.user_id} status={self.status}>"
