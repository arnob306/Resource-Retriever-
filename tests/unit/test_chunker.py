import pytest

from resource_retriever.chunking.chunker import ChunkingError, chunk_pages
from resource_retriever.extraction.pdf_text_extractor import PageText


class _WhitespaceTokenizer:
    """Deterministic fake HF-style tokenizer: one token per whitespace-delimited word.
    Avoids downloading a real model in a fast unit test — the real tokenizer is exercised
    by the integration test instead.
    """

    def __call__(self, text, add_special_tokens=False, return_offsets_mapping=True):
        offsets = []
        i, n = 0, len(text)
        while i < n:
            while i < n and text[i].isspace():
                i += 1
            if i >= n:
                break
            start = i
            while i < n and not text[i].isspace():
                i += 1
            offsets.append((start, i))
        return {"offset_mapping": offsets}


@pytest.fixture
def tokenizer():
    return _WhitespaceTokenizer()


def test_chunk_never_exceeds_configured_window_token_count(tokenizer):
    # Arrange
    pages = [PageText(page_number=1, text=" ".join(f"word{i}" for i in range(50)))]

    # Act
    spans = chunk_pages(pages, tokenizer, window_tokens=10, overlap_tokens=2)

    # Assert
    for span in spans:
        token_count = len(tokenizer(span.text)["offset_mapping"])
        assert token_count <= 10


def test_consecutive_chunks_overlap_by_configured_amount(tokenizer):
    # Arrange
    pages = [PageText(page_number=1, text=" ".join(f"word{i}" for i in range(20)))]

    # Act
    spans = chunk_pages(pages, tokenizer, window_tokens=10, overlap_tokens=3)

    # Assert
    first_words = spans[0].text.split()
    second_words = spans[1].text.split()
    assert first_words[-3:] == second_words[:3]


def test_chunk_spanning_two_pages_gets_different_page_start_and_end(tokenizer):
    # Arrange — page 1 has few words, page 2 has many, so a window will straddle the boundary
    pages = [
        PageText(page_number=1, text="alpha beta gamma"),
        PageText(page_number=2, text=" ".join(f"word{i}" for i in range(20))),
    ]

    # Act
    spans = chunk_pages(pages, tokenizer, window_tokens=8, overlap_tokens=2)

    # Assert
    crossing = [s for s in spans if s.page_start != s.page_end]
    assert crossing, "expected at least one chunk to span both pages"
    assert crossing[0].page_start == 1
    assert crossing[0].page_end == 2


def test_last_chunk_is_not_empty(tokenizer):
    # Arrange
    pages = [PageText(page_number=1, text=" ".join(f"word{i}" for i in range(23)))]

    # Act
    spans = chunk_pages(pages, tokenizer, window_tokens=10, overlap_tokens=2)

    # Assert
    assert spans[-1].text.strip() != ""
    assert spans[-1].char_end > spans[-1].char_start


def test_offset_mapping_char_ranges_are_exact(tokenizer):
    # Arrange
    text = "The quadratic formula solves ax^2 + bx + c = 0 exactly."
    pages = [PageText(page_number=1, text=text)]

    # Act
    spans = chunk_pages(pages, tokenizer, window_tokens=100, overlap_tokens=0)

    # Assert — single chunk should reproduce the source text exactly at its offsets
    assert len(spans) == 1
    assert text[spans[0].char_start : spans[0].char_end] == spans[0].text


def test_raises_chunking_error_on_all_whitespace_document(tokenizer):
    # Arrange
    pages = [PageText(page_number=1, text="   \n\n  ")]

    # Act / Assert
    with pytest.raises(ChunkingError):
        chunk_pages(pages, tokenizer, window_tokens=10, overlap_tokens=2)


def test_raises_chunking_error_on_zero_pages(tokenizer):
    # Act / Assert
    with pytest.raises(ChunkingError):
        chunk_pages([], tokenizer, window_tokens=10, overlap_tokens=2)


def test_raises_chunking_error_when_overlap_equals_window(tokenizer):
    # Arrange — step = window - overlap would be 0, so the sliding window could never advance
    pages = [PageText(page_number=1, text=" ".join(f"word{i}" for i in range(20)))]

    # Act / Assert
    with pytest.raises(ChunkingError):
        chunk_pages(pages, tokenizer, window_tokens=10, overlap_tokens=10)


def test_raises_chunking_error_when_overlap_exceeds_window(tokenizer):
    # Arrange — step = window - overlap would be negative, so the window would move backward
    pages = [PageText(page_number=1, text=" ".join(f"word{i}" for i in range(20)))]

    # Act / Assert
    with pytest.raises(ChunkingError):
        chunk_pages(pages, tokenizer, window_tokens=10, overlap_tokens=15)
