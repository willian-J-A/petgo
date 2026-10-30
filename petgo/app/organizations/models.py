"""Modelos de ONG e membros."""
from __future__ import annotations

from datetime import datetime, timezone

from app import db


class Ngo(db.Model):
    __tablename__ = "ngos"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    name = db.Column(db.String(200), nullable=False)
    cnpj_normalized = db.Column(db.String(14), nullable=False, unique=True)
    contact_email = db.Column(db.String(254), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(2), nullable=False)
    verification_status = db.Column(
        db.String(16), nullable=False, default="PENDING"
    )  # PENDING | APPROVED | REJECTED | SUSPENDED
    verified_by = db.Column(
        db.BigInteger, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    verified_at = db.Column(db.DateTime(timezone=True), nullable=True)
    rejection_reason = db.Column(db.Text, nullable=True)
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

    members = db.relationship("NgoMember", back_populates="ngo", lazy="dynamic")
    verifier = db.relationship("User", foreign_keys=[verified_by])

    def __repr__(self) -> str:
        return f"<Ngo id={self.id} name={self.name}>"


class NgoMember(db.Model):
    __tablename__ = "ngo_members"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    ngo_id = db.Column(
        db.BigInteger, db.ForeignKey("ngos.id", ondelete="CASCADE"), nullable=False
    )
    user_id = db.Column(
        db.BigInteger, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    active = db.Column(db.Boolean, default=True, nullable=False)
    role = db.Column(db.String(32), default="MEMBER", nullable=False)
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
        db.UniqueConstraint("ngo_id", "user_id", name="uq_ngo_member"),
    )

    ngo = db.relationship("Ngo", back_populates="members")
    user = db.relationship("User")

    def __repr__(self) -> str:
        return f"<NgoMember ngo={self.ngo_id} user={self.user_id}>"
