"""Serviço de prêmios — catálogo, troca transacional e uso de voucher."""
from __future__ import annotations

import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from flask import abort, current_app
from marshmallow import Schema, ValidationError, fields

from app import db
from app.admin.models import IdempotencyKey
from app.gamification.models import PointEntry, Wallet
from app.gamification.service import get_or_create_wallet
from app.organizations.service import is_active_member
from app.rewards.models import Partner, PartnerMember, Redemption, Reward


class RewardsError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        self.code = code
        self.message = message
        self.status = status
        super().__init__(message)


class RedeemSchema(Schema):
    reward_id = fields.Int(required=True)
    wallet_id = fields.Int(required=True)
    idempotency_key = fields.Str(required=True)


class ConsumeSchema(Schema):
    voucher_token = fields.Str(required=True)


# --------------------------------------------------------------------------- #
# Catálogo                                                                     #
# --------------------------------------------------------------------------- #

def list_rewards(page: int = 1, per_page: int = 20) -> dict:
    now = datetime.now(timezone.utc)
    q = (
        db.session.query(Reward)
        .filter(
            Reward.active.is_(True),
            Reward.stock > 0,
            db.or_(Reward.starts_at.is_(None), Reward.starts_at <= now),
            db.or_(Reward.ends_at.is_(None), Reward.ends_at >= now),
        )
        .order_by(Reward.id)
    )
    total = q.count()
    items = q.offset((page - 1) * per_page).limit(per_page).all()
    return {
        "items": [reward_dto(r) for r in items],
        "page": page,
        "page_size": per_page,
        "total": total,
    }


# --------------------------------------------------------------------------- #
# Troca transacional                                                           #
# --------------------------------------------------------------------------- #

def redeem_reward(current_user, data: dict) -> dict:
    schema = RedeemSchema()
    try:
        clean = schema.load(data)
    except ValidationError as e:
        raise RewardsError("VALIDATION_ERROR", str(e.messages), 422)

    idem_key = clean["idempotency_key"]
    body_hash = hashlib.sha256(str(sorted(data.items())).encode()).hexdigest()

    # Verifica idempotência
    existing_idem = (
        db.session.query(IdempotencyKey)
        .filter_by(actor_user_id=current_user.id, operation="redeem_reward", key=idem_key)
        .with_for_update()
        .first()
    )
    if existing_idem:
        if existing_idem.request_hash != body_hash:
            raise RewardsError("IDEMPOTENCY_CONFLICT", "Mesma chave com corpo diferente.", 409)
        return existing_idem.response_body

    if not current_user.email_verified:
        raise RewardsError("EMAIL_NOT_VERIFIED", "Verifique seu e-mail.", 403)

    wallet_id = clean["wallet_id"]
    reward_id = clean["reward_id"]

    # Bloqueia carteira ANTES do prêmio (ordem fixa)
    wallet = db.session.query(Wallet).filter_by(id=wallet_id).with_for_update().first()
    if not wallet:
        abort(404)

    # Autorização da carteira
    _assert_wallet_owner(current_user, wallet)

    # Bloqueia prêmio
    reward = db.session.query(Reward).filter_by(id=reward_id).with_for_update().first()
    if not reward:
        abort(404)

    # Valida prêmio
    now = datetime.now(timezone.utc)
    if not reward.active:
        raise RewardsError("REWARD_INACTIVE", "Prêmio inativo.", 409)
    if reward.stock <= 0:
        raise RewardsError("OUT_OF_STOCK", "Estoque esgotado.", 409)
    if reward.ends_at and reward.ends_at < now:
        raise RewardsError("REWARD_EXPIRED", "Prêmio expirado.", 409)
    if reward.starts_at and reward.starts_at > now:
        raise RewardsError("REWARD_NOT_STARTED", "Prêmio ainda não disponível.", 409)

    partner = db.session.get(Partner, reward.partner_id)
    if partner.status != "ACTIVE":
        raise RewardsError("PARTNER_INACTIVE", "Parceiro inativo.", 409)

    # Elegibilidade
    eligibility = reward.eligibility
    is_ngo_wallet = wallet.ngo_id is not None
    if eligibility == "PERSON" and is_ngo_wallet:
        raise RewardsError("NOT_ELIGIBLE", "Prêmio somente para pessoas.", 409)
    if eligibility == "NGO" and not is_ngo_wallet:
        raise RewardsError("NOT_ELIGIBLE", "Prêmio somente para ONGs.", 409)

    # Saldo
    if wallet.balance < reward.cost_points:
        raise RewardsError("INSUFFICIENT_POINTS", "Saldo insuficiente.", 409)

    # Gera voucher: token aleatório → hash para busca + ciphertext para reapresentação
    raw_voucher = secrets.token_urlsafe(32)
    voucher_hash = hashlib.sha256(raw_voucher.encode()).hexdigest()
    voucher_ciphertext = _encrypt_voucher(raw_voucher)
    expires_at = now + timedelta(days=reward.voucher_lifetime_days)

    redemption = Redemption(
        wallet_id=wallet.id,
        reward_id=reward.id,
        cost_snapshot=reward.cost_points,
        terms_snapshot=reward.fulfillment_terms,
        status="ISSUED",
        voucher_hash=voucher_hash,
        voucher_ciphertext=voucher_ciphertext,
        expires_at=expires_at,
    )
    db.session.add(redemption)
    db.session.flush()

    # Debita saldo
    entry_key = f"redemption:{redemption.id}:wallet:{wallet.id}:debit"
    debit = PointEntry(
        wallet_id=wallet.id,
        redemption_id=redemption.id,
        amount=-reward.cost_points,
        kind="REWARD_DEBIT",
        reason=f"Troca por prêmio '{reward.name}' (parceiro {partner.name})",
        entry_key=entry_key,
    )
    db.session.add(debit)
    wallet.balance -= reward.cost_points
    reward.stock -= 1
    db.session.flush()

    dto = redemption_dto(redemption, include_voucher=True)

    # Persiste idempotência
    idem = IdempotencyKey(
        actor_user_id=current_user.id,
        operation="redeem_reward",
        key=idem_key,
        request_hash=body_hash,
        response_status=201,
        response_body=dto,
        expires_at=now + timedelta(days=7),
    )
    db.session.add(idem)
    db.session.commit()
    return dto


