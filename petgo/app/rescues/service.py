"""Serviço de resgates — assunção exclusiva, comprovação e confirmação."""
from __future__ import annotations

from datetime import datetime, timezone

from flask import abort
from marshmallow import Schema, ValidationError, fields

from app import db
from app.gamification.service import settle_outcome
from app.notifications.service import enqueue_rescue_assumed, enqueue_rescue_confirmed
from app.organizations.service import is_active_member
from app.pets.models import Pet, PetEvent
from app.pets.service import get_pet_or_404
from app.rescues.models import Rescue


class RescueError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        self.code = code
        self.message = message
        self.status = status
        super().__init__(message)


class AssumeSchema(Schema):
    ngo_id = fields.Int(required=True)
    idempotency_key = fields.Str(load_default=None)


class SubmitSchema(Schema):
    evidence_media_id = fields.Int(required=True)


class ConfirmSchema(Schema):
    reason = fields.Str(load_default=None)


def assume_rescue(current_user, pet_id: int, data: dict) -> dict:
    """ONG assume atendimento — exclusivo, gera histórico, sem pontos."""
    schema = AssumeSchema()
    try:
        clean = schema.load(data)
    except ValidationError as e:
        raise RescueError("VALIDATION_ERROR", str(e.messages), 422)

    ngo_id = clean["ngo_id"]
    if not is_active_member(current_user.id, ngo_id):
        raise RescueError("NOT_NGO_MEMBER", "Você não é membro ativo desta ONG.", 403)

    # Bloqueia o pet para evitar corrida
    pet = (
        db.session.query(Pet)
        .filter_by(id=pet_id)
        .with_for_update()
        .first()
    )
    if not pet or pet.deleted_at:
        abort(404)
    if pet.status != "NEEDS_RESCUE":
        raise RescueError("INVALID_PET_STATUS",
                          f"Pet deve estar NEEDS_RESCUE; atual: {pet.status}.", 409)

    # Transição
    pet.status = "IN_RESCUE"
    pet.responsible_ngo_id = ngo_id
    pet.responsible_user_id = None
    pet.version += 1

    rescue = Rescue(
        pet_id=pet.id,
        ngo_id=ngo_id,
        executor_user_id=current_user.id,
        status="ASSUMED",
    )
    db.session.add(rescue)

    event = PetEvent(
        pet_id=pet.id,
        event_type="RESCUE_ASSUMED",
        actor_user_id=current_user.id,
        acting_ngo_id=ngo_id,
        from_status="NEEDS_RESCUE",
        to_status="IN_RESCUE",
    )
    db.session.add(event)

    enqueue_rescue_assumed(pet.id, ngo_id, pet.publisher_user_id)

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        if "uq_rescues_active_pet" in str(e):
            raise RescueError("RESCUE_CONFLICT", "Outro atendimento ativo já existe para este pet.", 409)
        raise

    return rescue_dto(rescue)


def submit_evidence(current_user, rescue_id: int, data: dict) -> dict:
    """Executor envia comprovação; resgate vai para PENDING_CONFIRMATION."""
    schema = SubmitSchema()
    try:
        clean = schema.load(data)
    except ValidationError as e:
        raise RescueError("VALIDATION_ERROR", str(e.messages), 422)

    rescue = _get_rescue_or_404(rescue_id)
    if rescue.executor_user_id != current_user.id:
        abort(403)
    if rescue.status != "ASSUMED":
        raise RescueError("INVALID_STATUS", "Atendimento deve estar ASSUMED.", 409)

    rescue.status = "PENDING_CONFIRMATION"
    rescue.evidence_media_id = clean["evidence_media_id"]
    rescue.updated_at = datetime.now(timezone.utc)

    event = PetEvent(
        pet_id=rescue.pet_id,
        event_type="RESCUE_EVIDENCE_SUBMITTED",
        actor_user_id=current_user.id,
        acting_ngo_id=rescue.ngo_id,
    )
    db.session.add(event)
    db.session.commit()
    return rescue_dto(rescue)


