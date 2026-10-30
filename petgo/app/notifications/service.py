"""Serviço de notificações — outbox + e-mail."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from app import db
from app.notifications.models import OutboxEvent


def _enqueue(event_type: str, payload: dict) -> OutboxEvent:
    """Cria evento na outbox dentro da transação corrente."""
    key = f"{event_type}:{uuid.uuid4()}"
    event = OutboxEvent(
        event_key=key,
        type=event_type,
        payload=payload,
        status="PENDING",
        next_attempt_at=datetime.now(timezone.utc),
    )
    db.session.add(event)
    return event


def enqueue_email_verification(user_id: int, token: str) -> OutboxEvent:
    return _enqueue("EMAIL_VERIFICATION", {"user_id": user_id, "token": token})


def enqueue_password_reset(user_id: int, token: str) -> OutboxEvent:
    return _enqueue("PASSWORD_RESET", {"user_id": user_id, "token": token})


def enqueue_pet_published(pet_id: int, publisher_id: int) -> OutboxEvent:
    return _enqueue("PET_PUBLISHED", {"pet_id": pet_id, "publisher_id": publisher_id})


def enqueue_pet_available(pet_id: int) -> OutboxEvent:
    return _enqueue("PET_AVAILABLE", {"pet_id": pet_id})


def enqueue_rescue_assumed(pet_id: int, ngo_id: int, publisher_id: int) -> OutboxEvent:
    return _enqueue(
        "RESCUE_ASSUMED",
        {"pet_id": pet_id, "ngo_id": ngo_id, "publisher_id": publisher_id},
    )


def enqueue_rescue_confirmed(pet_id: int, rescue_id: int) -> OutboxEvent:
    return _enqueue("RESCUE_CONFIRMED", {"pet_id": pet_id, "rescue_id": rescue_id})


def enqueue_adoption_decision(adoption_id: int, status: str) -> OutboxEvent:
    return _enqueue("ADOPTION_DECISION", {"adoption_id": adoption_id, "status": status})
