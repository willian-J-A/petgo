"""Worker PetGo — processa outbox, envia e-mails e expira vouchers.

Supervisionado por systemd (R10). Nunca rodar dentro do processo Flask.
Uso:
    python -m worker.worker
"""
from __future__ import annotations

import logging
import os
import signal
import smtplib
import time
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from dotenv import load_dotenv

load_dotenv(override=False)

from app import create_app, db  # noqa: E402
from app.notifications.models import EmailDelivery, OutboxEvent  # noqa: E402
from app.rewards.models import Redemption  # noqa: E402

logger = logging.getLogger("petgo.worker")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

LEASE_SECONDS = 120
MAX_ATTEMPTS = 5
RETRY_DELAYS = [60, 300, 900, 3600, 14400]  # segundos entre tentativas

_running = True


def _handle_sigterm(*_):
    global _running
    logger.info("SIGTERM recebido — encerrando loop.")
    _running = False


signal.signal(signal.SIGTERM, _handle_sigterm)
signal.signal(signal.SIGINT, _handle_sigterm)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- #
# Loop principal                                                               #
# --------------------------------------------------------------------------- #

def run() -> None:
    app = create_app(os.getenv("APP_ENV", "development"))
    logger.info("Worker iniciado.")

    with app.app_context():
        while _running:
            try:
                _process_outbox()
                _send_pending_emails()
                _expire_vouchers()
            except Exception:
                logger.exception("Erro no ciclo do worker")
            time.sleep(10)

    logger.info("Worker encerrado.")


# --------------------------------------------------------------------------- #
# Outbox                                                                       #
# --------------------------------------------------------------------------- #

def _process_outbox() -> None:
    now = _now()
    events = (
        db.session.query(OutboxEvent)
        .filter(
            OutboxEvent.status == "PENDING",
            db.or_(OutboxEvent.next_attempt_at.is_(None), OutboxEvent.next_attempt_at <= now),
            db.or_(OutboxEvent.lease_until.is_(None), OutboxEvent.lease_until < now),
        )
        .with_for_update(skip_locked=True)
        .limit(20)
        .all()
    )

    for event in events:
        event.lease_until = now + timedelta(seconds=LEASE_SECONDS)
        event.status = "PROCESSING"
        db.session.commit()

        try:
            _expand_recipients(event)
            event.status = "DONE"
        except Exception as e:
            event.status = "PENDING"
            event.attempts += 1
            if event.attempts >= MAX_ATTEMPTS:
                event.status = "FAILED"
            else:
                delay = RETRY_DELAYS[min(event.attempts - 1, len(RETRY_DELAYS) - 1)]
                event.next_attempt_at = now + timedelta(seconds=delay)
        finally:
            event.lease_until = None
            db.session.commit()


def _expand_recipients(event: OutboxEvent) -> None:
    """Cria EmailDelivery para cada destinatário adequado ao tipo de evento."""
    from app.auth.models import User
    from app.organizations.models import NgoMember

    etype = event.type
    payload = event.payload

    recipients: list[User] = []

    if etype in ("EMAIL_VERIFICATION", "PASSWORD_RESET"):
        user = db.session.get(User, payload["user_id"])
        if user:
            recipients = [user]

    elif etype == "PET_PUBLISHED":
        pet_id = payload["pet_id"]
        from app.pets.models import Pet
        pet = db.session.get(Pet, pet_id)
        if not pet:
            return

        # ONGs aprovadas
        from app.organizations.models import Ngo
        ngos = db.session.query(Ngo).filter_by(verification_status="APPROVED").all()
        ngo_user_ids = set()
        for ngo in ngos:
            members = db.session.query(NgoMember).filter_by(ngo_id=ngo.id, active=True).all()
            ngo_user_ids.update(m.user_id for m in members)

        # Pessoas interessadas em adoção
        interested = (
            db.session.query(User)
            .filter(
                User.interested_in_adoption.is_(True),
                User.email_opt_in.is_(True),
                User.email_verified_at.isnot(None),
                User.is_active.is_(True),
            )
            .all()
        )
        for u in interested:
            if u.all_locations or u.city == pet.city:
                if not u.species_preferences or pet.species in u.species_preferences:
                    recipients.append(u)

        ngo_users = db.session.query(User).filter(User.id.in_(ngo_user_ids)).all()
        recipients.extend(ngo_users)

    template_map = {
        "EMAIL_VERIFICATION": "email_verification",
        "PASSWORD_RESET": "password_reset",
        "PET_PUBLISHED": "pet_published",
        "PET_AVAILABLE": "pet_available",
        "RESCUE_ASSUMED": "rescue_assumed",
        "RESCUE_CONFIRMED": "rescue_confirmed",
        "ADOPTION_DECISION": "adoption_decision",
    }
    template = template_map.get(etype, etype.lower())

    seen: set[int] = set()
    for user in recipients:
        if user.id in seen:
            continue
        seen.add(user.id)

        existing = (
            db.session.query(EmailDelivery)
            .filter_by(event_id=event.id, user_id=user.id, template=template)
            .first()
        )
        if existing:
            continue

        delivery = EmailDelivery(
            event_id=event.id,
            user_id=user.id,
            recipient_email_snapshot=user.email_normalized,
            template=template,
            status="PENDING",
            next_attempt_at=_now(),
        )
        db.session.add(delivery)

    db.session.commit()


# --------------------------------------------------------------------------- #
# Envio de e-mails                                                             #
# --------------------------------------------------------------------------- #

