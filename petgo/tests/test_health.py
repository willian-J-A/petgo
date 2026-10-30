"""Testes de healthcheck — Task 1."""
from __future__ import annotations


def test_liveness(client):
    r = client.get("/health/live")
    assert r.status_code == 200
    assert r.json["status"] == "ok"
