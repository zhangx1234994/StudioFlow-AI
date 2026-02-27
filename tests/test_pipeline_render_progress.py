import asyncio
from pathlib import Path

import pytest

from app.config import Settings
from app.schemas import (
    ClipVariant,
    ProductBrief,
    ProjectRecord,
    ProjectStatus,
    RenderRequest,
    ScriptOption,
    ShotPlan,
    ShotReference,
    ShotStage,
    ShotApprovalStatus,
    StoryboardStatus,
)
from app.services.assembly_service import AssemblyService
from app.services.compliance_service import ComplianceService
from app.services.pipeline_service import PipelineService
from app.services.reference_image_service import ReferenceImageService
from app.services.volc_service import VolcScriptService
from app.store import InMemoryStore, utc_now


class _FakeSoraService:
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
        on_variant_done=None,
    ) -> tuple[dict[str, list[ClipVariant]], str | None]:
        result: dict[str, list[ClipVariant]] = {}
        total = len(shots) * variants_per_shot
        done = 0
        for shot in shots:
            variants: list[ClipVariant] = []
            for idx in range(variants_per_shot):
                clip = ClipVariant(
                    shot_id=shot.shot_id,
                    variant_index=idx,
                    score=0.9 - idx * 0.05,
                    task_id=f"task-{shot.shot_id}-{idx}",
                    video_url=f"https://cdn.example.com/{shot.shot_id}-{idx}.mp4",
                    local_path=None,
                )
                variants.append(clip)
                done += 1
                if on_variant_done:
                    maybe = on_variant_done(
                        clip,
                        {
                            "total": total,
                            "done": done,
                            "failed": 0,
                            "running": max(0, total - done),
                        },
                    )
                    if asyncio.iscoroutine(maybe):
                        await maybe
                await asyncio.sleep(0.01)
            result[shot.shot_id] = variants
        return result, image_public_url


def _build_script() -> ScriptOption:
    shots = [
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
        for idx in range(1, 7)
    ]
    return ScriptOption(
        script_id="script-1",
        title="测试脚本",
        format_type="口播讲解",
        strategy_note="测试",
        compliance_note="测试",
        total_duration_sec=33,
        shots=shots,
    )


@pytest.mark.asyncio
async def test_render_progress_updates_during_generation(tmp_path: Path) -> None:
    settings = Settings(use_mock_providers=True, storage_root=tmp_path)
    store = InMemoryStore()
    pipeline = PipelineService(
        store=store,
        script_service=VolcScriptService(settings),
        compliance_service=ComplianceService(),
        sora_service=_FakeSoraService(),
        reference_image_service=ReferenceImageService(settings),
        assembly_service=AssemblyService(settings),
        storage_root=tmp_path,
    )

    image_path = tmp_path / "uploads" / "project-render.png"
    image_path.parent.mkdir(parents=True, exist_ok=True)
    image_path.write_bytes(b"fake")

    script = _build_script()
    refs = {
        shot.shot_id: ShotReference(
            shot_id=shot.shot_id,
            source="generated",
            image_url=f"https://img.example.com/{shot.shot_id}.png",
            local_path=None,
            prompt=shot.reference_image_prompt,
        )
        for shot in script.shots
    }

    now = utc_now()
    project = ProjectRecord(
        project_id="project-render",
        status=ProjectStatus.scripted,
        created_at=now,
        updated_at=now,
        image_path=str(image_path),
        brief=ProductBrief(product_name="渲染测试"),
        selected_script=script,
        storyboard_status=StoryboardStatus.confirmed,
        storyboard_references=refs,
        shot_approvals={shot.shot_id: ShotApprovalStatus.approved for shot in script.shots},
    )
    store.add_project(project)

    _, render = pipeline.start_render_project(
        project_id="project-render",
        request=RenderRequest(variants_per_shot=2, async_mode=True),
    )
    render_id = render.render_id
    await asyncio.sleep(0.05)
    mid = pipeline.get_render(render_id)
    assert mid is not None
    assert mid.status == ProjectStatus.rendering
    assert mid.completed_variants > 0
    assert mid.total_variants == len(script.shots) * 2

    for _ in range(80):
        current = pipeline.get_render(render_id)
        assert current is not None
        if current.status == ProjectStatus.completed:
            break
        await asyncio.sleep(0.02)

    final = pipeline.get_render(render_id)
    assert final is not None
    assert final.status == ProjectStatus.completed
    assert final.completed_variants == final.total_variants
    assert final.running_variants == 0
