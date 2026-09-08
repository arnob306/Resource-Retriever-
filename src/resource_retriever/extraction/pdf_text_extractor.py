"""PyMuPDF-based per-page text extraction. Text-based PDFs only; no OCR fallback."""

from dataclasses import dataclass

import pymupdf as fitz


class ExtractionError(Exception):
    """Raised when a PDF cannot be opened, is encrypted, or has no extractable text."""


@dataclass(frozen=True)
class PageText:
    page_number: int  # 1-indexed
    text: str


def extract_pages(source: bytes) -> list[PageText]:
    """Extract text per page from PDF bytes. Never returns silently-empty results:
    encrypted or image-only (no extractable text) PDFs raise ExtractionError instead.
    """
    try:
        document = fitz.open(stream=bytes(source), filetype="pdf")
    except Exception as exc:
        raise ExtractionError(f"Failed to open PDF: {exc}") from exc

    try:
        if document.is_encrypted:
            raise ExtractionError("PDF is encrypted; cannot extract text")

        pages = [
            PageText(page_number=index + 1, text=document.load_page(index).get_text("text"))
            for index in range(document.page_count)
        ]

        if not any(page.text.strip() for page in pages):
            raise ExtractionError("PDF has no extractable text (likely scanned/image-only)")

        return pages
    finally:
        document.close()
