from __future__ import annotations

from typing import Any, Protocol

from wp_mcp_hub.domain.models import Site, ToolCallResult, ToolDefinition


class ProviderAdapter(Protocol):
    name: str

    async def ping(self, site: Site, headers: dict[str, str] | None = None) -> str | None: ...

    async def test(
        self, site: Site, headers: dict[str, str] | None = None
    ) -> tuple[str | None, int]: ...

    async def list_tools(
        self, site: Site, headers: dict[str, str] | None = None
    ) -> list[ToolDefinition]: ...

    async def call_tool(
        self,
        site: Site,
        tool_name: str,
        arguments: dict[str, Any],
        timeout: float | None,
        headers: dict[str, str] | None = None,
    ) -> ToolCallResult: ...
