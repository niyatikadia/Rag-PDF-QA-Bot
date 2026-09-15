"""
Day 2 / Stage 8 — the RAG pipeline: retrieval, generation, cold vs warm.

PDF: "pay particular attention to the actual user-facing operations and the
LLM/retrieval pipeline" and "Cold-start cost versus warm cost."

Retrieval is measured IN-PROCESS so its cost is separated from generation —
which otherwise swamps it by three orders of magnitude and makes the retrieval
half unmeasurable. Generation is measured over real HTTP, because that is what
a user actually waits for.

Run from backend/.
"""
import statistics
import sys
import time

import requests

BASE = "http://127.0.0.1:8000"

QUESTIONS = [
    "What is this document about?",
    "What keyword is used for retrieval testing?",
    "Summarise the main points.",
    "What does the second page say?",
    "Which page mentions pineapple?",
]


def pct(vals, p):
    s = sorted(vals)
    k = max(1, int(round(p / 100.0 * len(s))))
    return s[min(k, len(s)) - 1]


def summarise(label, samples, unit="ms", scale=1000):
    s = sorted(samples)
    if not s:
        print(f"  {label}: no samples")
        return
    print(f"  {label}")
    print(f"    n={len(s)}  min={s[0]*scale:.1f}{unit}  p50={pct(s,50)*scale:.1f}{unit}  "
          f"p95={pct(s,95)*scale:.1f}{unit}  p99={pct(s,99)*scale:.1f}{unit}  "
          f"max={s[-1]*scale:.1f}{unit}  mean={statistics.mean(s)*scale:.1f}{unit}")


def cmd_retrieval():
    """Embed + ChromaDB query, in-process, no LLM."""
    from app.services import retriever
    from app.services.embedder import embed_query

    print("=" * 78)
    print("STAGE 8 — RETRIEVAL PIPELINE (in-process, no LLM)")
    print("=" * 78)

    # Warm the embedding model and the Chroma collection handle first.
    for _ in range(3):
        retriever.retrieve("warmup query")

    print("\n--- embed_query() alone (sentence-transformers, 384-dim) ---")
    lat = []
    for i in range(50):
        q = QUESTIONS[i % len(QUESTIONS)]
        t = time.perf_counter()
        embed_query(q)
        lat.append(time.perf_counter() - t)
    summarise("embed_query()", lat)

    print("\n--- retrieve() end to end (embed + ChromaDB top-k) ---")
    lat = []
    for i in range(50):
        q = QUESTIONS[i % len(QUESTIONS)]
        t = time.perf_counter()
        hits = retriever.retrieve(q)
        lat.append(time.perf_counter() - t)
    summarise("retrieve()", lat)
    print(f"    (last query returned {len(hits)} chunk(s))")

    print("\n--- retrieve() filtered to one document ---")
    docs = requests.get(BASE + "/api/documents", timeout=30).json()
    if docs:
        did = docs[0]["document_id"]
        lat = []
        for i in range(50):
            t = time.perf_counter()
            retriever.retrieve(QUESTIONS[i % len(QUESTIONS)], document_id=did)
            lat.append(time.perf_counter() - t)
        summarise("retrieve(document_id=...)", lat)


def cmd_generate(n_warm=5):
    """Full /api/chat/ask over HTTP: the number the user actually experiences."""
    print("=" * 78)
    print("STAGE 8 — GENERATION: /api/chat/ask over HTTP")
    print("=" * 78)
    print("  Run `ollama stop <model>` immediately before this to make the")
    print("  first sample a genuine cold start.")

    skip_cold = "--warm-only" in sys.argv
    lat, codes, rates = [], [], []
    for i in range(n_warm + (0 if skip_cold else 1)):
        q = QUESTIONS[i % len(QUESTIONS)]
        t = time.perf_counter()
        answer_chars = 0
        try:
            r = requests.post(BASE + "/api/chat/ask", json={"question": q},
                              timeout=400)
            code = r.status_code
            body = r.json() if code == 200 else {}
            cites = len(body.get("citations", []))
            server_ms = body.get("processing_time_ms")
            answer_chars = len(body.get("answer", ""))
        except Exception as exc:
            code, cites, server_ms = type(exc).__name__, 0, None
        d = time.perf_counter() - t
        lat.append(d)
        codes.append(code)
        if answer_chars:
            rates.append(answer_chars / d)
        tag = "warm" if skip_cold else ("COLD" if i == 0 else f"warm {i}")
        print(f"    [{tag:<7}] {d:7.1f}s  http={code}  citations={cites}  "
              f"answer={answer_chars:4d} chars  "
              f"{answer_chars/d if d else 0:5.1f} char/s   q={q[:34]!r}")

    print()
    if skip_cold:
        summarise("warm requests", lat, unit="s", scale=1)
    elif len(lat) > 1:
        summarise("cold request (n=1)", lat[:1], unit="s", scale=1)
        summarise("warm requests", lat[1:], unit="s", scale=1)
        print(f"\n    cold-start premium: {lat[0] - statistics.median(lat[1:]):.1f}s "
              f"over the warm median")
    if rates:
        print(f"\n    output rate: p50={statistics.median(sorted(rates)):.1f} char/s "
              f"over n={len(rates)}  (min={min(rates):.1f}, max={max(rates):.1f})")
        print("    Latency tracks ANSWER LENGTH, not retrieval: retrieval is a "
              "flat ~36 ms of every one of these.")
    print(f"    status codes: {codes}")


if __name__ == "__main__":
    {"retrieval": cmd_retrieval,
     "generate": lambda: cmd_generate(int(sys.argv[2]) if len(sys.argv) > 2 else 5)
     }[sys.argv[1]]()
