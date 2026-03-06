# API 约定（核心）

> 仅记录核心接口与关键字段，详细字段以 `app/schemas.py` 为准。

## 项目创建
`POST /api/v1/projects`
- 必填：`product_name` + `image` 或 `image_public_url`
- 关键字段：
  - `tool_type`, `scenario_type`, `template_name`
  - `image_public_url`, `image_mime`, `image_suffix`
  - `reference_image_public_urls`, `style_reference_image_public_urls`

## 批量（模特精修）
`POST /api/v1/tools/model_retouch/batch-create`
- `images[]` 或 `image_public_urls`
- 支持 `style_reference_images[]` / `identity_image`
- 默认策略（可改）：`background_policy=keep_original`、`output_aspect_ratio=original`、`retouch_strength=light`
- 返回新增：`controller_project_id`（批次控制项目）

`GET /api/v1/tools/model_retouch/batches/{batch_group_id}`
- 批次聚合状态唯一真源：总数/运行中/失败/已完成、身份锚点状态、项目列表

`POST /api/v1/tools/model_retouch/batches/{batch_group_id}/identity/generate-candidate`
- 批次级身份候选生成（单锚点）
- `identity_source` 固定三选一：`use_uploaded | beautify_uploaded | generate_new`
- 语义：
  - `use_uploaded`：直接使用当前上传模特图作为候选锚点
  - `beautify_uploaded`：基于上传模特图做轻度精修后生成候选锚点
  - `generate_new`：按描述生成新的模特候选锚点

`POST /api/v1/tools/model_retouch/batches/{batch_group_id}/identity/upload`
- 在身份确认步骤替换模特图（覆盖之前上传）
- 入参：`image_public_url`（必填），`image_mime/image_suffix`（可选）
- 返回：批次汇总（`identity_status` 维持 `pending`，需显式确认锚点）

`POST /api/v1/tools/model_retouch/batches/{batch_group_id}/identity/clear-uploaded`
- 移除当前上传模特图（用于“X掉重传”）
- 行为：上传模特图从候选列表下线（软删除），若该图是当前锚点则批次回到 `identity_status=pending`
- 入参：`asset_id`（可选，不传默认移除最新上传模特图）

`POST /api/v1/tools/model_retouch/batches/{batch_group_id}/identity/confirm`
- 批次级身份确认，确认后锚点同步到批次内全部项目

`POST /api/v1/tools/model_retouch/batches/{batch_group_id}/generate`
- 批次并行精修触发，支持 `async_mode` 与可选 `project_ids[]`
- 支持 `output_aspect_ratio`（默认 `original`）：`original` 表示按原图比例（后端映射 `image_aspect_ratio=auto`）
- 当 `output_aspect_ratio=original` 时，前端不传 `image_resolution`，后端也不向模型传该字段，避免强制降到固定分辨率

`POST /api/v1/tools/model_retouch/batches/{batch_group_id}/retry`
- 批次失败重试；默认仅重跑失败项，也可指定 `project_ids[]`

## 方案与提示词
- `POST /api/v1/projects/{id}/plan`
  - 请求体支持：`force`、`async_mode`
  - 建议前端使用 `async_mode=true`，立即返回并通过 `GET /progress` 轮询状态
  - VL 模型调用支持模型回退：当主模型返回 `InvalidEndpointOrModel.NotFound`（404）时，后端自动切换到可用候选模型重试，避免流程直接失败
  - 商品棚拍会自动透传执行提示到 VL 规划器（后端注入）：
    - `expected_shot_count = set_config.target_final_count`
    - `takes_per_shot = set_config.takes_per_shot`
    - `target_candidate_assets = expected_shot_count * takes_per_shot`
  - 大镜头数（>=7）启用两段式规划：先生成大纲，再并发逐镜头补全提示词；不足镜头会自动补齐到目标数量
- `POST /api/v1/projects/{id}/derive-prompts`
  - `prompt_pack.guardrail_report` 现包含：
    - `image_prompt_quality_avg`（0~1）
    - `video_prompt_quality_avg`（0~1）
  - 用于评估“结构完整度”是否达到可执行阈值

