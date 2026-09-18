"""
perf_throughput_memory.py — post-coding Day 6, stage 8 (performance).

Closes the two sub-checks of stage 8 in 01_After_Coding_Is_Complete.pdf that
Day 2 left without a number:

  * "Throughput (requests per second)"
  * "Memory growth over time (a leak shows as a rising floor)"

Day 2 measured latency percentiles, cold-versus-warm cost, per-request memory
under an oversized upload, and behaviour when a dependency is slow. It did not
produce a requests-per-second figure or a memory floor over a sustained run.

Two honest notes about what throughput means for this system, stated here so
the numbers are not read as something they are not:

  1. The answer path is bounded by local CPU generation at 25-170 s per
     question. Its throughput is therefore a fraction of one request per
     second by construction, and measuring it with concurrency would measure
     Ollama's queueing, not this service's. What IS worth measuring is that
     the service stays responsive to other requests while a generation is in
     flight - Day 2 fixed a defect where it did not - so the read endpoints are
     measured both idle and during a live question.

  2. The read endpoints (/api/documents, /api/health) are what a UI polls, and
     they are the ones where a throughput number is meaningful.

Run with the backend up and Ollama running:

    backend/.venv/Scripts/python.exe .day6/perf_throughput_memory.py
"""
import json
import statistics
import sys
import threading
import time
from pathlib import Path

import requests

BASE = "http://127.0.0.1:8000"
REPO = Path(__file__).resolve().parent.parent
FIXTURES = REPO / "backend" / "tests" / "fixtures"

report = {}


def backend_process():
    """The uvicorn process serving BASE, found by the port it listens on."""
    import psutil  # noqa: F401  (only used when available)
    raise RuntimeError


def find_backend_rss_mb():
    """
    Working-set size of the process listening on 8000, via tasklist/netstat so
    no extra dependency is needed.
    """
    import re
    import subprocess

    net = subprocess.run(["netstat", "-ano"], capture_output=True, text=True).stdout
    pid = None
    for line in net.splitlines():
        if ":8000" in line and "LISTENING" in line:
            pid = line.split()[-1]
            break
    if not pid:
        return None, None

    tasks = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
        capture_output=True, text=True,
    ).stdout
    match = re.search(r'"([\d,]+) K"', tasks)
    if not match:
        return pid, None
    return pid, int(match.group(1).replace(",", "")) / 1024.0


def measure_throughput(path: str, seconds: float, label: str) -> dict:
    """Sequential closed-loop throughput: how many requests one client completes."""
    latencies = []
    deadline = time.time() + seconds
    session = requests.Session()
    errors = 0
    while time.time() < deadline:
        started = time.perf_counter()
        try:
            response = session.get(f"{BASE}{path}", timeout=30)
            if response.status_code != 200:
                errors += 1
        except Exception:
            errors += 1
        latencies.append((time.perf_counter() - started) * 1000)

    latencies.sort()
    elapsed = seconds
    result = {
        "endpoint": path,
        "duration_s": round(elapsed, 1),
        "requests": len(latencies),
        "requests_per_second": round(len(latencies) / elapsed, 1),
        "errors": errors,
        "p50_ms": round(statistics.median(latencies), 2),
        "p95_ms": round(latencies[int(len(latencies) * 0.95)], 2),
        "p99_ms": round(latencies[int(len(latencies) * 0.99)], 2),
        "max_ms": round(latencies[-1], 2),
    }
    print(f"  {label}: {result['requests_per_second']} req/s  "
          f"p50 {result['p50_ms']}ms  p95 {result['p95_ms']}ms  "
          f"p99 {result['p99_ms']}ms  errors {errors}")
    return result


def main() -> int:
    print("=" * 78)
    print("STAGE 8 - THROUGHPUT AND LONG-RUN MEMORY")
    print("=" * 78)

    pid, rss_start = find_backend_rss_mb()
    print(f"\nBackend PID {pid}, working set at start: {rss_start:.1f} MB\n")
    report["backend_pid"] = pid
    report["rss_start_mb"] = round(rss_start, 1) if rss_start else None

    # ── 1. Idle throughput of the two read endpoints ────────────────────────
    print("1. Read-endpoint throughput, service otherwise idle")
    report["idle"] = {
        "documents": measure_throughput("/api/documents", 10, "GET /api/documents"),
        "health": measure_throughput("/api/health", 10, "GET /api/health    "),
    }

    # ── 2. Throughput while a real generation is in flight ──────────────────
    #
    # This is the measurement that matters for this service: Day 2 found that
    # handlers declared `async def` while doing blocking work froze every other
    # request for the full duration of a question. They are `def` now, so they
    # run in the threadpool. This proves that still holds under the real model.
    print("\n2. Read-endpoint throughput WHILE a question is being answered")
    answer_result = {}

    def ask():
        started = time.perf_counter()
        try:
            response = requests.post(
                f"{BASE}/api/chat/ask",
                json={"question": "What was the keyword for retrieval testing?"},
                timeout=400,
            )
            answer_result["status"] = response.status_code
            answer_result["seconds"] = round(time.perf_counter() - started, 1)
        except Exception as exc:
            answer_result["error"] = str(exc)

    thread = threading.Thread(target=ask, daemon=True)
    thread.start()
    time.sleep(3)   # let the generation actually start
    report["under_load"] = {
        "documents": measure_throughput("/api/documents", 20, "GET /api/documents"),
    }
    print("  waiting for the generation to finish…")
    thread.join(timeout=400)
    report["concurrent_answer"] = answer_result
    print(f"  the question itself: {answer_result}")

    # ── 3. Memory floor over a sustained run ────────────────────────────────
    #
    # A leak shows as a rising floor, so the floor is sampled between bursts of
    # work rather than during them: transient allocation during a request is
    # expected and is not what this check is looking for.
    print("\n3. Memory floor across repeated ingest/query/delete cycles")
    samples = []
    pdf = (FIXTURES / "native_multi.pdf").read_bytes()
    for cycle in range(1, 6):
        for _ in range(3):
            response = requests.post(
                f"{BASE}/api/documents/upload",
                files={"file": ("perf_cycle.pdf", pdf, "application/pdf")},
                timeout=120,
            )
            doc_id = response.json()["document_id"]
            for _ in range(60):
                row = requests.get(f"{BASE}/api/documents/{doc_id}", timeout=30).json()
                if row["status"] != "processing":
                    break
                time.sleep(1)
            requests.delete(f"{BASE}/api/documents/{doc_id}", timeout=60)

        for _ in range(50):
            requests.get(f"{BASE}/api/documents", timeout=30)

        time.sleep(2)
        _, rss = find_backend_rss_mb()
        samples.append(round(rss, 1))
        print(f"  cycle {cycle}: 3 ingest+delete, 50 reads -> working set {rss:.1f} MB")

    report["memory_floor_mb"] = samples
    growth = samples[-1] - samples[0]
    report["memory_growth_mb"] = round(growth, 1)
    report["memory_verdict"] = (
        "no sustained growth" if growth < 25 else "INVESTIGATE - floor rose"
    )
    print(f"\n  floor {samples[0]} MB -> {samples[-1]} MB over {len(samples)} cycles "
          f"({growth:+.1f} MB): {report['memory_verdict']}")

    out = REPO / ".day6" / "perf_throughput_memory.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nWritten: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
