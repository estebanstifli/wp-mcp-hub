from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from wp_mcp_hub.domain.models import RiskClass


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    classification: RiskClass
    allowed: bool
    reason: str


def classify_annotations(annotations: dict[str, Any]) -> RiskClass:
    """Treat remote hints conservatively; names never grant permission."""
    if annotations.get("destructiveHint") is True:
        return RiskClass.DESTRUCTIVE
    if annotations.get("readOnlyHint") is True and annotations.get("destructiveHint") is not True:
        return RiskClass.READ
    return RiskClass.UNKNOWN


def decide_tool_call(
    annotations: dict[str, Any],
    configured_classification: RiskClass | None,
    explicitly_allowed: bool,
) -> PolicyDecision:
    classification = configured_classification or classify_annotations(annotations)
    if configured_classification is None:
        return PolicyDecision(classification, True, "allowed by default")
    if explicitly_allowed:
        return PolicyDecision(classification, True, "explicit local policy")
    return PolicyDecision(
        classification,
        False,
        "explicit local policy denies this tool",
    )
