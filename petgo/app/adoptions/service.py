"""Serviço de adoção — pedidos, reserva e confirmação de entrega."""
from __future__ import annotations

from datetime import datetime, timezone

from flask import abort
from marshmallow import Schema, ValidationError, fields

from app import db
from app.adoptions.models import AdoptionRequest
from app.gamification.service import settle_outcome
from app.notifications.service import enqueue_adoption_decision
from app.organizations.service import is_active_member
from app.pets.models import Pet, PetEvent
from app.pets.service import get_pet_or_404


class AdoptionError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        self.code = code
        self.message = message
        self.status = status
        super().__init__(message)


class CreateAdoptionSchema(Schema):
    contact_info = fields.Str(required=True)
    accepts_responsibility = fields.Bool(required=True)
    participating_ngo_id = fields.Int(load_default=None)


def create_adoption_request(current_user, pet_id: int, data: dict) -> dict:
    if not current_user.email_verified:
        raise AdoptionError("EMAIL_NOT_VERIFIED", "Verifique seu e-mail.", 403)

    schema = CreateAdoptionSchema()
    try:
        clean = schema.load(data)
    except ValidationError as e:
        raise AdoptionError("VALIDATION_ERROR", str(e.messages), 422)

    if not clean["accepts_responsibility"]:
        raise AdoptionError("RESPONSIBILITY_REQUIRED", "Aceite de responsabilidade obrigatório.", 422)

    pet = (
        db.session.query(Pet).filter_by(id=pet_id).with_for_update().first()
    )
    if not pet or pet.deleted_at:
        abort(404)
    if pet.status not in ("AVAILABLE", "NEEDS_RESCUE"):
        raise AdoptionError("INVALID_PET_STATUS",
                            f"Pet deve estar AVAILABLE ou NEEDS_RESCUE; atual: {pet.status}.", 409)

    req = AdoptionRequest(
        pet_id=pet.id,
        applicant_user_id=current_user.id,
        status="SENT",
        origin_status=pet.status,
        participating_ngo_id=clean.get("participating_ngo_id"),
    )
    db.session.add(req)

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        if "uq_adoption_active_applicant" in str(e):
            raise AdoptionError("DUPLICATE_REQUEST", "Pedido ativo já existe para este pet.", 409)
        raise

    return adoption_dto(req)


def review_adoption(current_user, adoption_id: int, decision: str, reason: str = "") -> dict:
    """Responsável ou admin aprova/rejeita/cancela pedido."""
    req = _get_or_404(adoption_id)
    pet = (
        db.session.query(Pet).filter_by(id=req.pet_id).with_for_update().first()
    )
    _assert_reviewer(current_user, pet)

    valid_transitions = {
        "SENT": {"UNDER_REVIEW", "APPROVED", "REJECTED", "CANCELLED"},
        "UNDER_REVIEW": {"APPROVED", "REJECTED", "CANCELLED"},
    }
    if req.status not in valid_transitions:
        raise AdoptionError("INVALID_STATUS", f"Pedido em estado terminal: {req.status}.", 409)
    if decision not in valid_transitions[req.status]:
        raise AdoptionError("INVALID_DECISION", f"Transição inválida de {req.status} para {decision}.", 422)

    req.status = decision
    req.reviewed_by = current_user.id

    if decision == "APPROVED":
        # Reserva o pet
        pet.status = "ADOPTION_PENDING"
        pet.version += 1

        # Cancela outros pedidos ativos
        others = (
            db.session.query(AdoptionRequest)
            .filter(
                AdoptionRequest.pet_id == pet.id,
                AdoptionRequest.id != req.id,
                AdoptionRequest.status.in_(["SENT", "UNDER_REVIEW"]),
            )
            .all()
        )
        for other in others:
            other.status = "CANCELLED"

        event = PetEvent(
            pet_id=pet.id,
            event_type="ADOPTION_APPROVED",
            actor_user_id=current_user.id,
            from_status=pet.status,
            to_status="ADOPTION_PENDING",
        )
        db.session.add(event)

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        if "uq_adoption_reservation" in str(e):
            raise AdoptionError("RESERVATION_CONFLICT", "Reserva já existe para este pet.", 409)
        raise

    enqueue_adoption_decision(adoption_id, decision)
    return adoption_dto(req)


def confirm_delivery(current_user, adoption_id: int) -> dict:
    """Responsável confirma entrega do animal."""
    req = _get_or_404(adoption_id)
    pet = db.session.query(Pet).filter_by(id=req.pet_id).with_for_update().first()
    _assert_reviewer(current_user, pet)

    if req.status != "APPROVED":
        raise AdoptionError("INVALID_STATUS", "Pedido deve estar APPROVED.", 409)
    if req.delivery_confirmed_at:
        raise AdoptionError("ALREADY_CONFIRMED", "Entrega já confirmada.", 409)

    req.delivery_confirmed_at = datetime.now(timezone.utc)
    db.session.commit()
    return _try_complete(req, pet)


