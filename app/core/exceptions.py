# app/core/exceptions.py
from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class RasaGateException(Exception):
    """Base application exception."""

    def __init__(
        self,
        status_code: int,
        error_code: str,
        message: str,
        details: dict | None = None,
    ):
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        self.details = details or {}
        super().__init__(message)


class IntentNotFoundError(RasaGateException):
    def __init__(self, intent_name: str):
        super().__init__(
            status.HTTP_404_NOT_FOUND,
            "INTENT_NOT_FOUND",
            f"Intent '{intent_name}' not found.",
            {"intent_name": intent_name},
        )


class IntentConflictError(RasaGateException):
    def __init__(self, intent_name: str):
        super().__init__(
            status.HTTP_409_CONFLICT,
            "INTENT_ALREADY_EXISTS",
            f"Intent '{intent_name}' already exists.",
            {"intent_name": intent_name},
        )


class ResourceNotFoundError(Exception):
    def __init__(self, resource: str, identifier: str | int) -> None:
        self.resource = resource
        self.identifier = identifier
        super().__init__(f"{resource} '{identifier}' not found")


class TrainingInProgressError(RasaGateException):
    def __init__(self):
        super().__init__(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "TRAINING_IN_PROGRESS",
            "A training task is already in progress.",
        )


class RasaUnreachableError(RasaGateException):
    def __init__(self, detail: str = ""):
        super().__init__(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "RASA_UNREACHABLE",
            f"Rasa server is unreachable. {detail}".strip(),
        )


def register_exception_handlers(app) -> None:
    @app.exception_handler(RasaGateException)
    async def handle_app_exception(request: Request, exc: RasaGateException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "status": "error",
                "error_code": exc.error_code,
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "status": "error",
                "error_code": "VALIDATION_ERROR",
                "message": first.get("msg", "Invalid input."),
                "details": {
                    "field": ".".join(str(p) for p in first.get("loc", [])),
                    "provided_value": first.get("input"),
                },
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "status": "error",
                "error_code": "HTTP_ERROR",
                "message": str(exc.detail),
            },
        )