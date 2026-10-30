"""Testes da política de pontos v1 — matriz mínima de aceite.

Cobertura:
  P1  Publicação +5
  P2  Um desfecho por pet
  P3  Valores corretos por situação de risco
  P8  Saldo = soma do extrato
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app import db as _db
from app.auth.models import User
from app.gamification.models import PointAward, PointEntry, Wallet
from app.gamification.service import (
    OUTCOME_NORMAL_NGO,
    OUTCOME_NORMAL_PUBLISHER,
    OUTCOME_RISK_NGO,
    OUTCOME_RISK_PUBLISHER,
    PUBLICATION_CREDIT,
    credit_publication,
    settle_outcome,
)
from app.organizations.models import Ngo, NgoMember
from app.pets.models import Pet, PetEvent


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #

def _user(app, suffix=""):
    with app.app_context():
        u = User(
            name=f"U{suffix}",
            email_normalized=f"u{suffix}@p.test",
            city="SP", state="SP",
        )
        u.set_password("pass1234")
        u.email_verified_at = datetime.now(timezone.utc)
        _db.session.add(u)
        _db.session.commit()
        return u.id


def _ngo(app, user_id):
    with app.app_context():
        cnpj = str(uuid.uuid4().int)[:14].ljust(14, "0")
        ngo = Ngo(
            name=f"ONG{uuid.uuid4().hex[:4]}",
            cnpj_normalized=cnpj,
            contact_email="o@p.test",
            city="SP", state="SP",
            verification_status="APPROVED",
        )
        _db.session.add(ngo)
        _db.session.flush()
        _db.session.add(NgoMember(ngo_id=ngo.id, user_id=user_id, active=True))
        _db.session.commit()
        return ngo.id


def _pub_pet(app, publisher_id, status="NEEDS_RESCUE", risk="NONE"):
    with app.app_context():
        pet = Pet(
            publisher_user_id=publisher_id,
            responsible_user_id=publisher_id,
            species="DOG", help_type="RESCUE",
            status=status, description="x " * 10,
            city="SP", state="SP",
            risk_status=risk,
        )
        _db.session.add(pet)
        _db.session.flush()
        ev = PetEvent(pet_id=pet.id, event_type="PUBLICATION",
                      actor_user_id=publisher_id, to_status=status)
        _db.session.add(ev)
        _db.session.flush()
        credit_publication(pet, ev, publisher_id)
        _db.session.commit()
        return pet.id


def _balance(app, user_id=None, ngo_id=None):
    with app.app_context():
        if user_id:
            w = _db.session.query(Wallet).filter_by(user_id=user_id).first()
        else:
            w = _db.session.query(Wallet).filter_by(ngo_id=ngo_id).first()
        return w.balance if w else 0


# --------------------------------------------------------------------------- #
# P1 — Publicação: publicador +5, ONG 0                                       #
# --------------------------------------------------------------------------- #

def test_P1_publication_normal(app):
    uid = _user(app, uuid.uuid4().hex[:6])
    ngo_uid = _user(app, uuid.uuid4().hex[:6])
    ngo_id = _ngo(app, ngo_uid)

    _pub_pet(app, uid)

    assert _balance(app, user_id=uid) == PUBLICATION_CREDIT
    assert _balance(app, ngo_id=ngo_id) == 0


# --------------------------------------------------------------------------- #
# P3a — Resgate normal confirmado: publicador total 15, ONG 15                #
# --------------------------------------------------------------------------- #

def test_P3a_rescue_normal_outcome(app):
    uid = _user(app, uuid.uuid4().hex[:6])
    ngo_uid = _user(app, uuid.uuid4().hex[:6])
    ngo_id = _ngo(app, ngo_uid)
    pet_id = _pub_pet(app, uid)

    with app.app_context():
        pet = _db.session.get(Pet, pet_id)
        pet.risk_status = "NONE"
        ev = PetEvent(pet_id=pet.id, event_type="RESCUE_CONFIRMED",
                      actor_user_id=ngo_uid, acting_ngo_id=ngo_id,
                      from_status="IN_RESCUE", to_status="SHELTERED")
        _db.session.add(ev)
        _db.session.flush()
        settle_outcome(pet, ev, ngo_id)
        _db.session.commit()

    pub_balance = _balance(app, user_id=uid)
    ngo_balance = _balance(app, ngo_id=ngo_id)

    assert pub_balance == PUBLICATION_CREDIT + OUTCOME_NORMAL_PUBLISHER, \
        f"Publicador esperado {PUBLICATION_CREDIT + OUTCOME_NORMAL_PUBLISHER}, obtido {pub_balance}"
    assert ngo_balance == OUTCOME_NORMAL_NGO, \
        f"ONG esperado {OUTCOME_NORMAL_NGO}, obtido {ngo_balance}"


# --------------------------------------------------------------------------- #
# P3b — Resgate com risco aprovado: publicador 25, ONG 40                     #
# --------------------------------------------------------------------------- #

def test_P3b_rescue_risk_outcome(app):
    uid = _user(app, uuid.uuid4().hex[:6])
    ngo_uid = _user(app, uuid.uuid4().hex[:6])
    ngo_id = _ngo(app, ngo_uid)
    pet_id = _pub_pet(app, uid, risk="APPROVED")

    with app.app_context():
        pet = _db.session.get(Pet, pet_id)
        pet.risk_status = "APPROVED"
        ev = PetEvent(pet_id=pet.id, event_type="RESCUE_CONFIRMED",
                      actor_user_id=ngo_uid, acting_ngo_id=ngo_id,
                      from_status="IN_RESCUE", to_status="SHELTERED")
        _db.session.add(ev)
        _db.session.flush()
        settle_outcome(pet, ev, ngo_id)
        _db.session.commit()

    pub_balance = _balance(app, user_id=uid)
    ngo_balance = _balance(app, ngo_id=ngo_id)

    assert pub_balance == PUBLICATION_CREDIT + OUTCOME_RISK_PUBLISHER
    assert ngo_balance == OUTCOME_RISK_NGO


# --------------------------------------------------------------------------- #
# P2 — Adoção após resgate já pontuado não duplica pontos                     #
# --------------------------------------------------------------------------- #

def test_P2_adoption_after_rescue_no_extra_points(app):
    uid = _user(app, uuid.uuid4().hex[:6])
    ngo_uid = _user(app, uuid.uuid4().hex[:6])
    ngo_id = _ngo(app, ngo_uid)
    pet_id = _pub_pet(app, uid)

    with app.app_context():
        pet = _db.session.get(Pet, pet_id)
        ev1 = PetEvent(pet_id=pet.id, event_type="RESCUE_CONFIRMED",
                       actor_user_id=ngo_uid, acting_ngo_id=ngo_id,
                       to_status="SHELTERED")
        _db.session.add(ev1)
        _db.session.flush()
        settle_outcome(pet, ev1, ngo_id)
        _db.session.commit()

    balance_after_rescue = _balance(app, user_id=uid)

    with app.app_context():
        pet = _db.session.get(Pet, pet_id)
        ev2 = PetEvent(pet_id=pet.id, event_type="ADOPTED",
                       actor_user_id=uid, to_status="ADOPTED")
        _db.session.add(ev2)
        _db.session.flush()
        settle_outcome(pet, ev2, None)  # sem ONG na adoção
        _db.session.commit()

    balance_after_adoption = _balance(app, user_id=uid)
    assert balance_after_adoption == balance_after_rescue, \
        "Adoção após resgate não deve gerar pontos adicionais"


# --------------------------------------------------------------------------- #
# P3c — Adoção direta sem ONG: publicador 15 normal / 25 risco               #
# --------------------------------------------------------------------------- #

def test_P3c_direct_adoption_no_ngo_normal(app):
    uid = _user(app, uuid.uuid4().hex[:6])
    pet_id = _pub_pet(app, uid, status="AVAILABLE")

    with app.app_context():
        pet = _db.session.get(Pet, pet_id)
        pet.risk_status = "NONE"
        ev = PetEvent(pet_id=pet.id, event_type="ADOPTED",
                      actor_user_id=uid, to_status="ADOPTED")
        _db.session.add(ev)
        _db.session.flush()
        settle_outcome(pet, ev, None)
        _db.session.commit()

    total = _balance(app, user_id=uid)
    assert total == PUBLICATION_CREDIT + OUTCOME_NORMAL_PUBLISHER


# --------------------------------------------------------------------------- #
# P8 — Saldo sempre igual à soma do extrato                                   #
# --------------------------------------------------------------------------- #

def test_P8_balance_reconciliation(app):
    uid = _user(app, uuid.uuid4().hex[:6])
    ngo_uid = _user(app, uuid.uuid4().hex[:6])
    ngo_id = _ngo(app, ngo_uid)
    pet_id = _pub_pet(app, uid)

    with app.app_context():
        pet = _db.session.get(Pet, pet_id)
        ev = PetEvent(pet_id=pet.id, event_type="RESCUE_CONFIRMED",
                      actor_user_id=ngo_uid, acting_ngo_id=ngo_id,
                      to_status="SHELTERED")
        _db.session.add(ev)
        _db.session.flush()
        settle_outcome(pet, ev, ngo_id)
        _db.session.commit()

    with app.app_context():
        for user_id, ngo in [(uid, None), (None, ngo_id)]:
            if user_id:
                w = _db.session.query(Wallet).filter_by(user_id=user_id).first()
            else:
                w = _db.session.query(Wallet).filter_by(ngo_id=ngo).first()

            if not w:
                continue
            total = _db.session.query(
                _db.func.sum(PointEntry.amount)
            ).filter_by(wallet_id=w.id).scalar() or 0

            assert w.balance == total, \
                f"Divergência carteira {w.id}: balance={w.balance} soma={total}"
