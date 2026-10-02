# Client configuration

First run the local panel and configure sites:

```console
wp-mcp-hub web
```

Then add one stdio MCP server to the host configuration. Use the absolute path to the Python
interpreter that has WP MCP Hub installed; the Settings tab generates it automatically.

For Claude Desktop and other clients that use JSON:

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

On macOS and Linux, replace the command with the absolute path to `.venv/bin/python`.

Codex CLI, the Codex app, its IDE extension, and the local coding experience in ChatGPT Desktop
share `~/.codex/config.toml`:

```toml
[mcp_servers.wp-mcp-hub]
command = "D:\\path\\to\\wp-mcp-hub\\.venv\\Scripts\\python.exe"
args = ["-m", "wp_mcp_hub.cli", "mcp"]
```

The dashboard can open Claude Desktop's JSON file and the shared Codex TOML file in a local text
editor on supported desktop operating systems. It does not overwrite or merge an existing file;
copy the generated block, preserve any existing servers, save, and restart the relevant client or
session.

ChatGPT web does not read this local configuration. Its hosted connector flow requires a remote
MCP endpoint; do not expose WP MCP Hub's loopback administration server to the internet.
