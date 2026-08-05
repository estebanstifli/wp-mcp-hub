from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest

from wp_mcp_hub.adapters.registry import AdapterRegistry
from wp_mcp_hub.application.services import HubService
from wp_mcp_hub.domain.models import Site, SiteCreate, ToolCallResult, ToolDefinition
from wp_mcp_hub.storage.database import create_engine, create_schema, session_factory
from wp_mcp_hub.storage.repositories import SiteRepository


class ConcurrentAdapter:
    name = "generic"

    def __init__(self, failing: set[UUID] | None = None) -> None:
        self.active = 0
        self.maximum = 0
        self.failing = failing or set()

    async def test(self, site: Site, headers: dict[str, str] | None = None) -> tuple[str, int]:
        self.active += 1
        self.maximum = max(self.maximum, self.active)
        try:
            await asyncio.sleep(0.1)
            if site.id in self.failing:
                raise TimeoutError
            return "2026-07-28", 1
        finally:
            self.active -= 1

    async def ping(self, site: Site, headers: dict[str, str] | None = None) -> str:
        return "2026-07-28"

    async def list_tools(
        self, site: Site, headers: dict[str, str] | None = None
    ) -> list[ToolDefinition]:
        return []

    async def call_tool(
        self,
        site: Site,
        tool_name: str,
        arguments: dict[str, Any],
        timeout: float | None,
        headers: dict[str, str] | None = None,
    ) -> ToolCallResult:
        raise NotImplementedError


@pytest.mark.asyncio
async def test_diagnosis_is_bounded_and_isolates_failures(tmp_path: Path) -> None:
    engine = create_engine(tmp_path / "diagnosis.sqlite3")
    await create_schema(engine)
    factory = session_factory(engine)
    async with factory.begin() as session:
        repo = SiteRepository(session)
        sites = [
            await repo.add(
                SiteCreate.model_validate(
                    {
                        "name": f"Site {index}",
                        "mcp_url": f"http://127.0.0.1:{8000 + index}/mcp",
                        "allow_private_network": True,
                    }
                )
            )
            for index in range(4)
        ]
    adapter = ConcurrentAdapter({sites[2].id})

    async def no_headers(_site_id: UUID) -> dict[str, str]:
        return {}

    service = HubService(
        factory,
        AdapterRegistry([adapter]),
        no_headers,
        max_concurrency=2,
    )
    results = await service.diagnose_sites("all")
    assert len(results) == 4
    assert adapter.maximum == 2
    assert sum(result.status == "error" for result in results) == 1
    assert any("timed out" in error for result in results for error in result.errors)
    missing_id = uuid4()
    selected = await service.diagnose_sites([sites[0].id, missing_id])
    assert [result.site_id for result in selected] == [sites[0].id, missing_id]
    assert selected[1].errors == ["Site was not found"]
    await engine.dispose()
