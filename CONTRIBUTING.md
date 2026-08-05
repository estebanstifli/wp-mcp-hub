# Contributing

Contributions are welcome. Open an issue before large architectural changes.
Do not include real tokens, WordPress credentials, production URLs, or customer
data in issues, fixtures, commits, or logs.

Set up the project with `uv sync --extra dev`, then run:

```console
uv run ruff check .
uv run ruff format --check .
uv run mypy src/wp_mcp_hub tests
uv run pytest
uv build
```

New provider behavior requires public documentation or sanitized fixtures. Keep
provider-specific behavior behind `ProviderAdapter`; the generic core must remain
standards-based. Schema or behavioral changes need contract tests and an update
to the versioned documentation.

By contributing, you agree that your contribution is licensed under Apache-2.0.
