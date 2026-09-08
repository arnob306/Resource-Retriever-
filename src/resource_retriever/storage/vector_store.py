"""Abstract interface for chunk-vector storage, so callers never import chromadb directly."""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from resource_retriever.models.chunk import Chunk


@dataclass(frozen=True)
class VectorMatch:
    file_id: str
    chunk_index: int
    text: str
    page_start: int
    page_end: int
    content_hash: str
    score: float  # higher is more similar


class VectorStore(ABC):
    @abstractmethod
    def upsert_chunks(self, chunks: list[Chunk], embeddings: list[list[float]], content_hash: str) -> None: ...

    @abstractmethod
    def delete_by_file_id(self, file_id: str) -> None: ...

    @abstractmethod
    def has_file_hash(self, file_id: str, content_hash: str) -> bool: ...

    @abstractmethod
    def query(self, embedding: list[float], top_k: int) -> list[VectorMatch]: ...
