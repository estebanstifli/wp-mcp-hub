from wp_mcp_hub.domain.models import RiskClass
from wp_mcp_hub.domain.policies import classify_annotations, decide_tool_call


def test_read_only_annotation_is_allowed() -> None:
    decision = decide_tool_call({"readOnlyHint": True}, None, False)
    assert decision.allowed
    assert decision.classification is RiskClass.READ


def test_unknown_tool_is_allowed_by_default() -> None:
    decision = decide_tool_call({}, None, False)
    assert decision.allowed
    assert decision.classification is RiskClass.UNKNOWN


def test_configured_policy_can_deny_or_allow_a_destructive_tool() -> None:
    assert classify_annotations({"destructiveHint": True}) is RiskClass.DESTRUCTIVE
    assert not decide_tool_call({}, RiskClass.DESTRUCTIVE, False).allowed
    assert decide_tool_call({}, RiskClass.DESTRUCTIVE, True).allowed
