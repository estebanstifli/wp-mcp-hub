from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from wp_mcp_hub.paths import AppPaths

_DEFAULT_WEB_PORT = 8766
_DEFAULT_ACTIVITY_ENABLED = True
_DEFAULT_ACTIVITY_TRACE_LEVEL = "tool"


def _web_settings_path() -> Path:
    return AppPaths.discover().config_dir / "web-settings.json"


def _web_preferences() -> dict[str, object]:
    """Read non-secret local preferences; malformed files are ignored."""
    try:
        value = json.loads(_web_settings_path().read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _configured_web_port() -> int:
    value = _web_preferences().get("web_port")
    return value if isinstance(value, int) and 1024 <= value <= 65535 else _DEFAULT_WEB_PORT


def save_web_port(port: int) -> None:
    """Persist a non-secret web preference for the next process start."""
    if not 1024 <= port <= 65535:
        raise ValueError("web_port must be between 1024 and 65535")
    path = _web_settings_path()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    preferences = _web_preferences()
    preferences["web_port"] = port
    temporary.write_text(json.dumps(preferences) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def activity_preferences() -> tuple[bool, str]:
    preferences = _web_preferences()
    enabled = preferences.get("activity_enabled", _DEFAULT_ACTIVITY_ENABLED)
    trace_level = preferences.get("activity_trace_level", _DEFAULT_ACTIVITY_TRACE_LEVEL)
    return (
        enabled if isinstance(enabled, bool) else _DEFAULT_ACTIVITY_ENABLED,
        trace_level
        if trace_level in {"tool", "tool_and_parameters", "full"}
        else _DEFAULT_ACTIVITY_TRACE_LEVEL,
    )


def save_activity_preferences(enabled: bool, trace_level: str) -> None:
    if trace_level not in {"tool", "tool_and_parameters", "full"}:
        raise ValueError("Unsupported activity trace level")
    path = _web_settings_path()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    preferences = _web_preferences()
    preferences["activity_enabled"] = enabled
    preferences["activity_trace_level"] = trace_level
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(preferences) + "\n", encoding="utf-8")
    os.replace(temporary, path)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="WP_MCP_HUB_", extra="ignore")

    database_path: Path | None = None
    web_host: str = "127.0.0.1"
    web_port: int = Field(default_factory=_configured_web_port, ge=1024, le=65535)
    connect_timeout_seconds: float = Field(default=10.0, gt=0, le=300)
    request_timeout_seconds: float = Field(default=30.0, gt=0, le=600)
    max_concurrency: int = Field(default=8, ge=1, le=64)
    read_retry_attempts: int = Field(default=1, ge=0, le=5)
    token_refresh_skew_seconds: int = Field(default=60, ge=5, le=600)
    log_level: str = "INFO"

    def resolved_database_path(self, paths: AppPaths) -> Path:
        return self.database_path or paths.data_dir / "hub.sqlite3"
