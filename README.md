# WordPress MCP Hub

[![CI](https://github.com/estebanstifli/wp-mcp-hub/actions/workflows/ci.yml/badge.svg)](https://github.com/estebanstifli/wp-mcp-hub/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![MCP](https://img.shields.io/badge/Model_Context_Protocol-MCP-6f42c1.svg)](https://modelcontextprotocol.io/)

**A free, open-source, local MCP hub for managing multiple WordPress sites from one AI
client connection.** Connect ChatGPT Desktop, Codex, Claude Desktop, Claude Code, Gemini CLI,
Cursor, VS Code, Windsurf, Cline, Roo Code, and other local MCP clients to WordPress without
paying for a hosted relay or sending credentials to a hub provider.

WordPress MCP Hub is a cross-platform control plane and gateway. Your AI client connects to
one small local MCP server over stdio; the Hub then connects directly to the remote MCP server
installed on each WordPress site. It discovers tools per site, handles OAuth or token-based
authentication, routes calls to the correct website, and records activity locally.

There is no WP MCP Hub account, subscription, telemetry service, hosted proxy, or
developer-controlled relay. The Hub itself has no usage fee. You still need your own AI client,
WordPress hosting, and a compatible MCP server on each site; those products may have their own
costs and data policies.

## Why use a free local WordPress MCP hub?

### One AI connection for every WordPress site

Without a hub, an agency or developer must configure every WordPress MCP endpoint separately in
every AI client. With WP MCP Hub, the client receives one stable local MCP configuration and the
Hub maintains the list of sites behind it. Add, rename, test, reconnect, or remove a site without
rewriting the client configuration each time.

### No paid cloud relay and no vendor account

The application runs on your Windows, macOS, or Linux computer. Requests travel from the local
Hub directly to the WordPress MCP endpoint you configured. WP MCP Hub does not charge per site,
per tool, per request, or per user, and there is no hosted account to maintain.

### Credentials stay under operating-system control

OAuth access tokens, refresh tokens, client secrets, Bearer tokens, and custom API keys are
stored in Windows Credential Manager, macOS Keychain, or Linux Secret Service. SQLite stores only
opaque credential references. The repository does not distribute an unsigned custom executable;
the MCP process is launched with your installed Python interpreter.

### A small tool surface instead of one enormous catalog

The local server exposes six stable hub tools. Remote WordPress tool catalogs are discovered only
for the selected site, so an AI host does not need a permanently flattened list containing every
tool from every website. This is especially useful when WooCommerce, SEO, forms, media, backup,
analytics, and plugin integrations produce hundreds of remote tools.

### Central diagnostics and activity

Use one dashboard to ping sites, test MCP negotiation, inspect discovered tools, diagnose several
sites concurrently, and review tool activity with the originating site, duration, status, and
sanitized result. Trace detail can be configured from tool name only through parameters and full
responses.

### Keep each WordPress server independent

WP MCP Hub is vendor-neutral. It does not require a proprietary WordPress plugin and does not
replace the security or permission model of the remote server. Each website keeps its own users,
capabilities, tokens, OAuth consent, available tools, and plugin integrations.

## What problem does it solve?

WP MCP Hub is designed for people who manage more than one WordPress installation:

- **Agencies and freelancers** managing client sites from one Claude, Gemini, or coding-agent
  setup.
- **WordPress networks and publishers** that want a single inventory of sites without merging
  their credentials or permissions.
- **WooCommerce operators** working across development, staging, and production stores.
- **SEO and content teams** whose remote servers expose posts, media, metadata, analytics, or
  Search Console tools.
- **Plugin developers** testing the same MCP tools against several WordPress environments.
- **Privacy-conscious users** who prefer local configuration and an OS credential vault over a
  third-party hub account.
- **AI power users** who switch between MCP hosts but want the WordPress connection layer to stay
  consistent.

![WP MCP Hub architecture](captura/esquema.png)

## How it works

1. Install an MCP server plugin on each WordPress site.
2. Add each remote MCP URL to the local dashboard and choose OAuth, Bearer token, custom header,
   or no authentication.
3. Configure WP MCP Hub once in a local stdio-compatible AI host.
4. The AI lists sites, selects one by UUID, discovers that site's tools, and calls the chosen
   remote tool through the Hub.
5. The Hub applies local policy, obtains the required credentials from the OS vault, sends the
   request directly to the site, and records a sanitized activity entry.

The Hub has three roles:

- a local MCP server over stdio for the AI host;
- an MCP client using Streamable HTTP or optional legacy SSE for WordPress sites;
- a loopback-only FastAPI dashboard for administration and OAuth callbacks.

The web dashboard and stdio server run as separate processes but share the same local database
and credential store. The dashboard does not need to remain open for ordinary stdio operation;
run it when adding sites, changing settings, inspecting activity, or completing OAuth.

## AI client compatibility

The Hub uses the official Python MCP SDK 2.2 and supports protocol revision
`2026-07-28`, while retaining `2025-11-25`, `2025-06-18`, `2025-03-26`, and
`2024-11-05` compatibility. Local stdio accepts modern discovery and legacy
initialization. Remote Streamable HTTP detects the server's protocol automatically;
the optional legacy SSE transport continues to use initialization.

The dashboard's Ping checks protocol discovery/initialization without invoking a
WordPress tool. The modern protocol removed the `ping` RPC. Each client and remote
site can use a different supported revision; no manual version setting is required.
This update does not add optional MCP extensions or a public HTTP endpoint for the Hub.
See the [official versioning specification](https://modelcontextprotocol.io/specification/2026-07-28/basic/versioning).

The current release exposes its **client-facing connection locally over stdio**. Use the exact
Python command generated in the dashboard's Settings tab.

| AI client or host | Current connection path |
| --- | --- |
| Claude Desktop | Direct local stdio configuration |
| Claude Code | Direct local stdio configuration |
| Gemini CLI | Direct local stdio configuration; Gemini CLI supports stdio MCP servers |
| Cursor, VS Code, Windsurf, Cline, Roo Code | Direct when the client is configured to launch a local stdio MCP server |
| Codex CLI, Codex app, and ChatGPT Desktop local coding experience | Direct local stdio through their shared `~/.codex/config.toml` |
| LibreChat and self-hosted agent platforms | Depends on how that deployment launches local MCP processes |
| ChatGPT web/cloud connectors | Not direct in the current alpha; they require a remote HTTP MCP endpoint or a compatible bridge |
| OpenAI Responses API | OpenAI models support remote MCP tools, but WP MCP Hub currently provides local stdio ingress rather than a public remote endpoint |

ChatGPT Desktop and Codex can launch the Hub locally over stdio. The limitation applies to
ChatGPT's web/cloud connector flow, not to the desktop app's local coding experience. A future
authenticated Streamable HTTP ingress could make a cloud deployment possible, but it must include
proper OAuth, tenant isolation, HTTPS, secure secret storage, and server hardening. Do not expose
the current loopback administration server to the internet.

For Gemini CLI, see Google's
[MCP server configuration](https://github.com/google-gemini/gemini-cli/blob/main/docs/tools/mcp-server.md).
For ChatGPT Desktop and Codex setup, see OpenAI's official
[Model Context Protocol guide](https://learn.chatgpt.com/docs/extend/mcp).

## Compatible WordPress MCP servers

WP MCP Hub uses a generic MCP adapter. The primary remote transport is MCP Streamable HTTP;
legacy SSE can be enabled per site. Compatibility ultimately depends on the remote endpoint,
protocol version, authentication flow, and tool schemas.

Useful WordPress MCP server projects include:

- [StifLi Flex MCP](https://wordpress.org/plugins/stifli-flex-mcp/) — a WordPress MCP server with
  OAuth 2.1, tool profiles, broad WordPress and WooCommerce coverage, and rollback-oriented
  workflows. It is a natural companion for WP MCP Hub when managing several sites.
- [Easy MCP AI](https://wordpress.org/plugins/easy-mcp-ai/) — a remote WordPress MCP server that
  advertises OAuth and Bearer-token connection paths plus WordPress, SEO, analytics, and plugin
  integration tools.
- [Royal MCP](https://wordpress.org/plugins/royal-mcp/) — a security-focused WordPress MCP server
  that advertises authenticated connections, rate limiting, audit logging, and conditional plugin
  integrations.
- Any other standards-conforming WordPress MCP endpoint that works with Streamable HTTP or the
  optional SSE transport and one of the Hub's authentication modes.

These are separate projects. WP MCP Hub does not bundle their code, copy their tool catalog, or
override their WordPress permission checks. A feature such as post editing, WooCommerce order
management, SEO metadata, form access, backups, analytics, or rollback is available only when the
selected remote WordPress server exposes the corresponding MCP tool and the authenticated
WordPress identity is allowed to use it.

## What can an AI do through the Hub?

The answer is determined by each site's remote tool catalog. Depending on the WordPress MCP
server and installed plugins, possible workflows may include:

- draft, read, update, schedule, publish, or search posts and pages;
- manage custom post types, categories, tags, taxonomies, comments, and menus;
- browse media, upload images, update captions, and improve alt text;
- read or update Yoast SEO, Rank Math, AIOSEO, or other SEO metadata;
- inspect WooCommerce products, variations, inventory, orders, customers, coupons, and reports;
- work with Advanced Custom Fields, forms, events, page builders, snippets, backups, or security
  plugins;
- inspect site information, diagnostics, logs, or health data when the remote server provides
  safe tools for them;
- query analytics, search performance, or external SEO services connected by the remote plugin;
- perform the same approved operation across several sites while preserving a separate audit
  trail for each call.

WP MCP Hub itself does not silently perform these actions. The AI must select a site and remote
tool explicitly through `call_site_tool`, and the remote WordPress server remains responsible for
capability checks and execution.

## Local dashboard

The loopback web dashboard keeps configuration and operations in one place:

- responsive site cards with grid and row layouts;
- inline site-name editing;
- Add Site flow with OAuth, Bearer token, custom-header/API-key, or no-auth modes;
- Claude-style JSON import for remote MCP definitions;
- Connect/Reconnect, Ping, Test, Tools, and Delete actions with live progress dialogs;
- per-site tool discovery and cached tool catalogs;
- application logs with sensitive-value redaction and polling-noise suppression;
- activity entries showing tool, site, duration, parameters, response, and status according to the
  configured trace level;
- activity filtering by WordPress site;
- generated absolute stdio client configuration;
- configurable local web port;
- light and dark themes;
- browser-language detection, language selection, and English fallback.

![WP MCP Hub local dashboard](captura/program_principal.png)

## Stable local MCP tools

The Hub intentionally exposes only six local tools:

- `list_sites` — list configured WordPress sites without credentials.
- `get_site` — retrieve one site by UUID.
- `test_site_connection` — test protocol negotiation and read-only discovery.
- `list_site_tools` — discover and cache the tools exposed by one site.
- `call_site_tool` — invoke one named remote tool on one selected site.
- `diagnose_sites` — concurrently diagnose all or selected sites without invoking remote tools.

This indirection keeps site selection explicit and prevents tool-name collisions between two
WordPress servers that expose tools with identical names.

## Authentication modes

| Mode | When to use it | Local storage |
| --- | --- | --- |
| OAuth 2.1 | Servers with discovery, browser authorization, and refresh tokens | Tokens and client secrets in the OS credential store |
| Static Bearer token | Servers that issue a long-lived token | Token in the OS credential store |
| Custom header / API key | Servers using headers such as `X-API-Key` | Header value in the OS credential store |
| None | Public endpoints or controlled local development | No secret stored |

JSON import accepts a Claude-style `mcpServers` object. When an imported entry contains an
`Authorization: Bearer ...` header or one custom authentication header, the Hub extracts the
secret, saves it to the OS credential store, and persists only its reference in SQLite. The user
is responsible for protecting and removing the original JSON file or pasted content.

## Security model

Connecting an AI agent to WordPress can permit real changes. WP MCP Hub therefore treats remote
servers, OAuth metadata, DNS responses, tool descriptions, arguments, and results as untrusted.

- **Loopback administration:** the web server binds only to `127.0.0.1`, validates the Host
  header, requires a random CSRF header for mutations, and sends CSP, no-store, frame, referrer,
  and MIME-sniffing protections.
- **Secure credentials:** secrets are never written to the SQLite site rows or normal log output.
  Credential operations fail closed when no supported OS keyring is available.
- **OAuth safeguards:** discovery, dynamic client registration, PKCE, token refresh, and revocation
  are handled locally. OAuth state and PKCE verifier values are single-use and memory-only.
- **SSRF protection:** remote URLs require HTTPS by default. Loopback, private, link-local,
  reserved, multicast, and unspecified destinations are blocked unless private-network access is
  explicitly enabled for that site.
- **Redirect safety:** automatic redirects are disabled, preventing credentials from being
  forwarded to an unvalidated origin.
- **Redaction:** structured logs and activity use recursive secret redaction. Full trace mode can
  still contain sensitive business or site content, so enable it only when appropriate.
- **Local tool policy:** tools are allowed by default unless a current explicit local policy denies
  them. Policies are bound to the remote tool schema hash, preventing an old decision from being
  silently reused after a schema changes.
- **No write retries:** remote tool calls are never retried automatically. Retries apply only to
  safe connection and discovery reads.
- **Remote enforcement remains mandatory:** the WordPress MCP server must still authenticate the
  caller and enforce WordPress capabilities for every tool.

The Hub improves credential handling and visibility, but it cannot make an unsafe remote tool
safe. Use low-privilege WordPress users, review the tools exposed by each server, keep backups, and
retain human confirmation for destructive operations in the AI host whenever possible.

Read the full [security model](docs/security-model.md) and report vulnerabilities according to
[SECURITY.md](SECURITY.md).

## Install and run

Python 3.11 or newer is required. The project is currently installed from GitHub; it has not yet
been published to PyPI.

### Install with pipx

```console
pipx install "git+https://github.com/estebanstifli/wp-mcp-hub.git"
wp-mcp-hub web
```

### Run once with uvx

```console
uvx --from git+https://github.com/estebanstifli/wp-mcp-hub.git wp-mcp-hub web
```

### Install from a Git checkout

```console
git clone https://github.com/estebanstifli/wp-mcp-hub.git
cd wp-mcp-hub
python -m venv .venv
```

Windows PowerShell:

```console
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m wp_mcp_hub.cli web
```

macOS/Linux:

```console
.venv/bin/python -m pip install -e .
.venv/bin/python -m wp_mcp_hub.cli web
```

With uv:

```console
uv sync --extra dev
uv run wp-mcp-hub web
```

Open `http://127.0.0.1:8766`, add a WordPress MCP site, and complete its authentication.

## Configure Claude Desktop, ChatGPT Desktop, Codex, and other stdio clients

Use Python directly instead of relying on an unsigned application executable. On Windows, add
the following server definition to the client's `mcpServers` configuration and restart the
client:

```json
{
  "mcpServers": {
    "wp-mcp-hub": {
      "command": "D:\\path\\to\\wp-mcp-hub\\.venv\\Scripts\\python.exe",
      "args": ["-m", "wp_mcp_hub.cli", "mcp"]
    }
  }
}
```

On macOS or Linux, use the absolute path to `.venv/bin/python` with the same arguments. The
Settings tab generates the exact absolute command for the current installation, which avoids
PATH differences between desktop applications and terminal sessions.

Codex CLI, the Codex app, its IDE extension, and the local coding experience in ChatGPT Desktop
share `~/.codex/config.toml`. Add this TOML block using the same absolute Python path:

```toml
[mcp_servers.wp-mcp-hub]
command = "D:\\path\\to\\wp-mcp-hub\\.venv\\Scripts\\python.exe"
args = ["-m", "wp_mcp_hub.cli", "mcp"]
```

On Windows, the dashboard shows and can open both Claude Desktop's JSON file and the shared Codex
TOML file in a text editor. On macOS and Linux it uses the corresponding per-user configuration
paths and the platform's standard file opener when available. It never replaces an existing
configuration file: copy the generated block, merge it with any existing servers, save, and
restart the relevant client or session.

See [client configuration](docs/client-configuration.md) for additional examples.

## Configuration

Configuration uses `WP_MCP_HUB_` environment variables. Common settings include:

- `WEB_PORT`
- `CONNECT_TIMEOUT_SECONDS`
- `REQUEST_TIMEOUT_SECONDS`
- `MAX_CONCURRENCY`
- `READ_RETRY_ATTEMPTS`
- `TOKEN_REFRESH_SKEW_SECONDS`
- `LOG_LEVEL`

Application data is stored in the operating system's standard per-user application-data
directory. The dashboard shows the exact local configuration directory and active credential
backend. Changing the HTTP port in Settings takes effect after restarting the web process.

Useful commands:

```console
wp-mcp-hub web       # start the loopback dashboard
wp-mcp-hub mcp       # start the stdio MCP server
wp-mcp-hub migrate   # apply local SQLite migrations
wp-mcp-hub doctor    # validate paths, configuration, and schema
```

## Current status and limitations

WP MCP Hub is an alpha release. The data contracts and local tool surface are intentionally
small, but installation and configuration may still change before 1.0.

- Client-facing transport is local stdio only.
- The loopback web dashboard is not a production HTTP MCP endpoint and must not be exposed
  publicly.
- There is no hosted synchronization between computers.
- There is no `.mcpb` bundle or custom unsigned executable in the supported installation path.
- Python 3.11 or newer and a working OS credential backend are required.
- Linux requires a working Secret Service implementation and D-Bus session.
- WordPress capabilities depend entirely on the remote MCP server and plugins installed on each
  site.
- Streamable HTTP is the primary remote transport; legacy SSE is opt-in.
- Direct ChatGPT web/cloud connector connectivity is not included yet; ChatGPT Desktop's local
  coding experience and Codex can use the Hub over stdio.

## Frequently asked questions

### Is WP MCP Hub free?

Yes. The Hub is open source under Apache-2.0 and has no paid tier, site limit, request meter, or
hosted subscription. Your WordPress hosting, AI plan, model API, and remote MCP server may have
separate costs.

### Is this a WordPress plugin or a WordPress MCP server?

No. It is a local MCP hub and client-side gateway written in Python. Install a separate MCP server
plugin on every WordPress site, then add those remote endpoints to the Hub.

### Why not configure every WordPress site directly in Claude or Gemini?

You can. The Hub becomes useful when you have several sites, several authentication methods, large
tool catalogs, or more than one local AI host. It gives you one stable client entry, central
diagnostics, secure local credentials, and a consistent site-selection workflow.

### Does it work with Claude Desktop?

Yes. Claude Desktop can launch the Hub as a local stdio MCP server. The dashboard generates a
configuration using the absolute path to the installation's Python interpreter.

### Does it work with Gemini?

Gemini CLI supports local stdio MCP servers and can launch WP MCP Hub with the same Python command
and arguments. Other Gemini products may have different connector requirements.

### Does it work with ChatGPT or OpenAI models?

Yes for local desktop use: Codex CLI, the Codex app, its IDE extension, and the local coding
experience in ChatGPT Desktop can launch WP MCP Hub over stdio using their shared
`~/.codex/config.toml`. ChatGPT web/cloud connectors normally need a remotely reachable MCP
endpoint, so that separate connection path is not part of this alpha. This distinction does not
prevent a WordPress server plugin from connecting directly to ChatGPT when that plugin provides a
suitable remote endpoint.

### Can it manage WooCommerce, SEO, posts, media, or plugins?

Only through tools exposed by the selected WordPress MCP server. The Hub routes and audits tool
calls; it does not fabricate WooCommerce, SEO, content, or administrative APIs.

### Where are OAuth credentials and API tokens stored?

In Windows Credential Manager, macOS Keychain, or Linux Secret Service. SQLite keeps an opaque
reference and non-secret site metadata, not the raw secret.

### Does the Hub send data to its developer?

No hosted Hub service is involved. Requests go directly from your computer to the configured
WordPress endpoint. Data returned to your AI client may then be processed according to that AI
provider's terms and privacy settings.

### Must the dashboard remain running?

No. The AI host launches the separate stdio MCP process. Start the dashboard when administering
sites, reading logs, changing settings, or completing a new OAuth browser flow.

### Can I use token-based WordPress MCP servers?

Yes. Static Bearer tokens and custom authentication headers are supported alongside OAuth 2.1.
The secret value is moved into the OS credential store.

### Can I connect local or private-network WordPress sites?

Private, loopback, and reserved destinations are blocked by default as an SSRF defense. A site can
explicitly opt into private-network access when the operator understands and controls the target.

## Development

```console
uv run ruff check .
uv run ruff format --check .
uv run mypy src/wp_mcp_hub tests
uv run pytest
uv build
```

The GitHub Actions matrix runs linting, formatting, type checking, tests, builds, and installation
smoke tests on Windows, macOS, and Linux with supported Python versions.

See [architecture](docs/architecture.md), [security model](docs/security-model.md),
[behavioral contract](docs/behavior.md), and [client configuration](docs/client-configuration.md).

## Contributing and security

Contributions are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.
If you discover a vulnerability, follow the private reporting guidance in
[SECURITY.md](SECURITY.md) instead of opening a public issue.

Licensed under Apache-2.0.
