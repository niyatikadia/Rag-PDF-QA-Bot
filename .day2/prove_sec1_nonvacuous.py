"""
Day 2 — prove the SEC-1 tests are not vacuous.

Rebuilds a pre-fix llm_service.py (the digit-length guard removed, everything
else byte-identical) in a temp tree that shadows the real one, and runs the SEC-1
tests against it. The real backend/app/services/llm_service.py is never written.
"""
import re
import shutil
import subprocess
import os
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
PY = str(BACKEND / ".venv" / "Scripts" / "python.exe")
TARGET = BACKEND / "app" / "services" / "llm_service.py"
FIXED = TARGET.read_text(encoding="utf-8")

GUARD = re.compile(
    r"pages\.update\(int\(n\) for n in re\.findall\(r\"\\d\+\", run\)\s*\n"
    r"\s*if len\(n\) <= _MAX_PAGE_NUMBER_DIGITS\)")

PREFIX = GUARD.sub('pages.update(int(n) for n in re.findall(r"\\\\d+", run))', FIXED)

assert PREFIX != FIXED, "the guard pattern did not match — nothing was reverted"
assert "_MAX_PAGE_NUMBER_DIGITS)" not in PREFIX.split("def _mentioned_pages")[1], \
    "the guard is still applied inside _mentioned_pages"
print("pre-fix reconstruction verified: the digit-length guard is gone from "
      "_mentioned_pages()")
print("  pre-fix line:",
      [l.strip() for l in PREFIX.splitlines() if "pages.update" in l])
print("  fixed  lines:",
      [l.strip() for l in FIXED.splitlines() if "pages.update" in l
       or "_MAX_PAGE_NUMBER_DIGITS)" in l])


def run_against(text, label):
    with tempfile.TemporaryDirectory() as tmp:
        tree = Path(tmp) / "backend"
        shutil.copytree(BACKEND, tree, ignore=shutil.ignore_patterns(
            ".venv", "__pycache__", ".pytest_cache", "data"))
        (tree / "app" / "services" / "llm_service.py").write_text(
            text, encoding="utf-8")
        proc = subprocess.run(
            [PY, "-m", "pytest", "tests/test_llm_service.py", "-q", "--no-header",
             "-p", "no:cacheprovider", "-k", "digit or six_digit", "--tb=line"],
            cwd=tree, capture_output=True, text=True, timeout=600,
            env={"PYTHONPATH": str(tree), "PYTHONIOENCODING": "utf-8",
                 "PATH": os.environ["PATH"],
                 "SYSTEMROOT": os.environ.get("SYSTEMROOT", "")})
    print(f"\n=== {label} ===")
    for line in proc.stdout.strip().splitlines():
        if ("passed" in line or "failed" in line or line.startswith("FAILED")
                or "ValueError" in line):
            print("   ", line.strip()[:150])


run_against(PREFIX, "PRE-FIX llm_service.py (SEC-1 present)")
run_against(FIXED, "FIXED llm_service.py (SEC-1 closed)")
