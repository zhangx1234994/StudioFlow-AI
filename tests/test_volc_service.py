import pytest
import httpx

from app.config import Settings
from app.schemas import ProductBrief
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
