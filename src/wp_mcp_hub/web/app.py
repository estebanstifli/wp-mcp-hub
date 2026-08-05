from __future__ import annotations

import secrets
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any, Literal, cast
from urllib.parse import urlencode
from uuid import UUID

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, SecretStr
from starlette.middleware.trustedhost import TrustedHostMiddleware

from wp_mcp_hub.bootstrap import AppContainer, create_container
from wp_mcp_hub.config import activity_preferences, save_activity_preferences, save_web_port
from wp_mcp_hub.credentials.keyring_backend import KeyringCredentialStore
from wp_mcp_hub.domain.errors import HubError, SiteNotFoundError
from wp_mcp_hub.domain.models import RiskClass, SiteCreate, TransportKind
from wp_mcp_hub.oauth.models import ManualOAuthConfiguration
from wp_mcp_hub.storage.repositories import OperationRepository


class ConnectRequest(BaseModel):
    client_id: str | None = None
    client_secret: SecretStr | None = None
    client_metadata_url: str | None = None
    scopes: list[str] | None = Field(default=None)
    manual: ManualOAuthConfiguration | None = None


class PolicyRequest(BaseModel):
    classification: RiskClass
    explicitly_allowed: bool = False


class SiteNameRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class SiteAddRequest(SiteCreate):
    auth_mode: Literal["oauth", "static_bearer", "custom_header", "none"] = "oauth"
    secret: SecretStr | None = None
    header_name: str | None = Field(default=None, max_length=200)


class SiteJsonImportRequest(BaseModel):
    config: dict[str, Any]


class WebSettingsRequest(BaseModel):
    web_port: int = Field(ge=1024, le=65535)


class ActivitySettingsRequest(BaseModel):
    enabled: bool = True
    trace_level: str = Field(pattern="^(tool|tool_and_parameters|full)$")


