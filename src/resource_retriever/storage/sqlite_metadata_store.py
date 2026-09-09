"""SQLite-backed MetadataStore implementation."""

import sqlite3
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from resource_retriever.models.file_record import FileRecord
from resource_retriever.storage.metadata_store import MetadataStore

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"

_UPSERT_SQL = """
INSERT INTO files (id, source_type, local_path, drive_id, display_name, content_hash,
                    file_size, modified_time, page_count, status, indexed_at, created_at)
VALUES (:id, :source_type, :local_path, :drive_id, :display_name, :content_hash,
        :file_size, :modified_time, :page_count, :status, :indexed_at, :created_at)
ON CONFLICT(id) DO UPDATE SET
    source_type = excluded.source_type,
    local_path = excluded.local_path,
    drive_id = excluded.drive_id,
    display_name = excluded.display_name,
    content_hash = excluded.content_hash,
    file_size = excluded.file_size,
    modified_time = excluded.modified_time,
    page_count = excluded.page_count,
    status = excluded.status,
    indexed_at = excluded.indexed_at
"""


class SqliteMetadataStore(MetadataStore):
    def __init__(self, db_path: Path):
        db_path = Path(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(str(db_path))
        self._connection.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self) -> None:
        self._connection.executescript(_SCHEMA_PATH.read_text(encoding="utf-8"))
        self._connection.commit()

    def close(self) -> None:
        self._connection.close()

    def upsert_file(self, record: FileRecord) -> None:
        self._connection.execute(_UPSERT_SQL, asdict(record))
        self._connection.commit()

    def get_by_hash(self, content_hash: str) -> Optional[FileRecord]:
        return self._fetch_one("SELECT * FROM files WHERE content_hash = ?", (content_hash,))

    def get_by_path(self, local_path: str) -> Optional[FileRecord]:
        return self._fetch_one("SELECT * FROM files WHERE local_path = ?", (local_path,))

    def get_by_drive_id(self, drive_id: str) -> Optional[FileRecord]:
        return self._fetch_one("SELECT * FROM files WHERE drive_id = ?", (drive_id,))

    def get_by_id(self, file_id: str) -> Optional[FileRecord]:
        return self._fetch_one("SELECT * FROM files WHERE id = ?", (file_id,))

    def list_stale(self, discovered_ids: set[str], source_type: Optional[str] = None) -> list[FileRecord]:
        if source_type is None:
            rows = self._connection.execute("SELECT * FROM files WHERE status != 'excluded'").fetchall()
        else:
            rows = self._connection.execute(
                "SELECT * FROM files WHERE status != 'excluded' AND source_type = ?", (source_type,)
            ).fetchall()
        return [self._row_to_record(row) for row in rows if row["id"] not in discovered_ids]

    def delete_file(self, file_id: str) -> None:
        self._connection.execute("DELETE FROM files WHERE id = ?", (file_id,))
        self._connection.commit()

    def list_all(self, source_type: Optional[str] = None) -> list[FileRecord]:
        if source_type is None:
            rows = self._connection.execute("SELECT * FROM files").fetchall()
        else:
            rows = self._connection.execute(
                "SELECT * FROM files WHERE source_type = ?", (source_type,)
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def record_index_run(
        self,
        *,
        started_at: str,
        finished_at: str,
        files_discovered: int,
        files_reprocessed: int,
        files_skipped: int,
        files_deleted: int,
        files_failed: int,
    ) -> None:
        self._connection.execute(
            """INSERT INTO index_runs
               (started_at, finished_at, files_discovered, files_reprocessed,
                files_skipped, files_deleted, files_failed)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (started_at, finished_at, files_discovered, files_reprocessed, files_skipped, files_deleted, files_failed),
        )
        self._connection.commit()

    def record_search(self, *, query: str, latency_ms: int, result_count: int) -> None:
        self._connection.execute(
            "INSERT INTO search_log (query, latency_ms, result_count, searched_at) VALUES (?, ?, ?, ?)",
            (query, latency_ms, result_count, datetime.now(timezone.utc).isoformat()),
        )
        self._connection.commit()

    def search_stats(self) -> tuple[int, Optional[float]]:
        row = self._connection.execute("SELECT COUNT(*) AS total, AVG(latency_ms) AS avg_latency FROM search_log").fetchone()
        average = float(row["avg_latency"]) if row["avg_latency"] is not None else None
        return row["total"], average

    def _fetch_one(self, sql: str, params: tuple) -> Optional[FileRecord]:
        row = self._connection.execute(sql, params).fetchone()
        return self._row_to_record(row) if row is not None else None

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> FileRecord:
        return FileRecord(
            id=row["id"],
            source_type=row["source_type"],
            local_path=row["local_path"],
            drive_id=row["drive_id"],
            display_name=row["display_name"],
            content_hash=row["content_hash"],
            file_size=row["file_size"],
            modified_time=row["modified_time"],
            page_count=row["page_count"],
            status=row["status"],
            indexed_at=row["indexed_at"],
            created_at=row["created_at"],
        )
