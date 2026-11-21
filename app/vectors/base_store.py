# SPDX-License-Identifier: MIT
"""Vector store abstraction.

Core Stable: capability-neutral add/query interface.
The local Chroma implementation is the default; Milvus is optional.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseVectorStore(ABC):
    """Store locator text and embeddings for later nearest-neighbor lookup."""

    @abstractmethod
    def add(
        self, identifiers: list[str], documents: list[str], embeddings: list[list[float]]
    ) -> None:
        """Add or upsert records."""

    @abstractmethod
    def query(self, embedding: list[float], limit: int = 5) -> list[dict[str, object]]:
        """Query nearest stored records."""

    @abstractmethod
    def capabilities(self) -> dict[str, object]:
        """Return store status and deployment characteristics."""
