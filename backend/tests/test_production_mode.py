"""
test_production_mode.py — guards the Day 4 (stage 18) production configuration.

Development and production are different programs, and Day 4 made that
difference explicit rather than implicit:

  * APP_ENV selects which one is running, and an unrecognised value stops the
    backend at startup instead of silently falling back to development.
  * In production the interactive API documentation is not mounted at all.
    /docs, /redoc and /openapi.json publish every endpoint and every schema;
    Day 2 carried "must be disabled if the service is ever exposed" as an open
    item, and this is the switch that closes it.
  * When a built frontend bundle is present the backend serves it, so a
    deployment is one process on one origin with no Node runtime and no CORS.
    That introduced a handler that turns a user-controlled URL path into a
    filesystem read, which is exactly the shape of an arbitrary-file-read bug —
    so the containment check has its own tests below.

The path-traversal tests call the handler directly rather than going through
TestClient, because an HTTP client normalises "../" out of the URL before it is
ever sent. Normalisation is a client-side courtesy, not a server-side control;
the server must refuse the escape on its own, and that is what is asserted.
"""
import asyncio
import importlib

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import app.config as config


ENV_VARS = ("APP_ENV", "LOG_LEVEL", "FRONTEND_DIST_DIR")


@pytest.fixture
def reload_config(monkeypatch):
    """Reload app.config under a controlled environment, then restore it."""
    def _reload(**env):
        for name in ENV_VARS:
            monkeypatch.delenv(name, raising=False)
        for name, value in env.items():
            monkeypatch.setenv(name, value)
        return importlib.reload(config)

    yield _reload
    monkeypatch.undo()
    importlib.reload(config)


def assert_is_configuration_error(excinfo):
    # ConfigurationError is rebuilt by each reload, so the concrete class object
    # differs from the one imported here; match on the stable base and assert
    # the name separately. Same reasoning as test_config_validation.py.
    assert type(excinfo.value).__name__ == "ConfigurationError", (
        f"expected ConfigurationError, got {type(excinfo.value).__name__}: "
        f"{excinfo.value}"
    )


# ── APP_ENV ──────────────────────────────────────────────────────────────────

def test_app_env_defaults_to_development(reload_config):
    cfg = reload_config()
    assert cfg.APP_ENV == "development"
    assert cfg.IS_PRODUCTION is False


def test_app_env_production_is_recognised(reload_config):
    cfg = reload_config(APP_ENV="production")
    assert cfg.IS_PRODUCTION is True


def test_app_env_is_case_and_whitespace_insensitive(reload_config):
    """A stray space or capital in a .env file must not silently mean 'dev'."""
    cfg = reload_config(APP_ENV="  Production  ")
    assert cfg.IS_PRODUCTION is True


def test_unknown_app_env_is_rejected_at_import(reload_config):
    """
    The dangerous failure is a typo reading as development, leaving /docs
    mounted on something the operator believes is production.
    """
    with pytest.raises(RuntimeError) as excinfo:
        reload_config(APP_ENV="prod")
    assert_is_configuration_error(excinfo)
    message = str(excinfo.value)
    assert "APP_ENV" in message
    assert ".env" in message


# ── LOG_LEVEL ────────────────────────────────────────────────────────────────

def test_log_level_defaults_to_info(reload_config):
    assert reload_config().LOG_LEVEL == "INFO"


def test_log_level_is_normalised(reload_config):
    assert reload_config(LOG_LEVEL="debug").LOG_LEVEL == "DEBUG"


def test_unknown_log_level_is_rejected_at_import(reload_config):
    """
    getattr(logging, "VERBOSE") would raise AttributeError from inside
    logging.basicConfig, far from the variable that caused it.
    """
    with pytest.raises(RuntimeError) as excinfo:
        reload_config(LOG_LEVEL="verbose")
    assert_is_configuration_error(excinfo)
    assert "LOG_LEVEL" in str(excinfo.value)


# ── FRONTEND_DIST_DIR ────────────────────────────────────────────────────────

def test_dist_dir_is_absolute_and_resolved(reload_config):
    from pathlib import Path
    assert Path(reload_config().FRONTEND_DIST_DIR).is_absolute()


