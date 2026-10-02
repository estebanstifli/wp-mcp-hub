from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, JsonValue


class TransportKind(StrEnum):
    STREAMABLE_HTTP = "streamable_http"
    SSE = "sse"


class RiskClass(StrEnum):
    READ = "read"
    WRITE = "write"
    DESTRUCTIVE = "destructive"
    UNKNOWN = "unknown"


class SiteStatus(StrEnum):
    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    ERROR = "error"


class SiteCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    mcp_url: HttpUrl
    transport: TransportKind = TransportKind.STREAMABLE_HTTP
    adapter: str = "generic"
    allow_private_network: bool = False


class Site(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    schema_version: Literal["1.0"] = "1.0"
    id: UUID = Field(default_factory=uuid4)
    name: str
    mcp_url: str
    transport: TransportKind
    adapter: str = "generic"
    allow_private_network: bool = False
    enabled: bool = True
    status: SiteStatus = SiteStatus.DISCONNECTED
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ToolDefinition(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    name: str
    description: str | None = None
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] | None = None
    annotations: dict[str, Any] = Field(default_factory=dict)
    schema_hash: str


class SiteDiagnostic(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    site_id: UUID
    status: str
    duration_ms: int = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    protocol_version: str | None = None
    tool_count: int | None = None
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ToolCallRequest(BaseModel):
    site_id: UUID
    remote_tool_name: str = Field(min_length=1, max_length=300)
    arguments: dict[str, Any] = Field(default_factory=dict)
    timeout: float | None = Field(default=None, gt=0, le=600)


class ToolCallResult(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    site_id: UUID
    remote_tool_name: str
    is_error: bool
    content: list[dict[str, Any]] = Field(default_factory=list)
    structured_content: JsonValue = None
    duration_ms: int = Field(ge=0)
