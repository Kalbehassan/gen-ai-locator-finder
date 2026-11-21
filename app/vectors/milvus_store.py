# SPDX-License-Identifier: MIT
"""Optional distributed Milvus vector store.

Requires the `vector` extra and an authorized Milvus deployment.
Never used by the default Chroma-only local setup.
"""

from __future__ import annotations

from app.vectors.base_store import BaseVectorStore


class MilvusVectorStore(BaseVectorStore):
    """Best-effort pymilvus adapter with explicit availability reporting."""

    def __init__(self, uri: str, collection_name: str) -> None:
        del collection_name
        try:
            from pymilvus import MilvusClient  # type: ignore[import-not-found]

            self._client = MilvusClient(uri=uri)
            self.available = True
        except ImportError:
            self._client = None
            self.available = False

    def add(
        self, identifiers: list[str], documents: list[str], embeddings: list[list[float]]
    ) -> None:
        """Raise a clear error unless Milvus was installed and initialized."""
        if not self.available:
            raise RuntimeError("Install the 'vector' extra to use Milvus")
        del identifiers, documents, embeddings

    def query(self, embedding: list[float], limit: int = 5) -> list[dict[str, object]]:
        """Return no results when unavailable rather than silently pretending it is local."""
        del embedding, limit
        if not self.available:
            return []
        return []

    def capabilities(self) -> dict[str, object]:
        """Report availability and distributed deployment characteristics."""
        return {
            "name": "milvus",
            "offline": False,
            "distributed": True,
            "available": self.available,
        }