def test_relative_dist_dir_does_not_depend_on_working_directory(
    reload_config, tmp_path, monkeypatch
):
    """
    The whole point of resolving this one against the backend package: a service
    manager may start uvicorn from anywhere. If this were resolved against the
    working directory, the deployment would serve the API and silently not serve
    the frontend, depending only on where it happened to be launched.
    """
    from_here = reload_config(FRONTEND_DIST_DIR="../frontend/dist").FRONTEND_DIST_DIR

    monkeypatch.chdir(tmp_path)
    from_elsewhere = reload_config(
        FRONTEND_DIST_DIR="../frontend/dist"
    ).FRONTEND_DIST_DIR

    assert from_here == from_elsewhere


# ── The production application ───────────────────────────────────────────────

@pytest.fixture
def production_app(monkeypatch, tmp_path):
    """
    Build the app in production mode against a throwaway bundle, so these tests
    do not depend on `npm run build` having been run.
    """
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>shell</title>")
    (dist / "assets" / "app.js").write_text("console.log(1)")

    # A file the traversal tests try to reach: a sibling of the bundle, standing
    # in for backend/.env.
    (tmp_path / "secret.txt").write_text("OLLAMA_BASE_URL=http://127.0.0.1:11434")

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("FRONTEND_DIST_DIR", str(dist))

    importlib.reload(config)
    import app.main as main_mod
    importlib.reload(main_mod)

    yield main_mod

    monkeypatch.undo()
    importlib.reload(config)
    importlib.reload(main_mod)


def test_production_serves_the_bundle(production_app):
    client = TestClient(production_app.app)
    response = client.get("/")
    assert response.status_code == 200
    assert "shell" in response.text


def test_production_serves_spa_route_as_the_shell(production_app):
    """A refresh on a client-side route must not 404."""
    response = TestClient(production_app.app).get("/documents")
    assert response.status_code == 200
    assert "shell" in response.text


def test_production_does_not_mount_the_openapi_schema(production_app):
    """
    The schema route is removed, not merely unlinked. It is asserted on the app
    object because the catch-all answers /openapi.json with the SPA shell, so a
    200 over HTTP proves nothing either way.
    """
    assert production_app.app.openapi_url is None
    assert production_app.app.docs_url is None
    assert production_app.app.redoc_url is None

    # Not every entry in .routes is a path-bearing route (mounts and included
    # routers are not), so this reads the attribute defensively.
    paths = {
        getattr(route, "path", None) for route in production_app.app.routes
    }
    assert "/openapi.json" not in paths
    assert "/docs" not in paths
    assert "/redoc" not in paths


def test_openapi_schema_is_not_reachable_over_http(production_app):
    body = TestClient(production_app.app).get("/openapi.json").text
    assert "paths" not in body
    assert "/api/chat/ask" not in body


def test_unmatched_api_path_is_404_not_the_shell(production_app):
    """
    Falling through to index.html would hand the client HTML with a 200 for a
    mistyped endpoint, which surfaces as a JSON parse error rather than a 404.
    """
    response = TestClient(production_app.app).get("/api/does-not-exist")
    assert response.status_code == 404
    assert "shell" not in response.text


def test_real_api_routes_still_win_over_the_catch_all(production_app):
    response = TestClient(production_app.app).get("/api/documents")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


# ── Path traversal ───────────────────────────────────────────────────────────

def _serve_frontend(main_mod):
    for route in main_mod.app.routes:
        if getattr(route, "name", None) == "serve_frontend":
            return route.endpoint
    raise AssertionError("serve_frontend route is not registered")


@pytest.mark.parametrize(
    "attack",
    [
        "../secret.txt",
        "../../secret.txt",
        "assets/../../secret.txt",
        "....//secret.txt",
        "..%2fsecret.txt",
    ],
)
def test_traversal_outside_the_bundle_never_returns_the_file(production_app, attack):
    """
    Each of these is handled without reading outside the bundle: the request
    either falls back to the shell or is refused, but it never returns the
    sibling file's contents.
    """
    handler = _serve_frontend(production_app)
    try:
        response = asyncio.run(handler(attack))
    except HTTPException as exc:
        assert exc.status_code == 404
        return

    served = getattr(response, "path", None)
    assert served is not None
    assert "secret" not in str(served), f"{attack} escaped the bundle: {served}"


def test_a_real_bundle_file_is_still_served(production_app):
    """
    The containment check must not be vacuous - a legitimate asset inside the
    bundle still resolves, so the tests above are constraining something.
    """
    handler = _serve_frontend(production_app)
    response = asyncio.run(handler("assets/app.js"))
    assert str(getattr(response, "path", "")).endswith("app.js")
