from __future__ import annotations

from pathlib import Path

from sqlalchemy import inspect

from wp_mcp_hub.storage.database import create_engine
from wp_mcp_hub.storage.migrations import run_migrations


async def test_initial_migration_creates_versioned_schema(tmp_path: Path) -> None:
    database = tmp_path / "migrated.sqlite3"
    await run_migrations(database)
    engine = create_engine(database)
    async with engine.connect() as connection:
        tables = await connection.run_sync(
            lambda sync_connection: set(inspect(sync_connection).get_table_names())
        )
        auth_columns = await connection.run_sync(
            lambda sync_connection: {
                column["name"]
                for column in inspect(sync_connection).get_columns("site_auth_metadata")
            }
        )
    assert {
        "sites",
        "site_auth_metadata",
        "site_capabilities",
        "cached_tools",
        "tool_policies",
        "operations",
        "operation_results",
        "settings",
        "schema_migrations",
    } <= tables
    assert "resource" in auth_columns
    await engine.dispose()
