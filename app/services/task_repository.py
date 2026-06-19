"""Repository for training task database operations."""

from typing import Optional, List

from sqlalchemy.orm import Session

from app.models.nlu import TrainingTask, TaskStatus


class TaskRepository:
    """Handles all database queries for training tasks."""

    def __init__(self, db: Session):
        self.db = db

    def has_active_task(self) -> bool:
        """Check if there's any task in PENDING or TRAINING status."""
        count = self.db.query(TrainingTask).filter(
            TrainingTask.status.in_([TaskStatus.PENDING, TaskStatus.TRAINING])
        ).count()
        return count > 0

    def get_task_by_id(self, task_id: str) -> Optional[TrainingTask]:
        """Retrieve a task by its ID."""
        return self.db.query(TrainingTask).filter(TrainingTask.id == task_id).first()

    def get_recent_tasks(self, limit: int = 10) -> List[TrainingTask]:
        """Get the most recent tasks, ordered by creation date."""
        return (
            self.db.query(TrainingTask)
            .order_by(TrainingTask.created_at.desc())
            .limit(limit)
            .all()
        )

    def get_failed_tasks(self, limit: int = 10) -> List[TrainingTask]:
        """Get recent failed tasks."""
        return (
            self.db.query(TrainingTask)
            .filter(TrainingTask.status == TaskStatus.FAILED)
            .order_by(TrainingTask.created_at.desc())
            .limit(limit)
            .all()
        )
