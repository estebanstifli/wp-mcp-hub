from __future__ import annotations

import asyncio
import hashlib
import json
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any, TypeVar

import httpx2
from mcp import Client
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamable_http_client

from wp_mcp_hub.domain.models import Site, ToolCallResult, ToolDefinition, TransportKind
from wp_mcp_hub.security.ssrf import validate_remote_url

T = TypeVar("T")


class GenericMcpAdapter:
    name = "generic"

    def __init__(self, default_timeout: float = 30.0, read_retry_attempts: int = 1) -> None:
        self._default_timeout = default_timeout
        self._read_retry_attempts = read_retry_attempts

    @asynccontextmanager
    async def _client(
        self, site: Site, headers: dict[str, str] | None, timeout: float | None = None
    ) -> AsyncIterator[Client]:
        await validate_remote_url(site.mcp_url, allow_private=site.allow_private_network)
        headers = headers or {}
        request_timeout = timeout or self._default_timeout
        async with httpx2.AsyncClient(
            headers=headers,
            timeout=httpx2.Timeout(request_timeout),
            follow_redirects=False,
        ) as http_client:
            if site.transport is TransportKind.SSE:
                transport = sse_client(
                    site.mcp_url,
                    headers=headers,
                    timeout=request_timeout,
                    sse_read_timeout=request_timeout,
                )
            else:
                transport = streamable_http_client(site.mcp_url, http_client=http_client)
            async with Client(transport, read_timeout_seconds=request_timeout) as client:
                yield client

    async def test(
        self, site: Site, headers: dict[str, str] | None = None
    ) -> tuple[str | None, int]:
        return await self._retry_read(lambda: self._test_once(site, headers))

    async def ping(self, site: Site, headers: dict[str, str] | None = None) -> str | None:
        """Perform only the MCP ping handshake; do not discover or cache tools."""
        return await self._retry_read(lambda: self._ping_once(site, headers))

    async def _ping_once(self, site: Site, headers: dict[str, str] | None = None) -> str | None:
        async with self._client(site, headers) as client:
            await client.send_ping()
            return client.protocol_version

    async def _test_once(
        self, site: Site, headers: dict[str, str] | None = None
    ) -> tuple[str | None, int]:
        async with self._client(site, headers) as client:
            await client.send_ping()
            tools = await client.list_tools()
            return client.protocol_version, len(tools.tools)

    async def list_tools(
        self, site: Site, headers: dict[str, str] | None = None
    ) -> list[ToolDefinition]:
        return await self._retry_read(lambda: self._list_tools_once(site, headers))

    async def _list_tools_once(
        self, site: Site, headers: dict[str, str] | None = None
    ) -> list[ToolDefinition]:
        async with self._client(site, headers) as client:
            result = await client.list_tools()
        definitions: list[ToolDefinition] = []
        for tool in result.tools:
            raw = tool.model_dump(mode="json", by_alias=True, exclude_none=True)
            schema = raw.get("inputSchema", {})
            fingerprint = hashlib.sha256(
                json.dumps(raw, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            definitions.append(
                ToolDefinition(
                    name=tool.name,
                    description=tool.description,
                    input_schema=schema,
                    output_schema=raw.get("outputSchema"),
                    annotations=raw.get("annotations") or {},
                    schema_hash=fingerprint,
                )
            )
        return definitions

    async def _retry_read(self, operation: Callable[[], Awaitable[T]]) -> T:
        for attempt in range(self._read_retry_attempts + 1):
            try:
                return await operation()
            except Exception:
                if attempt >= self._read_retry_attempts:
                    raise
                await asyncio.sleep(0.2 * (2**attempt))
        raise AssertionError("unreachable")

    async def call_tool(
        self,
        site: Site,
        tool_name: str,
        arguments: dict[str, Any],
        timeout: float | None,
        headers: dict[str, str] | None = None,
    ) -> ToolCallResult:
        started = time.perf_counter()
        async with self._client(site, headers, timeout) as client:
            result = await client.call_tool(tool_name, arguments, read_timeout_seconds=timeout)
        raw = result.model_dump(mode="json", by_alias=True, exclude_none=True)
        return ToolCallResult(
            site_id=site.id,
            remote_tool_name=tool_name,
            is_error=bool(raw.get("isError", False)),
            content=raw.get("content", []),
            structured_content=raw.get("structuredContent"),
            duration_ms=round((time.perf_counter() - started) * 1000),
        )
