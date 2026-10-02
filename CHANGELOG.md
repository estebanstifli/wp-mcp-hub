# Changelog

## 0.2.0 — 2026-10-02

- Support MCP protocol `2026-07-28` using the official Python SDK 2.2.0.
- Preserve stdio compatibility with `2024-11-05`, `2025-03-26`, `2025-06-18`,
  and `2025-11-25`; automatically fall back to legacy initialization over
  Streamable HTTP and retain the optional legacy SSE transport.
- Check connectivity through discovery/initialization instead of the removed ping RPC.
- Accept any JSON value in structured tool results and identify OAuth dynamic
  registrations as native applications.
- Add wire-level stdio compatibility tests and modern/legacy HTTP and SSE tests.
- Organize Settings into full-width cards, with OAuth information last.
- Provide separate Claude JSON and Codex/ChatGPT Desktop TOML configuration blocks,
  copy buttons, and local configuration-file opening on supported platforms.
- Update client setup documentation and use a shared runtime version identifier.

Existing sites and credentials require no migration. Restart running Hub web and
stdio processes after updating to load the new version.
