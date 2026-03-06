from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Awaitable, Callable

import httpx

from app.config import Settings
from app.services.oss_service import OssService
from app.schemas import PromptItem, ScriptOption, ShotPlan, ShotReference

logger = logging.getLogger(__name__)


class ReferenceImageService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._oss = OssService(settings)

    async def generate_storyboard(
        self,
        project_id: str,
        image_path: Path,
        image_public_url: str | None,
        script: ScriptOption,
        image_aspect_ratio: str | None = None,
        image_resolution: str | None = None,
        image_output_format: str | None = None,
        on_shot_done: Callable[[str, ShotReference], Awaitable[None] | None] | None = None,
    ) -> dict[str, ShotReference]:
        fallback_refs = self._build_original_references(
            image_path=image_path,
            image_public_url=image_public_url,
            script=script,
        )

        if self._settings.use_mock_providers or not self._settings.kie_api_key:
            if on_shot_done:
                for shot in script.shots:
                    reference = fallback_refs[shot.shot_id]
                    maybe = on_shot_done(shot.shot_id, reference)
                    if asyncio.iscoroutine(maybe):
                        await maybe
            return fallback_refs

        try:
            source_image_url = image_public_url or await self._upload_image(image_path)
        except Exception as exc:  # pragma: no cover - network instability
            logger.warning("Storyboard source upload failed, fallback to original: %s", exc)
            return fallback_refs

        concurrency = max(1, min(self._settings.storyboard_concurrency, 4))
        semaphore = asyncio.Semaphore(concurrency)

        async def build_one(shot: ShotPlan) -> tuple[str, ShotReference]:
            prompt = self._build_shot_prompt(shot)
            async with semaphore:
                image_url = await self._generate_single_storyboard_image(
                    image_input_urls=[source_image_url],
                    prompt=prompt,
                    image_aspect_ratio=image_aspect_ratio,
                    image_resolution=image_resolution,
                    image_output_format=image_output_format,
                )
            if image_url:
                persisted_url = await self._persist_generated_image(
                    project_id=project_id,
                    shot_id=shot.shot_id,
                    source_url=image_url,
                )
                return (
                    shot.shot_id,
                    ShotReference(
                        shot_id=shot.shot_id,
                        source="generated",
                        image_url=persisted_url,
                        local_path=None,
                        prompt=prompt,
                    ),
                )
            return (
                shot.shot_id,
                ShotReference(
                    shot_id=shot.shot_id,
                    source="original",
                    image_url=source_image_url,
                    local_path=str(image_path),
                    prompt=prompt,
                ),
            )

        tasks = [asyncio.create_task(build_one(shot)) for shot in script.shots]
        references: dict[str, ShotReference] = {}
        for task in asyncio.as_completed(tasks):
            shot_id, reference = await task
            references[shot_id] = reference
            if on_shot_done:
                maybe = on_shot_done(shot_id, reference)
                if asyncio.iscoroutine(maybe):
                    await maybe

        return {
            shot.shot_id: references[shot.shot_id]
            for shot in script.shots
            if shot.shot_id in references
        }

    async def generate_storyboard_shot(
        self,
        image_path: Path,
        image_public_url: str | None,
        shot: ShotPlan,
        image_aspect_ratio: str | None = None,
        image_resolution: str | None = None,
        image_output_format: str | None = None,
    ) -> ShotReference:
        fallback = ShotReference(
            shot_id=shot.shot_id,
            source="original",
            image_url=image_public_url,
            local_path=str(image_path),
            prompt=shot.reference_image_prompt or shot.visual_prompt,
        )
        if self._settings.use_mock_providers or not self._settings.kie_api_key:
            return fallback

        try:
            source_image_url = image_public_url or await self._upload_image(image_path)
        except Exception as exc:  # pragma: no cover - network instability
            logger.warning("Storyboard shot source upload failed: %s", exc)
            return fallback

        prompt = self._build_shot_prompt(shot)
        image_url = await self._generate_single_storyboard_image(
            image_input_urls=[source_image_url],
            prompt=prompt,
            image_aspect_ratio=image_aspect_ratio,
            image_resolution=image_resolution,
            image_output_format=image_output_format,
        )
        if image_url:
            persisted_url = await self._persist_generated_image(
                project_id=image_path.stem,
                shot_id=shot.shot_id,
                source_url=image_url,
            )
            return ShotReference(
                shot_id=shot.shot_id,
                source="generated",
                image_url=persisted_url,
                local_path=None,
                prompt=prompt,
            )
        return ShotReference(
            shot_id=shot.shot_id,
            source="original",
            image_url=source_image_url,
            local_path=str(image_path),
            prompt=prompt,
        )

    async def generate_images_from_prompts(
        self,
        image_path: Path,
        image_public_url: str | None,
        prompts: list[PromptItem],
        image_aspect_ratio: str | None = None,
        image_resolution: str | None = None,
        image_output_format: str | None = None,
        reference_image_urls: list[str] | None = None,
        reference_image_paths: list[Path] | None = None,
        on_item_done: Callable[[str, ShotReference], Awaitable[None] | None] | None = None,
    ) -> dict[str, ShotReference]:
        fallback: dict[str, ShotReference] = {}
        for item in prompts:
            fallback[item.shot_id] = ShotReference(
                shot_id=item.shot_id,
                source="original",
                image_url=image_public_url,
                local_path=str(image_path),
                prompt=item.prompt,
            )

        if not prompts:
            return fallback

        if self._settings.use_mock_providers or not self._settings.kie_api_key:
            if on_item_done:
                for shot_id, ref in fallback.items():
                    maybe = on_item_done(shot_id, ref)
                    if asyncio.iscoroutine(maybe):
                        await maybe
            return fallback

        try:
            source_image_url = image_public_url or await self._upload_image(image_path)
        except Exception as exc:  # pragma: no cover - network instability
            logger.warning("Prompt image source upload failed: %s", exc)
            return fallback

        image_input_urls: list[str] = [source_image_url]
        for url in reference_image_urls or []:
            value = str(url or "").strip()
            if value and value not in image_input_urls:
                image_input_urls.append(value)
        for ref_path in reference_image_paths or []:
            try:
                uploaded = await self._upload_image(ref_path)
                if uploaded and uploaded not in image_input_urls:
                    image_input_urls.append(uploaded)
            except Exception as exc:  # pragma: no cover - network instability
                logger.warning("Reference image upload failed: %s", exc)
        image_input_urls = image_input_urls[:8]

        task_count = len(prompts)
        concurrency = max(1, min(self._settings.storyboard_concurrency, 8, task_count))
        semaphore = asyncio.Semaphore(concurrency)

        async def _run(item: PromptItem) -> tuple[str, ShotReference]:
            async with semaphore:
                image_url = await self._generate_single_storyboard_image(
                    image_input_urls=image_input_urls,
                    prompt=item.prompt,
                    image_aspect_ratio=image_aspect_ratio,
                    image_resolution=image_resolution,
                    image_output_format=image_output_format,
                )
            if image_url:
                persisted_url = await self._persist_generated_image(
                    project_id=image_path.stem,
                    shot_id=item.shot_id,
                    source_url=image_url,
                )
                return (
                    item.shot_id,
                    ShotReference(
                        shot_id=item.shot_id,
                        source="generated",
                        image_url=persisted_url,
                        local_path=None,
                        prompt=item.prompt,
                    ),
                )
            return item.shot_id, fallback[item.shot_id]

        tasks = [asyncio.create_task(_run(item)) for item in prompts]
        result: dict[str, ShotReference] = {}
        for task in asyncio.as_completed(tasks):
            shot_id, ref = await task
            result[shot_id] = ref
            if on_item_done:
                maybe = on_item_done(shot_id, ref)
                if asyncio.iscoroutine(maybe):
                    await maybe
        return result

    def _build_original_references(
        self,
        image_path: Path,
        image_public_url: str | None,
        script: ScriptOption,
    ) -> dict[str, ShotReference]:
        refs: dict[str, ShotReference] = {}
        for shot in script.shots:
            refs[shot.shot_id] = ShotReference(
                shot_id=shot.shot_id,
                source="original",
                image_url=image_public_url,
                local_path=str(image_path),
                prompt=shot.reference_image_prompt or shot.visual_prompt,
            )
        return refs

    async def _generate_single_storyboard_image(
        self,
        image_input_urls: list[str],
        prompt: str,
        image_aspect_ratio: str | None = None,
        image_resolution: str | None = None,
        image_output_format: str | None = None,
    ) -> str | None:
        max_attempts = max(1, min(3, int(self._settings.image_task_retry_attempts or 2)))
        for attempt in range(1, max_attempts + 1):
            try:
                task_id = await self._create_task(
                    image_input_urls=image_input_urls,
                    prompt=prompt,
                    image_aspect_ratio=image_aspect_ratio,
                    image_resolution=image_resolution,
                    image_output_format=image_output_format,
                )
                image_url = await self._wait_task_result(task_id)
                if image_url:
                    return image_url
                logger.warning(
                    "Storyboard image generation returned empty result "
                    "(attempt=%s/%s, task_id=%s)",
                    attempt,
                    max_attempts,
                    task_id,
                )
            except Exception as exc:  # pragma: no cover - network instability
                logger.warning(
                    "Storyboard image generation failed "
                    "(attempt=%s/%s, error_type=%s, detail=%r)",
                    attempt,
                    max_attempts,
                    type(exc).__name__,
                    exc,
                )
            if attempt < max_attempts:
                await asyncio.sleep(float(attempt))
        return None

    async def _create_task(
        self,
        image_input_urls: list[str],
        prompt: str,
        image_aspect_ratio: str | None = None,
        image_resolution: str | None = None,
        image_output_format: str | None = None,
    ) -> str:
        url = f"{self._settings.kie_market_base_url}/api/v1/jobs/createTask"
        headers = {
            "Authorization": f"Bearer {self._settings.kie_api_key}",
            "Content-Type": "application/json",
        }
        input_payload: dict[str, Any] = {
            "prompt": prompt,
            "image_input": image_input_urls[:8],
            "aspect_ratio": image_aspect_ratio or "9:16",
            "output_format": image_output_format or self._settings.kie_image_output_format,
        }
        if image_resolution:
            input_payload["resolution"] = image_resolution
        payload: dict[str, Any] = {
                "model": self._settings.kie_image_model,
                "input": input_payload,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code >= 400:
                snippet = response.text[:240].replace("\n", " ")
                raise RuntimeError(f"createTask failed ({response.status_code}): {snippet}")
            try:
                data = response.json()
            except Exception as exc:
                snippet = response.text[:240].replace("\n", " ")
                raise RuntimeError(f"createTask invalid JSON response: {snippet}") from exc

        task_id = data.get("data", {}).get("taskId")
        if not isinstance(task_id, str):
            raise RuntimeError(f"Invalid storyboard createTask response: {data}")
        return task_id

    async def _wait_task_result(self, task_id: str) -> str | None:
        url = f"{self._settings.kie_jobs_base_url}/recordInfo"
        headers = {"Authorization": f"Bearer {self._settings.kie_api_key}"}
        poll_interval = max(1.0, float(self._settings.poll_interval_seconds))
        timeout_seconds = max(20.0, float(self._settings.image_task_timeout_seconds))
        max_attempts_by_timeout = max(1, int(timeout_seconds // poll_interval))
        max_attempts = min(self._settings.poll_max_attempts, max_attempts_by_timeout)

        async with httpx.AsyncClient(timeout=60.0) as client:
            for _ in range(max_attempts):
                response = await client.get(url, headers=headers, params={"taskId": task_id})
                if response.status_code >= 400:
                    snippet = response.text[:240].replace("\n", " ")
                    raise RuntimeError(
                        f"recordInfo failed ({response.status_code}, task_id={task_id}): {snippet}"
                    )
                try:
                    data = response.json()
                except Exception as exc:
                    snippet = response.text[:240].replace("\n", " ")
                    raise RuntimeError(
                        f"recordInfo invalid JSON (task_id={task_id}): {snippet}"
                    ) from exc

                state = self._read_task_state(data)
                if state in {"SUCCESS", "COMPLETED"}:
                    return self._extract_image_url(data)
                if state in {"FAILED", "CANCELED", "ERROR"}:
                    logger.warning(
                        "Storyboard task failed in provider response (task_id=%s, state=%s)",
                        task_id,
                        state,
                    )
                    return None
                await asyncio.sleep(poll_interval)
        logger.warning(
            "Storyboard task polling timeout (task_id=%s, attempts=%s, timeout_seconds=%s)",
            task_id,
            max_attempts,
            timeout_seconds,
        )
        return None

    def _read_task_state(self, data: dict[str, Any]) -> str:
        task = data.get("data", {}) if isinstance(data.get("data"), dict) else {}
        for key in ("state", "status", "taskStatus"):
            value = task.get(key)
            if isinstance(value, str):
                return value.upper()
        return "PENDING"

    def _extract_image_url(self, data: dict[str, Any]) -> str | None:
        task = data.get("data", {}) if isinstance(data.get("data"), dict) else {}

        direct = task.get("resultUrls")
        if isinstance(direct, list) and direct and isinstance(direct[0], str):
            return direct[0]

        result_json = task.get("resultJson")
        if isinstance(result_json, str):
            try:
                result_json = json.loads(result_json)
            except json.JSONDecodeError:
                result_json = None
        if isinstance(result_json, dict):
            urls = result_json.get("resultUrls")
            if isinstance(urls, list) and urls and isinstance(urls[0], str):
                return urls[0]
            images = result_json.get("images")
            if isinstance(images, list) and images and isinstance(images[0], str):
                return images[0]
        return None

    async def _upload_image(self, image_path: Path) -> str:
        if self._oss.enabled:
            try:
                object_key = self._oss.object_key("inputs", image_path.name)
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
                uploaded_url = self._extract_uploaded_file_url(payload)
                if uploaded_url:
                    return uploaded_url
                errors.append(f"{url}: missing url in response")
            except Exception as exc:  # pragma: no cover - network instability
                errors.append(f"{url}: {exc}")

        raise RuntimeError(f"Upload response missing URL: {' | '.join(errors)}")

    async def _persist_generated_image(self, project_id: str, shot_id: str, source_url: str) -> str:
        if not self._oss.enabled:
            return source_url
        try:
            object_key = self._oss.build_key_from_url(
                source_url,
                "generated",
                "images",
                project_id,
                shot_id,
                default_ext=".png",
            )
            return await self._oss.mirror_from_url(source_url=source_url, object_key=object_key)
        except Exception as exc:  # pragma: no cover - network instability
            logger.warning("Persist generated image to OSS failed, keep temporary URL: %s", exc)
            return source_url

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

    def _build_shot_prompt(self, shot: ShotPlan) -> str:
        image_prompt = shot.reference_image_prompt or shot.visual_prompt
        return (
            f"{image_prompt}。"
            f"镜头意图：{shot.narration}。"
            f"用于{shot.stage.value}阶段静态分镜关键帧，表达该镜头核心卖点。"
            "保留主体一致性，画面真实自然，不要文字、字幕、logo、水印。"
        )
