# SPDX-License-Identifier: MIT

from pydantic import SecretStr

from app.security.redaction import REDACTED_MASK, redact_payload, redact_text


def test_redact_secretstr() -> None:
    assert redact_payload({"password": SecretStr("fixture-secret")}) == {"password": REDACTED_MASK}


def test_redact_inline_secret() -> None:
    result = redact_text("password=fixture-secret Authorization: Bearer abcdefghijkl")
    assert "fixture-secret" not in result
    assert "abcdefghijkl" not in result


def test_redact_extra_secret_and_email() -> None:
    result = redact_text(
        "fixture@example.com / explicitly-fixture-secret",
        ["explicitly-fixture-secret"],
        mask_emails=True,
    )
    assert "fixture@example.com" not in result
    assert "explicitly-fixture-secret" not in result
