"""Modelos de parceiros, benefícios e resgates de prêmios."""
from __future__ import annotations

from datetime import datetime, timezone

from app import db


class Partner(db.Model):
    __tablename__ = "partners"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    name = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(16), nullable=False, default="PENDING")
    # PENDING | ACTIVE | SUSPENDED
    contact_email = db.Column(db.String(254), nullable=False)
    terms = db.Column(db.Text, nullable=True)
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

    members = db.relationship("PartnerMember", back_populates="partner", lazy="dynamic")
    rewards = db.relationship("Reward", back_populates="partner", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<Partner id={self.id} name={self.name}>"


class PartnerMember(db.Model):
    __tablename__ = "partner_members"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    partner_id = db.Column(
        db.BigInteger, db.ForeignKey("partners.id", ondelete="CASCADE"), nullable=False
    )
    user_id = db.Column(
        db.BigInteger, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        db.UniqueConstraint("partner_id", "user_id", name="uq_partner_member"),
    )

    partner = db.relationship("Partner", back_populates="members")
    user = db.relationship("User")

    def __repr__(self) -> str:
        return f"<PartnerMember partner={self.partner_id} user={self.user_id}>"


class Reward(db.Model):
    __tablename__ = "rewards"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    partner_id = db.Column(
        db.BigInteger, db.ForeignKey("partners.id", ondelete="RESTRICT"), nullable=False
    )
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    cost_points = db.Column(db.Integer, nullable=False)  # > 0
    stock = db.Column(db.Integer, nullable=False, default=0)
    starts_at = db.Column(db.DateTime(timezone=True), nullable=True)
    ends_at = db.Column(db.DateTime(timezone=True), nullable=True)
    voucher_lifetime_days = db.Column(db.Integer, nullable=False, default=30)
    eligibility = db.Column(db.String(16), nullable=False, default="BOTH")
    # PERSON | NGO | BOTH
    fulfillment_terms = db.Column(db.Text, nullable=True)
    active = db.Column(db.Boolean, default=True, nullable=False)
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

    partner = db.relationship("Partner", back_populates="rewards")
    redemptions = db.relationship("Redemption", back_populates="reward", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<Reward id={self.id} name={self.name}>"


class Redemption(db.Model):
    """Troca de pontos por benefício — voucher único, imutável após emissão."""

    __tablename__ = "redemptions"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    wallet_id = db.Column(
        db.BigInteger, db.ForeignKey("wallets.id", ondelete="RESTRICT"), nullable=False
    )
    reward_id = db.Column(
        db.BigInteger, db.ForeignKey("rewards.id", ondelete="RESTRICT"), nullable=False
    )
    cost_snapshot = db.Column(db.Integer, nullable=False)
    terms_snapshot = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(16), nullable=False, default="ISSUED")
    # ISSUED | USED | CANCELLED | EXPIRED
    voucher_hash = db.Column(db.String(128), nullable=False, unique=True)
    voucher_ciphertext = db.Column(db.Text, nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    consumed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    consumed_by = db.Column(
        db.BigInteger, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
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

    wallet = db.relationship("Wallet")
    reward = db.relationship("Reward", back_populates="redemptions")
    consumer = db.relationship("User", foreign_keys=[consumed_by])

    def __repr__(self) -> str:
        return f"<Redemption id={self.id} status={self.status}>"
