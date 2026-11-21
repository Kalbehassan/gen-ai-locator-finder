# Vector stores

## Core Stable: ChromaDB

ChromaDB is the default local, persistent vector store. It requires no paid API. Stored documents should contain sanitized descriptions and structural metadata, never passwords or session cookies.

## Optional: Milvus

Milvus is isolated behind the `vector` extra and must be separately deployed or authorized. It is not a fallback to local ChromaDB and should not receive credentials.

## Embeddings

The default embedding is a deterministic hashed local vector used for smoke testing and nearest-neighbor demonstration. Optional sentence-transformers support is clearly experimental and requires model downloads. Embedding similarity is only one ranking feature.
