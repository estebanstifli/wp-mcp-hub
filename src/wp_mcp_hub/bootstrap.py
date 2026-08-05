from __future__ import annotations

from dataclasses import dataclass

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from wp_mcp_hub.adapters.generic_mcp import GenericMcpAdapter
from wp_mcp_hub.adapters.registry import AdapterRegistry
from wp_mcp_hub.application.services import HubService
from wp_mcp_hub.config import Settings
from wp_mcp_hub.credentials.keyring_backend import KeyringCredentialStore
from wp_mcp_hub.logging import LoggingRuntime, configure_logging
from wp_mcp_hub.oauth.manager import OAuthManager
from wp_mcp_hub.paths import AppPaths
from wp_mcp_hub.storage.database import create_engine, session_factory
from wp_mcp_hub.storage.migrations import run_migrations
from wp_mcp_hub.storage.repositories import SqlAlchemyAuthMetadataStore


@dataclass(slots=True)
class AppContainer:
    settings: Settings
    paths: AppPaths
    engine: AsyncEngine
    sessions: async_sessionmaker[AsyncSession]
    http: httpx.AsyncClient
    oauth: OAuthManager
    hub: HubService
    logging: LoggingRuntime

    async def close(self) -> None:
        await self.http.aclose()
        await self.engine.dispose()
        self.logging.close()


async def create_container(settings: Settings | None = None) -> AppContainer:
    settings = settings or Settings()
    logging_runtime = configure_logging(settings.log_level)
    if settings.web_host != "127.0.0.1":
        raise ValueError("web_host must be 127.0.0.1")
    paths = AppPaths.discover()
    paths.ensure()
    database_path = settings.resolved_database_path(paths)
    database_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    await run_migrations(database_path)
    engine = create_engine(database_path)
    sessions = session_factory(engine)
    http = httpx.AsyncClient(
        timeout=httpx.Timeout(
            settings.request_timeout_seconds,
            connect=settings.connect_timeout_seconds,
        ),
        follow_redirects=False,
        headers={"User-Agent": "WP-MCP-Hub/0.1.0"},
    )
    auth_store = SqlAlchemyAuthMetadataStore(sessions)
    oauth = OAuthManager(
        http,
        KeyringCredentialStore(),
        auth_store,
        redirect_uri=f"http://127.0.0.1:{settings.web_port}/oauth/callback",
        refresh_skew_seconds=settings.token_refresh_skew_seconds,
    )
    adapters = AdapterRegistry(
        [
            GenericMcpAdapter(
                settings.request_timeout_seconds,
                settings.read_retry_attempts,
            )
        ]
    )
    hub = HubService(
        sessions,
        adapters,
        oauth.request_headers,
        max_concurrency=settings.max_concurrency,
    )
    return AppContainer(
        settings,
        paths,
        engine,
        sessions,
        http,
        oauth,
        hub,
        logging_runtime,
    )
