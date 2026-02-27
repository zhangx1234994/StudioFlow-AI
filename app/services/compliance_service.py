from __future__ import annotations

from dataclasses import dataclass

from app.schemas import ScriptOption


@dataclass(frozen=True)
class Rule:
    banned: str
    replacement: str


class ComplianceService:
    _rules = [
        Rule("最", "更"),
        Rule("唯一", "少见"),
        Rule("绝对", "更稳"),
        Rule("买不到", "不常见"),
        Rule("全网", "同类"),
    ]

    def sanitize_script(self, script: ScriptOption) -> ScriptOption:
        return script.model_copy(
            update={
                "title": self._sanitize_text(script.title),
                "strategy_note": self._sanitize_text(script.strategy_note),
                "compliance_note": self._sanitize_text(script.compliance_note),
                "shots": [
                    shot.model_copy(
                        update={
                            "visual_prompt": self._sanitize_text(shot.visual_prompt),
                            "reference_image_prompt": self._sanitize_text(
                                shot.reference_image_prompt or shot.visual_prompt
                            ),
                            "narration": self._sanitize_text(shot.narration),
                            "on_screen_text": self._sanitize_text(shot.on_screen_text),
                        }
                    )
                    for shot in script.shots
                ],
            }
        )

    def _sanitize_text(self, text: str) -> str:
        updated = text
        for rule in self._rules:
            updated = updated.replace(rule.banned, rule.replacement)
        return updated
