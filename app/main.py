# app/main.py
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from app.api.router import api_router
from app.core.auth import ApiKeyMiddleware
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import RequestIdMiddleware, configure_logging
from app.db.session import Base, engine
from app.services.rasa_client import RasaClient


def _recover_stale_tasks() -> None:
    """
    If the server crashed/restarted mid-training, tasks stuck in
    pending/processing would block all future training (503) forever.
    On startup, mark them as failed so the queue is usable again.
    """
    from sqlalchemy import select

    from app.db.session import SessionLocal
    from app.models.nlu import TaskStatus, TrainingTask

    db = SessionLocal()
    try:
        stale = db.scalars(
            select(TrainingTask).where(
                TrainingTask.status.in_([TaskStatus.pending, TaskStatus.processing])
            )
        ).all()
        for task in stale:
            task.status = TaskStatus.failed
            task.error_message = "Server restarted while task was in progress."
        if stale:
            db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.log_level)
    Base.metadata.create_all(bind=engine)  # dev only; use Alembic in prod
    _recover_stale_tasks()
    async with httpx.AsyncClient(timeout=30.0) as client:
        app.state.rasa = RasaClient(client)
        yield


app = FastAPI(title="Rasa Gate", version="1.0.0", lifespan=lifespan)

app.add_middleware(ApiKeyMiddleware)
app.add_middleware(RequestIdMiddleware)
register_exception_handlers(app)
app.include_router(api_router)


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}
