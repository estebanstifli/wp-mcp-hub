from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

from wp_mcp_hub.web.app import create_web_app


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
