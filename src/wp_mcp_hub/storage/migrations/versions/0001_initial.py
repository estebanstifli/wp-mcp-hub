"""Initial portable storage schema."""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sites",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("mcp_url", sa.Text(), nullable=False),
        sa.Column("transport", sa.String(32), nullable=False),
        sa.Column("adapter", sa.String(100), nullable=False),
        sa.Column("allow_private_network", sa.Boolean(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "site_auth_metadata",
        sa.Column(
            "site_id",
            sa.String(36),
            sa.ForeignKey("sites.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("issuer", sa.Text()),
        sa.Column("resource", sa.Text()),
        sa.Column("resource_metadata_url", sa.Text()),
        sa.Column("authorization_endpoint", sa.Text()),
        sa.Column("token_endpoint", sa.Text()),
        sa.Column("registration_endpoint", sa.Text()),
        sa.Column("revocation_endpoint", sa.Text()),
        sa.Column("client_id", sa.Text()),
        sa.Column("registration_method", sa.String(32)),
        sa.Column("scopes_requested", sa.Text()),
        sa.Column("scopes_granted", sa.Text()),
        sa.Column("token_expires_at", sa.DateTime(timezone=True)),
        sa.Column("access_token_ref", sa.Text()),
        sa.Column("refresh_token_ref", sa.Text()),
        sa.Column("client_secret_ref", sa.Text()),
    )
    op.create_table(
        "site_capabilities",
        sa.Column(
            "site_id",
            sa.String(36),
            sa.ForeignKey("sites.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("protocol_version", sa.String(32)),
        sa.Column("capabilities_json", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "cached_tools",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "site_id",
            sa.String(36),
            sa.ForeignKey("sites.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("input_schema_json", sa.Text(), nullable=False),
        sa.Column("output_schema_json", sa.Text()),
        sa.Column("annotations_json", sa.Text(), nullable=False),
        sa.Column("schema_hash", sa.String(64), nullable=False),
        sa.Column("cached_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("site_id", "name"),
    )
    op.create_index("ix_cached_tools_site_id", "cached_tools", ["site_id"])
    op.create_table(
        "tool_policies",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "site_id",
            sa.String(36),
            sa.ForeignKey("sites.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tool_name", sa.String(300), nullable=False),
        sa.Column("classification", sa.String(32), nullable=False),
        sa.Column("explicitly_allowed", sa.Boolean(), nullable=False),
        sa.Column("schema_hash", sa.String(64)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("site_id", "tool_name"),
    )
    op.create_index("ix_tool_policies_site_id", "tool_policies", ["site_id"])
    op.create_table(
        "operations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("parameters_json", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "operation_results",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "operation_id",
            sa.String(36),
            sa.ForeignKey("operations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("site_id", sa.String(36), sa.ForeignKey("sites.id", ondelete="SET NULL")),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("result_json", sa.Text(), nullable=False),
    )
    op.create_index("ix_operation_results_operation_id", "operation_results", ["operation_id"])
    op.create_table(
        "settings",
        sa.Column("key", sa.String(200), primary_key=True),
        sa.Column("value_json", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    schema_migrations = op.create_table(
        "schema_migrations",
        sa.Column("version", sa.String(64), primary_key=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.bulk_insert(
        schema_migrations,
        [{"version": revision, "applied_at": datetime.now(UTC)}],
    )


def downgrade() -> None:
    op.drop_table("schema_migrations")
    op.drop_table("settings")
    op.drop_index("ix_operation_results_operation_id", table_name="operation_results")
    op.drop_table("operation_results")
    op.drop_table("operations")
    op.drop_index("ix_tool_policies_site_id", table_name="tool_policies")
    op.drop_table("tool_policies")
    op.drop_index("ix_cached_tools_site_id", table_name="cached_tools")
    op.drop_table("cached_tools")
    op.drop_table("site_capabilities")
    op.drop_table("site_auth_metadata")
    op.drop_table("sites")
