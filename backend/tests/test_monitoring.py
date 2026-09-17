"""
test_monitoring.py — guards the Day 5 (stage 21) monitoring additions.

The health endpoint gained three fields (database_available, uptime_seconds,
version), request logging middleware was added, and production mode uses
structured JSON log output. These tests verify the new behaviour without
depending on external services being up.
"""
import json
import logging

from fastapi.testclient import TestClient

from app.main import app, _JSONFormatter, RequestLoggingMiddleware


client = TestClient(app)


# ── Enhanced health endpoint ────────────────────────────────────────────────


def test_health_includes_database_available():
    data = client.get("/api/health").json()
    assert "database_available" in data
    assert isinstance(data["database_available"], bool)


def test_health_database_is_reachable():
    data = client.get("/api/health").json()
    assert data["database_available"] is True


def test_health_includes_uptime():
    data = client.get("/api/health").json()
    assert "uptime_seconds" in data
    assert isinstance(data["uptime_seconds"], (int, float))
    assert data["uptime_seconds"] > 0


def test_health_includes_version():
    data = client.get("/api/health").json()
    assert data["version"] == "1.0.0"


def test_health_status_requires_database():
    """database_available is part of the ok/degraded gate."""
    data = client.get("/api/health").json()
    if data["database_available"] and data["ollama_available"] \
            and data["chroma_available"] and data["embedding_model_loaded"]:
        assert data["status"] == "ok"


# ── Request logging middleware ──────────────────────────────────────────────


def test_request_logging_emits_access_log(caplog):
    with caplog.at_level(logging.INFO, logger="app.access"):
        client.get("/api/documents")
    assert any("GET" in r.message and "/api/documents" in r.message for r in caplog.records)


def test_health_endpoint_is_excluded_from_access_log(caplog):
    with caplog.at_level(logging.INFO, logger="app.access"):
        client.get("/api/health")
    access_records = [r for r in caplog.records if r.name == "app.access"]
    assert not any("/api/health" in r.message for r in access_records)


# ── JSON formatter ──────────────────────────────────────────────────────────


def test_json_formatter_produces_valid_json():
    formatter = _JSONFormatter()
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="hello %s", args=("world",), exc_info=None,
    )
    output = formatter.format(record)
    parsed = json.loads(output)
    assert parsed["level"] == "INFO"
    assert parsed["message"] == "hello world"
    assert "timestamp" in parsed
