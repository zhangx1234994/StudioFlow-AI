from fastapi.testclient import TestClient

from app.main import app, settings


def test_login_page_and_protected_route_redirect() -> None:
    prev_enabled = settings.auth_enabled
    prev_provider = settings.auth_provider
    settings.auth_enabled = True
    settings.auth_provider = "local"

    client = TestClient(app)
    login = client.get("/app/login")
    assert login.status_code == 200
    assert "登录 AI摄影棚" in login.text

    protected = client.get("/app/tools", follow_redirects=False)
    assert protected.status_code == 302
    assert protected.headers["location"] == "/app/login"

    settings.auth_enabled = prev_enabled
    settings.auth_provider = prev_provider


def test_local_login_renders_tools_page() -> None:
    prev_enabled = settings.auth_enabled
    prev_provider = settings.auth_provider
    settings.auth_enabled = True
    settings.auth_provider = "local"

    client = TestClient(app)
    login = client.post("/api/v1/auth/login", data={"username": "admin", "password": "admin123"})
    assert login.status_code == 200
    tools = client.get("/app/tools")
    assert tools.status_code == 200
    assert "AI摄影棚" in tools.text

    settings.auth_enabled = prev_enabled
    settings.auth_provider = prev_provider
