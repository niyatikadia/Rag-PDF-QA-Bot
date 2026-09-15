"""
Day 2 — return the corpus to the exact state Day 1 left it in.

Day 1's verified baseline is 3 documents / 5 chunks:
    native_single.pdf        native  1 chunk
    native_multi.pdf         native  3 chunks
    scanned_image_only.pdf   ocr     1 chunk

Day 2's probes created and mostly deleted many documents; this deletes whatever
is left and restores the baseline using the three commands the README documents,
then verifies the result against both SQLite and ChromaDB.

Run from backend/.
"""
import time
from pathlib import Path

import requests

BASE = "http://127.0.0.1:8000"
FIXTURES = Path("tests/fixtures")
BASELINE = ["native_single.pdf", "native_multi.pdf", "scanned_image_only.pdf"]

print("=" * 78)
print("RESTORING DAY 1'S VERIFIED BASELINE")
print("=" * 78)

docs = requests.get(BASE + "/api/documents", timeout=60).json()
print(f"\nfound {len(docs)} document(s); deleting all")
removed = 0
for d in docs:
    try:
        if requests.delete(f"{BASE}/api/documents/{d['document_id']}",
                           timeout=180).status_code == 200:
            removed += 1
    except Exception as exc:
        print(f"  could not delete {d['filename']}: {type(exc).__name__}")
print(f"deleted {removed}/{len(docs)}")

time.sleep(3)
left = requests.get(BASE + "/api/documents", timeout=60).json()
print(f"remaining after delete: {len(left)}")

print("\nre-uploading the three README fixtures")
for name in BASELINE:
    r = requests.post(BASE + "/api/documents/upload",
                      files={"file": (name, (FIXTURES / name).read_bytes(),
                                      "application/pdf")}, timeout=180)
    print(f"  {name:<26} HTTP {r.status_code}")

# Wait for ingestion (the scanned one runs OCR).
deadline = time.time() + 300
while time.time() < deadline:
    docs = requests.get(BASE + "/api/documents", timeout=60).json()
    if docs and all(d["status"] in ("ready", "failed") for d in docs):
        break
    time.sleep(2)

print("\n--- final state, from the API ---")
for d in sorted(docs, key=lambda x: x["filename"]):
    print(f"  {d['filename']:<26} {d['status']:<9} "
          f"pages={d['total_pages']} chunks={d['total_chunks']} "
          f"ocr={d['ocr_pages_count']}")

print("\n--- final state, from ChromaDB directly ---")
import sys
sys.path.insert(0, ".")
from app.services.vector_store import get_collection
col = get_collection()
got = col.get(include=["metadatas"])
by_file = {}
for m in got["metadatas"]:
    key = (m.get("filename"), m.get("extraction_method"))
    by_file[key] = by_file.get(key, 0) + 1
print(f"  TOTAL VECTORS IN STORE: {len(got['ids'])}")
for (fn, method), n in sorted(by_file.items()):
    print(f"    {fn:<26} {method:<8} {n} chunk(s)")

expected = len(got["ids"]) == 5 and len(docs) == 3
print(f"\n  matches Day 1 baseline (3 documents / 5 chunks): {expected}")
