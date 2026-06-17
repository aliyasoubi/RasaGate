# app/api/v1/chat.py
from fastapi import APIRouter
from pydantic import BaseModel

from app.schemas.base import SuccessResponse
from app.services.rasa_client import RasaClient

router = APIRouter(prefix="/chat", tags=["chat"])


class MessageRequest(BaseModel):
    sender_id: str
    message: str


from fastapi import APIRouter, Request

@router.post("/", response_model=SuccessResponse)
async def chat(payload: MessageRequest, request: Request):
    client: RasaClient = request.app.state.rasa
    responses = await client.send_message(payload.sender_id, payload.message)
    return SuccessResponse(data={"responses": responses})
