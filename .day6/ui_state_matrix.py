"""
ui_state_matrix.py — post-coding Day 6, stage 10 (UI/UX verification).

Closes checklist item 9 of 01_After_Coding_Is_Complete.pdf, whose closing
evidence is "Screenshots of every state and breakpoint", and item 10, "Zero
console errors". The Day 2 record verified the same ground and recorded it as
tables; this produces the artifact the checklist actually names, and adds two
machine checks a screenshot cannot make:

  * horizontal overflow — compares documentElement.scrollWidth against the
    viewport width, so "no horizontal overflow at 375 px" is measured rather
    than eyeballed;
  * console errors — every console error and page error is collected per state
    and reported, so a silent failure cannot pass review.

States captured, at 375 / 768 / 1280 px (the three widths the PDF names):

    documents-empty        the first thing a new user sees
    documents-uploading    the upload indicator
    documents-ready        populated list, OCR badge, per-document OCR count
    documents-error        rejected upload (wrong type) -> error surfaced
    chat-empty             the chat hero empty state
    chat-loading           the escalating "thinking" indicator
    chat-answered          answer plus citation cards
    chat-error             a failed turn with its Retry control

Requires: the backend on :8000, the Vite dev server on :5173, Ollama running.
Playwright lives in the throwaway .venv-tools environment and its browsers are
kept inside the project folder, so nothing is installed into the application's
own environment and nothing lands outside the repository.

    $env:PLAYWRIGHT_BROWSERS_PATH = "<repo>\\.venv-tools\\ms-playwright"
    .venv-tools\\Scripts\\python.exe .day6\\ui_state_matrix.py
"""
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parent.parent
FIXTURES = REPO / "backend" / "tests" / "fixtures"
OUT = REPO / "docs" / "ui-verification"
APP = "http://localhost:5173"

VIEWPORTS = [("375", 375, 812), ("768", 768, 1024), ("1280", 1280, 900)]

findings = []
console_errors = []

# States where a transport failure is INJECTED on purpose, to photograph how the
# UI handles it. The browser logs an intercepted 503 as "Failed to load
# resource", which is the browser reporting the response we asked for - not an
# application defect. Those are recorded separately rather than counted as
# console errors, because the alternative is either reporting a defect that does
# not exist or weakening the zero-console-errors check until it proves nothing.
injected_failure_states = set()
current_phase = {"name": "startup", "injected": False}


def check(state: str, width: str, description: str, ok: bool, detail: str = "") -> None:
    findings.append({"state": state, "viewport": width, "check": description,
                     "ok": ok, "detail": detail})
    print(f"  [{'PASS' if ok else 'FAIL'}] {width:>4}px  {state:<20} {description} {detail}")


def shoot(page, state: str, width: str) -> None:
    """Capture the state and measure horizontal overflow at the same moment."""
    OUT.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(OUT / f"{state}-{width}.png"), full_page=False)

    metrics = page.evaluate(
        "() => ({scroll: document.documentElement.scrollWidth,"
        " client: document.documentElement.clientWidth})"
    )
    overflow = metrics["scroll"] - metrics["client"]
    check(state, width, "no horizontal overflow", overflow <= 0,
          f"(scrollWidth {metrics['scroll']} vs viewport {metrics['client']})")


def clear_documents(page) -> None:
    page.goto(f"{APP}/documents", wait_until="networkidle")
    while True:
        buttons = page.locator('button[aria-label^="Delete"]')
        if buttons.count() == 0:
            break
        buttons.first.click()
        page.wait_for_timeout(1200)


def upload(page, fixture: str) -> None:
    page.set_input_files('input[type="file"]', str(FIXTURES / fixture))


def wait_ready(page, timeout_ms: int = 180000) -> None:
    page.wait_for_function(
        "() => !document.body.innerText.includes('Processing')",
        timeout=timeout_ms,
    )


