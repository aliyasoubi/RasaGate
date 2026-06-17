# app/core/auth.py
"""
Optional API key authentication.

If `api_key` is set in settings (via .env), every request to /api/*
must include the header:  X-API-Key: <your_key>

If `api_key` is None / empty, auth is disabled (useful for local dev).
"""
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings

_UNPROTECTED_PREFIXES = ("/health", "/docs", "/openapi.json", "/redoc")


class ApiKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Auth disabled — let everything through
        if not settings.api_key:
            return await call_next(request)

        # Public routes — no key required
        if any(request.url.path.startswith(p) for p in _UNPROTECTED_PREFIXES):
            return await call_next(request)

        provided = request.headers.get("X-API-Key", "")
        if provided != settings.api_key:
            return JSONResponse(
                status_code=401,
                content={
                    "status": "error",
                    "error_code": "UNAUTHORIZED",
                    "message": "Missing or invalid X-API-Key header.",
                },
            )

        return await call_next(request)