import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_root_endpoint():
    response = client.get("/api/v1/chat/health")  # Example health route you make
    assert response.status_code == 200
    assert "status" in response.json()
