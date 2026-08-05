from typing import cast

import pytest

from wp_mcp_hub.bootstrap import AppContainer
from wp_mcp_hub.mcp_server import build_mcp_server


@pytest.mark.asyncio
async def test_local_server_exposes_only_six_high_level_tools() -> None:
    server = build_mcp_server(cast(AppContainer, object()))
    assert {tool.name for tool in await server.list_tools()} == {
        "list_sites",
        "get_site",
        "test_site_connection",
        "list_site_tools",
        "call_site_tool",
        "diagnose_sites",
    }
