import pytest

from wp_mcp_hub.domain.errors import UnsafeUrlError
from wp_mcp_hub.security.ssrf import validate_remote_url


@pytest.mark.asyncio
async def test_blocks_loopback_by_default() -> None:
    with pytest.raises(UnsafeUrlError):
        await validate_remote_url("http://127.0.0.1:8000/mcp")


@pytest.mark.asyncio
async def test_allows_explicit_private_site() -> None:
    await validate_remote_url("http://127.0.0.1:8000/mcp", allow_private=True)


@pytest.mark.asyncio
async def test_private_override_does_not_allow_public_plain_http() -> None:
    with pytest.raises(UnsafeUrlError):
        await validate_remote_url("http://example.com/mcp", allow_private=True)
