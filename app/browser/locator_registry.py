# SPDX-License-Identifier: MIT
"""Strategy registry for static and dynamic locator candidate generation.

Core Stable: deterministic candidate generation and fallback chain construction.
Experimental: semantic, embedding, visual, LLM and structural strategies.
Future Roadmap: learned ranking and cross-page template adaptation.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.browser.models import CandidateElement

STATIC_STRATEGIES = (
    "id",
    "name",
    "css",
    "xpath",
    "link_text",
    "role",
    "accessible_label",
    "placeholder",
    "text",
    "test_id",
    "form_field_association",
)
DYNAMIC_STRATEGIES = (
    "semantic_description",
    "nearby_text",
    "relative_position",
    "dom_ancestry",
    "structural_fingerprint",
    "embedding_similarity",
    "visual_region",
    "generated_stable_xpath",
    "playwright_chaining",
    "self_healing_fallback_chain",
    "retry_matching",
    "llm_generated",
)


def escape_css_attribute(value: str) -> str:
    """Escape a text value for use inside a CSS attribute selector."""
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\A ")


def escape_xpath_literal(value: str) -> str:
    """Return an XPath 1.0 literal expression for arbitrary text."""
    if "'" not in value:
        return f"'{value}'"
    if '"' not in value:
        return f'"{value}"'
    parts = value.split("'")
    return "concat(" + ', "\'", '.join(f"'{part}'" for part in parts) + ")"


def tokenize_description(description: str) -> set[str]:
    """Normalize a natural-language description into lowercase terms."""
    return {token for token in re.findall(r"[a-z0-9]+", description.lower()) if len(token) > 1}


class LocatorStrategy(StrEnum):
    """Enumeration of all static and dynamic locator strategies."""

    ID = "id"
    NAME = "name"
    CSS = "css"
    XPATH = "xpath"
    LINK_TEXT = "link_text"
    ROLE = "role"
    ACCESSIBLE_LABEL = "accessible_label"
    PLACEHOLDER = "placeholder"
    TEXT = "text"
    TEST_ID = "test_id"
    FORM_FIELD_ASSOCIATION = "form_field_association"
    SEMANTIC_DESCRIPTION = "semantic_description"
    NEARBY_TEXT = "nearby_text"
    RELATIVE_POSITION = "relative_position"
    DOM_ANCESTRY = "dom_ancestry"
    STRUCTURAL_FINGERPRINT = "structural_fingerprint"
    EMBEDDING_SIMILARITY = "embedding_similarity"
    VISUAL_REGION = "visual_region"
    GENERATED_STABLE_XPATH = "generated_stable_xpath"
    PLAYWRIGHT_CHAINING = "playwright_chaining"
    SELF_HEALING_FALLBACK_CHAIN = "self_healing_fallback_chain"
    RETRY_MATCHING = "retry_matching"
    LLM_GENERATED = "llm_generated"


class DOMNodeInfo(BaseModel):
    """Normalized browser element used by richer static and dynamic generation."""

    model_config = ConfigDict(extra="allow")

    tag: str = Field(..., min_length=1)
    element_id: str | None = None
    name: str | None = None
    classes: list[str] = Field(default_factory=list)
    role: str | None = None
    accessible_name: str | None = None
    aria_label: str | None = None
    placeholder: str | None = None
    text: str | None = None
    test_id: str | None = None
    href: str | None = None
    input_type: str | None = None
    form_id: str | None = None
    label_text: str | None = None
    nearby_text: str | None = None
    ancestry: list[str] = Field(default_factory=list)
    xpath: str | None = None
    css: str | None = None
    bbox: list[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])
    visible: bool = True
    attributes: dict[str, object] = Field(default_factory=dict)


class LocatorCandidate(BaseModel):
    """Candidate locator with quality scores, verification metadata, and risks."""

    model_config = ConfigDict(extra="forbid")

    strategy: LocatorStrategy
    value: str = Field(..., min_length=1)
    playwright_expr: str = Field(..., min_length=1)
    target_tag: str = "unknown"
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    stability_score: float = Field(default=0.5, ge=0.0, le=1.0)
    uniqueness_score: float = Field(default=0.5, ge=0.0, le=1.0)
    readability_score: float = Field(default=0.5, ge=0.0, le=1.0)
    relevance_score: float = Field(default=0.5, ge=0.0, le=1.0)
    explanation: str = ""
    risks: list[str] = Field(default_factory=list)
    verified: bool = False
    match_count: int = Field(default=0, ge=0)
    evidence: dict[str, object] = Field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ScoringWeights:
    """Weights used to combine stability, uniqueness, readability and relevance."""

    stability: float = 0.35
    uniqueness: float = 0.25
    readability: float = 0.15
    relevance: float = 0.25

    def normalized(self) -> ScoringWeights:
        total = self.stability + self.uniqueness + self.readability + self.relevance
        if total <= 0:
            return ScoringWeights()
        return ScoringWeights(
            stability=self.stability / total,
            uniqueness=self.uniqueness / total,
            readability=self.readability / total,
            relevance=self.relevance / total,
        )


class LocatorRegistry:
    """Rich registry for Playwright and semantic candidate generation."""

    def __init__(self, weights: ScoringWeights | None = None) -> None:
        self.weights = (weights or ScoringWeights()).normalized()

    @staticmethod
    def _tokens(value: str | None) -> set[str]:
        return {
            token.lower() for token in re.findall(r"[a-zA-Z0-9_-]+", value or "") if len(token) > 1
        }

    def relevance(self, node: DOMNodeInfo, description: str) -> float:
        """Compute a transparent lexical overlap score; it is not a trained probability."""
        query = self._tokens(description)
        signals = (
            node.text,
            node.accessible_name,
            node.aria_label,
            node.placeholder,
            node.label_text,
            node.nearby_text,
        )
        document = set().union(*(self._tokens(signal) for signal in signals))
        if not query:
            return 0.5
        if not document:
            return 0.1
        coverage = len(query & document) / len(query)
        jaccard = len(query & document) / len(query | document)
        return round(min(1.0, 0.55 * coverage + 0.25 * jaccard), 4)

    @staticmethod
    def evidence(node: DOMNodeInfo) -> dict[str, object]:
        """Return privacy-safe element evidence."""
        bbox = node.bbox if len(node.bbox) == 4 else [0.0, 0.0, 0.0, 0.0]
        return {
            "tag": node.tag,
            "text": node.text or "",
            "accessible_name": node.accessible_name or node.aria_label or node.label_text or "",
            "bbox": bbox,
            "visible": node.visible,
        }

    @staticmethod
    def structural_fingerprint(node: DOMNodeInfo) -> str:
        """Hash non-secret structural and semantic fields into a short fingerprint."""
        excluded = {"password", "token", "authorization", "cookie", "secret"}
        safe_attributes = sorted(
            (key, str(value))
            for key, value in node.attributes.items()
            if key.lower() not in excluded
        )
        payload = repr((node.tag, node.role, node.input_type, node.ancestry[-4:], safe_attributes))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def generate_static_candidates(
        self, node: DOMNodeInfo, description: str
    ) -> list[dict[str, object]]:
        """Generate stable role, label, test-id, text and structural candidates."""
        relevance = self.relevance(node, description)
        evidence = self.evidence(node)
        label = node.accessible_name or node.aria_label or node.label_text or node.text or ""
        candidates: list[dict[str, object]] = []

        if node.test_id:
            candidates.append(
                self._candidate(
                    LocatorStrategy.TEST_ID,
                    f"[data-testid='{node.test_id}']",
                    f'page.get_by_test_id("{node.test_id}")',
                    node,
                    0.94,
                    0.92,
                    0.92,
                    relevance,
                    evidence,
                )
            )
        if node.role or node.tag in {"button", "a", "input", "select", "textarea"}:
            role = node.role or ("button" if node.tag in {"button", "a"} else "textbox")
            candidates.append(
                self._candidate(
                    LocatorStrategy.ROLE,
                    f"{role}[name='{label}']",
                    f'page.get_by_role("{role}", name="{label}")',
                    node,
                    0.91,
                    0.88,
                    0.96,
                    relevance,
                    evidence,
                )
            )
        if node.label_text or node.aria_label:
            candidates.append(
                self._candidate(
                    LocatorStrategy.ACCESSIBLE_LABEL,
                    f"label={label}",
                    f'page.get_by_label("{label}")',
                    node,
                    0.88,
                    0.86,
                    0.95,
                    relevance,
                    evidence,
                )
            )
        if node.placeholder:
            candidates.append(
                self._candidate(
                    LocatorStrategy.PLACEHOLDER,
                    f"[placeholder='{node.placeholder}']",
                    f'page.get_by_placeholder("{node.placeholder}")',
                    node,
                    0.76,
                    0.78,
                    0.90,
                    relevance,
                    evidence,
                )
            )
        if node.element_id:
            candidates.append(
                self._candidate(
                    LocatorStrategy.ID,
                    f"#{node.element_id}",
                    f'page.locator("#{node.element_id}")',
                    node,
                    0.86 if not self._looks_dynamic(node.element_id) else 0.35,
                    0.95,
                    0.89,
                    relevance,
                    evidence,
                )
            )
        if node.text:
            candidates.append(
                self._candidate(
                    LocatorStrategy.TEXT,
                    f"text={node.text}",
                    f'page.get_by_text("{node.text}", exact=False)',
                    node,
                    0.72,
                    0.70,
                    0.91,
                    relevance,
                    evidence,
                )
            )
        if node.xpath:
            candidates.append(
                self._candidate(
                    LocatorStrategy.XPATH,
                    node.xpath,
                    f'page.locator("xpath={node.xpath}")',
                    node,
                    0.68,
                    0.78,
                    0.55,
                    relevance,
                    evidence,
                )
            )
        return candidates

    def generate_dynamic_candidates(
        self, node: DOMNodeInfo, description: str
    ) -> list[dict[str, object]]:
        """Generate explicit dynamic, context, visual, retry and fallback candidates."""
        relevance = self.relevance(node, description)
        evidence = self.evidence(node)
        label = node.accessible_name or node.aria_label or node.text or node.placeholder or node.tag
        candidates = [
            self._candidate(
                LocatorStrategy.SEMANTIC_DESCRIPTION,
                f"semantic:{node.tag}('{label}')",
                f'page.get_by_text("{label}", exact=False)',
                node,
                0.87,
                0.80,
                0.94,
                relevance,
                evidence,
            ),
            self._candidate(
                LocatorStrategy.STRUCTURAL_FINGERPRINT,
                self.structural_fingerprint(node),
                f'page.locator("{node.tag}")',
                node,
                0.74,
                0.83,
                0.60,
                relevance,
                evidence,
            ),
            self._candidate(
                LocatorStrategy.PLAYWRIGHT_CHAINING,
                "ancestor >> element",
                f'page.locator("main").get_by_text("{label}")',
                node,
                0.84,
                0.88,
                0.85,
                relevance,
                evidence,
            ),
            self._candidate(
                LocatorStrategy.SELF_HEALING_FALLBACK_CHAIN,
                "; ".join(filter(None, (node.test_id, node.element_id, node.xpath))),
                f'page.locator("{node.xpath or node.tag}")',
                node,
                0.89,
                0.84,
                0.76,
                relevance,
                evidence,
            ),
            self._candidate(
                LocatorStrategy.RETRY_MATCHING,
                "retry(3, 250ms)",
                f'page.get_by_text("{label}", exact=False)',
                node,
                0.82,
                0.78,
                0.81,
                relevance,
                evidence,
            ),
        ]
        if node.nearby_text:
            candidates.append(
                self._candidate(
                    LocatorStrategy.NEARBY_TEXT,
                    node.nearby_text,
                    f'page.get_by_text("{node.nearby_text}")',
                    node,
                    0.77,
                    0.79,
                    0.78,
                    relevance,
                    evidence,
                )
            )
        if len(node.bbox) == 4:
            region = (
                f"bbox={node.bbox[0]:.0f},{node.bbox[1]:.0f},{node.bbox[2]:.0f},{node.bbox[3]:.0f}"
            )
            candidates.append(
                self._candidate(
                    LocatorStrategy.VISUAL_REGION,
                    region,
                    f'page.locator("{node.tag}").first',
                    node,
                    0.63,
                    0.70,
                    0.77,
                    relevance,
                    evidence,
                )
            )
        return candidates

    @staticmethod
    def _looks_dynamic(identifier: str) -> bool:
        return bool(re.search(r"(?:^r:|[0-9a-f]{8}-|\d{5,}|react\d+)", identifier, re.IGNORECASE))

    def _candidate(
        self,
        strategy: LocatorStrategy,
        value: str,
        playwright_expr: str,
        node: DOMNodeInfo,
        stability: float,
        uniqueness: float,
        readability: float,
        relevance: float,
        evidence: dict[str, object],
    ) -> dict[str, object]:
        """Compose an explainable scored candidate dictionary."""
        confidence = (
            self.weights.stability * stability
            + self.weights.uniqueness * uniqueness
            + self.weights.readability * readability
            + self.weights.relevance * relevance
        )
        return {
            "strategy": strategy.value,
            "value": value,
            "playwright_expr": playwright_expr,
            "target_tag": node.tag,
            "confidence": round(min(1.0, confidence), 4),
            "stability_score": stability,
            "uniqueness_score": uniqueness,
            "readability_score": readability,
            "relevance_score": relevance,
            "explanation": f"Matches {strategy.value} through DOM and accessibility context.",
            "risks": ["Verify live uniqueness and retain a fallback chain."],
            "evidence": evidence,
        }

    @staticmethod
    def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
        """Compute bounded cosine similarity for optional embeddings."""
        if not left or len(left) != len(right):
            return 0.0
        left_norm = math.sqrt(sum(value * value for value in left))
        right_norm = math.sqrt(sum(value * value for value in right))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        dot = sum(a * b for a, b in zip(left, right, strict=True))
        return round(max(-1.0, min(1.0, dot / (left_norm * right_norm))), 4)

    def generate_candidates(
        self,
        nodes: list[DOMNodeInfo],
        description: str,
        *,
        include_dynamic: bool = True,
        embedding_similarities: dict[int, float] | None = None,
    ) -> list[LocatorCandidate]:
        """Generate and rank Pydantic candidate models across normalized DOM nodes."""
        raw: list[dict[str, object]] = []
        for index, node in enumerate(nodes):
            raw.extend(self.generate_static_candidates(node, description))
            if include_dynamic:
                dynamic = self.generate_dynamic_candidates(node, description)
                if embedding_similarities and index in embedding_similarities:
                    similarity = embedding_similarities[index]
                    for candidate in dynamic:
                        candidate = dict(candidate)
                        candidate["relevance_score"] = similarity
                        candidate["confidence"] = round(
                            min(1.0, float(str(candidate["confidence"])) * 0.6 + similarity * 0.4),
                            4,
                        )
                        raw.append(candidate)
                else:
                    raw.extend(dynamic)
        return self.rank_candidates(raw)

    def rank_candidates(
        self,
        candidates: Sequence[dict[str, object] | LocatorCandidate],
    ) -> list[LocatorCandidate]:
        """Normalize, score, and sort explainable candidate dictionaries."""
        models = [LocatorCandidate.model_validate(candidate) for candidate in candidates]
        scored: list[LocatorCandidate] = []
        for candidate in models:
            composite = (
                self.weights.stability * candidate.stability_score
                + self.weights.uniqueness * candidate.uniqueness_score
                + self.weights.readability * candidate.readability_score
                + self.weights.relevance * candidate.relevance_score
            )
            if candidate.verified and candidate.match_count == 1:
                composite += 0.04
            elif candidate.verified and candidate.match_count > 1:
                composite -= 0.08
            scored.append(
                candidate.model_copy(
                    update={"confidence": round(max(0.01, min(0.99, composite)), 4)}
                )
            )
        return sorted(
            scored,
            key=lambda candidate: (
                candidate.confidence,
                candidate.stability_score,
                candidate.uniqueness_score,
            ),
            reverse=True,
        )

    @staticmethod
    def summarize_strategies(candidates: Sequence[LocatorCandidate]) -> dict[str, int]:
        """Count candidates grouped by public strategy name."""
        counts = Counter(candidate.strategy.value for candidate in candidates)
        return dict(sorted(counts.items()))

    def generate_static(self, element: CandidateElement) -> list[tuple[str, str, str]]:
        """Adapter: generate tuple-based static candidates for the core agent."""
        node = self._candidate_element_to_node(element)
        candidates = self.generate_static_candidates(node, element.text or "")
        return [
            (str(item["strategy"]), str(item["value"]), str(item["explanation"]))
            for item in candidates
        ]

    def generate_dynamic(
        self, element: CandidateElement, description: str
    ) -> list[tuple[str, str, str]]:
        """Adapter: generate tuple-based dynamic candidates for the core agent."""
        node = self._candidate_element_to_node(element)
        candidates = self.generate_dynamic_candidates(node, description)
        return [
            (str(item["strategy"]), str(item["value"]), str(item["explanation"]))
            for item in candidates
        ]

    def fallback_chain(self, candidates: list[tuple[str, str, str]]) -> list[tuple[str, str, str]]:
        """Deduplicate and prioritize a stable self-healing fallback chain."""
        priorities = {
            "test_id": 0,
            "id": 1,
            "role": 2,
            "accessible_label": 3,
            "text": 4,
            "css": 5,
            "xpath": 6,
        }
        unique = {
            (strategy, value): (strategy, value, explanation)
            for strategy, value, explanation in candidates
        }
        return sorted(unique.values(), key=lambda candidate: priorities.get(candidate[0], 99))

    @staticmethod
    def _candidate_element_to_node(element: CandidateElement) -> DOMNodeInfo:
        """Normalize CandidateElement into DOMNodeInfo without exposing sensitive values."""
        attributes: dict[str, object] = {
            key: str(value) for key, value in element.attributes.items()
        }
        element_id = attributes.get("id")
        name = attributes.get("name")
        aria_label = attributes.get("aria-label")
        placeholder = attributes.get("placeholder")
        test_id = attributes.get("data-testid")
        href = attributes.get("href")
        input_type = attributes.get("type")
        return DOMNodeInfo(
            tag=element.tag,
            element_id=element_id if isinstance(element_id, str) else element.element_id,
            name=name if isinstance(name, str) else None,
            role=element.role,
            accessible_name=element.accessible_name,
            aria_label=aria_label if isinstance(aria_label, str) else None,
            placeholder=placeholder if isinstance(placeholder, str) else None,
            text=element.text,
            test_id=test_id if isinstance(test_id, str) else None,
            href=href if isinstance(href, str) else None,
            input_type=input_type if isinstance(input_type, str) else None,
            nearby_text=" | ".join(element.nearby_text),
            ancestry=element.dom_path.split(" > ") if element.dom_path else [],
            xpath=element.dom_path,
            bbox=(
                [element.bbox.x, element.bbox.y, element.bbox.width, element.bbox.height]
                if element.bbox is not None
                else [0.0, 0.0, 0.0, 0.0]
            ),
            visible=True,
            attributes=attributes,
        )


class LegacyLocatorRegistryV1(LocatorRegistry):
    """Legacy class for backward compatibility with version 1.x."""

    def __init__(self, weights: ScoringWeights | None = None) -> None:
        super().__init__(weights)

    def generate_candidates(
        self,
        nodes: list[DOMNodeInfo],
        description: str,
        *,
        include_dynamic: bool = True,
        embedding_similarities: dict[int, float] | None = None,
    ) -> list[LocatorCandidate]:
        """Generate and rank Pydantic candidate models across normalized DOM nodes."""
        candidates = super().generate_candidates(
            nodes,
            description,
            include_dynamic=include_dynamic,
            embedding_similarities=embedding_similarities,
        )
        # For legacy compatibility, truncate to 3 candidates
        return candidates[:3]
