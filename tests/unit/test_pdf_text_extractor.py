import pymupdf as fitz
import pytest

from resource_retriever.extraction.pdf_text_extractor import ExtractionError, extract_pages


def test_extracts_correct_page_count_and_nonempty_text(sample_pdf_bytes):
    pages = extract_pages(sample_pdf_bytes)

    assert len(pages) >= 1
    assert pages[0].page_number == 1
    assert pages[0].text.strip() != ""


def test_page_numbers_are_sequential_and_one_indexed(sample_pdfs_dir):
    multi_page_pdf = sample_pdfs_dir / "year9_quadratics_worksheet.pdf"

    pages = extract_pages(multi_page_pdf.read_bytes())

    assert [page.page_number for page in pages] == list(range(1, len(pages) + 1))


def test_raises_on_encrypted_pdf(tmp_path):
    document = fitz.open()
    document.new_page()
    encrypted_path = tmp_path / "encrypted.pdf"
    document.save(
        str(encrypted_path),
        encryption=fitz.PDF_ENCRYPT_AES_256,
        owner_pw="owner-secret",
        user_pw="user-secret",
    )
    document.close()

    with pytest.raises(ExtractionError):
        extract_pages(encrypted_path.read_bytes())


def test_raises_on_pdf_with_no_extractable_text(tmp_path):
    document = fitz.open()
    document.new_page()  # blank page, no text inserted
    blank_path = tmp_path / "blank.pdf"
    document.save(str(blank_path))
    document.close()

    with pytest.raises(ExtractionError):
        extract_pages(blank_path.read_bytes())


def test_raises_on_non_pdf_bytes():
    with pytest.raises(ExtractionError):
        extract_pages(b"this is not a pdf")


def test_page_parsing_failure_is_wrapped_as_extraction_error(sample_pdf_bytes, monkeypatch):
    """A raw exception mid-parse (e.g. a mupdf internal error on a specific page) must not
    escape as a bare exception — it should surface as ExtractionError so callers that only
    catch ExtractionError/OSError (like ingest_service) never crash on one bad page.
    """

    def _raise(self, index):
        raise RuntimeError("simulated mupdf page-parse failure")

    monkeypatch.setattr(fitz.Document, "load_page", _raise)

    with pytest.raises(ExtractionError) as exc_info:
        extract_pages(sample_pdf_bytes)

    assert isinstance(exc_info.value.__cause__, RuntimeError)
