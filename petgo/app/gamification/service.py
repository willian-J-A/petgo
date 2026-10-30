"""Serviço de gamificação — carteiras, política v1 e lançamentos imutáveis."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from flask import abort

from app import db
from app.gamification.models import PointAward, PointEntry, Wallet
from app.pets.models import Pet, PetEvent

# --------------------------------------------------------------------------- #
# Política v1 — valores em pontos                                              #
# --------------------------------------------------------------------------- #
POLICY_VERSION = "v1"

PUBLICATION_CREDIT = 5

OUTCOME_NORMAL_PUBLISHER = 10
OUTCOME_NORMAL_NGO = 15

OUTCOME_RISK_PUBLISHER = 20
OUTCOME_RISK_NGO = 40


# --------------------------------------------------------------------------- #
# Carteiras                                                                    #
# --------------------------------------------------------------------------- #

def get_or_create_wallet(user_id: int | None = None, ngo_id: int | None = None) -> Wallet:
    """Obtém ou cria carteira para user ou ngo (exatamente um)."""
    assert bool(user_id) ^ bool(ngo_id), "Exatamente um titular obrigatório."

    if user_id:
        w = db.session.query(Wallet).filter_by(user_id=user_id).with_for_update().first()
        if not w:
            w = Wallet(user_id=user_id, balance=0)
            db.session.add(w)
            db.session.flush()
    else:
        w = db.session.query(Wallet).filter_by(ngo_id=ngo_id).with_for_update().first()
        if not w:
            w = Wallet(ngo_id=ngo_id, balance=0)
            db.session.add(w)
            db.session.flush()
    return w


def _credit(wallet: Wallet, amount: int, kind: str, reason: str, entry_key: str,
            award_id: int | None = None) -> PointEntry:
    """Lançamento imutável de crédito com chave única."""
    entry = PointEntry(
        wallet_id=wallet.id,
        award_id=award_id,
        amount=amount,
        kind=kind,
        reason=reason,
        entry_key=entry_key,
    )
    db.session.add(entry)
    wallet.balance += amount
    db.session.flush()
    return entry


# --------------------------------------------------------------------------- #
# Crédito de publicação (+5)                                                   #
# --------------------------------------------------------------------------- #

def credit_publication(pet: Pet, event: PetEvent, publisher_user_id: int) -> PointAward:
    """Cria PointAward PUBLICATION e credita +5 ao publicador (dentro da transação)."""
    award = PointAward(
        pet_id=pet.id,
        phase="PUBLICATION",
        event_id=event.id,
        risk_snapshot="NONE",
        policy_version=POLICY_VERSION,
        status="SETTLED",
    )
    db.session.add(award)
    db.session.flush()

    wallet = get_or_create_wallet(user_id=publisher_user_id)
    _credit(
        wallet=wallet,
        amount=PUBLICATION_CREDIT,
        kind="PUBLICATION_CREDIT",
        reason=f"Publicação do pet #{pet.id}",
        entry_key=f"award:{award.id}:wallet:{wallet.id}:pub_credit",
        award_id=award.id,
    )
    return award


# --------------------------------------------------------------------------- #
# Desfecho — resgate ou adoção direta                                          #
# --------------------------------------------------------------------------- #

def settle_outcome(pet: Pet, event: PetEvent, ngo_id: int | None) -> PointAward | None:
    """Cria ou atualiza PointAward OUTCOME.

    Se risco pendente → WAITING_RISK (sem crédito).
    Se risco decidido → SETTLED com os valores corretos.
    Se adoção após resgate já pontuado → ignora.
    """
    # Verifica se já existe award OUTCOME (adoção após resgate pontuado)
    existing = (
        db.session.query(PointAward)
        .filter_by(pet_id=pet.id, phase="OUTCOME")
        .first()
    )
    if existing and existing.status == "SETTLED":
        # Desfecho já liquidado — adoção posterior não pontua
        return existing

    risk = pet.risk_status  # NONE | PENDING | APPROVED | REJECTED

    if risk == "PENDING":
        # Aguarda decisão
        if not existing:
            award = PointAward(
                pet_id=pet.id,
                phase="OUTCOME",
                event_id=event.id,
                risk_snapshot="PENDING",
                policy_version=POLICY_VERSION,
                status="WAITING_RISK",
            )
            db.session.add(award)
            db.session.flush()
        return existing or award  # type: ignore[return-value]

    # Risco decidido (NONE, APPROVED, REJECTED) ou sem risco
    if existing and existing.status == "WAITING_RISK":
        award = existing
        award.risk_snapshot = risk
        award.status = "SETTLED"
        db.session.flush()
    elif not existing:
        award = PointAward(
            pet_id=pet.id,
            phase="OUTCOME",
            event_id=event.id,
            risk_snapshot=risk,
            policy_version=POLICY_VERSION,
            status="SETTLED",
        )
        db.session.add(award)
        db.session.flush()
    else:
        return existing

    _settle_credits(pet, award, ngo_id)
    return award


def settle_waiting_risk(pet: Pet, event: PetEvent) -> None:
    """Chamado quando admin decide risco — liquida WAITING_RISK se existir."""
    award = (
        db.session.query(PointAward)
        .filter_by(pet_id=pet.id, phase="OUTCOME", status="WAITING_RISK")
        .with_for_update()
        .first()
    )
    if not award:
        return  # Desfecho ainda não ocorreu ou já liquidado

    award.risk_snapshot = pet.risk_status
    award.status = "SETTLED"
    db.session.flush()

    # Descobre ngo_id do desfecho (resgate ou adoção)
    from app.rescues.models import Rescue
    rescue = (
        db.session.query(Rescue)
        .filter_by(pet_id=pet.id, status="CONFIRMED")
        .first()
    )
    ngo_id = rescue.ngo_id if rescue else None
    _settle_credits(pet, award, ngo_id)


def _settle_credits(pet: Pet, award: PointAward, ngo_id: int | None) -> None:
    """Credita pontos de desfecho de acordo com a política v1."""
    risk_approved = award.risk_snapshot == "APPROVED"
    publisher_credit = OUTCOME_RISK_PUBLISHER if risk_approved else OUTCOME_NORMAL_PUBLISHER
    ngo_credit = OUTCOME_RISK_NGO if risk_approved else OUTCOME_NORMAL_NGO

    # Bloqueia carteiras em ordem crescente de ID para evitar deadlock
    pub_wallet = get_or_create_wallet(user_id=pet.publisher_user_id)
    ngo_wallet = get_or_create_wallet(ngo_id=ngo_id) if ngo_id else None

    wallets = sorted(
        filter(None, [pub_wallet, ngo_wallet]), key=lambda w: w.id
    )
    for w in wallets:
        db.session.refresh(w)  # re-lock na ordem correta

    # Crédito ao publicador
    _credit(
        wallet=pub_wallet,
        amount=publisher_credit,
        kind="OUTCOME_CREDIT",
        reason=f"Desfecho pet #{pet.id} — risco={'aprovado' if risk_approved else 'normal'}",
        entry_key=f"award:{award.id}:wallet:{pub_wallet.id}:outcome_credit",
        award_id=award.id,
    )

    # Crédito à ONG (se elegível)
    if ngo_wallet:
        _credit(
            wallet=ngo_wallet,
            amount=ngo_credit,
            kind="OUTCOME_CREDIT",
            reason=f"Desfecho ONG pet #{pet.id} — risco={'aprovado' if risk_approved else 'normal'}",
            entry_key=f"award:{award.id}:wallet:{ngo_wallet.id}:outcome_credit",
            award_id=award.id,
        )


# --------------------------------------------------------------------------- #
# Consulta de carteira                                                         #
# --------------------------------------------------------------------------- #

def get_user_wallet(user_id: int) -> dict:
    w = db.session.query(Wallet).filter_by(user_id=user_id).first()
    if not w:
        return {"balance": 0, "wallet_id": None}
    return {"balance": w.balance, "wallet_id": w.id}


def get_ngo_wallet(ngo_id: int) -> dict:
    w = db.session.query(Wallet).filter_by(ngo_id=ngo_id).first()
    if not w:
        return {"balance": 0, "wallet_id": None}
    return {"balance": w.balance, "wallet_id": w.id}


def get_wallet_entries(wallet_id: int, page: int = 1, per_page: int = 20) -> dict:
    w = db.session.get(Wallet, wallet_id)
    if not w:
        abort(404)
    q = db.session.query(PointEntry).filter_by(wallet_id=wallet_id).order_by(PointEntry.id.desc())
    total = q.count()
    items = q.offset((page - 1) * per_page).limit(per_page).all()
    return {
        "items": [entry_dto(e) for e in items],
        "page": page,
        "page_size": per_page,
        "total": total,
    }


def entry_dto(e: PointEntry) -> dict:
    return {
        "id": e.id,
        "amount": e.amount,
        "kind": e.kind,
        "reason": e.reason,
        "award_id": e.award_id,
        "redemption_id": e.redemption_id,
        "created_at": e.created_at.isoformat(),
    }


# --------------------------------------------------------------------------- #
# Estorno administrativo                                                       #
# --------------------------------------------------------------------------- #

def reverse_award(admin_user, award_id: int, reason: str) -> PointAward:
    """Estorno motivado — lançamentos compensatórios, saldo pode ficar negativo."""
    award = db.session.get(PointAward, award_id)
    if not award or award.status == "REVERSED":
        abort(404)

    entries = db.session.query(PointEntry).filter_by(award_id=award_id).all()
    for entry in entries:
        wallet = db.session.query(Wallet).filter_by(id=entry.wallet_id).with_for_update().first()
        correction_key = f"award:{award_id}:wallet:{wallet.id}:reversal:{admin_user.id}"
        _credit(
            wallet=wallet,
            amount=-entry.amount,
            kind="CORRECTION",
            reason=f"Estorno award #{award_id}: {reason}",
            entry_key=correction_key,
        )

    award.status = "REVERSED"
    db.session.commit()
    return award
