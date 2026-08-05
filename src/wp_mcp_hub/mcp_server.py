from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from mcp.server import MCPServer

from wp_mcp_hub.bootstrap import AppContainer
from wp_mcp_hub.domain.models import ToolCallRequest


def build_mcp_server(container: AppContainer) -> MCPServer:
    server = MCPServer(
        "WP MCP Hub",
        description="Vendor-neutral local gateway to configured WordPress MCP servers",
        version="0.1.0",
    )

    @server.tool()
    async def list_sites() -> list[dict[str, Any]]:
        """List configured WordPress MCP sites without exposing credentials."""
        return [site.model_dump(mode="json") for site in await container.hub.list_sites()]

    @server.tool()
    async def get_site(site_id: str) -> dict[str, Any]:
        """Get one configured site by UUID."""
        return (await container.hub.get_site(UUID(site_id))).model_dump(mode="json")

    @server.tool()
    async def test_site_connection(site_id: str) -> dict[str, Any]:
        """Test MCP connectivity and read-only discovery for one site."""
        return (await container.hub.test_site(UUID(site_id))).model_dump(mode="json")

    @server.tool()
    async def list_site_tools(site_id: str) -> list[dict[str, Any]]:
        """List and cache tools exposed by one remote MCP site."""
        return [
            tool.model_dump(mode="json")
            for tool in await container.hub.list_site_tools(UUID(site_id))
        ]

    @server.tool()
    async def call_site_tool(
        site_id: str,
        remote_tool_name: str,
        arguments: dict[str, Any],
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Call one remote tool after enforcing its local risk policy."""
        request = ToolCallRequest(
            site_id=UUID(site_id),
            remote_tool_name=remote_tool_name,
            arguments=arguments,
            timeout=timeout,
        )
        return (await container.hub.call_site_tool(request)).model_dump(mode="json")

    @server.tool()
    async def diagnose_sites(site_ids: list[str] | Literal["all"] = "all") -> list[dict[str, Any]]:
        """Run non-writing connectivity and discovery checks concurrently."""
        selected: list[UUID] | Literal["all"] = (
            "all" if site_ids == "all" else [UUID(site_id) for site_id in site_ids]
        )
        return [
            result.model_dump(mode="json")
            for result in await container.hub.diagnose_sites(selected)
        ]

    return server
