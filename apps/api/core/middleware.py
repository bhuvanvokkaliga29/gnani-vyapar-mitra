"""FastAPI Correlation and Telemetry Middleware for Phase 9.4."""

import time
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
import structlog

from services.observability.correlation import (
    validate_request_id,
    set_correlation_context,
    reset_correlation_context,
)
from services.observability.metrics import RuntimeMetricsRegistry


class CorrelationMiddleware(BaseHTTPMiddleware):
    """Async-safe HTTP middleware enforcing end-to-end request correlation and observability.
    
    Invariants:
    1. Extracts or generates a valid, bounded request_id (req_...).
    2. Binds request_id to structlog contextvars and correlation context.
    3. Guarantees zero context leak across concurrent requests via token reset.
    4. Sets X-Request-ID on every response header.
    5. Records safe, bounded operational request metrics.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        raw_header = request.headers.get("X-Request-ID")
        req_id = validate_request_id(raw_header)

        # Bind to structlog contextvars
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=req_id)

        token = set_correlation_context(request_id=req_id)
        start_time = time.perf_counter()

        try:
            response = await call_next(request)
            latency_ms = (time.perf_counter() - start_time) * 1000.0

            # Record safe request metric
            endpoint_path = request.url.path
            # Bounded endpoint group label
            component = "api"
            status_code = str(response.status_code)
            RuntimeMetricsRegistry.record_request(
                component=component,
                status=status_code,
                latency_ms=latency_ms
            )

            response.headers["X-Request-ID"] = req_id
            return response
        except Exception as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            RuntimeMetricsRegistry.record_request_error(
                component="api",
                error_type=exc.__class__.__name__
            )
            raise
        finally:
            reset_correlation_context(token)
            structlog.contextvars.clear_contextvars()
