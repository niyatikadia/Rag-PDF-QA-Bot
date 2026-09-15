"""
Day 2 / Stage 8 — where does /api/health's ~2 s actually go?

PDF: "Optimising a component that was never the bottleneck" is listed as a way
performance work goes wrong, so the four checks are timed individually before
anything is changed.

Run from backend/.
"""
import statistics
import time

from app.routers.health import (_check_ollama, _check_chroma,
                                _check_embedding_model, _check_ocr)

N = 10


def bench(label, fn):
    times = []
    for _ in range(N):
        t = time.perf_counter()
        result = fn()
        times.append(time.perf_counter() - t)
    s = sorted(times)
    print(f"  {label:<26} n={N}  p50={statistics.median(s)*1000:8.1f}ms  "
          f"min={s[0]*1000:8.1f}ms  max={s[-1]*1000:8.1f}ms  -> {result}")
    return statistics.median(s)


print("=" * 78)
print("STAGE 8 — /api/health component breakdown")
print("=" * 78)
total = 0.0
total += bench("_check_ollama()", _check_ollama)
total += bench("_check_chroma()", _check_chroma)
total += bench("_check_embedding_model()", _check_embedding_model)
total += bench("_check_ocr()", _check_ocr)
print(f"\n  sum of p50s: {total*1000:.1f} ms")

# _check_ocr is the suspect: pytesseract.get_tesseract_version() shells out to
# the tesseract binary. Confirm that the cost is process spawn, by timing the
# spawn directly.
print("\n--- is it process spawn? ---")
import subprocess
from app.config import TESSERACT_CMD_PATH
exe = TESSERACT_CMD_PATH or "tesseract"
times = []
for _ in range(N):
    t = time.perf_counter()
    subprocess.run([exe, "--version"], capture_output=True)
    times.append(time.perf_counter() - t)
print(f"  subprocess.run(['{exe}', '--version']) "
      f"p50={statistics.median(sorted(times))*1000:.1f}ms over n={N}")

print("\n--- and how fast is the same check when its result is reused? ---")
import pytesseract
t = time.perf_counter()
v = pytesseract.get_tesseract_version()
first = time.perf_counter() - t
t = time.perf_counter()
_ = str(v)
print(f"  first get_tesseract_version(): {first*1000:.1f}ms   "
      f"reading a cached value: {(time.perf_counter()-t)*1000:.4f}ms  (version {v})")
