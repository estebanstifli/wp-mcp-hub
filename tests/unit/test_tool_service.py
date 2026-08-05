from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

import pytest

from wp_mcp_hub.adapters.registry import AdapterRegistry
from wp_mcp_hub.application.services import HubService
from wp_mcp_hub.domain.errors import PolicyDeniedError
from wp_mcp_hub.domain.models import (
    RiskClass,
    Site,
    SiteCreate,
    ToolCallRequest,
    ToolCallResult,
    ToolDefinition,
)
from wp_mcp_hub.storage.database import create_engine, create_schema, session_factory
from wp_mcp_hub.storage.repositories import SiteRepository


class MutableToolAdapter:
    name = "generic"

    def __init__(self) -> None:
        self.schema_hash = "version-1"

    async def test(self, site: Site, headers: dict[str, str] | None = None) -> tuple[str, int]:
        return "2026-07-28", 1

    async def ping(self, site: Site, headers: dict[str, str] | None = None) -> str:
        return "2026-07-28"

    async def list_tools(
        self, site: Site, headers: dict[str, str] | None = None
    ) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="wp_update_post",
                input_schema={"type": "object"},
                annotations={"readOnlyHint": False},
                schema_hash=self.schema_hash,
            )
        ]

    async def call_tool(
        self,
        site: Site,
        tool_name: str,
        arguments: dict[str, Any],
        timeout: float | None,
        headers: dict[str, str] | None = None,
    ) -> ToolCallResult:
        return ToolCallResult(
            site_id=site.id,
            remote_tool_name=tool_name,
            is_error=False,
            structured_content={"updated": True},
            duration_ms=1,
        )


@pytest.mark.asyncio
async def test_tool_calls_are_allowed_by_default_and_honor_current_explicit_policies(
    tmp_path: Path,
) -> None:
    engine = create_engine(tmp_path / "policy.sqlite3")
    await create_schema(engine)
    factory = session_factory(engine)
    async with factory.begin() as session:
        site = await SiteRepository(session).add(
            SiteCreate.model_validate(
                {
                    "name": "Site",
                    "mcp_url": "http://127.0.0.1:9000/mcp",
                    "allow_private_network": True,
                }
            )
        )
    adapter = MutableToolAdapter()

    async def no_headers(_site_id: UUID) -> dict[str, str]:
        return {}

    service = HubService(factory, AdapterRegistry([adapter]), no_headers)
    await service.list_site_tools(site.id)
    request = ToolCallRequest(
        site_id=site.id,
        remote_tool_name="wp_update_post",
        arguments={"post_id": 1},
    )
    assert not (await service.call_site_tool(request)).is_error
    await service.set_tool_policy(
        site.id, "wp_update_post", RiskClass.WRITE, explicitly_allowed=False
    )
    with pytest.raises(PolicyDeniedError):
        await service.call_site_tool(request)
    await service.set_tool_policy(
        site.id, "wp_update_post", RiskClass.WRITE, explicitly_allowed=True
    )
    assert not (await service.call_site_tool(request)).is_error
    adapter.schema_hash = "version-2"
    await service.list_site_tools(site.id)
    assert not (await service.call_site_tool(request)).is_error
    await engine.dispose()
