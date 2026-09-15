"""
test_config_validation.py — guards the Day 2 configuration defect.

Day 2 (Stage 11, configuration and environment verification) found that
app/config.py coerced types but validated no ranges, so a typo in backend/.env
produced a backend that started cleanly, reported `/api/health: ok`, and then
failed at *use* time somewhere else entirely:

  CHUNK_OVERLAP=500 / CHUNK_SIZE=100  -> ValueError raised from inside
      langchain_text_splitters during ingestion; every upload reached 'failed'.
  TOP_K_RESULTS=0                     -> retrieval returned 0 hits silently.
  MAX_FILE_SIZE_MB=0                  -> every non-empty upload rejected.
  OCR_DPI=0                           -> MuPDF render failed; OCR self-disabled.

Each test below re-imports app.config in a controlled environment and requires
the failure to happen at import, naming the offending variable. config.py runs
its checks at module scope, so `importlib.reload` is what re-triggers them.
"""
import importlib

import pytest

import app.config as config


CONFIG_VARS = (
    "OLLAMA_TIMEOUT_SECONDS", "MAX_FILE_SIZE_MB", "CHUNK_SIZE",
    "CHUNK_OVERLAP", "TOP_K_RESULTS", "MAX_CONTEXT_TOKENS", "OCR_DPI",
)


def raises_configuration_error():
    """
    `pytest.raises(config.ConfigurationError)` cannot be used here.

    These tests trigger the failure with `importlib.reload(config)`, and a
    reload rebuilds the module's classes: the ConfigurationError raised during
    the reload is a *different class object* from the one that was resolved when
    the `pytest.raises(...)` argument was evaluated, so it is not caught and the
    test fails while the code under test is behaving perfectly.

    ConfigurationError subclasses RuntimeError, and that base is stable across
    reloads, so it is what the context manager matches — with the concrete class
    name asserted separately so this cannot pass on an unrelated RuntimeError.
    """
    return pytest.raises(RuntimeError)


def assert_is_configuration_error(excinfo):
    assert type(excinfo.value).__name__ == "ConfigurationError", (
        f"expected ConfigurationError, got {type(excinfo.value).__name__}: "
        f"{excinfo.value}"
    )


@pytest.fixture
def reload_config(monkeypatch):
    """
    Reload app.config with a controlled environment, then restore the real
    module so later tests in the session still see the committed settings.

    Every numeric variable is cleared first: without that, a value inherited
    from the developer's own backend/.env would decide the result instead of the
    value under test. load_dotenv() does not override variables that are already
    set, so the ones this fixture sets do win.
    """
    def _reload(**env):
        for name in CONFIG_VARS:
            monkeypatch.delenv(name, raising=False)
        for name, value in env.items():
            monkeypatch.setenv(name, value)
        return importlib.reload(config)

    yield _reload
    monkeypatch.undo()
    importlib.reload(config)


# ── the defect itself ────────────────────────────────────────────────────────

def test_overlap_not_smaller_than_chunk_size_is_rejected_at_import(reload_config):
    """The exact configuration that used to break every upload at ingestion."""
    with raises_configuration_error() as excinfo:
        reload_config(CHUNK_SIZE="100", CHUNK_OVERLAP="500")

    assert_is_configuration_error(excinfo)
    message = str(excinfo.value)
    # The operator must be able to tell which variables to edit, and where.
    assert "CHUNK_OVERLAP" in message
    assert "CHUNK_SIZE" in message
    assert ".env" in message


def test_overlap_equal_to_chunk_size_is_rejected(reload_config):
    """Equal is as unusable as larger — the splitter rejects both."""
    with raises_configuration_error() as excinfo:
        reload_config(CHUNK_SIZE="500", CHUNK_OVERLAP="500")
    assert_is_configuration_error(excinfo)


@pytest.mark.parametrize("name,value", [
    ("TOP_K_RESULTS", "0"),
    ("TOP_K_RESULTS", "-3"),
    ("MAX_FILE_SIZE_MB", "0"),
    ("OCR_DPI", "0"),
    ("OCR_DPI", "71"),
    ("CHUNK_SIZE", "0"),
    ("MAX_CONTEXT_TOKENS", "0"),
    ("OLLAMA_TIMEOUT_SECONDS", "0"),
])
def test_out_of_range_values_are_rejected_at_import(reload_config, name, value):
    """Each of these used to be accepted, then degraded something silently."""
    with raises_configuration_error() as excinfo:
        reload_config(**{name: value})
    assert_is_configuration_error(excinfo)
    assert name in str(excinfo.value)


@pytest.mark.parametrize("name,value", [
    ("CHUNK_SIZE", "five-hundred"),
    ("OCR_DPI", "3OO"),
    ("MAX_FILE_SIZE_MB", ""),
    ("TOP_K_RESULTS", "5.5"),
])
def test_non_numeric_values_fail_with_an_actionable_message(reload_config, name, value):
    """
    A bare `int()` already raised here, but with a message that named the value
    and not the file to edit. The contract now is: our own error type, the
    variable's name, and where to fix it.
    """
    with raises_configuration_error() as excinfo:
        reload_config(**{name: value})
    assert_is_configuration_error(excinfo)
    message = str(excinfo.value)
    assert name in message
    assert ".env" in message


# ── the other direction: valid configurations must still load ────────────────

def test_committed_defaults_load_cleanly(reload_config):
    """Nothing set: every variable falls back to its in-code default."""
    cfg = reload_config()
    assert cfg.CHUNK_SIZE == 500
    assert cfg.CHUNK_OVERLAP == 100
    assert cfg.TOP_K_RESULTS == 5
    assert cfg.MAX_FILE_SIZE_MB == 20
    assert cfg.OCR_DPI == 300
    assert cfg.MAX_FILE_SIZE_BYTES == 20 * 1024 * 1024


def test_boundary_values_are_accepted(reload_config):
    """
    The bounds are inclusive where that is meaningful, so the boundary itself
    must load — a validator that rejects its own limit is a new bug.
    """
    cfg = reload_config(CHUNK_SIZE="2", CHUNK_OVERLAP="1", TOP_K_RESULTS="1",
                        MAX_FILE_SIZE_MB="1", OCR_DPI="72",
                        MAX_CONTEXT_TOKENS="1", OLLAMA_TIMEOUT_SECONDS="1")
    assert (cfg.CHUNK_SIZE, cfg.CHUNK_OVERLAP) == (2, 1)
    assert cfg.OCR_DPI == 72


def test_zero_overlap_is_allowed(reload_config):
    """CHUNK_OVERLAP=0 is a legitimate choice: no overlap, not an error."""
    cfg = reload_config(CHUNK_SIZE="500", CHUNK_OVERLAP="0")
    assert cfg.CHUNK_OVERLAP == 0
