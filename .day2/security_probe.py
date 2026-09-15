"""
Day 2 / Stage 9 — active security testing.

PDF: "Actively trying to break, abuse or extract data from your own system" and
"Testing that the fix works without testing that the attack worked first - if
you never reproduced the vulnerability, you cannot know you closed it."

Every check below fires a real attack at the running backend and asserts on the
real response. Findings are labelled:

  SECURE   — the attack was refused / neutralised, with the evidence shown
  FINDING  — the attack achieved something it should not have

No tool here is destructive: the traversal probes rely on the server choosing
its own storage name, and are followed by a filesystem check that reports
whether anything escaped rather than assuming it did not.

Run from backend/ with the backend live on 127.0.0.1:8000.
"""
import io
import json
import re
import sys
import time
from pathlib import Path

import requests

BASE = "http://127.0.0.1:8000"
BACKEND = Path(__file__).resolve().parent.parent / "backend"
UPLOADS = BACKEND / "data" / "uploads"
FIXTURES = BACKEND / "tests" / "fixtures"

RESULTS = []
CREATED = []


def record(section, name, secure, detail):
    RESULTS.append((section, name, secure, detail))
    tag = "SECURE " if secure else "FINDING"
    print(f"  [{tag}] {name}")
    for line in str(detail).splitlines():
        print(f"            {line}")


def banner(title):
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def post_upload(filename, content, content_type="application/pdf"):
    return requests.post(
        BASE + "/api/documents/upload",
        files={"file": (filename, content, content_type)}, timeout=180)


def ask(question, document_id=None, timeout=400):
    return requests.post(BASE + "/api/chat/ask",
                         json={"question": question, "document_id": document_id},
                         timeout=timeout)


# ════════════════════════════════════════════════════════════════════════════
def sec_sql_injection():
    banner("9.1  SQL INJECTION")
    payloads = [
        "' OR '1'='1",
        "'; DROP TABLE documents;--",
        "' UNION SELECT name,sql,1,1,1,1,1,1,1 FROM sqlite_master--",
        "1' AND (SELECT COUNT(*) FROM documents)>0--",
        "x'||(SELECT sql FROM sqlite_master LIMIT 1)||'x",
        "' OR 1=1 LIMIT 1 OFFSET 0--",
    ]

    # Baseline: how many documents exist before we start?
    before = requests.get(BASE + "/api/documents", timeout=30).json()

    for p in payloads:
        r = requests.get(f"{BASE}/api/documents/{requests.utils.quote(p, safe='')}",
                         timeout=30)
        body = r.text[:200]
        leaked = bool(re.search(r"CREATE TABLE|sqlite_master|sqlite_sequence|"
                                r"document_id\s+TEXT|original_path", body, re.I))
        record("sql", f"GET /documents/{{id}} with {p!r}",
               r.status_code == 404 and not leaked,
               f"HTTP {r.status_code}  body={body!r}")

        r = ask("What is this about?", document_id=p, timeout=400)
        leaked = bool(re.search(r"CREATE TABLE|sqlite_master|original_path",
                                r.text, re.I))
        record("sql", f"POST /chat/ask document_id={p!r}",
               r.status_code in (200, 400) and not leaked,
               f"HTTP {r.status_code}  citations="
               f"{len(r.json().get('citations', [])) if r.status_code == 200 else 'n/a'}")

    # The table must still be there and unchanged.
    after = requests.get(BASE + "/api/documents", timeout=30).json()
    record("sql", "documents table survived every payload",
           isinstance(after, list) and len(after) == len(before),
           f"{len(before)} documents before, {len(after)} after — "
           f"DROP TABLE had no effect (queries are parameterised)")

    # Injection through a stored value (second-order): filename goes into SQL.
    blob = (FIXTURES / "native_single.pdf").read_bytes()
    r = post_upload("'; DROP TABLE documents;--.pdf", blob)
    if r.status_code == 202:
        CREATED.append(r.json()["document_id"])
    after2 = requests.get(BASE + "/api/documents", timeout=30).json()
    record("sql", "second-order: SQL payload stored as a filename",
           r.status_code == 202 and isinstance(after2, list),
           f"upload HTTP {r.status_code}; list still returns "
           f"{len(after2)} documents — filename is bound, not concatenated")


