# AI摄影棚 Agent 准则（强制执行）

> 目标：不重复犯错、交付可验证、流程可追踪。任何改动必须遵守本文件。

## 1. 文档体系（必须同步）
- 文档索引：`/Volumes/MAC 1/shipin/docs/INDEX.md`
- 任何接口/交互/流程变更必须同步更新对应文档。
- 每次交付后追加复盘：`/Volumes/MAC 1/shipin/docs/agent/RETRO_LOG.md`

## 2. 核心交付原则
- **先设计后实现**：交互/流程变更先写清楚再动代码。
- **不重复犯错**：错误必须记录、归因、并写入防护措施。
- **用户不做首轮排错**：本地能复现的问题必须先修复再交付。
- **单步主 CTA**：每个步骤只有一个主按钮，其余进“高级/更多”。
- **状态可见**：所有异步必须有 `submitting → running → success/failed`。
- **前端改动必构建**：任何前端修改需先 `npm --prefix frontend run build` 再重启服务。
- **交付前自启服务**：每次交付前主动重启前后端并自测关键路径，不要求用户先重启。
- **走查用 Playwright CLI**：交互/流程走查必须使用 Playwright CLI Skill 执行并记录。
- **设计用 UI/UX Pro Max**：所有设计与交互方案必须使用 UI/UX Pro Max Skill 产出与评审。

## 3. 工具与场景边界（强约束）
- 图片类工具不出现视频字段（如时长、帧数）。
- 视频类工具不出现图片批量/角度字段。
- 多角度工具仅展示机位控制与生成，不展示脚本/分镜字段。

## 4. OSS 直传规范
- 创建任务前**前端直传 OSS**，后端只接 URL。
- 创建后 **必须秒进工作台**（上传不阻塞创建）。
- `/api/v1/oss/sign` 返回字段必须完整（含 `updated_at`）。

## 5. 架构与代码索引
- 后端入口：`/Volumes/MAC 1/shipin/app/main.py`
- 服务编排：`/Volumes/MAC 1/shipin/app/services/`
- 数据模型：`/Volumes/MAC 1/shipin/app/schemas.py`
- 状态存储：`/Volumes/MAC 1/shipin/app/store.py`
- 前端入口：`/Volumes/MAC 1/shipin/frontend/app/page.jsx`

## 6. 运行与测试（必须通过）
- 启动：`python3 -m uvicorn app.main:app --host 0.0.0.0 --port 5005`
- Lint：`python3 -m ruff check app tests`
- Test：`python3 -m pytest -q`
- Smoke：创建→方案→生成→结果完整链路
 - 五工具全量自查后再交付用户测试（商品棚拍/模特精修/多角度/15秒/讲解视频）

## 7. UX 验收（必须通过）
- 任意页面 1 次点击可回 `/app/tools`
- 无遮罩阻塞主操作
- 上传按钮可点击且可撤回
- 日志默认折叠，不遮挡主操作区
- **批量创建自动跳转**：创建成功后必须自动进入第一个任务工作台；若不可跳转需提供清晰入口按钮。

## 8. 复盘与改进（强制）
- 每次 bug：写入 `RETRO_LOG.md`
- 每次改动：更新 `AGENT_PLAYBOOK.md` 中防护措施
- 交付前执行 `/docs/agent/CHECKLIST.md`

## 9. 用户建模与评审方法（强制）
- 互联网产品 UI 改版前必须完成 Persona 建模（至少 10 类用户：职业/年龄/兴趣/设备/场景/目标）。
- 设计评审必须使用多轮吐槽法：R1观感、R2动线、R3文案、R4商业风险、R5情绪曲线、R6付费信任。
- 每轮改版必须产出 Persona × 页面优先级矩阵（P0/P1/P2），并冻结当轮改造范围。
- 吐槽输出必须包含“用户故事化片段”（人物、时间、任务目标、阻塞点、情绪变化），禁止只写抽象结论。
- 用户故事文档完成后，必须同步产出“执行改造单”（页面/组件/验收标准/指标），禁止停留在情绪反馈层。
- 缺少 Persona 文档与优先级矩阵，禁止进入 UI 开发阶段。
