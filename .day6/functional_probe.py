"""
functional_probe.py — post-coding Day 6, stage 1 (functional testing).

Walks the specification's own completeness checklist (§32) one line at a time
against a RUNNING backend, from the outside, over HTTP — the "different hat"
stage 1 of 01_After_Coding_Is_Complete.pdf asks for: driven from the
requirements document rather than from memory of the code.

This is deliberately not pytest. The suite mocks the Ollama call so it stays
fast and deterministic; this probe makes real calls to the real model against
the real vector store, which is the only way to check the answers, the
citations and the "not found" behaviour that F9, F10 and F11 actually specify.

Run with the backend up:

    cd <repo>
    backend\\.venv\\Scripts\\python.exe .day6\\functional_probe.py

Every path is derived from this file's location. Exit code 0 = all checks
passed. Answers take 30-75 s each on the reference hardware, so allow ~6 min.
"""
import io
import json
import sys
import time
from pathlib import Path

import requests

BASE = "http://127.0.0.1:8000"
REPO = Path(__file__).resolve().parent.parent
FIXTURES = REPO / "backend" / "tests" / "fixtures"

results = []
created = []


def record(req: str, description: str, ok: bool, detail: str = "") -> None:
    results.append((req, description, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {req:<6} {description}")
    if detail:
        print(f"         {detail}")


def banner(text: str) -> None:
    print(f"\n{'=' * 78}\n{text}\n{'=' * 78}")


def upload(name: str, content: bytes, mime: str = "application/pdf"):
    return requests.post(
        f"{BASE}/api/documents/upload",
        files={"file": (name, io.BytesIO(content), mime)},
        timeout=120,
    )


def wait_for_terminal_status(doc_id: str, timeout: float = 300.0) -> dict:
    """Poll until the document leaves 'processing' (spec §15 status tracking)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        row = requests.get(f"{BASE}/api/documents/{doc_id}", timeout=30).json()
        if row["status"] != "processing":
            return row
        time.sleep(1.5)
    raise TimeoutError(f"{doc_id} never left 'processing'")


def ingest(fixture: str, as_name: str | None = None) -> dict:
    response = upload(as_name or fixture, (FIXTURES / fixture).read_bytes())
    assert response.status_code == 202, (response.status_code, response.text)
    doc_id = response.json()["document_id"]
    created.append(doc_id)
    return wait_for_terminal_status(doc_id)


def ask(question: str, document_id: str | None = None) -> dict:
    payload = {"question": question}
    if document_id:
        payload["document_id"] = document_id
    started = time.time()
    response = requests.post(f"{BASE}/api/chat/ask", json=payload, timeout=400)
    print(f"         (ask took {time.time() - started:.1f}s -> {response.status_code})")
    return response


# ══════════════════════════════════════════════════════════════════════════════
def f20_health():
    banner("F20  HEALTH CHECK — all services reported")
    data = requests.get(f"{BASE}/api/health", timeout=30).json()
    for field in ("status", "ollama_available", "chroma_available",
                  "embedding_model_loaded", "ocr_available", "database_available"):
        record("F20", f"health reports {field}", field in data)
    record("F20", "status is ok with every dependency up",
           data["status"] == "ok", json.dumps({k: v for k, v in data.items()
                                               if k.endswith("available")
                                               or k == "embedding_model_loaded"}))
    record("F20", "version is reported", bool(data.get("version")), data.get("version"))
    return data


def f17_upload_validation():
    banner("F17  UPLOAD VALIDATION — type, MIME, size, empty")
    pdf = (FIXTURES / "native_single.pdf").read_bytes()

    r = upload("notes.txt", b"this is not a pdf", "text/plain")
    record("F17", "non-.pdf extension rejected with 400", r.status_code == 400,
           r.json().get("detail"))

    r = upload("disguised.pdf", pdf, "image/png")
    record("F17", "wrong declared MIME rejected with 400", r.status_code == 400,
           r.json().get("detail"))

    r = upload("empty.pdf", b"", "application/pdf")
    record("F17", "empty file rejected with 400", r.status_code == 400,
           r.json().get("detail"))

    oversized = pdf + b"\x00" * (21 * 1024 * 1024)
    r = upload("huge.pdf", oversized)
    record("F17", "file over MAX_FILE_SIZE_MB rejected with 400", r.status_code == 400,
           r.json().get("detail"))

    # Boundary: just under the limit must be accepted, so the check is a limit
    # and not a blanket refusal of large files.
    just_under = pdf + b"\x00" * (19 * 1024 * 1024 - len(pdf))
    r = upload("just_under_limit.pdf", just_under)
    accepted = r.status_code == 202
    record("F17", "file just under the limit is accepted (boundary)", accepted,
           f"{len(just_under) / 1024 / 1024:.1f} MB -> {r.status_code}")
    if accepted:
        doc_id = r.json()["document_id"]
        created.append(doc_id)
        wait_for_terminal_status(doc_id)
        requests.delete(f"{BASE}/api/documents/{doc_id}", timeout=30)
        created.remove(doc_id)


def f1_f2_f2b_ingestion():
    banner("F1/F2/F2b  INGESTION — native, scanned (OCR), mixed, unreadable")

    native = ingest("native_single.pdf")
    record("F1/F2", "native PDF reaches 'ready'", native["status"] == "ready",
           native.get("error_message") or "")
    record("F2", "page count recorded", native["total_pages"] == 1, str(native["total_pages"]))
    record("F4", "chunks produced", native["total_chunks"] >= 1, str(native["total_chunks"]))
    record("F2", "native PDF used no OCR", native["ocr_pages_count"] == 0,
           str(native["ocr_pages_count"]))

    scanned = ingest("scanned_image_only.pdf")
    record("F2b", "image-only PDF reaches 'ready' via OCR", scanned["status"] == "ready",
           scanned.get("error_message") or "")
    record("F2b", "ocr_pages_count > 0 for the scanned document",
           scanned["ocr_pages_count"] > 0, str(scanned["ocr_pages_count"]))

    mixed = ingest("mixed_native_scanned.pdf")
    record("F2b", "mixed document OCRs only the pages that need it",
           mixed["status"] == "ready" and 0 < mixed["ocr_pages_count"] < mixed["total_pages"],
           f"{mixed['ocr_pages_count']} of {mixed['total_pages']} pages via OCR")

    unreadable = ingest("no_text.pdf")
    message = (unreadable.get("error_message") or "")
    record("F16", "PDF with no text by either method is marked 'failed'",
           unreadable["status"] == "failed", unreadable["status"])
    record("F16", "failure message says OCR was tried too", "ocr" in message.lower(), message)
    record("SEC", "failure message discloses no server path or document id",
           "uploads" not in message.lower() and unreadable["document_id"] not in message,
           message)

    multi = ingest("native_multi.pdf")
    record("F1", "multiple documents coexist (5 uploaded this run)",
           multi["status"] == "ready", f"{len(created)} documents created")
    return {"native": native, "scanned": scanned, "multi": multi}


def f14_document_management(docs):
    banner("F14  DOCUMENT MANAGEMENT — list, get, 404s")
    listing = requests.get(f"{BASE}/api/documents", timeout=30).json()
    ids = {d["document_id"] for d in listing}
    record("F14", "list returns every uploaded document",
           all(doc_id in ids for doc_id in created), f"{len(listing)} listed")
    record("F14", "list carries status, pages, chunks and OCR count",
           all({"status", "total_pages", "total_chunks", "ocr_pages_count"} <= set(d)
               for d in listing))

    r = requests.get(f"{BASE}/api/documents/{docs['native']['document_id']}", timeout=30)
    record("F14", "single document fetch returns 200", r.status_code == 200)
    r = requests.get(f"{BASE}/api/documents/no-such-document", timeout=30)
    record("F18", "unknown document id returns 404", r.status_code == 404)
    r = requests.delete(f"{BASE}/api/documents/no-such-document", timeout=30)
    record("F18", "deleting an unknown document returns 404", r.status_code == 404)


def f17_question_validation():
    banner("F17  QUESTION VALIDATION — empty, whitespace, over-length")
    r = ask("")
    record("F17", "empty question returns 400", r.status_code == 400)
    r = ask("   \n\t  ")
    record("F17", "whitespace-only question returns 400", r.status_code == 400)
    r = ask("x" * 2001)
    record("F17", "question over 2000 characters returns 422", r.status_code == 422)


def f7_f11_query(docs):
    banner("F7-F11  RETRIEVAL, GENERATION, CITATIONS, NOT-FOUND")

    r = ask("What does the document say about the history of artificial intelligence?")
    ok = r.status_code == 200
    record("F9", "grounded answer returned for an answerable question", ok,
           r.text[:160] if not ok else "")
    if ok:
        data = r.json()
        record("F10", "answer carries at least one citation",
               len(data["citations"]) >= 1, json.dumps(data["citations"])[:220])
        record("F10", "citation names a file and page numbers",
               all({"filename", "pages", "relevance_score", "extraction_method"} == set(c)
                   and c["pages"] for c in data["citations"]))
        record("F8", "processing time is reported",
               data["processing_time_ms"] >= 0, f"{data['processing_time_ms']} ms")
        print(f"         answer: {data['answer'][:200]}")

    r = ask("What was the keyword for retrieval testing in the scanned document?",
            document_id=docs["scanned"]["document_id"])
    ok = r.status_code == 200
    record("F2b", "question answerable only from OCR'd text succeeds", ok)
    if ok:
        data = r.json()
        methods = {c["extraction_method"] for c in data["citations"]}
        record("F10", "OCR-derived citation is tagged extraction_method='ocr'",
               "ocr" in methods, str(methods))
        print(f"         answer: {data['answer'][:200]}")

    r = ask("What is the recipe for a Victoria sponge cake?",
            document_id=docs["native"]["document_id"])
    ok = r.status_code == 200
    record("F11", "unanswerable question returns a 'not found' answer, not an invention",
           ok and r.json()["citations"] == [], r.json().get("answer", "")[:160])


def f14_delete(docs):
    banner("F14  DELETE — file, record and vectors removed together")
    doc_id = docs["native"]["document_id"]
    r = requests.delete(f"{BASE}/api/documents/{doc_id}", timeout=60)
    record("F14", "delete returns 200", r.status_code == 200)
    created.remove(doc_id)

    r = requests.get(f"{BASE}/api/documents/{doc_id}", timeout=30)
    record("F14", "deleted document is gone from the catalogue", r.status_code == 404)

    r = ask("What is in this document?", document_id=doc_id)
    gone = r.status_code == 200 and r.json()["citations"] == []
    record("F14", "deleted document's vectors are gone (scoped query retrieves nothing)",
           gone, r.json().get("answer", "")[:100])


def cleanup():
    banner("CLEANUP — removing documents created by this probe")
    for doc_id in list(created):
        requests.delete(f"{BASE}/api/documents/{doc_id}", timeout=60)
    remaining = requests.get(f"{BASE}/api/documents", timeout=30).json()
    print(f"  {len(created)} removed; {len(remaining)} document(s) left in the system")


def main() -> int:
    print(f"Functional probe against {BASE}")
    print(f"Fixtures: {FIXTURES}")
    f20_health()
    f17_upload_validation()
    docs = f1_f2_f2b_ingestion()
    f14_document_management(docs)
    f17_question_validation()
    f7_f11_query(docs)
    f14_delete(docs)
    cleanup()

    banner("SUMMARY")
    failed = [r for r in results if not r[2]]
    print(f"  {len(results) - len(failed)} passed, {len(failed)} failed, "
          f"{len(results)} checks total")
    for req, description, _, detail in failed:
        print(f"  FAILED  {req}  {description}  {detail}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
