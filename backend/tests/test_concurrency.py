"""
test_concurrency.py — guards the Day 2 event-loop blocking defect.

Day 2 (Stage 8, performance) found that /api/chat/ask and /api/health were
declared `async def` while doing entirely blocking work — an embedding model
call, a ChromaDB query, a Tesseract subprocess, and a synchronous HTTP call to
Ollama that is allowed to run for OLLAMA_TIMEOUT_SECONDS (300 s).

A coroutine runs on the event loop, so those handlers stalled the whole server.
Measured against the running backend: one question in flight for 92.0 s made a
`GET /api/documents` issued during it wait the full 92.0 s.

The fix is that both handlers are declared `def`, which makes FastAPI run them
in its threadpool. These tests assert that property two ways:

  1. statically — the handler functions are not coroutine functions, which is
     the actual thing that was wrong and the thing that could silently regress
     if someone "tidies up" by adding `async` back;
  2. behaviourally — with the LLM call stubbed to block, a second request is
     still served while the first is stuck.

The behavioural test needs real concurrency, so it drives the app over a real
loopback port with a thread pool rather than through TestClient (whose portal
would serialise the calls and hide exactly the property under test).
"""
import inspect
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
import requests
import uvicorn

from app.routers import chat as chat_router
from app.routers import health as health_router


# ── 1. static: the handlers must not be coroutines ───────────────────────────

@pytest.mark.parametrize("handler", [
    pytest.param(chat_router.ask_question, id="chat.ask_question"),
    pytest.param(health_router.health_check, id="health.health_check"),
])
def test_blocking_handlers_are_not_coroutines(handler):
    """
    `async def` + blocking body = the whole server stalls. These two handlers do
    blocking I/O with no `await` anywhere in their bodies, so they must stay
    plain `def` and be run in FastAPI's threadpool.
    """
    assert not inspect.iscoroutinefunction(handler), (
        f"{handler.__module__}.{handler.__name__} is declared `async def` but "
        f"its body is entirely blocking. On the event loop that stalls every "
        f"other request for its full duration — up to OLLAMA_TIMEOUT_SECONDS "
        f"for /chat/ask. Declare it `def` so FastAPI uses its threadpool."
    )


# ── 2. behavioural: a slow question must not block an unrelated read ─────────

def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def live_server():
    """A real uvicorn on a loopback port, so requests can genuinely overlap."""
    from app.main import app

    port = _free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    base = f"http://127.0.0.1:{port}"
    deadline = time.time() + 180
    while time.time() < deadline:
        try:
            if requests.get(f"{base}/", timeout=5).status_code == 200:
                break
        except Exception:
            time.sleep(0.2)
    else:
        pytest.fail("live server did not become ready")

    yield base

    server.should_exit = True
    thread.join(timeout=30)


SLOW_SECONDS = 6.0


def test_a_slow_question_does_not_block_other_requests(live_server, monkeypatch):
    """
    Stub the Ollama call so it blocks for a known time, then confirm an
    unrelated GET issued while the question is in flight is still served
    promptly. Before the fix this GET waited for the whole generation.
    """
    from app.services import llm_service

    def slow_call_ollama(prompt, system=None, timeout=None):
        time.sleep(SLOW_SECONDS)
        return "A stubbed answer."

    monkeypatch.setattr(llm_service, "call_ollama", slow_call_ollama)

    def ask():
        t = time.perf_counter()
        r = requests.post(f"{live_server}/api/chat/ask",
                          json={"question": "Anything at all?"},
                          timeout=SLOW_SECONDS + 60)
        return time.perf_counter() - t, r.status_code

    def read_documents():
        # Start after the question is definitely in flight.
        time.sleep(SLOW_SECONDS / 3)
        t = time.perf_counter()
        r = requests.get(f"{live_server}/api/documents",
                         timeout=SLOW_SECONDS + 60)
        return time.perf_counter() - t, r.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        f_ask = pool.submit(ask)
        f_read = pool.submit(read_documents)
        ask_seconds, ask_status = f_ask.result()
        read_seconds, read_status = f_read.result()

    assert read_status == 200
    assert ask_status in (200, 503)

    # The question really was slow — otherwise this test proves nothing.
    assert ask_seconds >= SLOW_SECONDS, (
        f"the stubbed question returned in {ask_seconds:.2f}s, faster than the "
        f"{SLOW_SECONDS}s block it was supposed to take; this test cannot "
        f"demonstrate anything about concurrency."
    )

    # And the unrelated read was NOT dragged along with it. Generous ceiling:
    # the point is 'did not wait for the whole generation', not a latency SLO.
    assert read_seconds < SLOW_SECONDS / 2, (
        f"GET /api/documents took {read_seconds:.2f}s while a "
        f"{ask_seconds:.2f}s question was in flight — it was blocked behind it. "
        f"That is the async-handler defect found on Day 2."
    )
