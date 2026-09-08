"""Phase 1 ingestion: discover local PDFs, hash + extract page counts, upsert metadata.
No chunking/embedding here — that is index_service.py's job in a later phase.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

from resource_retriever.config import AppConfig
from resource_retriever.extraction.pdf_text_extractor import ExtractionError, extract_pages
from resource_retriever.hashing import compute_content_hash
from resource_retriever.ingestion.exclusion import load_exclusion_config
from resource_retriever.ingestion.local_walker import DiscoveredFile, walk_local_folder
from resource_retriever.models.file_record import FileRecord
from resource_retriever.storage.metadata_store import MetadataStore


@dataclass(frozen=True)
class IngestSummary:
    discovered: int
    new: int
    unchanged: int
    updated: int
    excluded: int
    failed: int


def run_ingest(root: Path, store: MetadataStore, app_config: AppConfig) -> IngestSummary:
    exclusion_config = load_exclusion_config(app_config)
    counts = {"discovered": 0, "new": 0, "unchanged": 0, "updated": 0, "excluded": 0, "failed": 0}

    for found in walk_local_folder(root, exclusion_config):
        counts["discovered"] += 1
        existing = store.get_by_path(found.local_path)

        if found.is_excluded:
            store.upsert_file(_build_record(existing, found, status="excluded", content_hash=None, page_count=None))
            counts["excluded"] += 1
            continue

        try:
            file_bytes = Path(found.local_path).read_bytes()
            content_hash = compute_content_hash(file_bytes)
            page_count = len(extract_pages(file_bytes))
        except (OSError, ExtractionError):
            store.upsert_file(
                _build_record(existing, found, status="extraction_failed", content_hash=None, page_count=None)
            )
            counts["failed"] += 1
            continue

        _bump_change_counter(counts, existing, content_hash)
        store.upsert_file(
            _build_record(existing, found, status="discovered", content_hash=content_hash, page_count=page_count)
        )

    return IngestSummary(**counts)


def _bump_change_counter(counts: dict, existing: Optional[FileRecord], content_hash: str) -> None:
    if existing is None:
        counts["new"] += 1
    elif existing.content_hash == content_hash:
        counts["unchanged"] += 1
    else:
        counts["updated"] += 1


def _build_record(
    existing: Optional[FileRecord],
    found: DiscoveredFile,
    *,
    status: str,
    content_hash: Optional[str],
    page_count: Optional[int],
) -> FileRecord:
    return FileRecord(
        id=existing.id if existing else str(uuid4()),
        source_type="local",
        local_path=found.local_path,
        drive_id=None,
        display_name=found.display_name,
        content_hash=content_hash,
        file_size=found.file_size,
        modified_time=found.modified_time,
        page_count=page_count,
        status=status,
        indexed_at=existing.indexed_at if existing else None,
        created_at=existing.created_at if existing else datetime.now(timezone.utc).isoformat(),
    )
