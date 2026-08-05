from __future__ import annotations

import json
from pathlib import Path
from typing import cast
from uuid import uuid4

from jsonschema import Draft202012Validator, FormatChecker

from wp_mcp_hub.domain.models import Site, SiteDiagnostic, TransportKind

SCHEMA_DIR = Path(__file__).parents[2] / "schemas" / "v1"


def load_schema(name: str) -> dict[str, object]:
    return cast(
        dict[str, object],
        json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8")),
    )


def test_all_contract_schemas_are_valid_draft_2020_12() -> None:
    for path in SCHEMA_DIR.glob("*.schema.json"):
        Draft202012Validator.check_schema(json.loads(path.read_text(encoding="utf-8")))


def test_python_site_and_diagnostic_match_neutral_contracts() -> None:
    site_id = uuid4()
    site = Site(
        id=site_id,
        name="Example",
        mcp_url="https://example.com/mcp",
        transport=TransportKind.STREAMABLE_HTTP,
    )
    diagnostic = SiteDiagnostic(site_id=site_id, status="ok", duration_ms=5)
    Draft202012Validator(
        load_schema("site-profile.schema.json"), format_checker=FormatChecker()
    ).validate(site.model_dump(mode="json"))
    Draft202012Validator(
        load_schema("normalized-result.schema.json"), format_checker=FormatChecker()
    ).validate(diagnostic.model_dump(mode="json"))
