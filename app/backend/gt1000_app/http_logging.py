from __future__ import annotations

import time
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from gt1000_app.app_logging import app_log


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Response]) -> Response:
        started = time.monotonic()
        path = request.url.path
        skip_body_log = path.startswith("/api/chat") or path.startswith("/api/logs/client")
        try:
            response = await call_next(request)
            duration_ms = round((time.monotonic() - started) * 1000, 2)
            app_log(
                "info" if response.status_code < 400 else "warning",
                "http",
                f"{request.method} {path} -> {response.status_code}",
                method=request.method,
                path=path,
                status=response.status_code,
                durationMs=duration_ms,
                query=str(request.url.query) if request.url.query else None,
            )
            return response
        except Exception as error:
            duration_ms = round((time.monotonic() - started) * 1000, 2)
            app_log(
                "error",
                "http",
                f"{request.method} {path} failed",
                method=request.method,
                path=path,
                durationMs=duration_ms,
                error=str(error),
                skipBody=skip_body_log,
            )
            raise
