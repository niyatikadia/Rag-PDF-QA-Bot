"""
chunker.py — Split cleaned page text into overlapping chunks.
Uses LangChain's RecursiveCharacterTextSplitter.

Implemented: Day 3
"""
import logging
from typing import List, Dict
from app.config import CHUNK_SIZE, CHUNK_OVERLAP

logger = logging.getLogger(__name__)


def chunk_pages(page_data: List[Dict], document_id: str, filename: str) -> List[Dict]:
    """
    Split each page's text into overlapping chunks.

    Input:
      page_data — [{"page_number": int, "text": str, "extraction_method": str}]
      document_id — UUID of the parent document
      filename    — original filename (for metadata)

    Output:
      [{"chunk_text": str, "metadata": {"document_id", "filename",
        "page_number", "chunk_index", "extraction_method"}}]
    """
    if not page_data:
        return []

    from langchain_text_splitters import RecursiveCharacterTextSplitter

    # Separators deliberately omit a bare "\n" (found Day 11).
    #
    # RecursiveCharacterTextSplitter merges whole *split units* into a chunk and
    # then carries units back over for the overlap, popping from the front while
    # the carried length still exceeds chunk_overlap. So a unit that is by itself
    # longer than CHUNK_OVERLAP can never be carried: it is popped whole and the
    # next chunk starts with nothing behind it.
    #
    # With the library default separators (["\n\n", "\n", " ", ""]) the unit for
    # PDF text is a *line*, because PyMuPDF emits one "\n" per visual line. Pages
    # set in a dense or wide measure run past 100 characters per line, and every
    # adjacent chunk pair on such a page came out with exactly zero overlap —
    # measured 18/18 pairs on a 126-char-per-line document, against the 100 that
    # F4/§5.1 specify.
    #
    # Dropping "\n" makes the merge unit a *word*, which is always far shorter
    # than CHUNK_OVERLAP, so the overlap survives (measured 92-99 chars on the
    # same document). Paragraph breaks are still honoured first, and line breaks
    # are preserved inside the chunk text — only the choice of split point
    # changes, never the characters. Pages whose lines are already under 100
    # chars chunk byte-identically to before, which is what keeps the measured
    # similarity thresholds in test_retriever.py valid.
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
        separators=["\n\n", " ", ""],
    )

    chunks = []
    for page in page_data:
        splits = splitter.split_text(page["text"])
        for i, split in enumerate(splits):
            chunks.append({
                "chunk_text": split,
                "metadata": {
                    "document_id": document_id,
                    "filename": filename,
                    "page_number": page["page_number"],
                    "chunk_index": i,
                    "extraction_method": page.get("extraction_method", "native"),
                }
            })
    return chunks
