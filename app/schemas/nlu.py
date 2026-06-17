# app/schemas/nlu.py
import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

INTENT_PATTERN = re.compile(r"^[a-z0-9_]+$")


# ---------------------------------------------------------------------------
# Example schemas
# ---------------------------------------------------------------------------

class ExampleCreate(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)


class ExampleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    intent_id: int
    text: str
    created_at: datetime


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class ResponseCreate(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)


class ResponseUpdate(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)


class ResponseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    intent_id: int
    text: str
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Intent schemas
# ---------------------------------------------------------------------------

class IntentBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not INTENT_PATTERN.match(v):
            raise ValueError(
                "Intent name must contain only lowercase letters, "
                "digits, and underscores (^[a-z0-9_]+$)."
            )
        return v


class IntentCreate(IntentBase):
    """
    Accepts intent name, optional description, optional seed examples and
    response texts — all in a single payload (convenience endpoint).
    """
    examples: list[str] = Field(default_factory=list)
    responses: list[str] = Field(default_factory=list)


class IntentUpdate(BaseModel):
    """Only description is patchable; renaming an intent is a separate endpoint."""
    description: str | None = None


class IntentOut(IntentBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
    examples: list[ExampleOut] = Field(default_factory=list)
    responses: list[ResponseOut] = Field(default_factory=list)