"""Splits a file's extracted pages into overlapping, page-tracked passages for embedding.

Tokenizes with the embedding model's own HF fast tokenizer (not tiktoken) so chunk windows
never exceed what the model will actually embed, and so char offsets come directly from the
tokenizer's `offset_mapping` rather than a lossy decode-then-measure reconstruction.
"""

from bisect import bisect_right
from dataclasses import dataclass

from resource_retriever.extraction.pdf_text_extractor import PageText

_PAGE_SEPARATOR = "\n\n"


class ChunkingError(Exception):
    """Raised when a document has no usable text to chunk (all pages blank/whitespace)."""


@dataclass(frozen=True)
class ChunkSpan:
    text: str
    page_start: int
    page_end: int
    char_start: int
    char_end: int


def chunk_pages(pages: list[PageText], tokenizer, window_tokens: int, overlap_tokens: int) -> list[ChunkSpan]:
    """Slide a `window_tokens`-token window (stepping by `window_tokens - overlap_tokens`) over the
    pages' concatenated text, returning one ChunkSpan per window with exact char offsets and the
    page range that offset falls within.
    """
    full_text, page_boundaries = _concatenate_pages(pages)
    if not full_text.strip():
        raise ChunkingError("Document has no extractable text to chunk")

    offsets = tokenizer(full_text, add_special_tokens=False, return_offsets_mapping=True)["offset_mapping"]
    non_empty_offsets = [offset for offset in offsets if offset[1] > offset[0]]
    if not non_empty_offsets:
        raise ChunkingError("Document tokenized to zero content tokens")

    step = window_tokens - overlap_tokens
    spans: list[ChunkSpan] = []
    win_start = 0
    while win_start < len(non_empty_offsets):
        win_end = min(win_start + window_tokens, len(non_empty_offsets))
        char_start = non_empty_offsets[win_start][0]
        char_end = non_empty_offsets[win_end - 1][1]
        page_start = _page_at(page_boundaries, char_start)
        page_end = _page_at(page_boundaries, char_end - 1)
        spans.append(
            ChunkSpan(
                text=full_text[char_start:char_end],
                page_start=page_start,
                page_end=page_end,
                char_start=char_start,
                char_end=char_end,
            )
        )
        if win_end == len(non_empty_offsets):
            break
        win_start += step

    return spans


def _concatenate_pages(pages: list[PageText]) -> tuple[str, list[tuple[int, int]]]:
    """Returns (full_text, boundaries) where boundaries is a sorted list of
    (start_char_offset, page_number) — one entry per page, for bisecting a char offset to a page.
    """
    parts: list[str] = []
    boundaries: list[tuple[int, int]] = []
    offset = 0
    for page in pages:
        boundaries.append((offset, page.page_number))
        parts.append(page.text)
        offset += len(page.text) + len(_PAGE_SEPARATOR)
        parts.append(_PAGE_SEPARATOR)
    return "".join(parts), boundaries


def _page_at(boundaries: list[tuple[int, int]], char_offset: int) -> int:
    starts = [start for start, _ in boundaries]
    index = bisect_right(starts, char_offset) - 1
    index = max(index, 0)
    return boundaries[index][1]
