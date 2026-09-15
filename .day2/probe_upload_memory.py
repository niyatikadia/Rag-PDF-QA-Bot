"""
Day 2 — Day 1 deferral #4: "Upload reads the whole file into memory before the
size check (documents.py). Resource-handling concern -> Day 2."

documents.py does:
    content = await file.read()      # entire body materialised as one bytes
    _validate_file(file, content)    # size checked only now

So a client can make the server allocate a bytes object as large as it likes
before the 20 MB limit is ever consulted. On this 7.89 GB machine with ~1.9 GB
free that is worth measuring rather than reasoning about.

Working set is read straight from the Win32 API via ctypes (no subprocess per
sample, so a 50 ms sampling interval is actually 50 ms).

Usage:  python probe_upload_memory.py <backend_pid>
"""
import ctypes
import ctypes.wintypes as wt
import sys
import threading
import time

import requests

BASE = "http://127.0.0.1:8000"
LIMIT_MB = 20

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
    _fields_ = [
        ("cb", wt.DWORD),
        ("PageFaultCount", wt.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
        ("PrivateUsage", ctypes.c_size_t),
    ]


PID = int(sys.argv[1])
_handle = ctypes.windll.kernel32.OpenProcess(
    PROCESS_QUERY_LIMITED_INFORMATION, False, PID)
if not _handle:
    raise SystemExit(f"could not open process {PID}")


def mem():
    """(working_set_MB, private_MB, peak_working_set_MB)"""
    c = PROCESS_MEMORY_COUNTERS_EX()
    c.cb = ctypes.sizeof(c)
    ok = ctypes.windll.psapi.GetProcessMemoryInfo(
        _handle, ctypes.byref(c), c.cb)
    if not ok:
        return (float("nan"),) * 3
    return (c.WorkingSetSize / 2**20, c.PrivateUsage / 2**20,
            c.PeakWorkingSetSize / 2**20)


print("=" * 78)
print("STAGE 9/8 — memory cost of an oversized upload (Day 1 deferral #4)")
print("=" * 78)
base_ws, base_priv, _ = mem()
print(f"backend pid={PID}  size limit={LIMIT_MB} MB")
print(f"baseline: working set {base_ws:.1f} MB, private {base_priv:.1f} MB")

results = []
for size_mb in (20, 60, 150, 400):
    peak_ws = peak_priv = 0.0
    stop = threading.Event()

    def sample():
        global peak_ws, peak_priv
        while not stop.is_set():
            ws, priv, _ = mem()
            peak_ws = max(peak_ws, ws)
            peak_priv = max(peak_priv, priv)
            time.sleep(0.05)

    th = threading.Thread(target=sample, daemon=True)
    th.start()

    payload = b"%PDF-1.4\n" + b"0" * (size_mb * 1024 * 1024 - 9)
    t0 = time.perf_counter()
    try:
        r = requests.post(BASE + "/api/documents/upload",
                          files={"file": ("big.pdf", payload, "application/pdf")},
                          timeout=900)
        status = r.status_code
        detail = r.json().get("detail") if status != 202 else "ACCEPTED"
        if status == 202:
            requests.delete(f"{BASE}/api/documents/{r.json()['document_id']}",
                            timeout=180)
    except Exception as exc:
        status, detail = type(exc).__name__, str(exc)[:70]
    elapsed = time.perf_counter() - t0

    stop.set()
    th.join()
    del payload

    over = "OVER LIMIT" if size_mb > LIMIT_MB else "within limit"
    print(f"\n{size_mb:>4} MB body ({over})")
    print(f"    HTTP {status}   detail={detail!r}")
    print(f"    {elapsed:6.1f}s   peak working set {peak_ws:7.1f} MB "
          f"(+{peak_ws-base_ws:6.1f})   peak private {peak_priv:7.1f} MB "
          f"(+{peak_priv-base_priv:6.1f})")
    time.sleep(5)
    ws, priv, _ = mem()
    print(f"    settled: working set {ws:.1f} MB, private {priv:.1f} MB")
    results.append((size_mb, status, peak_priv - base_priv))

print("\n--- relationship between rejected body size and memory allocated ---")
for size_mb, status, delta in results:
    ratio = delta / size_mb if size_mb else 0
    print(f"    {size_mb:>4} MB -> HTTP {status}, +{delta:7.1f} MB private "
          f"({ratio:.2f}x the body)")

print("\n--- server still healthy? ---")
for p in ("/api/health", "/api/documents"):
    print(f"    GET {p:<18} HTTP {requests.get(BASE + p, timeout=90).status_code}")
