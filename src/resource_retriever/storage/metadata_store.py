"""Abstract interface for file metadata storage, so callers never import sqlite3 directly."""

from abc import ABC, abstractmethod
from typing import Optional

from resource_retriever.models.file_record import FileRecord


class MetadataStore(ABC):
    @abstractmethod
    def upsert_file(self, record: FileRecord) -> None: ...

    @abstractmethod
    def get_by_hash(self, content_hash: str) -> Optional[FileRecord]: ...

    @abstractmethod
    def get_by_path(self, local_path: str) -> Optional[FileRecord]: ...

    @abstractmethod
    def get_by_drive_id(self, drive_id: str) -> Optional[FileRecord]: ...

    @abstractmethod
    def list_stale(self, discovered_ids: set[str]) -> list[FileRecord]: ...

    @abstractmethod
    def delete_file(self, file_id: str) -> None: ...
