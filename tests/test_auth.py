# tests/test_auth.py
"""Auth middleware tests. Uses its own TestClient (not the `client` fixture)
because it needs to flip settings.auth_token between requests."""
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


def test_auth_disabled_by_default(client):
    """settings.auth_token is None/empty in the base test config -> no auth required."""
    r = client.get("/api/v1/intents/")
    assert r.status_code == 200


def test_auth_rejects_missing_key(client, monkeypatch):
    monkeypatch.setattr(settings, "auth_token", "secret123")
    r = client.get("/api/v1/intents/")
    assert r.status_code == 401
    assert r.json()["error_code"] == "UNAUTHORIZED"


def test_auth_rejects_wrong_key(client, monkeypatch):
    monkeypatch.setattr(settings, "auth_token", "secret123")
    r = client.get("/api/v1/intents/", headers={"X-API-Key": "wrong"})
    assert r.status_code == 401


def test_auth_accepts_correct_key(client, monkeypatch):
    monkeypatch.setattr(settings, "auth_token", "secret123")
    r = client.get("/api/v1/intents/", headers={"X-API-Key": "secret123"})
    assert r.status_code == 200


def test_health_always_public(client, monkeypatch):
    """Unprotected prefixes stay open even when auth is enabled."""
    monkeypatch.setattr(settings, "auth_token", "secret123")
    r = client.get("/health")
    assert r.status_code == 200
