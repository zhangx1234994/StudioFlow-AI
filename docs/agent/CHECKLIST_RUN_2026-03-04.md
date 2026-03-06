# 交付检查执行记录（2026-03-04）

## 功能
- [x] 创建任务成功，进入工作台  
  证据：Playwright 五工具创建均自动进入 `/projects/{id}`（product/model/multi-angle/intro/quick）。
- [x] 方案 → 提示词 → 生成 → 结果完整链路  
  证据：商品棚拍、模特精修、多角度三条链路触发 `plan.start -> plan.completed -> prompts.derived -> images.start`。
- [x] 批量任务（模特精修）可拆分  
  证据：2 张主图创建后 `batch_stats.total_images=2`。
- [x] OSS 签名接口 200，字段完整  
  证据：`/api/v1/oss/sign` 返回 `upload_url/access_id/policy/signature/key/public_url/expire_at/updated_at`。
- [x] 上传不阻塞创建（创建后秒进工作台）  
  证据：Playwright 创建耗时 1.7s~4.8s，并立即跳工作台。

## 交互
- [x] 只有一个主 CTA  
  证据：Step1 统一收敛为单主动作，非主动作下沉为次按钮。
- [x] 有加载/成功/失败/重试状态  
  证据：工作台状态统一为“提交中/执行中/成功/失败”，失败入口保留重试按钮。
- [x] 工具间字段不串台  
  证据：图片工具无时长；多角度无脚本/分镜输入；视频工具保留时长相关。
- [x] 文件选择按钮可点击 + 可撤回  
  证据：任务页输入组件提供“选择文件/选择多张 + 撤回已选”。
- [x] 日志默认折叠，不遮挡主要操作  
  证据：工作台日志区使用 `details` 折叠容器。
- [x] UI/UX 改动已按规范执行并记录  
  证据：文案与主 CTA 收敛写入 `RETRO_LOG` 与 `AGENT_PLAYBOOK`。
- [x] 走查已使用 Playwright 执行  
  证据：本次全量创建与关键链路由 Playwright 完成。

## 稳定性
- [x] Ruff/pytest 通过  
  证据：`ruff check app tests` 通过；`pytest -q` 47 passed。
- [x] Mock 模式流程可跑通  
  证据：回归测试集通过（含 mock 覆盖的 API/流程用例）。
- [x] 刷新后项目可恢复  
  证据：方案异步运行态下刷新可保持 `plan running` 并自动轮询恢复。

## 增量走查（同日二次）
- [x] 工作台流程区改为顶部横向步骤条  
  证据：`/app/tools/product-image/projects/{id}` 显示 `流程进度` 顶部 tablist，左侧本地步骤栏已移除，主内容区宽度释放。
- [x] 步骤切换仍可点击  
  证据：Playwright 点击 Step2 后 `当前步骤 2 / 4` 与 active 态同步更新。

## 增量走查（同日三次）
- [x] 首屏核心区图文并茂（矢量图标+文案精简）
  证据：首页导航、工具卡、KPI、样片区与工作台关键信息卡已接入统一 SVG 图标；工具描述卡限制为两行，避免文字堆叠。

## 增量走查（同日四次）
- [x] 全局视觉系统升级到“可商用”质感
  证据：`globals.css` 完成字体、背景氛围层、卡片材质、按钮动效、表格层级统一；Playwright 可见首页与工作台均已生效。

## 增量走查（同日五次）
- [x] 首页样片区升级为运营型结构
  证据：`ToolsHome` 已改为“主打案例 + 次级网格 + CTA”布局；空态改为可行动引导块而非纯文案。

## 增量走查（同日六次）
- [x] 工作台升级为步骤工作面板结构
  证据：`ProjectWorkspace` 已接入 Step 抬头体系与摘要信息条；步骤 chip 增加流程图标，方向提示更清晰。

## 增量走查（同日七次）
- [x] 生成与审核区升级为控制台 + 摘要看板结构
  证据：生成步骤新增 `generate-control-deck` 与 `generate-metrics`；审核步骤新增 `review-summary-grid`，关键信息前置。

## 增量走查（同日八次）
- [x] 结果墙升级为可筛选轨道结构（全部/已通过/待筛选/异常）
  证据：商品棚拍 Step3/Step4 新增筛选器并实时切换结果集；Playwright 点击“已通过”后显示空筛选态提示。
- [x] 日志降权为抽屉式交互，不再占主操作区
  证据：工作台底部仅保留“查看日志”入口按钮，点击后右侧抽屉展示最近 30 条日志。
- [x] 首页运营区补齐“套图包 + 近期热销”双模块
  证据：首页“套图商品包（可运营）”区域新增 `hot-sales-panel`，支持一键跳转对应工坊。
- [x] 本轮质量回归通过
  证据：`npm --prefix frontend run build`、`ruff check app tests`、`pytest -q`（47 passed）；Playwright 控制台错误 0。

