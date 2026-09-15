"""
Day 2 / Stage 8 — does one slow request block every other request?

Both /api/health and /api/chat/ask are declared `async def` but perform
BLOCKING work inside the coroutine:

  health.py     requests.get(ollama, timeout=3)          ~2 s on this machine
  chat.py       retriever.retrieve(...)                  embedding + ChromaDB
  chat.py       llm_service.generate_answer(...)         requests.post, up to 300 s

In FastAPI, a `def` handler is run in a threadpool, but an `async def` handler
runs ON the event loop — so any blocking call inside it stalls the entire
server, not just that request. This probe measures that directly:

  baseline : GET /api/documents on an idle server, n=20
  during   : the same GET, fired repeatedly WHILE one slow request is in flight

If the handler is blocking the loop, "during" latency rises to roughly the
remaining duration of the slow request. If it is not, "during" matches baseline.

Run from backend/.
"""
import statistics
import sys
import threading
import time

import requests

BASE = "http://127.0.0.1:8000"


def poll_documents(stop_evt, out):
    s = requests.Session()
    while not stop_evt.is_set():
        t = time.perf_counter()
        try:
            r = s.get(BASE + "/api/documents", timeout=400)
            code = r.status_code
        except Exception as exc:
            code = type(exc).__name__
        out.append((time.perf_counter() - t, code))


def summarise(label, samples):
    lat = sorted(d for d, _ in samples)
    codes = {}
    for _, c in samples:
        codes[c] = codes.get(c, 0) + 1
    if not lat:
        print(f"  {label}: no samples")
        return
    print(f"  {label}")
    print(f"    n={len(lat)}  p50={statistics.median(lat)*1000:.1f}ms  "
          f"max={lat[-1]*1000:.1f}ms  responses={codes}")


print("=" * 78)
print("STAGE 8 — event-loop blocking probe")
print("=" * 78)

# ── baseline, idle server ─────────────────────────────────────────────────────
base = []
stop = threading.Event()
th = threading.Thread(target=poll_documents, args=(stop, base), daemon=True)
th.start()
time.sleep(4)
stop.set(); th.join()
print("\nBASELINE (idle server)")
summarise("GET /api/documents", base)

# ── while ONE /api/health is in flight (blocking requests.get, ~2 s) ──────────
during = []
stop = threading.Event()
th = threading.Thread(target=poll_documents, args=(stop, during), daemon=True)
th.start()
time.sleep(0.4)
t0 = time.perf_counter()
h = requests.get(BASE + "/api/health", timeout=120)
health_ms = (time.perf_counter() - t0) * 1000
time.sleep(0.2)
stop.set(); th.join()
print(f"\nWHILE ONE /api/health IS IN FLIGHT  (health took {health_ms:.0f}ms)")
summarise("GET /api/documents", during)

# ── while a real /api/chat/ask is in flight (the expensive case) ──────────────
if "--with-chat" in sys.argv:
    during2 = []
    stop = threading.Event()
    th = threading.Thread(target=poll_documents, args=(stop, during2), daemon=True)
    th.start()
    time.sleep(0.5)
    t0 = time.perf_counter()
    try:
        r = requests.post(BASE + "/api/chat/ask",
                          json={"question": "What is this document about?"},
                          timeout=400)
        chat_s = time.perf_counter() - t0
        chat_desc = f"{r.status_code} in {chat_s:.1f}s"
    except Exception as exc:
        chat_s = time.perf_counter() - t0
        chat_desc = f"{type(exc).__name__} after {chat_s:.1f}s"
    time.sleep(0.3)
    stop.set(); th.join()
    print(f"\nWHILE ONE /api/chat/ask IS IN FLIGHT  ({chat_desc})")
    summarise("GET /api/documents", during2)
    blocked = [d for d, _ in during2 if d > 1.0]
    print(f"    requests that waited >1 s: {len(blocked)} of {len(during2)}")
    if blocked:
        print(f"    longest wait: {max(blocked):.1f}s  "
              f"(chat request itself took {chat_s:.1f}s)")
