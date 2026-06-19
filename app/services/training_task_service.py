"""Service for managing training tasks."""

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.nlu import TrainingTask, TaskStatus
from app.services.task_repository import TaskRepository

logger = logging.getLogger(__name__)


class TrainingTaskService:
    """Encapsulates training task business logic."""

    def __init__(self, db: Session):
        self.db = db
        self.repository = TaskRepository(db)

    def has_active_task(self) -> bool:
        """Check if there's an active training task."""
        return self.repository.has_active_task()

    def create_task(self, task_id: str, metadata: dict) -> TrainingTask:
        """Create a new training task."""
        task = TrainingTask(
            id=task_id,
            status=TaskStatus.PENDING,
            metadata=metadata,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        logger.info("Created training task %s", task_id)
        return task

    def get_task(self, task_id: str) -> Optional[TrainingTask]:
        """Retrieve a task by ID."""
        return self.repository.get_task_by_id(task_id)

    def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        error_message: Optional[str] = None,
        model_path: Optional[str] = None
    ) -> Optional[TrainingTask]:
        """Update task status and related fields."""
        task = self.get_task(task_id)
        if not task:
            logger.warning("Cannot update task %s: not found", task_id)
            return None

        task.status = status
        task.updated_at = datetime.utcnow()

        if status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            task.completed_at = datetime.utcnow()

        if error_message:
            task.error_message = error_message

        if model_path:
            task.model_path = model_path

        self.db.commit()
        self.db.refresh(task)
        logger.info("Updated task %s to status %s", task_id, status.value)
        return task
