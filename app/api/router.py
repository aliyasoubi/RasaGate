# app/api/router.py
from fastapi import APIRouter

from app.api.v1.chat import router as chat_router
from app.api.v1.intents import router as intents_router
from app.api.v1.training import router as training_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(chat_router)
api_router.include_router(intents_router)
api_router.include_router(training_router)