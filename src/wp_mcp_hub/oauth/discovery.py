from __future__ import annotations

import re
from urllib.parse import urlsplit, urlunsplit

import httpx

from wp_mcp_hub.domain.errors import OAuthError
from wp_mcp_hub.oauth.models import AuthorizationServerMetadata, ProtectedResourceMetadata
from wp_mcp_hub.security.ssrf import validate_remote_url

RESOURCE_METADATA_RE = re.compile(r'resource_metadata\s*=\s*"([^"]+)"', re.IGNORECASE)


def protected_resource_candidates(resource: str) -> list[str]:
    parsed = urlsplit(resource)
    origin = urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))
    path = parsed.path.lstrip("/")
    candidates = []
    if path:
        candidates.append(f"{origin}/.well-known/oauth-protected-resource/{path}")
    candidates.append(f"{origin}/.well-known/oauth-protected-resource")
    return candidates


def authorization_server_candidates(issuer: str) -> list[str]:
    parsed = urlsplit(issuer)
    origin = urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))
    path = parsed.path.rstrip("/")
    return [
        f"{origin}/.well-known/oauth-authorization-server{path}",
        f"{issuer.rstrip('/')}/.well-known/openid-configuration",
        f"{origin}/.well-known/openid-configuration{path}",
    ]


async def discover_protected_resource(
    client: httpx.AsyncClient, resource: str, *, allow_private: bool
) -> tuple[ProtectedResourceMetadata, str]:
    await validate_remote_url(resource, allow_private=allow_private)
    response = await client.get(resource)
    challenge = response.headers.get("WWW-Authenticate", "")
    match = RESOURCE_METADATA_RE.search(challenge)
    candidates = [match.group(1)] if match else protected_resource_candidates(resource)
    for candidate in candidates:
        await validate_remote_url(candidate, allow_private=allow_private)
        metadata_response = await client.get(candidate)
        if metadata_response.status_code == 200:
            try:
                metadata = ProtectedResourceMetadata.model_validate(metadata_response.json())
            except ValueError as exc:
                raise OAuthError("Protected Resource Metadata is invalid") from exc
            return metadata, candidate
    raise OAuthError("The MCP server did not expose Protected Resource Metadata")


async def discover_authorization_server(
    client: httpx.AsyncClient, issuer: str, *, allow_private: bool
) -> AuthorizationServerMetadata:
    await validate_remote_url(issuer, allow_private=allow_private)
    for candidate in authorization_server_candidates(issuer):
        await validate_remote_url(candidate, allow_private=allow_private)
        response = await client.get(candidate)
        if response.status_code != 200:
            continue
        try:
            metadata = AuthorizationServerMetadata.model_validate(response.json())
        except ValueError:
            continue
        if metadata.issuer != issuer:
            raise OAuthError("Authorization server issuer does not match discovery URL")
        for endpoint in (
            str(metadata.authorization_endpoint),
            str(metadata.token_endpoint),
            str(metadata.registration_endpoint) if metadata.registration_endpoint else None,
            str(metadata.revocation_endpoint) if metadata.revocation_endpoint else None,
        ):
            if endpoint:
                await validate_remote_url(endpoint, allow_private=allow_private)
        return metadata
    raise OAuthError("Authorization Server Metadata discovery failed")
