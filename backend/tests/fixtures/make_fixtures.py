"""
make_fixtures.py — Generate the reusable PDF test corpus for Day 9 (Phase 6).

Why this lives in `backend/tests/fixtures/`:
  * pytest reaches the PDFs by a path relative to `tests/`, so they are reusable
    by every future session;
  * it is entirely outside `frontend/`, so Vite can never serve or bundle them —
    Day 7's `public/__day7_fixtures/` mistake is structurally impossible here;
  * generating them from a script (rather than committing binaries) keeps the
    tree small and makes the corpus reproducible on a fresh clone.

Run:  python tests/fixtures/make_fixtures.py            (from backend/)
      python tests/fixtures/make_fixtures.py --verify   (report only, no writes)

No new dependencies — PyMuPDF alone renders both the native text and the
page images used for the scanned fixtures.
"""
from __future__ import annotations

import sys
from pathlib import Path

import fitz  # PyMuPDF

FIXTURE_DIR = Path(__file__).parent

# The OCR fallback fires when a page's native text is under this many
# characters (pdf_processor.MIN_CHARS_FOR_NATIVE_TEXT), so an "image-only"
# fixture page must contain no text objects at all.
OCR_RENDER_DPI = 150   # enough for Tesseract on 20pt+ print, ~40 KB/page


# ── Page builders ─────────────────────────────────────────────────────────────

def _write_text_page(page, lines) -> None:
    """Draw (text, size) pairs down a page as real, selectable PDF text."""
    y = 90
    for text, size in lines:
        page.insert_text((70, y), text, fontsize=size, fontname="helv")
        y += size * 1.9


def _render_lines_to_png(lines, dpi: int = OCR_RENDER_DPI) -> bytes:
    """
    Rasterise a text page to PNG bytes. Used to build image-only pages: the
    text exists only as pixels, exactly like a scanned document.
    """
    scratch = fitz.open()
    page = scratch.new_page()
    _write_text_page(page, lines)
    # Greyscale: printed-text OCR gains nothing from colour, and it cuts the
    # rasterised page to a third of the bytes.
    png = page.get_pixmap(dpi=dpi, colorspace=fitz.csGRAY).tobytes("png")
    scratch.close()
    return png


def _new_doc():
    return fitz.open()


def _save(doc, path: Path) -> None:
    """Save compressed — an uncompressed scanned page is ~6 MB, deflated ~50 KB."""
    doc.save(path, garbage=4, deflate=True, deflate_images=True)
    doc.close()


def _add_native_page(doc, lines):
    _write_text_page(doc.new_page(), lines)


def _add_scanned_page(doc, lines):
    """Add a page whose only content is a rasterised image of `lines`."""
    page = doc.new_page()
    page.insert_image(page.rect, stream=_render_lines_to_png(lines))


# ── Fixture content ───────────────────────────────────────────────────────────
#
# Content for the three canonical documents is chosen so the retrieval
# assertions in test_retriever.py stay true: each topic must be the clear
# winner for its own query and must not compete with the others.

NATIVE_SINGLE = [
    ("Quarterly Budget Summary", 20),
    ("The finance team reviewed operating expenses for the second quarter.", 12),
    ("Travel costs decreased by twelve percent against the previous quarter.", 12),
    ("Procurement renegotiated three vendor contracts during the period.", 12),
    ("A capital expenditure for new office furniture was approved.", 12),
]

# NATIVE_MULTI and SCANNED_ONLY reproduce the text already stored in the
# canonical ChromaDB collection (read back from the live store on Day 9), so a
# regenerated fixture and the persisted Day 3 corpus stay semantically identical.
NATIVE_MULTI = [
    [   # page 1 — AI history
        ("Page one talks about the history of artificial intelligence", 13),
        ("and machine learning research since the 1950s.", 13),
    ],
    [   # page 2 — ChromaDB
        ("Page two discusses ChromaDB, a vector database used to store", 13),
        ("embeddings for retrieval augmented generation.", 13),
    ],
    [   # page 3 — Tesseract
        ("Page three explains that Tesseract OCR is a free and open source", 13),
        ("optical character recognition engine.", 13),
    ],
]

SCANNED_ONLY = [
    ("SCANNED DOCUMENT TEST PAGE", 24),
    ("This page has no embedded text layer.", 16),
    ("It exists only as a rendered image.", 16),
    ("The RAG chatbot must recover this text", 16),
    ("using local Tesseract OCR before it can", 16),
    ("be chunked, embedded, and made searchable.", 16),
    ("Keyword for retrieval testing: PINEAPPLE OCR SUCCESS", 16),
]

# One identical page repeated — every line qualifies as a "running header"
# under text_cleaner._strip_repeated_headers_footers(), which is the exact
# input that emptied a document on Day 7.
REPEATED_PAGE = [
    ("CERTIFICATE OF COMPLETION", 22),
    ("This is to certify that the holder has completed", 13),
    ("the mandatory annual compliance training module.", 13),
    ("Issued by the Training Department.", 13),
]

