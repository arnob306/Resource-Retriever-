"""Phase 4 indexing: discover, decide, and embed Google Drive PDFs into the vector store.

Unlike local files (a cheap filesystem `ingest` discovery step, then a separate `index` embed
step), Drive discovery already costs an API call, so this module discovers, decides, and embeds
in one pass — every `find-resource index --source drive` run re-lists Drive directly and always
has fresh `md5Checksum`/`modifiedTime` to compare against, with no separate ingest step needed.
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from googleapiclient.discovery import Resource

from resource_retriever.chunking.chunker import chunk_pages
from resource_retriever.config import AppConfig
from resource_retriever.embedding.embedder import Embedder
from resource_retriever.extraction.pdf_text_extractor import extract_pages
from resource_retriever.indexing.index_service import IndexSummary
from resource_retriever.indexing.reindex_algorithm import Action, DiscoveredState, decide_action
from resource_retriever.ingestion.drive_download import stream_drive_file_bytes
from resource_retriever.ingestion.drive_walker import DiscoveredDriveFile, list_drive_pdfs
from resource_retriever.ingestion.exclusion import load_exclusion_config
from resource_retriever.models.chunk import Chunk
from resource_retriever.models.file_record import FileRecord
from resource_retriever.storage.metadata_store import MetadataStore
from resource_retriever.storage.vector_store import VectorStore

logger = logging.getLogger(__name__)

# Skip (and mark failed) a Drive file larger than this rather than buffering it fully into
# memory — generous for a teaching-PDF corpus, but bounds the worst case of a mislabeled file.
_MAX_DOWNLOAD_BYTES = 200 * 1024 * 1024


def run_drive_index(
    service: Resource, store: MetadataStore, vector_store: VectorStore, embedder: Embedder, app_config: AppConfig
) -> IndexSummary:
    exclusion_config = load_exclusion_config(app_config)
    started_at = datetime.now(timezone.utc).isoformat()
    counts = {"discovered": 0, "new": 0, "reprocessed": 0, "touched": 0, "skipped": 0, "deleted": 0, "failed": 0}
    seen_ids: set[str] = set()
    # Bulk-loaded once (mirrors index_service.py's local run_index using a single list_all() call)
    # instead of one get_by_drive_id() round-trip per Drive file — matters at full-corpus scale.
    existing_by_drive_id = {record.drive_id: record for record in store.list_all(source_type="drive")}

    for found in list_drive_pdfs(service, exclusion_config):
        existing = existing_by_drive_id.get(found.drive_id)
        record_id = existing.id if existing else str(uuid4())
        # list_stale (used by _purge_vanished below) compares against the internal FileRecord.id
        # primary key, not the external Drive id — seen_ids must track the same identity.
        seen_ids.add(record_id)

        if found.is_excluded:
            if existing is not None and existing.indexed_at is not None:
                vector_store.delete_by_file_id(record_id)
            store.upsert_file(_build_record(existing, found, record_id, status="excluded", clear_indexed_at=True))
            continue

        counts["discovered"] += 1
        discovered = DiscoveredState(
            content_hash=found.md5_checksum, modified_time=found.modified_time, file_size=found.file_size
        )
        existing_for_decision = existing if existing is not None and existing.status == "indexed" else None
        action = decide_action(discovered, existing_for_decision)

        if action in (Action.NEW, Action.REPROCESS):
            outcome = _embed_drive_file(service, found, existing, record_id, store, vector_store, embedder, app_config)
            counts[outcome] += 1
        elif action == Action.SKIP_BUT_TOUCH:
            store.upsert_file(_build_record(existing, found, record_id, status=existing.status))
            counts["touched"] += 1
        else:
            counts["skipped"] += 1

    counts["deleted"] = _purge_vanished(store, vector_store, seen_ids)
    finished_at = datetime.now(timezone.utc).isoformat()
    store.record_index_run(
        started_at=started_at,
        finished_at=finished_at,
        files_discovered=counts["discovered"],
        files_reprocessed=counts["new"] + counts["reprocessed"],
        files_skipped=counts["skipped"] + counts["touched"],
        files_deleted=counts["deleted"],
        files_failed=counts["failed"],
    )
    return IndexSummary(**counts)


def _embed_drive_file(
    service: Resource,
    found: DiscoveredDriveFile,
    existing: Optional[FileRecord],
    record_id: str,
    store: MetadataStore,
    vector_store: VectorStore,
    embedder: Embedder,
    app_config: AppConfig,
) -> str:
    is_new = existing is None or existing.status != "indexed"
    if found.file_size > _MAX_DOWNLOAD_BYTES:
        logger.warning("Skipping Drive file %s: %d bytes exceeds the download limit", found.display_name, found.file_size)
        store.upsert_file(_build_record(existing, found, record_id, status="extraction_failed"))
        return "failed"
    try:
        file_bytes = stream_drive_file_bytes(service, found.drive_id)
        pages = extract_pages(file_bytes)
        spans = chunk_pages(pages, embedder.tokenizer, app_config.chunk_window_tokens, app_config.chunk_overlap_tokens)
        chunks = [
            Chunk(
                file_id=record_id,
                chunk_index=i,
                text=span.text,
                page_start=span.page_start,
                page_end=span.page_end,
                char_start=span.char_start,
                char_end=span.char_end,
            )
            for i, span in enumerate(spans)
        ]
        embed_texts = [f"{found.display_name} {chunk.text}" for chunk in chunks]
        embeddings = embedder.embed_documents(embed_texts)
        vector_store.delete_by_file_id(record_id)
        vector_store.upsert_chunks(chunks, embeddings, found.md5_checksum)
    except Exception as exc:
        # Broad on purpose, matching index_service.py's local-file contract: one bad Drive file
        # (download error, corrupt PDF, embedding failure) must never abort the whole Drive run.
        logger.warning("Failed to index Drive file %s (%s): %s", found.display_name, found.drive_id, exc)
        store.upsert_file(_build_record(existing, found, record_id, status="extraction_failed"))
        return "failed"

    store.upsert_file(
        _build_record(existing, found, record_id, status="indexed", page_count=len(pages), touch_indexed_at=True)
    )
    return "new" if is_new else "reprocessed"


def _build_record(
    existing: Optional[FileRecord],
    found: DiscoveredDriveFile,
    record_id: str,
    *,
    status: str,
    page_count: Optional[int] = None,
    touch_indexed_at: bool = False,
    clear_indexed_at: bool = False,
) -> FileRecord:
    if touch_indexed_at:
        indexed_at = datetime.now(timezone.utc).isoformat()
    elif clear_indexed_at:
        indexed_at = None
    else:
        indexed_at = existing.indexed_at if existing else None

    return FileRecord(
        id=record_id,
        source_type="drive",
        local_path=None,
        drive_id=found.drive_id,
        display_name=found.display_name,
        content_hash=found.md5_checksum,
        file_size=found.file_size,
        modified_time=found.modified_time,
        page_count=page_count if page_count is not None else (existing.page_count if existing else None),
        status=status,
        indexed_at=indexed_at,
        created_at=existing.created_at if existing else datetime.now(timezone.utc).isoformat(),
    )


def _purge_vanished(store: MetadataStore, vector_store: VectorStore, seen_ids: set[str]) -> int:
    # list_stale already excludes status='excluded' rows, matching index_service.py's local
    # behavior: an excluded file whose Drive copy later vanishes stays tracked, not purged.
    stale = store.list_stale(seen_ids, source_type="drive")
    for record in stale:
        vector_store.delete_by_file_id(record.id)
        store.delete_file(record.id)
    return len(stale)
