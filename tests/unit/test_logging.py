from __future__ import annotations

import logging

from wp_mcp_hub.logging import LogBuffer, LogBufferHandler


def test_successful_uvicorn_access_logs_are_not_shown_but_failures_are() -> None:
    buffer = LogBuffer()
    handler = LogBufferHandler(buffer)
    logger = logging.getLogger("uvicorn.access.test")
    record_success = logger.makeRecord(
        "uvicorn.access",
        logging.INFO,
        __file__,
        1,
        '%s - "%s %s HTTP/%s" %s',
        ("127.0.0.1", "GET", "/logs", "1.1", 200),
        None,
    )
    record_failure = logger.makeRecord(
        "uvicorn.access",
        logging.INFO,
        __file__,
        1,
        '%s - "%s %s HTTP/%s" %s',
        ("127.0.0.1", "GET", "/logs", "1.1", 500),
        None,
    )
    handler.emit(record_success)
    handler.emit(record_failure)
    handler.emit(
        logger.makeRecord(
            "uvicorn.error", logging.INFO, __file__, 1, "Application startup complete.", (), None
        )
    )
    entries = buffer.snapshot()
    assert len(entries) == 1
    assert "500" in entries[0].message
