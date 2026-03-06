import os
from dataclasses import dataclass
from uuid import uuid4

from fastapi.testclient import TestClient

os.environ["MVP_AUTH_ENABLED"] = "true"

from app.main import app, settings


@dataclass
class _FakeSession:
    access_token: str
    refresh_token: str
    expires_in: int
    username: str
    email: str


class _FakeAuthService:
    is_configured = True

    async def sign_in_with_password(self, username_or_email: str, password: str):
        if password != "admin123":
            raise ValueError("Invalid credentials")
        return _FakeSession(
            access_token="access-token",
            refresh_token="refresh-token",
            expires_in=3600,
            username="admin",
            email="admin@studioflow.local",
        )

    async def verify_access_token(self, access_token: str):
        if access_token == "access-token":
            return {"username": "admin", "email": "admin@studioflow.local"}
        return None

    async def refresh_session(self, refresh_token: str):
        return _FakeSession(
            access_token="access-token-2",
            refresh_token="refresh-token-2",
            expires_in=3600,
            username="admin",
            email="admin@studioflow.local",
        )

    async def sign_out(self, access_token: str):
        return None


def test_auth_login_success_and_me(monkeypatch) -> None:
    import app.main as main

    prev_enabled = settings.auth_enabled
    prev_provider = settings.auth_provider
    monkeypatch.setattr(main, "auth_service", _FakeAuthService())
    settings.auth_enabled = True
    settings.auth_provider = "supabase"

    client = TestClient(app)
    resp = client.post("/api/v1/auth/login", data={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["ok"] is True
    assert payload["username"] == "admin"
    assert "expires_in" in payload
    assert "access_token" in resp.headers.get("set-cookie", "")

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["authenticated"] is True
    assert me.json()["username"] == "admin"

    settings.auth_enabled = prev_enabled
    settings.auth_provider = prev_provider


def test_auth_login_invalid_credentials(monkeypatch) -> None:
    import app.main as main

    prev_enabled = settings.auth_enabled
    prev_provider = settings.auth_provider
    monkeypatch.setattr(main, "auth_service", _FakeAuthService())
    settings.auth_enabled = True
    settings.auth_provider = "supabase"

    client = TestClient(app)
    resp = client.post("/api/v1/auth/login", data={"username": "admin", "password": "wrong"})
    assert resp.status_code == 401
    payload = resp.json()
    assert payload["code"] == "INVALID_CREDENTIALS"
    assert payload["request_id"]

    settings.auth_enabled = prev_enabled
    settings.auth_provider = prev_provider


def test_local_register_then_login() -> None:
    prev_enabled = settings.auth_enabled
    prev_provider = settings.auth_provider
    settings.auth_enabled = True
    settings.auth_provider = "local"
    try:
        client = TestClient(app)
        username = f"reg_{uuid4().hex[:8]}"
        register = client.post(
            "/api/v1/auth/register",
            json={
                "username": username,
                "password": "register123",
                "email": f"{username}@studioflow.local",
                "display_name": "注册用户",
            },
        )
        assert register.status_code == 200
        data = register.json()
        assert data["ok"] is True
        assert data["account_status"] == "trial"
        assert data["workspace_id"] == "default_workspace"

        login = client.post("/api/v1/auth/login", data={"username": username, "password": "register123"})
        assert login.status_code == 200
        me = client.get("/api/v1/auth/me")
        assert me.status_code == 200
        me_data = me.json()
        assert me_data["authenticated"] is True
        assert me_data["username"] == username
        assert me_data["account_status"] == "trial"
        assert me_data["workspace_id"] == "default_workspace"
    finally:
        settings.auth_enabled = prev_enabled
        settings.auth_provider = prev_provider


def test_local_login_lockout_after_too_many_failures() -> None:
    import app.main as main

    prev_enabled = settings.auth_enabled
    prev_provider = settings.auth_provider
    settings.auth_enabled = True
    settings.auth_provider = "local"
    try:
        main._login_failures_by_user.clear()
        main._login_lock_by_user.clear()
        main._login_attempts_by_ip.clear()
        client = TestClient(app)
        username = f"locked_{uuid4().hex[:8]}"
        for _ in range(5):
            resp = client.post("/api/v1/auth/login", data={"username": username, "password": "wrong"})
            assert resp.status_code == 401
        blocked = client.post("/api/v1/auth/login", data={"username": username, "password": "wrong"})
        assert blocked.status_code == 429
        assert blocked.json().get("code") == "LOGIN_LOCKED"
    finally:
        main._login_failures_by_user.clear()
        main._login_lock_by_user.clear()
        main._login_attempts_by_ip.clear()
        settings.auth_enabled = prev_enabled
        settings.auth_provider = prev_provider