## 生成
- `POST /api/v1/projects/{id}/generate-images`
- `POST /api/v1/projects/{id}/generate-videos`
- 多角度：`/multi-angle/plan` & `/multi-angle/generate`

`generate-images` 结果约束（2026-03-04 起）：
- 仅当模型真实返回生成图（`metadata.source=generated`）时，资产状态为 `ready`。
- 若走回退（`metadata.source=original`）：
  - 生产模式（`MVP_USE_MOCK_PROVIDERS=false`）标记为 `failed`，并给出可重试错误。
  - Mock 模式允许作为占位结果返回（`metadata.mock_placeholder=true`），仅用于本地流程调试。
- 当全部镜头都回退/失败时，项目状态进入 `task_status=failed`，不会按“成功出图”计费。
- 若部分镜头超时无返回，后端会为缺失镜头补写 `failed` 资产（`failure_reason=provider_missing_result`），前端不再无限等待整批完成。

## 进度
`GET /api/v1/projects/{id}/progress`

## 资产
`GET /api/v1/projects/{id}/assets`
`GET /api/v1/assets/{asset_id}`
`GET /api/v1/projects/{id}/download-images?scope=generated|approved|shared`（返回 zip 打包）
`GET /api/v1/showcase/assets?limit=`（公开样片墙，仅返回已分享素材）
`POST /api/v1/showcase/remix`（基于样片创建“拍同款”任务）

## 登录
`POST /api/v1/auth/login`
`POST /api/v1/auth/register`（本地认证可用）
`GET /api/v1/auth/me`
`POST /api/v1/auth/logout`

登录风控（v1）：
- 同账号 10 分钟内失败 5 次后锁定 15 分钟（`LOGIN_LOCKED`）。
- 同 IP 1 分钟内超过 20 次登录尝试触发限流（`LOGIN_RATE_LIMITED`）。

## 用户管理（管理员）
- `GET /api/v1/users`
- `POST /api/v1/users`
- `PATCH /api/v1/users/{username}`

关键字段：
- `UserRecord`: `username/email/display_name/workspace_id/role/account_status/is_active/points_balance`
- 角色：`admin | operator | member`
- 账号状态：`trial | active | suspended | frozen`

## 积分与充值
- `GET /api/v1/billing/me`
- `GET /api/v1/billing/ledger?limit=`
- `GET /api/v1/billing/recharges?limit=`
- `POST /api/v1/billing/recharge`（预留，默认关闭，返回 503）
- `POST /api/v1/billing/recharge/confirm`（预留，默认关闭，返回 503）
- `POST /api/v1/billing/adjust`（管理员）

v1 充值策略：
- 在线充值通道先预留，不对普通用户开放。
- 由管理员通过 `billing/adjust` 给注册账号加减积分。
- 后续接入支付网关后，再打开充值创建/确认通道。

计费规则（v1）：
- 图片生成：按“成功产物数”扣费（`1 point / asset`）
- 视频生成：按“成功候选数”扣费（`10 points / variant`）
- 首页样片分享：命中奖励规则后加分（`share_reward`）

## 质量与提示词评测（admin/operator）
- `GET /api/v1/quality/summary?days=&tool_type=`
- `GET /api/v1/prompts/metrics?days=&tool_type=`

用途：
- 追踪各工具质量通过率与高频问题。
- 对比 prompt 版本表现（项目数、产物数、通过率、平均分、最近使用时间）。

## 项目归属
- `ProjectRecord.owner_username` 为项目归属字段。
- 创建项目、批量创建、模特批量创建都会写入 `owner_username`。

## 权限规则（v1 RBAC）
- `admin`：全量可见 + 用户管理 + 财务操作（确认充值、手动调分）
- `operator`：全量可见 + 业务操作（项目/资产/生成/审核），无财务管理权限
- `member`：仅可见与操作自己创建的项目与资产

接口行为：
- 项目相关接口会校验 `project_id` 归属，不满足返回 `403`
- `GET /api/v1/projects`、`GET /api/v1/tools/{tool}/tasks`、`GET /api/v1/assets` 对 `member` 自动做归属过滤
