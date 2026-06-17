# app/services/training.py
"""
Background training orchestration:
  1. Mark task as processing
  2. Dump DB → YAML files on shared volume
  3. POST YAML to Rasa /model/train → receive .tar.gz bytes
  4. Write model to disk
  5. PUT /model to hot-reload
  6. Mark task success/failed
  7. Call webhook if provided
"""
import logging
from datetime import datetime, timezone
from pathlib import Path

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.nlu import TaskStatus, TrainingTask
from app.services.rasa_client import RasaClient
from app.services.yaml_builder import build_domain_yaml, build_nlu_yaml, build_rules_yaml

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _combined_yaml(db: Session) -> str:
    """
    Rasa accepts a single YAML payload that contains nlu + domain + rules.
    We concatenate the three YAML documents with a separator.
    """
    nlu = build_nlu_yaml(db)
    domain = build_domain_yaml(db)
    rules = build_rules_yaml(db)
    return f"{nlu}\n---\n{domain}\n---\n{rules}"


async def _notify_webhook(url: str, payload: dict) -> None:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(url, json=payload)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Webhook delivery failed for %s: %s", url, exc)


async def run_training_task(task_id: str, db: Session) -> None:
    """
    Called by FastAPI BackgroundTasks. Runs the full train → reload pipeline.
    `db` is a *dedicated* session created by the caller (not the request session).
    """
    task: TrainingTask | None = db.get(TrainingTask, task_id)
    if task is None:
        logger.error("Training task %s not found in DB.", task_id)
        return

    task.status = TaskStatus.processing
    db.commit()

    models_dir = Path(settings.rasa_shared_volume) / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    client = RasaClient()

    try:
        # 1. Generate combined training YAML from DB
        logger.info("[%s] Generating YAML from database...", task_id)
        training_yaml = _combined_yaml(db)

        # 2. Send to Rasa for training
        logger.info("[%s] Sending to Rasa /model/train...", task_id)
        model_bytes = await client.train(training_yaml)

        # 3. Persist the model file
        model_filename = f"{datetime.now(tz=timezone.utc).strftime('%Y%m%d-%H%M%S')}-latest.tar.gz"
        model_path = models_dir / model_filename
        model_path.write_bytes(model_bytes)
        logger.info("[%s] Model saved to %s", task_id, model_path)

        # 4. Hot-reload
        logger.info("[%s] Reloading model into Rasa memory...", task_id)
        await client.replace_model(str(model_path))

        # 5. Mark success
        task.status = TaskStatus.success
        task.completed_at = _now()
        db.commit()
        logger.info("[%s] Training completed successfully.", task_id)

        # 6. Notify webhook
        if task.webhook_url:
            await _notify_webhook(
                task.webhook_url,
                {
                    "task_id": task_id,
                    "event": "training_completed",
                    "status": "success",
                    "details": {
                        "model_file": model_filename,
                        "message": "Model trained and loaded into memory successfully.",
                    },
                },
            )

    except Exception as exc:  # noqa: BLE001
        logger.exception("[%s] Training failed: %s", task_id, exc)
        task.status = TaskStatus.failed
        task.completed_at = _now()
        task.error_message = str(exc)
        db.commit()

        if task.webhook_url:
            await _notify_webhook(
                task.webhook_url,
                {
                    "task_id": task_id,
                    "event": "training_failed",
                    "status": "failed",
                    "details": {"message": str(exc)},
                },
            )
    finally:
        db.close()