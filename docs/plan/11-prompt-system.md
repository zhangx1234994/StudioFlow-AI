# 11 提示词与 VL 体系（P1 冻结版）

## 1) Planner（VL 规划）
- 输入：用户表单 + 上传素材 + 风格参考 + 业务目标。
- 输出：结构化方案（严格 JSON），禁止自由散文。
- 通过 Schema 校验后才允许进入 Compiler。

## 2) Compiler（执行方案）
- 规划方案 -> 生图指令（静态）。
- 规划方案 -> 生视频指令（动态）。
- 参数映射：比例、分辨率、候选数、时长、并发档位。
- 用户仅可编辑“可读字段”（目标/风格/限制/镜头重点），不可直接改底层 JSON。

## 3) Guardrails（硬约束）
- 禁字幕、禁水印、禁口号、禁 UI overlay（视频默认注入）。
- 禁夸张承诺与误导性疗效类文案。
- 人像场景增加“去刻板标签”约束，避免身份偏见词。
- 校验失败流程：`schema_fail -> repair -> retry -> explicit_error`。

## 4) 质量回传与优化闭环（冻结）
- 每次生成必须记录：
  - prompt_version
  - planner_output_hash
  - model_params
  - quality_score（自动）
  - review_decision（人工）
- 自动评分维度：
  - 图像：清晰度、构图完整度、文本污染、人像一致性
  - 视频：时序稳定性、抖动、文字污染、镜头一致性
- 每日离线任务输出：
  - 低分样本清单
  - 高通过率片段库
  - 建议升级/回滚的 prompt 版本

## 5) Prompt 版本管理（冻结）
- 版本键：`tool_type + scenario + version + updated_at`。
- 状态：`draft | active | deprecated`。
- 发布策略：
  - 新版本先灰度到 10% 任务；
  - 若通过率下降 > 8%，自动回滚上一个 active 版本。
- 审计要求：版本发布人、变更说明、回滚记录必须可查。

## 6) Planner 输出 Schema（统一模板）
```json
{
  "scenario_type": "product_image_suite|model_retouch|multi_angle_camera|product_video",
  "summary": "string",
  "shots": [
    {
      "shot_id": "string",
      "title": "string",
      "intent": "string",
      "delivery_purpose": "string",
      "image_prompt": "string",
      "video_prompt": "string",
      "retouch_goal": "string",
      "retouch_prompt": "string",
      "identity_lock_rules": ["string"],
      "local_edit_instructions": ["string"],
      "negative_constraints": ["string"]
    }
  ]
}
```

## 7) Compiler 映射表（核心字段）
- 图像类：
  - image_prompt → 生图提示词
  - image_aspect_ratio / image_resolution → 模型参数
- 视频类：
  - video_prompt → 生视频提示词
  - duration / aspect_ratio / n_frames → 模型参数
- 模特精修：
  - retouch_prompt / retouch_goal → 生图精修提示词
  - identity_lock_rules → 一致性约束