def create_web_app(existing_container: AppContainer | None = None) -> FastAPI:
    csrf_token = secrets.token_urlsafe(32)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        container = existing_container or await create_container()
        app.state.container = container
        app.state.csrf_token = csrf_token
        yield
        if existing_container is None:
            await container.close()

    app = FastAPI(title="WP MCP Hub", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["127.0.0.1", "localhost", "testserver"],
    )
    templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
    app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

    @app.middleware("http")
    async def security_headers(request: Request, call_next: Any) -> Any:
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'unsafe-inline' https://unpkg.com; "
            "style-src 'unsafe-inline'; "
            "img-src 'self' https: data:; "
            "base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        return response

    async def require_csrf(x_wp_mcp_hub_csrf: Annotated[str | None, Header()] = None) -> None:
        if not x_wp_mcp_hub_csrf or not secrets.compare_digest(x_wp_mcp_hub_csrf, csrf_token):
            raise HTTPException(status_code=403, detail="Invalid CSRF token")

    def container(request: Request) -> AppContainer:
        return cast(AppContainer, request.app.state.container)

    @app.exception_handler(HubError)
    async def hub_error_handler(_request: Request, exc: HubError) -> Any:
        status = 404 if isinstance(exc, SiteNotFoundError) else 400
        return HTMLResponse(str(exc), status_code=status)

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        sites = await container(request).hub.list_sites()
        launcher = Path(sys.argv[0])
        mcp_command = str(
            launcher.parent / ("python.exe" if sys.platform == "win32" else "python")
        )
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "sites": sites,
                "csrf_token": csrf_token,
                "web_port": container(request).settings.web_port,
                "config_dir": str(container(request).paths.config_dir),
                "mcp_command": mcp_command,
                "mcp_args": ["-m", "wp_mcp_hub.cli", "mcp"],
            },
        )

    @app.get("/sites")
    async def list_sites(request: Request) -> list[dict[str, Any]]:
        return [site.model_dump(mode="json") for site in await container(request).hub.list_sites()]

    @app.post("/sites", dependencies=[])
    async def add_site(
        request: Request,
        value: SiteAddRequest,
        _: None = awaitable_dependency(require_csrf),
    ) -> dict[str, Any]:
        site = await container(request).hub.add_site(SiteCreate.model_validate(value.model_dump()))
        await _store_site_auth(
            container(request), site.id, value.auth_mode, value.secret, value.header_name
        )
        return site.model_dump(mode="json")

    @app.post("/sites/import")
    async def import_sites(
        request: Request,
        value: SiteJsonImportRequest,
        _: None = awaitable_dependency(require_csrf),
    ) -> dict[str, object]:
        servers = value.config.get("mcpServers")
        if not isinstance(servers, dict) or not servers:
            raise HTTPException(
                status_code=400, detail="JSON must contain a non-empty mcpServers object"
            )
        imported: list[str] = []
        for name, server in servers.items():
            if not isinstance(name, str) or not isinstance(server, dict):
                raise HTTPException(status_code=400, detail="Each MCP server must be an object")
            url = server.get("url") or server.get("mcp_url")
            if not isinstance(url, str):
                raise HTTPException(status_code=400, detail=f"Server {name!r} needs a URL")
            headers = server.get("headers", {})
            if not isinstance(headers, dict):
                raise HTTPException(
                    status_code=400, detail=f"Server {name!r} headers must be an object"
                )
            mode, secret, header_name = _import_auth(headers)
            site_create = SiteCreate.model_validate(
                {
                    "name": name,
                    "mcp_url": url,
                    "transport": (
                        TransportKind.SSE
                        if server.get("transport") == "sse"
                        else TransportKind.STREAMABLE_HTTP
                    ),
                    "allow_private_network": bool(server.get("allow_private_network", False)),
                }
            )
            site = await container(request).hub.add_site(site_create)
            await _store_site_auth(container(request), site.id, mode, secret, header_name)
            imported.append(site.name)
        return {"imported": imported}

    @app.get("/sites/{site_id}")
    async def get_site(request: Request, site_id: UUID) -> dict[str, Any]:
        return (await container(request).hub.get_site(site_id)).model_dump(mode="json")

    @app.get("/sites/{site_id}/auth-mode")
    async def site_auth_mode(request: Request, site_id: UUID) -> dict[str, str]:
        await container(request).hub.get_site(site_id)
        return {"mode": await container(request).oauth.authentication_mode(site_id)}

    @app.patch("/sites/{site_id}")
    async def rename_site(
        request: Request,
        site_id: UUID,
        value: SiteNameRequest,
        _: None = awaitable_dependency(require_csrf),
    ) -> dict[str, Any]:
        site = await container(request).hub.rename_site(site_id, value.name)
        return site.model_dump(mode="json")

    @app.get("/sites/{site_id}/tools")
    async def list_site_tools(request: Request, site_id: UUID) -> list[dict[str, Any]]:
        tools = await container(request).hub.list_site_tools(site_id)
        return [tool.model_dump(mode="json") for tool in tools]

    @app.post("/sites/{site_id}/connect")
    async def connect_site(
        request: Request,
        site_id: UUID,
        value: ConnectRequest,
        _: None = awaitable_dependency(require_csrf),
    ) -> dict[str, str]:
        app_container = container(request)
        site = await app_container.hub.get_site(site_id)
        authorization_url = await app_container.oauth.begin(
            site,
            client_id=value.client_id,
            client_secret=(value.client_secret.get_secret_value() if value.client_secret else None),
            client_metadata_url=value.client_metadata_url,
            scopes=value.scopes,
            manual=value.manual,
        )
        return {"authorization_url": authorization_url}

    @app.post("/sites/{site_id}/test")
    async def test_site(
        request: Request,
        site_id: UUID,
        _: None = awaitable_dependency(require_csrf),
    ) -> dict[str, Any]:
        return (await container(request).hub.test_site(site_id)).model_dump(mode="json")

    @app.post("/sites/{site_id}/ping")
    async def ping_site(
        request: Request,
        site_id: UUID,
        _: None = awaitable_dependency(require_csrf),
    ) -> dict[str, object]:
        return await container(request).hub.ping_site(site_id)

    @app.delete("/sites/{site_id}")
    async def delete_site(
        request: Request,
        site_id: UUID,
        _: None = awaitable_dependency(require_csrf),
    ) -> dict[str, bool]:
        app_container = container(request)
        await app_container.oauth.revoke(site_id)
        return {"deleted": await app_container.hub.delete_site(site_id)}

    @app.put("/sites/{site_id}/tools/{tool_name}/policy")
    async def set_tool_policy(
        request: Request,
        site_id: UUID,
        tool_name: str,
        value: PolicyRequest,
        _: None = awaitable_dependency(require_csrf),
    ) -> dict[str, bool]:
        await container(request).hub.set_tool_policy(
            site_id,
            tool_name,
            value.classification,
            value.explicitly_allowed,
        )
        return {"updated": True}

    @app.get("/oauth/callback")
    async def oauth_callback(
        request: Request,
        state: Annotated[str, Query(min_length=20)],
        code: Annotated[str, Query(min_length=1)],
        iss: str | None = None,
    ) -> RedirectResponse:
        try:
            await container(request).oauth.complete(state=state, code=code, issuer=iss)
        except HubError as exc:
            callback_url = f"/?{urlencode({'oauth_error': str(exc)})}"
            return RedirectResponse(url=callback_url, status_code=303)
        return RedirectResponse(url="/?connected=1", status_code=303)

    @app.get("/operations")
    async def operations(request: Request, site_id: UUID | None = None) -> list[dict[str, object]]:
        app_container = container(request)
        async with app_container.sessions() as session:
            return await OperationRepository(session).list_recent(site_id=site_id)

    @app.get("/logs")
    async def logs(
        request: Request,
        after: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1, le=500)] = 200,
    ) -> list[dict[str, object]]:
        entries = container(request).logging.buffer.snapshot(after=after, limit=limit)
        return [
            {
                "id": entry.id,
                "timestamp": entry.timestamp,
                "level": entry.level,
                "logger": entry.logger,
                "message": entry.message,
            }
            for entry in entries
        ]

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/settings")
    async def get_settings(request: Request) -> dict[str, object]:
        backend, available = KeyringCredentialStore.backend_description()
        app_container = container(request)
        return {
            "web_port": app_container.settings.web_port,
            "config_dir": str(app_container.paths.config_dir),
            "credential_backend": backend,
            "credential_backend_available": available,
            "activity_enabled": activity_preferences()[0],
            "activity_trace_level": activity_preferences()[1],
        }

    @app.put("/settings/web")
    async def update_web_settings(
        request: Request,
        value: WebSettingsRequest,
        _: None = awaitable_dependency(require_csrf),
    ) -> dict[str, object]:
        save_web_port(value.web_port)
        return {
            "web_port": value.web_port,
            "restart_required": True,
            "next_url": f"http://127.0.0.1:{value.web_port}",
        }

    @app.put("/settings/activity")
    async def update_activity_settings(
        value: ActivitySettingsRequest,
        _: None = awaitable_dependency(require_csrf),
    ) -> dict[str, object]:
        save_activity_preferences(value.enabled, value.trace_level)
        return {"updated": True, "enabled": value.enabled, "trace_level": value.trace_level}

    return app


