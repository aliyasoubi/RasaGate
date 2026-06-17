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


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.log_level)
    Base.metadata.create_all(bind=engine)  # dev only; use Alembic in prod
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
