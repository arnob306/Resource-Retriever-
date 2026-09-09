"""Phase 3 search: embed a query, rank vector matches, and join back to file metadata for display.

Chroma metadata deliberately never stores `local_path`/`display_name` (see the plan's Vector
Store section), so every hit is joined back to `MetadataStore` by `file_id` here rather than
trusting anything path-shaped out of the vector store directly — that's what keeps a file rename
from requiring a vector-metadata rewrite.
"""

import logging
import platform
import sqlite3
import time
from dataclasses import dataclass

from resource_retriever.embedding.embedder import Embedder
from resource_retriever.models.search_result import SearchResult
from resource_retriever.storage.metadata_store import MetadataStore
from resource_retriever.storage.vector_store import VectorMatch, VectorStore

logger = logging.getLogger(__name__)

_SNIPPET_MAX_CHARS = 220
# Over-fetch candidates before content-hash dedup so top_k results still survive collapsing
# duplicate copies of the same file (e.g. the same worksheet in Drive, local, and Downloads).
_CANDIDATE_MULTIPLIER = 4
# If the initial over-fetch still doesn't yield top_k usable results (heavy duplication, or many
# excluded/stale chunks in the candidate window), widen the window geometrically up to this cap
# rather than silently returning a short result set.
_MAX_CANDIDATE_MULTIPLIER = 64


@dataclass(frozen=True)
class SearchOutcome:
    results: list[SearchResult]
    latency_ms: int


def find(query: str, store: MetadataStore, vector_store: VectorStore, embedder: Embedder, top_k: int = 5) -> SearchOutcome:
    """Embed `query`, retrieve ranked chunk matches, dedupe by content hash, and resolve file paths."""
    if top_k <= 0:
        raise ValueError(f"top_k must be a positive integer, got {top_k}")

    start = time.perf_counter()
    query_embedding = embedder.embed_query(query)
    results = _search_with_expanding_window(query_embedding, store, vector_store, top_k)
    latency_ms = int((time.perf_counter() - start) * 1000)

    try:
        store.record_search(query=query, latency_ms=latency_ms, result_count=len(results))
    except sqlite3.Error:
        logger.warning("Failed to record search_log entry", exc_info=True)
    return SearchOutcome(results=results, latency_ms=latency_ms)


def _search_with_expanding_window(
    query_embedding: list[float], store: MetadataStore, vector_store: VectorStore, top_k: int
) -> list[SearchResult]:
    multiplier = _CANDIDATE_MULTIPLIER
    while True:
        candidate_count = top_k * multiplier
        matches = vector_store.query(query_embedding, candidate_count)
        results = _dedupe_and_resolve(matches, store, top_k)
        exhausted = len(matches) < candidate_count  # the vector store had nothing more to give
        if len(results) >= top_k or exhausted or multiplier >= _MAX_CANDIDATE_MULTIPLIER:
            return results
        multiplier *= 4


def _dedupe_and_resolve(matches: list[VectorMatch], store: MetadataStore, top_k: int) -> list[SearchResult]:
    seen_hashes: set[str] = set()
    results: list[SearchResult] = []
    for match in matches:
        if match.content_hash in seen_hashes:
            continue
        record = store.get_by_id(match.file_id)
        if record is None or record.local_path is None or record.status != "indexed":
            # None/no local_path: removed from the index since embedding, or drive-only (Phase 4).
            # status != "indexed": excluded since embedding (stale vectors a reindex hasn't purged
            # yet) or extraction_failed/discovered leftovers — never surface either as a result.
            continue
        seen_hashes.add(match.content_hash)
        results.append(
            SearchResult(
                file_path=record.local_path,
                snippet=_make_snippet(match.text),
                page_number=match.page_start,
                score=match.score,
                open_command=_open_command(record.local_path),
            )
        )
        if len(results) >= top_k:
            break
    return results


def _make_snippet(text: str) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= _SNIPPET_MAX_CHARS:
        return collapsed
    return collapsed[:_SNIPPET_MAX_CHARS].rsplit(" ", 1)[0] + "..."


def _open_command(local_path: str) -> str:
    system = platform.system()
    if system == "Windows":
        return f'start "" "{local_path}"'
    if system == "Darwin":
        return f'open "{local_path}"'
    return f'xdg-open "{local_path}"'
