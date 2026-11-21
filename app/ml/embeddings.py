# SPDX-License-Identifier: MIT
"""Text and locator embedding utilities.

Core Stable: deterministic hashed bag-of-character fallback requiring no model download.
Optional Provider Integrations: sentence-transformers and transformers.
Experimental Demos: cosine ranking between natural-language descriptions and locators.
"""

from __future__ import annotations

import hashlib
import math
from collections import Counter


class LocalEmbeddingProvider:
    """Small deterministic local embedding provider."""

    def __init__(self, dimensions: int = 128) -> None:
        if dimensions < 8:
            raise ValueError("dimensions must be at least 8")
        self.dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        """Embed text by hashing tokens into a bounded sparse vector."""
        tokens = text.lower().split()
        counts = Counter(tokens)
        vector = [0.0] * self.dimensions
        for token, count in counts.items():
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign * count
        norm = math.sqrt(sum(value * value for value in vector))
        if norm:
            vector = [value / norm for value in vector]
        return vector

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts in input order."""
        return [self.embed(text) for text in texts]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """Compute cosine similarity or return zero for incompatible vectors."""
    if not left or len(left) != len(right):
        return 0.0
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    return max(-1.0, min(1.0, dot / (left_norm * right_norm)))


class OptionalEmbeddingProvider:
    """Report optional model availability without importing it in the default path."""

    def __init__(self) -> None:
        self.available = False
        self.reason = "sentence-transformers is not installed"

    def load(self, model_name: str = "all-MiniLM-L6-v2") -> bool:
        """Attempt to load a model only when its optional extra is installed."""
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]

            self.model = SentenceTransformer(model_name)
            self.available = True
            self.reason = ""
            return True
        except ImportError as exc:
            self.reason = str(exc)
            return False

    def embed(self, text: str) -> list[float] | None:
        """Return model embeddings if the optional provider loaded successfully."""
        if not self.available:
            return None
        model = getattr(self, "model", None)
        if model is None:
            return None
        return [float(value) for value in model.encode([text])[0].tolist()]  # type: ignore[union-attr]
