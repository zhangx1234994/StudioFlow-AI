import pytest
import httpx

from app.config import Settings
from app.schemas import ProductBrief, QualityLevel, ScenarioType, ToolType
from app.services.volc_service import VolcScriptService


@pytest.mark.asyncio
async def test_volc_timeout_falls_back_to_mock_scripts() -> None:
    settings = Settings(use_mock_providers=False, volc_api_key="dummy")
    service = VolcScriptService(settings)

    async def always_timeout(_messages):
        raise httpx.ReadTimeout("timeout")

    service._call_with_retry = always_timeout  # type: ignore[method-assign]

    insight, scripts = await service.analyze_and_plan(
        image_bytes=b"fake-bytes",
        image_mime="image/png",
        brief=ProductBrief(product_name="测试产品"),
    )

    assert len(scripts) == 3
    assert any("回退" in item for item in insight.risks)


@pytest.mark.asyncio
async def test_refine_script_for_generation_adds_motion_and_voice_defaults() -> None:
    settings = Settings(use_mock_providers=True)
    service = VolcScriptService(settings)
    brief = ProductBrief(product_name="测试产品")
    _, scripts = await service.analyze_and_plan(
        image_bytes=b"fake-bytes",
        image_mime="image/png",
        brief=brief,
    )
    refined = await service.refine_script_for_generation(
        brief=brief,
        insight=None,
        script=scripts[0],
    )
    assert refined.shots
    assert all((shot.reference_image_prompt or "").strip() for shot in refined.shots)
    assert all((shot.visual_prompt or "").strip() for shot in refined.shots)
    assert all((shot.motion_direction or "").strip() for shot in refined.shots)
    assert all((shot.voiceover_direction or "").strip() for shot in refined.shots)


@pytest.mark.asyncio
async def test_derive_prompt_scripts_returns_split_prompt_layers() -> None:
    settings = Settings(use_mock_providers=True)
    service = VolcScriptService(settings)
    brief = ProductBrief(product_name="测试产品")
    _, scripts = await service.analyze_and_plan(
        image_bytes=b"fake-bytes",
        image_mime="image/png",
        brief=brief,
    )
    refined, image_script, video_script = await service.derive_prompt_scripts(
        brief=brief,
        insight=None,
        master_script=scripts[0],
    )
    assert len(refined.shots) == len(image_script.shots) == len(video_script.shots)
    assert all("候选版本" not in shot.prompt for shot in image_script.shots)
    assert all("No text, no subtitles" in shot.prompt for shot in video_script.shots)
    assert all("主体:" in shot.prompt for shot in image_script.shots)
    assert all("OutputConstraints:" in shot.prompt for shot in video_script.shots)


def test_compile_prompt_pack_outputs_structured_prompt_blocks() -> None:
    settings = Settings(use_mock_providers=True)
    service = VolcScriptService(settings)
    brief = ProductBrief(product_name="测试产品")
    plan = service._mock_project_plan(
        brief=brief,
        scenario_type=ScenarioType.product_image_suite,
        template_name="general",
        quality_level=QualityLevel.standard,
    )

    prompt_pack = service.compile_prompt_pack(
        plan=plan,
        brief=brief,
        quality_level=QualityLevel.standard,
        tool_type=ToolType.product_image_suite,
    )

    assert prompt_pack.image_prompt_pack
    assert prompt_pack.video_prompt_pack
    assert all("主体:" in item.prompt for item in prompt_pack.image_prompt_pack)
    assert all("统一约束:" in item.prompt for item in prompt_pack.image_prompt_pack)
    assert all("OutputConstraints:" in item.prompt for item in prompt_pack.video_prompt_pack)
    assert prompt_pack.guardrail_report["image_prompt_quality_avg"] >= 0.9
    assert prompt_pack.guardrail_report["video_prompt_quality_avg"] >= 0.9


