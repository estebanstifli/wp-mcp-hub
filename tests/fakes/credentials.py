class FakeCredentialStore:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def get(self, reference: str) -> str | None:
        return self.values.get(reference)

    async def set(self, reference: str, secret: str) -> None:
        self.values[reference] = secret

    async def delete(self, reference: str) -> None:
        self.values.pop(reference, None)
