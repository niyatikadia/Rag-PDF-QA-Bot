"""
Day 2 / Stage 8 — HTTP latency, percentiles and throughput.

PDF: "Latency at the 50th, 95th and 99th percentile - averages hide the users
having a terrible time. Throughput (requests per second)."

No load-testing package is installed (locust/k6/ab/JMeter all absent, and
installing was declined), so this driver uses `requests` + a thread pool, which
is already a project dependency. It measures the same things: per-request wall
latency, the percentiles, and achieved requests/second under a set concurrency.

Percentiles use the "nearest-rank" method on the sorted sample, stated in the
report so the numbers are reproducible. n is printed with every row, because a
p99 over 20 samples is the maximum and should be read as such.

Usage:  python perf_http.py read         # GET endpoints, sequential + concurrent
        python perf_http.py upload       # POST /documents/upload
"""
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

BASE = "http://127.0.0.1:8000"
FIXTURES = Path(__file__).resolve().parent.parent / "backend" / "tests" / "fixtures"


def pct(sorted_vals, p):
    """Nearest-rank percentile: the smallest value with at least p% below it."""
    if not sorted_vals:
        return float("nan")
    k = max(1, int(round(p / 100.0 * len(sorted_vals))))
    return sorted_vals[min(k, len(sorted_vals)) - 1]


def summarise(label, samples, wall, n_errors=0, extra=""):
    s = sorted(samples)
    print(f"\n  {label}")
    print(f"    n={len(s)}  errors={n_errors}  wall={wall:.2f}s"
          f"  throughput={len(s)/wall:.2f} req/s{extra}")
    if s:
        print(f"    min={s[0]*1000:.1f}ms  p50={pct(s,50)*1000:.1f}ms  "
              f"p95={pct(s,95)*1000:.1f}ms  p99={pct(s,99)*1000:.1f}ms  "
              f"max={s[-1]*1000:.1f}ms  mean={statistics.mean(s)*1000:.1f}ms")
    return s


def timed_get(path, session):
    t0 = time.perf_counter()
    try:
        r = session.get(BASE + path, timeout=60)
        ok = r.status_code == 200
    except Exception:
        ok = False
    return time.perf_counter() - t0, ok


def run_series(path, n, concurrency, warmup=3):
    """Fire n GETs at `path` with the given concurrency; return latencies."""
    session = requests.Session()
    for _ in range(warmup):                        # exclude connection setup
        timed_get(path, session)

    lat, errors = [], 0
    t0 = time.perf_counter()
    if concurrency == 1:
        for _ in range(n):
            d, ok = timed_get(path, session)
            lat.append(d)
            errors += (not ok)
    else:
        # One session per worker: requests.Session is not thread-safe.
        sessions = [requests.Session() for _ in range(concurrency)]
        with ThreadPoolExecutor(max_workers=concurrency) as ex:
            futs = [ex.submit(timed_get, path, sessions[i % concurrency])
                    for i in range(n)]
            for f in futs:
                d, ok = f.result()
                lat.append(d)
                errors += (not ok)
    return lat, time.perf_counter() - t0, errors


def cmd_read():
    print("=" * 78)
    print("STAGE 8 — READ-ENDPOINT LATENCY (sequential, concurrency=1)")
    print("=" * 78)
    for path, n in [("/api/documents", 100), ("/api/health", 30), ("/", 100)]:
        lat, wall, err = run_series(path, n, 1)
        summarise(f"GET {path}", lat, wall, err)

    # Single-document read needs a real id.
    docs = requests.get(BASE + "/api/documents", timeout=30).json()
    if docs:
        did = docs[0]["document_id"]
        lat, wall, err = run_series(f"/api/documents/{did}", 100, 1)
        summarise("GET /api/documents/{id}", lat, wall, err)

    print("\n" + "=" * 78)
    print("STAGE 8 — THROUGHPUT vs CONCURRENCY  (GET /api/documents, n=200)")
    print("=" * 78)
    print("  2 physical cores; uvicorn is single-process, so this measures the")
    print("  event loop plus SQLite, not parallel scaling.")
    for c in (1, 2, 4, 8, 16):
        lat, wall, err = run_series("/api/documents", 200, c)
        summarise(f"concurrency={c}", lat, wall, err)

    print("\n" + "=" * 78)
    print("STAGE 8 — /api/health UNDER CONCURRENCY (n=30)")
    print("=" * 78)
    print("  health fans out to Ollama over HTTP (timeout=3s), a Chroma")
    print("  heartbeat and a Tesseract version call, so it is the most")
    print("  expensive 'cheap' endpoint. Measured separately for that reason.")
    for c in (1, 4):
        lat, wall, err = run_series("/api/health", 30, c)
        summarise(f"concurrency={c}", lat, wall, err)


def cmd_upload():
    print("=" * 78)
    print("STAGE 8 — POST /api/documents/upload  (202, ingestion is async)")
    print("=" * 78)
    created = []
    for name, n in [("native_single.pdf", 10), ("native_multi.pdf", 10),
                    ("large_native.pdf", 10), ("scanned_image_only.pdf", 5)]:
        path = FIXTURES / name
        blob = path.read_bytes()
        lat, errors = [], 0
        t0 = time.perf_counter()
        for _ in range(n):
            f = {"file": (name, blob, "application/pdf")}
            t = time.perf_counter()
            try:
                r = requests.post(BASE + "/api/documents/upload", files=f, timeout=180)
                ok = r.status_code == 202
                if ok:
                    created.append(r.json()["document_id"])
            except Exception:
                ok = False
            lat.append(time.perf_counter() - t)
            errors += (not ok)
        summarise(f"upload {name} ({len(blob)/1024:.0f} KB)", lat,
                  time.perf_counter() - t0, errors)

    print(f"\n  created {len(created)} documents; ids written to uploaded_ids.txt")
    Path(__file__).with_name("uploaded_ids.txt").write_text("\n".join(created))


if __name__ == "__main__":
    {"read": cmd_read, "upload": cmd_upload}[sys.argv[1]]()