# A realistic form: a shared header and footer around a body that differs per
# page. Header/footer stripping SHOULD fire here and the body must survive —
# this is the case that proves the Day 9 fix did not turn stripping into a no-op.
def _certificate_page(n: int):
    return [
        ("ACME CORPORATION - INTERNAL", 16),
        ("Certificate of Completion", 20),
        (f"Recipient number {n} completed module {n} on the training portal.", 12),
        (f"Assessment score recorded for candidate {n} was {80 + n} percent.", 12),
        ("Confidential - Internal Use Only", 10),
    ]

LARGE_TOPICS = [
    "network routing protocols", "relational database indexing",
    "continuous integration pipelines", "container orchestration",
    "public key cryptography", "distributed consensus algorithms",
    "compiler optimisation passes", "garbage collection strategies",
    "operating system schedulers", "cache coherence protocols",
    "message queue delivery guarantees", "load balancing algorithms",
    "observability and structured logging", "infrastructure as code",
    "blue green deployment", "chaos engineering experiments",
]


# ── Builders ──────────────────────────────────────────────────────────────────

def build_native_single(path: Path):
    doc = _new_doc()
    _add_native_page(doc, NATIVE_SINGLE)
    _save(doc, path)


def build_native_multi(path: Path):
    doc = _new_doc()
    for page_lines in NATIVE_MULTI:
        _add_native_page(doc, page_lines)
    _save(doc, path)


def build_scanned_image_only(path: Path):
    doc = _new_doc()
    _add_scanned_page(doc, SCANNED_ONLY)
    _save(doc, path)


def build_large_native(path: Path):
    """16 pages (spec §20 requires 15+), each on a distinct topic."""
    doc = _new_doc()
    for i, topic in enumerate(LARGE_TOPICS, start=1):
        _add_native_page(doc, [
            (f"Chapter {i}: {topic.title()}", 18),
            (f"This chapter introduces {topic} and explains why the technique", 12),
            (f"matters in production systems. Section {i} covers the trade-offs", 12),
            (f"engineers weigh when they adopt {topic} at scale, together with", 12),
            (f"the failure modes that appear on page {i} of this handbook.", 12),
        ])
    _save(doc, path)


def build_mixed_native_scanned(path: Path):
    """4 pages: 1 and 4 native, 2 and 3 image-only (spec §20 'mixed')."""
    doc = _new_doc()
    _add_native_page(doc, [
        ("Mixed Extraction Test - Native Page One", 18),
        ("This first page carries a real embedded text layer and is read", 12),
        ("directly by PyMuPDF without any optical character recognition.", 12),
        ("Its marker phrase is NATIVE ALPHA MARKER.", 12),
    ])
    _add_scanned_page(doc, [
        ("MIXED TEST - SCANNED PAGE TWO", 24),
        ("This page is an image with no text layer.", 18),
        ("Its marker phrase is SCANNED BRAVO MARKER.", 20),
    ])
    _add_scanned_page(doc, [
        ("MIXED TEST - SCANNED PAGE THREE", 24),
        ("This page is also an image only page.", 18),
        ("Its marker phrase is SCANNED CHARLIE MARKER.", 20),
    ])
    _add_native_page(doc, [
        ("Mixed Extraction Test - Native Page Four", 18),
        ("The final page returns to embedded text so a single document", 12),
        ("exercises both extraction paths at once.", 12),
        ("Its marker phrase is NATIVE DELTA MARKER.", 12),
    ])
    _save(doc, path)


def build_repeated_page(path: Path):
    """5 byte-identical pages — the text_cleaner regression fixture."""
    doc = _new_doc()
    for _ in range(5):
        _add_native_page(doc, REPEATED_PAGE)
    _save(doc, path)


def build_repeated_header_footer(path: Path):
    """4 pages sharing a header/footer but with unique bodies."""
    doc = _new_doc()
    for n in range(1, 5):
        _add_native_page(doc, _certificate_page(n))
    _save(doc, path)


def build_no_text(path: Path):
    """2 genuinely blank pages — no text layer and no image, so neither
    native extraction nor OCR can recover anything (spec §32 'failed')."""
    doc = _new_doc()
    doc.new_page()
    doc.new_page()
    _save(doc, path)


FIXTURES = [
    ("native_single.pdf", build_native_single),
    ("native_multi.pdf", build_native_multi),
    ("scanned_image_only.pdf", build_scanned_image_only),
    ("large_native.pdf", build_large_native),
    ("mixed_native_scanned.pdf", build_mixed_native_scanned),
    ("repeated_page.pdf", build_repeated_page),
    ("repeated_header_footer.pdf", build_repeated_header_footer),
    ("no_text.pdf", build_no_text),
]


# ── Reporting ─────────────────────────────────────────────────────────────────

def describe(path: Path) -> str:
    """Report pages, size, and which pages have no native text (→ OCR path)."""
    doc = fitz.open(path)
    textless = [i for i, page in enumerate(doc, start=1)
                if len((page.get_text() or "").strip()) < 10]
    pages = len(doc)
    doc.close()
    kb = path.stat().st_size / 1024
    note = f"pages needing OCR: {textless}" if textless else "all pages native"
    return f"{path.name:<30} {pages:>3} page(s)  {kb:>8.1f} KB   {note}"


def main() -> int:
    verify_only = "--verify" in sys.argv
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)

    for name, builder in FIXTURES:
        path = FIXTURE_DIR / name
        if not verify_only:
            builder(path)
        if not path.exists():
            print(f"MISSING: {name}")
            return 1
        print(describe(path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
