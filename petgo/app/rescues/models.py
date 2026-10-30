"""Modelo de atendimento de resgate."""
from __future__ import annotations

from datetime import datetime, timezone

from app import db


class Rescue(db.Model):
    __tablename__ = "rescues"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    pet_id = db.Column(
        db.BigInteger, db.ForeignKey("pets.id", ondelete="RESTRICT"), nullable=False
    )
    ngo_id = db.Column(
        db.BigInteger, db.ForeignKey("ngos.id", ondelete="RESTRICT"), nullable=False
    )
    executor_user_id = db.Column(
        db.BigInteger, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    status = db.Column(db.String(24), nullable=False, default="ASSUMED")
    # ASSUMED | PENDING_CONFIRMATION | CONFIRMED | CANCELLED
    evidence_media_id = db.Column(
        db.BigInteger, db.ForeignKey("media.id", ondelete="SET NULL"), nullable=True
    )
    confirmed_by = db.Column(
        db.BigInteger, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    confirmed_at = db.Column(db.DateTime(timezone=True), nullable=True)
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

    # Unicidade de atendimento ativo por pet:
    # Garantida por índice único parcial criado na migração (coluna gerada MySQL).
    # Apenas um ASSUMED ou PENDING_CONFIRMATION por pet simultaneamente.

    pet = db.relationship("Pet")
    ngo = db.relationship("Ngo")
    executor = db.relationship("User", foreign_keys=[executor_user_id])
    confirmer = db.relationship("User", foreign_keys=[confirmed_by])

    def __repr__(self) -> str:
        return f"<Rescue id={self.id} pet={self.pet_id} status={self.status}>"