def awaitable_dependency(function: Any) -> Any:
    """Keep Depends imported lazily out of domain-facing annotations."""
    from fastapi import Depends

    return Depends(function)


async def _store_site_auth(
    app_container: AppContainer,
    site_id: UUID,
    mode: str,
    secret: SecretStr | None,
    header_name: str | None,
) -> None:
    if mode in {"static_bearer", "custom_header"}:
        if secret is None or not secret.get_secret_value():
            raise HTTPException(status_code=400, detail="A credential value is required")
        if mode == "custom_header" and (
            not header_name or "\r" in header_name or "\n" in header_name
        ):
            raise HTTPException(status_code=400, detail="A valid custom header name is required")
        await app_container.oauth.store_static_credential(
            site_id,
            mode=mode,
            secret=secret.get_secret_value(),
            header_name=header_name,
        )
    elif mode == "none":
        await app_container.oauth.store_no_auth(site_id)


def _import_auth(headers: dict[str, Any]) -> tuple[str, SecretStr | None, str | None]:
    if not headers:
        return "none", None, None
    if len(headers) != 1:
        raise HTTPException(status_code=400, detail="Only one authentication header is supported")
    header_name, secret = next(iter(headers.items()))
    if not isinstance(header_name, str) or not isinstance(secret, str):
        raise HTTPException(status_code=400, detail="Authentication headers must be string values")
    if header_name.lower() == "authorization" and secret.lower().startswith("bearer "):
        return "static_bearer", SecretStr(secret[7:]), None
    return "custom_header", SecretStr(secret), header_name


app = create_web_app()