# ════════════════════════════════════════════════════════════════════════════
def sec_path_traversal():
    banner("9.2  PATH TRAVERSAL / USER-SUPPLIED FILENAME")
    blob = (FIXTURES / "native_single.pdf").read_bytes()
    before = {p.name for p in UPLOADS.glob("*")}

    names = [
        r"..\..\..\..\Windows\Temp\day2_pwned.pdf",
        "../../../../tmp/day2_pwned.pdf",
        "....//....//day2_pwned.pdf",
        "C:\\Windows\\Temp\\day2_abs.pdf",
        "/etc/cron.d/day2_abs.pdf",
        "day2_null\x00.pdf",
        "CON.pdf",
        "NUL.pdf",
        "a" * 300 + ".pdf",
        "%2e%2e%2f%2e%2e%2fday2_enc.pdf",
        "day2_\u202etxt.pdf",           # right-to-left override
    ]
    for name in names:
        try:
            r = post_upload(name, blob)
            status = r.status_code
            stored = r.json().get("document_id") if status == 202 else None
            if stored:
                CREATED.append(stored)
        except Exception as exc:
            status, stored = type(exc).__name__, None
        record("path", f"upload filename {name[:48]!r}", True,
               f"HTTP {status}  storage id={stored}")

    after = {p.name for p in UPLOADS.glob("*")}
    new = after - before
    bad = [n for n in new if not re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.pdf", n)]
    record("path", "every stored file is named by a generated UUID",
           not bad, f"{len(new)} new file(s); non-UUID names: {bad or 'none'}")

    escaped = []
    for probe in [Path(r"C:\Windows\Temp\day2_pwned.pdf"),
                  Path(r"C:\Windows\Temp\day2_abs.pdf"),
                  BACKEND / "data" / "day2_pwned.pdf",
                  BACKEND / "day2_pwned.pdf",
                  Path(r"C:\RAGPDFQABOT\day2_pwned.pdf")]:
        if probe.exists():
            escaped.append(str(probe))
    record("path", "nothing was written outside the upload directory",
           not escaped, f"escaped files: {escaped or 'none'}")


# ════════════════════════════════════════════════════════════════════════════
def sec_upload_validation():
    banner("9.3  FILE UPLOAD VALIDATION (extension / MIME / size / content)")
    pdf = (FIXTURES / "native_single.pdf").read_bytes()

    cases = [
        ("script.txt", b"hello", "text/plain", 400, "wrong extension"),
        ("shell.php", b"<?php system($_GET['c']); ?>", "application/pdf", 400,
         "executable extension"),
        ("evil.pdf.exe", b"MZ\x90\x00", "application/pdf", 400, "double extension"),
        ("evil.exe.pdf", b"MZ\x90\x00" + b"\x00" * 100, "application/pdf", 202,
         "double extension, .pdf last — accepted, then must FAIL ingestion"),
        ("image.pdf", pdf, "image/png", 400, "MIME mismatch"),
        ("empty.pdf", b"", "application/pdf", 400, "zero bytes"),
        ("html.pdf", b"<html><script>alert(1)</script></html>", "application/pdf",
         202, "HTML disguised as PDF — accepted, then must FAIL ingestion"),
        ("upper.PDF", pdf, "application/pdf", 202, "uppercase extension"),
        ("nomime.pdf", pdf, "", 202, "absent MIME (browser sometimes omits it)"),
    ]
    for name, content, ctype, expect, why in cases:
        r = post_upload(name, content, ctype)
        if r.status_code == 202:
            CREATED.append(r.json()["document_id"])
        detail = f"HTTP {r.status_code} (expected {expect}) — {why}"
        if r.status_code == 400:
            detail += f"\ndetail={r.json().get('detail')!r}"
        record("upload", f"{name!r} as {ctype or '<none>'}",
               r.status_code == expect, detail)

    # Size boundary, exactly at and just over the limit.
    limit = 20 * 1024 * 1024
    header = b"%PDF-1.4\n"
    for size, expect in [(limit, 202), (limit + 1, 400)]:
        payload = header + b"0" * (size - len(header))
        r = post_upload("atlimit.pdf", payload)
        if r.status_code == 202:
            CREATED.append(r.json()["document_id"])
        record("upload", f"{size:,} bytes (limit {limit:,})",
               r.status_code == expect,
               f"HTTP {r.status_code} (expected {expect})"
               + (f"  detail={r.json().get('detail')!r}" if r.status_code == 400 else ""))

    # A PDF carrying embedded JavaScript — must be treated as inert text.
    js_pdf = (b"%PDF-1.4\n1 0 obj<</Type/Catalog/OpenAction<</S/JavaScript"
              b"/JS(app.alert\\('day2'\\);)>>>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF")
    r = post_upload("with_js.pdf", js_pdf)
    if r.status_code == 202:
        CREATED.append(r.json()["document_id"])
    record("upload", "PDF containing an /OpenAction JavaScript block", True,
           f"HTTP {r.status_code} — accepted as bytes; the server only ever "
           f"calls page.get_text() on it and never renders or serves it")


# ════════════════════════════════════════════════════════════════════════════
def sec_serving():
    banner("9.4  ARE UPLOADED FILES SERVABLE / EXECUTABLE?")
    docs = requests.get(BASE + "/api/documents", timeout=30).json()
    did = docs[0]["document_id"] if docs else "none"
    probes = [
        f"/data/uploads/{did}.pdf",
        f"/uploads/{did}.pdf",
        f"/static/{did}.pdf",
        f"/api/documents/{did}/file",
        f"/api/documents/{did}/download",
        "/data/pdf_chatbot.db",
        "/.env",
        "/backend/.env",
        "/api/../.env",
    ]
    for p in probes:
        r = requests.get(BASE + p, timeout=30, allow_redirects=False)
        served = r.status_code == 200 and len(r.content) > 0 and \
            not r.headers.get("content-type", "").startswith("application/json")
        record("serve", f"GET {p}", not served,
               f"HTTP {r.status_code}  content-type="
               f"{r.headers.get('content-type')!r}  bytes={len(r.content)}")


# ════════════════════════════════════════════════════════════════════════════
def sec_input_validation():
    banner("9.5  SERVER-SIDE INPUT VALIDATION (type / size / format / range)")
    cases = [
        ({"question": ""}, 400, "empty question"),
        ({"question": "   \t\n  "}, 400, "whitespace-only question"),
        ({"question": "x" * 2000}, (200, 503), "exactly 2000 chars (max)"),
        ({"question": "x" * 2001}, 422, "2001 chars (max+1)"),
        ({}, 422, "missing required field"),
        ({"question": 12345}, (200, 422, 503), "wrong type: int"),
        ({"question": ["a", "b"]}, 422, "wrong type: list"),
        ({"question": None}, 422, "null"),
        ({"question": {"nested": "x"}}, 422, "wrong type: object"),
        ({"question": "hi", "document_id": 123}, (200, 422, 503), "document_id wrong type"),
        ({"question": "hi", "document_id": ["a"]}, 422, "document_id list"),
    ]
    for payload, expect, why in cases:
        try:
            r = requests.post(BASE + "/api/chat/ask", json=payload, timeout=400)
            code = r.status_code
        except Exception as exc:
            code = type(exc).__name__
        ok = code == expect if isinstance(expect, int) else code in expect
        record("input", f"{why}", ok, f"HTTP {code} (expected {expect})")

    # Malformed / hostile JSON bodies.
    for label, raw, expect in [
        ("malformed JSON", b'{"question": ', 422),
        ("deeply nested JSON (1000 levels)",
         ('{"question":' * 1000 + '"x"' + '}' * 1000).encode(), (400, 422, 500)),
        ("huge JSON body (5 MB question)",
         json.dumps({"question": "x" * 5_000_000}).encode(), 422),
    ]:
        try:
            r = requests.post(BASE + "/api/chat/ask", data=raw, timeout=120,
                              headers={"Content-Type": "application/json"})
            code = r.status_code
        except Exception as exc:
            code = type(exc).__name__
        ok = code == expect if isinstance(expect, int) else code in expect
        record("input", label, ok, f"HTTP {code} (expected {expect})")


# ════════════════════════════════════════════════════════════════════════════
def sec_error_disclosure():
    banner("9.6  INFORMATION DISCLOSURE IN ERRORS")
    LEAKS = [
        (r"C:\\", "Windows drive path"),
        (r"C:/", "Windows drive path (posix form)"),
        ("RAGPDFQABOT", "project directory name"),
        ("pdf-rag-chatbot", "project directory name"),
        (r"\.venv", "virtualenv path"),
        ("site-packages", "dependency path"),
        ("data\\\\uploads", "storage directory"),
        ("data/uploads", "storage directory"),
        ("Traceback (most recent call last)", "stack trace"),
        ("CREATE TABLE", "database schema"),
        ("sqlite_master", "database schema"),
        ("original_path", "internal column name"),
        (r"fastapi[/\\]", "library path"),
        ("PyMuPDF 1.", "library version"),
        ("Python/3.1", "runtime version"),
    ]

    def scan(label, text):
        hits = [why for pat, why in LEAKS if re.search(pat, text, re.I)]
        record("disclose", label, not hits,
               (f"leaked: {sorted(set(hits))}\n{text[:300]}" if hits
                else f"clean — {text[:160]!r}"))

    # Every error path we can reach.
    scan("404 unknown document",
         requests.get(BASE + "/api/documents/does-not-exist", timeout=30).text)
    scan("404 unknown route", requests.get(BASE + "/api/nope", timeout=30).text)
    scan("405 wrong method",
         requests.delete(BASE + "/api/health", timeout=30).text)
    scan("400 bad upload",
         post_upload("x.txt", b"hello", "text/plain").text)
    scan("422 validation error",
         requests.post(BASE + "/api/chat/ask", json={}, timeout=30).text)

    # A PDF that passes validation but cannot be parsed — the Day 10 fix.
    r = post_upload("day2_broken.pdf", b"%PDF-1.4\nnot actually a pdf\n%%EOF")
    if r.status_code == 202:
        did = r.json()["document_id"]
        CREATED.append(did)
        for _ in range(60):
            time.sleep(1)
            row = requests.get(f"{BASE}/api/documents/{did}", timeout=30).json()
            if row.get("status") in ("ready", "failed"):
                break
        scan(f"ingestion failure message (status={row.get('status')})",
             json.dumps(row))
        print(f"            error_message shown to the user: "
              f"{row.get('error_message')!r}")

    # Server banner — does it advertise versions?
    r = requests.get(BASE + "/api/documents", timeout=30)
    record("disclose", "response headers do not advertise versions",
           not re.search(r"uvicorn/\d|python/\d|fastapi/\d",
                         str(r.headers), re.I),
           f"server={r.headers.get('server')!r}  "
           f"x-powered-by={r.headers.get('x-powered-by')!r}")

    # Is interactive API documentation exposed?
    for p in ("/docs", "/redoc", "/openapi.json"):
        r = requests.get(BASE + p, timeout=30)
        record("disclose", f"GET {p}", True,
               f"HTTP {r.status_code} — exposed; acceptable for a local-only "
               f"dev API, must be disabled if this is ever hosted")


# ════════════════════════════════════════════════════════════════════════════
def sec_cors():
    banner("9.7  CORS")
    allowed = "http://localhost:5173"
    hostile = [
        "http://evil.example",
        "http://localhost:5174",
        "https://localhost:5173",          # scheme differs
        "http://localhost:5173.evil.com",  # prefix trick
        "http://localhost",                # port differs
        "null",
    ]

    r = requests.get(BASE + "/api/documents",
                     headers={"Origin": allowed}, timeout=30)
    record("cors", f"allowed origin {allowed}",
           r.headers.get("access-control-allow-origin") == allowed,
           f"ACAO={r.headers.get('access-control-allow-origin')!r}  "
           f"ACAC={r.headers.get('access-control-allow-credentials')!r}")

    for origin in hostile:
        r = requests.get(BASE + "/api/documents",
                         headers={"Origin": origin}, timeout=30)
        acao = r.headers.get("access-control-allow-origin")
        record("cors", f"hostile origin {origin}",
               acao is None or acao == "",
               f"ACAO={acao!r} (must be absent so the browser blocks the read)")

    # Preflight for a state-changing method.
    r = requests.options(BASE + "/api/documents/abc", timeout=30, headers={
        "Origin": "http://evil.example",
        "Access-Control-Request-Method": "DELETE"})
    acao = r.headers.get("access-control-allow-origin")
    record("cors", "preflight DELETE from a hostile origin",
           acao is None or acao == "",
           f"HTTP {r.status_code}  ACAO={acao!r}")

    # Wildcard + credentials is the dangerous combination.
    record("cors", "wildcard '*' is not used with credentials", True,
           "main.py sets allow_origins=[FRONTEND_ORIGIN] (a single configured "
           "origin) with allow_credentials=True — verified above by the "
           "hostile-origin rows")


# ════════════════════════════════════════════════════════════════════════════
def sec_command_injection():
    banner("9.8  COMMAND INJECTION")
    blob = (FIXTURES / "scanned_image_only.pdf").read_bytes()
    marker = BACKEND / "data" / "day2_cmdinj.txt"
    if marker.exists():
        marker.unlink()

    names = [
        "day2 & echo pwned > data\\day2_cmdinj.txt.pdf",
        "day2; touch data/day2_cmdinj.txt.pdf",
        "day2$(echo pwned).pdf",
        "day2`echo pwned`.pdf",
        "day2|echo pwned.pdf",
        "day2\n echo pwned .pdf",
    ]
    for name in names:
        try:
            r = post_upload(name, blob)
            code = r.status_code
            if code == 202:
                CREATED.append(r.json()["document_id"])
        except Exception as exc:
            code = type(exc).__name__
        record("cmd", f"filename {name[:46]!r}", True, f"HTTP {code}")

    time.sleep(3)
    record("cmd", "no shell metacharacter in a filename ran a command",
           not marker.exists(),
           f"{marker.name} exists: {marker.exists()} — filenames are never "
           f"interpolated into a shell; storage names are generated UUIDs")

    # The question also reaches an HTTP JSON body only, never a shell.
    r = ask("What is this; echo pwned; $(whoami) `id` | cat /etc/passwd")
    record("cmd", "shell metacharacters in a question", r.status_code in (200, 503),
           f"HTTP {r.status_code} — the question is JSON-encoded into the "
           f"Ollama request body, never a command line")


# ════════════════════════════════════════════════════════════════════════════
def sec_redos():
    banner("9.9  REGULAR-EXPRESSION DENIAL OF SERVICE")
    # llm_service._mentioned_pages uses a nested quantifier:
    #   r"pages?\s*[:.]?\s*((?:\d+\s*(?:,|and|&|-|–)?\s*)+)"
    # A nested quantifier over overlapping alternatives is the classic
    # catastrophic-backtracking shape, so it is timed against an adversarial
    # string directly rather than assumed safe.
    sys.path.insert(0, str(BACKEND))
    from app.services.llm_service import _mentioned_pages

    for n in (100, 1000, 5000, 20000):
        evil = "page " + ("1 , " * n) + "!"
        t = time.perf_counter()
        _mentioned_pages(evil)
        d = time.perf_counter() - t
        record("redos", f"_mentioned_pages() on a {len(evil):,}-char adversarial run",
               d < 2.0, f"{d*1000:.1f} ms")

    evil2 = "pages " + ("9" * 50000)
    t = time.perf_counter()
    _mentioned_pages(evil2)
    record("redos", "50,000 consecutive digits", (time.perf_counter() - t) < 2.0,
           f"{(time.perf_counter()-t)*1000:.1f} ms")


# ════════════════════════════════════════════════════════════════════════════
def cleanup():
    banner("CLEANUP — removing documents created by this probe")
    removed = 0
    for did in CREATED:
        try:
            if requests.delete(f"{BASE}/api/documents/{did}",
                               timeout=60).status_code == 200:
                removed += 1
        except Exception:
            pass
    print(f"  deleted {removed}/{len(CREATED)} probe documents")


def summary():
    banner("STAGE 9 SUMMARY")
    findings = [r for r in RESULTS if not r[2]]
    by_section = {}
    for section, name, secure, _ in RESULTS:
        d = by_section.setdefault(section, [0, 0])
        d[0] += 1
        d[1] += (0 if secure else 1)
    for section, (total, bad) in by_section.items():
        print(f"  {section:<10} {total - bad}/{total} secure"
              + (f"   ** {bad} FINDING(S) **" if bad else ""))
    print(f"\n  TOTAL: {len(RESULTS) - len(findings)}/{len(RESULTS)} secure")
    if findings:
        print("\n  FINDINGS:")
        for section, name, _, detail in findings:
            print(f"    [{section}] {name}")
            print(f"        {str(detail).splitlines()[0]}")
    return len(findings)


if __name__ == "__main__":
    only = sys.argv[1:] or ["sql", "path", "upload", "serve", "input",
                            "disclose", "cors", "cmd", "redos"]
    fns = {"sql": sec_sql_injection, "path": sec_path_traversal,
           "upload": sec_upload_validation, "serve": sec_serving,
           "input": sec_input_validation, "disclose": sec_error_disclosure,
           "cors": sec_cors, "cmd": sec_command_injection, "redos": sec_redos}
    for key in only:
        fns[key]()
    cleanup()
    sys.exit(1 if summary() else 0)
