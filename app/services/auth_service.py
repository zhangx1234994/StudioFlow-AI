from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from app.config import Settings


@dataclass
class AuthSession:
    access_token: str
    refresh_token: str
    expires_in: int
    username: str
    email: str
    expires_at: datetime | None = None


class AuthService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._base_url = (settings.supabase_url or "").rstrip("/")
        self._anon_key = settings.supabase_anon_key or ""
        self._service_key = settings.supabase_service_role_key or ""

    @property
    def is_configured(self) -> bool:
        if self._settings.auth_provider != "supabase":
            return False
        return bool(self._base_url and self._anon_key and self._service_key)

    async def sign_in_with_password(self, username_or_email: str, password: str) -> AuthSession:
        email = self._normalize_email(username_or_email)
        payload = {"email": email, "password": password}
        data = await self._post_auth_token(grant_type="password", payload=payload)
        user = data.get("user") or {}
        return self._build_session(data=data, fallback_email=email, fallback_username=username_or_email, user=user)

    async def refresh_session(self, refresh_token: str) -> AuthSession:
        payload = {"refresh_token": refresh_token}
        data = await self._post_auth_token(grant_type="refresh_token", payload=payload)
        user = data.get("user") or {}
        return self._build_session(data=data, fallback_email=str(user.get("email") or ""), fallback_username=str(user.get("email") or ""), user=user)

    async def verify_access_token(self, access_token: str) -> dict[str, Any] | None:
        if not access_token or not self.is_configured:
            return None
        headers = {
            "apikey": self._anon_key,
            "Authorization": f"Bearer {access_token}",
        }
        timeout = httpx.Timeout(10.0, connect=5.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(f"{self._base_url}/auth/v1/user", headers=headers)
        if resp.status_code >= 400:
            return None
        payload = resp.json()
        email = str(payload.get("email") or "")
        return {
            "user_id": str(payload.get("id") or ""),
            "email": email,
            "username": self._display_username_from_email(email),
            "raw": payload,
        }

    async def sign_out(self, access_token: str) -> None:
        if not access_token or not self.is_configured:
            return
        headers = {
            "apikey": self._anon_key,
            "Authorization": f"Bearer {access_token}",
        }
        timeout = httpx.Timeout(10.0, connect=5.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            await client.post(f"{self._base_url}/auth/v1/logout", headers=headers)

    async def _post_auth_token(self, grant_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.is_configured:
            raise ValueError("Supabase auth is not configured.")
        headers = {
            "apikey": self._anon_key,
            "Authorization": f"Bearer {self._service_key}",
            "Content-Type": "application/json",
        }
        timeout = httpx.Timeout(15.0, connect=5.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{self._base_url}/auth/v1/token",
                params={"grant_type": grant_type},
                headers=headers,
                json=payload,
            )
        if resp.status_code >= 400:
            detail = "Supabase auth request failed."
            try:
                err = resp.json()
                detail = str(err.get("msg") or err.get("error_description") or err.get("error") or detail)
            except Exception:
                pass
            if resp.status_code in (400, 401):
                raise ValueError("Invalid credentials") from None
            raise RuntimeError(detail)
        return resp.json()

    def _normalize_email(self, username_or_email: str) -> str:
        value = (username_or_email or "").strip().lower()
        if "@" in value:
            return value
        if value == (self._settings.admin_username or "admin").strip().lower():
            return (self._settings.admin_email or "admin@studioflow.local").strip().lower()
        return f"{value}@studioflow.local"

    def _display_username_from_email(self, email: str) -> str:
        normalized = (email or "").strip().lower()
        if normalized == (self._settings.admin_email or "admin@studioflow.local").strip().lower():
            return self._settings.admin_username or "admin"
        return normalized.split("@", 1)[0] if "@" in normalized else (normalized or "user")

    def _build_session(
        self,
        *,
        data: dict[str, Any],
        fallback_email: str,
        fallback_username: str,
        user: dict[str, Any],
    ) -> AuthSession:
        access_token = str(data.get("access_token") or "")
        refresh_token = str(data.get("refresh_token") or "")
        expires_in = int(data.get("expires_in") or 3600)
        email = str(user.get("email") or fallback_email or "")
        username = self._display_username_from_email(email) if email else (fallback_username or "user")
        expires_at = datetime.fromtimestamp(
            datetime.now(timezone.utc).timestamp() + max(1, expires_in),
            tz=timezone.utc,
        )
        return AuthSession(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
            username=username,
            email=email,
            expires_at=expires_at,
        )
