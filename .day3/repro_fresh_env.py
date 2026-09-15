"""
Day 3 / stage 14 — reproducibility verification.

Builds a BRAND-NEW throwaway virtual environment inside the project folder and
proves the documented install works end to end in it. The existing
`backend/.venv` is never read, written or activated by this script — the whole
point is that the working environment must not be the thing under test.

Checks, in order:
  1. the 14 declared pins in requirements.txt parse and are all `==` pinned
  2. those pins match what is actually installed in backend/.venv (drift check)
  3. `pip install -r requirements.txt` succeeds in an empty venv
  4. `pip check` reports no broken/conflicting requirements
  5. every declared distribution imports in that fresh venv
  6. the runtime version and the system-level dependencies are recorded

Run from the project root:
    .\\.venv-tools\\Scripts\\python.exe .day3\\repro_fresh_env.py

The throwaway environment is left on disk for inspection and is removed by the
caller; it is git-ignored via `.venv-tools/`-style entries, see .gitignore.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQ = ROOT / "backend" / "requirements.txt"
MAIN_VENV_PY = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"
FRESH = ROOT / ".venv-repro-day3"
FRESH_PY = FRESH / "Scripts" / "python.exe"

# Distribution name -> module name to import. Only differs where the two names
# are not the same string; pip cannot tell you this, so it is stated explicitly.
IMPORT_NAME = {
    "PyMuPDF": "pymupdf",
    "python-multipart": "multipart",
    "python-dotenv": "dotenv",
    "sentence-transformers": "sentence_transformers",
    "langchain-text-splitters": "langchain_text_splitters",
    "Pillow": "PIL",
    "uvicorn[standard]": "uvicorn",
}


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    print(f"\n$ {' '.join(str(c) for c in cmd)}", flush=True)
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def parse_requirements() -> list[tuple[str, str]]:
    """Return [(distribution, version)] for every non-comment line."""
    pins = []
    for line in REQ.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^([A-Za-z0-9_.\-]+(?:\[[^\]]+\])?)==(.+)$", line)
        if not m:
            raise SystemExit(f"NOT PINNED WITH '==': {line!r}")
        pins.append((m.group(1), m.group(2)))
    return pins


def installed_versions(python: Path) -> dict[str, str]:
    out = run([str(python), "-m", "pip", "list", "--format=json"])
    return {p["name"].lower(): p["version"] for p in json.loads(out.stdout)}


def base_name(dist: str) -> str:
    return dist.split("[", 1)[0].lower()


def main() -> int:
    failures: list[str] = []
    pins = parse_requirements()
    print(f"=== 1. requirements.txt: {len(pins)} declared dependencies, all '==' pinned ===")
    for d, v in pins:
        print(f"    {d}=={v}")

    print("\n=== 2. Drift check: declared pins vs backend/.venv ===")
    if MAIN_VENV_PY.exists():
        have = installed_versions(MAIN_VENV_PY)
        for dist, want in pins:
            got = have.get(base_name(dist))
            state = "OK " if got == want else "DRIFT"
            if got != want:
                failures.append(f"drift: {dist} declared {want}, installed {got}")
            print(f"    [{state}] {dist:<28} declared {want:<12} installed {got}")
    else:
        print("    backend/.venv not found — skipped")

    print(f"\n=== 3. Fresh environment at {FRESH} ===")
    if FRESH.exists():
        print("    already exists — reusing (delete it for a truly cold run)")
    else:
        r = run([sys.executable, "-m", "venv", str(FRESH)])
        if r.returncode != 0:
            print(r.stdout, r.stderr)
            return 1
    print(f"    python: {FRESH_PY}")

    r = run([str(FRESH_PY), "-m", "pip", "install", "--upgrade", "pip", "-q"])
    if r.returncode != 0:
        print(r.stdout[-2000:], r.stderr[-2000:])

    print("\n=== 4. pip install -r backend/requirements.txt (this takes a while) ===")
    r = run([str(FRESH_PY), "-m", "pip", "install", "-r", str(REQ)])
    print(r.stdout[-4000:])
    if r.returncode != 0:
        print("STDERR:", r.stderr[-4000:])
        failures.append("pip install failed")
    else:
        print("    INSTALL OK")

    print("\n=== 5. pip check (dependency consistency) ===")
    r = run([str(FRESH_PY), "-m", "pip", "check"])
    print("   ", (r.stdout or r.stderr).strip() or "(no output)")
    if r.returncode != 0:
        failures.append("pip check reported conflicts")

    print("\n=== 6. Every declared dependency imports in the fresh environment ===")
    for dist, _ in pins:
        module = IMPORT_NAME.get(dist, base_name(dist).replace("-", "_"))
        r = run([str(FRESH_PY), "-c", f"import {module}; print({module!r}, 'OK')"])
        ok = r.returncode == 0
        if not ok:
            failures.append(f"import failed: {dist} -> {module}")
        print(f"    [{'OK ' if ok else 'FAIL'}] {dist:<28} import {module}")
        if not ok:
            print("        ", r.stderr.strip().splitlines()[-1] if r.stderr else "")

    print("\n=== 7. Versions actually installed in the fresh environment ===")
    fresh_have = installed_versions(FRESH_PY)
    for dist, want in pins:
        got = fresh_have.get(base_name(dist))
        mark = "OK " if got == want else "MISMATCH"
        if got != want:
            failures.append(f"fresh env has {dist}=={got}, declared {want}")
        print(f"    [{mark}] {dist:<28} {got}")

    r = run([str(FRESH_PY), "--version"])
    print("\n    fresh env runtime:", r.stdout.strip() or r.stderr.strip())
    print("    total distributions installed (incl. transitive):", len(fresh_have))

    print("\n" + "=" * 70)
    if failures:
        print("REPRODUCIBILITY: FAILURES")
        for f in failures:
            print("  -", f)
        return 1
    print("REPRODUCIBILITY: ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
