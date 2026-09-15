"""
test_chunker.py — Unit tests for chunker.py
Implemented Day 3.
"""
from app.services.chunker import chunk_pages
from app.config import CHUNK_SIZE, CHUNK_OVERLAP


def _long_page(page_number=1, extraction_method="native"):
    # Long enough text (well over CHUNK_SIZE) with word boundaries so the
    # splitter produces multiple chunks.
    text = " ".join(f"word{i}" for i in range(400))
    return [{"page_number": page_number, "text": text, "extraction_method": extraction_method}]


def test_chunk_sizes():
    """Each chunk must not exceed CHUNK_SIZE characters."""
    page_data = _long_page()
    chunks = chunk_pages(page_data, "doc-123", "test.pdf")
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk["chunk_text"]) <= CHUNK_SIZE


def test_chunk_overlap():
    """Adjacent chunks must share CHUNK_OVERLAP characters."""
    page_data = _long_page()
    chunks = chunk_pages(page_data, "doc-123", "test.pdf")
    assert len(chunks) > 1
    for prev, curr in zip(chunks, chunks[1:]):
        prev_text = prev["chunk_text"]
        curr_text = curr["chunk_text"]
        # RecursiveCharacterTextSplitter overlaps on a word boundary near
        # CHUNK_OVERLAP chars, so check the tail of one chunk reappears at
        # the head of the next rather than requiring an exact-length match.
        overlap_found = any(
            prev_text[-n:] == curr_text[:n]
            for n in range(min(CHUNK_OVERLAP, len(prev_text), len(curr_text)), 0, -1)
        )
        assert overlap_found, f"No overlap found between chunks:\n{prev_text!r}\n{curr_text!r}"


def _long_lines_page(line_length=126, n_lines=60, page_number=1):
    """
    A page shaped the way PyMuPDF actually returns one: newline-separated
    visual lines, each longer than CHUNK_OVERLAP.
    """
    filler = "the history of computing machinery and its many notable inventors"
    lines = []
    for i in range(n_lines):
        head = f"Section {i + 1}. Unique sentence {i} concerning "
        line = (head + filler * 3)[:line_length]
        lines.append(line)
    return [{"page_number": page_number, "text": "\n".join(lines),
             "extraction_method": "native"}]


def test_chunk_overlap_with_newline_separated_long_lines():
    """
    Overlap must survive on real PDF text, not just on one space-joined line.

    Regression guard for the Day 11 defect: the splitter carries whole split
    units back for the overlap, so when the unit was a *line* (the library
    default separators include a bare "\\n", and PyMuPDF emits one per visual
    line) any line longer than CHUNK_OVERLAP was popped whole and adjacent
    chunks shared nothing at all — 18 of 18 pairs at zero overlap on a
    126-char-per-line page.

    test_chunk_overlap above cannot catch this: its input is a single
    space-separated line, which is precisely the shape that always overlapped.
    """
    page_data = _long_lines_page()
    line_lengths = {len(l) for l in page_data[0]["text"].split("\n")}
    assert min(line_lengths) > CHUNK_OVERLAP, (
        "fixture must have lines longer than CHUNK_OVERLAP or it cannot "
        f"reproduce the defect (got {sorted(line_lengths)[:3]})"
    )

    chunks = chunk_pages(page_data, "doc-123", "dense.pdf")
    assert len(chunks) > 1

    for prev, curr in zip(chunks, chunks[1:]):
        prev_text, curr_text = prev["chunk_text"], curr["chunk_text"]
        overlap = max(
            (n for n in range(min(CHUNK_OVERLAP, len(prev_text), len(curr_text)), 0, -1)
             if prev_text[-n:] == curr_text[:n]),
            default=0,
        )
        assert overlap > 0, (
            "adjacent chunks share no text; the overlap was dropped:\n"
            f"...{prev_text[-90:]!r}\n{curr_text[:90]!r}..."
        )


def test_chunk_sizes_with_newline_separated_long_lines():
    """CHUNK_SIZE must still hold once the separators stop splitting on lines."""
    chunks = chunk_pages(_long_lines_page(), "doc-123", "dense.pdf")
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk["chunk_text"]) <= CHUNK_SIZE


def test_chunk_metadata_preserved():
    """Each chunk must carry document_id, filename, page_number, chunk_index, extraction_method."""
    page_data = _long_page(page_number=3, extraction_method="ocr")
    chunks = chunk_pages(page_data, "doc-abc", "scanned.pdf")
    assert len(chunks) > 0
    for i, chunk in enumerate(chunks):
        meta = chunk["metadata"]
        assert meta["document_id"] == "doc-abc"
        assert meta["filename"] == "scanned.pdf"
        assert meta["page_number"] == 3
        assert meta["chunk_index"] == i
        assert meta["extraction_method"] == "ocr"


def test_chunk_empty_text():
    """Empty page list should return empty chunk list."""
    result = chunk_pages([], "doc-123", "test.pdf")
    assert result == []
