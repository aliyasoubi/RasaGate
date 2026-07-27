"""Health and chat proxy tests."""
from unittest.mock import AsyncMock

from app.services.rasa_client import RasaClient


def test_health_endpoint(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_chat_proxies_to_rasa(client):
    # Mock the Rasa client so no real Rasa server is needed.
    mock_rasa = AsyncMock(spec=RasaClient)
    mock_rasa.send_message.return_value = [
        {"recipient_id": "u1", "text": "Hello! How can I help you?"}
    ]
    client.app.state.rasa = mock_rasa

    r = client.post("/api/v1/chat/", json={"sender_id": "u1", "message": "hi"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "success"
    assert body["data"]["responses"][0]["text"] == "Hello! How can I help you?"
    mock_rasa.send_message.assert_awaited_once_with("u1", "hi")