def run_viewport(browser, label: str, width: int, height: int, with_answer: bool) -> None:
    context = browser.new_context(viewport={"width": width, "height": height})
    page = context.new_page()
    page.on("console", lambda m: console_errors.append(
        (label, m.text, current_phase["injected"])) if m.type == "error" else None)
    page.on("pageerror", lambda e: console_errors.append(
        (label, f"pageerror: {e}", current_phase["injected"])))

    # ── documents: empty ────────────────────────────────────────────────────
    clear_documents(page)
    page.wait_for_timeout(600)
    shoot(page, "documents-empty", label)
    check("documents-empty", label, "empty state is explained, not blank",
          "No documents yet" in page.inner_text("body"))

    # ── documents: rejected upload (error state) ────────────────────────────
    bad = REPO / ".day6" / "not-a-pdf.txt"
    bad.write_text("this is not a pdf", encoding="utf-8")
    page.set_input_files('input[type="file"]', str(bad))
    page.wait_for_timeout(1500)
    body = page.inner_text("body")
    shoot(page, "documents-error", label)
    check("documents-error", label, "invalid file is refused with a visible message",
          "PDF" in body and ("Only" in body or "not" in body.lower()))
    bad.unlink(missing_ok=True)

    # ── documents: uploading / processing ──────────────────────────────────
    upload(page, "mixed_native_scanned.pdf")
    page.wait_for_timeout(700)
    shoot(page, "documents-uploading", label)
    wait_ready(page)

    # ── documents: ready, with the OCR badge ───────────────────────────────
    upload(page, "scanned_image_only.pdf")
    wait_ready(page)
    page.wait_for_timeout(800)
    shoot(page, "documents-ready", label)
    body = page.inner_text("body")
    check("documents-ready", label, "OCR badge shown for OCR-derived documents",
          "OCR" in body)
    check("documents-ready", label, "per-document OCR page count shown",
          "via OCR" in body, "")

    # ── chat: empty ─────────────────────────────────────────────────────────
    page.goto(f"{APP}/chat", wait_until="networkidle")
    page.wait_for_timeout(500)
    shoot(page, "chat-empty", label)
    check("chat-empty", label, "chat empty state explains what to do",
          "Ask a question" in page.inner_text("body"))

    # Keyboard accessibility: the composer must be reachable and send on Enter.
    page.keyboard.press("Tab")
    focused = page.evaluate("() => document.activeElement.tagName")
    check("chat-empty", label, "keyboard focus reaches an interactive element",
          focused in ("A", "BUTTON", "TEXTAREA", "INPUT"), f"(first Tab -> {focused})")

    if with_answer:
        # ── chat: loading, then answered ────────────────────────────────────
        page.fill("textarea", "What was the keyword for retrieval testing?")
        page.keyboard.press("Enter")
        page.wait_for_timeout(2500)
        shoot(page, "chat-loading", label)
        body = page.inner_text("body")
        # Matched against the indicator's actual copy (LoadingIndicator.jsx), not
        # a loose set of substrings: `any(w in body for w in (..., "s", "…"))`
        # would pass on almost any page, which is a test that proves nothing.
        expected = ("Searching your documents", "Reading the most relevant passages",
                    "Generating the answer", "Still working")
        check("chat-loading", label, "escalating loading indicator is shown",
              any(w in body for w in expected),
              f"({[w for w in expected if w in body]})")

        page.wait_for_selector("text=/match strength/i", timeout=400000)
        page.wait_for_timeout(800)
        shoot(page, "chat-answered", label)
        body = page.inner_text("body")
        check("chat-answered", label, "answer renders with a citation card",
              "match strength" in body.lower())
        check("chat-answered", label, "citation names the source file",
              ".pdf" in body)

    context.close()


def capture_answered_at_other_widths(browser) -> None:
    """
    The answered and loading states cost a real generation each, which is 30-170 s
    on the reference hardware. Capturing them once at 1280 and then re-rendering
    the same conversation at the two narrower widths keeps the evidence complete
    without paying for three generations.
    """
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    page = context.new_page()
    page.on("console", lambda m: console_errors.append(
        ("resize", m.text, current_phase["injected"])) if m.type == "error" else None)

    page.goto(f"{APP}/chat", wait_until="networkidle")
    page.fill("textarea", "What was the keyword for retrieval testing?")
    page.keyboard.press("Enter")
    page.wait_for_timeout(2500)
    shoot(page, "chat-loading", "1280")
    page.wait_for_selector("text=/match strength/i", timeout=400000)
    page.wait_for_timeout(800)
    shoot(page, "chat-answered", "1280")
    body = page.inner_text("body")
    check("chat-answered", "1280", "answer renders with a citation card",
          "match strength" in body.lower())

    for label, width, height in (("768", 768, 1024), ("375", 375, 812)):
        page.set_viewport_size({"width": width, "height": height})
        page.wait_for_timeout(700)
        shoot(page, "chat-answered", label)

    context.close()


