"""
Day 2 / Stage 11 — does an incoherent-but-type-valid config fail clearly at
startup, or "fail mysteriously later"?

Cases probed, each in this process with env already set by the caller:
  CHUNK_OVERLAP >= CHUNK_SIZE     -> splitter construction
  TOP_K_RESULTS = 0 / negative    -> retrieval
  MAX_FILE_SIZE_MB = 0            -> upload validation
  OCR_DPI = 0                     -> page rendering

Run via config_range_probe.ps1 so each case gets a clean interpreter.
"""
import os
import sys
import traceback

case = sys.argv[1]
print(f"--- case: {case} ---")
print("    env:", {k: v for k, v in os.environ.items()
                   if k in ("CHUNK_SIZE", "CHUNK_OVERLAP", "TOP_K_RESULTS",
                            "MAX_FILE_SIZE_MB", "OCR_DPI")})

import app.config as cfg
print(f"    config.py imported OK "
      f"(CHUNK_SIZE={cfg.CHUNK_SIZE} CHUNK_OVERLAP={cfg.CHUNK_OVERLAP} "
      f"TOP_K_RESULTS={cfg.TOP_K_RESULTS} MAX_FILE_SIZE_MB={cfg.MAX_FILE_SIZE_MB} "
      f"OCR_DPI={cfg.OCR_DPI})")

try:
    if case == "overlap":
        # This is the path a real upload takes, step 3 of ingestion.
        from app.services.chunker import chunk_pages
        pages = [{"page_number": 1, "text": "word " * 400,
                  "extraction_method": "native"}]
        chunks = chunk_pages(pages, "probe-doc", "probe.pdf")
        print(f"    RESULT: chunk_pages() returned {len(chunks)} chunk(s) — no error")
    elif case == "topk":
        from app.services.vector_store import query_chunks
        res = query_chunks([0.0] * 384, top_k=cfg.TOP_K_RESULTS)
        print(f"    RESULT: query_chunks() returned "
              f"{len(res['documents'][0])} hit(s) — no error")
    elif case == "maxsize":
        print(f"    RESULT: MAX_FILE_SIZE_BYTES={cfg.MAX_FILE_SIZE_BYTES} — "
              f"any non-empty upload now exceeds it")
    elif case == "dpi":
        import fitz
        from app.services.ocr_processor import ocr_page
        doc = fitz.open("tests/fixtures/scanned_image_only.pdf")
        txt = ocr_page(doc[0])
        doc.close()
        print(f"    RESULT: ocr_page() returned "
              f"{'None' if txt is None else str(len(txt)) + ' chars'} — no error")
except Exception:
    print("    RESULT: raised at USE time, not at startup:")
    for line in traceback.format_exc().strip().splitlines()[-6:]:
        print("      |", line)
