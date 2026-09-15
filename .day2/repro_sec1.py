"""
Day 2 / Stage 9 — SEC-1: unguarded int() on untrusted LLM output.

Found by the ReDoS probe. The regex itself is fine (linear: 97 ms over 80,000
adversarial chars), but this line has no defence against its own input:

    app/services/llm_service.py, _mentioned_pages()
        pages.update(int(n) for n in re.findall(r"\\d+", run))

Python 3.11+ refuses int() on a decimal string longer than 4300 digits
(CVE-2020-10735 mitigation), raising ValueError. `answer` is model output, which
is untrusted text: the model can be induced to emit a long digit run, and a
document can ask it to.

This script proves the impact in the order the PDF requires — the attack FIRST,
then the fix — at two levels:

  1. the function raises;
  2. the HTTP request a user made returns 500, losing the answer, with the LLM
     call stubbed so the reproduction is deterministic rather than dependent on
     what the model feels like emitting.

Run from backend/.
"""
import sys
import traceback

from fastapi.testclient import TestClient

sys.path.insert(0, ".")

from app.services import llm_service          # noqa: E402
from app.main import app                      # noqa: E402

DIGITS = 5000
EVIL_ANSWER = ("According to the document, see pages "
               + "9" * DIGITS
               + " for the full table. (native_single.pdf, Page 1)")

print("=" * 78)
print("SEC-1 — unguarded int() on model output")
print("=" * 78)
print(f"\nattack payload: an answer containing 'pages ' followed by {DIGITS} digits")

# ── level 1: the function ────────────────────────────────────────────────────
print("\n--- level 1: _mentioned_pages() directly ---")
try:
    pages = llm_service._mentioned_pages(EVIL_ANSWER)
    print(f"    returned {pages!r}  -> NO EXCEPTION (fixed)")
    level1_raised = False
except Exception:
    level1_raised = True
    print("    RAISED:")
    for line in traceback.format_exc().strip().splitlines()[-3:]:
        print("      |", line)

# ── level 2: through extract_citations, the real call path ───────────────────
print("\n--- level 2: extract_citations() (the path generate_answer uses) ---")
chunks = [{
    "chunk_id": "c1", "text": "Some text about testing.", "score": 0.7,
    "metadata": {"filename": "native_single.pdf", "page_number": 1,
                 "document_id": "d1", "chunk_index": 0,
                 "extraction_method": "native"},
}]
try:
    cites = llm_service.extract_citations(EVIL_ANSWER, chunks)
    print(f"    returned {len(cites)} citation(s): {cites}  -> NO EXCEPTION (fixed)")
    level2_raised = False
except Exception as exc:
    level2_raised = True
    print(f"    RAISED: {type(exc).__name__}: {str(exc)[:110]}")

# ── level 3: what the USER gets, over HTTP ───────────────────────────────────
print("\n--- level 3: POST /api/chat/ask with the LLM stubbed to return it ---")
original = llm_service.call_ollama
llm_service.call_ollama = lambda *a, **k: EVIL_ANSWER
try:
    with TestClient(app) as client:
        r = client.post("/api/chat/ask", json={"question": "Where is the table?"})
        print(f"    HTTP {r.status_code}")
        body = r.json()
        if r.status_code == 200:
            print(f"    answer length : {len(body.get('answer', ''))} chars")
            print(f"    citations     : {body.get('citations')}")
            print("    -> the user got their answer (fixed)")
        else:
            print(f"    detail: {body.get('detail')!r}")
            print("    -> the user's answer was DISCARDED and replaced with a 500")
        level3_status = r.status_code
finally:
    llm_service.call_ollama = original

print("\n" + "=" * 78)
print(f"level 1 raised: {level1_raised}   level 2 raised: {level2_raised}   "
      f"level 3 HTTP: {level3_status}")
print("VULNERABLE" if (level1_raised or level3_status != 200) else "NOT VULNERABLE")
print("=" * 78)
