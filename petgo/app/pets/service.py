"""Serviço de pets — publicação, consulta, mídia e histórico."""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

from flask import abort, current_app
from marshmallow import ValidationError
from sqlalchemy import select

from app import db
from app.admin.models import IdempotencyKey
from app.gamification.service import credit_publication
from app.notifications.service import enqueue_pet_published
from app.organizations.service import is_active_member
from app.pets.models import Media, Pet, PetEvent
from app.pets.schemas import CreatePetSchema, PetFilterSchema, UpdatePetSchema


class PetError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        self.code = code
        self.message = message
        self.status = status
        super().__init__(message)


# --------------------------------------------------------------------------- #
# Idempotência                                                                 #
# --------------------------------------------------------------------------- #

def _check_idempotency(user_id: int, operation: str, key: str, body_hash: str):
    """Retorna resposta cacheada se existir, ou None."""
    record = (
        db.session.query(IdempotencyKey)
        .filter_by(actor_user_id=user_id, operation=operation, key=key)
        .with_for_update()
        .first()
    )
    if not record:
        return None
    if record.request_hash != body_hash:
        raise PetError("IDEMPOTENCY_CONFLICT", "Mesma chave com corpo diferente.", 409)
    return record.response_body


def _save_idempotency(user_id: int, operation: str, key: str, body_hash: str,
                      status: int, body: dict, ttl_days: int = 7):
    from datetime import timedelta
    record = IdempotencyKey(
        actor_user_id=user_id,
        operation=operation,
        key=key,
        request_hash=body_hash,
        response_status=status,
        response_body=body,
        expires_at=datetime.now(timezone.utc) + timedelta(days=ttl_days),
    )
    db.session.add(record)


# --------------------------------------------------------------------------- #
# Publicação                                                                   #
# --------------------------------------------------------------------------- #

def create_pet(current_user, data: dict, idempotency_key: str | None = None) -> dict:
    """Cria pet transacionalmente com crédito de +5 e outbox."""
    if not current_user.email_verified:
        raise PetError("EMAIL_NOT_VERIFIED", "Verifique seu e-mail antes de publicar.", 403)

    schema = CreatePetSchema()
    try:
        clean = schema.load(data)
    except ValidationError as e:
        raise PetError("VALIDATION_ERROR", str(e.messages), 422)

    body_hash = hashlib.sha256(str(sorted(data.items())).encode()).hexdigest()

    # --- início da transação ---
    if idempotency_key:
        cached = _check_idempotency(current_user.id, "create_pet", idempotency_key, body_hash)
        if cached:
            return cached

    # Valida mídia
    media_ids = clean["media_ids"]
    medias = (
        db.session.query(Media)
        .filter(Media.id.in_(media_ids), Media.uploaded_by == current_user.id,
                Media.pet_id.is_(None))
        .all()
    )
    if len(medias) != len(media_ids):
        raise PetError("INVALID_MEDIA", "Um ou mais media_ids inválidos ou já utilizados.", 422)

    # Valida ONG (opcional)
    ngo_id = clean.get("ngo_id")
    if ngo_id and not is_active_member(current_user.id, ngo_id):
        raise PetError("NOT_NGO_MEMBER", "Você não é membro ativo desta ONG.", 403)

    # Estado inicial por tipo de ajuda
    initial_status_map = {
        "RESCUE": "NEEDS_RESCUE",
        "ADOPTION": "AVAILABLE",
        "TREATMENT": "SHELTERED",
        "FOSTER": "SHELTERED",
    }
    status = initial_status_map[clean["help_type"]]

    private_loc = None
    if clean.get("latitude") is not None and clean.get("longitude") is not None:
        private_loc = {"latitude": clean["latitude"], "longitude": clean["longitude"]}

    pet = Pet(
        publisher_user_id=current_user.id,
        responsible_user_id=current_user.id if not ngo_id else None,
        responsible_ngo_id=ngo_id,
        species=clean["species"],
        size=clean.get("size"),
        sex=clean.get("sex"),
        age_months=clean.get("age_months"),
        help_type=clean["help_type"],
        status=status,
        description=clean["description"],
        city=clean["city"],
        state=clean["state"].upper(),
        private_location=private_loc,
        risk_status="PENDING" if clean.get("risk_reported") else "NONE",
        risk_details=clean.get("risk_description"),
    )
    db.session.add(pet)
    db.session.flush()

    # Vincula mídia ao pet
    for m in medias:
        m.pet_id = pet.id

    # Evento de publicação
    event = PetEvent(
        pet_id=pet.id,
        event_type="PUBLICATION",
        actor_user_id=current_user.id,
        acting_ngo_id=ngo_id,
        from_status=None,
        to_status=status,
    )
    db.session.add(event)
    db.session.flush()

    # Crédito +5 ao publicador (dentro da mesma transação)
    credit_publication(pet, event, current_user.id)

    # Outbox
    enqueue_pet_published(pet.id, current_user.id)

    dto = pet_public_dto(pet)

    if idempotency_key:
        _save_idempotency(current_user.id, "create_pet", idempotency_key, body_hash, 201, dto)

    db.session.commit()
    return dto


