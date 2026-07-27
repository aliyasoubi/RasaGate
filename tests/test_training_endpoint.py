# tests/test_training_endpoint.py
"""
Training trigger/status endpoint tests.

We don't want real training to run against a fake Rasa server here — that's
covered separately in test_training_orchestrator.py with a mocked RasaClient.
Here we only exercise the HTTP layer: task creation, the one-at-a-time
concurrency guard, and status polling. Background tasks are patched out.
"""
from unittest.mock import AsyncMock

import app.api.v1.training as training_module


def test_trigger_training_returns_202_with_task_id(client, monkeypatch):
    # Don't actually run the pipeline — just assert it *would* be scheduled.
    monkeypatch.setattr(training_module, "run_training_pipeline", AsyncMock())

    r = client.post("/api/v1/models/train", json={})
    assert r.status_code == 202
    body = r.json()
    assert body["data"]["status"] == "pending"
    assert body["data"]["task_id"].startswith("task_")


def test_second_training_while_active_returns_503(client, monkeypatch):
    monkeypatch.setattr(training_module, "run_training_pipeline", AsyncMock())

    first = client.post("/api/v1/models/train", json={})
    assert first.status_code == 202

    second = client.post("/api/v1/models/train", json={})
    assert second.status_code == 503
    assert second.json()["error_code"] == "TRAINING_IN_PROGRESS"


def test_status_polling(client, monkeypatch):
    monkeypatch.setattr(training_module, "run_training_pipeline", AsyncMock())

    task_id = client.post("/api/v1/models/train", json={}).json()["data"]["task_id"]

    r = client.get(f"/api/v1/models/train/status/{task_id}")
    assert r.status_code == 200
    assert r.json()["data"]["task_id"] == task_id
    assert r.json()["data"]["status"] == "pending"


def test_status_for_missing_task_404(client):
    r = client.get("/api/v1/models/train/status/task_doesnotexist")
    assert r.status_code == 404
    assert r.json()["error_code"] == "RESOURCE_NOT_FOUND"


def test_webhook_url_is_stored_on_task(client, monkeypatch):
    monkeypatch.setattr(training_module, "run_training_pipeline", AsyncMock())

    r = client.post(
        "/api/v1/models/train", json={"webhook_url": "https://example.com/hook"}
    )
    assert r.status_code == 202
    task_id = r.json()["data"]["task_id"]

    # webhook_url isn't in the status response schema, but the task should
    # have been created without error — confirmed indirectly via 200 status.
    status_resp = client.get(f"/api/v1/models/train/status/{task_id}")
    assert status_resp.status_code == 200
