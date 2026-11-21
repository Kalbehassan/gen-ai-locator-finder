# SPDX-License-Identifier: MIT
"""Honest rule and feature-based locator ranking.

Core Stable: deterministic weighted ranking with explicit feature scores.
Experimental: learned/scikit-learn rankers can be added behind training APIs.
Not claimed: untrained models or synthetic benchmarks have production accuracy.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.api.schemas import LocatorCandidate

STABILITY_WEIGHTS: dict[str, float] = {
    "id": 0.96,
    "test_id": 0.95,
    "accessible_label": 0.90,
    "role": 0.89,
    "name": 0.84,
    "placeholder": 0.76,
    "link_text": 0.73,
    "text": 0.70,
    "css": 0.68,
    "form_field_association": 0.67,
    "xpath": 0.58,
    "generated_stable_xpath": 0.62,
    "semantic_description": 0.64,
    "nearby_text": 0.55,
    "dom_ancestry": 0.50,
    "structural_fingerprint": 0.60,
    "embedding_similarity": 0.45,
    "visual_region": 0.38,
    "relative_position": 0.35,
    "playwright_chaining": 0.72,
    "self_healing_fallback_chain": 0.65,
    "retry_matching": 0.52,
    "llm_generated": 0.40,
}


@dataclass(frozen=True, slots=True)
class RankingFeatures:
    """Explainable features used to rank a candidate."""

    stability: float
    uniqueness: float
    readability: float
    verification: float

    def weighted_score(self) -> float:
        """Compute a bounded weighted score."""
        score = (
            0.38 * self.stability
            + 0.25 * self.uniqueness
            + 0.20 * self.readability
            + 0.17 * self.verification
        )
        return max(0.0, min(1.0, score))


def estimate_uniqueness(strategy: str, value: str) -> float:
    """Produce a conservative uniqueness estimate without live DOM frequency data."""
    del strategy
    if not value:
        return 0.0
    if " " not in value and len(value) >= 8:
        return 0.82
    if "#" in value or "[data-" in value:
        return 0.88
    if "button" in value.lower() or "input" in value.lower():
        return 0.67
    return 0.55


def estimate_readability(strategy: str, value: str) -> float:
    """Prefer short, semantic selectors over opaque machine-derived strings."""
    base = {
        "id": 0.96,
        "test_id": 0.95,
        "role": 0.94,
        "accessible_label": 0.92,
        "link_text": 0.88,
        "name": 0.84,
        "text": 0.82,
        "placeholder": 0.78,
        "css": 0.68,
        "xpath": 0.52,
    }.get(strategy, 0.50)
    length_penalty = max(0.0, (len(value) - 120) / 400)
    return max(0.0, min(1.0, base - length_penalty))


class LocatorRanker:
    """Rank and rank-live-verification candidate locators deterministically."""

    def score_candidate(
        self,
        *,
        strategy: str,
        value: str,
        explanation: str,
        verified: bool = False,
        unique_match: bool = False,
    ) -> LocatorCandidate:
        """Create a fully scored candidate from strategy-level heuristics."""
        stability = STABILITY_WEIGHTS.get(strategy, 0.45)
        uniqueness = estimate_uniqueness(strategy, value)
        readability = estimate_readability(strategy, value)
        if unique_match:
            uniqueness = max(uniqueness, 0.95)
        features = RankingFeatures(
            stability=stability,
            uniqueness=uniqueness,
            readability=readability,
            verification=1.0 if verified else 0.35,
        )
        score = features.weighted_score()
        if verified:
            score = min(1.0, score + 0.06)
        return LocatorCandidate(
            strategy=strategy,
            value=value,
            confidence=round(score, 4),
            explanation=explanation,
            stability_score=round(stability, 4),
            uniqueness_score=round(uniqueness, 4),
            readability_score=round(readability, 4),
            verified=verified,
            match_count=1 if unique_match else 0,
        )

    def rank(self, candidates: list[LocatorCandidate]) -> list[LocatorCandidate]:
        """Sort candidates descending and attach one-based rank positions."""
        ranked = sorted(candidates, key=lambda item: item.confidence, reverse=True)
        for rank, candidate in enumerate(ranked, start=1):
            candidate.rank = rank
        return ranked
