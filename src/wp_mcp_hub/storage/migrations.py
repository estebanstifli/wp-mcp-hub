from __future__ import annotations

import asyncio
from pathlib import Path

from alembic import command
from alembic.config import Config
from filelock import FileLock


def run_migrations_sync(database_path: Path) -> None:
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).with_name("migrations")))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path.as_posix()}")
    lock_path = database_path.with_suffix(f"{database_path.suffix}.migrate.lock")
    with FileLock(lock_path, timeout=30):
        command.upgrade(config, "head")
        database_path.chmod(0o600)


async def run_migrations(database_path: Path) -> None:
    await asyncio.to_thread(run_migrations_sync, database_path)
