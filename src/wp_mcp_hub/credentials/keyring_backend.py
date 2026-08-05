from __future__ import annotations

import asyncio

import keyring
from keyring.errors import KeyringError

from wp_mcp_hub.domain.errors import CredentialStoreError


class KeyringCredentialStore:
    def __init__(self, service_name: str = "wp-mcp-hub") -> None:
        self._service_name = service_name

    @staticmethod
    def backend_description() -> tuple[str, bool]:
        backend = keyring.get_keyring()
        priority = float(getattr(backend, "priority", 0))
        name = f"{backend.__class__.__module__}.{backend.__class__.__name__}"
        return name, priority > 0

    async def get(self, reference: str) -> str | None:
        try:
            return await asyncio.to_thread(keyring.get_password, self._service_name, reference)
        except KeyringError as exc:
            raise CredentialStoreError(
                "The operating-system credential store is unavailable"
            ) from exc

    async def set(self, reference: str, secret: str) -> None:
        try:
            await asyncio.to_thread(keyring.set_password, self._service_name, reference, secret)
        except KeyringError as exc:
            raise CredentialStoreError(
                "The operating-system credential store rejected the secret"
            ) from exc

    async def delete(self, reference: str) -> None:
        try:
            await asyncio.to_thread(keyring.delete_password, self._service_name, reference)
        except keyring.errors.PasswordDeleteError:
            return
        except KeyringError as exc:
            raise CredentialStoreError(
                "The operating-system credential store is unavailable"
            ) from exc
