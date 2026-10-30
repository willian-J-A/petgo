"""Modelos de pets, mídia e eventos."""
from __future__ import annotations

from datetime import datetime, timezone

from app import db


class Pet(db.Model):
    __tablename__ = "pets"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)

    # Publicador — imutável para pontuação
    publisher_user_id = db.Column(
        db.BigInteger, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    # Responsável atual — pessoa ou ONG (exatamente um)
    responsible_user_id = db.Column(
        db.BigInteger, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    responsible_ngo_id = db.Column(
        db.BigInteger, db.ForeignKey("ngos.id", ondelete="SET NULL"), nullable=True
    )

    species = db.Column(db.String(16), nullable=False)   # DOG | CAT | OTHER
    size = db.Column(db.String(16), nullable=True)        # SMALL | MEDIUM | LARGE | desconhecido
    sex = db.Column(db.String(8), nullable=True)          # M | F | desconhecido
    age_months = db.Column(db.Integer, nullable=True)
    help_type = db.Column(db.String(16), nullable=False)  # RESCUE | ADOPTION | TREATMENT | FOSTER
    status = db.Column(db.String(24), nullable=False, default="NEEDS_RESCUE")
    description = db.Column(db.Text, nullable=False)
    city = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(2), nullable=False)

    # Localização restrita — não exposta no DTO público
    private_location = db.Column(db.JSON, nullable=True)

    # Risco
    risk_status = db.Column(db.String(16), nullable=False, default="NONE")
    risk_details = db.Column(db.Text, nullable=True)
    risk_decided_by = db.Column(
        db.BigInteger, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    risk_decided_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # Timestamps de ciclo de vida
    rescued_at = db.Column(db.DateTime(timezone=True), nullable=True)
    adopted_at = db.Column(db.DateTime(timezone=True), nullable=True)
    adopter_user_id = db.Column(
        db.BigInteger, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    deleted_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # Versão para controle de concorrência otimista
    version = db.Column(db.Integer, nullable=False, default=1)

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
    publisher = db.relationship("User", foreign_keys=[publisher_user_id])
    responsible_user = db.relationship("User", foreign_keys=[responsible_user_id])
    responsible_ngo = db.relationship("Ngo", foreign_keys=[responsible_ngo_id])
    adopter = db.relationship("User", foreign_keys=[adopter_user_id])
    risk_decider = db.relationship("User", foreign_keys=[risk_decided_by])
    media = db.relationship("Media", back_populates="pet", lazy="dynamic")
    events = db.relationship(
        "PetEvent", back_populates="pet", lazy="dynamic", order_by="PetEvent.id"
    )

    __table_args__ = (
        db.Index("ix_pets_status_city_state_species", "status", "city", "state", "species"),
        db.Index("ix_pets_risk_status", "risk_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<Pet id={self.id} status={self.status}>"


class Media(db.Model):
    __tablename__ = "media"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    pet_id = db.Column(
        db.BigInteger, db.ForeignKey("pets.id", ondelete="RESTRICT"), nullable=True
    )
    ngo_id = db.Column(
        db.BigInteger, db.ForeignKey("ngos.id", ondelete="RESTRICT"), nullable=True
    )
    storage_key = db.Column(db.String(512), nullable=False, unique=True)
    content_type = db.Column(db.String(64), nullable=False)
    size_bytes = db.Column(db.Integer, nullable=False)
    purpose = db.Column(db.String(32), nullable=False)        # PHOTO | DOCUMENT
    visibility = db.Column(db.String(16), nullable=False, default="PRIVATE")
    uploaded_by = db.Column(
        db.BigInteger, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    pet = db.relationship("Pet", back_populates="media")

    def __repr__(self) -> str:
        return f"<Media id={self.id} purpose={self.purpose}>"


class PetEvent(db.Model):
    __tablename__ = "pet_events"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    pet_id = db.Column(
        db.BigInteger, db.ForeignKey("pets.id", ondelete="RESTRICT"), nullable=False
    )
    event_type = db.Column(db.String(64), nullable=False)
    actor_user_id = db.Column(
        db.BigInteger, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    acting_ngo_id = db.Column(
        db.BigInteger, db.ForeignKey("ngos.id", ondelete="SET NULL"), nullable=True
    )
    from_status = db.Column(db.String(24), nullable=True)
    to_status = db.Column(db.String(24), nullable=True)
    reason = db.Column(db.Text, nullable=True)
    evidence_media_id = db.Column(
        db.BigInteger, db.ForeignKey("media.id", ondelete="SET NULL"), nullable=True
    )
    metadata_ = db.Column("metadata", db.JSON, nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    pet = db.relationship("Pet", back_populates="events")
    actor = db.relationship("User", foreign_keys=[actor_user_id])

    def __repr__(self) -> str:
        return f"<PetEvent id={self.id} type={self.event_type}>"
