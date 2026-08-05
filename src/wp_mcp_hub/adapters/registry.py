from __future__ import annotations

from wp_mcp_hub.adapters.protocol import ProviderAdapter


class AdapterRegistry:
    def __init__(self, adapters: list[ProviderAdapter]) -> None:
        self._adapters = {adapter.name: adapter for adapter in adapters}

    def get(self, name: str) -> ProviderAdapter:
        try:
            return self._adapters[name]
        except KeyError as exc:
            raise ValueError(f"Unknown provider adapter: {name}") from exc
