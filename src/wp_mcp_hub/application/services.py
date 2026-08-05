from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Literal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from wp_mcp_hub.adapters.registry import AdapterRegistry
from wp_mcp_hub.config import activity_preferences
from wp_mcp_hub.domain.errors import PolicyDeniedError, SiteNotFoundError
from wp_mcp_hub.domain.models import (
    RiskClass,
    Site,
    SiteCreate,
    SiteDiagnostic,
    SiteStatus,
    ToolCallRequest,
    ToolCallResult,
    ToolDefinition,
)
from wp_mcp_hub.domain.policies import decide_tool_call
from wp_mcp_hub.security.redaction import redact
from wp_mcp_hub.security.ssrf import validate_remote_url
from wp_mcp_hub.storage.repositories import (
    CapabilityRepository,
    OperationRepository,
    SiteRepository,
    ToolPolicyRepository,
    ToolRepository,
)

RequestHeadersProvider = Callable[[UUID], Awaitable[dict[str, str]]]
logger = logging.getLogger(__name__)


class HubService:
    def __init__(
        self,
        factory: async_sessionmaker[AsyncSession],
        adapters: AdapterRegistry,
        request_headers_provider: RequestHeadersProvider,
        *,
        max_concurrency: int = 8,
    ) -> None:
        self._factory = factory
        self._adapters = adapters
        self._request_headers_provider = request_headers_provider
        self._max_concurrency = max_concurrency

    async def list_sites(self) -> list[Site]:
        async with self._factory() as session:
            return await SiteRepository(session).list()

    async def get_site(self, site_id: UUID) -> Site:
        async with self._factory() as session:
            site = await SiteRepository(session).get(site_id)
        if site is None:
            raise SiteNotFoundError(f"Site {site_id} was not found")
        return site

    async def add_site(self, value: SiteCreate) -> Site:
        await validate_remote_url(str(value.mcp_url), allow_private=value.allow_private_network)
        async with self._factory.begin() as session:
            site = await SiteRepository(session).add(value)
        logger.info("Site added: site_id=%s name=%s", site.id, site.name)
        return site

    async def delete_site(self, site_id: UUID) -> bool:
        async with self._factory.begin() as session:
            deleted = await SiteRepository(session).delete(site_id)
        logger.info("Site deletion: site_id=%s deleted=%s", site_id, deleted)
        return deleted

    async def rename_site(self, site_id: UUID, name: str) -> Site:
        cleaned_name = name.strip()
        if not cleaned_name or len(cleaned_name) > 200:
            raise ValueError("Site name must contain 1 to 200 characters")
        async with self._factory.begin() as session:
            site = await SiteRepository(session).rename(site_id, cleaned_name)
        if site is None:
            raise SiteNotFoundError(f"Site {site_id} was not found")
        logger.info("Site renamed: site_id=%s name=%s", site.id, site.name)
        return site

    async def test_site(self, site_id: UUID) -> SiteDiagnostic:
        started = time.perf_counter()
        site = await self.get_site(site_id)
        logger.info("Connection test started: site_id=%s", site.id)
        try:
            headers = await self._request_headers_provider(site.id)
            protocol, tool_count = await self._adapters.get(site.adapter).test(site, headers)
            async with self._factory.begin() as session:
                await SiteRepository(session).set_status(site.id, SiteStatus.CONNECTED)
                await CapabilityRepository(session).set(
                    site.id,
                    protocol,
                    {"tool_count": tool_count},
                )
            result = SiteDiagnostic(
                site_id=site.id,
                status="ok",
                duration_ms=round((time.perf_counter() - started) * 1000),
                protocol_version=protocol,
                tool_count=tool_count,
            )
            logger.info(
                "Connection test succeeded: site_id=%s protocol=%s tools=%s duration_ms=%s",
                site.id,
                protocol,
                tool_count,
                result.duration_ms,
            )
            return result
        except Exception as exc:
            await self._set_status(site.id, SiteStatus.ERROR)
            result = SiteDiagnostic(
                site_id=site.id,
                status="error",
                duration_ms=round((time.perf_counter() - started) * 1000),
                errors=[_safe_error(exc)],
            )
            logger.error(
                "Connection test failed: site_id=%s duration_ms=%s error=%s",
                site.id,
                result.duration_ms,
                result.errors[0],
            )
            return result

    async def ping_site(self, site_id: UUID) -> dict[str, object]:
        """Check MCP reachability without enumerating remote capabilities."""
        started = time.perf_counter()
        site = await self.get_site(site_id)
        logger.info("MCP ping started: site_id=%s", site.id)
        try:
            headers = await self._request_headers_provider(site.id)
            protocol = await self._adapters.get(site.adapter).ping(site, headers)
            duration_ms = round((time.perf_counter() - started) * 1000)
            logger.info("MCP ping succeeded: site_id=%s duration_ms=%s", site.id, duration_ms)
            return {"status": "ok", "duration_ms": duration_ms, "protocol_version": protocol}
        except Exception as exc:
            duration_ms = round((time.perf_counter() - started) * 1000)
            message = _safe_error(exc)
            logger.error(
                "MCP ping failed: site_id=%s duration_ms=%s error=%s",
                site.id,
                duration_ms,
                message,
            )
            return {"status": "error", "duration_ms": duration_ms, "error": message}

    async def list_site_tools(self, site_id: UUID, *, refresh: bool = True) -> list[ToolDefinition]:
        site = await self.get_site(site_id)
        if refresh:
            headers = await self._request_headers_provider(site.id)
            tools = await self._adapters.get(site.adapter).list_tools(site, headers)
            async with self._factory.begin() as session:
                await ToolRepository(session).replace_for_site(site.id, tools)
            logger.info("Remote tools cached: site_id=%s count=%s", site.id, len(tools))
            return tools
        async with self._factory() as session:
            return await ToolRepository(session).list(site.id)

    async def call_site_tool(self, request: ToolCallRequest) -> ToolCallResult:
        site = await self.get_site(request.site_id)
        activity_enabled, trace_level = activity_preferences()
        operation_id = (
            await self._start_operation(
                "tool_call",
                self._tool_trace_parameters(site.id, request, trace_level),
            )
            if activity_enabled
            else None
        )
        async with self._factory() as session:
            tools = ToolRepository(session)
            definition = await tools.get(site.id, request.remote_tool_name)
        if definition is None:
            await self.list_site_tools(site.id)
            async with self._factory() as session:
                definition = await ToolRepository(session).get(site.id, request.remote_tool_name)
        if definition is None:
            if operation_id:
                await self._finish_operation(
                    operation_id,
                    "failed",
                    site.id,
                    "error",
                    0,
                    {"error": "Remote tool does not exist"},
                )
            raise ValueError(f"Remote tool {request.remote_tool_name!r} does not exist")
        async with self._factory() as session:
            policy = await ToolPolicyRepository(session).get(site.id, definition.name)
        configured = policy[0] if policy and policy[2] == definition.schema_hash else None
        explicitly_allowed = bool(policy and policy[1] and policy[2] == definition.schema_hash)
        decision = decide_tool_call(definition.annotations, configured, explicitly_allowed)
        if not decision.allowed:
            logger.warning(
                "Remote tool denied: site_id=%s tool=%s classification=%s",
                site.id,
                request.remote_tool_name,
                decision.classification.value,
            )
            if operation_id:
                await self._finish_operation(
                    operation_id,
                    "failed",
                    site.id,
                    "denied",
                    0,
                    {"error": decision.reason, "classification": decision.classification.value},
                )
            raise PolicyDeniedError(decision.reason)
        headers = await self._request_headers_provider(site.id)
        logger.info(
            "Remote tool call started: site_id=%s tool=%s",
            site.id,
            request.remote_tool_name,
        )
        try:
            result = await self._adapters.get(site.adapter).call_tool(
                site,
                request.remote_tool_name,
                request.arguments,
                request.timeout,
                headers,
            )
        except Exception as exc:
            if operation_id:
                await self._finish_operation(
                    operation_id, "failed", site.id, "error", 0, {"error": _safe_error(exc)}
                )
            raise
        if operation_id:
            await self._finish_operation(
                operation_id,
                "completed" if not result.is_error else "failed",
                site.id,
                "error" if result.is_error else "ok",
                result.duration_ms,
                self._tool_trace_result(result, trace_level),
            )
        logger.info(
            "Remote tool call finished: site_id=%s tool=%s is_error=%s duration_ms=%s",
            site.id,
            request.remote_tool_name,
            result.is_error,
            result.duration_ms,
        )
        return result

    @staticmethod
    def _tool_trace_parameters(
        site_id: UUID, request: ToolCallRequest, trace_level: str
    ) -> dict[str, object]:
        parameters: dict[str, object] = {
            "site_id": str(site_id),
            "remote_tool_name": request.remote_tool_name,
            "timeout": request.timeout,
        }
        if trace_level in {"tool_and_parameters", "full"}:
            parameters["arguments"] = redact(request.arguments)
        return parameters

    @staticmethod
    def _tool_trace_result(result: ToolCallResult, trace_level: str) -> dict[str, object]:
        summary: dict[str, object] = {"is_error": result.is_error}
        if trace_level == "full":
            summary["content"] = redact(result.content)
            summary["structured_content"] = redact(result.structured_content)
        return summary

    async def diagnose_sites(self, site_ids: list[UUID] | Literal["all"]) -> list[SiteDiagnostic]:
        available = await self.list_sites()
        missing: dict[UUID, SiteDiagnostic] = {}
        if isinstance(site_ids, list):
            by_id = {site.id: site for site in available}
            sites = [by_id[site_id] for site_id in site_ids if site_id in by_id]
            missing = {
                site_id: SiteDiagnostic(
                    site_id=site_id,
                    status="error",
                    duration_ms=0,
                    errors=["Site was not found"],
                )
                for site_id in site_ids
                if site_id not in by_id
            }
        else:
            sites = available
        semaphore = asyncio.Semaphore(self._max_concurrency)

        async def guarded(site: Site) -> SiteDiagnostic:
            async with semaphore:
                return await self.test_site(site.id)

        operation_site_ids = [site.id for site in sites] if site_ids == "all" else site_ids
        operation_id = await self._start_operation(
            "diagnose", {"site_ids": [str(site_id) for site_id in operation_site_ids]}
        )
        logger.info(
            "Multi-site diagnosis started: operation_id=%s site_count=%s",
            operation_id,
            len(operation_site_ids),
        )
        checked = list(await asyncio.gather(*(guarded(site) for site in sites)))
        if site_ids == "all":
            results = checked
        else:
            checked_by_id = {result.site_id: result for result in checked}
            results = [checked_by_id.get(site_id) or missing[site_id] for site_id in site_ids]
        overall = "partial" if any(result.status != "ok" for result in results) else "completed"
        async with self._factory.begin() as session:
            operations = OperationRepository(session)
            existing_ids = {site.id for site in sites}
            for result in results:
                await operations.record_site_result(
                    operation_id,
                    result.site_id if result.site_id in existing_ids else None,
                    result.status,
                    result.duration_ms,
                    {
                        "warnings": result.warnings,
                        "errors": result.errors,
                        "protocol_version": result.protocol_version,
                        "tool_count": result.tool_count,
                    },
                )
            await operations.finish(operation_id, overall)
        logger.info(
            "Multi-site diagnosis finished: operation_id=%s status=%s",
            operation_id,
            overall,
        )
        return results

    async def set_tool_policy(
        self,
        site_id: UUID,
        tool_name: str,
        classification: RiskClass,
        explicitly_allowed: bool,
    ) -> None:
        definition = None
        async with self._factory() as session:
            definition = await ToolRepository(session).get(site_id, tool_name)
        if definition is None:
            await self.list_site_tools(site_id)
            async with self._factory() as session:
                definition = await ToolRepository(session).get(site_id, tool_name)
        if definition is None:
            raise ValueError(f"Remote tool {tool_name!r} does not exist")
        async with self._factory.begin() as session:
            await ToolPolicyRepository(session).set(
                site_id,
                tool_name,
                classification,
                explicitly_allowed,
                definition.schema_hash,
            )
        logger.info(
            "Tool policy updated: site_id=%s tool=%s classification=%s allowed=%s",
            site_id,
            tool_name,
            classification.value,
            explicitly_allowed,
        )

    async def _set_status(self, site_id: UUID, status: SiteStatus) -> None:
        async with self._factory.begin() as session:
            await SiteRepository(session).set_status(site_id, status)

    async def _start_operation(self, kind: str, parameters: dict[str, object]) -> UUID:
        async with self._factory.begin() as session:
            return await OperationRepository(session).start(kind, parameters)

    async def _finish_operation(
        self,
        operation_id: UUID,
        operation_status: str,
        site_id: UUID,
        result_status: str,
        duration_ms: int,
        result: dict[str, object],
    ) -> None:
        async with self._factory.begin() as session:
            operations = OperationRepository(session)
            await operations.record_site_result(
                operation_id,
                site_id,
                result_status,
                duration_ms,
                result,
            )
            await operations.finish(operation_id, operation_status)


def _safe_error(exc: Exception) -> str:
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError)):
        return "Connection timed out"
    return str(redact(f"{type(exc).__name__}: {exc}"))
