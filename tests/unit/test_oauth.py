from __future__ import annotations

from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit
from uuid import UUID, uuid4

import httpx
import pytest

from wp_mcp_hub.domain.models import Site, TransportKind
from wp_mcp_hub.oauth.manager import OAuthManager
from wp_mcp_hub.oauth.models import StoredAuthMetadata


class FakeCredentials:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def get(self, reference: str) -> str | None:
        return self.values.get(reference)

    async def set(self, reference: str, secret: str) -> None:
        self.values[reference] = secret

    async def delete(self, reference: str) -> None:
        self.values.pop(reference, None)


class FakeAuthStore:
    def __init__(self) -> None:
        self.value: StoredAuthMetadata | None = None

    async def get(self, site_id: UUID) -> StoredAuthMetadata | None:
        return self.value if self.value and self.value.site_id == site_id else None

    async def upsert(self, value: StoredAuthMetadata) -> None:
        self.value = value

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
        assert self.value is not None
        self.value.access_token_ref = access_ref
        self.value.refresh_token_ref = refresh_ref or self.value.refresh_token_ref
        self.value.client_secret_ref = client_secret_ref or self.value.client_secret_ref
        self.value.token_expires_at = expires_at
        self.value.scopes_granted = scopes

    async def clear_credentials(self, site_id: UUID) -> None:
        assert self.value is not None
        self.value.access_token_ref = None
        self.value.refresh_token_ref = None
        self.value.client_secret_ref = None


@pytest.mark.asyncio
async def test_oauth_pkce_exchange_and_refresh() -> None:
    token_requests: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/mcp":
            return httpx.Response(
                401,
                headers={
                    "WWW-Authenticate": (
                        'Bearer resource_metadata="http://127.0.0.1/'
                        '.well-known/oauth-protected-resource"'
                    )
                },
            )
        if request.url.path == "/.well-known/oauth-protected-resource":
            return httpx.Response(
                200,
                json={
                    "resource": "http://127.0.0.1/mcp",
                    "authorization_servers": ["http://127.0.0.1/auth"],
                    "scopes_supported": ["mcp:read"],
                },
            )
        if request.url.path == "/.well-known/oauth-authorization-server/auth":
            return httpx.Response(
                200,
                json={
                    "issuer": "http://127.0.0.1/auth",
                    "authorization_endpoint": ("http://127.0.0.1/authorize?sflmcp_oauth=authorize"),
                    "token_endpoint": "http://127.0.0.1/token",
                    "registration_endpoint": "http://127.0.0.1/register",
                    "code_challenge_methods_supported": ["S256"],
                },
            )
        if request.url.path == "/register":
            return httpx.Response(201, json={"client_id": "dynamic-client"})
        if request.url.path == "/token":
            data = {key: values[0] for key, values in parse_qs(request.content.decode()).items()}
            token_requests.append(data)
            if data["grant_type"] == "refresh_token":
                return httpx.Response(
                    200,
                    json={"access_token": "access-2", "expires_in": 3600},
                )
            return httpx.Response(
                200,
                json={
                    "access_token": "access-1",
                    "refresh_token": "refresh-1",
                    "expires_in": 1,
                    "scope": "mcp:read",
                },
            )
        return httpx.Response(404)

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    credentials = FakeCredentials()
    auth = FakeAuthStore()
    manager = OAuthManager(
        http,
        credentials,
        auth,
        redirect_uri="http://127.0.0.1:8766/oauth/callback",
        refresh_skew_seconds=60,
    )
    site = Site(
        id=uuid4(),
        name="Fixture",
        mcp_url="http://127.0.0.1/mcp",
        transport=TransportKind.STREAMABLE_HTTP,
        allow_private_network=True,
    )
    authorization_url = await manager.begin(site)
    query = parse_qs(urlsplit(authorization_url).query)
    assert query["sflmcp_oauth"] == ["authorize"]
    assert query["code_challenge_method"] == ["S256"]
    assert query["resource"] == ["http://127.0.0.1/mcp"]
    await manager.complete(state=query["state"][0], code="authorization-code")
    assert token_requests[0]["code_verifier"]
    assert await credentials.get(f"credential://site/{site.id}/access-token") == "access-1"
    assert auth.value is not None
    auth.value.token_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    assert await manager.access_token(site.id) == "access-2"
    assert token_requests[-1]["grant_type"] == "refresh_token"
    assert token_requests[-1]["resource"] == "http://127.0.0.1/mcp"
    await http.aclose()


@pytest.mark.asyncio
async def test_static_credentials_become_request_headers() -> None:
    http = httpx.AsyncClient()
    credentials = FakeCredentials()
    auth = FakeAuthStore()
    manager = OAuthManager(
        http,
        credentials,
        auth,
        redirect_uri="http://127.0.0.1:8766/oauth/callback",
    )
    site_id = uuid4()
    bearer_value = "token-value"
    header_value = "key-value"
    await manager.store_static_credential(site_id, mode="static_bearer", secret=bearer_value)
    assert await manager.request_headers(site_id) == {"Authorization": f"Bearer {bearer_value}"}
    await manager.store_static_credential(
        site_id,
        mode="custom_header",
        secret=header_value,
        header_name="X-API-Key",
    )
    assert await manager.request_headers(site_id) == {"X-API-Key": header_value}
    await http.aclose()
