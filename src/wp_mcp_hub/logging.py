from __future__ import annotations

import logging
import sys
import threading
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

import structlog
from structlog.types import Processor

from wp_mcp_hub.security.redaction import redact, redact_event


@dataclass(frozen=True, slots=True)
class LogEntry:
    id: int
    timestamp: str
    level: str
    logger: str
    message: str


class LogBuffer:
    def __init__(self, capacity: int = 500) -> None:
        self._entries: deque[LogEntry] = deque(maxlen=capacity)
        self._next_id = 1
        self._lock = threading.Lock()

    def append(self, level: str, logger_name: str, message: str) -> None:
        with self._lock:
            self._entries.append(
                LogEntry(
                    id=self._next_id,
                    timestamp=datetime.now(UTC).isoformat(),
                    level=level,
                    logger=logger_name,
                    message=str(redact(message)),
                )
            )
            self._next_id += 1

    def snapshot(self, *, after: int = 0, limit: int = 200) -> list[LogEntry]:
        with self._lock:
            matching = [entry for entry in self._entries if entry.id > after]
            return matching[-limit:]


class LogBufferHandler(logging.Handler):
    def __init__(self, buffer: LogBuffer) -> None:
        super().__init__()
        self._buffer = buffer

    def emit(self, record: logging.LogRecord) -> None:
        try:
            if _is_routine_framework_log(record):
                return
            message = self.format(record)
            self._buffer.append(record.levelname, record.name, message)
        except Exception:
            self.handleError(record)


def _is_routine_framework_log(record: logging.LogRecord) -> bool:
    """Keep framework startup/polling chatter out of the user-facing log."""
    if record.name == "uvicorn.access":
        status_code: object | None = None
        if isinstance(record.args, dict):
            status_code = record.args.get("status_code")
        elif isinstance(record.args, tuple) and len(record.args) >= 5:
            status_code = record.args[4]
        try:
            return int(cast(str | int, status_code)) < 400
        except (TypeError, ValueError):
            return False
    return record.name.startswith(("uvicorn.", "alembic.")) and record.levelno < logging.ERROR


@dataclass(slots=True)
class LoggingRuntime:
    buffer: LogBuffer
    handler: LogBufferHandler

    def close(self) -> None:
        for logger_name in ("", "uvicorn.error", "uvicorn.access"):
            logging.getLogger(logger_name).removeHandler(self.handler)
        self.handler.close()


def configure_logging(level: str = "INFO") -> LoggingRuntime:
    logging.basicConfig(level=level, stream=sys.stderr, format="%(message)s")
    logging.getLogger().setLevel(level)
    buffer = LogBuffer()
    handler = LogBufferHandler(buffer)
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter("%(message)s"))
    for logger_name in ("", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(logger_name).addHandler(handler)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            cast(Processor, redact_event),
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    logging.getLogger(__name__).info("In-memory redacted log viewer initialized")
    return LoggingRuntime(buffer, handler)
