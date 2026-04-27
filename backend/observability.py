"""
Observability helpers for the RelayPay support API.

Provides:
- JSON structured logging (Cloud Logging parses JSON natively)
- Request-scoped context (request_id, session_id) via contextvars
- FastAPI middleware that injects context and logs every request/response
- Helper for emitting structured "event" log entries at key agent steps
"""

import json
import logging
import time
import uuid
from contextvars import ContextVar
from typing import Any

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

# ── Context vars — propagate per-request state through async call chains ───────

_request_id: ContextVar[str] = ContextVar("request_id", default="")
_session_id: ContextVar[str] = ContextVar("session_id", default="")


def set_request_context(request_id: str, session_id: str = "") -> None:
    _request_id.set(request_id)
    _session_id.set(session_id)


def get_request_id() -> str:
    return _request_id.get()


def get_session_id() -> str:
    return _session_id.get()


# ── JSON log formatter ─────────────────────────────────────────────────────────

class JsonFormatter(logging.Formatter):
    """Emits one JSON object per log line — Cloud Logging parses this natively."""

    # Map Python levels → Cloud Logging severity
    _SEVERITY = {
        logging.DEBUG: "DEBUG",
        logging.INFO: "INFO",
        logging.WARNING: "WARNING",
        logging.ERROR: "ERROR",
        logging.CRITICAL: "CRITICAL",
    }

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "severity": self._SEVERITY.get(record.levelno, "DEFAULT"),
            "message": record.getMessage(),
            "logger": record.name,
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
        }

        # Attach request context if available
        rid = _request_id.get()
        if rid:
            entry["request_id"] = rid
        sid = _session_id.get()
        if sid:
            entry["session_id"] = sid

        # Attach any extra structured fields the caller added
        for key, val in record.__dict__.items():
            if key.startswith("_"):
                continue
            if key not in (
                "msg", "args", "created", "filename", "funcName", "levelname",
                "levelno", "lineno", "module", "msecs", "name", "pathname",
                "process", "processName", "relativeCreated", "stack_info",
                "taskName", "thread", "threadName", "exc_info", "exc_text",
                "message",
            ):
                entry[key] = val

        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(entry, default=str)


def configure_logging(level: int = logging.INFO) -> None:
    """Replace the root handler with a JSON formatter. Call once at startup."""
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # Quiet noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


# ── Request middleware ─────────────────────────────────────────────────────────

logger = logging.getLogger(__name__)


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """
    For every HTTP request:
    1. Generates a unique request_id (or reads X-Request-ID from headers)
    2. Sets request context vars so all log lines in this request are tagged
    3. Logs request start and response with method, path, status, latency
    """

    SKIP_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}

    async def dispatch(self, request: Request, call_next):
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)

        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())[:8]
        set_request_context(request_id=request_id)

        start = time.perf_counter()
        logger.info(
            "→ %s %s",
            request.method,
            request.url.path,
            extra={"http_method": request.method, "http_path": request.url.path},
        )

        response = await call_next(request)

        latency_ms = round((time.perf_counter() - start) * 1000)
        level = logging.ERROR if response.status_code >= 500 else logging.INFO
        logger.log(
            level,
            "← %s %s %d (%dms)",
            request.method,
            request.url.path,
            response.status_code,
            latency_ms,
            extra={
                "http_method": request.method,
                "http_path": request.url.path,
                "http_status": response.status_code,
                "latency_ms": latency_ms,
            },
        )

        response.headers["X-Request-ID"] = request_id
        return response


# ── Structured event helper ────────────────────────────────────────────────────

def log_event(event: str, **fields: Any) -> None:
    """
    Emit a structured log entry for a named agent event.

    Usage:
        log_event("kb_search", query="transfer fees", hits=3, top_score=0.91)
        log_event("escalation", customer="alice@example.com", category="dispute")
    """
    logger.info(event, extra={"event": event, **fields})
