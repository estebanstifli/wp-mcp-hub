# Security model

## Trust boundaries

Configured WordPress servers, their OAuth servers, remote tool metadata, tool
results, and DNS answers are untrusted. The browser interface is local but is
still protected against cross-origin requests and DNS rebinding.

## Credentials

SQLite stores opaque credential references only. Access tokens, refresh tokens,
client secrets, passwords, OAuth state, and PKCE verifiers are never persisted
in SQLite, configuration files, operation parameters, or logs. OAuth state and
PKCE verifiers are single-use, memory-only values with a ten-minute lifetime.

If an OS keyring is unavailable, credential operations fail closed. Linux users
need a working Secret Service implementation and D-Bus session.

## Network destinations

Remote URLs require HTTPS by default. Every discovered endpoint is validated.
Loopback, private, link-local, reserved, multicast, and unspecified IP addresses
are blocked for both IPv4 and IPv6. Private destinations require an explicit
per-site override. Redirect following is disabled; a later implementation may
follow redirects only after validating every hop and preventing Authorization
header forwarding across origins.

## Tool calls

Remote names are never used to classify permissions. Tools are allowed by
default and every call is audited locally. A current local policy can explicitly
deny a tool; policies are tied to the tool schema hash, so a schema change
returns the tool to the default behavior.

`diagnose_sites` only negotiates MCP, pings, and lists tools. It never invokes a
remote tool.

## Local web server

The server rejects any configured bind host except `127.0.0.1`, validates Host,
has no permissive CORS policy, requires a random CSRF header for mutations, and
emits CSP, no-store, frame, referrer, and MIME-sniffing protections.

Report vulnerabilities privately as described in `SECURITY.md`.
