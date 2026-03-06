import asyncio
from pathlib import Path

from app.config import Settings
from app.schemas import PromptItem, ScriptOption, ShotPlan, ShotStage
from app.services.reference_image_service import ReferenceImageService


def _build_script() -> ScriptOption:
    shots = [
        ShotPlan(
            shot_id="shot-1",
            stage=ShotStage.hook,
            duration_sec=3,
            visual_prompt="特写产品外观",
            reference_image_prompt="主体置中，背景干净",
            narration="开场钩子",
            on_screen_text="第一眼就抓住重点",
        ),
        ShotPlan(
            shot_id="shot-2",
            stage=ShotStage.feature,
            duration_sec=5,
            visual_prompt="展示使用动作",
            reference_image_prompt="手部动作清晰，强调细节",
            narration="展示功能",
            on_screen_text="细节和质感同时到位",
        ),
        ShotPlan(
            shot_id="shot-3",
            stage=ShotStage.feature,
            duration_sec=5,
            visual_prompt="侧面结构",
            reference_image_prompt="强调结构层次",
            narration="强调结构",
            on_screen_text="结构清晰更放心",
        ),
        ShotPlan(
            shot_id="shot-4",
            stage=ShotStage.proof,
            duration_sec=6,
            visual_prompt="对比展示",
            reference_image_prompt="同场景对比，真实光线",
            narration="展示对比",
            on_screen_text="同场景对比更直观",
        ),
        ShotPlan(
            shot_id="shot-5",
            stage=ShotStage.proof,
            duration_sec=6,
            visual_prompt="使用反馈",
            reference_image_prompt="人物使用动作自然",
            narration="使用反馈",
            on_screen_text="连续使用反馈稳定",
        ),
        ShotPlan(
            shot_id="shot-6",
            stage=ShotStage.cta,
            duration_sec=7,
            visual_prompt="收束镜头",
            reference_image_prompt="主体稳定，便于转化",
            narration="引导行动",
            on_screen_text="点击了解更多",
        ),
    ]
    return ScriptOption(
        script_id="script-1",
        title="测试脚本",
        format_type="口播讲解",
        strategy_note="测试",
        compliance_note="测试",
        total_duration_sec=32,
        shots=shots,
    )


def test_generate_storyboard_emits_shot_progress_callback(monkeypatch, tmp_path: Path) -> None:
    settings = Settings(
        use_mock_providers=False,
        kie_api_key="test-key",
        storage_root=tmp_path,
        storyboard_concurrency=2,
        poll_interval_seconds=0.0,
    )
    service = ReferenceImageService(settings)
    script = _build_script()
    done_shots: list[str] = []

    async def fake_upload(self, image_path: Path) -> str:
        return "https://example.com/source.png"

    async def fake_generate(self, image_input_urls: list[str], prompt: str, **kwargs) -> str | None:
        await asyncio.sleep(0.001)
        assert image_input_urls
        if "开场钩子" in prompt:
            return "https://img.example.com/shot-1.png"
        if "展示功能" in prompt:
            return "https://img.example.com/shot-2.png"
        return "https://img.example.com/shot-3.png"

    async def on_done(shot_id: str, _reference) -> None:
        done_shots.append(shot_id)

    monkeypatch.setattr(ReferenceImageService, "_upload_image", fake_upload)
    monkeypatch.setattr(ReferenceImageService, "_generate_single_storyboard_image", fake_generate)

    references = asyncio.run(
        service.generate_storyboard(
            project_id="project-1",
            image_path=tmp_path / "input.png",
            image_public_url=None,
            script=script,
            on_shot_done=on_done,
        )
    )

    assert set(done_shots) == {"shot-1", "shot-2", "shot-3", "shot-4", "shot-5", "shot-6"}
    assert list(references.keys()) == ["shot-1", "shot-2", "shot-3", "shot-4", "shot-5", "shot-6"]
    assert all(item.source == "generated" for item in references.values())


