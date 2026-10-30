"""Fixtures pytest para o PetGo.

Testes transacionais e de concorrência rodam em MySQL real isolado.
SQLite não é utilizado (constraints e comportamento diferem do MySQL).
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("APP_ENV", "testing")

from app import create_app, db as _db  # noqa: E402


@pytest.fixture(scope="session")
def app():
    """Aplicação Flask para toda a sessão de testes."""
    application = create_app("testing")
    with application.app_context():
        _db.create_all()
        yield application
        _db.drop_all()


@pytest.fixture()
def client(app):
    """Cliente de teste Flask."""
    return app.test_client()


@pytest.fixture()
def db(app):
    """Sessão de banco limpa por teste (rollback ao final)."""
    with app.app_context():
        connection = _db.engine.connect()
        transaction = connection.begin()
        _db.session.configure(bind=connection)
        yield _db
        _db.session.remove()
        transaction.rollback()
        connection.close()
