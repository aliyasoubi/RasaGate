"""Pydantic schemas for training endpoints."""
from datetime import datetime

from pydantic import BaseModel, Field


class TrainRequest(BaseModel):
    """Request body for triggering training."""

    webhook_url: str | None = Field(
        default=None,
        description="Optional URL notified when training finishes.",
    )


class TaskStatusOut(BaseModel):
    """Optional typed status response."""

    model_config = {"from_attributes": True}

    task_id: str
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
