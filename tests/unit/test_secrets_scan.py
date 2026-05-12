from agent.tools.secrets_scan import scan_secrets, redact_secrets


def test_detects_aws_key():
    content = "aws_access_key_id = AKIAIOSFODNN7EXAMPLE"
    found = scan_secrets(content)
    assert "aws_key" in found


def test_detects_openai_key():
    content = "OPENAI_API_KEY=sk-" + "a" * 48
    found = scan_secrets(content)
    assert "openai_key" in found


def test_clean_content():
    content = "def process_data(df):\n    return df.groupby('id').sum()"
    assert scan_secrets(content) == []


def test_redact_replaces_secret():
    content = "key = AKIAIOSFODNN7EXAMPLE"
    redacted = redact_secrets(content)
    assert "AKIAIOSFODNN7EXAMPLE" not in redacted
    assert "[REDACTED]" in redacted