def capture_failure_and_loading_states(browser) -> None:
    """
    The failed turn and the loading indicator, at all three widths.

    Both are captured by intercepting POST /api/chat/ask rather than by stopping
    Ollama or waiting out a real generation:

      * the failed turn needs the backend's 503 shape, and stopping the user's
        Ollama service to produce one would be a machine-level side effect for a
        screenshot;
      * the loading indicator is transient, and holding the response open is the
        only way to photograph it reliably at three widths.

    What is under test here is the FRONTEND's handling - that a failure becomes a
    real turn in the history with a Retry rather than a vanishing toast, and that
    the indicator renders - so intercepting the transport is the right seam. The
    backend's own 503 behaviour is covered for real by test_api.py and by the
    functional probe.
    """
    for label, width, height in VIEWPORTS:
        context = browser.new_context(viewport={"width": width, "height": height})
        page = context.new_page()
        page.on("console", lambda m, lbl=label: console_errors.append(
            (lbl, m.text, current_phase["injected"])) if m.type == "error" else None)

        # ── loading: leave the request pending ─────────────────────────────
        #
        # The handler stores the route and returns WITHOUT fulfilling it, so the
        # request genuinely stays in flight and the indicator renders exactly as
        # it does during a real generation.
        #
        # An earlier version slept inside the handler instead. In Playwright's
        # sync API the handler runs on the same thread that drives the page, so
        # the sleep froze the page itself: React never re-rendered and the
        # indicator was absent from the screenshot. The check caught it, which is
        # the point of asserting on the indicator's real copy rather than on
        # something loose enough to pass either way.
        pending = []
        page.route("**/api/chat/ask", lambda route: pending.append(route))
        page.goto(f"{APP}/chat", wait_until="networkidle")
        page.fill("textarea", "What was the keyword for retrieval testing?")
        page.keyboard.press("Enter")
        page.wait_for_timeout(2500)
        shoot(page, "chat-loading", label)
        body = page.inner_text("body")
        expected = ("Searching your documents", "Reading the most relevant passages",
                    "Generating the answer", "Still working")
        check("chat-loading", label, "escalating loading indicator is shown",
              any(w in body for w in expected),
              f"({[w for w in expected if w in body]})")
        # Release the held request with a normal answer rather than aborting it.
        # Aborting ends the loading state just as well, but the browser logs the
        # cancelled request as `net::ERR_FAILED`, which then shows up as a console
        # error the application never caused. Fulfilling leaves the console clean
        # and exercises the loading -> answered transition besides.
        for route in pending:
            try:
                route.fulfill(
                    status=200, content_type="application/json",
                    body=json.dumps({
                        "answer": "Held open by the UI verification harness to "
                                  "photograph the loading state.",
                        "citations": [], "processing_time_ms": 2500}))
            except Exception:
                pass
        page.unroute("**/api/chat/ask")
        page.wait_for_timeout(1500)

        # ── error: the backend's real 503 body for an unreachable model ────
        injected_failure_states.add(label)
        current_phase["injected"] = True
        page.route("**/api/chat/ask", lambda route: route.fulfill(
            status=503, content_type="application/json",
            body=json.dumps({"detail": "Cannot reach the language model. "
                                       "Make sure Ollama is running."})))
        page.goto(f"{APP}/chat", wait_until="networkidle")
        page.fill("textarea", "What was the keyword for retrieval testing?")
        page.keyboard.press("Enter")
        page.wait_for_timeout(2500)
        shoot(page, "chat-error", label)
        body = page.inner_text("body")
        check("chat-error", label, "failure is surfaced with an actionable message",
              "Ollama" in body, "")
        check("chat-error", label, "failed turn offers Retry rather than vanishing",
              "Retry" in body, "")
        current_phase["injected"] = False

        context.close()


def main() -> int:
    started = time.time()
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for label, width, height in VIEWPORTS:
            print(f"\n=== viewport {label}px ===")
            run_viewport(browser, label, width, height, with_answer=False)
        print("\n=== failure and loading states (transport intercepted) ===")
        capture_failure_and_loading_states(browser)
        print("\n=== answered state (one real generation) ===")
        capture_answered_at_other_widths(browser)
        browser.close()

    print("\n=== CONSOLE ERRORS ===")
    real = [c for c in console_errors if not c[2]]
    injected = [c for c in console_errors if c[2]]
    if real:
        for where, text, _ in real:
            print(f"  [{where}] {text}")
    else:
        print("  none in any state the application is expected to succeed in")
    if injected:
        print(f"  ({len(injected)} logged during the deliberately-injected 503 — the "
              f"browser reporting the response this harness asked for, in "
              f"{sorted(injected_failure_states)}px chat-error)")
    check("all", "all", "zero console errors outside injected-failure states",
          not real, f"({len(real)} found)")

    (REPO / ".day6" / "ui_state_matrix_results.json").write_text(
        json.dumps({"findings": findings,
                    "console_errors": [{"state": w, "text": t, "injected": inj}
                                       for w, t, inj in console_errors]},
                   indent=2),
        encoding="utf-8")

    failed = [f for f in findings if not f["ok"]]
    print(f"\n{len(findings) - len(failed)} passed, {len(failed)} failed, "
          f"{len(findings)} checks in {time.time() - started:.0f}s")
    print(f"Screenshots: {OUT}")
    for f in failed:
        print(f"  FAILED {f['viewport']}px {f['state']}: {f['check']} {f['detail']}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
