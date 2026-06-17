# app/api/v1/training.py
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.orm import Session

from app.core.exceptions import TrainingInProgressError
from app.db.session import SessionLocal, get_db
from app.models.nlu import TaskStatus, TrainingTask
from app.schemas.base import SuccessResponse
from app.schemas.training import TrainRequest
from app.services.training import run_training_task

router = APIRouter(prefix="/models", tags=["models"])


def _has_active_task(db: Session) -> bool:
    from sqlalchemy import select

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
def start_training(
    payload: TrainRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
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

    # Spawn a NEW session for the background task so it outlives the request.
    bg_db = SessionLocal()
    background_tasks.add_task(run_training_task, task_id, bg_db)

    return SuccessResponse(
        message="Training started in the background.",
        data={"task_id": task_id, "status": TaskStatus.pending},
    )


@router.get("/train/status/{task_id}", response_model=SuccessResponse)
def get_training_status(task_id: str, db: Session = Depends(get_db)):
    from sqlalchemy import select

    task: TrainingTask | None = db.scalar(
        select(TrainingTask).where(TrainingTask.task_id == task_id)
    )
    if task is None:
        from app.core.exceptions import ResourceNotFoundError
        raise ResourceNotFoundError("training task", task_id)  # type: ignore[arg-type]

    return SuccessResponse(
        data={
            "task_id": task.task_id,
            "status": task.status,
            "started_at": task.started_at,
            "completed_at": task.completed_at,
            "error_message": task.error_message,
        }
    )