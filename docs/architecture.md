# Architecture

WP MCP Hub has three roles:

1. An MCP server over stdio for the local AI host.
2. An MCP client using Streamable HTTP for each remote WordPress site.
3. A loopback FastAPI application for local administration and OAuth callbacks.

The stdio and web roles run as separate processes. They share a WAL-mode SQLite
database and the operating-system credential store, but never share database
sessions, network clients, or token objects.

## Boundaries

- `domain`: Pydantic contracts, risk classifications, normalized results.
- `application`: use cases shared by web and stdio.
- `adapters`: provider-neutral interface and the generic MCP implementation.
- `oauth`: discovery, registration, PKCE, token lifecycle, and revocation.
- `credentials`: a narrow secret-store protocol and OS keyring backend.
- `storage`: SQLAlchemy repositories and versioned SQLite migrations.
- `security`: SSRF validation and structured-log redaction.
- `web`: loopback API and server-rendered administration UI.

Domain and JSON contracts do not expose SDK-specific MCP types. A future
TypeScript implementation can consume the versioned schemas under `schemas/`
and the transport fixtures under `fixtures/`.

## Dependency rules

Domain code imports no FastAPI, SQLAlchemy, keyring, or MCP SDK modules.
Application services depend on adapter and credential protocols. Infrastructure
implements those protocols and is assembled explicitly in `bootstrap.py`.

The official MCP SDK is constrained to `>=2.0.0,<2.1`; `uv.lock` records the
tested dependency graph. Calls into the SDK are concentrated in
`GenericMcpAdapter` and `mcp_server.py`.

## Processes and commands

- `wp-mcp-hub mcp`: stdio server; stdout is reserved exclusively for MCP.
- `wp-mcp-hub web`: FastAPI bound to `127.0.0.1`.
- `wp-mcp-hub migrate`: apply SQLite migrations.
- `wp-mcp-hub doctor`: validate directories, configuration, and schema.

The initial release is installed as a Python wheel. A future standalone build
should use PyInstaller or Nuitka in per-platform CI, sign each executable, emit
SBOMs and checksums, and keep the same data directories and JSON contracts.
