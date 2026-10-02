from __future__ import annotations

import re
from importlib import import_module
from pathlib import Path

from fastapi.testclient import TestClient

from wp_mcp_hub.web.app import create_web_app

web_app_module = import_module("wp_mcp_hub.web.app")


def test_health_and_csrf_protection(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.setenv("WP_MCP_HUB_DATABASE_PATH", str(tmp_path / "web.sqlite3"))  # type: ignore[attr-defined]
    with TestClient(create_web_app()) as client:
        assert client.get("/health").json() == {"status": "ok"}
        response = client.post(
            "/sites",
            json={"name": "Example", "mcp_url": "https://example.com/mcp"},
        )
        assert response.status_code == 403
        home = client.get("/")
        csrf = re.search(r'const csrf = "([^"]+)"', home.text)
        assert csrf is not None
        assert client.post("/settings/client-config/codex/open").status_code == 403
        response = client.post(
            "/sites",
            headers={"X-WP-MCP-Hub-CSRF": csrf.group(1)},
            json={
                "name": "Private fixture",
                "mcp_url": "http://127.0.0.1:9000/mcp",
                "allow_private_network": True,
            },
        )
        assert response.status_code == 200
        site_id = client.get("/sites").json()[0]["id"]
        assert client.get("/sites").json()[0]["name"] == "Private fixture"
        rename = client.patch(
            f"/sites/{site_id}",
            headers={"X-WP-MCP-HUB-CSRF": csrf.group(1)},
            json={"name": "Renamed fixture"},
        )
        assert rename.status_code == 200
        assert rename.json()["name"] == "Renamed fixture"
        logs = client.get("/logs").json()
        assert any("log viewer initialized" in entry["message"] for entry in logs)


def test_stdio_client_settings_and_safe_config_open(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.setenv("WP_MCP_HUB_DATABASE_PATH", str(tmp_path / "settings.sqlite3"))  # type: ignore[attr-defined]
    opened: list[str] = []

    def fake_config_path(client_name: str) -> Path:
        suffix = "claude_desktop_config.json" if client_name == "claude" else "config.toml"
        return tmp_path / suffix

    def fake_open(client_name: str) -> Path:
        opened.append(client_name)
        return fake_config_path(client_name)

    monkeypatch.setattr(web_app_module, "_client_config_path", fake_config_path)  # type: ignore[attr-defined]
    monkeypatch.setattr(web_app_module, "_open_client_config", fake_open)  # type: ignore[attr-defined]
    monkeypatch.setattr(web_app_module, "_client_config_open_supported", lambda: True)  # type: ignore[attr-defined]

    with TestClient(create_web_app()) as client:
        home = client.get("/")
        assert home.status_code == 200
        assert 'id="claude-client-config"' in home.text
        assert 'id="codex-client-config"' in home.text
        assert "[mcp_servers.wp-mcp-hub]" in home.text
        assert str(fake_config_path("claude")) in home.text
        assert home.text.index('id="oauth-settings-card"') > home.text.index(
            'id="activity-settings"'
        )

        csrf = re.search(r'const csrf = "([^"]+)"', home.text)
        assert csrf is not None
        response = client.post(
            "/settings/client-config/codex/open",
            headers={"X-WP-MCP-Hub-CSRF": csrf.group(1)},
        )
        assert response.status_code == 200
        assert response.json() == {
            "opened": True,
            "path": str(fake_config_path("codex")),
        }
        assert opened == ["codex"]


def test_config_editor_launcher_preserves_existing_files(
    tmp_path: Path, monkeypatch: object
) -> None:
    paths = {
        "claude": tmp_path / "Claude" / "claude_desktop_config.json",
        "codex": tmp_path / ".codex" / "config.toml",
    }
    paths["codex"].parent.mkdir(parents=True)
    paths["codex"].write_text("# existing configuration\n", encoding="utf-8")
    launched: list[list[str]] = []

    def fake_popen(arguments: list[str], **_kwargs: object) -> object:
        launched.append(arguments)
        return object()

    monkeypatch.setattr(web_app_module, "_client_config_path", lambda name: paths[name])  # type: ignore[attr-defined]
    monkeypatch.setattr(web_app_module.shutil, "which", lambda _name: "text-editor")  # type: ignore[attr-defined]
    monkeypatch.setattr(web_app_module.subprocess, "Popen", fake_popen)  # type: ignore[attr-defined]

    assert web_app_module._open_client_config("codex") == paths["codex"]
    assert paths["codex"].read_text(encoding="utf-8") == "# existing configuration\n"
    assert web_app_module._open_client_config("claude") == paths["claude"]
    assert '"mcpServers": {}' in paths["claude"].read_text(encoding="utf-8")
    assert [arguments[0] for arguments in launched] == ["text-editor", "text-editor"]
    assert [arguments[-1] for arguments in launched] == [
        str(paths["codex"]),
        str(paths["claude"]),
    ]
