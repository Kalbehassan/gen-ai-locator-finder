# SPDX-License-Identifier: MIT
"""Experimental locator ranker training utilities.

No default model is trained here. Synthetic examples are useful for smoke tests only;
they cannot establish production accuracy or generalize across applications.
Optional: scikit-learn, xgboost, lightgbm, and deep-learning runtimes.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TrainingEvaluation:
    """Transparent evaluation artifact for experimental ranking models."""

    sample_count: int
    accuracy: float
    caveat: str = "Synthetic data has limited value; holdout leakage and website diversity can invalidate claims."


def evaluate_synthetic_smoke_model(samples: list[tuple[list[float], int]]) -> TrainingEvaluation:
    """Run a dependency-light split-free smoke evaluation.

    This deliberately does not claim a learned model is production-ready.
    """
    if not samples:
        return TrainingEvaluation(sample_count=0, accuracy=0.0)
    correct = sum(1 for features, label in samples if (sum(features) >= 0.5) == bool(label))
    accuracy = correct / len(samples)
    return TrainingEvaluation(sample_count=len(samples), accuracy=round(accuracy, 4))


def generate_synthetic_samples(count: int = 40) -> list[tuple[list[float], int]]:
    """Generate deterministic synthetic samples for smoke testing only."""
    if count < 0:
        raise ValueError("count must be non-negative")
    samples: list[tuple[list[float], int]] = []
    for index in range(count):
        stable = 0.9 if index % 3 else 0.3
        unique = 0.85 if index % 2 else 0.4
        readable = 0.75 if index % 5 else 0.35
        label = int(stable + unique + readable >= 1.8)
        samples.append(([stable, unique, readable], label))
    return samples


def capability_report() -> dict[str, object]:
    """Return optional ML framework availability without importing heavy packages."""
    report: dict[str, object] = {"synthetic_smoke": True}
    for name in ("sklearn", "xgboost", "lightgbm", "torch", "tensorflow"):
        try:
            __import__(name)
            report[name] = True
        except ImportError:
            report[name] = False
    return report
