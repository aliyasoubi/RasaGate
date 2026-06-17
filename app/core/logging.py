# app/core/logging.py
"""
Structured JSON logging via structlog.

Every log line includes:
  - timestamp (ISO-8601)
  - log level
  - logger name
  - request_id  (from X-Request-ID header, propagated via contextvars)
  - the log message + any extra kwargs

Usage anywhere in the app:
    from app.core.logging import get_logger
    logger = get_logger(__name__)
    logger.info("intent_created", intent_name="greet")
"""
import logging
import uuid
from contextvars import ContextVar

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

# Context variable — holds the current request's correlation ID
_request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


def get_request_id() -> str:
    return _request_id_var.get()


def configure_logging(log_level: str = "INFO") -> None:
    """Call once at startup (from main.py lifespan)."""
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(log_level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Also route stdlib logging through structlog so SQLAlchemy / uvicorn
    # log lines appear in the same JSON format.
    logging.basicConfig(
        format="%(message)s",
        level=logging.getLevelName(log_level.upper()),
    )


def get_logger(name: str):
    return structlog.get_logger(name)


class RequestIdMiddleware(BaseHTTPMiddleware):
    """
    1. Read X-Request-ID from the incoming request (or generate one).
    2. Store it in the ContextVar so all log lines within this request
       automatically include it.
    3. Echo it back in the response header.
    """

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        token = _request_id_var.set(request_id)

        # Bind to structlog's contextvars so every logger.* call gets it for free
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        try:
            response = await call_next(request)
        finally:
            _request_id_var.reset(token)

        response.headers["X-Request-ID"] = request_id
        return response