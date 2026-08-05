from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from platformdirs import PlatformDirs


@dataclass(frozen=True, slots=True)
class AppPaths:
    data_dir: Path
    config_dir: Path
    cache_dir: Path

    @classmethod
    def discover(cls) -> AppPaths:
        dirs = PlatformDirs("wp-mcp-hub", "WP MCP Hub", roaming=False)
        return cls(
            Path(dirs.user_data_path),
            Path(dirs.user_config_path),
            Path(dirs.user_cache_path),
        )

    def ensure(self) -> None:
        for path in (self.data_dir, self.config_dir, self.cache_dir):
            path.mkdir(mode=0o700, parents=True, exist_ok=True)
