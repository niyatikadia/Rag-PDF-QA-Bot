"""
Day 2 / Stage 11 (behavioural half).

PDF requirement: "The application starts and reports a clear error when a
required variable is missing, instead of failing mysteriously later" and
"A copy of the example config, unedited, produces a working system".

Each case below imports app.config in a FRESH subprocess with a controlled
environment, so nothing leaks between cases and the live backend/.env is never
touched. Run from backend/.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
PY = str(BACKEND / ".venv" / "Scripts" / "python.exe")
EXAMPLE = BACKEND / ".env.example"

PROBE = (
    "import app.config as c; "
    "print('LOADED', c.OLLAMA_MODEL, c.CHUNK_SIZE, c.CHUNK_OVERLAP, "
    "c.MAX_FILE_SIZE_MB, c.TOP_K_RESULTS, c.FRONTEND_ORIGIN)"
)

CONFIG_KEYS = [
    "OLLAMA_BASE_URL", "OLLAMA_MODEL", "OLLAMA_TIMEOUT_SECONDS",
    "EMBEDDING_MODEL", "CHROMA_PERSIST_DIR", "UPLOAD_DIR", "MAX_FILE_SIZE_MB",
    "CHUNK_SIZE", "CHUNK_OVERLAP", "TOP_K_RESULTS", "MAX_CONTEXT_TOKENS",
    "FRONTEND_ORIGIN", "DATABASE_PATH", "OCR_ENABLED", "OCR_LANGUAGE",
    "OCR_DPI", "TESSERACT_CMD_PATH",
]


def run_case(label, env_file_text, extra_env=None, expect="start"):
    """
    Import app.config in a temp working directory containing env_file_text as
    its .env, with every CONFIG_KEY scrubbed from the inherited environment so
    only the file under test is in play.
    """
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        if env_file_text is not None:
            (tmp / ".env").write_text(env_file_text, encoding="utf-8")

        env = {k: v for k, v in os.environ.items() if k not in CONFIG_KEYS}
        env["PYTHONPATH"] = str(BACKEND)
        env["PYTHONIOENCODING"] = "utf-8"
        if extra_env:
            env.update(extra_env)

        proc = subprocess.run([PY, "-c", PROBE], cwd=tmp, env=env,
                              capture_output=True, text=True, timeout=180)

    started = proc.returncode == 0 and "LOADED" in proc.stdout
    ok = started if expect == "start" else (not started)
    print(f"\n[{'PASS' if ok else 'FAIL'}] {label}")
    print(f"        expected: {'starts cleanly' if expect == 'start' else 'fails'}"
          f"   actual: {'started' if started else f'exit {proc.returncode}'}")
    if started:
        print(f"        {proc.stdout.strip()}")
    else:
        err = [l for l in proc.stderr.strip().splitlines() if l.strip()]
        for line in err[-4:]:
            print(f"        stderr| {line}")
    # Report which directories the import created — config.py mkdirs at import.
    return ok, proc


results = []
print("=" * 78)
print("STAGE 11 (behaviour) — missing / malformed / unedited configuration")
print("=" * 78)

example_text = EXAMPLE.read_text(encoding="utf-8")

# C1 — the PDF's headline requirement: unedited example config works.
results.append(run_case(
    "C1  Unedited .env.example, copied as .env, in an empty directory",
    example_text, expect="start"))

# C2 — no .env at all: every variable falls back to its in-code default.
results.append(run_case(
    "C2  No .env file whatsoever (pure in-code defaults)",
    None, expect="start"))

# C3 — an empty .env: file present, nothing in it.
results.append(run_case(
    "C3  Empty .env (present but zero variables)",
    "", expect="start"))

# C4 — one variable removed. There are no *required* variables by design, so a
#      missing one must fall back, not crash.
partial = "\n".join(l for l in example_text.splitlines()
                    if not l.startswith("OLLAMA_MODEL="))
results.append(run_case(
    "C4  .env with OLLAMA_MODEL removed (falls back to code default)",
    partial, expect="start"))

# C5-C7 — malformed values. int() at import time is where a bad value lands.
for key, bad in [("CHUNK_SIZE", "five-hundred"),
                 ("OCR_DPI", "3OO"),
                 ("MAX_FILE_SIZE_MB", "")]:
    text = "\n".join(
        (f"{key}={bad}" if l.startswith(f"{key}=") else l)
        for l in example_text.splitlines())
    results.append(run_case(
        f"C  .env with {key}={bad!r} (non-numeric)",
        text, expect="fail"))

# C8 — out-of-range but type-valid values: CHUNK_OVERLAP >= CHUNK_SIZE is
#      nonsense for the splitter. Does config.py notice?
#
#      This case is the Day 2 CONFIG-1 defect. Before the fix it STARTED
#      cleanly, and every subsequent upload then failed during ingestion with a
#      ValueError raised inside langchain_text_splitters. The expectation is now
#      "fail", at startup, naming the two variables — so this case flips from
#      start to fail across the fix and is the behavioural proof of it.
text = example_text.replace("CHUNK_SIZE=500", "CHUNK_SIZE=100") \
                   .replace("CHUNK_OVERLAP=100", "CHUNK_OVERLAP=500")
ok, proc = run_case(
    "C8  CHUNK_OVERLAP(500) > CHUNK_SIZE(100) — rejected at startup (CONFIG-1)",
    text, expect="fail")
results.append((ok, proc))

# C10 — range floors on the other numeric settings, same defect class.
for key, bad in [("TOP_K_RESULTS", "0"), ("MAX_FILE_SIZE_MB", "0"),
                 ("OCR_DPI", "0")]:
    text = "\n".join(
        (f"{key}={bad}" if l.startswith(f"{key}=") else l)
        for l in example_text.splitlines())
    results.append(run_case(
        f"C10 .env with {key}={bad} — rejected at startup (CONFIG-1)",
        text, expect="fail"))

# C9 — environment variable overrides the file (12-factor precedence).
results.append(run_case(
    "C9  Process env overrides .env  (OLLAMA_MODEL=env-wins)",
    example_text, extra_env={"OLLAMA_MODEL": "env-wins"}, expect="start"))

passed = sum(1 for ok, _ in results if ok)
print("\n" + "=" * 78)
print(f"STAGE 11 (behaviour): {passed}/{len(results)} cases as expected")
print("=" * 78)
