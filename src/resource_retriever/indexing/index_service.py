"""Phase 2 indexing: embed already-tracked local files (from `ingest`) into the vector store.

Operates over files already discovered by `ingest` (does not walk directories itself) — for each
tracked local file it re-stats the on-disk file, applies a cheap mtime/size pre-check to decide
whether a rehash is warranted, runs that through `reindex_algorithm.decide_action`, and extracts,
chunks, and embeds only files that are new, changed, or were never successfully indexed before.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from resource_retriever.chunking.chunker import chunk_pages
from resource_retriever.config import AppConfig
from resource_retriever.embedding.embedder import Embedder
from resource_retriever.extraction.pdf_text_extractor import extract_pages
from resource_retriever.hashing import compute_content_hash
from resource_retriever.indexing.reindex_algorithm import Action, DiscoveredState, decide_action
from resource_retriever.models.chunk import Chunk
from resource_retriever.models.file_record import FileRecord
from resource_retriever.storage.metadata_store import MetadataStore
from resource_retriever.storage.vector_store import VectorStore

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IndexSummary:
    discovered: int
    new: int
    reprocessed: int
    touched: int
    skipped: int
    deleted: int
    failed: int


def run_index(
    store: MetadataStore, vector_store: VectorStore, embedder: Embedder, app_config: AppConfig, *, force_rehash: bool = False
) -> IndexSummary:
    started_at = datetime.now(timezone.utc).isoformat()
    counts = {"discovered": 0, "new": 0, "reprocessed": 0, "touched": 0, "skipped": 0, "deleted": 0, "failed": 0}
    processed_ids: set[str] = set()

    for record in store.list_all(source_type="local"):
        if record.status == "excluded":
            continue
        counts["discovered"] += 1
        try:
            discovered = _resolve_discovered_state(record, force_rehash)
        except OSError as exc:
            logger.warning("Failed to stat/hash %s: %s", record.local_path, exc)
            processed_ids.add(record.id)  # exists on disk; don't let list_stale purge it
            counts["failed"] += 1
            continue
        if discovered is None:
            continue  # missing on disk; caught by list_stale below
        processed_ids.add(record.id)
        outcome = _apply_action(record, discovered, store, vector_store, embedder, app_config)
        counts[outcome] += 1

    counts["deleted"] = _purge_stale(store, vector_store, processed_ids)
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


def _resolve_discovered_state(record: FileRecord, force_rehash: bool) -> Optional[DiscoveredState]:
    path = Path(record.local_path)
    if not path.exists():
        return None
    stat = path.stat()
    current_mtime = int(stat.st_mtime * 1000)
    current_size = stat.st_size
    unchanged = (
        current_mtime == record.modified_time
        and current_size == record.file_size
        and record.content_hash is not None
    )

    content_hash = None
    if force_rehash or not unchanged:
        content_hash = compute_content_hash(path.read_bytes())
    return DiscoveredState(content_hash=content_hash, modified_time=current_mtime, file_size=current_size)


def _apply_action(
    record: FileRecord,
    discovered: DiscoveredState,
    store: MetadataStore,
    vector_store: VectorStore,
    embedder: Embedder,
    app_config: AppConfig,
) -> str:
    existing_for_decision = record if record.status == "indexed" else None
    action = decide_action(discovered, existing_for_decision)
    resolved_hash = discovered.content_hash or record.content_hash

    if action in (Action.NEW, Action.REPROCESS):
        return _embed_file(record, discovered, resolved_hash, store, vector_store, embedder, app_config)
    if action == Action.SKIP_BUT_TOUCH:
        store.upsert_file(_with_stat(record, discovered, resolved_hash))
        return "touched"
    return "skipped"


def _embed_file(
    record: FileRecord,
    discovered: DiscoveredState,
    resolved_hash: str,
    store: MetadataStore,
    vector_store: VectorStore,
    embedder: Embedder,
    app_config: AppConfig,
) -> str:
    is_new = record.status != "indexed"
    try:
        pages = extract_pages(Path(record.local_path).read_bytes())
        spans = chunk_pages(pages, embedder.tokenizer, app_config.chunk_window_tokens, app_config.chunk_overlap_tokens)
        chunks = [
            Chunk(
                file_id=record.id,
                chunk_index=i,
                text=span.text,
                page_start=span.page_start,
                page_end=span.page_end,
                char_start=span.char_start,
                char_end=span.char_end,
            )
            for i, span in enumerate(spans)
        ]
        embed_texts = [f"{record.display_name} {chunk.text}" for chunk in chunks]
        embeddings = embedder.embed_documents(embed_texts)
        vector_store.delete_by_file_id(record.id)
        vector_store.upsert_chunks(chunks, embeddings, resolved_hash)
    except Exception as exc:
        # Broad on purpose: extraction/chunking/embedding/vector-store failures all land here, and
        # the plan's contract is that one bad file must never abort the whole indexing run.
        logger.warning("Failed to index %s: %s", record.local_path, exc)
        store.upsert_file(_with_stat(record, discovered, resolved_hash, status="extraction_failed"))
        return "failed"

    store.upsert_file(
        _with_stat(record, discovered, resolved_hash, status="indexed", page_count=len(pages), touch_indexed_at=True)
    )
    return "new" if is_new else "reprocessed"


def _with_stat(
    record: FileRecord,
    discovered: DiscoveredState,
    resolved_hash: str,
    *,
    status: Optional[str] = None,
    page_count: Optional[int] = None,
    touch_indexed_at: bool = False,
) -> FileRecord:
    return FileRecord(
        id=record.id,
        source_type=record.source_type,
        local_path=record.local_path,
        drive_id=record.drive_id,
        display_name=record.display_name,
        content_hash=resolved_hash,
        file_size=discovered.file_size,
        modified_time=discovered.modified_time,
        page_count=page_count if page_count is not None else record.page_count,
        status=status or record.status,
        indexed_at=datetime.now(timezone.utc).isoformat() if touch_indexed_at else record.indexed_at,
        created_at=record.created_at,
    )


def _purge_stale(store: MetadataStore, vector_store: VectorStore, processed_ids: set[str]) -> int:
    # run_index only walks source_type="local" above, so only local records can be "stale" here —
    # Drive-sourced rows must never be purged by a run that never looked at Drive.
    stale = store.list_stale(processed_ids, source_type="local")
    for record in stale:
        vector_store.delete_by_file_id(record.id)
        store.delete_file(record.id)
    return len(stale)
