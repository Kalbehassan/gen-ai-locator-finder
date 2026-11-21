# SPDX-License-Identifier: MIT
"""Pydantic API contracts for locator discovery.

Core Stable: request validation and redacted response contracts.
Optional Provider Integrations: provider selection metadata.
Experimental: export options and framework adapters.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator

from app.browser.models import DOMSnapshot, ElementEvidence, VerificationEvidence


class LoginProfile(BaseModel):
    """Configurable authentication steps for a target application."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(default="standard_form", min_length=1, max_length=100)
    username_selector: str = Field(default="input[name='username']", min_length=1)
    password_selector: str = Field(default="input[type='password']", min_length=1)
    submit_selector: str = Field(default="button[type='submit']", min_length=1)
    success_url_fragment: str | None = None
    success_text: str | None = None


class LocatorRequest(BaseModel):
    """Public request for authenticated locator discovery."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    url: str
    username: str | None = None
    password: SecretStr | None = None
    login_profile: str = Field(default="standard_form", min_length=1, max_length=100)
    tenant: str | None = None
    description: str = Field(..., min_length=3, max_length=1000)
    capture_screenshot: bool = False
    provider: Literal["mock", "litellm", "genai"] = "mock"
    max_retries: int = Field(default=2, ge=0, le=10)

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            raise ValueError("url must start with http:// or https://")
        return value

    @field_validator("username", "tenant")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        return value if value else None

    @model_validator(mode="after")
    def require_credentials(self) -> LocatorRequest:
        """Require credentials when the request is not explicitly marked public."""
        if bool(self.username) != (self.password is not None):
            raise ValueError("username and password must be supplied together")
        return self


class LocatorCandidate(BaseModel):
    """Ranked static or dynamic locator strategy."""

    model_config = ConfigDict(extra="forbid")

    strategy: str = Field(min_length=1, max_length=100)
    value: str = Field(min_length=1, max_length=4000)
    confidence: float = Field(ge=0.0, le=1.0)
    explanation: str = Field(default="", max_length=2000)
    stability_score: float = Field(default=0.5, ge=0.0, le=1.0)
    uniqueness_score: float = Field(default=0.5, ge=0.0, le=1.0)
    readability_score: float = Field(default=0.5, ge=0.0, le=1.0)
    verified: bool = False
    match_count: int = Field(default=0, ge=0)
    rank: int | None = Field(default=None, ge=1)


class LocatorResult(BaseModel):
    """Detailed locator discovery result used internally and externally."""

    model_config = ConfigDict(extra="forbid")

    success: bool = False
    matched: bool = False
    best_locator: LocatorCandidate | None = None
    alternatives: list[LocatorCandidate] = Field(default_factory=list)
    evidence: ElementEvidence = Field(default_factory=ElementEvidence)
    verification: VerificationEvidence = Field(default_factory=VerificationEvidence)
    suggested_tests: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class AuthenticationResult(BaseModel):
    """Sanitized authentication outcome."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["success", "failed", "skipped", "not_required"]
    sensitive_fields_redacted: bool = True
    message: str = ""
    attempts: int = Field(default=0, ge=0)


class AgentState(BaseModel):
    """Serializable state for the 15-step locator agent workflow."""

    model_config = ConfigDict(extra="forbid")

    request: LocatorRequest
    profile: LoginProfile = Field(default_factory=LoginProfile)
    snapshot: DOMSnapshot | None = None
    candidates: list[LocatorCandidate] = Field(default_factory=list)
    result: LocatorResult = Field(default_factory=LocatorResult)
    authentication: AuthenticationResult = Field(
        default_factory=lambda: AuthenticationResult(status="skipped")
    )
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    step: str = "validate_request"
    warnings: list[str] = Field(default_factory=list)


class AgentResponse(BaseModel):
    """Stable public response contract."""

    model_config = ConfigDict(extra="forbid")

    success: bool
    matched: bool
    best_locator: LocatorCandidate | None = None
    alternatives: list[LocatorCandidate] = Field(default_factory=list)
    authentication: AuthenticationResult
    warnings: list[str] = Field(default_factory=list)
    evidence: ElementEvidence = Field(default_factory=ElementEvidence)
    suggested_tests: list[str] = Field(default_factory=list)


class ExportFormat(str):
    """Marker name is not used as an enum to permit schema-extension compatibility."""


def default_export_formats() -> list[Literal["json", "csv", "xlsx"]]:
    """Return the stable default export format list."""
    return ["json"]


class ExportRequest(BaseModel):
    """Optional report export request."""

    model_config = ConfigDict(extra="forbid")

    response: AgentResponse
    formats: list[Literal["json", "csv", "xlsx"]] = Field(default_factory=default_export_formats)
    include_evidence: bool = True
