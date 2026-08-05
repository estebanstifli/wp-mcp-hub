import pytest


class FakeCredentialStore:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def get(self, reference: str) -> str | None:
        return self.values.get(reference)

    async def set(self, reference: str, secret: str) -> None:
        self.values[reference] = secret

    async def delete(self, reference: str) -> None:
        self.values.pop(reference, None)


@pytest.mark.asyncio
async def test_fake_credential_store_lifecycle() -> None:
    store = FakeCredentialStore()
    await store.set("credential://site/1/access-token", "secret")
    assert await store.get("credential://site/1/access-token") == "secret"
    await store.delete("credential://site/1/access-token")
    assert await store.get("credential://site/1/access-token") is None
