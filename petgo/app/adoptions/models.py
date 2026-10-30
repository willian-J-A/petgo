"""Modelo de pedidos de adoção."""
from __future__ import annotations

from datetime import datetime, timezone

from app import db


class AdoptionRequest(db.Model):
    __tablename__ = "adoption_requests"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    pet_id = db.Column(
        db.BigInteger, db.ForeignKey("pets.id", ondelete="RESTRICT"), nullable=False
    )
    applicant_user_id = db.Column(
        db.BigInteger, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    status = db.Column(db.String(24), nullable=False, default="SENT")
    # SENT | UNDER_REVIEW | APPROVED | COMPLETED | REJECTED | CANCELLED
    origin_status = db.Column(db.String(24), nullable=True)  # estado do pet ao pedir
    participating_ngo_id = db.Column(
        db.BigInteger, db.ForeignKey("ngos.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_by = db.Column(
        db.BigInteger, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    delivery_confirmed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    receipt_confirmed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)
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

    # Unicidade de pedido ativo por (pet, solicitante):
    # Garantida por índice único parcial na migração (coluna gerada MySQL).

    pet = db.relationship("Pet")
    applicant = db.relationship("User", foreign_keys=[applicant_user_id])
    reviewer = db.relationship("User", foreign_keys=[reviewed_by])
    participating_ngo = db.relationship("Ngo", foreign_keys=[participating_ngo_id])

    def __repr__(self) -> str:
        return f"<AdoptionRequest id={self.id} pet={self.pet_id} status={self.status}>"
