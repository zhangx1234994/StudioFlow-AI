from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Awaitable, Callable
from uuid import uuid4

import httpx

from app.config import Settings
from app.services.oss_service import OssService
from app.schemas import ClipVariant, ShotPlan, ShotReference
from app.utils.ffmpeg_tools import make_image_clip

logger = logging.getLogger(__name__)


class KieSoraService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._oss = OssService(settings)

    async def generate_variants(
        self,
        project_id: str,
        image_path: Path,
        image_public_url: str | None,
        shots: list[ShotPlan],
        variants_per_shot: int,
        references: dict[str, ShotReference],
        video_aspect_ratio: str = "portrait",
        video_n_frames: str = "10",
        video_size: str = "standard",
        video_remove_watermark: bool = True,
        video_upload_method: str = "s3",
        on_variant_done: (
            Callable[[ClipVariant, dict[str, int]], Awaitable[None] | None] | None
        ) = None,
    ) -> tuple[dict[str, list[ClipVariant]], str | None]:
        if self._settings.use_mock_providers or not self._settings.kie_api_key:
            return (
                await self._mock_variants(
                    project_id=project_id,
                    fallback_image_path=image_path,
                    shots=shots,
                    variants_per_shot=variants_per_shot,
                    references=references,
                    on_variant_done=on_variant_done,
                ),
                image_public_url,
            )

        try:
            upload_url = image_public_url or await self.upload_image(image_path)
            uploaded_cache: dict[str, str] = {}
            reference_urls: dict[str, str] = {}
            for shot in shots:
                reference_urls[shot.shot_id] = await self._resolve_shot_reference_url(
                    fallback_url=upload_url,
                    references=references,
                    shot_id=shot.shot_id,
                    uploaded_cache=uploaded_cache,
                )

            total_variants = len(shots) * variants_per_shot
            progress = {"total": total_variants, "done": 0, "failed": 0, "running": total_variants}
            progress_lock = asyncio.Lock()
            semaphore = asyncio.Semaphore(max(1, min(self._settings.video_task_concurrency, 20)))
            result: dict[str, list[ClipVariant]] = {}

            async def run_variant(shot: ShotPlan, variant_index: int) -> None:
                task_id: str | None = None
                video_url: str | None = None
                local_path: str | None = None
                async with semaphore:
                    try:
                        task_id = await self.create_image_to_video_task(
                            image_url=reference_urls[shot.shot_id],
                            shot=shot,
                            variant_index=variant_index,
                            video_aspect_ratio=video_aspect_ratio,
                            video_n_frames=video_n_frames,
                            video_size=video_size,
                            video_remove_watermark=video_remove_watermark,
                            video_upload_method=video_upload_method,
                        )
                        logger.info(
                            "KIE video task created: shot=%s variant=%s task_id=%s",
                            shot.shot_id,
                            variant_index + 1,
                            task_id,
                        )
                        video_url = await self.wait_for_task(task_id)
                        if video_url:
                            local = self._render_dir(project_id) / f"{shot.shot_id}_v{variant_index + 1}.mp4"
                            downloaded = await self.download_video(video_url, local)
                            local_path = str(local) if downloaded else None
                            if downloaded and self._oss.enabled:
                                try:
                                    object_key = self._oss.object_key(
                                        "generated",
                                        "videos",
                                        project_id,
                                        f"{shot.shot_id}_v{variant_index + 1}.mp4",
                                    )
                                    video_url = await self._oss.upload_file(
                                        local_path=local,
                                        object_key=object_key,
                                        content_type="video/mp4",
                                    )
                                except Exception as exc:  # pragma: no cover - network instability
                                    logger.warning("Persist video to OSS failed, keep temporary URL: %s", exc)
                            elif self._oss.enabled:
                                try:
                                    object_key = self._oss.build_key_from_url(
                                        video_url,
                                        "generated",
                                        "videos",
                                        project_id,
                                        shot.shot_id,
                                        f"v{variant_index + 1}",
                                        default_ext=".mp4",
                                    )
                                    video_url = await self._oss.mirror_from_url(
                                        source_url=video_url,
                                        object_key=object_key,
                                        content_type="video/mp4",
                                    )
                                except Exception as exc:  # pragma: no cover - network instability
                                    logger.warning("Mirror video URL to OSS failed, keep temporary URL: %s", exc)
                    except Exception as exc:  # pragma: no cover - network instability
                        logger.warning(
                            "KIE variant generation failed: shot=%s variant=%s error=%s",
                            shot.shot_id,
                            variant_index + 1,
                            exc,
                        )
                clip = ClipVariant(
                    shot_id=shot.shot_id,
                    variant_index=variant_index,
                    score=1.0 - 0.1 * variant_index + (0.05 if (video_url or local_path) else -0.3),
                    task_id=task_id,
                    video_url=video_url,
                    local_path=local_path,
                )
                async with progress_lock:
                    variants = list(result.get(shot.shot_id, []))
                    variants = [item for item in variants if item.variant_index != variant_index]
                    variants.append(clip)
                    variants.sort(key=lambda item: item.variant_index)
                    result[shot.shot_id] = variants
                    progress["done"] += 1
                    if not (video_url or local_path):
                        progress["failed"] += 1
                    progress["running"] = max(0, progress["total"] - progress["done"])
                    snapshot = dict(progress)
                if on_variant_done:
                    maybe = on_variant_done(clip, snapshot)
                    if asyncio.iscoroutine(maybe):
                        await maybe

            tasks = [
                asyncio.create_task(run_variant(shot=shot, variant_index=variant_index))
                for shot in shots
                for variant_index in range(variants_per_shot)
            ]
            await asyncio.gather(*tasks)

            has_live_source = any(
                clip.video_url or clip.local_path
                for variants in result.values()
                for clip in variants
            )
            if not has_live_source:
                raise RuntimeError(
                    "KIE video tasks were submitted, but no playable clip was returned."
                )
            return result, upload_url
        except Exception as exc:
            logger.warning("KIE live generation failed: %s", exc)
            raise RuntimeError(f"KIE video generation failed: {exc}") from exc

    async def _resolve_shot_reference_url(
        self,
        fallback_url: str,
        references: dict[str, ShotReference],
        shot_id: str,
        uploaded_cache: dict[str, str],
    ) -> str:
        reference = references.get(shot_id)
        if not reference:
            return fallback_url

        if reference.image_url:
            return reference.image_url

        if reference.local_path:
            path = str(Path(reference.local_path).resolve())
            if path not in uploaded_cache:
                uploaded_cache[path] = await self.upload_image(Path(path))
            return uploaded_cache[path]

        return fallback_url

    async def upload_image(self, image_path: Path) -> str:
        if self._oss.enabled:
            try:
                object_key = self._oss.object_key("inputs", image_path.parent.name, f"{uuid4().hex}_{image_path.name}")
                return await self._oss.upload_file(
                    local_path=image_path,
                    object_key=object_key,
                    content_type="application/octet-stream",
                )
            except Exception as exc:  # pragma: no cover - network instability
                logger.warning("OSS source upload failed, fallback to kie upload: %s", exc)

        headers = {"Authorization": f"Bearer {self._settings.kie_api_key}"}
        candidates = [
            self._settings.kie_upload_base_url.rstrip("/"),
            "https://kieai.redpandaai.co",
        ]
        tried: set[str] = set()
        errors: list[str] = []

        for base in candidates:
            if not base or base in tried:
                continue
            tried.add(base)
            url = f"{base}/api/file-stream-upload"
            try:
                async with httpx.AsyncClient(timeout=90.0) as client:
                    with image_path.open("rb") as f:
                        files = {"file": (image_path.name, f, "application/octet-stream")}
                        data = {"uploadPath": "photo2video", "fileName": image_path.name}
                        response = await client.post(url, headers=headers, files=files, data=data)
                    response.raise_for_status()
                    payload = response.json()
                file_url = self._extract_uploaded_file_url(payload)
                if isinstance(file_url, str):
                    return file_url
                errors.append(f"{url}: missing url in response")
            except Exception as exc:  # pragma: no cover - network instability
                errors.append(f"{url}: {exc}")

        raise RuntimeError(f"KIE image upload failed: {' | '.join(errors)}")

    async def create_image_to_video_task(
        self,
        image_url: str,
        shot: ShotPlan,
        variant_index: int,
        video_aspect_ratio: str = "portrait",
        video_n_frames: str = "10",
        video_size: str = "standard",
        video_remove_watermark: bool = True,
        video_upload_method: str = "s3",
    ) -> str:
        base = self._settings.kie_jobs_base_url.rstrip("/")
        url = f"{base}/createTask"
        headers = {
            "Authorization": f"Bearer {self._settings.kie_api_key}",
            "Content-Type": "application/json",
        }
        duration_sec = max(3, min(8, shot.duration_sec))
        payload: dict[str, Any] = {
            "model": self._settings.kie_video_model,
            "input": {
                "prompt": self._build_shot_prompt(shot, variant_index),
                "image_urls": [image_url],
                "aspect_ratio": video_aspect_ratio,
                "duration": str(duration_sec),
                "n_frames": video_n_frames,
                "size": video_size,
                "remove_watermark": bool(video_remove_watermark),
                "upload_method": video_upload_method,
            },
        }
        if self._settings.kie_callback_url:
            payload["callBackUrl"] = self._settings.kie_callback_url

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        task_id = data.get("data", {}).get("taskId")
        if not isinstance(task_id, str):
            raise RuntimeError(f"KIE create job failed: {data}")
        return task_id

    async def wait_for_task(self, task_id: str) -> str | None:
        base = self._settings.kie_jobs_base_url.rstrip("/")
        url = f"{base}/recordInfo"
        headers = {"Authorization": f"Bearer {self._settings.kie_api_key}"}

        async with httpx.AsyncClient(timeout=60.0) as client:
            for _ in range(self._settings.poll_max_attempts):
                response = await client.get(url, headers=headers, params={"taskId": task_id})
                response.raise_for_status()
                data = response.json()

                state = self._read_task_state(data)
                if state in {"SUCCESS", "COMPLETED"}:
                    return self._read_video_url(data)
                if state in {"FAILED", "FAIL", "CANCELED", "ERROR"}:
                    raise RuntimeError(self._read_task_error(data) or f"Task {task_id} failed")
                await asyncio.sleep(self._settings.poll_interval_seconds)
        raise RuntimeError(f"Task {task_id} timed out after {self._settings.poll_max_attempts} polls")

    async def download_video(self, video_url: str, output_path: Path) -> bool:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            response = await client.get(video_url)
            if response.status_code >= 400:
                return False
            output_path.write_bytes(response.content)
        return True

    def _read_task_state(self, data: dict[str, Any]) -> str:
        task = data.get("data", {}) if isinstance(data.get("data"), dict) else {}
        for key in ("state", "status", "taskStatus"):
            value = task.get(key)
            if isinstance(value, str):
                return value.upper()
        return "PENDING"

    def _read_video_url(self, data: dict[str, Any]) -> str | None:
        task = data.get("data", {}) if isinstance(data.get("data"), dict) else {}
        result = task.get("resultJson")
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except json.JSONDecodeError:
                result = None
        if isinstance(result, dict):
            for key in ("resultUrls", "video_urls", "videos"):
                urls = result.get(key)
                if isinstance(urls, list) and urls and isinstance(urls[0], str):
                    return urls[0]
            for key in ("resultUrl", "video_url"):
                value = result.get(key)
                if isinstance(value, str):
                    return value

        direct = task.get("resultUrls")
        if isinstance(direct, list) and direct and isinstance(direct[0], str):
            return direct[0]
        for key in ("resultUrl", "videoUrl", "video_url"):
            value = task.get(key)
            if isinstance(value, str):
                return value
        return None

    def _read_task_error(self, data: dict[str, Any]) -> str | None:
        task = data.get("data", {}) if isinstance(data.get("data"), dict) else {}
        for key in ("failMsg", "errorMessage", "message", "msg"):
            value = task.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

        result = task.get("resultJson")
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except json.JSONDecodeError:
                result = None
        if isinstance(result, dict):
            for key in ("error", "errorMessage", "message"):
                value = result.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return None

    def _extract_uploaded_file_url(self, payload: dict[str, Any]) -> str | None:
        data = payload.get("data")
        if isinstance(data, dict):
            for key in ("url", "downloadUrl", "fileUrl"):
                value = data.get(key)
                if isinstance(value, str):
                    return value
        for key in ("url", "downloadUrl"):
            value = payload.get(key)
            if isinstance(value, str):
                return value
        return None

    def _build_shot_prompt(self, shot: ShotPlan, _variant_index: int) -> str:
        motion = shot.motion_direction or ""
        voice = shot.voiceover_direction or ""
        segments = [
            shot.visual_prompt.strip(),
            f"动作与运镜：{motion.strip()}" if motion.strip() else "",
            f"口播表达：{voice.strip()}" if voice.strip() else "",
            "与参考分镜保持主体一致和场景连续。",
            "画面真实自然，避免夸张广告感。",
            "No text, no subtitles, no captions, no logo, no watermark, no letters, no UI overlays.",
        ]
        return " ".join([item for item in segments if item])

    async def _mock_variants(
        self,
        project_id: str,
        fallback_image_path: Path,
        shots: list[ShotPlan],
        variants_per_shot: int,
        references: dict[str, ShotReference],
        on_variant_done: (
            Callable[[ClipVariant, dict[str, int]], Awaitable[None] | None] | None
        ) = None,
    ) -> dict[str, list[ClipVariant]]:
        total_variants = len(shots) * variants_per_shot
        done_count = 0
        failed_count = 0
        output: dict[str, list[ClipVariant]] = {}
        for shot in shots:
            reference = references.get(shot.shot_id)
            shot_image_path = (
                Path(reference.local_path)
                if reference and reference.local_path
                else fallback_image_path
            )
            variants: list[ClipVariant] = []
            for variant_index in range(variants_per_shot):
                clip_path = (
                    self._render_dir(project_id)
                    / f"{shot.shot_id}_v{variant_index + 1}.mp4"
                )
                ok = make_image_clip(shot_image_path, clip_path, shot.duration_sec)
                variants.append(
                    ClipVariant(
                        shot_id=shot.shot_id,
                        variant_index=variant_index,
                        score=1.0 - (variant_index * 0.05) + (0.05 if ok else -0.4),
                        local_path=str(clip_path) if ok else None,
                    )
                )
                done_count += 1
                if not ok:
                    failed_count += 1
                if on_variant_done:
                    clip = variants[-1]
                    progress = {
                        "total": total_variants,
                        "done": done_count,
                        "failed": failed_count,
                        "running": max(0, total_variants - done_count),
                    }
                    maybe = on_variant_done(clip, progress)
                    if asyncio.iscoroutine(maybe):
                        await maybe
            output[shot.shot_id] = variants
        return output

    def _render_dir(self, project_id: str) -> Path:
        path = self._settings.storage_root / "renders" / project_id
        path.mkdir(parents=True, exist_ok=True)
        return path
