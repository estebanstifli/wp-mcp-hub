class HubError(Exception):
    """Base error safe to map to local API/MCP responses."""


class SiteNotFoundError(HubError):
    pass


class PolicyDeniedError(HubError):
    pass


class UnsafeUrlError(HubError):
    pass


class OAuthError(HubError):
    pass


class CredentialStoreError(HubError):
    pass
