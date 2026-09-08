"""The Chunk model: one embeddable passage of a file's extracted text."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    file_id: str
    chunk_index: int
    text: str
    page_start: int  # 1-indexed
    page_end: int  # 1-indexed, >= page_start
    char_start: int  # offset into the file's concatenated page text
    char_end: int
