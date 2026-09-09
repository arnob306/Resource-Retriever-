"""The SearchResult model: one ranked, file-resolved hit returned by `find`."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SearchResult:
    file_path: str
    snippet: str
    page_number: int
    score: float
    open_command: str
