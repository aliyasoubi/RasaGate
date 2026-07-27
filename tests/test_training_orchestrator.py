# tests/test_training_orchestrator.py
"""
End-to-end orchestrator tests with a mocked RasaClient — no real Rasa
server involved. Covers the success path, the failure path, and that the
task status ends up correct in the DB either way (regression coverage for
the TaskStatus.completed -> .success bug).
"""
from unittest.mock import AsyncMock, patch

import pytest

from app.models.nlu import Intent, Example, Response, TaskStatus, TrainingTask
from app.services.training_orchestrator import run_training_pipeline


@pytest.fixture
def seeded_task(db_session):
    """A pending task plus one trainable intent, committed to the DB."""
    intent = Intent(name="greet")
    db_session.add(intent)
    db_session.flush()
    db_session.add(Example(text="hi", intent_id=intent.id))
    db_session.add(Response(text="Hi there!", intent_id=intent.id))

    task = TrainingTask(task_id="task_test123", status=TaskStatus.pending)
    db_session.add(task)
    db_session.commit()
    return task.task_id


@pytest.fixture(autouse=True)
def _use_test_db(db_session, monkeypatch):
    """
    The orchestrator opens its own session via app.db.session.SessionLocal
    (by design — it must not depend on the request scope). Point that at
    the same in-memory engine the test fixture uses.
    """
    from sqlalchemy.orm import sessionmaker

    TestSessionLocal = sessionmaker(bind=db_session.get_bind())
    monkeypatch.setattr(
        "app.services.training_orchestrator.SessionLocal", TestSessionLocal
    )


async def test_pipeline_success_marks_task_success(seeded_task, db_session):
    mock_rasa = AsyncMock()
    mock_rasa.train.return_value = b"fake-model-bytes"
    mock_rasa.replace_model.return_value = None

    with patch(
        "app.services.training_orchestrator.RasaClient", return_value=mock_rasa
    ), patch(
        "app.services.training_orchestrator.ModelPersister"
    ) as mock_persister_cls:
        mock_persister_cls.return_value.save_model.return_value.name = "fake.tar.gz"
        mock_persister_cls.return_value.save_model.return_value.absolute.return_value = "/tmp/fake.tar.gz"

        await run_training_pipeline(seeded_task)

    task = db_session.get(TrainingTask, seeded_task)
    db_session.refresh(task)
    assert task.status == TaskStatus.success
    assert task.completed_at is not None
    assert task.error_message is None
    mock_rasa.train.assert_awaited_once()
    mock_rasa.replace_model.assert_awaited_once()


async def test_pipeline_failure_marks_task_failed(seeded_task, db_session):
    mock_rasa = AsyncMock()
    mock_rasa.train.side_effect = RuntimeError("Rasa exploded")

    with patch(
        "app.services.training_orchestrator.RasaClient", return_value=mock_rasa
    ):
        await run_training_pipeline(seeded_task)

    task = db_session.get(TrainingTask, seeded_task)
    db_session.refresh(task)
    assert task.status == TaskStatus.failed
    assert "Rasa exploded" in task.error_message


async def test_pipeline_notifies_webhook_on_success(db_session):
    intent = Intent(name="greet")
    db_session.add(intent)
    db_session.flush()
    db_session.add(Example(text="hi", intent_id=intent.id))
    db_session.add(Response(text="Hi!", intent_id=intent.id))
    task = TrainingTask(
        task_id="task_webhook",
        status=TaskStatus.pending,
        webhook_url="https://example.com/hook",
    )
    db_session.add(task)
    db_session.commit()

    mock_rasa = AsyncMock()
    mock_rasa.train.return_value = b"bytes"

    with patch(
        "app.services.training_orchestrator.RasaClient", return_value=mock_rasa
    ), patch(
        "app.services.training_orchestrator.ModelPersister"
    ) as mock_persister_cls, patch(
        "app.services.training_orchestrator.NotificationService"
    ) as mock_notifier_cls:
        mock_persister_cls.return_value.save_model.return_value.name = "fake.tar.gz"
        mock_persister_cls.return_value.save_model.return_value.absolute.return_value = "/tmp/fake.tar.gz"
        mock_notifier = mock_notifier_cls.return_value
        mock_notifier.notify_success = AsyncMock()

        await run_training_pipeline("task_webhook")

        mock_notifier.notify_success.assert_awaited_once()
