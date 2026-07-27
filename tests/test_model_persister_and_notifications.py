# tests/test_model_persister_and_notifications.py
import httpx

from app.services.model_persister import ModelPersister
from app.services.notification_service import NotificationService


def test_model_persister_writes_timestamped_file(tmp_path):
    persister = ModelPersister(models_dir=tmp_path)
    path = persister.save_model(b"fake-model-bytes")

    assert path.exists()
    assert path.read_bytes() == b"fake-model-bytes"
    assert path.name.endswith("-latest.tar.gz")
    assert path.parent == tmp_path


def test_model_persister_creates_missing_dir(tmp_path):
    target = tmp_path / "does" / "not" / "exist"
    persister = ModelPersister(models_dir=target)
    path = persister.save_model(b"x")
    assert path.exists()


def _patched_async_client_factory(monkeypatch, transport: httpx.MockTransport):
    """
    Replace httpx.AsyncClient (as seen by notification_service) with a
    factory that always uses our mock transport, while still using the
    REAL httpx.AsyncClient class underneath — avoids the trap of patching
    httpx.AsyncClient globally and then having the replacement call itself.
    """
    import app.services.notification_service as mod

    real_async_client = httpx.AsyncClient  # captured before any patching

    def fake_async_client(*args, **kwargs):
        kwargs.pop("timeout", None)
        return real_async_client(transport=transport)

    monkeypatch.setattr(mod.httpx, "AsyncClient", fake_async_client)


async def test_notify_success_posts_expected_payload(monkeypatch):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured["json"] = json.loads(request.content)
        return httpx.Response(200)

    _patched_async_client_factory(monkeypatch, httpx.MockTransport(handler))

    await NotificationService().notify_success(
        "https://example.com/hook", "task_1", "model.tar.gz"
    )

    assert captured["json"]["event"] == "training_completed"
    assert captured["json"]["status"] == "success"
    assert captured["json"]["details"]["model_file"] == "model.tar.gz"


async def test_notify_failure_posts_expected_payload(monkeypatch):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured["json"] = json.loads(request.content)
        return httpx.Response(200)

    _patched_async_client_factory(monkeypatch, httpx.MockTransport(handler))

    await NotificationService().notify_failure(
        "https://example.com/hook", "task_1", "boom"
    )

    assert captured["json"]["event"] == "training_failed"
    assert captured["json"]["status"] == "failed"
    assert captured["json"]["details"]["message"] == "boom"


async def test_notify_never_raises_on_webhook_error(monkeypatch):
    """Webhook delivery failures must be swallowed (logged), not propagated —
    a broken customer webhook shouldn't fail the training pipeline."""

    def handler(request: httpx.Request):
        raise httpx.ConnectError("nope")

    _patched_async_client_factory(monkeypatch, httpx.MockTransport(handler))

    # Should not raise.
    await NotificationService().notify_success("https://example.com/hook", "task_1", "m.tar.gz")
    await NotificationService().notify_failure("https://example.com/hook", "task_1", "boom")
