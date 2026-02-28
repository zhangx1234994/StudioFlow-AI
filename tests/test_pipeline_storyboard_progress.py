import asyncio
from pathlib import Path

import pytest

from app.config import Settings
from app.schemas import (
    ProductBrief,
    ProjectRecord,
    ProjectStatus,
    ScriptOption,
    ShotPlan,
    ShotReference,
    ShotStage,
    StoryboardStatus,
)
from app.services.assembly_service import AssemblyService
from app.services.compliance_service import ComplianceService
from app.services.pipeline_service import PipelineService
from app.services.sora_service import KieSoraService
from app.services.volc_service import VolcScriptService
from app.store import InMemoryStore, utc_now


def _build_script() -> ScriptOption:
    shots: list[ShotPlan] = []
    for idx in range(1, 7):
        shots.append(
            ShotPlan(
                shot_id=f"shot-{idx}",
                stage=ShotStage.feature if idx > 1 else ShotStage.hook,
                duration_sec=5 if idx > 1 else 3,
                visual_prompt=f"镜头{idx}画面",
                reference_image_prompt=f"镜头{idx}参考图",
                motion_direction="轻微推进",
                voiceover_direction="自然口播",
                narration=f"镜头{idx}旁白",
                on_screen_text=f"镜头{idx}字幕",
            )
        )
    return ScriptOption(
        script_id="script-1",
        title="测试脚本",
        format_type="口播讲解",
        strategy_note="测试",
        compliance_note="测试",
        total_duration_sec=33,
        shots=shots,
    )


class _FakeReferenceImageService:
    async def generate_storyboard(
        self,
        project_id: str,
        image_path: Path,
        image_public_url: str | None,
        script: ScriptOption,
        on_shot_done=None,
    ) -> dict[str, ShotReference]:
        refs: dict[str, ShotReference] = {}
        for shot in script.shots:
            ref = ShotReference(
                shot_id=shot.shot_id,
                source="generated",
                image_url=f"https://img.example.com/{shot.shot_id}.png",
                local_path=None,
                prompt=shot.reference_image_prompt,
            )
            if on_shot_done:
                maybe = on_shot_done(shot.shot_id, ref)
                if asyncio.iscoroutine(maybe):
                    await maybe
            refs[shot.shot_id] = ref
            await asyncio.sleep(0.02)
        return refs

    async def generate_storyboard_shot(self, image_path: Path, image_public_url: str | None, shot: ShotPlan):
        return ShotReference(
            shot_id=shot.shot_id,
            source="generated",
            image_url=f"https://img.example.com/{shot.shot_id}.png",
            local_path=None,
            prompt=shot.reference_image_prompt,
        )


@pytest.mark.asyncio
async def test_storyboard_progress_updates_references_incrementally(tmp_path: Path) -> None:
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
        settings=settings,
    )

    image_path = tmp_path / "uploads" / "project-1.png"
    image_path.parent.mkdir(parents=True, exist_ok=True)
    image_path.write_bytes(b"fake")

    now = utc_now()
    project = ProjectRecord(
        project_id="project-1",
        status=ProjectStatus.scripted,
        created_at=now,
        updated_at=now,
        image_path=str(image_path),
        brief=ProductBrief(product_name="测试产品"),
        selected_script=_build_script(),
        storyboard_status=StoryboardStatus.not_started,
    )
    store.add_project(project)

    service.start_storyboard_generation(project_id="project-1", regenerate=False)
    await asyncio.sleep(0.05)
    mid = service.get_project("project-1")
    assert mid is not None
    assert mid.storyboard_status == StoryboardStatus.generating
    assert 0 < len(mid.storyboard_references) < len(mid.selected_script.shots)

    for _ in range(40):
        current = service.get_project("project-1")
        assert current is not None
        if current.storyboard_status == StoryboardStatus.ready:
            break
        await asyncio.sleep(0.02)

    final_project = service.get_project("project-1")
    assert final_project is not None
    assert final_project.storyboard_status == StoryboardStatus.ready
    assert len(final_project.storyboard_references) == len(final_project.selected_script.shots)
