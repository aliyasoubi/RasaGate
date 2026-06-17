# app/models/nlu.py
import enum
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Intent(Base):
    __tablename__ = "intents"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    examples: Mapped[list["Example"]] = relationship(
        back_populates="intent",
        cascade="all, delete-orphan",
    )
    responses: Mapped[list["Response"]] = relationship(
        back_populates="intent",
        cascade="all, delete-orphan",
    )


class Example(Base):
    __tablename__ = "examples"
    __table_args__ = (
        UniqueConstraint("intent_id", "text", name="uq_intent_example_text"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    text: Mapped[str] = mapped_column(Text)
    intent_id: Mapped[int] = mapped_column(
        ForeignKey("intents.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    intent: Mapped["Intent"] = relationship(back_populates="examples")


class Response(Base):
    """
    One intent → many response text variations, all grouped under utter_{intent.name}
    during YAML generation. Clients never see the utter_ prefix.
    """

    __tablename__ = "responses"

    id: Mapped[int] = mapped_column(primary_key=True)
    text: Mapped[str] = mapped_column(Text)
    intent_id: Mapped[int] = mapped_column(
        ForeignKey("intents.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    intent: Mapped["Intent"] = relationship(back_populates="responses")


class TaskStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    success = "success"
    failed = "failed"


class TrainingTask(Base):
    __tablename__ = "training_tasks"

    task_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus), default=TaskStatus.pending
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    webhook_url: Mapped[str | None] = mapped_column(String(500), nullable=True)