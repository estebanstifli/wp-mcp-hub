from __future__ import annotations

import asyncio
import ipaddress
import socket
from urllib.parse import urlsplit

from wp_mcp_hub.domain.errors import UnsafeUrlError


def _blocked(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    return not ip.is_global


async def validate_remote_url(url: str, *, allow_private: bool = False) -> None:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise UnsafeUrlError("URL must be an absolute HTTP(S) URL")
    if parsed.username or parsed.password or parsed.fragment:
        raise UnsafeUrlError("URL userinfo and fragments are not allowed")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        answers = await asyncio.to_thread(
            socket.getaddrinfo, parsed.hostname, port, type=socket.SOCK_STREAM
        )
    except socket.gaierror as exc:
        raise UnsafeUrlError("Hostname could not be resolved") from exc
    addresses = {str(answer[4][0]) for answer in answers}
    if not addresses:
        raise UnsafeUrlError("Hostname did not resolve to an address")
    if parsed.scheme == "http" and (not allow_private or any(not _blocked(a) for a in addresses)):
        raise UnsafeUrlError("HTTP is allowed only for explicitly approved private destinations")
    if not allow_private and any(_blocked(address) for address in addresses):
        raise UnsafeUrlError("URL resolves to a private or non-global address")
