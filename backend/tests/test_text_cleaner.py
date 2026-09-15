"""
test_text_cleaner.py — Unit tests for text_cleaner.py
Implement fully in Day 2 alongside text_cleaner.py.
"""
import pytest
from app.services.text_cleaner import clean_text, clean_pages


def test_clean_text_removes_extra_whitespace():
    raw = "Hello   world\n\n\n\nFoo"
    result = clean_text(raw)
    assert "   " not in result
    assert result.count("\n\n\n") == 0


def test_clean_text_handles_empty_string():
    assert clean_text("") == ""


def test_clean_text_strips_control_chars():
    raw = "Hello\x00World\x07"
    result = clean_text(raw)
    assert "\x00" not in result
    assert "\x07" not in result


def test_clean_pages_filters_empty_pages():
    pages = [
        {"page_number": 1, "text": "   \n  ", "extraction_method": "native"},
        {"page_number": 2, "text": "Useful content here.", "extraction_method": "native"},
    ]
    result = clean_pages(pages)
    assert len(result) == 1
    assert result[0]["page_number"] == 2


def test_clean_pages_preserves_extraction_method():
    pages = [
        {"page_number": 1, "text": "OCR text.", "extraction_method": "ocr"},
    ]
    result = clean_pages(pages)
    assert result[0]["extraction_method"] == "ocr"


# ── Header/footer stripping (Day 9 regression — spec §5.1, §32 items 5 & 12) ──
#
# Day 7 built a 5-page PDF by repeating one scanned page. All 5 pages OCR'd
# successfully, then _strip_repeated_headers_footers() removed every line —
# because with identical pages *every* line looks like a running header — and
# the document was marked "failed: no text could be extracted". Reproduced on
# Day 9 at n = 2, 3 and 5: two identical pages are enough to empty a document.
#
# The guard: stripping headers must never empty a page. If removing the
# "headers" removes everything, they were the body.

REPEATED_BODY = (
    "CERTIFICATE OF COMPLETION\n"
    "This is to certify that the holder has completed\n"
    "the mandatory annual compliance training module.\n"
    "Issued by the Training Department."
)


@pytest.mark.parametrize("page_count", [2, 3, 5])
def test_identical_pages_survive_header_stripping(page_count):
    """A document whose pages are identical must not be emptied."""
    pages = [
        {"page_number": n, "text": REPEATED_BODY, "extraction_method": "ocr"}
        for n in range(1, page_count + 1)
    ]
    result = clean_pages(pages)

    assert len(result) == page_count, (
        f"{page_count} identical pages were reduced to {len(result)} — "
        "header stripping emptied the document"
    )
    for page in result:
        assert "CERTIFICATE OF COMPLETION" in page["text"]
        assert "Training Department" in page["text"]


def test_repeated_header_and_footer_are_still_stripped():
    """
    The guard must not turn stripping into a no-op: a real running header and
    footer around unique per-page bodies must still be removed.
    """
    pages = [
        {
            "page_number": n,
            "text": (
                "ACME CORPORATION - INTERNAL\n"
                f"Recipient number {n} completed module {n}.\n"
                f"Assessment score for candidate {n} was {80 + n} percent.\n"
                "Confidential - Internal Use Only"
            ),
            "extraction_method": "native",
        }
        for n in range(1, 5)
    ]
    result = clean_pages(pages)

    assert len(result) == 4
    for page in result:
        n = page["page_number"]
        assert "ACME CORPORATION" not in page["text"]          # header stripped
        assert "Confidential" not in page["text"]              # footer stripped
        assert f"Recipient number {n}" in page["text"]         # body survives
        assert f"candidate {n}" in page["text"]


def test_page_keeps_only_its_unique_lines_when_some_survive():
    """
    A page that shares a header with others but has unique content of its own
    keeps exactly the unique part — the guard only engages when nothing is left.
    """
    pages = [
        {"page_number": 1, "text": "SHARED HEADER\nUnique line for page one.",
         "extraction_method": "native"},
        {"page_number": 2, "text": "SHARED HEADER\nUnique line for page two.",
         "extraction_method": "native"},
    ]
    result = clean_pages(pages)

    assert [p["text"] for p in result] == [
        "Unique line for page one.",
        "Unique line for page two.",
    ]
