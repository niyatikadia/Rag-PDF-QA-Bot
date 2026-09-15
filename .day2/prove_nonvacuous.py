"""
Day 2 — prove test_config_validation.py is not vacuous.

Builds a genuine pre-fix app/config.py (plain int() coercion, no _int_env, no
CHUNK_OVERLAP guard) in a temp tree that shadows the real one, runs the new test
module against it, and reports which tests fail. Then does the same against the
fixed file. The real backend/app/config.py is never written to.
"""
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
PY = str(BACKEND / ".venv" / "Scripts" / "python.exe")
FIXED = (BACKEND / "app" / "config.py").read_text(encoding="utf-8")


def make_prefix_config(src: str) -> str:
    """Undo the Day 2 fix textually: restore bare int() and drop the guards."""
    out = re.sub(r'_int_env\(\s*"([A-Z_]+)",\s*"([^"]*)",\s*minimum=\d+\s*\)',
                 r'int(os.getenv("\1", "\2"))', src)
    # Remove the CHUNK_OVERLAP >= CHUNK_SIZE block (if-statement + raise call).
    out = re.sub(r'\nif CHUNK_OVERLAP >= CHUNK_SIZE:\n'
                 r'    raise ConfigurationError\(\n(?:.*\n)*?    \)\n',
                 '\n', out)
    # Remove the _int_env helper definition itself.
    out = re.sub(r'\ndef _int_env\(.*?\n    return value\n', '\n', out,
                 flags=re.DOTALL)
    return out


def run_against(config_text: str, label: str):
    with tempfile.TemporaryDirectory() as tmp:
        tree = Path(tmp) / "backend"
        shutil.copytree(BACKEND, tree,
                        ignore=shutil.ignore_patterns(
                            ".venv", "__pycache__", ".pytest_cache", "data"))
        (tree / "app" / "config.py").write_text(config_text, encoding="utf-8")
        # config.py mkdirs ./data/... relative to cwd, so let it.
        proc = subprocess.run(
            [PY, "-m", "pytest", "tests/test_config_validation.py", "-q",
             "--no-header", "-p", "no:cacheprovider"],
            cwd=tree, capture_output=True, text=True, timeout=600,
            env={"PYTHONPATH": str(tree), "PYTHONIOENCODING": "utf-8",
                 "PATH": __import__("os").environ["PATH"],
                 "SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT", "")},
        )
    tail = [l for l in proc.stdout.strip().splitlines() if l.strip()]
    print(f"\n=== {label} ===")
    for line in tail:
        if line.startswith("FAILED") or "passed" in line or "failed" in line:
            print("   ", line)
    return proc


PREFIX = make_prefix_config(FIXED)
# Assert on the *executable* guard, not on the docstring that describes it —
# the ConfigurationError docstring also contains the text "CHUNK_OVERLAP >=
# CHUNK_SIZE", and matching that made the first version of this check fail
# against a correctly-reconstructed pre-fix file.
assert "_int_env" not in PREFIX, "pre-fix build still calls _int_env"
assert "def _int_env" not in PREFIX, "pre-fix build still defines _int_env"
assert not re.search(r"^if CHUNK_OVERLAP >= CHUNK_SIZE:", PREFIX, re.M), \
    "pre-fix build still has the executable overlap guard"
assert PREFIX.count("int(os.getenv(") == 7, \
    f"expected 7 bare int(os.getenv()) reads, got {PREFIX.count('int(os.getenv(')}"
print("pre-fix reconstruction verified: no _int_env, no executable overlap "
      "guard, 7 bare int(os.getenv()) reads")

run_against(PREFIX, "PRE-FIX config.py (the defect present)")
run_against(FIXED, "FIXED config.py (the defect closed)")