## 增量走查（同日九次）
- [x] 修复 `queued` 误判“方案生成中”导致主按钮锁死
  证据：Playwright 打开 `af88027a-046c-40ff-907c-098ff41fbc82` 时显示“生成拍摄方案”可点击，不再默认“方案生成中”。
- [x] 方案生成新增2分钟超时兜底
  证据：前端新增 `PLAN_TIMEOUT_MS=120000` 与超时解锁提示逻辑，避免长时间假等待。
- [x] 轮询策略降噪
  证据：仅在 `running` 或明确 pending 场景持续轮询；`queued` 空闲态不再无意义高频轮询。

## 增量走查（同日十次）
- [x] 方案分镜 `delivery_purpose` 空值补齐（解析层 + 保存层 + 读取层）
  证据：`VolcScriptService` 新增空白/null 占位归一化；`PipelineService` 在生成/更新/读取方案时统一补齐用途。
- [x] VL 规划提示词结构补强
  证据：`_project_plan_schema_example` 与 `hard_rules` 增加 `delivery_purpose` 必填约束，商品棚拍限定枚举用途。
- [x] 前端显示兜底
  证据：工作台 Step2 与结果区在缺省值下自动显示用途（主图/场景图/细节图/对比图），避免空白字段。
- [x] 回归验证通过
  证据：`npm --prefix frontend run build`、`python3 -m ruff check app tests`、`python3 -m pytest -q`（49 passed）。

## 增量走查（同日十一次）
- [x] 商品棚拍并发提速
  证据：图片生成默认并发从 2 调整到 4，执行并发上限放宽到 8（按任务量自动收敛）。
- [x] 结果卡片补齐电商运营文案
  证据：后端生成资产 metadata 新增 `marketing_copy`，前端优先展示该文案，避免仅显示“用途+卖点字段拼接”。
- [x] 回归验证通过
  证据：`npm --prefix frontend run build`、`python3 -m ruff check app tests`、`python3 -m pytest -q`（49 passed）。

## 增量走查（同日十二次）
- [x] 商品棚拍 Step4 改为“选片分享”
  证据：工具步骤文案与阶段标签统一替换为“选片分享”，不再出现“选片定稿”。
- [x] 分享动作打通首页样片墙
  证据：新增分享接口后，首页样片墙仅拉取 `tag=showcase_shared` 的资产，未分享素材不再自动公开。
- [x] 分享积分激励上线
  证据：KPI 新增“样片墙已分享/分享积分”；分享成功提示奖励积分（+2）并写入资产 metadata。

## 增量走查（同日十三次）
- [x] 用户管理与积分中心页面上线（含导航）
  证据：Playwright 走查 `/app/billing` 与 `/app/users`，页面可正常渲染与操作，无白屏。
- [x] 本地登录改为用户仓库鉴权
  证据：新增 `tests/test_user_billing_api.py`，`test_local_login_uses_user_store_credentials` 通过。
- [x] 充值、确认到账、积分调整接口跑通
  证据：新增 `tests/test_user_billing_api.py`，`test_user_management_and_billing_endpoints` 通过。
- [x] 生成扣费与分享奖励流水可见
  证据：Playwright 在积分流水表可见 `consume_generation/share_reward/recharge` 三类记录。
- [x] 本轮质量回归通过
  证据：`python3 -m ruff check app tests`、`python3 -m pytest -q`（51 passed）、`npm --prefix frontend run build` 全通过。

## 增量走查（同日十四次）
- [x] RBAC 权限隔离上线（admin/operator/member）
  证据：项目读写接口与列表接口已按 `owner_username` 进行权限控制；member 仅可见自己的项目与资产。
- [x] 权限回归用例通过
  证据：新增 `test_member_project_permission_isolation`，`pytest -q` 结果 52 passed。

## 增量走查（同日十五次）
- [x] 充值通道按策略预留（默认关闭）
  证据：`/api/v1/billing/recharge` 与 `/api/v1/billing/recharge/confirm` 增加开关拦截，关闭时返回 503。
- [x] 积分中心交互改为“管理员手动调分优先”
  证据：前端移除“创建充值申请”主流程，新增“充值通道预留”说明，保留管理员积分调整入口。
- [x] 本轮质量回归通过
  证据：`python3 -m ruff check app tests`、`python3 -m pytest -q`（52 passed）、`npm --prefix frontend run build` 全通过。

## 增量走查（同日十六次）
- [x] P0 规划文档冻结完成（定价/认证）
  证据：`docs/plan/01-pricing.md` 与 `docs/plan/02-auth.md` 已补齐失败扣费、价格梯度、SLA、试用、结算、注册、风控、Workspace、账号状态等决策。
- [x] MASTER_TODO 进度与剩余项重新校正
  证据：按复选框统计更新为 `84/91`，剩余项收敛为 7 项（P1+P2）。

