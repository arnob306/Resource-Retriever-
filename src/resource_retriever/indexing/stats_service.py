"""Phase 5: aggregate stats — tracked file counts by source/status, and search-log performance."""

from collections import Counter
from dataclasses import dataclass
from typing import Optional

from resource_retriever.storage.metadata_store import MetadataStore


@dataclass(frozen=True)
class StatsSummary:
    total_files: int
    by_source_and_status: dict[tuple[str, str], int]
    total_searches: int
    average_search_latency_ms: Optional[float]


def compute_stats(store: MetadataStore) -> StatsSummary:
    records = store.list_all()
    by_source_and_status = Counter((record.source_type, record.status) for record in records)
    total_searches, average_latency_ms = store.search_stats()
    return StatsSummary(
        total_files=len(records),
        by_source_and_status=dict(by_source_and_status),
        total_searches=total_searches,
        average_search_latency_ms=average_latency_ms,
    )
