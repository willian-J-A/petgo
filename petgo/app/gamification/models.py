"""Modelos de gamificação — Wallets, PointAwards e PointEntries."""
from __future__ import annotations

from datetime import datetime, timezone

from app import db


class Wallet(db.Model):
    """Carteira de pontos — exatamente um titular (user ou ngo)."""

    __tablename__ = "wallets"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    # Exatamente um dos dois FKs deve ser não-nulo (enforced via CHECK na migração)
    user_id = db.Column(
        db.BigInteger,
        db.ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
        unique=True,
    )
    ngo_id = db.Column(
        db.BigInteger,
        db.ForeignKey("ngos.id", ondelete="RESTRICT"),
        nullable=True,
        unique=True,
    )
    balance = db.Column(db.BigInteger, nullable=False, default=0)
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

    user = db.relationship("User", foreign_keys=[user_id])
    ngo = db.relationship("Ngo", foreign_keys=[ngo_id])
    entries = db.relationship(
        "PointEntry", back_populates="wallet", lazy="dynamic",
        order_by="PointEntry.id"
    )

    def __repr__(self) -> str:
        owner = f"user={self.user_id}" if self.user_id else f"ngo={self.ngo_id}"
        return f"<Wallet id={self.id} {owner} balance={self.balance}>"


class PointAward(db.Model):
    """Controla o crédito de pontos por fase do pet (máximo um por fase)."""

    __tablename__ = "point_awards"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    pet_id = db.Column(
        db.BigInteger, db.ForeignKey("pets.id", ondelete="RESTRICT"), nullable=False
    )
    phase = db.Column(db.String(16), nullable=False)  # PUBLICATION | OUTCOME
    event_id = db.Column(
        db.BigInteger, db.ForeignKey("pet_events.id", ondelete="RESTRICT"), nullable=True
    )
    risk_snapshot = db.Column(db.String(16), nullable=True)  # NONE | APPROVED | REJECTED
    policy_version = db.Column(db.String(16), nullable=False, default="v1")
    status = db.Column(db.String(16), nullable=False, default="SETTLED")
    # WAITING_RISK | SETTLED | REVERSED
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
        db.UniqueConstraint("pet_id", "phase", name="uq_point_award_pet_phase"),
    )

    pet = db.relationship("Pet")
    event = db.relationship("PetEvent")
    entries = db.relationship("PointEntry", back_populates="award", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<PointAward id={self.id} pet={self.pet_id} phase={self.phase} status={self.status}>"


class PointEntry(db.Model):
    """Lançamento imutável de pontos — crédito ou débito."""

    __tablename__ = "point_entries"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    wallet_id = db.Column(
        db.BigInteger, db.ForeignKey("wallets.id", ondelete="RESTRICT"), nullable=False
    )
    award_id = db.Column(
        db.BigInteger, db.ForeignKey("point_awards.id", ondelete="RESTRICT"), nullable=True
    )
    redemption_id = db.Column(
        db.BigInteger,
        # FK para redemptions — adicionada via migração para evitar ciclo de import
        nullable=True,
    )
    correction_id = db.Column(db.BigInteger, nullable=True)
    amount = db.Column(db.BigInteger, nullable=False)  # != 0 enforced via CHECK
    kind = db.Column(db.String(32), nullable=False)
    # PUBLICATION_CREDIT | OUTCOME_CREDIT | REWARD_DEBIT | REFUND | CORRECTION
    reason = db.Column(db.Text, nullable=False)
    entry_key = db.Column(db.String(255), nullable=False, unique=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        db.Index("ix_point_entries_wallet_id", "wallet_id", "id"),
    )

    wallet = db.relationship("Wallet", back_populates="entries")
    award = db.relationship("PointAward", back_populates="entries")

    def __repr__(self) -> str:
        return f"<PointEntry id={self.id} wallet={self.wallet_id} amount={self.amount}>"
