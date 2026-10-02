from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest


@pytest.mark.parametrize(
    "version", ["2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25", "2026-07-28"]
)
async def test_hub_stdio_protocol_versions(version: str, tmp_path: Path) -> None:
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "wp_mcp_hub.cli",
        "mcp",
        env={**os.environ, "WP_MCP_HUB_DATABASE_PATH": str(tmp_path / "hub.sqlite3")},
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    assert process.stdin is not None
    assert process.stdout is not None
    writer, reader = process.stdin, process.stdout

    async def send(message: dict[str, Any]) -> None:
        writer.write((json.dumps({"jsonrpc": "2.0", **message}) + "\n").encode())
        await writer.drain()

    async def response(request_id: int) -> dict[str, Any]:
        async with asyncio.timeout(15):
            while True:
                line = await reader.readline()
                assert line, "MCP process closed before responding"
                value: dict[str, Any] = json.loads(line)
                if value.get("id") == request_id:
                    assert "error" not in value, value
                    return dict(value["result"])

    modern = version == "2026-07-28"
    metadata = {
        "io.modelcontextprotocol/protocolVersion": version,
        "io.modelcontextprotocol/clientCapabilities": {},
        "io.modelcontextprotocol/clientInfo": {"name": "compatibility-test", "version": "1"},
    }
    try:
        if modern:
            await send({"id": 1, "method": "server/discover", "params": {"_meta": metadata}})
            discovery = await response(1)
            assert version in discovery["supportedVersions"]
        else:
            await send(
                {
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": version,
                        "capabilities": {},
                        "clientInfo": {"name": "compatibility-test", "version": "1"},
                    },
                }
            )
            assert (await response(1))["protocolVersion"] == version
            await send({"method": "notifications/initialized"})

        params: dict[str, Any] = {"_meta": metadata} if modern else {}
        await send({"id": 2, "method": "tools/list", "params": params})
        catalog = await response(2)
        assert len(catalog["tools"]) == 6
        if modern:
            assert catalog["resultType"] == "complete"
            assert "ttlMs" in catalog and "cacheScope" in catalog
        await send(
            {
                "id": 3,
                "method": "tools/call",
                "params": {
                    **params,
                    "name": "list_sites",
                    "arguments": {},
                },
            }
        )
        assert not (await response(3)).get("isError", False)
    finally:
        writer.close()
        try:
            await asyncio.wait_for(process.wait(), timeout=5)
        except TimeoutError:
            process.kill()
            await process.wait()
