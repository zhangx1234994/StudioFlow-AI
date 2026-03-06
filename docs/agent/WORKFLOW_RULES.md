# AI摄影棚 工作流准则（测试 / 设计 / 前端 / 技能）

> 目标：统一研发与设计流程，避免重复问题；交付前确保质量可验证。

## 1. 设计准则
- 设计与交互规划必须先于开发落地。
- 所有 UI/UX 方案需使用 **UI/UX Pro Max 技能**进行产出与审视。
  - 技能路径：`/Users/zhangxin/.codex/skills/ui-ux-pro-max-skill/SKILL.md`
- 设计交付物必须包含：流程图、关键页面线框、状态与文案规范。
- 互联网产品改版必须先完成人群建模（至少10个 Persona：职业/年龄/兴趣/设备/场景/目标）。
- 评审输出必须采用多轮吐槽框架（R1观感 / R2动线 / R3文案 / R4商业风险 / R5情绪曲线 / R6付费信任）。
- 每个 Persona 必须至少提供 1 段故事化场景吐槽（时间点 + 任务 + 用户独白 + 受阻后果）。
- 改版范围必须由 `Persona × 页面优先级矩阵` 冻结，优先处理 P0，再处理 P1/P2。
- 故事化吐槽完成后必须输出“执行改造单”（页面/组件/DoD/指标），否则不进入开发排期。

## 2. 测试准则
- 交付前必须通过：
  - `python3 -m ruff check app tests`
  - `python3 -m pytest -q`
  - 本地 API smoke（创建→方案→生成→结果）
- 任何前端改动必须 `npm --prefix frontend run build` 后再验证。

## 3. 前端准则
- 工具场景必须独立：不得复用导致字段/文案混淆。
- 每个步骤仅允许一个主 CTA。
- 所有异步操作必须有状态反馈（submitting/running/success/failed）。
- 日志区默认折叠，避免占用核心操作区。

## 4. 技能使用准则
- UX/设计必须使用 **UI/UX Pro Max** 技能
- 走查/回归必须使用 **Playwright CLI** 技能
- Figma 相关必须使用 **figma** / **figma-implement-design** 技能
- 自动化 UI 测试必须使用 **playwright** 技能

## 5. 其他已安装技能（按需使用）
- figma
- figma-implement-design
- ui-ux-pro-max-skill
- playwright
- vercel-deploy（仅部署相关）

## 5. 文档准则
- 任何流程与交互变更必须更新规划文档。
- 文档索引更新后才允许进入开发阶段。
- Persona 文档与优先级矩阵是设计阶段强制产物，缺失则不得进入 UI 实现。
