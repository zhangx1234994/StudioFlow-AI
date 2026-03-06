from __future__ import annotations

import asyncio
import base64
import json
import os
import re
from typing import Any

import httpx

from app.config import Settings
from app.schemas import (
    ImagePromptScript,
    PlanShot,
    PromptInputForm,
    ProductBrief,
    ProjectPlan,
    PromptItem,
    PromptPack,
    QualityLevel,
    ScenarioType,
    ScriptOption,
    ShotPlan,
    ShotStage,
    ToolType,
    VideoPromptScript,
    VisualInsight,
)
from app.utils.json_tools import extract_json_object


class VolcScriptService:
    _PLANNER_PROMPT_VERSION = "2026-02-v1"
    _TEMPLATE_LIBRARY: dict[ToolType, dict[str, dict[str, Any]]] = {
        ToolType.intro_video_multi_script: {
            "talking_head": {
                "display_name": "口播讲解",
                "description": "主播口播为主，强调核心卖点和购买理由。",
                "planner_focus": [
                    "前3秒给出强钩子问题或反差画面",
                    "3-30秒逐点拆解卖点并给出证据镜头",
                    "结尾用行动引导，不用绝对化词汇",
                ],
                "default_form": {
                    "platform": "douyin",
                    "target_audience": "注重体验和性价比的人群",
                    "key_features": ["核心卖点", "真实反馈", "使用场景"],
                    "evidence_points": ["上手演示", "连续使用反馈"],
                    "tone": "真实、克制、有钩子",
                    "channels": ["douyin", "tiktok"],
                    "content_template": "talking_head",
                    "prompt_goal": "提升下单转化",
                    "prompt_style": "真人口播+真实演示",
                    "prompt_shot_focus": "3秒钩子、卖点拆解、证据收束",
                    "prompt_constraints": ["避免夸张广告感", "避免绝对化表达"],
                },
            },
            "comparison": {
                "display_name": "对比测评",
                "description": "用对比结构强化产品优势，强调可感知差异。",
                "planner_focus": [
                    "同场景对比，镜头标准一致",
                    "先给结论再给证据，避免堆砌形容词",
                    "结尾强调适用人群和下单时机",
                ],
                "default_form": {
                    "platform": "douyin",
                    "target_audience": "重视真实测评和决策效率的人群",
                    "key_features": ["核心性能对比", "使用体验差异", "稳定性"],
                    "evidence_points": ["同场景对比", "连续使用反馈"],
                    "tone": "客观、真实、结论清晰",
                    "channels": ["douyin", "tiktok"],
                    "prompt_goal": "提升转化意愿",
                    "prompt_style": "测评对比风格",
                    "prompt_shot_focus": "结论前置、证据充分、结尾引导",
                    "prompt_constraints": ["不贬低竞品", "不使用极限词"],
                },
            },
            "story": {
                "display_name": "场景剧情",
                "description": "通过生活剧情引出痛点和解决方案。",
                "planner_focus": [
                    "第一镜头直接展示痛点冲突",
                    "中段用连续动作展示产品介入",
                    "结尾强调变化结果和行动引导",
                ],
                "default_form": {
                    "platform": "douyin",
                    "target_audience": "关注使用场景和情绪价值的人群",
                    "key_features": ["痛点解决", "真实场景适配", "体验提升"],
                    "evidence_points": ["前后对比", "高频场景复现"],
                    "tone": "生活化、真实、有节奏",
                    "channels": ["douyin", "tiktok", "xiaohongshu"],
                    "prompt_goal": "提高点击和停留",
                    "prompt_style": "微剧情短视频",
                    "prompt_shot_focus": "痛点冲突、方案介入、结果收束",
                    "prompt_constraints": ["避免煽动性表达"],
                },
            },
            "tutorial": {
                "display_name": "教程清单",
                "description": "步骤化讲解，突出易上手和实用性。",
                "planner_focus": [
                    "步骤编号清晰但画面不出现文字",
                    "每步必须有可视化动作证据",
                    "结尾总结适配人群和行动建议",
                ],
                "default_form": {
                    "platform": "douyin",
                    "target_audience": "希望快速上手的新用户",
                    "key_features": ["简单上手", "关键步骤", "结果可复现"],
                    "evidence_points": ["步骤演示", "结果镜头"],
                    "tone": "清晰、实操、可信",
                    "channels": ["douyin", "video号", "tiktok"],
                    "prompt_goal": "提升收藏与转化",
                    "prompt_style": "分步教程",
                    "prompt_shot_focus": "步骤镜头、动作细节、结果镜头",
                    "prompt_constraints": ["避免过度承诺"],
                },
            },
            "unboxing": {
                "display_name": "开箱首发",
                "description": "聚焦开箱体验与第一印象。",
                "planner_focus": [
                    "开场直接展示包装与第一触感",
                    "中段拆解材质、细节、配件",
                    "结尾给购买建议和使用人群",
                ],
                "default_form": {
                    "platform": "tiktok",
                    "target_audience": "关注新品和颜值体验的人群",
                    "key_features": ["开箱体验", "材质细节", "第一印象"],
                    "evidence_points": ["近景细节", "上手动作"],
                    "tone": "轻快、真实、不过度夸张",
                    "channels": ["tiktok", "douyin"],
                    "prompt_goal": "提升首发转化",
                    "prompt_style": "开箱体验",
                    "prompt_shot_focus": "开箱钩子、细节拆解、收尾建议",
                    "prompt_constraints": ["避免绝对化评价"],
                },
            },
        },
        ToolType.product_image_suite: {
            "general": {
                "display_name": "图像通用模板",
                "description": "覆盖主图、场景图、细节图与对比图的标准电商套图。",
                "planner_focus": [
                    "先主图后场景，再细节与对比",
                    "每张图的构图和光线目标要明确",
                    "输出要可直接用于商品详情页",
                ],
                "default_form": {
                    "platform": "douyin",
                    "target_audience": "追求品质和实用性的消费人群",
                    "key_features": ["材质质感", "核心细节", "使用场景"],
                    "evidence_points": ["光线方向", "构图层次", "材质纹理"],
                    "tone": "真实电商摄影感，不夸张",
                    "channels": ["douyin", "xiaohongshu", "tiktok"],
                    "scene_style": "商业棚拍+生活化场景",
                    "scene_goals": ["主图精修", "场景图", "细节特写", "对比图"],
                    "prompt_goal": "提升点击率和详情页转化",
                    "prompt_style": "高质感电商摄影",
                    "prompt_shot_focus": "主图清晰、场景可信、细节有证据",
                    "prompt_constraints": ["避免过度修饰", "避免品牌侵权元素"],
                },
            },
            "hero_clean": {
                "display_name": "主图纯净风",
                "description": "高洁净背景主图，突出产品主体与材质。",
                "planner_focus": [
                    "背景干净，主体绝对清晰",
                    "高光控制和材质纹理并重",
                    "输出适配首图点击场景",
                ],
                "default_form": {
                    "platform": "tiktok",
                    "target_audience": "追求效率决策的电商用户",
                    "key_features": ["主体突出", "材质清晰", "光线干净"],
                    "evidence_points": ["边缘细节", "高光控制"],
                    "tone": "简洁、干净、专业",
                    "channels": ["tiktok", "douyin"],
                    "scene_style": "纯色背景棚拍",
                    "scene_goals": ["主图精修", "细节特写"],
                },
            },
            "lifestyle_scene": {
                "display_name": "生活场景风",
                "description": "真实生活环境中展示产品使用状态。",
                "planner_focus": [
                    "场景真实，动作自然",
                    "镜头体现产品在生活中的价值",
                    "注意人与物体比例和空间关系",
                ],
                "default_form": {
                    "platform": "xiaohongshu",
                    "target_audience": "看重真实场景代入感的人群",
                    "key_features": ["场景代入", "真实使用", "氛围感"],
                    "evidence_points": ["环境细节", "动作连贯"],
                    "tone": "生活化、可信、克制",
                    "channels": ["xiaohongshu", "douyin", "tiktok"],
                    "scene_style": "自然光生活场景",
                    "scene_goals": ["场景图", "使用状态图"],
                },
            },
            "detail_macro": {
                "display_name": "细节特写风",
                "description": "通过微距细节强化做工和质感。",
                "planner_focus": [
                    "关键细节特写必须可辨识",
                    "镜头集中于工艺与纹理证据",
                    "避免无效装饰性背景",
                ],
                "default_form": {
                    "platform": "douyin",
                    "target_audience": "对做工细节敏感的人群",
                    "key_features": ["工艺细节", "纹理质感", "耐用结构"],
                    "evidence_points": ["微距纹理", "接口细节"],
                    "tone": "专业、克制、细节导向",
                    "channels": ["douyin", "tiktok"],
                    "scene_style": "微距摄影风",
                    "scene_goals": ["细节特写", "局部对比图"],
                },
            },
            "bundle_combo": {
                "display_name": "组合套装风",
                "description": "适配多SKU组合陈列和权益展示。",
                "planner_focus": [
                    "组合关系清楚，主次分明",
                    "突出套装价值与搭配逻辑",
                    "保持整体视觉统一",
                ],
                "default_form": {
                    "platform": "tiktok",
                    "target_audience": "追求一次购齐和性价比人群",
                    "key_features": ["组合陈列", "搭配价值", "视觉统一"],
                    "evidence_points": ["套装全景", "核心单品细节"],
                    "tone": "清晰、直接、可信",
                    "channels": ["tiktok", "douyin"],
                    "scene_style": "组合陈列摄影",
                    "scene_goals": ["套装主图", "组合场景图"],
                },
            },
        },
        ToolType.model_retouch: {
            "general": {
                "display_name": "精修通用模板",
                "description": "覆盖动作、面部、肤质、服装与光线的综合精修。",
                "planner_focus": [
                    "先诊断问题再分步修复",
                    "优先保持人物身份一致",
                    "避免过度磨皮和肢体形变",
                ],
                "default_form": {
                    "platform": "xiaohongshu",
                    "target_audience": "服饰与人像内容团队",
                    "key_features": ["身份一致", "表情自然", "细节干净"],
                    "evidence_points": ["面部细节", "肢体自然度", "服装纹理"],
                    "tone": "写实精修，克制自然",
                    "channels": ["xiaohongshu", "instagram", "tiktok"],
                    "retouch_targets": ["动作自然", "面部状态", "肤质统一", "服装褶皱", "光线修正"],
                    "fidelity_requirement": "保持人物身份一致，避免形变和过度磨皮",
                    "prompt_goal": "提升图像可用率",
                    "prompt_style": "写实人像精修",
                    "prompt_shot_focus": "先诊断后修复，分局部给出动作指令",
                    "prompt_constraints": ["不改变人物身份", "不生成多余肢体"],
                },
            },
            "face_expression": {
                "display_name": "面部状态优化",
                "description": "重点修复面部表情、眼神和肤质表现。",
                "planner_focus": [
                    "保持身份特征不变",
                    "修复表情僵硬或疲态",
                    "肤质处理自然不过度",
                ],
                "default_form": {
                    "platform": "xiaohongshu",
                    "target_audience": "美妆服饰拍摄团队",
                    "key_features": ["表情自然", "眼神状态", "肤质真实"],
                    "evidence_points": ["眼周细节", "口部细节", "肤质纹理"],
                    "retouch_targets": ["面部状态", "眼神优化", "肤质质感"],
                    "fidelity_requirement": "保留五官结构和个人特征",
                },
            },
            "pose_adjust": {
                "display_name": "动作姿态优化",
                "description": "修复肢体姿态不自然、比例不协调等问题。",
                "planner_focus": [
                    "优先修正肢体连贯性",
                    "保证重心和透视合理",
                    "修复后动作需符合真实人体",
                ],
                "default_form": {
                    "platform": "tiktok",
                    "target_audience": "服装拍摄与素材外包团队",
                    "key_features": ["姿态自然", "比例协调", "动作连贯"],
                    "evidence_points": ["手部细节", "肩颈线条", "腿部比例"],
                    "retouch_targets": ["动作微调", "肢体比例", "站姿重心"],
                    "fidelity_requirement": "禁止新增肢体或关节扭曲",
                },
            },
            "lighting_rebalance": {
                "display_name": "光线与肤色平衡",
                "description": "修复曝光、偏色和阴影问题，提升画面统一性。",
                "planner_focus": [
                    "修复偏色与曝光不均",
                    "保证脸部和服装亮度平衡",
                    "保留真实阴影层次",
                ],
                "default_form": {
                    "platform": "instagram",
                    "target_audience": "人像后期团队",
                    "key_features": ["曝光均衡", "肤色自然", "光线统一"],
                    "evidence_points": ["亮部层次", "暗部细节"],
                    "retouch_targets": ["光线修正", "肤色平衡", "阴影细节"],
                    "fidelity_requirement": "不破坏原始风格与质感",
                },
            },
        },
        ToolType.quick_video_15s: {
            "general": {
                "display_name": "15秒快产模板",
                "description": "标准15秒节奏：钩子-演示-证据-引导。",
                "planner_focus": [
                    "0-3秒强钩子，提升停留",
                    "中段只讲一个核心价值点",
                    "结尾给清晰行动引导",
                ],
                "default_form": {
                    "platform": "tiktok",
                    "target_audience": "短视频电商用户",
                    "key_features": ["开场钩子", "核心演示", "行动引导"],
                    "evidence_points": ["核心场景", "卖点证明"],
                    "tone": "快节奏、真实、克制",
                    "channels": ["tiktok", "douyin"],
                    "prompt_goal": "快速产出可投放候选",
                    "prompt_style": "快节奏短视频",
                    "prompt_shot_focus": "钩子、演示、证据、CTA",
                    "prompt_constraints": ["无字幕", "无水印", "无logo"],
                },
            },
            "comparison": {
                "display_name": "15秒对比快产",
                "description": "在15秒内快速完成对比叙事。",
                "planner_focus": [
                    "开场给结论，中段给对比证据",
                    "镜头切换简洁，信息密度高",
                    "结尾保留转化动机",
                ],
                "default_form": {
                    "platform": "tiktok",
                    "target_audience": "偏理性决策人群",
                    "key_features": ["结果对比", "体验差异", "稳定输出"],
                    "evidence_points": ["同场景对比", "前后变化"],
                    "tone": "直接、客观、干净",
                    "channels": ["tiktok", "douyin"],
                },
            },
            "scenario_demo": {
                "display_name": "15秒场景演示",
                "description": "聚焦单一高频场景，突出产品作用。",
                "planner_focus": [
                    "第一镜头直接进入场景",
                    "中段动作连续，信息不跳跃",
                    "结尾强调适合谁用",
                ],
                "default_form": {
                    "platform": "douyin",
                    "target_audience": "关注真实场景转化的人群",
                    "key_features": ["高频场景", "真实动作", "结果变化"],
                    "evidence_points": ["场景过程", "结果镜头"],
                    "tone": "生活化、真实、克制",
                    "channels": ["douyin", "tiktok"],
                },
            },
            "unboxing_fast": {
                "display_name": "15秒开箱快产",
                "description": "快节奏开箱并完成价值传达。",
                "planner_focus": [
                    "开场0-2秒开箱钩子",
                    "中段突出细节与质感",
                    "结尾给下单理由",
                ],
                "default_form": {
                    "platform": "tiktok",
                    "target_audience": "关注新品体验用户",
                    "key_features": ["开箱体验", "细节质感", "第一印象"],
                    "evidence_points": ["上手细节", "包装与主体"],
                    "tone": "轻快、真实、不过度包装",
                    "channels": ["tiktok", "douyin"],
                },
            },
        },
        ToolType.multi_angle_camera: {
            "general": {
                "display_name": "多角度拍摄模板",
                "description": "输入单张产品图，输出多角度电商拍摄结果。",
                "planner_focus": [
                    "角度变化要连续且可理解，优先覆盖主视角、侧视角和俯视角",
                    "保持主体尺度和材质一致，避免透视畸变",
                    "输出可直接用于详情页的多角度图组",
                ],
                "default_form": {
                    "platform": "douyin",
                    "target_audience": "电商视觉和商品运营团队",
                    "key_features": ["多角度展示", "材质一致", "透视稳定"],
                    "evidence_points": ["主视角", "侧视角", "俯仰角变化"],
                    "tone": "专业摄影棚风格，真实克制",
                    "channels": ["douyin", "xiaohongshu", "tiktok"],
                    "prompt_goal": "输出可用的多角度商品图组",
                    "prompt_style": "3D相机位移摄影感",
                    "prompt_shot_focus": "角度变化、透视控制、材质一致",
                    "prompt_constraints": ["禁止文字", "禁止logo", "避免畸变"],
                },
            }
        },
    }

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _resolve_template_spec(self, tool_type: ToolType, template_name: str) -> dict[str, Any]:
        tool_templates = self._TEMPLATE_LIBRARY.get(tool_type, {})
        if template_name in tool_templates:
            return tool_templates[template_name]
        if "general" in tool_templates:
            return tool_templates["general"]
        if tool_templates:
            return next(iter(tool_templates.values()))
        return {
            "display_name": "通用模板",
            "description": "通用电商模板",
            "planner_focus": [],
            "default_form": {},
        }

    def default_prompt_inputs(self, tool_type: ToolType, template_name: str) -> PromptInputForm:
        spec = self._resolve_template_spec(tool_type=tool_type, template_name=template_name)
        defaults = spec.get("default_form", {})
        raw_constraints = defaults.get("prompt_constraints", [])
        constraints = [str(item).strip() for item in raw_constraints if str(item).strip()]
        return PromptInputForm(
            goal=str(defaults.get("prompt_goal") or PromptInputForm.model_fields["goal"].default),
            style=str(defaults.get("prompt_style") or PromptInputForm.model_fields["style"].default),
            shot_focus=str(
                defaults.get("prompt_shot_focus") or PromptInputForm.model_fields["shot_focus"].default
            ),
            constraints=constraints,
        )

    def get_template_defaults(self, tool_type: ToolType, template_name: str) -> dict[str, Any]:
        spec = self._resolve_template_spec(tool_type=tool_type, template_name=template_name)
        defaults = spec.get("default_form", {})
        normalized: dict[str, Any] = {}
        for key, value in defaults.items():
            if isinstance(value, list):
                normalized[key] = [str(item) for item in value if str(item).strip()]
            else:
                normalized[key] = value
        return normalized

    def list_tool_templates(self, tool_type: ToolType) -> list[dict[str, Any]]:
        templates = self._TEMPLATE_LIBRARY.get(tool_type, {})
        output: list[dict[str, Any]] = []
        for template_name, spec in templates.items():
            output.append(
                {
                    "tool_type": tool_type,
                    "template_name": template_name,
                    "display_name": spec.get("display_name", template_name),
                    "description": spec.get("description", ""),
                    "planner_focus": [str(item) for item in spec.get("planner_focus", []) if str(item).strip()],
                    "default_form": self.get_template_defaults(tool_type=tool_type, template_name=template_name),
                }
            )
        return output

    async def analyze_and_plan(
        self,
        image_bytes: bytes,
        image_mime: str,
        brief: ProductBrief,
    ) -> tuple[VisualInsight, list[ScriptOption]]:
        if self._settings.use_mock_providers or not self._settings.volc_api_key:
            return self._mock_analyze_and_plan(brief)

        try:
            return await asyncio.wait_for(
                self._analyze_and_plan_live(
                    image_bytes=image_bytes,
                    image_mime=image_mime,
                    brief=brief,
                ),
                timeout=self._settings.vl_overall_timeout_seconds,
            )
        except Exception:
            pass

        fallback_insight, fallback_scripts = self._mock_analyze_and_plan(brief)
        fallback_insight.risks.append("VL 服务超时或返回异常，已自动回退到模板脚本。")
        return fallback_insight, fallback_scripts

    async def generate_project_plan(
        self,
        image_bytes: bytes,
        image_mime: str,
        brief: ProductBrief,
        scenario_type: ScenarioType,
        template_name: str,
        quality_level: QualityLevel = QualityLevel.standard,
        tool_type: ToolType | None = None,
        expected_shot_count: int | None = None,
        takes_per_shot: int | None = None,
        target_candidate_assets: int | None = None,
        strict_json: bool = False,
    ) -> ProjectPlan:
        if self._settings.use_mock_providers or not self._settings.volc_api_key:
            return self._mock_project_plan(
                brief=brief,
                scenario_type=scenario_type,
                template_name=template_name,
                quality_level=quality_level,
            )

        resolved_expected = self._resolve_expected_shot_count(
            scenario_type=scenario_type,
            expected_shot_count=expected_shot_count,
        )
        resolved_takes = max(1, min(4, int(takes_per_shot or 1)))
        resolved_candidates = (
            int(target_candidate_assets)
            if isinstance(target_candidate_assets, int) and target_candidate_assets > 0
            else max(1, resolved_expected) * resolved_takes
        )
        try:
            image_data_url = self._to_data_url(image_bytes, image_mime)
            if self._should_use_outline_strategy(
                scenario_type=scenario_type,
                expected_shot_count=resolved_expected,
            ):
                parsed = await self._generate_project_plan_outline_first(
                    image_data_url=image_data_url,
                    brief=brief,
                    scenario_type=scenario_type,
                    template_name=template_name,
                    quality_level=quality_level,
                    tool_type=tool_type,
                    expected_shot_count=resolved_expected,
                    takes_per_shot=resolved_takes,
                    target_candidate_assets=resolved_candidates,
                )
            else:
                raw_text = await asyncio.wait_for(
                    self._call_with_retry(
                        self._build_planner_messages(
                            image_data_url=image_data_url,
                            brief=brief,
                            scenario_type=scenario_type,
                            template_name=template_name,
                            quality_level=quality_level,
                            tool_type=tool_type,
                            expected_shot_count=resolved_expected,
                            takes_per_shot=resolved_takes,
                            target_candidate_assets=resolved_candidates,
                        )
                    ),
                    timeout=min(60.0, max(30.0, self._settings.vl_overall_timeout_seconds)),
                )
                payload = await self._parse_json_or_repair(
                    raw_text=raw_text,
                    schema_name="project_plan",
                    schema_example=self._project_plan_schema_example(),
                )
                parsed = self._parse_project_plan(
                    payload=payload or {},
                    brief=brief,
                    scenario_type=scenario_type,
                    template_name=template_name,
                    quality_level=quality_level,
                )

            if resolved_expected > 0 and len(parsed.shots) < resolved_expected:
                expanded_shots = await self._expand_missing_plan_shots(
                    image_data_url=image_data_url,
                    brief=brief,
                    scenario_type=scenario_type,
                    existing_shots=list(parsed.shots),
                    expected_shot_count=resolved_expected,
                )
                parsed = parsed.model_copy(update={"shots": expanded_shots})
            notes = [item for item in parsed.planner_notes if item]
            if not any(item.startswith("source:") for item in notes):
                notes.insert(0, "source:volc")
            if not any(item.startswith("planner_prompt_version:") for item in notes):
                notes.insert(1, f"planner_prompt_version:{self._PLANNER_PROMPT_VERSION}")
            if resolved_expected > 0:
                notes.append(f"expected_shot_count:{resolved_expected}")
            if resolved_takes > 0:
                notes.append(f"takes_per_shot:{resolved_takes}")
            notes.append(f"target_candidate_assets:{resolved_candidates}")
            return parsed.model_copy(update={"planner_notes": notes[:8]})
        except Exception as exc:
            if strict_json:
                raise ValueError(f"VL planner failed: {self._format_exception(exc)}") from exc
            return self._mock_project_plan(
                brief=brief,
                scenario_type=scenario_type,
                template_name=template_name,
                quality_level=quality_level,
            )

    def compile_prompt_pack(
        self,
        plan: ProjectPlan,
        brief: ProductBrief,
        quality_level: QualityLevel = QualityLevel.standard,
        tool_type: ToolType | None = None,
    ) -> PromptPack:
        planner_prompt = (
            f"场景:{plan.scenario_type.value}; 模板:{plan.template_name};"
            f" 品牌:{brief.product_name}; 目标渠道:{','.join(plan.channels or brief.channels)};"
            f" 质量档位:{quality_level.value}"
        )
        normalized_shots = self._ensure_plan_prompt_diversity(
            shots=plan.shots,
            product_name=brief.product_name,
            scenario_type=plan.scenario_type,
        )
        image_pack = [
            PromptItem(
                shot_id=shot.shot_id,
                prompt=self._compile_image_generation_prompt(
                    shot=shot,
                    scenario_type=plan.scenario_type,
                    product_name=brief.product_name,
                    quality_level=quality_level,
                ),
            )
            for shot in normalized_shots
        ]
        video_pack = [
            PromptItem(
                shot_id=shot.shot_id,
                prompt=self._compile_video_generation_prompt(
                    shot=shot,
                    scenario_type=plan.scenario_type,
                    product_name=brief.product_name,
                    quality_level=quality_level,
                ),
            )
            for shot in normalized_shots
        ]
        image_quality_scores = [self._prompt_quality_score(item.prompt, mode="image") for item in image_pack]
        video_quality_scores = [self._prompt_quality_score(item.prompt, mode="video") for item in video_pack]
        planner_source = next(
            (item for item in plan.planner_notes if isinstance(item, str) and item.startswith("source:")),
            "source:unknown",
        )
        planner_prompt_version = next(
            (
                item
                for item in plan.planner_notes
                if isinstance(item, str) and item.startswith("planner_prompt_version:")
            ),
            f"planner_prompt_version:{self._PLANNER_PROMPT_VERSION}",
        )
        guardrail_report = {
            "enforced_rules": [
                "no_absolute_claims",
                "no_text_overlay_for_video",
                "schema_required",
                "compliance_blocklist",
            ],
            "blocked_terms": brief.compliance_blocklist,
            "quality_level": quality_level.value,
            "planner_source": planner_source,
            "planner_prompt_version": planner_prompt_version,
            "tool_type": (tool_type.value if tool_type else "unknown"),
            "template_name": plan.template_name,
            "image_prompt_quality_avg": round(sum(image_quality_scores) / max(1, len(image_quality_scores)), 3),
            "video_prompt_quality_avg": round(sum(video_quality_scores) / max(1, len(video_quality_scores)), 3),
        }
        return PromptPack(
            planner_prompt=planner_prompt,
            image_prompt_pack=image_pack,
            video_prompt_pack=video_pack,
            guardrail_report=guardrail_report,
            version=1,
        )

    async def refine_script_for_generation(
        self,
        brief: ProductBrief,
        insight: VisualInsight | None,
        script: ScriptOption,
    ) -> ScriptOption:
        baseline = self._fallback_refine_script_for_generation(brief=brief, script=script)
        if self._settings.use_mock_providers or not self._settings.volc_api_key:
            return baseline

        try:
            raw_text = await asyncio.wait_for(
                self._call_with_retry(
                    self._build_generation_refine_messages(
                        brief=brief,
                        insight=insight,
                        script=baseline,
                    )
                ),
                timeout=min(self._settings.vl_overall_timeout_seconds, 35.0),
            )
            payload = await self._parse_json_or_repair(
                raw_text=raw_text,
                schema_name="generation_shot_plan",
                schema_example=self._generation_refine_schema_example(),
            )
            return self._merge_generation_refinement(
                baseline=baseline,
                payload=payload or {},
                product_name=brief.product_name,
            )
        except Exception:
            return baseline

    async def derive_prompt_scripts(
        self,
        brief: ProductBrief,
        insight: VisualInsight | None,
        master_script: ScriptOption,
    ) -> tuple[ScriptOption, ImagePromptScript, VideoPromptScript]:
        refined = await self.refine_script_for_generation(
            brief=brief,
            insight=insight,
            script=master_script,
        )
        image_script = ImagePromptScript(
            script_id=refined.script_id,
            shots=[
                {
                    "shot_id": shot.shot_id,
                    "prompt": self._compile_script_image_prompt(
                        shot=shot,
                        product_name=brief.product_name,
                    ),
                }
                for shot in refined.shots
            ],
        )
        video_script = VideoPromptScript(
            script_id=refined.script_id,
            shots=[
                {
                    "shot_id": shot.shot_id,
                    "prompt": self._compile_script_video_prompt(
                        shot=shot,
                        product_name=brief.product_name,
                    ),
                }
                for shot in refined.shots
            ],
        )
        return refined, image_script, video_script

    async def _analyze_and_plan_live(
        self,
        image_bytes: bytes,
        image_mime: str,
        brief: ProductBrief,
    ) -> tuple[VisualInsight, list[ScriptOption]]:
        image_data_url = self._to_data_url(image_bytes, image_mime)

        analysis_raw = await self._call_with_retry(
            self._build_analysis_messages(
                image_data_url=image_data_url,
                brief=brief,
            )
        )
        analysis_payload = await self._parse_json_or_repair(
            raw_text=analysis_raw,
            schema_name="image_insight",
            schema_example=self._analysis_schema_example(),
        )
        insight = self._parse_insight(analysis_payload or {}, brief)

        script_raw = await self._call_with_retry(
            self._build_script_messages(brief=brief, insight=insight)
        )
        script_payload = await self._parse_json_or_repair(
            raw_text=script_raw,
            schema_name="script_bundle",
            schema_example=self._script_schema_example(),
        )

        scripts_raw = script_payload.get("scripts", []) if isinstance(script_payload, dict) else []
        scripts = self._parse_scripts(scripts_raw, brief)
        if not scripts:
            raise ValueError("No valid scripts from VL")

        return insight, self._ensure_three_scripts(scripts, brief)

    async def _call_with_retry(self, messages: list[dict[str, Any]]) -> str:
        return await self._call_responses_api(messages)

    def _format_exception(self, exc: Exception) -> str:
        if isinstance(exc, asyncio.TimeoutError):
            timeout = max(30.0, self._settings.vl_overall_timeout_seconds)
            return f"timeout after {int(timeout)}s"
        if isinstance(exc, httpx.HTTPStatusError):
            detail = exc.response.text.strip()
            if detail:
                return f"HTTP {exc.response.status_code}: {detail[:300]}"
            return f"HTTP {exc.response.status_code}"
        message = str(exc).strip()
        if message:
            return message
        return exc.__class__.__name__

    async def _parse_json_or_repair(
        self,
        raw_text: str,
        schema_name: str,
        schema_example: dict[str, Any],
    ) -> dict[str, Any] | None:
        parsed = extract_json_object(raw_text)
        if parsed:
            return parsed

        if not self._settings.volc_api_key:
            return None

        repaired = await self._call_responses_api(
            self._build_repair_messages(
                schema_name=schema_name,
                schema_example=schema_example,
                raw_text=raw_text,
            )
        )
        return extract_json_object(repaired)

    async def _call_responses_api(self, messages: list[dict[str, Any]]) -> str:
        headers = {
            "Authorization": f"Bearer {self._settings.volc_api_key}",
            "Content-Type": "application/json",
        }
        request_descriptor = json.dumps(messages, ensure_ascii=False)
        max_output_tokens = 3000
        if "project_plan_single_shot" in request_descriptor:
            max_output_tokens = 900
        elif "project_plan_outline" in request_descriptor:
            max_output_tokens = 1200
        model_candidates = self._resolve_volc_model_candidates()
        request_timeout = min(180.0, max(70.0, self._settings.vl_overall_timeout_seconds + 20.0))
        last_http_error: httpx.HTTPStatusError | None = None
        async with httpx.AsyncClient(timeout=request_timeout) as client:
            for model_name in model_candidates:
                body: dict[str, Any] = {
                    "model": model_name,
                    "input": messages,
                    "max_output_tokens": max_output_tokens,
                }
                if self._settings.volc_disable_thinking:
                    body["thinking"] = {"type": "disabled"}
                response = await client.post(self._settings.volc_base_url, headers=headers, json=body)
                if response.status_code >= 400:
                    if self._can_retry_with_fallback_model(response=response):
                        try:
                            response.raise_for_status()
                        except httpx.HTTPStatusError as exc:
                            last_http_error = exc
                            continue
                    response.raise_for_status()
                data = response.json()
                if isinstance(data.get("output_text"), str):
                    return data["output_text"]

                output = data.get("output", [])
                text_chunks: list[str] = []
                if isinstance(output, list):
                    for item in output:
                        content = item.get("content", []) if isinstance(item, dict) else []
                        if not isinstance(content, list):
                            continue
                        for chunk in content:
                            if not isinstance(chunk, dict):
                                continue
                            if isinstance(chunk.get("text"), str):
                                text_chunks.append(chunk["text"])
                return "\n".join(text_chunks)

        if last_http_error:
            raise last_http_error
        raise RuntimeError("volc response request failed without valid response")

    def _resolve_volc_model_candidates(self) -> list[str]:
        primary = (self._settings.volc_model or "").strip()
        fallback_env = (os.getenv("ARK_FALLBACK_MODEL") or "").strip()
        candidates = [
            primary,
            fallback_env,
            "doubao-seed-2-0-pro-260215",
            "doubao-seed-1-6-251015",
        ]
        dedup: list[str] = []
        for item in candidates:
            if item and item not in dedup:
                dedup.append(item)
        return dedup or ["doubao-seed-1-6-251015"]

    def _can_retry_with_fallback_model(self, *, response: httpx.Response) -> bool:
        if response.status_code != 404:
            return False
        code = ""
        message = ""
        try:
            payload = response.json()
            err = payload.get("error", {}) if isinstance(payload, dict) else {}
            code = str(err.get("code") or "")
            message = str(err.get("message") or "")
        except Exception:
            message = response.text or ""
        code_lower = code.lower()
        message_lower = message.lower()
        return (
            "invalidendpointormodel.notfound" in code_lower
            or "model or endpoint" in message_lower
            or "does not exist" in message_lower
            or "do not have access" in message_lower
        )

    def _build_analysis_messages(
        self,
        image_data_url: str,
        brief: ProductBrief,
    ) -> list[dict[str, Any]]:
        system_prompt = (
            "你是资深短视频视觉策划。"
            "你只输出 JSON，不输出解释。"
            "禁止使用绝对化词汇。"
        )
        user_prompt = {
            "task": "识图并提炼短视频卖点",
            "brief": {
                "product_name": brief.product_name,
                "target_audience": brief.target_audience,
                "platform": brief.platform,
                "price_band": brief.price_band,
            },
            "output_schema": self._analysis_schema_example(),
            "rules": [
                "识别可见主体、材质、场景、使用动作",
                "总结可用于脚本的具体卖点",
                "指出潜在合规风险词",
            ],
        }
        return [
            {
                "role": "system",
                "content": [{"type": "input_text", "text": system_prompt}],
            },
            {
                "role": "user",
                "content": [
                    {"type": "input_image", "image_url": image_data_url},
                    {
                        "type": "input_text",
                        "text": json.dumps(user_prompt, ensure_ascii=False),
                    },
                ],
            },
        ]

    def _resolve_expected_shot_count(
        self,
        *,
        scenario_type: ScenarioType,
        expected_shot_count: int | None,
    ) -> int:
        if isinstance(expected_shot_count, int) and expected_shot_count > 0:
            return max(1, min(30, expected_shot_count))
        defaults = {
            ScenarioType.product_image_suite: 4,
            ScenarioType.model_retouch: 4,
            ScenarioType.multi_angle_camera: 4,
            ScenarioType.product_video: 4,
        }
        return defaults.get(scenario_type, 4)

    def _should_use_outline_strategy(
        self,
        *,
        scenario_type: ScenarioType,
        expected_shot_count: int,
    ) -> bool:
        if expected_shot_count <= 0:
            return False
        if scenario_type in {ScenarioType.product_image_suite, ScenarioType.model_retouch}:
            return expected_shot_count >= 7
        return expected_shot_count >= 8

    async def _generate_project_plan_outline_first(
        self,
        *,
        image_data_url: str,
        brief: ProductBrief,
        scenario_type: ScenarioType,
        template_name: str,
        quality_level: QualityLevel,
        tool_type: ToolType | None,
        expected_shot_count: int,
        takes_per_shot: int,
        target_candidate_assets: int,
    ) -> ProjectPlan:
        outline_raw = await asyncio.wait_for(
            self._call_with_retry(
                self._build_plan_outline_messages(
                    image_data_url=image_data_url,
                    brief=brief,
                    scenario_type=scenario_type,
                    template_name=template_name,
                    quality_level=quality_level,
                    tool_type=tool_type,
                    expected_shot_count=expected_shot_count,
                    takes_per_shot=takes_per_shot,
                    target_candidate_assets=target_candidate_assets,
                )
            ),
            timeout=max(20.0, min(45.0, self._settings.vl_overall_timeout_seconds)),
        )
        outline_payload = await self._parse_json_or_repair(
            raw_text=outline_raw,
            schema_name="project_plan_outline",
            schema_example=self._plan_outline_schema_example(),
        )
        outline_summary = (
            str((outline_payload or {}).get("summary") or "").strip()
            or f"{brief.product_name}执行方案（outline）"
        )
        outline_notes = [
            str(item).strip()
            for item in (outline_payload or {}).get("planner_notes", [])
            if str(item).strip()
        ][:6]
        outline_shots_raw = (outline_payload or {}).get("shots", [])
        outline_shots: list[dict[str, Any]] = []
        if isinstance(outline_shots_raw, list):
            for idx, item in enumerate(outline_shots_raw, start=1):
                if isinstance(item, dict):
                    outline_shots.append(dict(item))
                if len(outline_shots) >= expected_shot_count:
                    break
        while len(outline_shots) < expected_shot_count:
            outline_shots.append(
                self._build_outline_fallback_entry(
                    scenario_type=scenario_type,
                    shot_index=len(outline_shots) + 1,
                )
            )

        parallelism = min(8, max(2, self._settings.storyboard_concurrency))
        semaphore = asyncio.Semaphore(parallelism)

        async def _render_one(index: int, outline_entry: dict[str, Any]) -> PlanShot:
            async with semaphore:
                try:
                    raw_shot = await asyncio.wait_for(
                        self._generate_single_plan_shot_payload(
                            image_data_url=image_data_url,
                            brief=brief,
                            scenario_type=scenario_type,
                            template_name=template_name,
                            quality_level=quality_level,
                            tool_type=tool_type,
                            shot_index=index,
                            outline_entry=outline_entry,
                        ),
                        timeout=max(15.0, min(35.0, self._settings.vl_overall_timeout_seconds)),
                    )
                    return self._parse_plan_shot(
                        raw_shot=raw_shot,
                        shot_index=index,
                        brief=brief,
                        scenario_type=scenario_type,
                    )
                except Exception:
                    return self._build_fallback_plan_shot(
                        brief=brief,
                        scenario_type=scenario_type,
                        shot_index=index,
                        outline_entry=outline_entry,
                    )

        tasks = [
            _render_one(idx, outline_shots[idx - 1])
            for idx in range(1, expected_shot_count + 1)
        ]
        generated_shots = list(await asyncio.gather(*tasks))
        generated_shots = self._ensure_plan_prompt_diversity(
            shots=generated_shots,
            product_name=brief.product_name,
            scenario_type=scenario_type,
        )
        generated_shots = self._apply_creative_direction_to_shots(
            shots=generated_shots,
            creative_direction=brief.creative_direction,
            scenario_type=scenario_type,
        )
        return ProjectPlan(
            scenario_type=scenario_type,
            template_name=template_name,
            channels=brief.channels,
            summary=outline_summary,
            planner_notes=[*outline_notes, "planner_strategy:outline_parallel_fill"][:8],
            shots=generated_shots[:expected_shot_count],
        )

    async def _expand_missing_plan_shots(
        self,
        *,
        image_data_url: str,
        brief: ProductBrief,
        scenario_type: ScenarioType,
        existing_shots: list[PlanShot],
        expected_shot_count: int,
    ) -> list[PlanShot]:
        merged = list(existing_shots[:expected_shot_count])
        if expected_shot_count <= 0 or len(merged) >= expected_shot_count:
            return merged

        parallelism = min(6, max(2, self._settings.storyboard_concurrency))
        semaphore = asyncio.Semaphore(parallelism)

        async def _fill_one(shot_index: int) -> PlanShot:
            outline_entry = self._build_outline_fallback_entry(
                scenario_type=scenario_type,
                shot_index=shot_index,
            )
            async with semaphore:
                try:
                    raw_shot = await asyncio.wait_for(
                        self._generate_single_plan_shot_payload(
                            image_data_url=image_data_url,
                            brief=brief,
                            scenario_type=scenario_type,
                            template_name="general",
                            quality_level=QualityLevel.standard,
                            tool_type=None,
                            shot_index=shot_index,
                            outline_entry=outline_entry,
                        ),
                        timeout=max(12.0, min(28.0, self._settings.vl_overall_timeout_seconds)),
                    )
                    return self._parse_plan_shot(
                        raw_shot=raw_shot,
                        shot_index=shot_index,
                        brief=brief,
                        scenario_type=scenario_type,
                    )
                except Exception:
                    return self._build_fallback_plan_shot(
                        brief=brief,
                        scenario_type=scenario_type,
                        shot_index=shot_index,
                        outline_entry=outline_entry,
                    )

        start_index = len(merged) + 1
        tasks = [_fill_one(idx) for idx in range(start_index, expected_shot_count + 1)]
        if tasks:
            merged.extend(await asyncio.gather(*tasks))
        merged = self._ensure_plan_prompt_diversity(
            shots=merged,
            product_name=brief.product_name,
            scenario_type=scenario_type,
        )
        merged = self._apply_creative_direction_to_shots(
            shots=merged,
            creative_direction=brief.creative_direction,
            scenario_type=scenario_type,
        )
        return merged[:expected_shot_count]

    async def _generate_single_plan_shot_payload(
        self,
        *,
        image_data_url: str,
        brief: ProductBrief,
        scenario_type: ScenarioType,
        template_name: str,
        quality_level: QualityLevel,
        tool_type: ToolType | None,
        shot_index: int,
        outline_entry: dict[str, Any],
    ) -> dict[str, Any]:
        raw_text = await self._call_with_retry(
            self._build_single_shot_messages(
                image_data_url=image_data_url,
                brief=brief,
                scenario_type=scenario_type,
                template_name=template_name,
                quality_level=quality_level,
                tool_type=tool_type,
                shot_index=shot_index,
                outline_entry=outline_entry,
            )
        )
        payload = await self._parse_json_or_repair(
            raw_text=raw_text,
            schema_name="project_plan_single_shot",
            schema_example=self._single_shot_schema_example(),
        )
        if isinstance(payload, dict) and isinstance(payload.get("shot"), dict):
            return dict(payload["shot"])
        if isinstance(payload, dict):
            return dict(payload)
        raise ValueError("single shot payload is invalid")

    def _build_outline_fallback_entry(
        self,
        *,
        scenario_type: ScenarioType,
        shot_index: int,
    ) -> dict[str, Any]:
        stage = self._stage_for_shot_index(shot_index)
        return {
            "shot_id": f"shot-{shot_index}",
            "title": f"镜头{shot_index}",
            "intent": "补充卖点表达",
            "stage": stage.value,
            "duration_sec": 4,
            "delivery_purpose": self._default_delivery_purpose(
                scenario_type=scenario_type,
                stage=stage,
            ),
        }

    def _build_fallback_plan_shot(
        self,
        *,
        brief: ProductBrief,
        scenario_type: ScenarioType,
        shot_index: int,
        outline_entry: dict[str, Any],
    ) -> PlanShot:
        stage_name = str(outline_entry.get("stage") or self._stage_for_shot_index(shot_index).value)
        stage_value = stage_name if stage_name in ShotStage._value2member_map_ else ShotStage.feature.value
        stage = ShotStage(stage_value)
        title = str(outline_entry.get("title") or f"镜头{shot_index}")
        intent = str(outline_entry.get("intent") or "补充卖点表达")
        image_prompt = self._compose_image_prompt(
            product_name=brief.product_name,
            scenario_type=scenario_type,
            stage=stage.value,
            shot_index=shot_index,
            title=title,
            intent=intent,
            base_prompt=f"{brief.product_name}，{title}，突出{intent}",
        )
        video_prompt = self._sanitize_video_prompt(
            f"{brief.product_name}，{title}，{intent}，动作自然，镜头路径清晰。"
        )
        return PlanShot(
            shot_id=str(outline_entry.get("shot_id") or f"shot-{shot_index}"),
            title=title,
            intent=intent,
            duration_sec=max(3, min(8, int(outline_entry.get("duration_sec") or 4))),
            stage=stage,
            image_prompt=image_prompt,
            video_prompt=video_prompt,
            delivery_purpose=str(outline_entry.get("delivery_purpose") or "").strip()
            or self._default_delivery_purpose(scenario_type=scenario_type, stage=stage),
            retouch_prompt=(
                f"{brief.product_name}，{title}，轻度精修，保持身份与构图稳定。"
                if scenario_type == ScenarioType.model_retouch
                else ""
            ),
            retouch_goal=(
                f"{title}：轻度保真精修，保持原图动作和背景"
                if scenario_type == ScenarioType.model_retouch
                else None
            ),
            identity_lock_rules=(
                ["保持五官结构和骨相一致", "保持服装版型与动作骨架一致"]
                if scenario_type == ScenarioType.model_retouch
                else []
            ),
            local_edit_instructions=(
                ["先修动作连贯性，再修肤色和光线", "保持背景与构图不重构"]
                if scenario_type == ScenarioType.model_retouch
                else []
            ),
            negative_constraints=(
                ["禁止背景重构", "禁止半身替代全身", "禁止新增肢体"]
                if scenario_type == ScenarioType.model_retouch
                else []
            ),
        )

    def _build_plan_outline_messages(
        self,
        *,
        image_data_url: str,
        brief: ProductBrief,
        scenario_type: ScenarioType,
        template_name: str,
        quality_level: QualityLevel,
        tool_type: ToolType | None,
        expected_shot_count: int,
        takes_per_shot: int,
        target_candidate_assets: int,
    ) -> list[dict[str, Any]]:
        resolved_tool = tool_type or ToolType.intro_video_multi_script
        prompt_header = self._planner_system_prompt(tool_type=tool_type, scenario_type=scenario_type)
        system_prompt = (
            f"{prompt_header}"
            "你是分镜大纲规划器。"
            "先输出shot大纲，禁止长篇说明，禁止思考过程。"
            "只返回JSON。"
        )
        payload = {
            "task": "输出分镜大纲",
            "response_style": "fast_outline_json_only",
            "scenario_type": scenario_type.value,
            "tool_type": resolved_tool.value,
            "template_name": template_name,
            "quality_level": quality_level.value,
            "execution_hints": {
                "expected_shot_count": expected_shot_count,
                "takes_per_shot": takes_per_shot,
                "target_candidate_assets": target_candidate_assets,
                "latency_mode": "fast",
            },
            "brief": {
                "product_name": brief.product_name,
                "target_audience": brief.target_audience,
                "platform": brief.platform,
                "key_features": brief.key_features,
                "creative_direction": brief.creative_direction,
            },
            "hard_rules": [
                f"shots总数必须等于{expected_shot_count}",
                "每个shot必须包含shot_id/title/intent/stage/delivery_purpose/duration_sec",
                "只输出分镜大纲，不输出image_prompt/video_prompt",
                "按shot_id升序输出，不允许缺号",
            ],
            "output_schema": self._plan_outline_schema_example(),
        }
        return [
            {
                "role": "system",
                "content": [{"type": "input_text", "text": system_prompt}],
            },
            {
                "role": "user",
                "content": [
                    {"type": "input_image", "image_url": image_data_url},
                    {"type": "input_text", "text": json.dumps(payload, ensure_ascii=False)},
                ],
            },
        ]

    def _build_single_shot_messages(
        self,
        *,
        image_data_url: str,
        brief: ProductBrief,
        scenario_type: ScenarioType,
        template_name: str,
        quality_level: QualityLevel,
        tool_type: ToolType | None,
        shot_index: int,
        outline_entry: dict[str, Any],
    ) -> list[dict[str, Any]]:
        resolved_tool = tool_type or ToolType.intro_video_multi_script
        prompt_header = self._planner_system_prompt(tool_type=tool_type, scenario_type=scenario_type)
        system_prompt = (
            f"{prompt_header}"
            "你是单镜头分镜生成器。"
            "仅生成一个shot，速度优先，不要思考过程。"
            "只返回JSON。"
        )
        payload = {
            "task": "补全单镜头提示词",
            "response_style": "fast_single_shot_json_only",
            "scenario_type": scenario_type.value,
            "tool_type": resolved_tool.value,
            "template_name": template_name,
            "quality_level": quality_level.value,
            "shot_index": shot_index,
            "outline_shot": outline_entry,
            "brief": {
                "product_name": brief.product_name,
                "target_audience": brief.target_audience,
                "platform": brief.platform,
                "key_features": brief.key_features,
                "creative_direction": brief.creative_direction,
            },
            "hard_rules": [
                "只输出一个shot对象",
                "image_prompt必须可执行且和其他镜头明显不同",
                "video_prompt禁止字幕/文字/logo/水印/UI",
                "提示词写结果，不写解释",
            ],
            "output_schema": self._single_shot_schema_example(),
        }
        return [
            {
                "role": "system",
                "content": [{"type": "input_text", "text": system_prompt}],
            },
            {
                "role": "user",
                "content": [
                    {"type": "input_image", "image_url": image_data_url},
                    {"type": "input_text", "text": json.dumps(payload, ensure_ascii=False)},
                ],
            },
        ]

    def _build_planner_messages(
        self,
        image_data_url: str,
        brief: ProductBrief,
        scenario_type: ScenarioType,
        template_name: str,
        quality_level: QualityLevel,
        tool_type: ToolType | None = None,
        expected_shot_count: int | None = None,
        takes_per_shot: int | None = None,
        target_candidate_assets: int | None = None,
    ) -> list[dict[str, Any]]:
        resolved_tool = tool_type or ToolType.intro_video_multi_script
        template_spec = self._resolve_template_spec(
            tool_type=resolved_tool,
            template_name=template_name,
        )
        resolved_expected = self._resolve_expected_shot_count(
            scenario_type=scenario_type,
            expected_shot_count=expected_shot_count,
        )
        resolved_takes = max(1, min(4, int(takes_per_shot or 1)))
        resolved_candidates = (
            int(target_candidate_assets)
            if isinstance(target_candidate_assets, int) and target_candidate_assets > 0
            else max(1, resolved_expected) * resolved_takes
        )
        prompt_header = self._planner_system_prompt(tool_type=tool_type, scenario_type=scenario_type)
        system_prompt = (
            f"{prompt_header}"
            "你只输出严格JSON，不能输出解释。"
            "你需要把创意拆成可执行分镜，兼容生图和生视频。"
            "速度优先：禁止输出思考过程，不要长篇分析，只返回结果JSON。"
        )
        payload = {
            "task": "生成跨模型执行计划",
            "response_style": "fast_direct_json_only",
            "scenario_type": scenario_type.value,
            "tool_type": resolved_tool.value,
            "template_name": template_name,
            "execution_hints": {
                "expected_shot_count": resolved_expected,
                "takes_per_shot": resolved_takes,
                "target_candidate_assets": resolved_candidates,
                "latency_mode": "fast",
            },
            "template_pack": {
                "display_name": template_spec.get("display_name", template_name),
                "description": template_spec.get("description", ""),
                "planner_focus": template_spec.get("planner_focus", []),
                "default_form": template_spec.get("default_form", {}),
            },
            "quality_level": quality_level.value,
            "brief": {
                "product_name": brief.product_name,
                "target_audience": brief.target_audience,
                "platform": brief.platform,
                "channels": brief.channels,
                "key_features": brief.key_features,
                "goal_type": brief.goal_type.value,
                "tone": brief.tone,
                "evidence_points": brief.evidence_points,
                "creative_direction": brief.creative_direction,
            },
            "hard_rules": [
                "必须输出shots数组，按shot_id升序",
                "每个shot同时提供image_prompt和video_prompt",
                "每个shot必须提供delivery_purpose，不能为空字符串",
                "video_prompt禁止要求字幕、文字、logo、水印",
                "动作和镜头语言明确，避免元话术",
                "场景A/B至少4个shot，场景C至少3个shot",
                f"shots总数必须等于{resolved_expected}",
                f"按每镜头试拍{resolved_takes}张估算候选产物，总候选目标约{resolved_candidates}",
                "不同shot的image_prompt/video_prompt必须明显不同，不允许仅换序号",
                "image_prompt必须包含: 主体对象 + 景别/机位 + 构图 + 光线 + 材质/色彩，不得空泛",
                "所有输出遵守合规，不使用绝对化词汇",
                "template_pack.planner_focus中的要求优先级最高，必须落到具体分镜",
                "若brief.creative_direction非空，必须将其落为可执行镜头与提示词，不得忽略",
                "当tool_type=product_image_suite时，delivery_purpose只能使用：主图/场景图/细节图/对比图",
            ],
            "scenario_focus": self._scenario_focus_rules(scenario_type),
            "creative_rules": self._creative_direction_rules(brief.creative_direction),
            "template_focus": template_spec.get("planner_focus", []),
            "aesthetic_requirements": self._aesthetic_requirements(
                scenario_type=scenario_type,
                tool_type=resolved_tool,
            ),
            "output_schema": self._project_plan_schema_example(),
        }
        return [
            {
                "role": "system",
                "content": [{"type": "input_text", "text": system_prompt}],
            },
            {
                "role": "user",
                "content": [
                    {"type": "input_image", "image_url": image_data_url},
                    {"type": "input_text", "text": json.dumps(payload, ensure_ascii=False)},
                ],
            },
        ]

    def _planner_system_prompt(
        self,
        tool_type: ToolType | None,
        scenario_type: ScenarioType,
    ) -> str:
        if tool_type == ToolType.intro_video_multi_script:
            return (
                "你是电商短视频导演，专长多脚本创意与转化节奏。"
                "优先输出可比较的3种叙事路径。"
            )
        if tool_type == ToolType.quick_video_15s:
            return (
                "你是15秒短视频提效导演。"
                "你必须优先输出高效率、强节奏、可直接投放的方案。"
            )
        if tool_type == ToolType.model_retouch:
            return (
                "你是人像精修总监，强调身份一致、动作自然、皮肤与光线真实。"
            )
        if tool_type == ToolType.product_image_suite:
            return (
                "你是电商静态图创意总监，擅长主图、场景图、细节图和对比图规划。"
            )
        if tool_type == ToolType.multi_angle_camera:
            return (
                "你是AI摄影棚的多角度拍摄导演，擅长在不改变原对象本体的前提下，用相机参数规划同一对象的多角度视图。"
            )
        if scenario_type == ScenarioType.product_video:
            return "你是电商视觉总监与导演。"
        if scenario_type == ScenarioType.model_retouch:
            return "你是电商人像精修总监。"
        return "你是电商视觉总监。"

    def _build_script_messages(
        self,
        brief: ProductBrief,
        insight: VisualInsight,
    ) -> list[dict[str, Any]]:
        system_prompt = (
            "你是短视频转化脚本总监。"
            "你只输出 JSON，不输出解释。"
            "必须严格遵守输出 schema。"
        )
        payload = {
            "task": "生成3套30-50秒带货脚本",
            "brief": {
                "product_name": brief.product_name,
                "target_audience": brief.target_audience,
                "platform": brief.platform,
                "price_band": brief.price_band,
                "key_features": brief.key_features,
                "cta_text": brief.cta_text,
                "desired_duration_sec": brief.desired_duration_sec,
                "tone": brief.tone,
                "content_template": brief.content_template,
                "presenter_mode": brief.presenter_mode.value,
                "presenter_source": brief.presenter_source.value,
                "goal_type": brief.goal_type.value,
                "evidence_points": brief.evidence_points,
                "compliance_blocklist": brief.compliance_blocklist,
                "creative_direction": brief.creative_direction,
            },
            "insight": insight.model_dump(),
            "hard_rules": [
                "3套脚本 format_type 必须不同，优先覆盖：口播讲解、场景剧情、对比测评",
                "每套6-10镜头",
                "第一镜头必须是hook且3秒",
                "总时长30-50秒",
                "语言克制，不用绝对化宣传",
                "每个镜头必须给参考图提示词 reference_image_prompt",
                "每个 narration 要具体，包含场景动作与价值点，建议20-45字",
                "每个 visual_prompt 要包含主体、景别、镜头运动、光线、构图",
                "每个 on_screen_text 控制在14字以内，短句有力",
                "主脚本用于创意决策，不要输出模型调用参数或版本描述",
            ],
            "output_schema": self._script_schema_example(),
        }
        return [
            {
                "role": "system",
                "content": [{"type": "input_text", "text": system_prompt}],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": json.dumps(payload, ensure_ascii=False)}],
            },
        ]

    def _build_generation_refine_messages(
        self,
        brief: ProductBrief,
        insight: VisualInsight | None,
        script: ScriptOption,
    ) -> list[dict[str, Any]]:
        system_prompt = (
            "你是短视频镜头导演与分镜规划师。"
            "你只输出 JSON，不输出解释。"
            "分镜图提示词与视频提示词必须分离。"
        )
        payload = {
            "task": "基于已选脚本，生成每个镜头用于生图和生视频的可执行参数",
            "brief": {
                "product_name": brief.product_name,
                "platform": brief.platform,
                "tone": brief.tone,
                "cta_text": brief.cta_text,
                "creative_direction": brief.creative_direction,
            },
            "insight": (insight.model_dump() if insight else {}),
            "creative_rules": self._creative_direction_rules(brief.creative_direction),
            "selected_script": {
                "script_id": script.script_id,
                "format_type": script.format_type,
                "shots": [
                    {
                        "shot_id": shot.shot_id,
                        "stage": shot.stage.value,
                        "duration_sec": shot.duration_sec,
                        "reference_image_prompt": shot.reference_image_prompt,
                        "visual_prompt": shot.visual_prompt,
                        "motion_direction": shot.motion_direction,
                        "voiceover_direction": shot.voiceover_direction,
                        "narration": shot.narration,
                        "on_screen_text": shot.on_screen_text,
                    }
                    for shot in script.shots
                ],
            },
            "hard_rules": [
                "reference_image_prompt 只描述静态关键帧画面，不写运镜，不写候选版本，不写系统说明",
                "reference_image_prompt必须包含: 主体 + 景别/机位 + 构图 + 光线 + 质感/色彩",
                "visual_prompt 只写给视频模型的镜头画面与动作，不写“提示词/镜头用途/候选版本”等元信息",
                "motion_direction 单独描述镜头运动与主体动作，10-35字",
                "voiceover_direction 单独描述语速语气与情绪，8-30字",
                "视频相关字段禁止出现文字、字幕、logo、水印、界面叠层要求",
                "保持合规表达，避免绝对化词汇",
                "按 shot_id 对齐输出，不能遗漏镜头",
                "每个镜头必须给出差异化美术与摄影表达，避免镜头间提示词同质化",
                "若brief.creative_direction非空，必须将其转成可执行画面描述，不得只复述原文",
            ],
            "output_schema": self._generation_refine_schema_example(),
        }
        return [
            {
                "role": "system",
                "content": [{"type": "input_text", "text": system_prompt}],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": json.dumps(payload, ensure_ascii=False)}],
            },
        ]

    def _build_repair_messages(
        self,
        schema_name: str,
        schema_example: dict[str, Any],
        raw_text: str,
    ) -> list[dict[str, Any]]:
        system_prompt = "你是 JSON 修复器。只输出一个合法 JSON 对象，不要任何额外文字。"
        payload = {
            "task": "修复为严格 JSON",
            "schema_name": schema_name,
            "schema_example": schema_example,
            "raw_text": raw_text,
        }
        return [
            {
                "role": "system",
                "content": [{"type": "input_text", "text": system_prompt}],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": json.dumps(payload, ensure_ascii=False)}],
            },
        ]

    def _analysis_schema_example(self) -> dict[str, Any]:
        return {
            "summary": "string",
            "visible_points": ["string"],
            "risks": ["string"],
        }

    def _script_schema_example(self) -> dict[str, Any]:
        return {
            "scripts": [
                {
                    "title": "string",
                    "format_type": "口播讲解|场景剧情|对比测评|清单推荐",
                    "strategy_note": "string",
                    "compliance_note": "string",
                    "shots": [
                        {
                            "stage": "hook|feature|proof|cta",
                            "duration_sec": 3,
                            "visual_prompt": "string",
                            "reference_image_prompt": "string",
                            "motion_direction": "string",
                            "voiceover_direction": "string",
                            "narration": "string",
                            "on_screen_text": "string",
                        }
                    ],
                }
            ]
        }

    def _generation_refine_schema_example(self) -> dict[str, Any]:
        return {
            "shots": [
                {
                    "shot_id": "shot-1",
                    "reference_image_prompt": "string",
                    "visual_prompt": "string",
                    "motion_direction": "string",
                    "voiceover_direction": "string",
                    "narration": "string",
                    "on_screen_text": "string",
                }
            ]
        }

    def _project_plan_schema_example(self) -> dict[str, Any]:
        return {
            "summary": "string",
            "planner_notes": ["string"],
            "shots": [
                {
                    "shot_id": "shot-1",
                    "title": "string",
                    "intent": "string",
                    "duration_sec": 5,
                    "stage": "hook|feature|proof|cta",
                    "delivery_purpose": "主图|场景图|细节图|对比图",
                    "image_prompt": "string",
                    "video_prompt": "string",
                    "retouch_prompt": "string",
                    "retouch_goal": "string",
                    "identity_lock_rules": ["string"],
                    "local_edit_instructions": ["string"],
                    "negative_constraints": ["string"],
                }
            ],
        }

    def _plan_outline_schema_example(self) -> dict[str, Any]:
        return {
            "summary": "string",
            "planner_notes": ["string"],
            "shots": [
                {
                    "shot_id": "shot-1",
                    "title": "string",
                    "intent": "string",
                    "stage": "hook|feature|proof|cta",
                    "delivery_purpose": "主图|场景图|细节图|对比图",
                    "duration_sec": 4,
                }
            ],
        }

    def _single_shot_schema_example(self) -> dict[str, Any]:
        return {
            "shot": {
                "shot_id": "shot-1",
                "title": "string",
                "intent": "string",
                "duration_sec": 4,
                "stage": "hook|feature|proof|cta",
                "delivery_purpose": "主图|场景图|细节图|对比图",
                "image_prompt": "string",
                "video_prompt": "string",
                "retouch_prompt": "string",
                "retouch_goal": "string",
                "identity_lock_rules": ["string"],
                "local_edit_instructions": ["string"],
                "negative_constraints": ["string"],
            }
        }

    def _parse_project_plan(
        self,
        payload: dict[str, Any],
        brief: ProductBrief,
        scenario_type: ScenarioType,
        template_name: str,
        quality_level: QualityLevel,
    ) -> ProjectPlan:
        raw_shots = payload.get("shots", []) if isinstance(payload, dict) else []
        shots: list[PlanShot] = []
        for idx, raw_shot in enumerate(raw_shots):
            parsed_shot = self._parse_plan_shot(
                raw_shot=raw_shot,
                shot_index=idx + 1,
                brief=brief,
                scenario_type=scenario_type,
            )
            if parsed_shot:
                shots.append(parsed_shot)
        shots = self._ensure_plan_prompt_diversity(
            shots=shots,
            product_name=brief.product_name,
            scenario_type=scenario_type,
        )
        shots = self._apply_creative_direction_to_shots(
            shots=shots,
            creative_direction=brief.creative_direction,
            scenario_type=scenario_type,
        )
        min_shots = 3 if scenario_type == ScenarioType.product_video else 4
        if len(shots) < min_shots:
            shots = self._mock_project_plan(
                brief=brief,
                scenario_type=scenario_type,
                template_name=template_name,
                quality_level=quality_level,
            ).shots
        return ProjectPlan(
            scenario_type=scenario_type,
            template_name=template_name,
            channels=brief.channels,
            summary=str(payload.get("summary") or f"{brief.product_name}内容资产生成方案"),
            planner_notes=[str(item) for item in payload.get("planner_notes", [])][:8],
            shots=shots,
        )

    def _parse_plan_shot(
        self,
        *,
        raw_shot: Any,
        shot_index: int,
        brief: ProductBrief,
        scenario_type: ScenarioType,
    ) -> PlanShot | None:
        if not isinstance(raw_shot, dict):
            return None
        stage_name = str(raw_shot.get("stage") or "feature")
        stage_value = stage_name if stage_name in ShotStage._value2member_map_ else ShotStage.feature.value
        stage = ShotStage(stage_value)
        try:
            duration = int(raw_shot.get("duration_sec") or (5 if scenario_type == ScenarioType.product_video else 4))
        except (TypeError, ValueError):
            duration = 5
        duration = max(3, min(8, duration))
        shot_id = str(raw_shot.get("shot_id") or f"shot-{shot_index}")
        image_prompt = self._cleanup_prompt_text(str(raw_shot.get("image_prompt") or ""))
        video_prompt = self._sanitize_video_prompt(str(raw_shot.get("video_prompt") or image_prompt))
        if not image_prompt:
            image_prompt = self._default_image_prompt(brief.product_name, stage_value)
        if not video_prompt:
            video_prompt = self._sanitize_video_prompt(image_prompt)
        delivery_purpose = self._normalize_delivery_purpose_value(raw_shot.get("delivery_purpose"))
        if not delivery_purpose:
            delivery_purpose = self._normalize_delivery_purpose_value(raw_shot.get("usage"))
        if not delivery_purpose:
            delivery_purpose = self._default_delivery_purpose(
                scenario_type=scenario_type,
                stage=stage,
            )
        return PlanShot(
            shot_id=shot_id,
            title=str(raw_shot.get("title") or f"镜头{shot_index}"),
            intent=str(raw_shot.get("intent") or "强化核心卖点"),
            duration_sec=duration,
            stage=stage,
            image_prompt=image_prompt,
            video_prompt=video_prompt,
            delivery_purpose=delivery_purpose,
            retouch_prompt=str(raw_shot.get("retouch_prompt") or ""),
            retouch_goal=str(raw_shot.get("retouch_goal") or "").strip() or None,
            identity_lock_rules=[
                str(item).strip()
                for item in raw_shot.get("identity_lock_rules", [])
                if str(item).strip()
            ][:6],
            local_edit_instructions=[
                str(item).strip()
                for item in raw_shot.get("local_edit_instructions", [])
                if str(item).strip()
            ][:8],
            negative_constraints=[
                str(item).strip()
                for item in raw_shot.get("negative_constraints", [])
                if str(item).strip()
            ][:8],
        )

    def _normalize_delivery_purpose_value(self, value: Any) -> str:
        if value is None:
            return ""
        text = str(value).strip()
        if not text:
            return ""
        if text.lower() in {"none", "null", "n/a", "na", "-", "待定", "未定", "unknown"}:
            return ""
        return text

    def _scenario_focus_rules(self, scenario_type: ScenarioType) -> list[str]:
        if scenario_type == ScenarioType.product_image_suite:
            return [
                "先做产品主图精修，再做场景图、细节特写、对比图",
                "image_prompt必须写清楚景别、机位、焦段、光线、构图、色彩、材质表现",
                "video_prompt仅用于动态预览，不要出现字幕与UI",
            ]
        if scenario_type == ScenarioType.model_retouch:
            return [
                "先做人像诊断再精修，保证身份一致和肢体自然",
                "retouch_prompt必须具体到局部动作/面部/肤质/服装/光线",
                "image_prompt强调精修后交付标准，不要泛化表达",
                "每镜头补充retouch_goal、identity_lock_rules、local_edit_instructions、negative_constraints",
            ]
        if scenario_type == ScenarioType.multi_angle_camera:
            return [
                "围绕上传原图中的同一对象输出视角变化方案，覆盖主视角、侧视角、俯仰变化",
                "image_prompt必须包含相机角度语义（yaw/pitch/focal/distance）",
                "保持同一对象的外观、材质、纹理、轮廓和比例连续，不得重画主体本体、替换服装或改变对象类别",
            ]
        return [
            "15秒节奏：开场抓停留 -> 特点演示 -> 证据 -> 行动引导",
            "分镜提示词要有动作与运镜，禁用字幕logo水印",
            "首镜头必须具备强视觉钩子，后续镜头层层推进转化动机",
        ]

    def _aesthetic_requirements(
        self,
        scenario_type: ScenarioType,
        tool_type: ToolType,
    ) -> list[str]:
        base = [
            "画面层次: 前景/主体/背景关系明确，避免平铺",
            "光线策略: 主光方向明确，必要时补轮廓光或反射光",
            "构图策略: 说明中心构图、三分法或对角线构图中的一种",
            "质感策略: 指明材质纹理、边缘清晰度、色彩倾向",
        ]
        if scenario_type == ScenarioType.product_image_suite:
            return [
                *base,
                "主图优先高完成度商业摄影感，背景干净不抢主体",
                "场景图必须有真实环境语义，避免悬浮摆拍感",
                "细节图优先微距或特写，体现可验证证据点",
            ]
        if scenario_type == ScenarioType.model_retouch:
            return [
                *base,
                "人物身份一致，五官结构与骨相不漂移",
                "肤质写实，不做塑料磨皮，不增加多余肢体",
                "服装褶皱、发丝、边缘抠图需自然",
            ]
        if scenario_type == ScenarioType.multi_angle_camera:
            return [
                *base,
                "透视与比例稳定，角度变化平滑",
                "产品边缘完整，避免拉伸和截断",
                "每个角度保持一致的棚拍质感和色温",
            ]
        if tool_type == ToolType.quick_video_15s:
            return [
                *base,
                "镜头节奏紧凑，前3秒画面必须有高辨识视觉钩子",
                "每个镜头必须可直接衔接下一镜头，不跳轴",
            ]
        return [
            *base,
            "镜头之间要有明确景别变化和视觉重心转移",
            "尽量使用真实场景质感，避免纯广告棚拍腔",
        ]

    def _creative_direction_rules(self, creative_direction: str) -> list[str]:
        text = (creative_direction or "").strip()
        if not text:
            return []
        rules = ["creative_direction 属于高优先级约束，必须落地到每个镜头描述中。"]
        if any(token in text for token in ["替换", "换脸", "模特替换"]):
            rules.extend(
                [
                    "替换人物时保持原图动作骨架、原套图服装版型、机位构图和光线方向一致。",
                    "禁止出现额外肢体、五官错位、边缘糊化和身份漂移。",
                ]
            )
        rules.append("避免刻板化或标签化的人像描述，保持专业、中性、可执行。")
        return rules

    def _apply_creative_direction_to_shots(
        self,
        shots: list[PlanShot],
        creative_direction: str,
        scenario_type: ScenarioType,
    ) -> list[PlanShot]:
        directive = self._cleanup_prompt_text(creative_direction)
        if not directive:
            return shots

        replacement_guard = ""
        if scenario_type == ScenarioType.model_retouch:
            replacement_guard = "保持同一人物身份，保留原套图动作骨架、服装版型、构图与光线连续，不得继承锚点服装。"
        anti_stereotype_guard = ""
        if scenario_type == ScenarioType.model_retouch:
            anti_stereotype_guard = "描述人物风格时避免刻板化与标签化表达。"

        updated: list[PlanShot] = []
        for shot in shots:
            candidate = shot.model_copy(deep=True)
            image_prompt = self._cleanup_prompt_text(candidate.image_prompt)
            retouch_prompt = self._cleanup_prompt_text(candidate.retouch_prompt or "")

            if directive not in image_prompt:
                image_prompt = self._cleanup_prompt_text(f"{image_prompt}。{directive}")
            if replacement_guard and replacement_guard not in image_prompt:
                image_prompt = self._cleanup_prompt_text(f"{image_prompt}。{replacement_guard}")
            if anti_stereotype_guard and anti_stereotype_guard not in image_prompt:
                image_prompt = self._cleanup_prompt_text(f"{image_prompt}。{anti_stereotype_guard}")

            if scenario_type == ScenarioType.model_retouch:
                if directive not in retouch_prompt:
                    retouch_prompt = self._cleanup_prompt_text(f"{retouch_prompt}。{directive}")
                if replacement_guard and replacement_guard not in retouch_prompt:
                    retouch_prompt = self._cleanup_prompt_text(f"{retouch_prompt}。{replacement_guard}")
                if anti_stereotype_guard and anti_stereotype_guard not in retouch_prompt:
                    retouch_prompt = self._cleanup_prompt_text(f"{retouch_prompt}。{anti_stereotype_guard}")

            candidate.image_prompt = image_prompt
            candidate.retouch_prompt = retouch_prompt
            updated.append(candidate)
        return updated

    def _prompt_fingerprint(self, text: str) -> str:
        value = self._cleanup_prompt_text(text).lower()
        return re.sub(r"[^a-z0-9\u4e00-\u9fa5]+", "", value)

    def _ensure_plan_prompt_diversity(
        self,
        shots: list[PlanShot],
        product_name: str,
        scenario_type: ScenarioType,
    ) -> list[PlanShot]:
        diversified: list[PlanShot] = []
        seen_image: set[str] = set()
        seen_video: set[str] = set()
        for index, shot in enumerate(shots, start=1):
            candidate = shot.model_copy(deep=True)
            stage = candidate.stage.value
            intent = candidate.intent.strip() or f"{product_name}核心卖点"
            title = candidate.title.strip() or f"镜头{index}"
            base = f"{product_name}，{title}，重点:{intent}，阶段:{stage}"

            image_prompt = self._cleanup_prompt_text(candidate.image_prompt)
            if not image_prompt or len(self._prompt_fingerprint(image_prompt)) < 16:
                image_prompt = f"{base}，静态电商拍摄，主体清晰，光线与构图可执行。"
            image_prompt = self._compose_image_prompt(
                product_name=product_name,
                scenario_type=scenario_type,
                stage=stage,
                shot_index=index,
                title=title,
                intent=intent,
                base_prompt=image_prompt,
            )
            image_fp = self._prompt_fingerprint(image_prompt)
            if image_fp in seen_image:
                image_prompt = self._compose_image_prompt(
                    product_name=product_name,
                    scenario_type=scenario_type,
                    stage=stage,
                    shot_index=index,
                    title=f"{title}-差异化版本",
                    intent=f"{intent}，与前镜头明显不同",
                    base_prompt=image_prompt,
                )
                image_fp = self._prompt_fingerprint(image_prompt)
            seen_image.add(image_fp)

            video_prompt = self._sanitize_video_prompt(candidate.video_prompt or image_prompt)
            if len(self._prompt_fingerprint(video_prompt)) < 16:
                video_prompt = self._sanitize_video_prompt(
                    f"{base}，动态演示，动作自然，镜头运动清晰，不要画面文字。"
                )
            video_fp = self._prompt_fingerprint(video_prompt)
            if video_fp in seen_video:
                video_prompt = self._sanitize_video_prompt(
                    f"{base}，第{index}镜头专属运镜，动作路径与节奏与前镜头不同。"
                )
                video_fp = self._prompt_fingerprint(video_prompt)
            seen_video.add(video_fp)

            candidate.image_prompt = image_prompt
            candidate.video_prompt = video_prompt
            if scenario_type == ScenarioType.model_retouch and not candidate.retouch_prompt:
                candidate.retouch_prompt = f"{base}，精修动作与面部细节，保持身份一致。"
            if scenario_type == ScenarioType.model_retouch:
                if not candidate.retouch_goal:
                    candidate.retouch_goal = f"{title}：提升人像自然度并保持身份一致"
                if not candidate.identity_lock_rules:
                    candidate.identity_lock_rules = [
                        "保持五官结构、脸型和骨相一致",
                        "保持原套图服装版型、动作骨架和构图一致",
                    ]
                if not candidate.local_edit_instructions:
                    candidate.local_edit_instructions = [
                        "先修复动作和肢体连贯性，再修复面部状态",
                        "最后统一肤色、光线和原套图服装纹理",
                    ]
                if not candidate.negative_constraints:
                    candidate.negative_constraints = [
                        "禁止新增肢体或五官错位",
                        "禁止过度磨皮和塑料质感",
                        "禁止出现文字、logo、水印",
                    ]
            diversified.append(candidate)
        return diversified

    def _quality_clause(self, quality_level: QualityLevel) -> str:
        if quality_level == QualityLevel.premium:
            return "画质目标4K商业级细节，纹理与材质层次优先，边缘干净无噪点"
        if quality_level == QualityLevel.standard:
            return "画质目标2K清晰，主体边缘干净，细节可用于电商投放"
        return "画质目标1K稳定可用，主体清晰，优先保证执行稳定性"

    def _join_prompt_sections(self, sections: list[str]) -> str:
        cleaned = [
            self._cleanup_prompt_text(item).strip("；;,. ")
            for item in sections
            if self._cleanup_prompt_text(item)
        ]
        return self._cleanup_prompt_text("；".join(cleaned))

    def _trim_prompt(self, text: str, max_chars: int = 420) -> str:
        value = self._cleanup_prompt_text(text)
        if len(value) <= max_chars:
            return value
        return value[:max_chars].rstrip("；;,，。 ") + "。"

    def _compile_image_generation_prompt(
        self,
        shot: PlanShot,
        scenario_type: ScenarioType,
        product_name: str,
        quality_level: QualityLevel,
    ) -> str:
        base_prompt = self._compose_image_prompt(
            product_name=product_name,
            scenario_type=scenario_type,
            stage=shot.stage.value,
            shot_index=self._shot_index_from_id(shot.shot_id),
            title=shot.title,
            intent=shot.intent,
            base_prompt=shot.image_prompt,
        )
        subject_line = f"主体:{product_name}"
        if scenario_type == ScenarioType.multi_angle_camera:
            subject_line = "主体:上传原图中的同一对象（保持原对象识别，不重绘主体，不替换服装）"
        sections = [
            subject_line,
            f"镜头:{shot.title}",
            f"目标:{shot.intent}",
            f"用途:{shot.delivery_purpose}",
            f"核心画面:{base_prompt}",
            f"质感约束:{self._quality_clause(quality_level)}",
            "统一约束:无文字、无字幕、无logo、无水印、无UI叠层",
        ]
        if scenario_type == ScenarioType.model_retouch:
            sections.extend(
                [
                    "参考图角色声明: 图1=套图主图（决定动作、构图、背景、服装）；图2=模特锚点图（只决定人物身份、发型、肤色、身体比例，不决定服装与背景）",
                    f"精修目标:{shot.retouch_goal or '保持身份一致并修复动作与面部细节'}",
                    f"身份锁定:{' / '.join(shot.identity_lock_rules or ['保持五官结构与脸型一致'])}",
                    f"局部修正:{' / '.join(shot.local_edit_instructions or ['先修动作，再修肤色与服装纹理'])}",
                    f"避免事项:{' / '.join(shot.negative_constraints or ['禁止新增肢体', '禁止过度磨皮'])}",
                ]
            )
        return self._trim_prompt(self._join_prompt_sections(sections), max_chars=500)

    def _compile_video_generation_prompt(
        self,
        shot: PlanShot,
        scenario_type: ScenarioType,
        product_name: str,
        quality_level: QualityLevel,
    ) -> str:
        shot_index = self._shot_index_from_id(shot.shot_id)
        visual = self._remove_video_constraint_tail(
            self._cleanup_prompt_text(shot.video_prompt or shot.image_prompt)
        )
        motion_raw = getattr(shot, "motion_direction", "") or ""
        motion = self._cleanup_prompt_text(motion_raw)
        if not motion:
            stage_obj = shot.stage if isinstance(shot.stage, ShotStage) else ShotStage.feature
            motion = self._default_motion_direction(stage_obj)
        sections = [
            f"Subject:{product_name}",
            f"Shot:{shot.title}",
            f"Intent:{shot.intent}",
            f"ShotPurpose:{shot.delivery_purpose}",
            "OutputConstraints: prohibit textual overlays and branding elements",
            f"VisualPlan:{visual}",
            f"MotionPath:{motion}",
            f"CameraRhythm:{self._video_stage_spec(shot.stage.value, shot_index)}",
            f"QualityTarget:{self._quality_clause(quality_level)}",
        ]
        if scenario_type == ScenarioType.model_retouch:
            sections.append("IdentityConsistency: keep face structure, body proportion, clothing shape and lighting direction consistent")
        compiled = self._join_prompt_sections(sections)
        return self._trim_prompt(self._sanitize_video_prompt(compiled), max_chars=900)

    def _compile_script_image_prompt(
        self,
        shot: ShotPlan,
        product_name: str,
    ) -> str:
        shot_index = self._shot_index_from_id(shot.shot_id)
        intent = self._cleanup_prompt_text(shot.on_screen_text or shot.narration or "镜头核心信息")
        base = self._compose_image_prompt(
            product_name=product_name,
            scenario_type=ScenarioType.product_video,
            stage=shot.stage.value,
            shot_index=shot_index,
            title=f"镜头{shot_index}",
            intent=intent,
            base_prompt=shot.reference_image_prompt or shot.visual_prompt,
        )
        sections = [
            f"主体:{product_name}",
            f"镜头{shot_index}:视频关键帧",
            f"画面目标:{intent}",
            f"关键帧描述:{base}",
            f"运动衔接:{self._cleanup_prompt_text(shot.motion_direction or self._default_motion_direction(shot.stage))}",
            "统一约束:无文字、无logo、无水印、无UI叠层",
        ]
        return self._trim_prompt(self._join_prompt_sections(sections), max_chars=480)

    def _compile_script_video_prompt(
        self,
        shot: ShotPlan,
        product_name: str,
    ) -> str:
        shot_index = self._shot_index_from_id(shot.shot_id)
        intent = self._cleanup_prompt_text(shot.on_screen_text or shot.narration or "镜头核心信息")
        visual = self._remove_video_constraint_tail(self._cleanup_prompt_text(shot.visual_prompt))
        motion = self._cleanup_prompt_text(shot.motion_direction or self._default_motion_direction(shot.stage))
        sections = [
            f"Subject:{product_name}",
            f"Shot:{shot_index}",
            f"Intent:{intent}",
            "OutputConstraints: prohibit textual overlays and branding elements",
            f"VisualPlan:{visual}",
            f"MotionPath:{motion}",
            f"CameraRhythm:{self._video_stage_spec(shot.stage.value, shot_index)}",
        ]
        return self._trim_prompt(self._sanitize_video_prompt(self._join_prompt_sections(sections)), max_chars=900)

    def _video_stage_spec(self, stage: str, shot_index: int) -> str:
        if stage == ShotStage.hook.value:
            return "0-2s fast hook, push-in camera, high visual contrast, stable axis"
        if stage == ShotStage.proof.value:
            return "proof-style comparison rhythm, slow lateral move, detail-first framing"
        if stage == ShotStage.cta.value:
            return "closing rhythm, camera settle and hold 1s, conversion-oriented composition"
        return (
            "mid rhythm, clear action path, camera movement smooth and readable, "
            f"shot variation marker {shot_index}"
        )

    def _prompt_quality_score(self, prompt: str, mode: str) -> float:
        text = self._cleanup_prompt_text(prompt).lower()
        if not text:
            return 0.0
        if mode == "video":
            markers = [
                "subject:",
                "shot:",
                "intent:",
                "motionpath:",
                "camerarhythm:",
                "outputconstraints:",
            ]
        else:
            markers = [
                "主体:",
                "镜头:",
                "目标:",
                "核心画面:",
                "质感约束:",
                "统一约束:",
            ]
        hit = sum(1 for marker in markers if marker in text)
        return min(1.0, hit / max(1, len(markers)))

    def _compose_image_prompt(
        self,
        product_name: str,
        scenario_type: ScenarioType,
        stage: str,
        shot_index: int,
        title: str,
        intent: str,
        base_prompt: str,
    ) -> str:
        base = self._cleanup_prompt_text(base_prompt)
        stage_spec = self._image_stage_spec(stage=stage, shot_index=shot_index)
        scenario_spec = self._image_scenario_spec(scenario_type=scenario_type)
        anchor = f"{product_name}，{title}，表达{intent}"
        if scenario_type == ScenarioType.multi_angle_camera:
            anchor = f"上传原图中的同一对象，{title}，表达{intent}；只改变观察角度，不改变主体本体、服装、材质与轮廓"

        if self._needs_image_prompt_upgrade(base):
            return (
                f"{anchor}。{stage_spec}。{scenario_spec}。"
                "高细节、真实质感、画面干净，不要文字、logo、水印。"
            )

        # 已具备镜头和美学字段时，不重复叠加同一段描述，避免越迭代越冗长
        if "高细节、真实质感、画面干净" in base:
            return self._cleanup_prompt_text(base)
        return self._cleanup_prompt_text(
            f"{base}。高细节、真实质感、画面干净，不要文字、logo、水印。"
        )

    def _needs_image_prompt_upgrade(self, prompt: str) -> bool:
        text = self._cleanup_prompt_text(prompt)
        if len(text) < 28:
            return True
        markers = ["景别", "机位", "焦段", "构图", "光线", "色彩", "材质", "层次"]
        hit_count = sum(1 for token in markers if token in text)
        return hit_count < 3

    def _image_stage_spec(self, stage: str, shot_index: int) -> str:
        if stage == ShotStage.hook.value:
            return (
                "景别: hero特写；机位: 45度侧前；焦段: 85mm；"
                "构图: 中心构图+适度留白；光线: 柔光主光+轮廓光"
            )
        if stage == ShotStage.proof.value:
            return (
                "景别: 微距特写；机位: 俯拍与侧拍结合；焦段: 100mm macro；"
                "构图: 纹理占画面主体；光线: 侧逆光强调细节"
            )
        if stage == ShotStage.cta.value:
            return (
                "景别: 中景收束；机位: 正面平视；焦段: 50mm；"
                "构图: 主体稳定居中、转化导向；光线: 均匀柔光"
            )
        angle = "平视" if shot_index % 2 == 1 else "45度侧前"
        return (
            f"景别: 中近景；机位: {angle}；焦段: 50mm；"
            "构图: 三分法突出主体；光线: 自然柔光与环境反射"
        )

    def _stage_for_shot_index(self, shot_index: int) -> ShotStage:
        if shot_index <= 1:
            return ShotStage.hook
        cycle = [ShotStage.feature, ShotStage.proof, ShotStage.cta]
        return cycle[(shot_index - 2) % len(cycle)]

    def _default_delivery_purpose(self, scenario_type: ScenarioType, stage: ShotStage) -> str:
        if scenario_type == ScenarioType.product_image_suite:
            mapping = {
                ShotStage.hook: "主图",
                ShotStage.feature: "场景图",
                ShotStage.proof: "细节图",
                ShotStage.cta: "对比图",
            }
            return mapping.get(stage, "场景图")
        if scenario_type == ScenarioType.model_retouch:
            return "单图精修交付"
        if scenario_type == ScenarioType.multi_angle_camera:
            return "角度展示图"
        return "视频关键帧"

    def _image_scenario_spec(self, scenario_type: ScenarioType) -> str:
        if scenario_type == ScenarioType.product_image_suite:
            return (
                "风格: 高端电商商业摄影；色彩: 中性高级灰+品牌色点缀；"
                "材质纹理可辨识，背景整洁且空间层次清楚"
            )
        if scenario_type == ScenarioType.model_retouch:
            return (
                "风格: 写实人像精修；保持人物身份一致；"
                "肤质保留真实纹理，服装与发丝细节自然"
            )
        if scenario_type == ScenarioType.multi_angle_camera:
            return (
                "风格: AI摄影棚多角度拍摄；透视与尺度稳定；"
                "角度变化清晰，但主体本体、服装、材质和轮廓必须保持一致"
            )
        return (
            "风格: 真实短视频关键帧；色彩克制自然；"
            "主体与环境比例真实，便于后续视频连续性生成"
        )

    def _parse_insight(self, raw: Any, brief: ProductBrief) -> VisualInsight:
        if not isinstance(raw, dict):
            return self._mock_insight(brief)

        summary = str(raw.get("summary") or f"图片展示了{brief.product_name}的核心外观和使用场景。")
        visible_points = [str(item) for item in raw.get("visible_points", [])][:6]
        risks = [str(item) for item in raw.get("risks", [])][:6]
        return VisualInsight(summary=summary, visible_points=visible_points, risks=risks)

    def _parse_scripts(self, raw_scripts: Any, brief: ProductBrief) -> list[ScriptOption]:
        if not isinstance(raw_scripts, list):
            return []

        scripts: list[ScriptOption] = []
        for idx, raw in enumerate(raw_scripts[:3]):
            if not isinstance(raw, dict):
                continue
            format_type = self._normalize_format_type(
                str(raw.get("format_type") or ""),
                idx=idx,
            )
            shots = self._parse_shots(
                raw_shots=raw.get("shots", []),
                desired_duration=brief.desired_duration_sec,
                brief=brief,
            )
            if not shots:
                continue
            total = sum(shot.duration_sec for shot in shots)
            scripts.append(
                ScriptOption(
                    script_id=f"script-{idx + 1}",
                    title=str(raw.get("title") or f"方案{idx + 1}"),
                    format_type=format_type,
                    strategy_note=str(raw.get("strategy_note") or "先引起停留，再放大使用价值。"),
                    compliance_note=str(raw.get("compliance_note") or "避免绝对化词汇，使用体验型表达。"),
                    total_duration_sec=max(30, min(50, total)),
                    shots=shots,
                )
            )
        return scripts

    def _ensure_three_scripts(
        self,
        scripts: list[ScriptOption],
        brief: ProductBrief,
    ) -> list[ScriptOption]:
        if len(scripts) >= 3:
            return scripts[:3]

        merged = [item.model_copy(deep=True) for item in scripts]
        fallback_scripts = self._mock_scripts(brief)
        for item in fallback_scripts:
            if len(merged) >= 3:
                break
            item.script_id = f"script-{len(merged) + 1}"
            merged.append(item)
        return merged[:3]

    def _parse_shots(
        self,
        raw_shots: Any,
        desired_duration: int,
        brief: ProductBrief,
    ) -> list[ShotPlan]:
        if not isinstance(raw_shots, list):
            return []

        shots: list[ShotPlan] = []
        for idx, raw in enumerate(raw_shots[:10]):
            if not isinstance(raw, dict):
                continue

            stage_name = str(raw.get("stage") or "feature")
            stage_value = stage_name if stage_name in ShotStage._value2member_map_ else ShotStage.feature.value

            try:
                duration = int(raw.get("duration_sec") or 5)
            except (TypeError, ValueError):
                duration = 5
            duration = max(3, min(8, duration))

            visual_prompt = str(raw.get("visual_prompt") or "展示产品细节与真实使用场景")
            ref_prompt = str(raw.get("reference_image_prompt") or visual_prompt)

            shot = ShotPlan(
                shot_id=f"shot-{idx + 1}",
                stage=ShotStage(stage_value),
                duration_sec=duration,
                visual_prompt=visual_prompt,
                reference_image_prompt=ref_prompt,
                motion_direction=str(raw.get("motion_direction") or ""),
                voiceover_direction=str(raw.get("voiceover_direction") or ""),
                narration=str(raw.get("narration") or "这个细节在日常使用里很加分。"),
                on_screen_text=str(raw.get("on_screen_text") or "细节看得见"),
            )
            shots.append(self._enhance_shot_detail(shot, brief.product_name))

        if len(shots) < 6:
            return []

        shots = self._enforce_shot_rules(shots, desired_duration)
        return shots

    def _enforce_shot_rules(
        self,
        shots: list[ShotPlan],
        desired_duration: int,
    ) -> list[ShotPlan]:
        adjusted = [shot.model_copy() for shot in shots]

        if adjusted:
            adjusted[0].stage = ShotStage.hook
            adjusted[0].duration_sec = 3
            adjusted[0].reference_image_prompt = (
                adjusted[0].reference_image_prompt or adjusted[0].visual_prompt
            )

        for shot in adjusted[1:]:
            shot.reference_image_prompt = shot.reference_image_prompt or shot.visual_prompt

        total = sum(shot.duration_sec for shot in adjusted)
        if total < 30 or total > 50:
            adjusted = self._retime_shots(adjusted, desired_duration)

        return adjusted

    def _retime_shots(self, shots: list[ShotPlan], desired_duration: int) -> list[ShotPlan]:
        target = max(30, min(50, desired_duration))
        current = sum(shot.duration_sec for shot in shots)
        if current == target:
            return shots

        adjusted = [shot.model_copy() for shot in shots]
        adjustable_indices = list(range(1, len(adjusted))) or [0]

        i = 0
        while current != target and adjustable_indices:
            idx = adjustable_indices[i % len(adjustable_indices)]
            shot = adjusted[idx]
            if current < target and shot.duration_sec < 8:
                shot.duration_sec += 1
                current += 1
            elif current > target and shot.duration_sec > 3:
                shot.duration_sec -= 1
                current -= 1
            i += 1
            if i > 400:
                break
        return adjusted

    def _to_data_url(self, image_bytes: bytes, mime_type: str) -> str:
        encoded = base64.b64encode(image_bytes).decode("utf-8")
        return f"data:{mime_type};base64,{encoded}"

    def _enhance_shot_detail(self, shot: ShotPlan, product_name: str) -> ShotPlan:
        result = shot.model_copy(deep=True)

        stage_guides = {
            ShotStage.hook: "先抛痛点反差，再给出结果预告，制造继续观看动机。",
            ShotStage.feature: "展示真实使用动作和细节反馈，让用户知道为什么值得买。",
            ShotStage.proof: "给出对比或使用后体验，增强可信度与代入感。",
            ShotStage.cta: "强调适合人群和决策门槛，引导点击了解详情。",
        }

        if len(result.narration.strip()) < 20:
            result.narration = (
                f"{result.narration.strip()} "
                f"{stage_guides.get(result.stage, '突出关键信息并自然推进下单。')}"
            ).strip()

        result.visual_prompt = self._sanitize_video_prompt(result.visual_prompt)
        if len(result.visual_prompt.strip()) < 12:
            result.visual_prompt = (
                f"{product_name}在真实生活场景中展示，突出产品关键细节，"
                "主体清晰，动作自然，镜头稳定推进。"
            )

        reference_prompt = self._cleanup_prompt_text(result.reference_image_prompt or "")
        shot_index = self._shot_index_from_id(result.shot_id)
        if not reference_prompt:
            reference_prompt = (
                f"{product_name}静态分镜关键帧，突出{result.on_screen_text}，"
                "主体清晰，背景简洁，自然光。"
            )
        result.reference_image_prompt = self._compose_image_prompt(
            product_name=product_name,
            scenario_type=ScenarioType.product_video,
            stage=result.stage.value,
            shot_index=shot_index,
            title=f"镜头{shot_index}关键帧",
            intent=result.on_screen_text or "镜头核心卖点",
            base_prompt=reference_prompt,
        )

        if len(result.on_screen_text.strip()) < 3:
            result.on_screen_text = "细节值得看"

        if not result.motion_direction or len(result.motion_direction.strip()) < 4:
            result.motion_direction = self._default_motion_direction(result.stage)
        else:
            result.motion_direction = self._cleanup_prompt_text(result.motion_direction)

        if not result.voiceover_direction or len(result.voiceover_direction.strip()) < 4:
            result.voiceover_direction = self._default_voiceover_direction(result.stage)
        else:
            result.voiceover_direction = self._cleanup_prompt_text(result.voiceover_direction)

        return result

    def _shot_index_from_id(self, shot_id: str) -> int:
        text = str(shot_id or "").strip().lower()
        match = re.search(r"(\d+)$", text)
        if match:
            try:
                return max(1, int(match.group(1)))
            except Exception:
                return 1
        return 1

    def _mock_analyze_and_plan(
        self,
        brief: ProductBrief,
    ) -> tuple[VisualInsight, list[ScriptOption]]:
        insight = self._mock_insight(brief)
        return insight, self._mock_scripts(brief)

    def _mock_project_plan(
        self,
        brief: ProductBrief,
        scenario_type: ScenarioType,
        template_name: str,
        quality_level: QualityLevel,
    ) -> ProjectPlan:
        if scenario_type == ScenarioType.model_retouch:
            shots = [
                PlanShot(
                    shot_id="shot-1",
                    title="面部细节优化",
                    intent="提升皮肤质感和表情自然度",
                    duration_sec=4,
                    stage=ShotStage.feature,
                    image_prompt=f"{brief.product_name}模特图精修，面部光线均匀，肤色自然，保留真实毛孔质感",
                    video_prompt=self._sanitize_video_prompt(
                        "模特中景，轻微转头展示面部细节提升，动作自然"
                    ),
                    delivery_purpose="单图精修交付",
                    retouch_prompt="微调面部亮度和眼神，避免塑料感",
                ),
                PlanShot(
                    shot_id="shot-2",
                    title="动作姿态修正",
                    intent="提升肢体姿态与构图",
                    duration_sec=4,
                    stage=ShotStage.feature,
                    image_prompt=f"{brief.product_name}模特图精修，调整手部与肩颈姿态，服装褶皱自然",
                    video_prompt=self._sanitize_video_prompt("半身镜头展示动作连贯性和服装质感"),
                    delivery_purpose="单图精修交付",
                    retouch_prompt="修正手部姿态和肩颈线条，避免肢体扭曲",
                ),
                PlanShot(
                    shot_id="shot-3",
                    title="质感统一",
                    intent="统一光影和背景质感",
                    duration_sec=4,
                    stage=ShotStage.proof,
                    image_prompt=f"{brief.product_name}模特图精修，统一光影层次，背景干净，色彩高级",
                    video_prompt=self._sanitize_video_prompt("全身缓推镜头，展示整体精修前后差异"),
                    delivery_purpose="单图精修交付",
                    retouch_prompt="统一白平衡，提升服装纹理清晰度",
                ),
                PlanShot(
                    shot_id="shot-4",
                    title="交付主图",
                    intent="形成可直接投放素材",
                    duration_sec=4,
                    stage=ShotStage.cta,
                    image_prompt=f"{brief.product_name}精修主图，主体突出，构图稳定，可直接电商投放",
                    video_prompt=self._sanitize_video_prompt("定格镜头展示最终精修主图效果"),
                    delivery_purpose="单图精修交付",
                    retouch_prompt="输出主图比例并保持人物一致性",
                ),
            ]
            shots = self._ensure_plan_prompt_diversity(
                shots=shots,
                product_name=brief.product_name,
                scenario_type=scenario_type,
            )
            shots = self._apply_creative_direction_to_shots(
                shots=shots,
                creative_direction=brief.creative_direction,
                scenario_type=scenario_type,
            )
            return ProjectPlan(
                scenario_type=scenario_type,
                template_name=template_name,
                channels=brief.channels,
                summary=f"{brief.product_name}模特图精修方案（{quality_level.value}）",
                planner_notes=[
                    "source:mock-fallback",
                    "先做人像一致性，再做局部精修",
                    "交付前保留可回退版本",
                ],
                shots=shots,
            )

        if scenario_type == ScenarioType.multi_angle_camera:
            shots = [
                PlanShot(
                    shot_id="shot-front",
                    title="正面主视角",
                    intent="建立主体形态和材质基准",
                    duration_sec=4,
                    stage=ShotStage.feature,
                    image_prompt="基于上传原图中的同一对象生成正面主视角，yaw 0°，pitch 0°，50mm；只改变观察角度，不改变主体本体、服装、材质与轮廓；保持原图对象识别一致。",
                    video_prompt=self._sanitize_video_prompt("正面稳定镜头，不要文字"),
                    delivery_purpose="角度展示图",
                ),
                PlanShot(
                    shot_id="shot-left45",
                    title="左前45度",
                    intent="展示立体结构和侧面材质",
                    duration_sec=4,
                    stage=ShotStage.feature,
                    image_prompt="基于上传原图中的同一对象生成左前45度视角，yaw -45°，pitch 0°，50mm；只改变观察角度，保持对象尺度、服装、材质与轮廓一致。",
                    video_prompt=self._sanitize_video_prompt("左前45度轻微平移镜头，不要文字"),
                    delivery_purpose="角度展示图",
                ),
                PlanShot(
                    shot_id="shot-right45",
                    title="右前45度",
                    intent="补全另一侧结构信息",
                    duration_sec=4,
                    stage=ShotStage.feature,
                    image_prompt="基于上传原图中的同一对象生成右前45度视角，yaw 45°，pitch 0°，50mm；只改变观察角度，保持对象尺度、服装、材质与轮廓一致。",
                    video_prompt=self._sanitize_video_prompt("右前45度稳定镜头，不要文字"),
                    delivery_purpose="角度展示图",
                ),
                PlanShot(
                    shot_id="shot-top",
                    title="俯拍视角",
                    intent="展示顶部细节与结构",
                    duration_sec=4,
                    stage=ShotStage.proof,
                    image_prompt="基于上传原图中的同一对象生成俯拍视角，yaw 0°，pitch -25°，35mm；只改变观察角度，透视自然，不过度拉伸，不改变主体本体。",
                    video_prompt=self._sanitize_video_prompt("俯拍慢推镜头，不要文字"),
                    delivery_purpose="角度展示图",
                ),
            ]
            shots = self._ensure_plan_prompt_diversity(
                shots=shots,
                product_name=brief.product_name,
                scenario_type=scenario_type,
            )
            return ProjectPlan(
                scenario_type=scenario_type,
                template_name=template_name,
                channels=brief.channels,
                summary=f"{brief.product_name} 多角度拍摄方案",
                planner_notes=[
                    "source:mock-fallback",
                    "覆盖主视角、侧视角、俯拍视角",
                    "保持主体比例、材质和光线一致",
                ],
                shots=shots,
            )

        if scenario_type == ScenarioType.product_video:
            shots = [
                PlanShot(
                    shot_id="shot-1",
                    title="外观吸引",
                    intent="3秒建立停留",
                    duration_sec=5,
                    stage=ShotStage.hook,
                    image_prompt=f"{brief.product_name}竖屏关键帧，外观高质感特写，背景简洁",
                    video_prompt=self._sanitize_video_prompt(
                        f"{brief.product_name}特写开场，快速推进到核心外观细节，光线自然高级感"
                    ),
                    delivery_purpose="视频关键帧",
                ),
                PlanShot(
                    shot_id="shot-2",
                    title="场景演示",
                    intent="展示真实使用动作和收益",
                    duration_sec=5,
                    stage=ShotStage.feature,
                    image_prompt=f"{brief.product_name}真实使用场景关键帧，手部动作清晰，主体突出",
                    video_prompt=self._sanitize_video_prompt(
                        f"{brief.product_name}中景演示，手部操作连贯，镜头平稳推进"
                    ),
                    delivery_purpose="视频关键帧",
                ),
                PlanShot(
                    shot_id="shot-3",
                    title="收束转化",
                    intent="输出决策理由和行动引导",
                    duration_sec=5,
                    stage=ShotStage.cta,
                    image_prompt=f"{brief.product_name}收束镜头关键帧，主体居中，画面克制",
                    video_prompt=self._sanitize_video_prompt(
                        f"{brief.product_name}收束镜头，稳定构图，强化购买动机"
                    ),
                    delivery_purpose="视频关键帧",
                ),
            ]
            shots = self._ensure_plan_prompt_diversity(
                shots=shots,
                product_name=brief.product_name,
                scenario_type=scenario_type,
            )
            return ProjectPlan(
                scenario_type=scenario_type,
                template_name=template_name,
                channels=brief.channels,
                summary=f"{brief.product_name} 15秒产品视频方案",
                planner_notes=[
                    "source:mock-fallback",
                    "每镜头5秒，总长15秒",
                    "禁止任何画面文字和水印",
                ],
                shots=shots,
            )

        shots = [
            PlanShot(
                shot_id="shot-1",
                title="主图精修",
                intent="输出电商主图",
                duration_sec=4,
                stage=ShotStage.hook,
                image_prompt=f"{brief.product_name}电商主图精修，主体清晰，背景干净，质感提升",
                video_prompt=self._sanitize_video_prompt("产品静态展示，细节层次清晰"),
                delivery_purpose="主图",
            ),
            PlanShot(
                shot_id="shot-2",
                title="场景化展示",
                intent="展示产品在真实生活场景中的状态",
                duration_sec=4,
                stage=ShotStage.feature,
                image_prompt=f"{brief.product_name}生活场景图，光线自然，主体突出，氛围真实",
                video_prompt=self._sanitize_video_prompt("中景展示产品融入生活场景"),
                delivery_purpose="场景图",
            ),
            PlanShot(
                shot_id="shot-3",
                title="细节特写",
                intent="凸显材质与卖点细节",
                duration_sec=4,
                stage=ShotStage.proof,
                image_prompt=f"{brief.product_name}细节特写，材质纹理清晰，构图稳定",
                video_prompt=self._sanitize_video_prompt("特写慢推镜头，展示材质细节"),
                delivery_purpose="细节图",
            ),
            PlanShot(
                shot_id="shot-4",
                title="多平台输出",
                intent="形成多渠道可复用素材",
                duration_sec=4,
                stage=ShotStage.cta,
                image_prompt=f"{brief.product_name}平台通用收束图，主体居中，留白合理",
                video_prompt=self._sanitize_video_prompt("稳定镜头收束，保持主体一致"),
                delivery_purpose="对比图",
            ),
        ]
        shots = self._ensure_plan_prompt_diversity(
            shots=shots,
            product_name=brief.product_name,
            scenario_type=scenario_type,
        )
        return ProjectPlan(
            scenario_type=scenario_type,
            template_name=template_name,
            channels=brief.channels,
            summary=f"{brief.product_name} 场景图生成方案",
            planner_notes=["source:mock-fallback", "先主图后场景", "自动筛除低清晰度结果"],
            shots=shots,
        )

    def _mock_insight(self, brief: ProductBrief) -> VisualInsight:
        points = brief.key_features or ["外观质感", "上手体验", "场景适配"]
        return VisualInsight(
            summary=f"图片主体聚焦{brief.product_name}，适合用细节+场景组合表达价值。",
            visible_points=points,
            risks=["避免绝对化承诺", "避免医疗功效或极限词"],
        )

    def _mock_scripts(self, brief: ProductBrief) -> list[ScriptOption]:
        templates = [
            ("口播讲解", "痛点反差口播"),
            ("场景剧情", "生活场景剧情"),
            ("对比测评", "同价位对比测评"),
        ]
        scripts: list[ScriptOption] = []
        for idx, (format_type, title) in enumerate(templates, start=1):
            shots = self._build_shot_template(brief, idx)
            scripts.append(
                ScriptOption(
                    script_id=f"script-{idx}",
                    title=title,
                    format_type=format_type,
                    strategy_note="先让用户停留，再给理由，最后顺势下单。",
                    compliance_note="采用体验表达，不触发绝对化宣传风险。",
                    total_duration_sec=sum(shot.duration_sec for shot in shots),
                    shots=shots,
                )
            )
        return scripts

    def _build_shot_template(self, brief: ProductBrief, seed: int) -> list[ShotPlan]:
        format_type = self._default_format_type(seed - 1)
        durations = self._duration_plan(brief.desired_duration_sec)
        features = brief.key_features or ["细节做工", "使用效率", "场景适配"]
        hook_lines = [
            "很多人选这类产品时，第一眼看错了重点。",
            "你是不是也遇到过：看着不错，用起来差一口气？",
            "别急着看参数，先看这个最容易被忽略的细节。",
        ]
        hook = hook_lines[(seed - 1) % len(hook_lines)]

        shot_defs = [
            (
                ShotStage.hook,
                f"{hook} 30秒内看完你就知道，这个品为什么能留住回头客。",
                "先看关键差异",
            ),
            (
                ShotStage.feature,
                f"先看{features[0]}，现场操作一步到位，反馈直接，用户很容易感知到差异。",
                features[0],
            ),
            (
                ShotStage.feature,
                f"再看{features[min(1, len(features) - 1)]}，连续使用时更顺手，细节不会拖后腿。",
                features[min(1, len(features) - 1)],
            ),
            (
                ShotStage.feature,
                "放到真实生活场景里演示，重点看效率和稳定性，用户一眼能感知省心点。",
                "真实场景演示",
            ),
            (
                ShotStage.proof,
                "连续使用后的状态更说明问题：输出稳定、细节不掉线，体验更可预期。",
                "连续使用反馈",
            ),
            (
                ShotStage.proof,
                "同价位对比里，这款把高频使用痛点处理得更干净，决策成本更低。",
                "同价位体验差异",
            ),
            (
                ShotStage.cta,
                "如果你在意长期使用体验，这个版本建议先加入候选清单再做决定。",
                "先加入候选",
            ),
            (
                ShotStage.cta,
                f"{brief.cta_text}，把完整参数、真实评价和使用建议一次看清。",
                brief.cta_text,
            ),
        ]

        shots: list[ShotPlan] = []
        for idx, (stage, narration, on_screen) in enumerate(shot_defs):
            prompt = (
                f"{brief.platform}短视频风格，形式{format_type}，突出{brief.product_name}，"
                f"镜头{idx + 1}重点：{on_screen}，画面自然真实，避免夸张广告感"
            )
            shot = ShotPlan(
                shot_id=f"shot-{idx + 1}",
                stage=stage,
                duration_sec=durations[idx],
                visual_prompt=prompt,
                reference_image_prompt=f"产品主体清晰，突出{on_screen}，画面干净，光线自然",
                motion_direction=self._default_motion_direction(stage),
                voiceover_direction=self._default_voiceover_direction(stage),
                narration=narration,
                on_screen_text=on_screen,
            )
            shots.append(self._enhance_shot_detail(shot, brief.product_name))
        return shots

    def _fallback_refine_script_for_generation(
        self,
        brief: ProductBrief,
        script: ScriptOption,
    ) -> ScriptOption:
        refined = script.model_copy(deep=True)
        for shot in refined.shots:
            normalized = self._enhance_shot_detail(shot, brief.product_name)
            shot.reference_image_prompt = normalized.reference_image_prompt
            shot.visual_prompt = normalized.visual_prompt
            shot.motion_direction = normalized.motion_direction
            shot.voiceover_direction = normalized.voiceover_direction
            shot.narration = normalized.narration
            shot.on_screen_text = normalized.on_screen_text
        return refined

    def _merge_generation_refinement(
        self,
        baseline: ScriptOption,
        payload: dict[str, Any],
        product_name: str,
    ) -> ScriptOption:
        refined = baseline.model_copy(deep=True)
        raw_shots = payload.get("shots", []) if isinstance(payload, dict) else []
        if not isinstance(raw_shots, list):
            return refined

        updates: dict[str, dict[str, Any]] = {}
        for item in raw_shots:
            if not isinstance(item, dict):
                continue
            shot_id = str(item.get("shot_id") or "").strip()
            if shot_id:
                updates[shot_id] = item

        for shot in refined.shots:
            item = updates.get(shot.shot_id)
            if not item:
                continue
            ref_prompt = str(item.get("reference_image_prompt") or shot.reference_image_prompt or "").strip()
            vis_prompt = str(item.get("visual_prompt") or shot.visual_prompt or "").strip()
            motion = str(item.get("motion_direction") or shot.motion_direction or "").strip()
            voice = str(item.get("voiceover_direction") or shot.voiceover_direction or "").strip()
            narration = str(item.get("narration") or shot.narration or "").strip()
            text = str(item.get("on_screen_text") or shot.on_screen_text or "").strip()

            shot.reference_image_prompt = self._cleanup_prompt_text(ref_prompt)
            shot.visual_prompt = self._sanitize_video_prompt(vis_prompt)
            shot.motion_direction = self._cleanup_prompt_text(motion)
            shot.voiceover_direction = self._cleanup_prompt_text(voice)
            if narration:
                shot.narration = narration
            if text:
                shot.on_screen_text = text[:14]

            normalized = self._enhance_shot_detail(shot, product_name)
            shot.reference_image_prompt = normalized.reference_image_prompt
            shot.visual_prompt = normalized.visual_prompt
            shot.motion_direction = normalized.motion_direction
            shot.voiceover_direction = normalized.voiceover_direction
            shot.narration = normalized.narration
            shot.on_screen_text = normalized.on_screen_text
        return refined

    def _cleanup_prompt_text(self, text: str) -> str:
        value = str(text or "").strip()
        if not value:
            return ""
        value = value.replace("视频生成提示词：", "")
        value = value.replace("分镜图提示词：", "")
        value = value.replace("镜头用途:", "")
        value = value.replace("镜头用途：", "")
        value = value.replace("旁白内容:", "")
        value = value.replace("旁白内容：", "")
        value = value.replace("画面字幕:", "")
        value = value.replace("画面字幕：", "")
        value = value.replace("候选版本1", "")
        value = value.replace("候选版本2", "")
        value = value.replace("候选版本3", "")
        value = value.replace("候选版本4", "")
        value = re.sub(r"\s+", " ", value)
        value = value.replace("。。", "。")
        return value.strip(" 。")

    def _sanitize_video_prompt(self, text: str) -> str:
        value = self._cleanup_prompt_text(text)
        value = self._remove_video_constraint_tail(value)
        banned_words = [
            "字幕",
            "文字",
            "文案",
            "候选版本",
            "提示词",
            "镜头用途",
            "旁白内容",
            "画面字幕",
        ]
        for word in banned_words:
            value = value.replace(word, "")
        value = re.sub(r"\s+", " ", value).strip(" ，。")
        suffix = "No text, no subtitles, no captions, no logo, no watermark, no letters, no UI overlays."
        if not value:
            return suffix
        return f"{value}。{suffix}"

    def _remove_video_constraint_tail(self, text: str) -> str:
        return re.sub(
            r"No text[^.。]*[.。]?",
            "",
            str(text or ""),
            flags=re.IGNORECASE,
        ).strip(" ，。;")

    def _default_image_prompt(self, product_name: str, stage: str) -> str:
        if stage == ShotStage.hook.value:
            return (
                f"{product_name}高质感特写关键帧，景别: hero特写，机位:45度侧前，焦段:85mm，"
                "构图中心稳定，柔光主光+轮廓光，材质纹理清晰，背景干净"
            )
        if stage == ShotStage.proof.value:
            return (
                f"{product_name}细节特写关键帧，景别:微距，机位:俯拍+侧拍，焦段:100mm macro，"
                "突出纹理与工艺证据，侧逆光强化层次"
            )
        if stage == ShotStage.cta.value:
            return (
                f"{product_name}收束关键帧，景别:中景，机位:正面平视，焦段:50mm，"
                "主体居中，留白可用于转化区域，光线均匀干净"
            )
        return (
            f"{product_name}场景关键帧，景别:中近景，机位:平视，焦段:50mm，"
            "三分法构图，主体清晰，动作自然，光线层次真实"
        )

    def _default_motion_direction(self, stage: ShotStage) -> str:
        if stage == ShotStage.hook:
            return "开场快速推进到主体特写，动作干脆有冲击力。"
        if stage == ShotStage.feature:
            return "中景到特写平稳切换，展示手部操作和关键细节。"
        if stage == ShotStage.proof:
            return "先给全景再切细节对比，镜头缓慢横移强调差异。"
        return "镜头轻推至产品与行动按钮，停留2秒强化下单动作。"

    def _default_voiceover_direction(self, stage: ShotStage) -> str:
        if stage == ShotStage.hook:
            return "语速偏快，语气有张力，先抛问题再给承诺。"
        if stage == ShotStage.feature:
            return "语速中等，语气客观，边演示边解释价值点。"
        if stage == ShotStage.proof:
            return "语速平稳，强调对比结果和使用反馈。"
        return "语气坚定但克制，明确行动建议并收束。"

    def _normalize_format_type(self, raw: str, idx: int) -> str:
        raw = raw.strip()
        if raw in {"口播讲解", "场景剧情", "对比测评", "清单推荐"}:
            return raw
        return self._default_format_type(idx)

    def _default_format_type(self, idx: int) -> str:
        ordered = ["口播讲解", "场景剧情", "对比测评"]
        return ordered[idx % len(ordered)]

    def _duration_plan(self, desired_duration: int) -> list[int]:
        total = max(30, min(50, desired_duration))
        base = [3, 5, 5, 5, 5, 5, 4, 3]
        delta = total - sum(base)
        idx = 1
        while delta != 0:
            shot_index = idx % len(base)
            if delta > 0 and base[shot_index] < 8:
                base[shot_index] += 1
                delta -= 1
            elif delta < 0 and base[shot_index] > 3:
                base[shot_index] -= 1
                delta += 1
            idx += 1
            if idx > 200:
                break
        return base