def confirm_receipt(current_user, adoption_id: int) -> dict:
    """Adotante confirma recebimento."""
    req = _get_or_404(adoption_id)
    if req.applicant_user_id != current_user.id:
        abort(403)
    if req.status != "APPROVED":
        raise AdoptionError("INVALID_STATUS", "Pedido deve estar APPROVED.", 409)
    if req.receipt_confirmed_at:
        raise AdoptionError("ALREADY_CONFIRMED", "Recebimento já confirmado.", 409)

    req.receipt_confirmed_at = datetime.now(timezone.utc)
    pet = db.session.query(Pet).filter_by(id=req.pet_id).with_for_update().first()
    db.session.commit()
    return _try_complete(req, pet)


def cancel_adoption(current_user, adoption_id: int) -> dict:
    """Cancela antes da entrega — retorna ao estado de origem."""
    req = _get_or_404(adoption_id)
    if req.status not in ("APPROVED",) and req.applicant_user_id != current_user.id:
        abort(403)
    if req.delivery_confirmed_at or req.receipt_confirmed_at:
        raise AdoptionError("ALREADY_IN_PROGRESS", "Entrega/recebimento já iniciados.", 409)

    pet = db.session.query(Pet).filter_by(id=req.pet_id).with_for_update().first()
    req.status = "CANCELLED"

    origin = req.origin_status or "AVAILABLE"
    pet.status = origin
    pet.version += 1

    event = PetEvent(
        pet_id=pet.id,
        event_type="ADOPTION_CANCELLED",
        actor_user_id=current_user.id,
        from_status="ADOPTION_PENDING",
        to_status=origin,
    )
    db.session.add(event)
    db.session.commit()
    return adoption_dto(req)


def list_my_adoptions(current_user) -> list:
    items = (
        db.session.query(AdoptionRequest)
        .filter_by(applicant_user_id=current_user.id)
        .order_by(AdoptionRequest.id.desc())
        .all()
    )
    return [adoption_dto(r) for r in items]


def list_pet_adoptions(current_user, pet_id: int) -> list:
    pet = get_pet_or_404(pet_id)
    # Apenas responsável ou admin vê candidatos
    if not current_user.is_admin and pet.responsible_user_id != current_user.id:
        if not (pet.responsible_ngo_id and is_active_member(current_user.id, pet.responsible_ngo_id)):
            abort(403)
    items = (
        db.session.query(AdoptionRequest)
        .filter_by(pet_id=pet_id)
        .order_by(AdoptionRequest.id.desc())
        .all()
    )
    return [adoption_dto(r) for r in items]


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #

def _try_complete(req: AdoptionRequest, pet: Pet) -> dict:
    """Conclui adoção se ambas as confirmações existirem."""
    if req.delivery_confirmed_at and req.receipt_confirmed_at:
        now = datetime.now(timezone.utc)
        req.status = "COMPLETED"
        req.completed_at = now
        pet.status = "ADOPTED"
        pet.adopted_at = now
        pet.adopter_user_id = req.applicant_user_id
        pet.version += 1

        event = PetEvent(
            pet_id=pet.id,
            event_type="ADOPTED",
            actor_user_id=req.applicant_user_id,
            acting_ngo_id=req.participating_ngo_id,
            from_status="ADOPTION_PENDING",
            to_status="ADOPTED",
        )
        db.session.add(event)
        db.session.flush()

        # Pontuação de desfecho (só se não houve resgate já pontuado)
        settle_outcome(pet, event, req.participating_ngo_id)

        db.session.commit()

    return adoption_dto(req)


def _get_or_404(adoption_id: int) -> AdoptionRequest:
    r = db.session.get(AdoptionRequest, adoption_id)
    if not r:
        abort(404)
    return r


def _assert_reviewer(user, pet: Pet) -> None:
    if user.is_admin:
        return
    if pet.responsible_user_id == user.id:
        return
    if pet.responsible_ngo_id and is_active_member(user.id, pet.responsible_ngo_id):
        return
    abort(403)


def adoption_dto(req: AdoptionRequest) -> dict:
    return {
        "id": req.id,
        "pet_id": req.pet_id,
        "applicant_user_id": req.applicant_user_id,
        "status": req.status,
        "origin_status": req.origin_status,
        "participating_ngo_id": req.participating_ngo_id,
        "delivery_confirmed_at": req.delivery_confirmed_at.isoformat() if req.delivery_confirmed_at else None,
        "receipt_confirmed_at": req.receipt_confirmed_at.isoformat() if req.receipt_confirmed_at else None,
        "completed_at": req.completed_at.isoformat() if req.completed_at else None,
        "created_at": req.created_at.isoformat(),
    }
