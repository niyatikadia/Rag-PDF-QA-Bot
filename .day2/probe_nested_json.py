"""
Day 2 / Stage 9 — the one input-validation row that answered 500, examined.

A 500 on client-supplied malformed input is worth looking at directly: does it
leak internals, and does it leave the server healthy?
"""
import re
import requests

BASE = "http://127.0.0.1:8000"

LEAK = re.compile(r"C:\\\\|C:/|RAGPDFQABOT|site-packages|Traceback|"
                  r"RecursionError|\.venv|maximum recursion", re.I)

for depth in (200, 1000, 5000):
    raw = ('{"question":' * depth + '"x"' + '}' * depth).encode()
    r = requests.post(BASE + "/api/chat/ask", data=raw, timeout=120,
                      headers={"Content-Type": "application/json"})
    leaks = LEAK.findall(r.text)
    print(f"\ndepth={depth:<5} HTTP {r.status_code}  bytes={len(r.content)}")
    print(f"  body   : {r.text[:220]!r}")
    print(f"  leaks  : {sorted(set(leaks)) or 'none'}")

print("\n--- is the server still healthy afterwards? ---")
for path in ("/api/documents", "/api/health"):
    r = requests.get(BASE + path, timeout=60)
    print(f"  GET {path:<18} HTTP {r.status_code}")

print("\n--- and does a normal question still work? ---")
r = requests.post(BASE + "/api/chat/ask",
                  json={"question": "Anything?"}, timeout=400)
print(f"  POST /api/chat/ask HTTP {r.status_code}")
