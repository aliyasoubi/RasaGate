"""Training API endpoints: trigger training, check status."""
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ResourceNotFoundError, TrainingInProgressError
from app.db.session import get_db
from app.models.nlu import TaskStatus, TrainingTask
from app.schemas.base import SuccessResponse
from app.schemas.training import TrainRequest
from app.services.training_orchestrator import run_training_pipeline

router = APIRouter(prefix="/models", tags=["models"])


def _has_active_task(db: Session) -> bool:
    return db.scalar(
        select(TrainingTask).where(
            TrainingTask.status.in_([TaskStatus.pending, TaskStatus.processing])
        )
    ) is not None


@router.post(
    "/train",
    response_model=SuccessResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def trigger_training(
    payload: TrainRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Start model training in the background; returns a task_id for polling."""
    if _has_active_task(db):
        raise TrainingInProgressError()

    task_id = f"task_{uuid.uuid4().hex[:10]}"
    task = TrainingTask(
        task_id=task_id,
        status=TaskStatus.pending,
        webhook_url=payload.webhook_url,
    )
    db.add(task)
    db.commit()

    # Orchestrator opens and closes its own session — do NOT pass a session here.
    background_tasks.add_task(run_training_pipeline, task_id)

    return SuccessResponse(
        message="Training started",
        data={"task_id": task_id, "status": TaskStatus.pending},
    )


@router.get("/train/status/{task_id}", response_model=SuccessResponse)
def get_task_status(task_id: str, db: Session = Depends(get_db)):
    """Poll training task status."""
    task = db.scalar(select(TrainingTask).where(TrainingTask.task_id == task_id))
    if task is None:
        raise ResourceNotFoundError("training task", task_id)

    return SuccessResponse(
        data={
            "task_id": task.task_id,
            "status": task.status,
            "started_at": task.started_at,
            "completed_at": task.completed_at,
            "error_message": task.error_message,
        }
    )
