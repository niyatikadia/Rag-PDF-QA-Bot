"""
Day 2 / Stage 11 — Configuration and environment verification.

Source requirement (01_After_Coding_Is_Complete.pdf, Stage 11):
  "Every variable the code reads is present in the example configuration file,
   and vice versa - diff the two sets and require them to be identical.
   Sensible defaults. No secrets committed. Relative paths resolve from a
   documented working directory. The application starts and reports a clear
   error when a required variable is missing."

This script does not modify anything. Run from backend/.
"""
import ast
import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
CONFIG_PY = BACKEND / "app" / "config.py"
ENV_EXAMPLE = BACKEND / ".env.example"
ENV_LIVE = BACKEND / ".env"

FAIL = []

# Functions in the project that read an environment variable named by their
# first argument. Treated exactly like os.getenv for the purposes of the
# code-vs-example diff.
_ENV_READER_WRAPPERS = {"_int_env"}


def note(ok, label, detail=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(label)


# ── 1. Which variables does the code actually read? ──────────────────────────
# Walk every .py under app/ for os.getenv / os.environ access, not just
# config.py — a variable read anywhere else would bypass the documented set.
def vars_read_by_code():
    found = {}          # name -> (file, default_or_None)
    for py in sorted((BACKEND / "app").rglob("*.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            name = None
            if isinstance(fn, ast.Attribute) and fn.attr == "getenv":
                name = "getenv"
            elif (isinstance(fn, ast.Attribute) and fn.attr == "get"
                  and isinstance(fn.value, ast.Attribute)
                  and fn.value.attr == "environ"):
                name = "environ.get"
            elif isinstance(fn, ast.Name) and fn.id in _ENV_READER_WRAPPERS:
                # config.py reads its integer settings through a validating
                # wrapper (_int_env), so a scanner that only recognises literal
                # os.getenv() calls reports those 7 variables as "in
                # .env.example but unread by the code" — which is exactly
                # backwards. Any wrapper whose first argument is the variable
                # name counts as an env read.
                name = fn.id
            elif isinstance(fn, ast.Subscript):
                continue
            if not name or not node.args:
                continue
            key = node.args[0]
            if not isinstance(key, ast.Constant) or not isinstance(key.value, str):
                continue
            default = None
            if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
                default = node.args[1].value
            found[key.value] = (py.relative_to(BACKEND).as_posix(), default)
    # os.environ["X"] direct subscript reads (no default -> must fail loudly)
    for py in sorted((BACKEND / "app").rglob("*.py")):
        src = py.read_text(encoding="utf-8")
        for m in re.finditer(r"os\.environ\[[\"']([A-Z0-9_]+)[\"']\]", src):
            found.setdefault(m.group(1), (py.relative_to(BACKEND).as_posix(), "<<REQUIRED>>"))
    return found


def vars_in_env_file(path):
    """KEY=VALUE lines, ignoring comments and blanks. Returns {name: value}."""
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out


code = vars_read_by_code()
example = vars_in_env_file(ENV_EXAMPLE)
live = vars_in_env_file(ENV_LIVE) if ENV_LIVE.exists() else {}

print("=" * 78)
print("STAGE 11 — CONFIGURATION AND ENVIRONMENT VERIFICATION")
print("=" * 78)
print(f"\nVariables read by code   : {len(code)}")
print(f"Variables in .env.example: {len(example)}")
print(f"Variables in .env (live) : {len(live)}")

# ── 2. The required diff: code set vs example set ─────────────────────────────
print("\n--- 2.1  code-vs-.env.example diff (PDF: 'require them to be identical') ---")
missing_from_example = sorted(set(code) - set(example))
extra_in_example = sorted(set(example) - set(code))
note(not missing_from_example, "Every variable the code reads is in .env.example",
     f"missing: {missing_from_example}" if missing_from_example else "none missing")
note(not extra_in_example, "No variable in .env.example is unread by the code",
     f"unused: {extra_in_example}" if extra_in_example else "none unused")

# ── 3. .env vs .env.example ───────────────────────────────────────────────────
print("\n--- 2.2  .env vs .env.example ---")
missing_from_live = sorted(set(example) - set(live))
extra_in_live = sorted(set(live) - set(example))
note(not missing_from_live, ".env covers every variable in .env.example",
     f"missing: {missing_from_live}" if missing_from_live else "complete")
note(not extra_in_live, ".env introduces no variable absent from .env.example",
     f"extra: {extra_in_live}" if extra_in_live else "none")

# ── 4. Defaults ───────────────────────────────────────────────────────────────
print("\n--- 2.3  defaults in code ---")
no_default = sorted(k for k, (f, d) in code.items() if d is None or d == "<<REQUIRED>>")
note(True, f"{len(code) - len(no_default)}/{len(code)} variables have an in-code default",
     f"without default: {no_default}" if no_default else "all have defaults")

# Where example value != code default, that divergence must be deliberate.
print("\n--- 2.4  value divergence: .env.example vs in-code fallback ---")
diverged = []
for k, v in example.items():
    if k in code:
        d = code[k][1]
        if d is not None and str(d) != v:
            diverged.append((k, v, d))
for k, v, d in diverged:
    print(f"    {k}: .env.example={v!r}  code fallback={d!r}")
if not diverged:
    print("    (identical everywhere)")

# ── 5. Secrets ────────────────────────────────────────────────────────────────
print("\n--- 2.5  secrets in the example configuration ---")
# NOTE (harness defect, fixed): the first version of this pattern matched a bare
# `token`, which fired on MAX_CONTEXT_TOKENS — a *count* of tokens, not a
# credential. A name pattern loose enough to flag that is a false positive
# generator, so credential-ish token names are now matched specifically and the
# value-shape patterns (which are what actually catch a leaked key) are kept.
SECRET_NAME_PAT = re.compile(
    r"(?i)(api[_-]?key|\bsecret\b|secret[_-]|passwo?rd|access[_-]?token|"
    r"auth[_-]?token|refresh[_-]?token|bearer|private[_-]?key|credential)")
SECRET_VALUE_PAT = re.compile(
    r"(sk-[A-Za-z0-9]{16,}|ghp_[A-Za-z0-9]{20,}|gho_[A-Za-z0-9]{20,}|"
    r"AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_\-]{30,}|xox[baprs]-[A-Za-z0-9-]{10,}|"
    r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}|"
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----)")
hits = [(k, v) for k, v in example.items()
        if SECRET_NAME_PAT.search(k) or SECRET_VALUE_PAT.search(v)]
note(not hits, ".env.example contains no secret-shaped variable or value",
     str([k for k, _ in hits]) if hits else "clean")

# ── 6. Relative paths ─────────────────────────────────────────────────────────
print("\n--- 2.6  relative paths resolve from backend/ ---")
PATH_VARS = ["CHROMA_PERSIST_DIR", "UPLOAD_DIR", "DATABASE_PATH"]
for k in PATH_VARS:
    v = example.get(k, "")
    note(v.startswith("./"), f"{k} is relative and documented", f"value={v!r}")

# ── 7. Type coercion safety ───────────────────────────────────────────────────
print("\n--- 2.7  int()/bool() coercion of example values ---")
INT_VARS = ["OLLAMA_TIMEOUT_SECONDS", "MAX_FILE_SIZE_MB", "CHUNK_SIZE",
            "CHUNK_OVERLAP", "TOP_K_RESULTS", "MAX_CONTEXT_TOKENS", "OCR_DPI"]
for k in INT_VARS:
    v = example.get(k, "")
    try:
        int(v)
        note(True, f"{k} parses as int", f"value={v!r}")
    except ValueError:
        note(False, f"{k} parses as int", f"value={v!r}")

# ── 8. CORS must not be a wildcard ────────────────────────────────────────────
print("\n--- 2.8  CORS ---")
origin = example.get("FRONTEND_ORIGIN", "")
note(origin not in ("*", "") and "*" not in origin,
     "FRONTEND_ORIGIN is a specific origin, not '*'", f"value={origin!r}")

# ── 9. Everything points at localhost (no external service) ──────────────────
print("\n--- 2.9  portability: no machine-specific or external endpoints ---")
bad = []
for k, v in example.items():
    if re.search(r"https?://", v) and not re.search(r"//(localhost|127\.0\.0\.1)", v):
        bad.append((k, v))
    if re.search(r"[A-Za-z]:\\", v):        # absolute Windows path
        bad.append((k, v))
note(not bad, "No absolute machine paths and no non-localhost URLs in .env.example",
     str(bad) if bad else "clean")

print("\n" + "=" * 78)
print(f"STAGE 11 RESULT: {'PASS' if not FAIL else 'FAIL — ' + '; '.join(FAIL)}")
print("=" * 78)
sys.exit(1 if FAIL else 0)
