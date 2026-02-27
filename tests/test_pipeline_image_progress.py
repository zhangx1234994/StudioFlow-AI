import asyncio
from pathlib import Path

import pytest

from app.config import Settings
from app.schemas import (
    AssetSourceType,
    GenerateImagesRequest,
    ProductBrief,
    PromptItem,
    PromptPack,
    ProjectRecord,
    ProjectStatus,
    ScenarioType,
    ShotReference,
    StoryboardStatus,
    TaskRunStatus,
    ToolType,
)
from app.services.assembly_service import AssemblyService
from app.services.compliance_service import ComplianceService
from app.services.pipeline_service import PipelineService
from app.services.sora_service import KieSoraService
from app.services.volc_service import VolcScriptService
from app.store import InMemoryStore, utc_now


class _FakeReferenceImageService:
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
        on_item_done=None,
    ) -> dict[str, ShotReference]:
        refs: dict[str, ShotReference] = {}
        for item in prompts:
            ref = ShotReference(
                shot_id=item.shot_id,
                source="generated",
                image_url=f"https://img.example.com/{item.shot_id}.png",
                local_path=None,
                prompt=item.prompt,
            )
            if on_item_done:
                maybe = on_item_done(item.shot_id, ref)
                if asyncio.iscoroutine(maybe):
                    await maybe
            refs[item.shot_id] = ref
            await asyncio.sleep(0.03)
        return refs


@pytest.mark.asyncio
async def test_image_generation_updates_assets_incrementally(tmp_path: Path) -> None:
    settings = Settings(use_mock_providers=True, storage_root=tmp_path)
    store = InMemoryStore()
    service = PipelineService(
        store=store,
        script_service=VolcScriptService(settings),
        compliance_service=ComplianceService(),
        sora_service=KieSoraService(settings),
        reference_image_service=_FakeReferenceImageService(),
        assembly_service=AssemblyService(settings),
        storage_root=tmp_path,
    )

    image_path = tmp_path / "uploads" / "project-image.png"
    image_path.parent.mkdir(parents=True, exist_ok=True)
    image_path.write_bytes(b"fake")

    now = utc_now()
    project = ProjectRecord(
        project_id="project-image",
        tool_type=ToolType.product_image_suite,
        status=ProjectStatus.scripted,
        task_status=TaskRunStatus.queued,
        created_at=now,
        updated_at=now,
        image_path=str(image_path),
        brief=ProductBrief(product_name="测试产品"),
        scenario_type=ScenarioType.product_image_suite,
        prompt_pack=PromptPack(
            planner_prompt="planner",
            image_prompt_pack=[
                PromptItem(shot_id="shot-1", prompt="镜头1"),
                PromptItem(shot_id="shot-2", prompt="镜头2"),
                PromptItem(shot_id="shot-3", prompt="镜头3"),
            ],
            video_prompt_pack=[],
        ),
    )
    store.add_project(project)

    await service.generate_images_for_project(
        project_id="project-image",
        request=GenerateImagesRequest(async_mode=True, candidates_per_prompt=1),
    )

    await asyncio.sleep(0.05)
    mid_assets = [
        item
        for item in service.list_assets("project-image")
        if item.source_type == AssetSourceType.generated
    ]
    assert 0 < len(mid_assets) < 3

    for _ in range(80):
        current = service.get_project("project-image")
        assert current is not None
        if current.storyboard_status == StoryboardStatus.ready:
            break
        await asyncio.sleep(0.02)

    final_project = service.get_project("project-image")
    assert final_project is not None
    assert final_project.storyboard_status == StoryboardStatus.ready
    final_assets = [
        item
        for item in service.list_assets("project-image")
        if item.source_type == AssetSourceType.generated
    ]
    assert len(final_assets) == 3
