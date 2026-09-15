"""
Day 2 — prove the PERF-3 tests are not vacuous.

Rebuilds the pre-fix documents.py in a temp tree: _read_within_limit() reverted
to the original shape (read the WHOLE body, then check its size), with the same
name and signature so the tests still target it. The real file is never written.
"""
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
PY = str(BACKEND / ".venv" / "Scripts" / "python.exe")
TARGET = BACKEND / "app" / "routers" / "documents.py"
FIXED = TARGET.read_text(encoding="utf-8")

# The original logic, restored behind the new name/signature: buffer everything
# first, then judge it. This is exactly what the handler did before Day 2.
PREFIX_BODY = '''async def _read_within_limit(file: UploadFile) -> bytes:
    """PRE-FIX RECONSTRUCTION: read the whole body, then check the size."""
    content = await file.read()
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File exceeds the {MAX_FILE_SIZE_BYTES // (1024*1024)} MB limit.",
        )
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )
    return content
'''

# Replace from the def line up to (not including) the next top-level decorator.
pattern = re.compile(
    r"async def _read_within_limit\(file: UploadFile\) -> bytes:\n(?:.*?\n)*?"
    r"    return b\"\"\.join\(chunks\)\n")
PREFIX = pattern.sub(PREFIX_BODY, FIXED)

assert PREFIX != FIXED, "pre-fix substitution did not match anything"
assert 'b"".join(chunks)' not in PREFIX, "chunked reader still present"
assert "PRE-FIX RECONSTRUCTION" in PREFIX
print("pre-fix reconstruction verified: _read_within_limit() buffers the whole "
      "body before checking its size")


def run_against(text, label):
    with tempfile.TemporaryDirectory() as tmp:
        tree = Path(tmp) / "backend"
        shutil.copytree(BACKEND, tree, ignore=shutil.ignore_patterns(
            ".venv", "__pycache__", ".pytest_cache", "data"))
        (tree / "app" / "routers" / "documents.py").write_text(text, encoding="utf-8")
        proc = subprocess.run(
            [PY, "-m", "pytest", "tests/test_api.py", "-q", "--no-header",
             "-p", "no:cacheprovider", "--tb=line",
             "-k", "oversized or chunked or within_the_limit or non_pdf"],
            cwd=tree, capture_output=True, text=True, timeout=900,
            env={"PYTHONPATH": str(tree), "PYTHONIOENCODING": "utf-8",
                 "PATH": os.environ["PATH"],
                 "SYSTEMROOT": os.environ.get("SYSTEMROOT", "")})
    print(f"\n=== {label} ===")
    for line in proc.stdout.strip().splitlines():
        s = line.strip()
        if (s.startswith("FAILED") or "passed" in s or "failed" in s
                or "bytes of a" in s or "Day 2 PERF-3" in s):
            print("   ", s[:200])


run_against(PREFIX, "PRE-FIX documents.py (PERF-3 present)")
run_against(FIXED, "FIXED documents.py (PERF-3 closed)")
