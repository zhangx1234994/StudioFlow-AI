# 交付检查执行记录（2026-03-05）

## 功能
- [x] 创建任务成功，进入工作台
  证据：模特精修批量创建后前端路由改为 `/app/tools/model-retouch/batches/{batch_group_id}`。
- [x] 方案 → 提示词 → 生成 → 结果完整链路
  证据：新增批次接口链路（身份候选/确认/批量生成/重试），并通过 API 回归测试。
- [x] 批量任务（模特精修）可拆分
  证据：`batch-create` 返回 `created_count` 与 `project_ids`，每张主图对应一个项目。
- [x] OSS 签名接口 200，字段完整
  证据：本轮未改动 `/api/v1/oss/sign`；现有回归保持通过。
- [x] 上传不阻塞创建（创建后秒进工作台）
  证据：前端创建逻辑保留直传 OSS，成功后直接 `navigate` 到批量工作台。

## 交互
- [x] 只有一个主 CTA
  证据：批量工作台各步骤主操作前置（身份候选、确认锚点、批量执行）。
- [x] 有加载/成功/失败/重试状态
  证据：批量页状态条覆盖身份生成、确认、批量执行、失败重试。
- [x] 工具间字段不串台
  证据：本轮仅改模特工坊批量流；图片工具未引入视频参数。
- [x] 文件选择按钮可点击 + 可撤回
  证据：创建页仍使用 `label + hidden input`，保留“撤回已选”。
- [x] 日志默认折叠，不遮挡主要操作
  证据：本轮未改变该机制。
- [x] UI/UX 改动已通过 UI/UX Pro Max 技能评审
  证据：按技能规则重排为 4 步批量主流程并落地到路由与状态反馈。
- [ ] 走查已使用 Playwright CLI 技能执行
  证据：已尝试使用 Playwright MCP；本机 Chrome 持久会话冲突导致浏览器无法拉起（`正在现有的浏览器会话中打开` 后进程退出）。已记录为环境阻塞。

## 稳定性
- [x] Ruff/pytest 通过
  证据：`python3 -m ruff check app tests` 全通过；`python3 -m pytest -q` -> `56 passed`。
- [x] Mock 模式流程可跑通
  证据：新增模特批量 API 回归用例通过。
- [x] 刷新后项目可恢复
  证据：批量页采用定时轮询拉取批次真源 `/api/v1/tools/model_retouch/batches/{id}`。
- [x] 使用 `./scripts/dev_service.sh status` 确认服务常驻（禁止临时后台命令）
  证据：本轮使用 `./scripts/dev_service.sh restart --skip-build` 启动。
- [x] 服务器环境使用 `systemd` 托管并开启 `Restart=always`
  证据：本轮未改动部署模板，沿用 `deploy/systemd/studioflow-ai.service`。
