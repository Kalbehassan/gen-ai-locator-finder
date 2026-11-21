# SPDX-License-Identifier: MIT
"""Core local ChromaDB vector store.

Persistence is local by default and requires no paid API or account.
"""

from __future__ import annotations

from pathlib import Path

from app.vectors.base_store import BaseVectorStore


class ChromaVectorStore(BaseVectorStore):
    """Thin wrapper around persistent ChromaDB collections."""

    def __init__(self, directory: Path, collection_name: str) -> None:
        try:
            import chromadb
        except ImportError as exc:
            raise RuntimeError("Install core dependencies including chromadb") from exc

        directory.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(directory))
        self._collection = self._client.get_or_create_collection(collection_name)

    def add(
        self, identifiers: list[str], documents: list[str], embeddings: list[list[float]]
    ) -> None:
        """Upsert records into the local collection."""
        if not (len(identifiers) == len(documents) == len(embeddings)):
            raise ValueError("identifiers, documents and embeddings must have equal lengths")
        self._collection.upsert(  # type: ignore[arg-type]
            ids=identifiers,
            documents=documents,
            embeddings=embeddings,  # type: ignore[arg-type]
        )

    def query(self, embedding: list[float], limit: int = 5) -> list[dict[str, object]]:
        """Query the collection and normalize Chroma result keys."""
        if limit < 1:
            return []
        result = self._collection.query(  # type: ignore[arg-type]
            query_embeddings=[embedding],  # type: ignore[arg-type]
            n_results=min(limit, 100),
        )
        ids = (result.get("ids") or [[]])[0]
        documents = (result.get("documents") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        return [
            {"id": identifier, "document": document, "distance": distance}
            for identifier, document, distance in zip(ids, documents, distances, strict=False)
        ]

    def capabilities(self) -> dict[str, object]:
        """Report the store's local deployment status."""
        return {"name": "chroma", "offline": True, "distributed": False, "persistent": True}
