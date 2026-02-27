from app.schemas import ScriptOption, ShotPlan, ShotStage
from app.services.compliance_service import ComplianceService


def test_compliance_replaces_banned_words() -> None:
    shots = [
        ShotPlan(
            shot_id=f"shot-{idx}",
            stage=ShotStage.feature if idx > 1 else ShotStage.hook,
            duration_sec=5 if idx > 1 else 3,
            visual_prompt="全网第一" if idx == 1 else "同类对比",
            narration="外面买不到" if idx == 1 else "点击了解",
            on_screen_text="绝对推荐" if idx == 1 else "了解详情",
        )
        for idx in range(1, 7)
    ]

    script = ScriptOption(
        script_id="script-1",
        title="全网唯一最好的方案",
        strategy_note="绝对会让你满意",
        compliance_note="避免夸张",
        total_duration_sec=32,
        shots=shots,
    )

    cleaned = ComplianceService().sanitize_script(script)

    assert "唯一" not in cleaned.title
    assert "最" not in cleaned.title
    assert "绝对" not in cleaned.strategy_note
    assert "买不到" not in cleaned.shots[0].narration
