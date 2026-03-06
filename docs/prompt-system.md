# 提示词系统（VL + 编译器）

## 目标
- VL 负责“规划与结构化输出”
- 图/视频提示词由编译器派生
- 用户只编辑“可读表单”，不直接改 JSON

## 分层
- L0 System：角色、边界、禁字幕/水印/文字
- L1 Task：业务目标与平台风格
- L2 Schema：严格结构化输出
- L3 Model Adapter：映射到 KIE 图/视频参数
- L4 Guardrails：禁词与修复

## 关键约束
- 视频默认注入：`No text/subtitles/logo/watermark/UI overlays`
- 输出必须通过 Schema 校验
- 失败：JSON repair → fallback
- 方案分镜必须包含 `delivery_purpose`（不可为空）
- 商品棚拍 `delivery_purpose` 固定枚举：`主图/场景图/细节图/对比图`

## 提示词编译结构（2026-03-05）
- 生图提示词统一结构：
  - `主体` / `镜头` / `目标` / `用途` / `核心画面` / `质感约束` / `统一约束`
  - 模特精修额外注入：`精修目标` / `身份锁定` / `局部修正` / `避免事项`
- 生视频提示词统一结构：
  - `Subject` / `Shot` / `Intent` / `ShotPurpose` / `VisualPlan` / `MotionPath` / `CameraRhythm` / `QualityTarget` / `OutputConstraints`
- 统一质量评分：
  - 编译器对 image/video prompt 做结构命中评分（0~1）
  - 平均分回写 `guardrail_report.image_prompt_quality_avg` 与 `guardrail_report.video_prompt_quality_avg`


## 多图输入角色声明（2026-03-06）
- 只要向图模型传入 2 张及以上图片，提示词中必须显式声明每张图的角色，禁止只依赖数组顺序让模型自行猜测。
- 标准写法示例：
  - `图1=主图/基底图`：决定动作、构图、背景、原服装或原对象本体。
  - `图2=身份锚点图`：只决定人物身份、发型、肤色、身体比例，不决定服装与背景。
  - `图3+ = 风格参考图`：只提供质感、打光、氛围参考，不覆盖主图的主体定义。
- 商品棚拍：若用户上传风格参考图，必须显式写明“主图为主体真源，风格图只提供质感/氛围参考”。
- 模特精修：必须显式写明“主图决定动作、构图、背景、原套图服装；锚点图只决定人物身份”。
- 多角度工坊：必须显式写明“上传原图中的同一对象为主体；只改变观察角度，不改变主体本体、服装、材质与轮廓”。
