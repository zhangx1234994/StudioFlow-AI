# AI摄影棚 文档索引

> 目的：建立“入口清晰、按职责分层、可追踪变更”的文档体系。
> 读者：产品 / 设计 / 前端 / 后端 / 运维 / 测试

---

## 0. 快速入口
- 新手必读：`/Volumes/MAC 1/shipin/README.md`
- UX 规范：`/Volumes/MAC 1/shipin/docs/ux-interaction-contract.md`
- 状态/进度标准：`/Volumes/MAC 1/shipin/docs/status-progress-standard.md`

## 1. 产品与流程
- 工具总览与流程差异：`/Volumes/MAC 1/shipin/docs/tools-overview.md`
- 进度与状态标准（全局唯一真源）：`/Volumes/MAC 1/shipin/docs/status-progress-standard.md`
- 规划 ToDo（先设计后开发）：`/Volumes/MAC 1/shipin/docs/MASTER_TODO.md`
- 规划目录（分主题）：`/Volumes/MAC 1/shipin/docs/plan/README.md`
- v1.2 需求总梳理（冻结版）：`/Volumes/MAC 1/shipin/docs/plan/16-v1.2-requirements-freeze.md`
- ISO 需求文档框架：`/Volumes/MAC 1/shipin/docs/plan/17-iso-srs-framework.md`
- ISO 详细需求规格（v1.2）：`/Volumes/MAC 1/shipin/docs/plan/18-iso-srs-v1.2-detailed.md`
- 逐条需求检查执行清单：`/Volumes/MAC 1/shipin/docs/plan/19-v1.2-requirements-itemized-review.md`
- FR 实现追踪矩阵：`/Volumes/MAC 1/shipin/docs/plan/20-v1.2-fr-implementation-traceability.md`
- 业务逻辑决策表：`/Volumes/MAC 1/shipin/docs/plan/21-v1.2-business-logic-decision-tables.md`
- 字段级规格与交互约束：`/Volumes/MAC 1/shipin/docs/plan/22-v1.2-field-level-spec.md`
- 验收用例目录（AT Catalog）：`/Volumes/MAC 1/shipin/docs/plan/23-v1.2-acceptance-test-catalog.md`

## 2. 架构与代码索引
- 系统架构与模块说明：`/Volumes/MAC 1/shipin/docs/architecture.md`
- API 约定与字段说明：`/Volumes/MAC 1/shipin/docs/api-contract.md`
- 用户/积分/充值接口说明：`/Volumes/MAC 1/shipin/docs/api-contract.md`（同页“用户管理”“积分与充值”章节）

## 3. 提示词与 VL 体系
- 提示词分层与 Guardrails：`/Volumes/MAC 1/shipin/docs/prompt-system.md`

## 4. 交互与视觉
- 交互约束与文案规范：`/Volumes/MAC 1/shipin/docs/ux-interaction-contract.md`
- 体验走查清单：`/Volumes/MAC 1/shipin/docs/ux/qa-checklist.md`
- 用户视角多轮吐槽（R1-R4）：`/Volumes/MAC 1/shipin/docs/ux/USER_PERSPECTIVE_ROAST_ROUNDS_2026-03-05.md`
- Persona × 页面优先级矩阵：`/Volumes/MAC 1/shipin/docs/ux/PERSONA_PAGE_PRIORITY_MATRIX_2026-03-05.md`
- 用户故事执行改造单（排期与验收）：`/Volumes/MAC 1/shipin/docs/ux/USER_STORY_EXECUTION_BACKLOG_2026-03-05.md`
- 模特工坊 10 角色用户视角复盘：`/Volumes/MAC 1/shipin/docs/ux/MODEL_RETOUCH_PERSONA_REVIEW_2026-03-06.md`
- 模特工坊 10 角色第二轮点评（异常提示与锚点命中）：`/Volumes/MAC 1/shipin/docs/ux/MODEL_RETOUCH_PERSONA_REVIEW_ROUND2_2026-03-06.md`
- P0 冲刺计划（任务拆分与发布）：`/Volumes/MAC 1/shipin/docs/ux/UX_P0_SPRINT_PLAN_2026-03-05.md`

## 4.1 Agent 内部准则
- Agent 工作准则：`/Volumes/MAC 1/shipin/docs/agent/AGENT_PLAYBOOK.md`
- 错误复盘日志：`/Volumes/MAC 1/shipin/docs/agent/RETRO_LOG.md`
- 决策记录：`/Volumes/MAC 1/shipin/docs/agent/DECISIONS.md`
- 交付检查清单：`/Volumes/MAC 1/shipin/docs/agent/CHECKLIST.md`
- 交付执行记录（最新）：`/Volumes/MAC 1/shipin/docs/agent/CHECKLIST_RUN_2026-03-05.md`
- 工作流准则（测试/设计/前端/技能）：`/Volumes/MAC 1/shipin/docs/agent/WORKFLOW_RULES.md`
- UX P0 执行检查单：`/Volumes/MAC 1/shipin/docs/agent/UX_P0_EXECUTION_CHECKLIST_2026-03-05.md`

## 5. 运维与部署
- 本地/服务器运行与排错：`/Volumes/MAC 1/shipin/docs/ops-runbook.md`
- 服务常驻脚本：`/Volumes/MAC 1/shipin/scripts/dev_service.sh`
- Linux systemd 服务模板：`/Volumes/MAC 1/shipin/deploy/systemd/studioflow-ai.service`

---

## 6. 代码结构速查
- 后端入口：`/Volumes/MAC 1/shipin/app/main.py`
- 业务编排：`/Volumes/MAC 1/shipin/app/services/`
- 数据模型：`/Volumes/MAC 1/shipin/app/schemas.py`
- 状态存储：`/Volumes/MAC 1/shipin/app/store.py`
- 前端入口：`/Volumes/MAC 1/shipin/frontend/app/page.jsx`

---

## 7. 维护规范
- 任何新功能必须新增/更新相应文档：
  - API：`api-contract.md`
  - 交互：`ux-interaction-contract.md`
  - 工具流程：`tools-overview.md`
- 文档变更需在 PR 描述中注明。
