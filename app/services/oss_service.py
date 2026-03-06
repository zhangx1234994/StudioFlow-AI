from __future__ import annotations

import asyncio
import base64
import hmac
import json
import logging
from datetime import datetime, timezone
from hashlib import sha1
from pathlib import Path
from time import time
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)

try:  # pragma: no cover - optional dependency
    import oss2
except Exception:  # pragma: no cover - optional dependency
    oss2 = None


class OssService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._enabled = False
        self._bucket = None
        self._public_base = ""
        self._upload_base = ""
        self._prefix = str(settings.oss_root_prefix or "").strip().strip("/")

        if not all(
            [
                settings.oss_access_key,
                settings.oss_secret_key,
                settings.oss_bucket,
                settings.oss_endpoint,
            ]
        ):
            return
        if oss2 is None:
            logger.warning("oss2 is not installed; OSS integration disabled.")
            return

        auth = oss2.Auth(settings.oss_access_key, settings.oss_secret_key)
        endpoint = settings.oss_endpoint or "oss-cn-hangzhou.aliyuncs.com"
        self._bucket = oss2.Bucket(auth, f"https://{endpoint}", settings.oss_bucket)
        self._enabled = True
        self._upload_base = f"https://{settings.oss_bucket}.{endpoint}"

        public_domain = (settings.oss_public_domain or "").strip().rstrip("/")
        if public_domain:
            self._public_base = public_domain
        else:
            self._public_base = f"https://{settings.oss_bucket}.{endpoint}"

    @property
    def enabled(self) -> bool:
        return self._enabled and self._bucket is not None

    def object_key(self, *parts: Any, suffix: str = "") -> str:
        items = [str(p).strip("/") for p in parts if str(p).strip("/")]
        raw = "/".join(items)
        if self._prefix:
            raw = f"{self._prefix}/{raw}" if raw else self._prefix
        if suffix and not raw.endswith(suffix):
            raw = f"{raw}{suffix}"
        return raw

    def sign_post(
        self,
        object_key: str,
        expire_seconds: int = 300,
        max_size_mb: int = 20,
    ) -> dict[str, Any]:
        if not self.enabled:
            raise RuntimeError("OSS is not enabled")
        access_key = self._settings.oss_access_key or ""
        secret_key = self._settings.oss_secret_key or ""
        if not access_key or not secret_key:
            raise RuntimeError("OSS credentials missing")
        expires_at = int(time()) + max(60, expire_seconds)
        expiration = datetime.fromtimestamp(expires_at, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        policy = {
            "expiration": expiration,
            "conditions": [
                ["eq", "$key", object_key],
                ["content-length-range", 1, max_size_mb * 1024 * 1024],
            ],
        }
        policy_encoded = base64.b64encode(json.dumps(policy).encode("utf-8")).decode("utf-8")
        signature = base64.b64encode(
            hmac.new(secret_key.encode("utf-8"), policy_encoded.encode("utf-8"), sha1).digest()
        ).decode("utf-8")
        return {
            "upload_url": self._upload_base,
            "access_id": access_key,
            "policy": policy_encoded,
            "signature": signature,
            "key": object_key,
            "expire_at": expires_at,
            "public_url": f"{self._public_base}/{object_key}",
        }

    async def upload_file(self, local_path: Path, object_key: str, content_type: str | None = None) -> str:
        if not self.enabled:
            raise RuntimeError("OSS is not enabled")
        headers = {"Content-Type": content_type} if content_type else None
        await asyncio.to_thread(
            self._bucket.put_object_from_file,  # type: ignore[union-attr]
            object_key,
            str(local_path),
            headers=headers,
        )
        return f"{self._public_base}/{object_key}"

    async def upload_bytes(self, payload: bytes, object_key: str, content_type: str | None = None) -> str:
        if not self.enabled:
            raise RuntimeError("OSS is not enabled")
        headers = {"Content-Type": content_type} if content_type else None
        await asyncio.to_thread(
            self._bucket.put_object,  # type: ignore[union-attr]
            object_key,
            payload,
            headers=headers,
        )
        return f"{self._public_base}/{object_key}"

    async def mirror_from_url(
        self,
        source_url: str,
        object_key: str,
        content_type: str | None = None,
        timeout: float = 120.0,
    ) -> str:
        if not self.enabled:
            raise RuntimeError("OSS is not enabled")
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(source_url)
            response.raise_for_status()
            payload = response.content
            inferred_type = content_type or response.headers.get("content-type")
        return await self.upload_bytes(payload, object_key=object_key, content_type=inferred_type)

    def build_key_from_url(self, source_url: str, *parts: Any, default_ext: str = ".bin") -> str:
        parsed = urlsplit(source_url)
        source_name = Path(parsed.path).name or f"{uuid4().hex}{default_ext}"
        if "." not in source_name:
            source_name = f"{source_name}{default_ext}"
        return self.object_key(*parts, source_name)
