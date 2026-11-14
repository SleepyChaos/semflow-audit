"""Model-facing redaction and bounded batches; private audit history stays intact."""

import re

SECRET_KEY = re.compile(
    "(?:password|passwd|api[_-]?key|access[_-]?token|refresh[_-]?token|secret[_-]?key|authorization|client[_-]?secret|private[_-]?key)$",
    re.IGNORECASE,
)
SECRET_TEXT = [
    re.compile("(?i)(\\b(?:Bearer|Basic)\\s+)[A-Za-z0-9._~+/=-]+"),
    re.compile(
        "(?i)(\\b(?:password|passwd|api[_-]?key|access[_-]?token|refresh[_-]?token|secret[_-]?key|client[_-]?secret)(?:['\\\"]\\s*\\])?['\\\"]?\\s*[=:]\\s*['\\\"]?)[^\\s'\\\";,}]+"
    ),
    re.compile("\\b(?:sk-|ghp_|github_pat_)[A-Za-z0-9_-]{12,}"),
    re.compile(
        "(?s)-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----"
    ),
    re.compile("(?i)([a-z][a-z0-9+.-]*://[^\\s/:@]+:)[^\\s/@]+(?=@)"),
]


def redact(value):
    if isinstance(value, dict):
        return {
            key: "[凭据已隐藏]" if SECRET_KEY.search(key) else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        for pattern in SECRET_TEXT:
            value = pattern.sub(
                lambda match: (match[1] if match.lastindex else "") + "[凭据已隐藏]",
                value,
            )
    return value
