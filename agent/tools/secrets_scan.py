import re

# Common secret patterns to detect and redact before sending to LLM
SECRET_PATTERNS = {
    "aws_key": r"AKIA[0-9A-Z]{16}",
    "aws_secret": r"(?i)aws.{0,20}secret.{0,20}['\"][0-9a-zA-Z/+]{40}['\"]",
    "github_token": r"ghp_[a-zA-Z0-9]{36}",
    "openai_key": r"sk-[a-zA-Z0-9]{48}",
    "generic_api_key": r"(?i)(api_key|apikey|api-key)\s*[=:]\s*['\"][a-zA-Z0-9_\-]{20,}['\"]",
    "private_key": r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----",
    "jwt": r"eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+",
}

REDACT_PLACEHOLDER = "[REDACTED]"


def scan_secrets(content: str) -> list[str]:
    found = []
    for name, pattern in SECRET_PATTERNS.items():
        if re.search(pattern, content):
            found.append(name)
    return found


def redact_secrets(content: str) -> str:
    for pattern in SECRET_PATTERNS.values():
        content = re.sub(pattern, REDACT_PLACEHOLDER, content)
    return content
