"""ChromaDB-backed VectorStore implementation.

Telemetry is explicitly disabled (Chroma's PostHog telemetry is on by default, which would be a
network call from a tool whose entire premise is local-only), embedding_function is explicitly
None (we always supply our own vectors — otherwise Chroma silently downloads its bundled ONNX
MiniLM), and the collection's distance space is set to cosine at creation time since it is
immutable afterward (the default is squared L2).
"""

from pathlib import Path

import chromadb
from chromadb.config import Settings

from resource_retriever.models.chunk import Chunk
from resource_retriever.storage.vector_store import VectorMatch, VectorStore

_COLLECTION_NAME = "teaching_resources"


class ChromaVectorStore(VectorStore):
    def __init__(self, persist_dir: Path):
        persist_dir = Path(persist_dir)
        persist_dir.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=str(persist_dir), settings=Settings(anonymized_telemetry=False)
        )
        self._collection = self._client.get_or_create_collection(
            name=_COLLECTION_NAME,
            embedding_function=None,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert_chunks(self, chunks: list[Chunk], embeddings: list[list[float]], content_hash: str) -> None:
        if not chunks:
            return
        self._collection.upsert(
            ids=[f"{chunk.file_id}:{chunk.chunk_index}" for chunk in chunks],
            embeddings=embeddings,
            documents=[chunk.text for chunk in chunks],
            metadatas=[
                {
                    "file_id": chunk.file_id,
                    "content_hash": content_hash,
                    "page_start": chunk.page_start,
                    "page_end": chunk.page_end,
                    "char_start": chunk.char_start,
                    "char_end": chunk.char_end,
                    "chunk_index": chunk.chunk_index,
                }
                for chunk in chunks
            ],
        )

    def delete_by_file_id(self, file_id: str) -> None:
        self._collection.delete(where={"file_id": file_id})

    def has_file_hash(self, file_id: str, content_hash: str) -> bool:
        result = self._collection.get(
            where={"$and": [{"file_id": file_id}, {"content_hash": content_hash}]},
            limit=1,
        )
        return len(result["ids"]) > 0

    def query(self, embedding: list[float], top_k: int) -> list[VectorMatch]:
        result = self._collection.query(
            query_embeddings=[embedding],
            n_results=top_k,
            include=["metadatas", "documents", "distances"],
        )
        if not result["ids"] or not result["ids"][0]:
            return []

        matches = []
        for metadata, document, distance in zip(
            result["metadatas"][0], result["documents"][0], result["distances"][0]
        ):
            matches.append(
                VectorMatch(
                    file_id=metadata["file_id"],
                    chunk_index=metadata["chunk_index"],
                    text=document,
                    page_start=metadata["page_start"],
                    page_end=metadata["page_end"],
                    content_hash=metadata["content_hash"],
                    score=1.0 - distance,
                )
            )
        return matches