## 增量走查（同日十七次）
- [x] P1/P2 规划文档冻结完成（运营、提示词、多端、线框）
  证据：`docs/plan/04-ops-content.md`、`docs/plan/11-prompt-system.md`、`docs/plan/14-multiplatform.md`、`docs/plan/15-deliverables.md` 已补齐剩余决策项。
- [x] MASTER_TODO 全量完成
  证据：复选框统计 `91/91`，未完成项 `0`，并在顶部标注进入实现阶段。

## 增量走查（同日十八次）
- [x] 账号体系实现推进：本地注册 + 登录风控 + 账号状态字段
  证据：后端新增 `/api/v1/auth/register`；登录增加账号锁定/IP限流；`/api/v1/auth/me` 返回 `account_status/workspace_id`。
- [x] 前端认证页补齐注册入口与错误提示
  证据：登录页新增“注册新账号”；新增注册页；登录错误新增“频率限制/账号受限”提示。
- [x] 质量回归通过
  证据：`python3 -m ruff check app tests`、`python3 -m pytest -q`（54 passed）、`npm --prefix frontend run build` 全通过。

## 增量走查（同日十九次）
- [x] 样片墙“拍同款”链路打通
  证据：新增 `/api/v1/showcase/assets` 与 `/api/v1/showcase/remix`；首页样片“拍同款”点击后直接创建并跳转工作台，记录来源样片ID。
- [x] 质量与提示词评测接口上线
  证据：新增 `/api/v1/quality/summary` 与 `/api/v1/prompts/metrics`，支持按天数/工具统计通过率、分数与版本表现。
- [x] 回归覆盖新增能力
  证据：新增 `tests/test_showcase_metrics_api.py`，验证样片分享、拍同款、质量汇总、提示词指标接口链路。

## 增量走查（同日二十次，Playwright CLI）
- [x] 登录与注册链路走查通过
  证据：使用 Playwright CLI 执行 `/app/login -> /app/register -> /app/login -> /app/tools` 全链路，状态与跳转正常。
- [x] 样片墙“拍同款”按钮可用性修复
  证据：修复 `assetId` 为空时按钮被误判“创建中”问题；修复样片过滤条件（`kind=generated_image`），按钮恢复可点击。
- [x] 样片同款创建实测通过
  证据：Playwright 点击首页“立即拍同款”后成功跳转到新项目工作台 `/app/tools/product-image/projects/{id}`。

## 增量走查（同日二十一次）
- [x] 服务常驻启动链路标准化
  证据：新增 `scripts/dev_service.sh`，支持 `up/down/restart/status/logs`，并在启动时执行健康检查。
- [x] Linux 服务器进程托管模板补齐
  证据：新增 `deploy/systemd/studioflow-ai.service` 与 `deploy/systemd/install.sh`，默认 `Restart=always`。
- [x] 模特批量创建链路复测通过（Playwright CLI）
  证据：通过 Playwright 设置两张主图后点击“批量创建单图精修任务”，成功跳转 `/app/tools/model-retouch/projects/{id}`，后端返回 200。

## 增量走查（同日二十二次）
- [x] 模特精修 Step2 主 CTA 上移到顶部
  证据：`frontend/app/page.jsx` Step2 先展示“生成精修方案/确认方案并进入身份确认或精修”主操作，再展示批次卡和方案内容。
- [x] 批次卡查看行为去歧义
  证据：当前任务按钮显示“当前查看”并禁用，其他任务显示“查看该图”并可跳转，避免点击无反馈。
- [x] 模特精修改为单任务单图产出
  证据：`PipelineService.generate_images_for_project` 对 `model_retouch` 仅执行首个 image prompt；`ProjectProgress` 该工具目标资产按 1 计算。

## 增量走查（同日二十三次）
- [x] 模特精修创建后默认进入“身份确认”主流程
  证据：工作台初始步骤映射中，`model-retouch` 的 `plan/prompt/scripted` 阶段统一跳转到身份确认步骤。
- [x] 模特精修流程隐藏“批次精修要求”中间页
  证据：Step2 页面对 `model-retouch` 不再渲染，顶部步骤条同步改为 4 步可见（上传套图/身份确认/单张精修执行/批次交付）。
- [x] 首页主操作改为“进入模特确认”
  证据：Step1 主按钮文案与行为更新：先进入身份确认；若未生成约束则后台先生成后继续。

## 增量走查（同日二十四次）
- [x] 提示词编译结构化升级（image/video）
  证据：`VolcScriptService.compile_prompt_pack` 改为模板化字段输出，image/video 均带固定结构段落，且保留硬约束。
- [x] 提示词质量评分回写 guardrail_report
  证据：新增 `image_prompt_quality_avg` 与 `video_prompt_quality_avg`，用于量化提示词可执行结构完整度。
- [x] 提示词结构回归用例补齐
  证据：`tests/test_volc_service.py` 新增结构化输出断言与质量评分断言。
