# tests/test_rasa_client.py
"""RasaClient tests using a mocked httpx transport — no real Rasa needed."""
import json

import httpx
import pytest

from app.core.exceptions import RasaUnreachableError
from app.services.rasa_client import RasaClient


def _client_with_handler(handler) -> httpx.AsyncClient:
    transport = httpx.MockTransport(handler)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


async def test_send_message_returns_rasa_responses():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/webhooks/rest/webhook"
        assert json.loads(request.content) == {"sender": "u1", "message": "hi"}
        return httpx.Response(200, json=[{"recipient_id": "u1", "text": "hello"}])

    async with _client_with_handler(handler) as http:
        rasa = RasaClient(http, base_url="http://testserver")
        result = await rasa.send_message("u1", "hi")
        assert result == [{"recipient_id": "u1", "text": "hello"}]


async def test_train_returns_model_bytes():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/model/train"
        assert request.headers["content-type"] == "application/yaml"
        return httpx.Response(200, content=b"fake-tar-gz-bytes")

    async with _client_with_handler(handler) as http:
        rasa = RasaClient(http, base_url="http://testserver")
        result = await rasa.train("version: '3.1'")
        assert result == b"fake-tar-gz-bytes"


async def test_replace_model_puts_model_path():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PUT"
        assert request.url.path == "/model"
        assert json.loads(request.content) == {"model_file": "/models/latest.tar.gz"}
        return httpx.Response(204)

    async with _client_with_handler(handler) as http:
        rasa = RasaClient(http, base_url="http://testserver")
        await rasa.replace_model("/models/latest.tar.gz")  # should not raise


async def test_http_error_status_raises_rasa_unreachable():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    async with _client_with_handler(handler) as http:
        rasa = RasaClient(http, base_url="http://testserver")
        with pytest.raises(RasaUnreachableError):
            await rasa.send_message("u1", "hi")


async def test_connection_error_raises_rasa_unreachable():
    def handler(request: httpx.Request):
        raise httpx.ConnectError("connection refused")

    async with _client_with_handler(handler) as http:
        rasa = RasaClient(http, base_url="http://testserver")
        with pytest.raises(RasaUnreachableError):
            await rasa.send_message("u1", "hi")
