from wp_mcp_hub.security.redaction import redact


def test_redacts_nested_secrets_and_bearer_values() -> None:
    value = {
        "access_token": "abc",
        "nested": {"Authorization": "Bearer super-secret"},
        "message": "failed with Bearer token-value",
        "url": (
            "https://example.test/callback?access_token=query-secret"
            "&code=oauth-code&state=oauth-state"
        ),
    }
    redacted = redact(value)
    assert "abc" not in str(redacted)
    assert "super-secret" not in str(redacted)
    assert "token-value" not in str(redacted)
    assert "query-secret" not in str(redacted)
    assert "oauth-code" not in str(redacted)
    assert "oauth-state" not in str(redacted)