def test_parse_project_plan_fills_blank_delivery_purpose() -> None:
    settings = Settings(use_mock_providers=True)
    service = VolcScriptService(settings)
    brief = ProductBrief(product_name="测试产品")
    payload = {
        "summary": "测试",
        "shots": [
            {
                "shot_id": "shot-1",
                "title": "主图展示",
                "intent": "突出主体质感",
                "stage": "hook",
                "duration_sec": 4,
                "image_prompt": "主体特写，45度机位，干净背景",
                "video_prompt": "主体特写缓慢推进",
                "delivery_purpose": "   ",
            },
            {
                "shot_id": "shot-2",
                "title": "卖点细节",
                "intent": "展示纹理细节",
                "stage": "proof",
                "duration_sec": 4,
                "image_prompt": "微距细节，逆光强调纹理",
                "video_prompt": "微距缓慢横移",
                "delivery_purpose": "null",
            },
            {
                "shot_id": "shot-3",
                "title": "场景展示",
                "intent": "展示使用场景",
                "stage": "feature",
                "duration_sec": 4,
                "image_prompt": "中景场景，柔光布光",
                "video_prompt": "场景慢推",
                "delivery_purpose": "",
            },
            {
                "shot_id": "shot-4",
                "title": "收束图",
                "intent": "形成转化收束",
                "stage": "cta",
                "duration_sec": 4,
                "image_prompt": "主体居中，留白稳定",
                "video_prompt": "收束镜头",
                "delivery_purpose": "未定",
            },
        ],
    }
    plan = service._parse_project_plan(
        payload=payload,
        brief=brief,
        scenario_type=ScenarioType.product_image_suite,
        template_name="general",
        quality_level=QualityLevel.standard,
    )
    purposes = [shot.delivery_purpose for shot in plan.shots]
    assert purposes[0] == "主图"
    assert purposes[1] == "细节图"
    assert purposes[2] == "场景图"
    assert purposes[3] == "对比图"


def test_resolve_expected_shot_count_prefers_explicit_value() -> None:
    settings = Settings(use_mock_providers=True)
    service = VolcScriptService(settings)
    assert service._resolve_expected_shot_count(
        scenario_type=ScenarioType.product_image_suite,
        expected_shot_count=9,
    ) == 9
    assert service._resolve_expected_shot_count(
        scenario_type=ScenarioType.product_image_suite,
        expected_shot_count=None,
    ) == 4


@pytest.mark.asyncio
async def test_expand_missing_plan_shots_fills_to_expected_count() -> None:
    settings = Settings(use_mock_providers=False, volc_api_key="dummy")
    service = VolcScriptService(settings)
    brief = ProductBrief(product_name="测试产品")
    existing = service._mock_project_plan(
        brief=brief,
        scenario_type=ScenarioType.product_image_suite,
        template_name="general",
        quality_level=QualityLevel.standard,
    ).shots[:2]

    async def fake_single_shot_payload(
        *,
        shot_index: int,
        outline_entry: dict[str, str],
        **_: object,
    ) -> dict[str, object]:
        return {
            "shot_id": f"shot-{shot_index}",
            "title": f"镜头{shot_index}",
            "intent": f"目标{shot_index}",
            "duration_sec": 4,
            "stage": outline_entry.get("stage", "feature"),
            "delivery_purpose": outline_entry.get("delivery_purpose", "场景图"),
            "image_prompt": f"测试产品镜头{shot_index}，主体清晰，机位变化明显",
            "video_prompt": f"测试产品镜头{shot_index}，动作自然，无字幕",
        }

    service._generate_single_plan_shot_payload = fake_single_shot_payload  # type: ignore[method-assign]
    expanded = await service._expand_missing_plan_shots(
        image_data_url="data:image/png;base64,AAAA",
        brief=brief,
        scenario_type=ScenarioType.product_image_suite,
        existing_shots=existing,
        expected_shot_count=5,
    )
    assert len(expanded) == 5
    assert expanded[4].shot_id == "shot-5"


def test_model_retouch_prompt_pack_declares_reference_image_roles() -> None:
    settings = Settings(use_mock_providers=True)
    service = VolcScriptService(settings)
    brief = ProductBrief(product_name="测试产品")
    plan = service._mock_project_plan(
        brief=brief,
        scenario_type=ScenarioType.model_retouch,
        template_name="general",
        quality_level=QualityLevel.standard,
    )
    prompt_pack = service.compile_prompt_pack(
        plan=plan,
        brief=brief,
        quality_level=QualityLevel.standard,
        tool_type=ToolType.model_retouch,
    )
    assert prompt_pack.image_prompt_pack
    assert '图1=套图主图' in prompt_pack.image_prompt_pack[0].prompt
    assert '图2=模特锚点图' in prompt_pack.image_prompt_pack[0].prompt


def test_multi_angle_prompt_pack_preserves_same_object_instead_of_reimagining_subject() -> None:
    settings = Settings(use_mock_providers=True)
    service = VolcScriptService(settings)
    brief = ProductBrief(product_name="瑜伽服")
    plan = service._mock_project_plan(
        brief=brief,
        scenario_type=ScenarioType.multi_angle_camera,
        template_name="general",
        quality_level=QualityLevel.standard,
    )
    prompt_pack = service.compile_prompt_pack(
        plan=plan,
        brief=brief,
        quality_level=QualityLevel.standard,
        tool_type=ToolType.multi_angle_camera,
    )
    assert prompt_pack.image_prompt_pack
    prompt = prompt_pack.image_prompt_pack[0].prompt
    assert '主体:上传原图中的同一对象' in prompt
    assert '不重绘主体' in prompt
    assert '不替换服装' in prompt
    assert '主体:瑜伽服' not in prompt
