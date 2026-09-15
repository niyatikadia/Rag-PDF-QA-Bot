"""
Day 2 / Stage 8 — "Behaviour when a dependency is slow rather than down."

Down is already covered (Day 1: a stopped Ollama gives 503). Slow is the harder
and more interesting case, because a slow dependency does not announce itself.

A stand-in Ollama is run on a spare port and the backend is pointed at it with
OLLAMA_BASE_URL, so the delay is exact and reproducible. The real Ollama is
never touched and backend/.env is never edited — the override is passed to the
child process only.

Scenarios:
  fast      0 s   sanity: the harness itself is not the bottleneck
  slow     20 s   well inside OLLAMA_TIMEOUT_SECONDS
  slower  0.8x    just inside the timeout
  timeout 1.2x    just past it -> must be 503, not 500, and not a hang
  trickle         headers immediately, body dribbled out slowly (the nastiest
                  case: the connection is alive, so a naive client waits forever)

Usage:  python perf_slow_dependency.py <backend_port> <stub_port>
"""
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests

BACKEND = f"http://127.0.0.1:{sys.argv[1]}"
STUB_PORT = int(sys.argv[2])

DELAY = {"seconds": 0.0, "mode": "normal"}
BODY = json.dumps({"response": "A stubbed answer from the slow dependency.",
                   "done": True}).encode()


class Stub(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def do_GET(self):
        # /api/tags — the health check
        self.send_response(200)
        payload = json.dumps({"models": [{"name": "stub:latest"}]}).encode()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        self.rfile.read(length)

        if DELAY["mode"] == "trickle":
            # Respond immediately, then dribble the body out. The socket never
            # goes idle long enough to look dead.
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(BODY)))
            self.end_headers()
            for i in range(0, len(BODY), 8):
                try:
                    self.wfile.write(BODY[i:i + 8])
                    self.wfile.flush()
                except Exception:
                    return
                time.sleep(DELAY["seconds"] / max(1, len(BODY) / 8))
            return

        time.sleep(DELAY["seconds"])
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(BODY)))
        self.end_headers()
        self.wfile.write(BODY)


server = HTTPServer(("127.0.0.1", STUB_PORT), Stub)
threading.Thread(target=server.serve_forever, daemon=True).start()
print(f"stub Ollama listening on 127.0.0.1:{STUB_PORT}")

health = requests.get(BACKEND + "/api/health", timeout=60).json()
timeout_s = None
try:
    sys.path.insert(0, ".")
    from app.config import OLLAMA_TIMEOUT_SECONDS as timeout_s
except Exception:
    timeout_s = 300
print(f"backend OLLAMA_TIMEOUT_SECONDS = {timeout_s}")
print(f"backend health = {health.get('status')} "
      f"(ollama_available={health.get('ollama_available')})")

CASES = [
    ("fast    (0 s)", 0.0, "normal"),
    ("slow    (20 s)", 20.0, "normal"),
    (f"slower  (0.8x timeout = {timeout_s * 0.8:.0f} s)", timeout_s * 0.8, "normal"),
    (f"timeout (1.2x timeout = {timeout_s * 1.2:.0f} s)", timeout_s * 1.2, "normal"),
    ("trickle (30 s dribbled body)", 30.0, "trickle"),
]

print("\n" + "=" * 78)
print("STAGE 8 — BEHAVIOUR WHEN OLLAMA IS SLOW (not down)")
print("=" * 78)

for label, secs, mode in CASES:
    DELAY["seconds"], DELAY["mode"] = secs, mode

    # Does the rest of the app stay responsive while one question is stuck?
    other = {"codes": [], "max_ms": 0.0}
    stop = threading.Event()

    def poll():
        s = requests.Session()
        while not stop.is_set():
            t = time.perf_counter()
            try:
                r = s.get(BACKEND + "/api/documents", timeout=600)
                code = r.status_code
            except Exception as exc:
                code = type(exc).__name__
            d = (time.perf_counter() - t) * 1000
            other["codes"].append(code)
            other["max_ms"] = max(other["max_ms"], d)
            time.sleep(0.25)

    th = threading.Thread(target=poll, daemon=True)
    th.start()

    t0 = time.perf_counter()
    try:
        r = requests.post(BACKEND + "/api/chat/ask",
                          json={"question": "What does the document say?"},
                          timeout=timeout_s * 2)
        status, detail = r.status_code, (
            r.json().get("detail", "")[:95] if r.status_code != 200
            else r.json().get("answer", "")[:60])
    except Exception as exc:
        status, detail = type(exc).__name__, str(exc)[:90]
    elapsed = time.perf_counter() - t0

    stop.set()
    th.join()
    uniq = sorted({str(c) for c in other["codes"]})

    print(f"\n  {label}")
    print(f"    /chat/ask -> HTTP {status} after {elapsed:7.1f}s")
    print(f"    detail    : {detail!r}")
    print(f"    meanwhile : {len(other['codes'])} x GET /api/documents, "
          f"responses={uniq}, slowest {other['max_ms']:.0f} ms")

server.shutdown()
print("\nstub stopped")
