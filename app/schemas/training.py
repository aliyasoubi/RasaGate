from pydantic import BaseModel

class TrainRequest(BaseModel):
    webhook_url: str | None = None
