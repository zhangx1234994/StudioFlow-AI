from __future__ import annotations

import asyncio
import logging
from pathlib import Path
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
