# 电商AI工具箱：状态与进度标准（v1 冻结）

## 1. 目标
- 统一四个工具的流程定义、状态语义、进度计算与失败重试策略。
- 保证任务中心与工作台对同一项目展示一致的进度值与引导文案。

## 2. 需求建模模板（每工具必填）
- 用户与场景：目标用户、输入素材、输出结果、计费点、SLA。
- 阶段定义：谁触发、依赖输入、完成判定、失败判定、可重试边界。
- 质量要求：自动质检阈值、人工审核标准、合规要求。

## 3. 能力域抽象
- 素材能力：上传/引用/版本/标签（uploaded/generated）。
- 规划能力：VL 输出严格 schema 的结构化方案。
- 编译能力：图像/视频提示词编译与 guardrail 过滤。
- 生成能力：并发、轮询、超时、失败原因、重试。
- 质检能力：自动评分 + 人工审核闭环。
- 追踪能力：状态机、进度、日志、错误码。

## 4. 两层状态机
### 项目生命周期（ProjectStatus）
- draft / scripted / rendering / completed / failed

### 阶段运行态（TaskRunStatus）
- queued / running / reviewing / succeeded / failed / done

### 统一判定
- 开始：创建项目成功即开始。
- 进行中：存在未完成阶段，且阶段运行态为 queued/running/reviewing。
- 已完成：图像/视频均需“目标产物齐全 + 人工审核通过”。
- 失败：当前阶段失败即停，必须通过 retry 接口恢复。

## 5. 进度标准（阶段加权）
### 图像类（产品图精修、模特精修）
- AI方案 20% + 提示词编译 10% + 图像生成 50% + 人工审核 20%
- 生成进度 = generated_assets / target_assets
- 审核进度 = reviewed_assets / target_assets

### 视频类（产品介绍多脚本、15秒快产）
- 主脚本 15% + AI方案 15% + 提示词编译 10% + 分镜确认 20% + 视频生成 30% + 审核 10%
- 分镜进度 = approved_shots / total_shots
- 视频进度 = completed_variants / total_variants

### 计算约束
- 百分比仅由 Progress steps 推导，不允许页面自行计算。
- 空分母按 1 兜底，最终 clamp 到 [0, 100]。

## 6. 失败与重试
- 失败即停：阶段失败后不继续自动推进。
- 可重试：`POST /api/v1/projects/{id}/retry` 从失败阶段恢复并重跑。
- 错误可观测：每个步骤返回 error_code / 错误文案 / 最近日志线索。