# --------------------------------------------------------------------------- #
# Consulta                                                                     #
# --------------------------------------------------------------------------- #

def list_rescue_pets(filters: dict):
    schema = PetFilterSchema()
    f = schema.load(filters)
    q = db.session.query(Pet).filter(
        Pet.status.in_(["NEEDS_RESCUE", "IN_RESCUE"]),
        Pet.deleted_at.is_(None),
    )
    q = _apply_filters(q, f)
    total = q.count()
    items = q.order_by(Pet.id.desc()).offset((f["page"] - 1) * f["page_size"]).limit(f["page_size"]).all()
    return [pet_public_dto(p) for p in items], total, f["page"], f["page_size"]


def list_adoption_pets(filters: dict):
    schema = PetFilterSchema()
    f = schema.load(filters)
    q = db.session.query(Pet).filter(
        Pet.status == "AVAILABLE",
        Pet.deleted_at.is_(None),
    )
    q = _apply_filters(q, f)
    total = q.count()
    items = q.order_by(Pet.id.desc()).offset((f["page"] - 1) * f["page_size"]).limit(f["page_size"]).all()
    return [pet_public_dto(p) for p in items], total, f["page"], f["page_size"]


def _apply_filters(q, f):
    if f.get("species"):
        q = q.filter(Pet.species == f["species"])
    if f.get("size"):
        q = q.filter(Pet.size == f["size"])
    if f.get("sex"):
        q = q.filter(Pet.sex == f["sex"])
    if f.get("city"):
        q = q.filter(Pet.city.ilike(f["city"]))
    if f.get("state"):
        q = q.filter(Pet.state == f["state"].upper())
    if f.get("help_type"):
        q = q.filter(Pet.help_type == f["help_type"])
    if f.get("risk_validated") is True:
        q = q.filter(Pet.risk_status == "APPROVED")
    return q


def get_pet_or_404(pet_id: int) -> Pet:
    pet = db.session.get(Pet, pet_id)
    if not pet or pet.deleted_at:
        abort(404)
    return pet


def update_pet(current_user, pet_id: int, data: dict) -> dict:
    pet = get_pet_or_404(pet_id)
    _assert_responsible(current_user, pet)

    schema = UpdatePetSchema()
    try:
        clean = schema.load(data)
    except ValidationError as e:
        raise PetError("VALIDATION_ERROR", str(e.messages), 422)

    forbidden = {"status", "risk_status", "publisher_user_id", "responsible_ngo_id", "adopter_user_id"}
    for k in forbidden:
        clean.pop(k, None)

    for k, v in clean.items():
        setattr(pet, k, v)

    db.session.commit()
    return pet_public_dto(pet)


