from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, SecretStr


class ProtectedResourceMetadata(BaseModel):
    resource: str
    authorization_servers: list[str] = Field(min_length=1)
    scopes_supported: list[str] = Field(default_factory=list)


class AuthorizationServerMetadata(BaseModel):
    issuer: str
    authorization_endpoint: HttpUrl
    token_endpoint: HttpUrl
    registration_endpoint: HttpUrl | None = None
    revocation_endpoint: HttpUrl | None = None
    code_challenge_methods_supported: list[str] = Field(default_factory=list)
    scopes_supported: list[str] = Field(default_factory=list)
    authorization_response_iss_parameter_supported: bool = False


class OAuthClientRegistration(BaseModel):
    client_id: str
    client_secret: SecretStr | None = None
    method: str


class ManualOAuthConfiguration(BaseModel):
    issuer: HttpUrl
    authorization_endpoint: HttpUrl
    token_endpoint: HttpUrl
    registration_endpoint: HttpUrl | None = None
    revocation_endpoint: HttpUrl | None = None
    resource: HttpUrl | None = None


class OAuthTokenSet(BaseModel):
    access_token: SecretStr
    token_type: str = "Bearer"
    expires_in: int | None = None
    refresh_token: SecretStr | None = None
    scope: str | None = None


class OAuthFlow(BaseModel):
    site_id: UUID
    state: str
    code_verifier: str
    issuer: str
    token_endpoint: str
    redirect_uri: str
    resource: str
    client_id: str
    client_secret: SecretStr | None = None
    scopes: list[str] = Field(default_factory=list)
    authorization_response_iss_parameter_supported: bool = False
    created_at: datetime


class StoredAuthMetadata(BaseModel):
    site_id: UUID
    issuer: str | None = None
    resource: str | None = None
    resource_metadata_url: str | None = None
    authorization_endpoint: str | None = None
    token_endpoint: str | None = None
    registration_endpoint: str | None = None
    revocation_endpoint: str | None = None
    client_id: str | None = None
    registration_method: str | None = None
    scopes_requested: list[str] = Field(default_factory=list)
    scopes_granted: list[str] = Field(default_factory=list)
    token_expires_at: datetime | None = None
    access_token_ref: str | None = None
    refresh_token_ref: str | None = None
    client_secret_ref: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class AuthMetadataStore(Protocol):
    async def get(self, site_id: UUID) -> StoredAuthMetadata | None: ...

    async def upsert(self, value: StoredAuthMetadata) -> None: ...

    async def update_tokens(
        self,
        site_id: UUID,
        *,
        access_ref: str,
        refresh_ref: str | None,
        client_secret_ref: str | None,
        expires_at: datetime | None,
        scopes: list[str],
    ) -> None: ...

    async def clear_credentials(self, site_id: UUID) -> None: ...
