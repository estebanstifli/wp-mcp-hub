from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from wp_mcp_hub.domain.models import (
    RiskClass,
    Site,
    SiteCreate,
    SiteStatus,
    ToolDefinition,
    TransportKind,
)
from wp_mcp_hub.oauth.models import StoredAuthMetadata
from wp_mcp_hub.storage.models import (
    CachedToolRow,
    OperationResultRow,
    OperationRow,
    SiteAuthMetadataRow,
    SiteCapabilityRow,
    SiteRow,
    ToolPolicyRow,
)


class SiteRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, value: SiteCreate) -> Site:
        now = datetime.now(UTC)
        site = Site(
            name=value.name,
            mcp_url=str(value.mcp_url),
            transport=value.transport,
            adapter=value.adapter,
            allow_private_network=value.allow_private_network,
            created_at=now,
            updated_at=now,
        )
        self._session.add(
            SiteRow(
                id=str(site.id),
                name=site.name,
                mcp_url=site.mcp_url,
                transport=site.transport.value,
                adapter=site.adapter,
                allow_private_network=site.allow_private_network,
                enabled=site.enabled,
                status=site.status.value,
                created_at=site.created_at,
                updated_at=site.updated_at,
            )
        )
        await self._session.flush()
        return site

    async def list(self) -> list[Site]:
        rows = (await self._session.scalars(select(SiteRow).order_by(SiteRow.name))).all()
        return [self._to_domain(row) for row in rows]

    async def get(self, site_id: UUID) -> Site | None:
        row = await self._session.get(SiteRow, str(site_id))
        return self._to_domain(row) if row else None

    async def delete(self, site_id: UUID) -> bool:
        result = await self._session.execute(delete(SiteRow).where(SiteRow.id == str(site_id)))
        assert isinstance(result, CursorResult)
        return bool(result.rowcount)

    async def set_status(self, site_id: UUID, status: SiteStatus) -> None:
        row = await self._session.get(SiteRow, str(site_id))
        if row is not None:
            row.status = status.value
            row.updated_at = datetime.now(UTC)

    async def rename(self, site_id: UUID, name: str) -> Site | None:
        row = await self._session.get(SiteRow, str(site_id))
        if row is None:
            return None
        row.name = name
        row.updated_at = datetime.now(UTC)
        await self._session.flush()
        return self._to_domain(row)

    @staticmethod
    def _to_domain(row: SiteRow) -> Site:
        return Site(
            id=UUID(row.id),
            name=row.name,
            mcp_url=row.mcp_url,
            transport=TransportKind(row.transport),
            adapter=row.adapter,
            allow_private_network=row.allow_private_network,
            enabled=row.enabled,
            status=SiteStatus(row.status),
            created_at=_as_utc(row.created_at),
            updated_at=_as_utc(row.updated_at),
        )


class OperationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_recent(
        self, limit: int = 100, site_id: UUID | None = None
    ) -> list[dict[str, object]]:
        query = select(OperationRow).order_by(OperationRow.started_at.desc()).limit(limit)
        rows = (await self._session.scalars(query)).all()
        site_names = {
            row.id: row.name for row in (await self._session.scalars(select(SiteRow))).all()
        }
        operations: list[dict[str, object]] = []
        for row in rows:
            result_rows = (
                await self._session.scalars(
                    select(OperationResultRow).where(OperationResultRow.operation_id == row.id)
                )
            ).all()
            results = [
                {
                    "site_id": result.site_id,
                    "site_name": site_names.get(result.site_id) if result.site_id else None,
                    "status": result.status,
                    "duration_ms": result.duration_ms,
                    "result": json.loads(result.result_json),
                }
                for result in result_rows
            ]
            if site_id and not any(result["site_id"] == str(site_id) for result in results):
                continue
            operations.append(
                {
                    "id": row.id,
                    "kind": row.kind,
                    "status": row.status,
                    "parameters": json.loads(row.parameters_json),
                    "started_at": row.started_at,
                    "finished_at": row.finished_at,
                    "results": results,
                }
            )
        return operations

    async def add_result(self, result: OperationResultRow) -> None:
        self._session.add(result)

    async def start(self, kind: str, parameters: dict[str, object]) -> UUID:
        operation_id = uuid4()
        self._session.add(
            OperationRow(
                id=str(operation_id),
                kind=kind,
                status="running",
                parameters_json=json.dumps(parameters, separators=(",", ":")),
                started_at=datetime.now(UTC),
            )
        )
        await self._session.flush()
        return operation_id

    async def finish(self, operation_id: UUID, status: str) -> None:
        row = await self._session.get(OperationRow, str(operation_id))
        if row:
            row.status = status
            row.finished_at = datetime.now(UTC)

    async def record_site_result(
        self,
        operation_id: UUID,
        site_id: UUID | None,
        status: str,
        duration_ms: int,
        result: dict[str, object],
    ) -> None:
        self._session.add(
            OperationResultRow(
                operation_id=str(operation_id),
                site_id=str(site_id) if site_id else None,
                status=status,
                duration_ms=duration_ms,
                result_json=json.dumps(result, separators=(",", ":"), default=str),
            )
        )


class ToolRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def replace_for_site(self, site_id: UUID, tools: list[ToolDefinition]) -> None:
        await self._session.execute(
            delete(CachedToolRow).where(CachedToolRow.site_id == str(site_id))
        )
        now = datetime.now(UTC)
        for tool in tools:
            self._session.add(
                CachedToolRow(
                    site_id=str(site_id),
                    name=tool.name,
                    description=tool.description,
                    input_schema_json=json.dumps(tool.input_schema, separators=(",", ":")),
                    output_schema_json=(
                        json.dumps(tool.output_schema, separators=(",", ":"))
                        if tool.output_schema is not None
                        else None
                    ),
                    annotations_json=json.dumps(tool.annotations, separators=(",", ":")),
                    schema_hash=tool.schema_hash,
                    cached_at=now,
                )
            )

    async def get(self, site_id: UUID, name: str) -> ToolDefinition | None:
        query = select(CachedToolRow).where(
            CachedToolRow.site_id == str(site_id), CachedToolRow.name == name
        )
        row = await self._session.scalar(query)
        if row is None:
            return None
        return ToolDefinition(
            name=row.name,
            description=row.description,
            input_schema=json.loads(row.input_schema_json),
            output_schema=json.loads(row.output_schema_json) if row.output_schema_json else None,
            annotations=json.loads(row.annotations_json),
            schema_hash=row.schema_hash,
        )

    async def list(self, site_id: UUID) -> list[ToolDefinition]:
        rows = (
            await self._session.scalars(
                select(CachedToolRow)
                .where(CachedToolRow.site_id == str(site_id))
                .order_by(CachedToolRow.name)
            )
        ).all()
        return [
            ToolDefinition(
                name=row.name,
                description=row.description,
                input_schema=json.loads(row.input_schema_json),
                output_schema=(
                    json.loads(row.output_schema_json) if row.output_schema_json else None
                ),
                annotations=json.loads(row.annotations_json),
                schema_hash=row.schema_hash,
            )
            for row in rows
        ]


class CapabilityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def set(
        self,
        site_id: UUID,
        protocol_version: str | None,
        capabilities: dict[str, object],
    ) -> None:
        row = await self._session.get(SiteCapabilityRow, str(site_id))
        if row is None:
            self._session.add(
                SiteCapabilityRow(
                    site_id=str(site_id),
                    protocol_version=protocol_version,
                    capabilities_json=json.dumps(capabilities, separators=(",", ":")),
                    updated_at=datetime.now(UTC),
                )
            )
        else:
            row.protocol_version = protocol_version
            row.capabilities_json = json.dumps(capabilities, separators=(",", ":"))
            row.updated_at = datetime.now(UTC)


class ToolPolicyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, site_id: UUID, tool_name: str) -> tuple[RiskClass, bool, str | None] | None:
        query = select(ToolPolicyRow).where(
            ToolPolicyRow.site_id == str(site_id), ToolPolicyRow.tool_name == tool_name
        )
        row = await self._session.scalar(query)
        if row is None:
            return None
        return RiskClass(row.classification), row.explicitly_allowed, row.schema_hash

    async def set(
        self,
        site_id: UUID,
        tool_name: str,
        classification: RiskClass,
        explicitly_allowed: bool,
        schema_hash: str | None,
    ) -> None:
        query = select(ToolPolicyRow).where(
            ToolPolicyRow.site_id == str(site_id), ToolPolicyRow.tool_name == tool_name
        )
        row = await self._session.scalar(query)
        if row is None:
            self._session.add(
                ToolPolicyRow(
                    site_id=str(site_id),
                    tool_name=tool_name,
                    classification=classification.value,
                    explicitly_allowed=explicitly_allowed,
                    schema_hash=schema_hash,
                    updated_at=datetime.now(UTC),
                )
            )
        else:
            row.classification = classification.value
            row.explicitly_allowed = explicitly_allowed
            row.schema_hash = schema_hash
            row.updated_at = datetime.now(UTC)


class AuthMetadataRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, site_id: UUID) -> StoredAuthMetadata | None:
        row = await self._session.get(SiteAuthMetadataRow, str(site_id))
        if row is None:
            return None
        return self._to_domain(row)

    async def upsert(self, value: StoredAuthMetadata) -> None:
        row = await self._session.get(SiteAuthMetadataRow, str(value.site_id))
        data = {
            "issuer": value.issuer,
            "resource": value.resource,
            "resource_metadata_url": value.resource_metadata_url,
            "authorization_endpoint": value.authorization_endpoint,
            "token_endpoint": value.token_endpoint,
            "registration_endpoint": value.registration_endpoint,
            "revocation_endpoint": value.revocation_endpoint,
            "client_id": value.client_id,
            "registration_method": value.registration_method,
            "scopes_requested": " ".join(value.scopes_requested),
            "scopes_granted": " ".join(value.scopes_granted),
        }
        if row is None:
            self._session.add(SiteAuthMetadataRow(site_id=str(value.site_id), **data))
        else:
            for key, item in data.items():
                setattr(row, key, item)
        await self._session.flush()

    async def update_tokens(
        self,
        site_id: UUID,
        *,
        access_ref: str,
        refresh_ref: str | None,
        client_secret_ref: str | None,
        expires_at: datetime | None,
        scopes: list[str],
    ) -> None:
        row = await self._session.get(SiteAuthMetadataRow, str(site_id))
        if row is None:
            row = SiteAuthMetadataRow(site_id=str(site_id))
            self._session.add(row)
        row.access_token_ref = access_ref
        if refresh_ref:
            row.refresh_token_ref = refresh_ref
        if client_secret_ref:
            row.client_secret_ref = client_secret_ref
        row.token_expires_at = expires_at
        row.scopes_granted = " ".join(scopes)
        await self._session.flush()

    async def clear_credentials(self, site_id: UUID) -> None:
        row = await self._session.get(SiteAuthMetadataRow, str(site_id))
        if row:
            row.access_token_ref = None
            row.refresh_token_ref = None
            row.client_secret_ref = None
            row.token_expires_at = None

    @staticmethod
    def _to_domain(row: SiteAuthMetadataRow) -> StoredAuthMetadata:
        return StoredAuthMetadata(
            site_id=UUID(row.site_id),
            issuer=row.issuer,
            resource=row.resource,
            resource_metadata_url=row.resource_metadata_url,
            authorization_endpoint=row.authorization_endpoint,
            token_endpoint=row.token_endpoint,
            registration_endpoint=row.registration_endpoint,
            revocation_endpoint=row.revocation_endpoint,
            client_id=row.client_id,
            registration_method=row.registration_method,
            scopes_requested=(row.scopes_requested or "").split(),
            scopes_granted=(row.scopes_granted or "").split(),
            token_expires_at=(_as_utc(row.token_expires_at) if row.token_expires_at else None),
            access_token_ref=row.access_token_ref,
            refresh_token_ref=row.refresh_token_ref,
            client_secret_ref=row.client_secret_ref,
        )


class SqlAlchemyAuthMetadataStore:
    """Transaction-scoped facade safe to share between concurrent services."""

    def __init__(self, factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = factory

    async def get(self, site_id: UUID) -> StoredAuthMetadata | None:
        async with self._factory() as session:
            return await AuthMetadataRepository(session).get(site_id)

    async def upsert(self, value: StoredAuthMetadata) -> None:
        async with self._factory.begin() as session:
            await AuthMetadataRepository(session).upsert(value)

    async def update_tokens(
        self,
        site_id: UUID,
        *,
        access_ref: str,
        refresh_ref: str | None,
        client_secret_ref: str | None,
        expires_at: datetime | None,
        scopes: list[str],
    ) -> None:
        async with self._factory.begin() as session:
            await AuthMetadataRepository(session).update_tokens(
                site_id,
                access_ref=access_ref,
                refresh_ref=refresh_ref,
                client_secret_ref=client_secret_ref,
                expires_at=expires_at,
                scopes=scopes,
            )

    async def clear_credentials(self, site_id: UUID) -> None:
        async with self._factory.begin() as session:
            await AuthMetadataRepository(session).clear_credentials(site_id)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value
