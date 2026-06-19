"""Background training pipeline aligned to the real service contracts."""
import logging
from datetime import datetime, timezone
from pathlib import Path

import httpx
from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.nlu import TaskStatus, TrainingTask
from app.services.model_persister import ModelPersister
from app.services.notification_service import NotificationService
from app.services.rasa_client import RasaClient
from app.services.training_data_builder import build_combined_training_data

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


async def run_training_pipeline(task_id: str) -> None:
    """
    Run the full training pipeline as a background task.

    Manages its own DB session and HTTP client so it never depends on the
    request scope. Steps: compile data -> train -> persist -> hot-swap model.
    """
    db = SessionLocal()
    notifier = NotificationService()
    webhook_url: str | None = None

    try:
        task = db.scalar(select(TrainingTask).where(TrainingTask.task_id == task_id))
        if task is None:
            logger.error("Training task %s not found", task_id)
            return

        webhook_url = task.webhook_url
        task.status = TaskStatus.processing
        task.started_at = _now()
        db.commit()

        # 1. Compile DB intents/examples/responses into a single Rasa YAML payload.
        training_data = build_combined_training_data(db)

        # 2 + 4. Rasa calls need an httpx client; create a dedicated one for the task.
        async with httpx.AsyncClient() as http_client:
            rasa = RasaClient(http_client, base_url=settings.rasa_url)

            # 2. Train -> model archive bytes.
            model_bytes = await rasa.train(training_data)

            # 3. Persist the archive to the models directory.
            persister = ModelPersister(models_dir=Path(settings.rasa_model_path))
            model_path = persister.save_model(model_bytes)

            # 4. Hot-swap the freshly trained model into Rasa.
            await rasa.replace_model(str(model_path.absolute()))

        task.status = TaskStatus.completed
        task.completed_at = _now()
        db.commit()

        logger.info("Training task %s completed: %s", task_id, model_path.name)
        if webhook_url:
            await notifier.notify_success(webhook_url, task_id, model_path.name)

    except Exception as exc:
        logger.error("Training task %s failed: %s", task_id, exc, exc_info=True)
        db.rollback()
        try:
            task = db.scalar(
                select(TrainingTask).where(TrainingTask.task_id == task_id)
            )
            if task is not None:
                task.status = TaskStatus.failed
                task.error_message = str(exc)
                task.completed_at = _now()
                db.commit()
        except Exception:
            logger.exception("Could not mark task %s as failed", task_id)
            db.rollback()

        if webhook_url:
            await notifier.notify_failure(webhook_url, task_id, str(exc))

    finally:
        db.close()
