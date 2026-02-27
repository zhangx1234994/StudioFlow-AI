import asyncio
from pathlib import Path
from typing import Any

from app.config import Settings
from app.schemas import ShotPlan, ShotReference, ShotStage
from app.services.sora_service import KieSoraService


def _build_settings(tmp_path: Path) -> Settings:
    return Settings(
        use_mock_providers=False,
        kie_api_key="test-key",
        storage_root=tmp_path,
        poll_interval_seconds=0.0,
        poll_max_attempts=1,
    )


def _build_shot() -> ShotPlan:
    return ShotPlan(
        shot_id="shot-1",
        stage=ShotStage.feature,
        duration_sec=4,
        visual_prompt="产品中景，轻推镜头",
        reference_image_prompt="产品主体清晰",
        narration="展示使用细节",
        on_screen_text="细节更清楚",
    )


def test_create_image_to_video_task_uses_create_task_endpoint(monkeypatch, tmp_path: Path) -> None:
    service = KieSoraService(_build_settings(tmp_path))
    calls: list[dict[str, Any]] = []

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, Any]:
            return {"data": {"taskId": "task-123"}}

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def post(self, url: str, headers=None, json=None):
            calls.append({"url": url, "headers": headers, "json": json})
            return FakeResponse()

    monkeypatch.setattr("app.services.sora_service.httpx.AsyncClient", FakeClient)

    task_id = asyncio.run(
        service.create_image_to_video_task(
            image_url="https://example.com/input.png",
            shot=_build_shot(),
            variant_index=0,
        )
    )

    assert task_id == "task-123"
    assert calls
    assert calls[0]["url"].endswith("/api/v1/jobs/createTask")
    assert calls[0]["json"]["model"] == "sora-2-image-to-video"
    assert calls[0]["json"]["input"]["aspect_ratio"] == "portrait"


def test_wait_for_task_uses_record_info_and_parses_video_url(monkeypatch, tmp_path: Path) -> None:
    service = KieSoraService(_build_settings(tmp_path))
    calls: list[dict[str, Any]] = []

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, Any]:
            return {
                "data": {
                    "status": "SUCCESS",
                    "resultJson": '{"resultUrls":["https://cdn.example.com/video.mp4"]}',
                }
            }

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def get(self, url: str, headers=None, params=None):
            calls.append({"url": url, "headers": headers, "params": params})
            return FakeResponse()

    monkeypatch.setattr("app.services.sora_service.httpx.AsyncClient", FakeClient)

    video_url = asyncio.run(service.wait_for_task("task-abc"))
    assert video_url == "https://cdn.example.com/video.mp4"
    assert calls
    assert calls[0]["url"].endswith("/api/v1/jobs/recordInfo")
    assert calls[0]["params"] == {"taskId": "task-abc"}


def test_generate_variants_raises_if_no_live_clip(monkeypatch, tmp_path: Path) -> None:
    service = KieSoraService(_build_settings(tmp_path))
    shot = _build_shot()

    async def fake_upload(self, image_path: Path) -> str:
        return "https://example.com/upload.png"

    async def fake_resolve(self, fallback_url, references, shot_id, uploaded_cache) -> str:
        return fallback_url

    async def fake_create(self, image_url: str, shot: ShotPlan, variant_index: int, **kwargs) -> str:
        return f"task-{variant_index}"

    async def fake_wait(self, task_id: str) -> str | None:
        return None

    monkeypatch.setattr(KieSoraService, "upload_image", fake_upload)
    monkeypatch.setattr(KieSoraService, "_resolve_shot_reference_url", fake_resolve)
    monkeypatch.setattr(KieSoraService, "create_image_to_video_task", fake_create)
    monkeypatch.setattr(KieSoraService, "wait_for_task", fake_wait)

    try:
        asyncio.run(
            service.generate_variants(
                project_id="p1",
                image_path=tmp_path / "input.png",
                image_public_url=None,
                shots=[shot],
                variants_per_shot=1,
                references={},
            )
        )
        raise AssertionError("Expected RuntimeError when no live clip is returned")
    except RuntimeError as exc:
        assert "no playable clip" in str(exc).lower()


def test_generate_variants_returns_live_video_url(monkeypatch, tmp_path: Path) -> None:
    service = KieSoraService(_build_settings(tmp_path))
    shot = _build_shot()

    async def fake_upload(self, image_path: Path) -> str:
        return "https://example.com/upload.png"

    async def fake_resolve(self, fallback_url, references, shot_id, uploaded_cache) -> str:
        return fallback_url

    async def fake_create(self, image_url: str, shot: ShotPlan, variant_index: int, **kwargs) -> str:
        return f"task-{variant_index}"

    async def fake_wait(self, task_id: str) -> str | None:
        return "https://cdn.example.com/live.mp4"

    async def fake_download(self, video_url: str, output_path: Path) -> bool:
        return False

    monkeypatch.setattr(KieSoraService, "upload_image", fake_upload)
    monkeypatch.setattr(KieSoraService, "_resolve_shot_reference_url", fake_resolve)
    monkeypatch.setattr(KieSoraService, "create_image_to_video_task", fake_create)
    monkeypatch.setattr(KieSoraService, "wait_for_task", fake_wait)
    monkeypatch.setattr(KieSoraService, "download_video", fake_download)

    variants, image_url = asyncio.run(
        service.generate_variants(
            project_id="p2",
            image_path=tmp_path / "input.png",
            image_public_url=None,
            shots=[shot],
            variants_per_shot=1,
            references={"shot-1": ShotReference(shot_id="shot-1", source="generated")},
        )
    )

    assert image_url == "https://example.com/upload.png"
    assert "shot-1" in variants
    assert variants["shot-1"][0].task_id == "task-0"
    assert variants["shot-1"][0].video_url == "https://cdn.example.com/live.mp4"


def test_build_shot_prompt_enforces_no_text(tmp_path: Path) -> None:
    service = KieSoraService(_build_settings(tmp_path))
    prompt = service._build_shot_prompt(_build_shot(), 0)
    assert "字幕" not in prompt
    assert "No text, no subtitles" in prompt