def confirm_rescue(current_user, rescue_id: int, data: dict) -> dict:
    """Admin ou publicador independente confirma o resgate."""
    rescue = _get_rescue_or_404(rescue_id)
    if rescue.status != "PENDING_CONFIRMATION":
        raise RescueError("INVALID_STATUS", "Atendimento deve estar PENDING_CONFIRMATION.", 409)

    pet = (
        db.session.query(Pet)
        .filter_by(id=rescue.pet_id)
        .with_for_update()
        .first()
    )

    # Verificação de independência: admin ou publicador != executor/ONG
    executor_id = rescue.executor_user_id
    is_admin = current_user.is_admin
    is_independent_publisher = (
        pet.publisher_user_id == current_user.id
        and current_user.id != executor_id
        and not is_active_member(current_user.id, rescue.ngo_id)
    )
    if not (is_admin or is_independent_publisher):
        raise RescueError(
            "CONFIRMATION_NOT_AUTHORIZED",
            "Confirmação requer administrador ou publicador independente do executor.",
            403,
        )

    now = datetime.now(timezone.utc)
    rescue.status = "CONFIRMED"
    rescue.confirmed_by = current_user.id
    rescue.confirmed_at = now
    pet.status = "SHELTERED"
    pet.rescued_at = now
    pet.responsible_ngo_id = rescue.ngo_id
    pet.responsible_user_id = None
    pet.version += 1

    event = PetEvent(
        pet_id=pet.id,
        event_type="RESCUE_CONFIRMED",
        actor_user_id=current_user.id,
        acting_ngo_id=rescue.ngo_id,
        from_status="IN_RESCUE",
        to_status="SHELTERED",
        evidence_media_id=rescue.evidence_media_id,
    )
    db.session.add(event)
    db.session.flush()

    # Liquida pontos de desfecho (ou coloca em espera se risco pendente)
    settle_outcome(pet, event, rescue.ngo_id)

    enqueue_rescue_confirmed(pet.id, rescue.id)
    db.session.commit()
    return rescue_dto(rescue)


def cancel_rescue(current_user, rescue_id: int) -> dict:
    """Cancela atendimento antes da confirmação; libera pet para NEEDS_RESCUE."""
    rescue = _get_rescue_or_404(rescue_id)
    if rescue.status not in ("ASSUMED", "PENDING_CONFIRMATION"):
        raise RescueError("INVALID_STATUS", "Atendimento já finalizado.", 409)

    is_executor = rescue.executor_user_id == current_user.id
    is_ngo_member = is_active_member(current_user.id, rescue.ngo_id)
    if not (is_executor or is_ngo_member or current_user.is_admin):
        abort(403)

    rescue.status = "CANCELLED"
    pet = db.session.get(Pet, rescue.pet_id)
    pet.status = "NEEDS_RESCUE"
    pet.responsible_ngo_id = None
    pet.responsible_user_id = pet.publisher_user_id
    pet.version += 1

    event = PetEvent(
        pet_id=pet.id,
        event_type="RESCUE_CANCELLED",
        actor_user_id=current_user.id,
        acting_ngo_id=rescue.ngo_id,
        from_status="IN_RESCUE",
        to_status="NEEDS_RESCUE",
    )
    db.session.add(event)
    db.session.commit()
    return rescue_dto(rescue)


def admin_risk_decision(admin_user, pet_id: int, decision: str, reason: str = "") -> dict:
    """Admin aprova ou rejeita risco; liquida WAITING_RISK se existir."""
    from app.gamification.service import settle_waiting_risk

    if decision not in ("APPROVED", "REJECTED"):
        raise RescueError("INVALID_DECISION", "Decisão deve ser APPROVED ou REJECTED.", 422)

    pet = (
        db.session.query(Pet)
        .filter_by(id=pet_id)
        .with_for_update()
        .first()
    )
    if not pet:
        abort(404)
    if pet.risk_status not in ("PENDING",):
        raise RescueError("RISK_NOT_PENDING", "Risco não está PENDING.", 409)
    if pet.publisher_user_id == admin_user.id:
        raise RescueError("CONFLICT_OF_INTEREST", "Admin beneficiário não pode decidir risco.", 403)

    now = datetime.now(timezone.utc)
    pet.risk_status = decision
    pet.risk_decided_by = admin_user.id
    pet.risk_decided_at = now

    event = PetEvent(
        pet_id=pet.id,
        event_type=f"RISK_{decision}",
        actor_user_id=admin_user.id,
        reason=reason,
    )
    db.session.add(event)
    db.session.flush()

    settle_waiting_risk(pet, event)
    db.session.commit()

    from app.pets.service import pet_public_dto
    return pet_public_dto(pet)


def _get_rescue_or_404(rescue_id: int) -> Rescue:
    r = db.session.get(Rescue, rescue_id)
    if not r:
        abort(404)
    return r


def rescue_dto(rescue: Rescue) -> dict:
    return {
        "id": rescue.id,
        "pet_id": rescue.pet_id,
        "ngo_id": rescue.ngo_id,
        "executor_user_id": rescue.executor_user_id,
        "status": rescue.status,
        "confirmed_at": rescue.confirmed_at.isoformat() if rescue.confirmed_at else None,
        "created_at": rescue.created_at.isoformat(),
    }
