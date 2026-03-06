from fastapi.testclient import TestClient

from app.main import app, settings


def test_login_page_and_protected_route_redirect() -> None:
    prev_enabled = settings.auth_enabled
    prev_provider = settings.auth_provider
    settings.auth_enabled = True
    settings.auth_provider = "local"
    try:
        client = TestClient(app)
        login = client.get("/app/login")
        assert login.status_code == 200
        assert "AI摄影棚" in login.text

        protected = client.get("/app/tools", follow_redirects=False)
        assert protected.status_code == 302
        assert protected.headers["location"] == "/app/login"
    finally:
        settings.auth_enabled = prev_enabled
        settings.auth_provider = prev_provider


def test_local_login_renders_tools_page() -> None:
    prev_enabled = settings.auth_enabled
    prev_provider = settings.auth_provider
    settings.auth_enabled = True
    settings.auth_provider = "local"
    try:
        client = TestClient(app)
        login = client.post("/api/v1/auth/login", data={"username": "admin", "password": "admin123"})
        assert login.status_code == 200
        tools = client.get("/app/tools")
        assert tools.status_code == 200
        assert "AI摄影棚" in tools.text
    finally:
        settings.auth_enabled = prev_enabled
        settings.auth_provider = prev_provider


def test_next_assets_path_not_blocked_by_auth() -> None:
    prev_enabled = settings.auth_enabled
    settings.auth_enabled = True
    try:
        client = TestClient(app)
        resp = client.get("/_next/static/not-exists.js", follow_redirects=False)
        assert resp.status_code == 404
    finally:
        settings.auth_enabled = prev_enabled
