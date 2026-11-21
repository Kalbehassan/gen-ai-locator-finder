# SPDX-License-Identifier: MIT
"""Browser-domain Pydantic models.

Core Stable: DOM snapshots, bounding boxes, candidate elements and screenshot metadata.
Optional: richer accessibility/visual models may be supplied by Playwright or adapters.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class BoundingBox(BaseModel):
    """Viewport-relative element rectangle."""

    model_config = ConfigDict(extra="forbid")

    x: float = Field(ge=0)
    y: float = Field(ge=0)
    width: float = Field(default=0, ge=0)
    height: float = Field(default=0, ge=0)

    def to_list(self) -> list[float]:
        """Return the four-value API representation."""
        return [self.x, self.y, self.width, self.height]


class DOMSnapshot(BaseModel):
    """Redacted snapshot of the live page context."""

    model_config = ConfigDict(extra="forbid")

    url: str
    title: str = ""
    dom_html: str = Field(default="", description="Sanitized DOM fragment or document")
    visible_text: str = ""
    accessibility_tree: dict[str, object] = Field(default_factory=dict)
    screenshot_path: str | None = None
    captured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        value = value.strip()
        if not value.startswith(("http://", "https://")):
            raise ValueError("DOM snapshot URL must use HTTP or HTTPS")
        return value


class ElementEvidence(BaseModel):
    """Human-readable evidence associated with a matched element."""

    model_config = ConfigDict(extra="forbid")

    tag: str = ""
    text: str = ""
    accessible_name: str = ""
    role: str | None = None
    placeholder: str | None = None
    test_id: str | None = None
    id: str | None = None
    name: str | None = None
    bbox: list[float] = Field(default_factory=list, min_length=0, max_length=4)

    @model_validator(mode="after")
    def validate_bbox(self) -> ElementEvidence:
        if self.bbox:
            if len(self.bbox) != 4:
                raise ValueError("bbox must contain x, y, width, height")
            if any(value < 0 for value in self.bbox):
                raise ValueError("bbox values must be non-negative")
        return self


class CandidateElement(BaseModel):
    """A raw DOM candidate extracted before locator ranking."""

    model_config = ConfigDict(extra="forbid")

    element_id: str
    tag: str
    text: str = ""
    visible_text: str = ""
    accessible_name: str = ""
    role: str | None = None
    attributes: dict[str, str] = Field(default_factory=dict)
    bbox: BoundingBox | None = None
    dom_path: str = ""
    nearby_text: list[str] = Field(default_factory=list)


class VerificationEvidence(BaseModel):
    """Live verification details for a locator."""

    model_config = ConfigDict(extra="forbid")

    verified: bool = False
    match_count: int = Field(default=0, ge=0)
    unique_match: bool = False
    visible: bool = False
    enabled: bool = False
    elapsed_ms: float = Field(default=0, ge=0)
    error: str | None = None
