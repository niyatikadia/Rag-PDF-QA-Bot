"""
text_cleaner.py — Clean and normalise raw text extracted from PDFs.
Applies equally to natively-extracted text and OCR output.

Implemented: Day 2
"""
import re
import unicodedata
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


def clean_text(raw: str) -> str:
    """
    Clean a single block of raw text.
    - Normalise unicode to NFKC
    - Remove null bytes and control characters (keep newlines/tabs)
    - Collapse excessive whitespace / blank lines
    - Drop immediate duplicate consecutive lines (common OCR/extraction artifact)
    - Strip leading / trailing whitespace
    """
    text = unicodedata.normalize("NFKC", raw)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)   # control chars
    text = re.sub(r"\n{3,}", "\n\n", text)                            # max 2 blank lines
    text = re.sub(r"[ \t]{2,}", " ", text)                            # collapse spaces/tabs

    deduped_lines: List[str] = []
    for line in text.split("\n"):
        if deduped_lines and line.strip() and line.strip() == deduped_lines[-1].strip():
            continue
        deduped_lines.append(line)
    text = "\n".join(deduped_lines)

    return text.strip()


def _strip_repeated_headers_footers(pages: List[Dict]) -> List[Dict]:
    """
    Remove short lines (e.g. running headers/footers, page numbers) that
    recur across a majority of pages. Only meaningful with 2+ non-empty pages.

    Stripping never empties a page. A document built from a repeated template —
    a form, a certificate, the same scanned page twice — makes *every* line look
    like a running header, and without this guard the whole document was reduced
    to nothing and then reported as "no text could be extracted" (found Day 7,
    reproduced Day 9 at 2, 3 and 5 identical pages). If removing the headers
    removes everything, they were the body, so that page keeps its original text.
    """
    non_empty = [p for p in pages if p["text"]]
    if len(non_empty) < 2:
        return pages

    line_counts: Dict[str, int] = {}
    for page in non_empty:
        lines_in_page = {line.strip() for line in page["text"].split("\n") if line.strip()}
        for line in lines_in_page:
            if len(line) <= 80:
                line_counts[line] = line_counts.get(line, 0) + 1

    threshold = max(2, len(non_empty) // 2 + 1)
    repeated = {line for line, count in line_counts.items() if count >= threshold}
    if not repeated:
        return pages

    for page in non_empty:
        kept_lines = [line for line in page["text"].split("\n") if line.strip() not in repeated]
        stripped = clean_text("\n".join(kept_lines))
        if not stripped:
            logger.info(
                "Page %d is entirely repeated lines — keeping its original text "
                "rather than emptying the page.", page["page_number"]
            )
            continue
        page["text"] = stripped
    return pages


def clean_pages(page_data: List[Dict]) -> List[Dict]:
    """
    Clean each page's text, then strip recurring header/footer lines across
    the document as a whole.
    Input:  [{"page_number": int, "text": str, "extraction_method": str}, ...]
    Output: same structure with text replaced by cleaned version.
    Pages whose cleaned text is empty are filtered out.
    """
    pages = [{**page, "text": clean_text(page["text"])} for page in page_data]
    pages = _strip_repeated_headers_footers(pages)

    cleaned = []
    for page in pages:
        if page["text"]:
            cleaned.append(page)
        else:
            logger.debug("Page %d produced empty text after cleaning — skipped",
                         page["page_number"])
    return cleaned
