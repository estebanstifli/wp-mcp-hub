from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, cast

SENSITIVE_KEYS = re.compile(
    r"^(authorization|access[_-]?token|refresh[_-]?token|client[_-]?secret|password|"
    r"code_verifier|code|state)$",
    re.IGNORECASE,
)
BEARER = re.compile(r"(?i)Bearer\s+[A-Za-z0-9._~+/=-]+")
SECRET_VALUE = re.compile(
    r"(?i)(?<![A-Za-z0-9_-])"
    r"(access[_-]?token|refresh[_-]?token|client[_-]?secret|password|code_verifier|code|state)"
    r"(\s*[:=]\s*[\"']?)[^\s&\"',}]+"
)


def redact(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): "[REDACTED]" if SENSITIVE_KEYS.search(str(key)) else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact(item) for item in value)
    if isinstance(value, str):
        value = BEARER.sub("Bearer [REDACTED]", value)
        return SECRET_VALUE.sub(r"\1\2[REDACTED]", value)
    return value


def redact_event(_logger: object, _method: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    return cast(dict[str, Any], redact(event_dict))