def consume_voucher(current_user, data: dict) -> dict:
    """Parceiro consome voucher — uso único."""
    schema = ConsumeSchema()
    try:
        clean = schema.load(data)
    except ValidationError as e:
        raise RewardsError("VALIDATION_ERROR", str(e.messages), 422)

    voucher_hash = hashlib.sha256(clean["voucher_token"].encode()).hexdigest()
    redemption = (
        db.session.query(Redemption)
        .filter_by(voucher_hash=voucher_hash)
        .with_for_update()
        .first()
    )
    if not redemption:
        raise RewardsError("VOUCHER_NOT_FOUND", "Voucher não encontrado.", 404)

    # Verifica que o usuário é membro do parceiro correto
    reward = db.session.get(Reward, redemption.reward_id)
    if not is_active_member(current_user.id, reward.partner_id) and not current_user.is_admin:
        abort(403)

    now = datetime.now(timezone.utc)
    if redemption.status != "ISSUED":
        raise RewardsError("VOUCHER_NOT_VALID", f"Voucher em estado: {redemption.status}.", 409)
    if redemption.expires_at < now:
        raise RewardsError("VOUCHER_EXPIRED", "Voucher expirado.", 409)

    redemption.status = "USED"
    redemption.consumed_at = now
    redemption.consumed_by = current_user.id
    db.session.commit()
    return redemption_dto(redemption)


def cancel_redemption(admin_user, redemption_id: int, reason: str) -> dict:
    """Admin cancela voucher não utilizado com devolução de pontos e estoque."""
    redemption = (
        db.session.query(Redemption)
        .filter_by(id=redemption_id)
        .with_for_update()
        .first()
    )
    if not redemption:
        abort(404)
    if redemption.status != "ISSUED":
        raise RewardsError("CANNOT_CANCEL", f"Voucher em estado: {redemption.status}.", 409)

    now = datetime.now(timezone.utc)
    if redemption.expires_at < now:
        raise RewardsError("ALREADY_EXPIRED", "Voucher já expirado.", 409)

    redemption.status = "CANCELLED"

    wallet = db.session.query(Wallet).filter_by(id=redemption.wallet_id).with_for_update().first()
    reward = db.session.query(Reward).filter_by(id=redemption.reward_id).with_for_update().first()

    refund_key = f"redemption:{redemption.id}:wallet:{wallet.id}:refund"
    refund = PointEntry(
        wallet_id=wallet.id,
        redemption_id=redemption.id,
        amount=redemption.cost_snapshot,
        kind="REFUND",
        reason=f"Cancelamento voucher #{redemption.id}: {reason}",
        entry_key=refund_key,
    )
    db.session.add(refund)
    wallet.balance += redemption.cost_snapshot
    reward.stock += 1
    db.session.commit()
    return redemption_dto(redemption)


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #

def _encrypt_voucher(raw: str) -> str:
    """Criptografia simples para o MVP — Fernet via chave de ambiente."""
    try:
        from cryptography.fernet import Fernet
        key_b64 = current_app.config.get("VOUCHER_ENCRYPTION_KEY", "")
        if not key_b64:
            # Desenvolvimento: armazena texto plano com prefixo
            return f"PLAIN:{raw}"
        key = base64.urlsafe_b64decode(key_b64.encode())
        # Fernet exige 32 bytes codificados em url-safe base64
        fernet_key = base64.urlsafe_b64encode(key[:32])
        f = Fernet(fernet_key)
        return f.encrypt(raw.encode()).decode()
    except Exception:
        return f"PLAIN:{raw}"


def _assert_wallet_owner(user, wallet: Wallet) -> None:
    if user.is_admin:
        return
    if wallet.user_id and wallet.user_id == user.id:
        return
    if wallet.ngo_id and is_active_member(user.id, wallet.ngo_id):
        return
    abort(403)


def reward_dto(r: Reward) -> dict:
    return {
        "id": r.id,
        "partner_id": r.partner_id,
        "name": r.name,
        "description": r.description,
        "cost_points": r.cost_points,
        "stock": r.stock,
        "starts_at": r.starts_at.isoformat() if r.starts_at else None,
        "ends_at": r.ends_at.isoformat() if r.ends_at else None,
        "eligibility": r.eligibility,
        "fulfillment_terms": r.fulfillment_terms,
    }


def redemption_dto(r: Redemption, include_voucher: bool = False) -> dict:
    d = {
        "id": r.id,
        "reward_id": r.reward_id,
        "wallet_id": r.wallet_id,
        "cost_snapshot": r.cost_snapshot,
        "status": r.status,
        "expires_at": r.expires_at.isoformat(),
        "consumed_at": r.consumed_at.isoformat() if r.consumed_at else None,
        "created_at": r.created_at.isoformat(),
    }
    if include_voucher:
        d["voucher_ciphertext"] = r.voucher_ciphertext
    return d
