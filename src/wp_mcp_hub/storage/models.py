from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class SiteRow(Base):
    __tablename__ = "sites"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    mcp_url: Mapped[str] = mapped_column(Text)
    transport: Mapped[str] = mapped_column(String(32), default="streamable_http")
    adapter: Mapped[str] = mapped_column(String(100), default="generic")
    allow_private_network: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(32), default="disconnected")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SiteAuthMetadataRow(Base):
    __tablename__ = "site_auth_metadata"

    site_id: Mapped[str] = mapped_column(
        ForeignKey("sites.id", ondelete="CASCADE"), primary_key=True
    )
    issuer: Mapped[str | None] = mapped_column(Text)
    resource: Mapped[str | None] = mapped_column(Text)
    resource_metadata_url: Mapped[str | None] = mapped_column(Text)
    authorization_endpoint: Mapped[str | None] = mapped_column(Text)
    token_endpoint: Mapped[str | None] = mapped_column(Text)
    registration_endpoint: Mapped[str | None] = mapped_column(Text)
    revocation_endpoint: Mapped[str | None] = mapped_column(Text)
    client_id: Mapped[str | None] = mapped_column(Text)
    registration_method: Mapped[str | None] = mapped_column(String(32))
    scopes_requested: Mapped[str | None] = mapped_column(Text)
    scopes_granted: Mapped[str | None] = mapped_column(Text)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    access_token_ref: Mapped[str | None] = mapped_column(Text)
    refresh_token_ref: Mapped[str | None] = mapped_column(Text)
    client_secret_ref: Mapped[str | None] = mapped_column(Text)


class SiteCapabilityRow(Base):
    __tablename__ = "site_capabilities"

    site_id: Mapped[str] = mapped_column(
        ForeignKey("sites.id", ondelete="CASCADE"), primary_key=True
    )
    protocol_version: Mapped[str | None] = mapped_column(String(32))
    capabilities_json: Mapped[str] = mapped_column(Text, default="{}")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CachedToolRow(Base):
    __tablename__ = "cached_tools"
    __table_args__ = (UniqueConstraint("site_id", "name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    input_schema_json: Mapped[str] = mapped_column(Text)
    output_schema_json: Mapped[str | None] = mapped_column(Text)
    annotations_json: Mapped[str] = mapped_column(Text, default="{}")
    schema_hash: Mapped[str] = mapped_column(String(64))
    cached_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ToolPolicyRow(Base):
    __tablename__ = "tool_policies"
    __table_args__ = (UniqueConstraint("site_id", "tool_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), index=True)
    tool_name: Mapped[str] = mapped_column(String(300))
    classification: Mapped[str] = mapped_column(String(32), default="unknown")
    explicitly_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    schema_hash: Mapped[str | None] = mapped_column(String(64))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class OperationRow(Base):
    __tablename__ = "operations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    kind: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))
    parameters_json: Mapped[str] = mapped_column(Text, default="{}")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OperationResultRow(Base):
    __tablename__ = "operation_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    operation_id: Mapped[str] = mapped_column(
        ForeignKey("operations.id", ondelete="CASCADE"), index=True
    )
    site_id: Mapped[str | None] = mapped_column(ForeignKey("sites.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(32))
    duration_ms: Mapped[int] = mapped_column(Integer)
    result_json: Mapped[str] = mapped_column(Text, default="{}")


class SettingRow(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(200), primary_key=True)
    value_json: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SchemaMigrationRow(Base):
    __tablename__ = "schema_migrations"

    version: Mapped[str] = mapped_column(String(64), primary_key=True)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
