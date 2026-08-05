from __future__ import annotations

from typing import Protocol


class CredentialStore(Protocol):
    async def get(self, reference: str) -> str | None: ...

    async def set(self, reference: str, secret: str) -> None: ...

    async def delete(self, reference: str) -> None: ...