def _send_pending_emails() -> None:
    from app import create_app
    from flask import current_app

    now = _now()
    deliveries = (
        db.session.query(EmailDelivery)
        .filter(
            EmailDelivery.status == "PENDING",
            db.or_(EmailDelivery.next_attempt_at.is_(None), EmailDelivery.next_attempt_at <= now),
            db.or_(EmailDelivery.lease_until.is_(None), EmailDelivery.lease_until < now),
        )
        .with_for_update(skip_locked=True)
        .limit(20)
        .all()
    )

    for delivery in deliveries:
        # Revalida consentimento antes de enviar
        from app.auth.models import User
        user = db.session.get(User, delivery.user_id)
        if not user or not user.is_active or not user.email_opt_in:
            delivery.status = "CANCELLED"
            db.session.commit()
            continue
        if user.email_normalized != delivery.recipient_email_snapshot:
            delivery.status = "CANCELLED"
            db.session.commit()
            continue

        delivery.lease_until = now + timedelta(seconds=LEASE_SECONDS)
        db.session.commit()

        try:
            event = db.session.get(OutboxEvent, delivery.event_id)
            _send_email(
                to=delivery.recipient_email_snapshot,
                template=delivery.template,
                payload=event.payload if event else {},
            )
            delivery.status = "ACCEPTED_BY_PROVIDER"
            delivery.attempts += 1
        except Exception as e:
            delivery.attempts += 1
            sanitized = str(e)[:200]
            delivery.sanitized_error = sanitized
            if delivery.attempts >= MAX_ATTEMPTS:
                delivery.status = "FAILED"
                logger.error("Entrega permanentemente falhou: %s", delivery.id)
            else:
                delay = RETRY_DELAYS[min(delivery.attempts - 1, len(RETRY_DELAYS) - 1)]
                delivery.next_attempt_at = now + timedelta(seconds=delay)
        finally:
            delivery.lease_until = None
            db.session.commit()


def _send_email(to: str, template: str, payload: dict) -> None:
    """Envia via SMTP autenticado."""
    from flask import current_app as app

    host = app.config.get("SMTP_HOST", "")
    if not host:
        logger.debug("SMTP não configurado; e-mail simulado para %s (%s)", to, template)
        return

    port = app.config.get("SMTP_PORT", 587)
    username = app.config.get("SMTP_USERNAME", "")
    password = app.config.get("SMTP_PASSWORD", "")
    sender = app.config.get("EMAIL_FROM", "noreply@petgo.local")

    msg = EmailMessage()
    msg["Subject"] = _subject(template, payload)
    msg["From"] = sender
    msg["To"] = to
    msg.set_content(_body(template, payload))

    with smtplib.SMTP(host, port, timeout=15) as s:
        s.starttls()
        if username:
            s.login(username, password)
        s.send_message(msg)


def _subject(template: str, payload: dict) -> str:
    subjects = {
        "email_verification": "PetGo — Verifique seu e-mail",
        "password_reset": "PetGo — Redefinição de senha",
        "pet_published": "PetGo — Novo animal precisa de ajuda",
        "pet_available": "PetGo — Animal disponível para adoção",
        "rescue_assumed": "PetGo — Atendimento iniciado",
        "rescue_confirmed": "PetGo — Resgate confirmado",
        "adoption_decision": "PetGo — Atualização do seu pedido",
    }
    return subjects.get(template, "PetGo — Notificação")


def _body(template: str, payload: dict) -> str:
    base_url = os.getenv("PUBLIC_BASE_URL", "http://localhost:5000")
    if template == "email_verification":
        token = payload.get("token", "")
        return f"Clique para verificar: {base_url}/auth/verify-email?token={token}"
    if template == "password_reset":
        token = payload.get("token", "")
        return f"Clique para redefinir a senha: {base_url}/auth/reset-password?token={token}"
    return "Acesse o PetGo para mais informações."


# --------------------------------------------------------------------------- #
# Expiração de vouchers                                                        #
# --------------------------------------------------------------------------- #

def _expire_vouchers() -> None:
    now = _now()
    expired = (
        db.session.query(Redemption)
        .filter(
            Redemption.status == "ISSUED",
            Redemption.expires_at < now,
        )
        .with_for_update(skip_locked=True)
        .limit(50)
        .all()
    )

    for r in expired:
        from app.gamification.models import PointEntry, Wallet
        wallet = db.session.query(Wallet).filter_by(id=r.wallet_id).with_for_update().first()
        from app.rewards.models import Reward
        reward = db.session.query(Reward).filter_by(id=r.reward_id).with_for_update().first()

        refund_key = f"redemption:{r.id}:wallet:{r.wallet_id}:expiry_refund"
        existing = db.session.query(PointEntry).filter_by(entry_key=refund_key).first()
        if existing:
            r.status = "EXPIRED"
            db.session.commit()
            continue

        r.status = "EXPIRED"
        refund = PointEntry(
            wallet_id=wallet.id,
            redemption_id=r.id,
            amount=r.cost_snapshot,
            kind="REFUND",
            reason=f"Expiração automática voucher #{r.id}",
            entry_key=refund_key,
        )
        db.session.add(refund)
        wallet.balance += r.cost_snapshot
        reward.stock += 1
        db.session.commit()
        logger.info("Voucher %s expirado — pontos devolvidos.", r.id)


if __name__ == "__main__":
    run()