def test_generate_storyboard_mock_mode_still_emits_callback(tmp_path: Path) -> None:
    settings = Settings(
        use_mock_providers=True,
        storage_root=tmp_path,
    )
    service = ReferenceImageService(settings)
    script = _build_script()
    done_shots: list[str] = []

    async def on_done(shot_id: str, _reference) -> None:
        done_shots.append(shot_id)

    references = asyncio.run(
        service.generate_storyboard(
            project_id="project-1",
            image_path=tmp_path / "input.png",
            image_public_url=None,
            script=script,
            on_shot_done=on_done,
        )
    )

    assert done_shots == ["shot-1", "shot-2", "shot-3", "shot-4", "shot-5", "shot-6"]
    assert all(item.source == "original" for item in references.values())


def test_generate_images_from_prompts_supports_multi_reference_inputs(
    monkeypatch,
    tmp_path: Path,
) -> None:
    settings = Settings(
        use_mock_providers=False,
        kie_api_key="test-key",
        storage_root=tmp_path,
        poll_interval_seconds=0.0,
    )
    service = ReferenceImageService(settings)
    main = tmp_path / "main.png"
    ref = tmp_path / "ref.png"
    main.write_bytes(b"main")
    ref.write_bytes(b"ref")

    captured_inputs: list[list[str]] = []

    async def fake_upload(self, image_path: Path) -> str:
        return f"https://cdn.example.com/{image_path.name}"

    async def fake_create_task(self, image_input_urls: list[str], prompt: str, **kwargs) -> str:
        captured_inputs.append(list(image_input_urls))
        return "task-1"

    async def fake_wait(self, task_id: str) -> str | None:
        assert task_id == "task-1"
        return "https://img.example.com/out.png"

    monkeypatch.setattr(ReferenceImageService, "_upload_image", fake_upload)
    monkeypatch.setattr(ReferenceImageService, "_create_task", fake_create_task)
    monkeypatch.setattr(ReferenceImageService, "_wait_task_result", fake_wait)

    output = asyncio.run(
        service.generate_images_from_prompts(
            image_path=main,
            image_public_url=None,
            prompts=[PromptItem(shot_id="shot-1", prompt="测试提示词")],
            reference_image_urls=["https://public.example.com/ref-a.png"],
            reference_image_paths=[ref],
        )
    )

    assert "shot-1" in output
    assert output["shot-1"].source == "generated"
    assert captured_inputs
    assert captured_inputs[0] == [
        "https://cdn.example.com/main.png",
        "https://public.example.com/ref-a.png",
        "https://cdn.example.com/ref.png",
    ]


def test_generate_images_from_prompts_prefers_coze_workflow(monkeypatch, tmp_path: Path) -> None:
    settings = Settings(
        use_mock_providers=False,
        storage_root=tmp_path,
        coze_base_url="http://127.0.0.1:8888",
        coze_api_token="token",
        coze_image_workflow_id="workflow",
    )
    service = ReferenceImageService(settings)
    main = tmp_path / "main.png"
    main.write_bytes(b"main")

    async def fake_upload(self, image_path: Path) -> str:
        return f"https://cdn.example.com/{image_path.name}"

    async def fake_coze(self, **kwargs) -> str | None:
        assert kwargs["image_input_urls"][0] == "https://cdn.example.com/main.png"
        return "https://img.example.com/out.png"

    monkeypatch.setattr(ReferenceImageService, "_upload_image", fake_upload)
    monkeypatch.setattr(ReferenceImageService, "_run_coze_image_workflow", fake_coze)

    output = asyncio.run(
        service.generate_images_from_prompts(
            image_path=main,
            image_public_url=None,
            prompts=[PromptItem(shot_id="shot-1", prompt="测试提示词")],
        )
    )

    assert output["shot-1"].source == "generated"
    assert output["shot-1"].image_url == "https://img.example.com/out.png"


def test_extract_coze_task_payload_parses_status_and_images(tmp_path: Path) -> None:
    settings = Settings(storage_root=tmp_path)
    service = ReferenceImageService(settings)
    payload = {
        "data": {
            "taskStatus": "succeeded",
            "images": ["https://img.example.com/a.png", "https://img.example.com/b.png"],
        }
    }
    assert service._extract_coze_task_status(payload) == "succeeded"
    assert service._extract_coze_images(payload) == [
        "https://img.example.com/a.png",
        "https://img.example.com/b.png",
    ]
