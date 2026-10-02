from __future__ import annotations

import asyncio
import socket
from contextlib import closing
from typing import Any
from uuid import uuid4

import pytest
import uvicorn
from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from wp_mcp_hub.adapters.generic_mcp import GenericMcpAdapter
from wp_mcp_hub.domain.models import Site, TransportKind


def unused_port() -> int:
    with closing(socket.socket()) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("legacy", "transport"),
    [
        (False, TransportKind.STREAMABLE_HTTP),
        (True, TransportKind.STREAMABLE_HTTP),
        (True, TransportKind.SSE),
    ],
)
async def test_generic_adapter_uses_streamable_http(legacy: bool, transport: TransportKind) -> None:
    port = unused_port()
    remote = MCPServer("remote-wordpress")

    @remote.tool(annotations=ToolAnnotations(read_only_hint=True))
    async def wp_site_name() -> dict[str, str]:
        return {"name": "Fixture"}

    app = remote.sse_app() if transport is TransportKind.SSE else remote.streamable_http_app()
    methods: list[str] = []

    async def compatibility_app(scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] == "http" and scope["method"] == "POST":
            headers = dict(scope["headers"])
            methods.append(headers.get(b"mcp-method", b"").decode())
            if legacy and headers.get(b"mcp-protocol-version") == b"2026-07-28":
                await send({"type": "http.response.start", "status": 400, "headers": []})
                await send({"type": "http.response.body", "body": b"Initialize first"})
                return
        await app(scope, receive, send)

    uvicorn_server = uvicorn.Server(
        uvicorn.Config(
            compatibility_app,
            host="127.0.0.1",
            port=port,
            log_level="critical",
        )
    )
    task = asyncio.create_task(uvicorn_server.serve())
    for _ in range(100):
        if uvicorn_server.started:
            break
        await asyncio.sleep(0.01)
    try:
        site = Site(
            id=uuid4(),
            name="Fixture",
            mcp_url=f"http://127.0.0.1:{port}/{'sse' if transport is TransportKind.SSE else 'mcp'}",
            transport=transport,
            allow_private_network=True,
        )
        adapter = GenericMcpAdapter(default_timeout=2, read_retry_attempts=0)
        expected = "2025-11-25" if legacy else "2026-07-28"
        assert await adapter.ping(site) == expected
        assert "tools/list" not in methods
        assert await adapter.test(site) == (expected, 1)
        tools = await adapter.list_tools(site)
        assert [tool.name for tool in tools] == ["wp_site_name"]
        assert tools[0].annotations["readOnlyHint"] is True
        result = await adapter.call_tool(site, "wp_site_name", {}, timeout=2)
        assert result.structured_content == {"name": "Fixture"}
        assert not result.is_error
    finally:
        uvicorn_server.should_exit = True
        await asyncio.wait_for(task, timeout=5)


@pytest.mark.asyncio
async def test_generic_adapter_reports_down_server_quickly() -> None:
    port = unused_port()
    site = Site(
        id=uuid4(),
        name="Down",
        mcp_url=f"http://127.0.0.1:{port}/mcp",
        transport=TransportKind.STREAMABLE_HTTP,
        allow_private_network=True,
    )
    with pytest.raises(ExceptionGroup):
        await GenericMcpAdapter(default_timeout=0.2).test(site)
