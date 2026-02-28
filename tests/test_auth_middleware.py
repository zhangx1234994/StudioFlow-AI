import os
from dataclasses import dataclass

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

    async def verify_access_token(self, access_token: str):
        if access_token in {"ok-access", "refreshed-access"}:
            return {"username": "admin", "email": "admin@studioflow.local"}
        return None

    async def refresh_session(self, refresh_token: str):
        if refresh_token != "ok-refresh":
            raise ValueError("refresh failed")
        return _FakeSession(
            access_token="refreshed-access",
            refresh_token="refreshed-refresh",
            expires_in=3600,
            username="admin",
            email="admin@studioflow.local",
        )

    async def sign_in_with_password(self, username_or_email: str, password: str):
        return _FakeSession(
            access_token="ok-access",
            refresh_token="ok-refresh",
            expires_in=3600,
            username="admin",
            email="admin@studioflow.local",
        )

    async def sign_out(self, access_token: str):
        return None


def test_middleware_rejects_unauthorized_api(monkeypatch) -> None:
    import app.main as main

    prev_enabled = settings.auth_enabled
    prev_provider = settings.auth_provider
    monkeypatch.setattr(main, "auth_service", _FakeAuthService())
    settings.auth_enabled = True
    settings.auth_provider = "supabase"

    client = TestClient(app)
    resp = client.get("/api/v1/ui/tool-meta")
    assert resp.status_code == 401
    payload = resp.json()
    assert payload["code"] == "UNAUTHORIZED"
    assert payload["request_id"]

    settings.auth_enabled = prev_enabled
    settings.auth_provider = prev_provider


def test_middleware_allows_refresh_flow(monkeypatch) -> None:
    import app.main as main

    prev_enabled = settings.auth_enabled
    prev_provider = settings.auth_provider
    monkeypatch.setattr(main, "auth_service", _FakeAuthService())
    settings.auth_enabled = True
    settings.auth_provider = "supabase"

    client = TestClient(app)
    client.cookies.set("refresh_token", "ok-refresh")
    resp = client.get("/api/v1/ui/tool-meta")
    assert resp.status_code == 200
    assert "access_token=" in resp.headers.get("set-cookie", "")

    settings.auth_enabled = prev_enabled
    settings.auth_provider = prev_provider
