from __future__ import annotations

import asyncio
import logging
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import UUID

import httpx
from pydantic import SecretStr

from wp_mcp_hub.credentials.protocol import CredentialStore
from wp_mcp_hub.domain.errors import OAuthError
from wp_mcp_hub.domain.models import Site
from wp_mcp_hub.oauth.discovery import discover_authorization_server, discover_protected_resource
from wp_mcp_hub.oauth.models import (
    AuthMetadataStore,
    AuthorizationServerMetadata,
    ManualOAuthConfiguration,
    OAuthClientRegistration,
    OAuthFlow,
    OAuthTokenSet,
    ProtectedResourceMetadata,
    StoredAuthMetadata,
)
from wp_mcp_hub.oauth.pkce import create_state, create_verifier, s256_challenge
from wp_mcp_hub.security.ssrf import validate_remote_url

logger = logging.getLogger(__name__)


class OAuthManager:
    def __init__(
        self,
        http_client: httpx.AsyncClient,
        credentials: CredentialStore,
        auth_repository: AuthMetadataStore,
        *,
        redirect_uri: str,
        refresh_skew_seconds: int = 60,
    ) -> None:
        self._http = http_client
        self._credentials = credentials
        self._auth = auth_repository
        self._redirect_uri = redirect_uri
        self._refresh_skew = timedelta(seconds=refresh_skew_seconds)
        self._flows: dict[str, OAuthFlow] = {}
        self._refresh_locks: dict[UUID, asyncio.Lock] = {}

    async def begin(
        self,
        site: Site,
        *,
        client_id: str | None = None,
        client_secret: str | None = None,
        client_metadata_url: str | None = None,
        scopes: list[str] | None = None,
        manual: ManualOAuthConfiguration | None = None,
    ) -> str:
        logger.info("OAuth authorization started: site_id=%s", site.id)
        if manual is None:
            resource, resource_metadata_url = await discover_protected_resource(
                self._http, site.mcp_url, allow_private=site.allow_private_network
            )
            issuer = resource.authorization_servers[0]
            server = await discover_authorization_server(
                self._http, issuer, allow_private=site.allow_private_network
            )
        else:
            endpoints = [
                str(manual.issuer),
                str(manual.authorization_endpoint),
                str(manual.token_endpoint),
                str(manual.registration_endpoint) if manual.registration_endpoint else None,
                str(manual.revocation_endpoint) if manual.revocation_endpoint else None,
                str(manual.resource) if manual.resource else site.mcp_url,
            ]
            for endpoint in endpoints:
                if endpoint:
                    await validate_remote_url(endpoint, allow_private=site.allow_private_network)
            resource = ProtectedResourceMetadata(
                resource=str(manual.resource or site.mcp_url),
                authorization_servers=[str(manual.issuer)],
                scopes_supported=scopes or [],
            )
            resource_metadata_url = None
            server = AuthorizationServerMetadata(
                issuer=str(manual.issuer),
                authorization_endpoint=manual.authorization_endpoint,
                token_endpoint=manual.token_endpoint,
                registration_endpoint=manual.registration_endpoint,
                revocation_endpoint=manual.revocation_endpoint,
                code_challenge_methods_supported=["S256"],
                scopes_supported=scopes or [],
            )
        if "S256" not in server.code_challenge_methods_supported:
            raise OAuthError("Authorization server does not advertise PKCE S256 support")
        registration = await self._register(
            server.model_dump(mode="json"), client_id, client_secret, client_metadata_url
        )
        requested = scopes if scopes is not None else resource.scopes_supported
        state = create_state()
        verifier = create_verifier()
        flow = OAuthFlow(
            site_id=site.id,
            state=state,
            code_verifier=verifier,
            issuer=server.issuer,
            token_endpoint=str(server.token_endpoint),
            redirect_uri=self._redirect_uri,
            resource=resource.resource,
            client_id=registration.client_id,
            client_secret=registration.client_secret,
            scopes=requested,
            authorization_response_iss_parameter_supported=(
                server.authorization_response_iss_parameter_supported
            ),
            created_at=datetime.now(UTC),
        )
        self._flows[state] = flow
        await self._auth.upsert(
            StoredAuthMetadata(
                site_id=site.id,
                issuer=server.issuer,
                resource=resource.resource,
                resource_metadata_url=resource_metadata_url,
                authorization_endpoint=str(server.authorization_endpoint),
                token_endpoint=str(server.token_endpoint),
                registration_endpoint=(
                    str(server.registration_endpoint) if server.registration_endpoint else None
                ),
                revocation_endpoint=(
                    str(server.revocation_endpoint) if server.revocation_endpoint else None
                ),
                client_id=registration.client_id,
                registration_method=registration.method,
                scopes_requested=requested,
            )
        )
        query = {
            "response_type": "code",
            "client_id": registration.client_id,
            "redirect_uri": self._redirect_uri,
            "code_challenge": s256_challenge(verifier),
            "code_challenge_method": "S256",
            "state": state,
            "resource": resource.resource,
        }
        if requested:
            query["scope"] = " ".join(requested)
        logger.info(
            "OAuth authorization URL prepared: site_id=%s registration=%s scope_count=%s",
            site.id,
            registration.method,
            len(requested),
        )
        authorization_parts = urlsplit(str(server.authorization_endpoint))
        combined_query = [
            *parse_qsl(authorization_parts.query, keep_blank_values=True),
            *query.items(),
        ]
        return urlunsplit(
            (
                authorization_parts.scheme,
                authorization_parts.netloc,
                authorization_parts.path,
                urlencode(combined_query),
                authorization_parts.fragment,
            )
        )

    async def complete(self, *, state: str, code: str, issuer: str | None = None) -> UUID:
        flow = self._flows.pop(state, None)
        if flow is None or not secrets.compare_digest(flow.state, state):
            raise OAuthError("OAuth state is invalid or expired")
        if datetime.now(UTC) - flow.created_at > timedelta(minutes=10):
            raise OAuthError("OAuth flow expired")
        if issuer is not None and issuer != flow.issuer:
            raise OAuthError("Authorization response issuer mismatch")
        if flow.authorization_response_iss_parameter_supported and issuer is None:
            raise OAuthError("Authorization response omitted the required issuer")
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": flow.redirect_uri,
            "client_id": flow.client_id,
            "code_verifier": flow.code_verifier,
            "resource": flow.resource,
        }
        if flow.client_secret:
            data["client_secret"] = flow.client_secret.get_secret_value()
        response = await self._http.post(flow.token_endpoint, data=data)
        if response.status_code != 200:
            raise OAuthError("Authorization code exchange failed")
        token = OAuthTokenSet.model_validate(response.json())
        await self._store_tokens(flow.site_id, token, flow.client_secret)
        logger.info("OAuth callback completed: site_id=%s", flow.site_id)
        return flow.site_id

    async def access_token(self, site_id: UUID) -> str | None:
        metadata = await self._auth.get(site_id)
        if not metadata or not metadata.access_token_ref:
            return None
        if (
            metadata.token_expires_at
            and metadata.token_expires_at <= datetime.now(UTC) + self._refresh_skew
        ):
            await self._refresh(site_id)
            metadata = await self._auth.get(site_id)
        if metadata is None or metadata.access_token_ref is None:
            return None
        return await self._credentials.get(metadata.access_token_ref)

    async def request_headers(self, site_id: UUID) -> dict[str, str]:
        """Return request headers for OAuth, static Bearer, or custom-header sites."""
        metadata = await self._auth.get(site_id)
        if not metadata or not metadata.access_token_ref:
            return {}
        secret = await self._credentials.get(metadata.access_token_ref)
        if not secret:
            return {}
        if metadata.registration_method == "custom_header":
            if not metadata.client_id:
                raise OAuthError("Custom header configuration is incomplete")
            return {metadata.client_id: secret}
        if metadata.registration_method == "static_bearer":
            return {"Authorization": f"Bearer {secret}"}
        token = await self.access_token(site_id)
        return {"Authorization": f"Bearer {token}"} if token else {}

    async def authentication_mode(self, site_id: UUID) -> str:
        metadata = await self._auth.get(site_id)
        return (
            metadata.registration_method if metadata and metadata.registration_method else "oauth"
        )

    async def store_no_auth(self, site_id: UUID) -> None:
        await self._auth.upsert(StoredAuthMetadata(site_id=site_id, registration_method="none"))

    async def store_static_credential(
        self, site_id: UUID, *, mode: str, secret: str, header_name: str | None = None
    ) -> None:
        if mode not in {"static_bearer", "custom_header"}:
            raise OAuthError("Unsupported static credential mode")
        if mode == "custom_header" and not header_name:
            raise OAuthError("A custom header name is required")
        reference = f"credential://site/{site_id}/static-credential"
        await self._credentials.set(reference, secret)
        await self._auth.upsert(
            StoredAuthMetadata(
                site_id=site_id,
                client_id=header_name,
                registration_method=mode,
            )
        )
        await self._auth.update_tokens(
            site_id,
            access_ref=reference,
            refresh_ref=None,
            client_secret_ref=None,
            expires_at=None,
            scopes=[],
        )
        logger.info("Static credential stored: site_id=%s mode=%s", site_id, mode)

    async def revoke(self, site_id: UUID) -> None:
        logger.info("OAuth credential revocation started: site_id=%s", site_id)
        metadata = await self._auth.get(site_id)
        if metadata and metadata.revocation_endpoint and metadata.refresh_token_ref:
            token = await self._credentials.get(metadata.refresh_token_ref)
            if token:
                try:
                    await self._http.post(metadata.revocation_endpoint, data={"token": token})
                except httpx.HTTPError:
                    pass
        if metadata:
            for reference in (
                metadata.access_token_ref,
                metadata.refresh_token_ref,
                metadata.client_secret_ref,
            ):
                if reference:
                    await self._credentials.delete(reference)
        await self._auth.clear_credentials(site_id)
        logger.info("OAuth local credentials removed: site_id=%s", site_id)

    async def _register(
        self,
        server: dict[str, object],
        client_id: str | None,
        client_secret: str | None,
        client_metadata_url: str | None,
    ) -> OAuthClientRegistration:
        if client_metadata_url:
            return OAuthClientRegistration(client_id=client_metadata_url, method="client_metadata")
        if client_id:
            return OAuthClientRegistration(
                client_id=client_id,
                client_secret=SecretStr(client_secret) if client_secret else None,
                method="manual",
            )
        endpoint = server.get("registration_endpoint")
        if not endpoint:
            raise OAuthError("No client registration method is available; configure client_id")
        response = await self._http.post(
            str(endpoint),
            json={
                "client_name": "WP MCP Hub",
                "application_type": "native",
                "redirect_uris": [self._redirect_uri],
                "grant_types": ["authorization_code", "refresh_token"],
                "response_types": ["code"],
                "token_endpoint_auth_method": "none",
            },
        )
        if response.status_code not in {200, 201}:
            raise OAuthError("Dynamic Client Registration failed")
        payload = response.json()
        return OAuthClientRegistration(
            client_id=payload["client_id"],
            client_secret=payload.get("client_secret"),
            method="dynamic",
        )

    async def _refresh(self, site_id: UUID) -> None:
        lock = self._refresh_locks.setdefault(site_id, asyncio.Lock())
        async with lock:
            metadata = await self._auth.get(site_id)
            if not metadata or not metadata.refresh_token_ref or not metadata.token_endpoint:
                raise OAuthError("No refresh token is available; reconnect the site")
            if (
                metadata.token_expires_at
                and metadata.token_expires_at > datetime.now(UTC) + self._refresh_skew
            ):
                return
            refresh_token = await self._credentials.get(metadata.refresh_token_ref)
            if not refresh_token:
                raise OAuthError("Refresh token is missing from the credential store")
            data = {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": metadata.client_id or "",
            }
            if metadata.resource:
                data["resource"] = metadata.resource
            if metadata.client_secret_ref:
                client_secret = await self._credentials.get(metadata.client_secret_ref)
                if client_secret:
                    data["client_secret"] = client_secret
            response = await self._http.post(metadata.token_endpoint, data=data)
            if response.status_code != 200:
                raise OAuthError("Access token refresh failed")
            await self._store_tokens(site_id, OAuthTokenSet.model_validate(response.json()), None)
            logger.info("OAuth access token refreshed: site_id=%s", site_id)

    async def _store_tokens(
        self, site_id: UUID, token: OAuthTokenSet, client_secret: SecretStr | None
    ) -> None:
        access_ref = f"credential://site/{site_id}/access-token"
        refresh_ref = f"credential://site/{site_id}/refresh-token"
        secret_ref = f"credential://site/{site_id}/client-secret"
        await self._credentials.set(access_ref, token.access_token.get_secret_value())
        if token.refresh_token:
            await self._credentials.set(refresh_ref, token.refresh_token.get_secret_value())
        if client_secret:
            await self._credentials.set(secret_ref, client_secret.get_secret_value())
        expires_at = (
            datetime.now(UTC) + timedelta(seconds=token.expires_in) if token.expires_in else None
        )
        await self._auth.update_tokens(
            site_id,
            access_ref=access_ref,
            refresh_ref=refresh_ref if token.refresh_token else None,
            client_secret_ref=secret_ref if client_secret else None,
            expires_at=expires_at,
            scopes=(token.scope or "").split(),
        )
