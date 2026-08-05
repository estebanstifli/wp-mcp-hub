from __future__ import annotations

from mcp import Client
from mcp.server import MCPServer
from mcp.types import ToolAnnotations


async def test_official_sdk_in_memory_client_and_server() -> None:
    server = MCPServer("remote-wordpress-fixture")

    @server.tool(annotations=ToolAnnotations(read_only_hint=True))
    async def wp_get_title() -> dict[str, str]:
        """Return a fixture WordPress title."""
        return {"title": "Example WordPress"}

    async with Client(server) as client:
        tools = await client.list_tools()
        assert [tool.name for tool in tools.tools] == ["wp_get_title"]
        result = await client.call_tool("wp_get_title", {})
        assert not result.is_error
        assert result.structured_content == {"title": "Example WordPress"}
