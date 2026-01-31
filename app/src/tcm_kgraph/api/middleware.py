"""FastAPI middleware for logging and error handling."""

import time
import uuid
from typing import Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from tcm_kgraph.core.exceptions import TCMKGraphError
from tcm_kgraph.core.logging import get_logger


logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging HTTP requests and responses."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with logging."""
        # Generate request ID
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id

        # Log request
        start_time = time.perf_counter()
        logger.info(
            f"[{request_id}] {request.method} {request.url.path}",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "client": request.client.host if request.client else None,
            },
        )

        # Process request
        response = await call_next(request)

        # Log response
        duration = time.perf_counter() - start_time
        logger.info(
            f"[{request_id}] {response.status_code} ({duration:.3f}s)",
            extra={
                "request_id": request_id,
                "status_code": response.status_code,
                "duration_ms": duration * 1000,
            },
        )

        # Add headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{duration:.3f}s"

        return response


async def tcm_exception_handler(request: Request, exc: TCMKGraphError) -> JSONResponse:
    """Handle TCMKGraphError exceptions."""
    request_id = getattr(request.state, "request_id", "unknown")

    logger.error(
        f"[{request_id}] {exc.__class__.__name__}: {exc.message}",
        extra={
            "request_id": request_id,
            "error_type": exc.__class__.__name__,
            "details": exc.details,
        },
    )

    # Map exception types to HTTP status codes
    status_code = 500
    if "Configuration" in exc.__class__.__name__:
        status_code = 500
    elif "NotFound" in exc.__class__.__name__:
        status_code = 404
    elif "Validation" in exc.__class__.__name__:
        status_code = 400
    elif "Authentication" in exc.__class__.__name__:
        status_code = 401

    return JSONResponse(
        status_code=status_code,
        content={
            "error": exc.__class__.__name__,
            "message": exc.message,
            "details": exc.details,
            "request_id": request_id,
        },
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions."""
    request_id = getattr(request.state, "request_id", "unknown")

    logger.exception(
        f"[{request_id}] Unexpected error: {exc}",
        extra={"request_id": request_id},
    )

    return JSONResponse(
        status_code=500,
        content={
            "error": "InternalServerError",
            "message": "An unexpected error occurred",
            "request_id": request_id,
        },
    )


def setup_middleware(app: FastAPI) -> None:
    """Configure middleware and exception handlers for the application."""
    # Add request logging middleware
    app.add_middleware(RequestLoggingMiddleware)

    # Register exception handlers
    app.add_exception_handler(TCMKGraphError, tcm_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