def delete_pet(current_user, pet_id: int) -> None:
    """Exclusão lógica."""
    pet = get_pet_or_404(pet_id)
    _assert_responsible(current_user, pet)
    pet.deleted_at = datetime.now(timezone.utc)
    db.session.commit()


def mark_available(current_user, pet_id: int) -> dict:
    """SHELTERED → AVAILABLE."""
    pet = get_pet_or_404(pet_id)
    _assert_responsible(current_user, pet)
    if pet.status != "SHELTERED":
        raise PetError("INVALID_STATUS", "Pet deve estar SHELTERED para marcar como disponível.", 409)

    pet.status = "AVAILABLE"
    pet.version += 1
    event = PetEvent(
        pet_id=pet.id,
        event_type="AVAILABILITY_DECLARED",
        actor_user_id=current_user.id,
        from_status="SHELTERED",
        to_status="AVAILABLE",
    )
    db.session.add(event)

    from app.notifications.service import enqueue_pet_available
    enqueue_pet_available(pet.id)
    db.session.commit()
    return pet_public_dto(pet)


def report_risk(current_user, pet_id: int, data: dict) -> dict:
    pet = get_pet_or_404(pet_id)
    if pet.risk_status not in ("NONE",):
        raise PetError("RISK_ALREADY_REPORTED", "Risco já relatado.", 409)
    pet.risk_status = "PENDING"
    pet.risk_details = data.get("description", "")
    db.session.commit()
    return pet_public_dto(pet)


# --------------------------------------------------------------------------- #
# Upload de mídia                                                              #
# --------------------------------------------------------------------------- #

def register_media(current_user, storage_key: str, content_type: str,
                   size_bytes: int, purpose: str = "PHOTO") -> Media:
    allowed_types = current_app.config.get(
        "ALLOWED_MEDIA_MIMETYPES", {"image/jpeg", "image/png", "image/webp"}
    )
    if content_type not in allowed_types:
        raise PetError("INVALID_MEDIA_TYPE", "Tipo de mídia não permitido.", 415)

    media = Media(
        storage_key=storage_key,
        content_type=content_type,
        size_bytes=size_bytes,
        purpose=purpose,
        visibility="PRIVATE",
        uploaded_by=current_user.id,
    )
    db.session.add(media)
    db.session.commit()
    return media


# --------------------------------------------------------------------------- #
# DTOs                                                                         #
# --------------------------------------------------------------------------- #

def pet_public_dto(pet: Pet) -> dict:
    """DTO público — sem localização precisa ou dados privados."""
    return {
        "id": pet.id,
        "species": pet.species,
        "size": pet.size,
        "sex": pet.sex,
        "age_months": pet.age_months,
        "help_type": pet.help_type,
        "status": pet.status,
        "description": pet.description,
        "city": pet.city,
        "state": pet.state,
        "risk_status": pet.risk_status,
        "publisher_user_id": pet.publisher_user_id,
        "responsible_user_id": pet.responsible_user_id,
        "responsible_ngo_id": pet.responsible_ngo_id,
        "rescued_at": pet.rescued_at.isoformat() if pet.rescued_at else None,
        "adopted_at": pet.adopted_at.isoformat() if pet.adopted_at else None,
        "created_at": pet.created_at.isoformat(),
        "updated_at": pet.updated_at.isoformat(),
        # localização precisa omitida — disponível via endpoint autenticado separado
    }


def pet_private_dto(pet: Pet) -> dict:
    """DTO privado para atores autorizados."""
    base = pet_public_dto(pet)
    base["private_location"] = pet.private_location
    return base


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #

def _assert_responsible(user, pet: Pet) -> None:
    if user.is_admin:
        return
    is_responsible_user = pet.responsible_user_id == user.id
    is_responsible_ngo = (
        pet.responsible_ngo_id is not None and
        is_active_member(user.id, pet.responsible_ngo_id)
    )
    if not (is_responsible_user or is_responsible_ngo):
        abort(403)
