# Behavioral contract

The normative cross-language contracts are the JSON Schemas in `schemas/v1`.
Fields are additive only within a schema major version. Breaking changes require
a new directory such as `schemas/v2`.

## Diagnosis

`diagnose_sites` accepts `"all"` or an explicit list of UUIDs. It preserves the
configured site ordering, limits concurrency, and returns one normalized result
per selected site. A timeout or exception from one site never cancels another.
Diagnostics may perform URL validation, OAuth refresh, MCP negotiation, ping,
and tool discovery. They must not call remote tools.

## Tool policy

The effective classification order is manual configuration, trustworthy MCP
annotations, then `unknown`. Names can produce warnings but cannot grant access.
Read-only calls are permitted. Other classifications require an explicit grant
bound to the current schema hash.

## Error handling

Public errors identify the stage and site without including tokens, authorization
headers, client secrets, PKCE values, passwords, or raw credential-store errors.
Operations record only sanitized parameters. Tool arguments are deliberately not
persisted because arbitrary argument values may themselves be secrets.
