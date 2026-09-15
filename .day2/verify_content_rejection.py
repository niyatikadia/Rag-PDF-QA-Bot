"""
Day 2 — verify a claim I made but had not actually checked.

§2.8 states that files accepted at upload on name+MIME are then rejected at
ingestion because their CONTENT is not a PDF. The security probe deleted those
documents before reading their final status, so the claim was unverified. This
uploads each one, waits for ingestion to settle, and records the real outcome.
"""
import time

import requests

BASE = "http://127.0.0.1:8000"

CASES = [
    ("evil.exe.pdf", b"MZ\x90\x00" + b"\x00" * 200, "Windows executable"),
    ("html.pdf", b"<html><script>alert(1)</script></html>", "HTML"),
    ("zeros.pdf", b"%PDF-1.4\n" + b"0" * 5000, "PDF header, garbage body"),
]

print("=" * 78)
print("Does content that passes name+MIME validation actually fail ingestion?")
print("=" * 78)

for name, blob, what in CASES:
    r = requests.post(BASE + "/api/documents/upload",
                      files={"file": (name, blob, "application/pdf")}, timeout=180)
    print(f"\n{name}  ({what})")
    print(f"    upload: HTTP {r.status_code}")
    if r.status_code != 202:
        print(f"    detail: {r.json().get('detail')!r}")
        continue

    doc_id = r.json()["document_id"]
    row = {}
    for _ in range(90):
        time.sleep(1)
        row = requests.get(f"{BASE}/api/documents/{doc_id}", timeout=30).json()
        if row.get("status") in ("ready", "failed"):
            break
    print(f"    final status  : {row.get('status')}")
    print(f"    chunks stored : {row.get('total_chunks')}")
    print(f"    error shown   : {row.get('error_message')!r}")
    requests.delete(f"{BASE}/api/documents/{doc_id}", timeout=120)
    print("    (cleaned up)")
