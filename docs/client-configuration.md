# Client configuration

First run the local panel and configure sites:

```console
wp-mcp-hub web
```

Then add one stdio MCP server to the host configuration:

```json
{
  "mcpServers": {
    "wp-mcp-hub": {
      "command": "wp-mcp-hub",
      "args": ["mcp"]
    }
  }
}
```

For a source checkout, use the absolute project directory:

```json
{
  "mcpServers": {
    "wp-mcp-hub": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/wp-mcp-hub", "run", "wp-mcp-hub", "mcp"]
    }
  }
}
```

Restart the host after editing its MCP configuration. Exact configuration-file
locations differ between hosts and operating systems; consult the host's current
documentation.
