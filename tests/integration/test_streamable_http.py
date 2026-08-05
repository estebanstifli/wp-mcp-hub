from __future__ import annotations

import asyncio
import socket
from contextlib import closing
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
async def test_generic_adapter_uses_streamable_http() -> None:
    port = unused_port()
    remote = MCPServer("remote-wordpress")

    @remote.tool(annotations=ToolAnnotations(read_only_hint=True))
    async def wp_site_name() -> dict[str, str]:
        return {"name": "Fixture"}

    uvicorn_server = uvicorn.Server(
        uvicorn.Config(
            remote.streamable_http_app(),
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
            mcp_url=f"http://127.0.0.1:{port}/mcp",
            transport=TransportKind.STREAMABLE_HTTP,
            allow_private_network=True,
        )
        tools = await GenericMcpAdapter(default_timeout=2).list_tools(site)
        assert [tool.name for tool in tools] == ["wp_site_name"]
        assert tools[0].annotations["readOnlyHint"] is True
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
