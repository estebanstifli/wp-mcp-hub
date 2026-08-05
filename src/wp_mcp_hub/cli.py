from __future__ import annotations

import argparse
import asyncio
import sys

import uvicorn

from wp_mcp_hub.bootstrap import create_container
from wp_mcp_hub.config import Settings
from wp_mcp_hub.credentials.keyring_backend import KeyringCredentialStore
from wp_mcp_hub.mcp_server import build_mcp_server


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wp-mcp-hub")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("mcp", help="Run the local MCP stdio server")
    subcommands.add_parser("web", help="Run the loopback administration panel")
    subcommands.add_parser("migrate", help="Create or migrate the local database")
    subcommands.add_parser("doctor", help="Validate local configuration")
    return parser


async def _run_mcp() -> None:
    container = await create_container()
    try:
        await build_mcp_server(container).run_stdio_async()
    finally:
        await container.close()


async def _initialize() -> None:
    container = await create_container()
    await container.close()


def main() -> None:
    args = _parser().parse_args()
    if args.command == "mcp":
        asyncio.run(_run_mcp())
    elif args.command == "web":
        settings = Settings()
        uvicorn.run(
            "wp_mcp_hub.web.app:app",
            host="127.0.0.1",
            port=settings.web_port,
            log_level=settings.log_level.lower(),
        )
    elif args.command == "migrate":
        asyncio.run(_initialize())
        print("Database schema is up to date.")
    elif args.command == "doctor":
        asyncio.run(_initialize())
        backend, available = KeyringCredentialStore.backend_description()
        print("WP MCP Hub configuration and database are valid.")
        if available:
            print(f"Secure credential backend: {backend}")
        else:
            print(
                f"WARNING: no secure credential backend is available ({backend}); "
                "OAuth credential storage will fail closed.",
                file=sys.stderr,
            )
    else:
        sys.exit(2)


if __name__ == "__main__":
    main()
