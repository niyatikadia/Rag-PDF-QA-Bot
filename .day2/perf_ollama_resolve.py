"""
Day 2 / Stage 8 — why does a localhost GET to Ollama cost ~2 seconds?

Hypothesis: on Windows, "localhost" resolves to BOTH ::1 (IPv6) and 127.0.0.1.
If Ollama binds IPv4 only, the client tries ::1 first, waits for that connection
to fail, and only then falls back to IPv4 — a fixed penalty on every request.

This compares the three forms against each other and reports what the name
actually resolves to and what Ollama is actually listening on. Nothing is
changed. Run from backend/.
"""
import socket
import statistics
import time

import requests

N = 10
URLS = [
    "http://localhost:11434/api/tags",
    "http://127.0.0.1:11434/api/tags",
    "http://[::1]:11434/api/tags",
]

print("=" * 78)
print("STAGE 8 — Ollama localhost resolution cost")
print("=" * 78)

print("\n--- what does 'localhost' resolve to, in the order the client tries? ---")
for fam, typ, proto, canon, sockaddr in socket.getaddrinfo(
        "localhost", 11434, proto=socket.IPPROTO_TCP):
    print(f"    {socket.AddressFamily(fam).name:<10} {sockaddr}")

print("\n--- raw TCP connect time per address ---")
for family, addr, label in [(socket.AF_INET6, ("::1", 11434), "::1      "),
                            (socket.AF_INET, ("127.0.0.1", 11434), "127.0.0.1")]:
    times, outcome = [], ""
    for _ in range(N):
        s = socket.socket(family, socket.SOCK_STREAM)
        s.settimeout(5)
        t = time.perf_counter()
        try:
            s.connect(addr)
            outcome = "connected"
        except Exception as exc:
            outcome = f"{type(exc).__name__}"
        times.append(time.perf_counter() - t)
        s.close()
    print(f"    {label} p50={statistics.median(sorted(times))*1000:8.1f}ms  "
          f"-> {outcome}")

print("\n--- full HTTP GET via requests (the call health.py actually makes) ---")
for url in URLS:
    times, status = [], ""
    for _ in range(N):
        t = time.perf_counter()
        try:
            r = requests.get(url, timeout=5)
            status = r.status_code
        except Exception as exc:
            status = type(exc).__name__
        times.append(time.perf_counter() - t)
    s = sorted(times)
    print(f"    {url:<42} p50={statistics.median(s)*1000:8.1f}ms  "
          f"min={s[0]*1000:7.1f}ms  -> {status}")

print("\n--- with a reused connection (requests.Session, keep-alive) ---")
for url in URLS[:2]:
    sess = requests.Session()
    try:
        sess.get(url, timeout=5)
    except Exception:
        pass
    times = []
    for _ in range(N):
        t = time.perf_counter()
        try:
            sess.get(url, timeout=5)
        except Exception:
            pass
        times.append(time.perf_counter() - t)
    print(f"    {url:<42} p50={statistics.median(sorted(times))*1000:8.1f}ms")
