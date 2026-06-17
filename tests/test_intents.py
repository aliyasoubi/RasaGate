# tests/test_intents.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_create_intent():
    r = client.post("/api/v1/intents/", json={
        "name": "greet",
        "examples": ["hi", "hello"],
        "responses": ["Hi there!"]
    })
    assert r.status_code == 201
    assert r.json()["status"] == "success"

def test_invalid_intent_name():
    r = client.post("/api/v1/intents/", json={"name": "Bad Name"})
    assert r.status_code == 422  # regex rejects
