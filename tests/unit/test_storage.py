from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from wp_mcp_hub.domain.models import SiteCreate
from wp_mcp_hub.oauth.models import StoredAuthMetadata
from wp_mcp_hub.storage.database import create_engine, create_schema, session_factory
from wp_mcp_hub.storage.repositories import SiteRepository, SqlAlchemyAuthMetadataStore


@pytest.mark.asyncio
async def test_site_repository_round_trip(tmp_path: Path) -> None:
    engine = create_engine(tmp_path / "test.sqlite3")
    await create_schema(engine)
    factory = session_factory(engine)
    async with factory.begin() as session:
        created = await SiteRepository(session).add(
            SiteCreate.model_validate({"name": "Example", "mcp_url": "https://example.com/mcp"})
        )
    async with factory() as session:
        loaded = await SiteRepository(session).get(created.id)
        assert loaded == created
    await engine.dispose()


@pytest.mark.asyncio
async def test_sqlite_stores_references_but_not_token_values(tmp_path: Path) -> None:
    database = tmp_path / "secrets.sqlite3"
    engine = create_engine(database)
    await create_schema(engine)
    factory = session_factory(engine)
    async with factory.begin() as session:
        site = await SiteRepository(session).add(
            SiteCreate.model_validate({"name": "Example", "mcp_url": "https://example.com/mcp"})
        )
    auth = SqlAlchemyAuthMetadataStore(factory)
    credential_store = {
        f"credential://site/{site.id}/access-token": "real-access-token",
        f"credential://site/{site.id}/refresh-token": "real-refresh-token",
        f"credential://site/{site.id}/client-secret": "real-client-secret",
    }
    await auth.upsert(StoredAuthMetadata(site_id=site.id, client_id="public-client-id"))
    await auth.update_tokens(
        site.id,
        access_ref=f"credential://site/{site.id}/access-token",
        refresh_ref=f"credential://site/{site.id}/refresh-token",
        client_secret_ref=f"credential://site/{site.id}/client-secret",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        scopes=["mcp:read"],
    )
    await engine.dispose()
    assert set(credential_store.values()) == {
        "real-access-token",
        "real-refresh-token",
        "real-client-secret",
    }
    raw_database = database.read_bytes()
    assert b"credential://site/" in raw_database
    assert b"real-access-token" not in raw_database
    assert b"real-refresh-token" not in raw_database
    assert b"real-client-secret" not in raw_database
