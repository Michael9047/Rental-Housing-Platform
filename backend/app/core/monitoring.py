"""Prometheus metrics collection for FastAPI, Celery, and database connections.

Requires `prometheus-client` (pip install prometheus-client).
All metrics are no-ops when the package is not installed.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional prometheus-client import
# ---------------------------------------------------------------------------

try:
    from prometheus_client import (
        Counter,
        Gauge,
        Histogram,
        generate_latest,
        CONTENT_TYPE_LATEST,
    )

    _PROMETHEUS_AVAILABLE = True
except ImportError:
    _PROMETHEUS_AVAILABLE = False
    logger.info("prometheus-client not installed; metrics disabled.")

    # No-op stubs
    class _NoopMetric:
        def labels(self, **kwargs: Any) -> "_NoopMetric":
            return self

        def inc(self, amount: int = 1) -> None:  # noqa: ARG002
            pass

        def dec(self, amount: int = 1) -> None:  # noqa: ARG002
            pass

        def observe(self, value: float) -> None:  # noqa: ARG002
            pass

        def set(self, value: float) -> None:  # noqa: ARG002
            pass

    def _noop_counter(*args: Any, **kwargs: Any) -> _NoopMetric:  # noqa: ARG001
        return _NoopMetric()

    def _noop_gauge(*args: Any, **kwargs: Any) -> _NoopMetric:  # noqa: ARG001
        return _NoopMetric()

    def _noop_histogram(*args: Any, **kwargs: Any) -> _NoopMetric:  # noqa: ARG001
        return _NoopMetric()

    Counter = _noop_counter  # type: ignore
    Gauge = _noop_gauge  # type: ignore
    Histogram = _noop_histogram  # type: ignore
    generate_latest = lambda: b"# prometheus-client not installed\n"  # type: ignore
    CONTENT_TYPE_LATEST = "text/plain"


# ---------------------------------------------------------------------------
# Metrics Definitions
# ---------------------------------------------------------------------------

REQUEST_COUNT = Counter(
    "app_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)

REQUEST_LATENCY = Histogram(
    "app_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

REQUEST_IN_FLIGHT = Gauge(
    "app_requests_in_flight",
    "Currently in-flight HTTP requests",
)

CELERY_TASK_COUNT = Counter(
    "celery_tasks_total",
    "Total Celery tasks processed",
    ["task_name", "status"],
)

CELERY_TASK_LATENCY = Histogram(
    "celery_task_duration_seconds",
    "Celery task execution duration",
    ["task_name"],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0],
)

DB_POOL_SIZE = Gauge(
    "db_pool_size",
    "Database connection pool current size",
)

DB_POOL_OVERFLOW = Gauge(
    "db_pool_overflow",
    "Database connection pool overflow count",
)

DB_POOL_CHECKED_OUT = Gauge(
    "db_pool_checked_out",
    "Database connections currently checked out",
)


# ---------------------------------------------------------------------------
# Prometheus Middleware
# ---------------------------------------------------------------------------


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Collect request count, latency, and in-flight gauge for every HTTP request."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        method = request.method
        path_template = request.scope.get("route")
        if path_template is not None:
            endpoint = path_template.path if hasattr(path_template, "path") else str(path_template)
        else:
            endpoint = request.url.path

        if endpoint == "/metrics":
            return await call_next(request)

        REQUEST_IN_FLIGHT.inc()
        start = time.monotonic()
        try:
            response = await call_next(request)
            status_code = str(response.status_code)
            REQUEST_COUNT.labels(method=method, endpoint=endpoint, status_code=status_code).inc()
            REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(
                time.monotonic() - start
            )
            return response
        except Exception:
            REQUEST_COUNT.labels(method=method, endpoint=endpoint, status_code="500").inc()
            REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(
                time.monotonic() - start
            )
            raise
        finally:
            REQUEST_IN_FLIGHT.dec()


# ---------------------------------------------------------------------------
# Metrics Endpoint
# ---------------------------------------------------------------------------


def add_metrics_endpoint(app: FastAPI) -> None:
    """Mount a /metrics endpoint that serves Prometheus text format."""

    @app.get("/metrics", include_in_schema=False)
    async def metrics_endpoint() -> Response:
        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST,
        )


# ---------------------------------------------------------------------------
# Celery Signal Handlers
# ---------------------------------------------------------------------------


def install_celery_metrics() -> None:
    """Install Celery task signals to track task count and latency."""
    try:
        from celery.signals import task_postrun, task_prerun
    except ImportError:
        logger.debug("Celery not installed; skipping Celery metrics.")
        return

    _task_start_times: dict[str, float] = {}

    @task_prerun.connect
    def _on_task_prerun(sender=None, task_id=None, task=None, **kwargs):  # noqa: ARG001
        task_name = task.name if task else "unknown"
        _task_start_times[task_id] = time.monotonic()

    @task_postrun.connect
    def _on_task_postrun(sender=None, task_id=None, task=None, state=None, **kwargs):  # noqa: ARG001
        task_name = task.name if task else "unknown"
        CELERY_TASK_COUNT.labels(task_name=task_name, status=state or "success").inc()
        start_time = _task_start_times.pop(task_id, None)
        if start_time is not None:
            CELERY_TASK_LATENCY.labels(task_name=task_name).observe(
                time.monotonic() - start_time
            )

    logger.info("Celery metrics signal handlers installed.")


# ---------------------------------------------------------------------------
# Database Pool Monitoring
# ---------------------------------------------------------------------------


async def update_db_pool_metrics() -> None:
    """Poll the async engine pool status and update gauges."""
    try:
        from app.db.session import engine

        pool = engine.pool
        DB_POOL_SIZE.set(pool.size())
        DB_POOL_OVERFLOW.set(pool.overflow())
        DB_POOL_CHECKED_OUT.set(pool.checkedout())
    except Exception:
        logger.debug("Failed to update DB pool metrics.", exc_info=True)
