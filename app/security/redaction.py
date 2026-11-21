# SPDX-License-Identifier: MIT
"""Centralized secret, credential, token, PII, and sensitive-field redaction.

Core Stable: payload, text, URL, and logging record redaction.
Optional: integrations may supply additional secret sources at runtime.
Experimental: screenshot masking helpers are implemented by the browser client.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, SecretStr

REDACTED_MASK = "[REDACTED]"

SENSITIVE_KEY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"password", re.IGNORECASE),
    re.compile(r"passwd", re.IGNORECASE),
    re.compile(r"secret", re.IGNORECASE),
    re.compile(r"api[_-]?key", re.IGNORECASE),
    re.compile(r"access[_-]?token", re.IGNORECASE),
    re.compile(r"refresh[_-]?token", re.IGNORECASE),
    re.compile(r"auth[_-]?token", re.IGNORECASE),
    re.compile(r"bearer", re.IGNORECASE),
    re.compile(r"authorization", re.IGNORECASE),
    re.compile(r"cookie", re.IGNORECASE),
    re.compile(r"session[_-]?id", re.IGNORECASE),
    re.compile(r"private[_-]?key", re.IGNORECASE),
    re.compile(r"client[_-]?secret", re.IGNORECASE),
)

EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")


class RedactedLogRecord(BaseModel):
    """Pydantic v2 model for a sanitized structured log entry."""

    model_config = ConfigDict(extra="forbid")

    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    level: str = Field(..., min_length=1)
    component: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    redaction_applied: bool = Field(default=True)
    redacted_fields: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


def is_sensitive_key(key: str) -> bool:
    """Return whether a key name identifies a secret or credential."""
    return any(pattern.search(key.strip()) for pattern in SENSITIVE_KEY_PATTERNS)


def redact_text(
    text: str,
    extra_secrets: Sequence[str] | None = None,
    *,
    mask_emails: bool = False,
) -> str:
    """Redact inline secrets, URL basic auth, bearer tokens, and known prefixes."""
    redacted = text
    for secret in extra_secrets or ():
        if secret and len(secret) >= 3:
            redacted = redacted.replace(secret, REDACTED_MASK)

    redacted = re.sub(
        r"(https?://[^:\s/@]+:)([^@\s/]+)(@)",
        rf"\g<1>{REDACTED_MASK}\g<3>",
        redacted,
    )
    redacted = re.sub(
        r"(?i)\b(password|passwd|secret|api[_-]?key|token|access_token|refresh_token)\s*([:=])\s*(['\"]?)([^\s,'\"&;]+)\3",
        rf"\1\2\3{REDACTED_MASK}\3",
        redacted,
    )
    redacted = re.sub(
        r"\b(Bearer|Basic)\s+[A-Za-z0-9\-._~+/]+=*",
        rf"\1 {REDACTED_MASK}",
        redacted,
        flags=re.IGNORECASE,
    )
    redacted = re.sub(
        r"\b(?:sk-|ghp_|gho_|github_pat_|AIza)[A-Za-z0-9_\-]{12,}\b",
        REDACTED_MASK,
        redacted,
    )
    if mask_emails:
        redacted = EMAIL_PATTERN.sub(REDACTED_MASK, redacted)
    return redacted


def redact_payload(
    payload: Any,
    extra_secrets: Sequence[str] | None = None,
    *,
    _seen_keys: list[str] | None = None,
) -> Any:
    """Recursively sanitize mappings, sequences, Pydantic models, and SecretStr values."""
    tracked = _seen_keys if _seen_keys is not None else []
    if isinstance(payload, SecretStr):
        tracked.append("SecretStr")
        return REDACTED_MASK
    if isinstance(payload, BaseModel):
        return redact_payload(payload.model_dump(mode="json"), extra_secrets, _seen_keys=tracked)
    if isinstance(payload, Mapping):
        result: dict[str, Any] = {}
        for key, value in payload.items():
            str_key = str(key)
            if is_sensitive_key(str_key):
                tracked.append(str_key)
                result[str_key] = REDACTED_MASK
            else:
                result[str_key] = redact_payload(value, extra_secrets, _seen_keys=tracked)
        return result
    if isinstance(payload, list):
        return [redact_payload(item, extra_secrets, _seen_keys=tracked) for item in payload]
    if isinstance(payload, tuple):
        return tuple(redact_payload(item, extra_secrets, _seen_keys=tracked) for item in payload)
    if isinstance(payload, str):
        return redact_text(payload, extra_secrets)
    return payload


def build_redacted_log_record(
    *,
    level: str,
    component: str,
    message: str,
    metadata: Mapping[str, Any] | None = None,
    extra_secrets: Sequence[str] | None = None,
) -> RedactedLogRecord:
    """Construct a validated log record with all metadata scrubbed."""
    seen_fields: list[str] = []
    safe_metadata: dict[str, Any] = {}
    for key, value in (metadata or {}).items():
        str_key = str(key)
        if is_sensitive_key(str_key):
            seen_fields.append(str_key)
            safe_metadata[str_key] = REDACTED_MASK
        else:
            safe_metadata[str_key] = redact_payload(value, extra_secrets, _seen_keys=seen_fields)
    return RedactedLogRecord(
        level=level.upper(),
        component=component,
        message=redact_text(message, extra_secrets),
        redacted_fields=sorted(set(seen_fields)),
        metadata=safe_metadata,
    )


class SecretRedactionFilter(logging.Filter):
    """Standard logging filter that scrubs messages and arguments before output."""

    def __init__(self, extra_secrets: Sequence[str] | None = None) -> None:
        super().__init__()
        self._extra_secrets = tuple(secret for secret in extra_secrets or () if secret)

    def filter(self, record: logging.LogRecord) -> bool:
        """Sanitize a log record in place."""
        if isinstance(record.msg, str):
            record.msg = redact_text(record.msg, self._extra_secrets)
        if isinstance(record.args, Mapping):
            record.args = redact_payload(dict(record.args), self._extra_secrets)
        elif isinstance(record.args, tuple):
            record.args = tuple(
                redact_text(arg, self._extra_secrets) if isinstance(arg, str) else arg
                for arg in record.args
            )
        return True
