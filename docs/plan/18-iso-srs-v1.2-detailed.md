# AI摄影棚 v1.2 详细需求规格说明（ISO 风格 SRS）

> 参考：ISO/IEC/IEEE 29148:2018
> 文档状态：Baseline
> 版本：v1.2.0
> 日期：2026-03-05

---

## 0. 文档控制

| 字段 | 内容 |
|---|---|
| 文档编号 | SRS-AIPS-v1.2 |
| 作者 | 产品/研发联合 |
| 评审 | 前端、后端、测试、设计 |
| 批准 | 项目负责人 |
| 适用版本 | Web v1.2 |

### 变更记录
| 版本 | 日期 | 变更 |
|---|---|---|
| 1.0 | 2026-03-05 | 首版详细冻结 |

---

## 1. 引言

### 1.1 目的
本说明用于统一开发、测试、验收对需求的理解，减少口头解释造成的偏差。

### 1.2 产品范围
- 覆盖 5 个工坊：商品棚拍、模特精修、多角度、讲解视频、15 秒短片。
- 覆盖账号、权限、积分、样片墙、资产中台。

### 1.3 不在范围
- 真实支付接入
- 小程序正式版
- 企业审批流

---

## 2. 干系人与业务目标

## 2.1 角色
1. 电商运营（高频建任务）
2. 内容创作者（关注画面质量）
3. 交付经理（关注批量状态）
4. 管理员（账号/积分/权限）

## 2.2 业务目标
- BO-01：缩短从创建到可交付素材的时间。
- BO-02：降低任务“无反馈等待”的不确定性。
- BO-03：让优质内容可复用，形成样片运营闭环。

## 2.3 KPI
- KPI-01：创建后进入工作台 p95 <= 2s
- KPI-02：批量任务“无终态”数量 = 0
- KPI-03：关键流程走查通过率 = 100%

---

## 3. 系统上下文与边界

## 3.1 系统内职责
- 前端：交互、状态可视化、OSS 直传。
- 后端：流程编排、状态机、权限、计费、重试。

## 3.2 外部依赖
- OSS：媒体持久化
- 模型服务：方案、提示词、图/视频生成

## 3.3 约束
- 创建动作不允许被上传阻塞。
- 批量执行必须可中途观测与恢复。

---

## 4. 业务场景（BS）

## BS-001 新建并快速交付（商品工坊）
- 角色：运营
- 前置：已登录
- 触发：上传素材并创建任务
- 成功流：创建 -> 方案 -> 试拍 -> 选片分享 -> 下载
- 异常流：方案超时 -> 显示失败 -> 重试
- 成功标准：可导出入选结果

## BS-002 组图替换模特并批量精修（模特工坊）
- 角色：运营/交付经理
- 前置：上传 N 张主图
- 触发：进入 batch 工作台
- 成功流：素材确认 -> 身份确认 -> 批量执行 -> 审核导出
- 异常流：单任务无结果 -> 单任务重试
- 成功标准：N 张任务全部进入终态

## BS-003 单图机位控制输出（多角度）
- 角色：创作者
- 成功流：上传 -> 机位调整 -> 生成当前角度 -> 审核
- 异常流：生成失败 -> 重试当前角度

## BS-004 先脚本后视频（讲解视频）
- 角色：内容创作者
- 成功流：脚本确认 -> 分镜确认 -> 视频生成
- 约束：未确认脚本不得生成视频

## BS-005 15 秒短片快产（短片工坊）
- 角色：运营
- 成功流：需求 -> 方案 -> 一键生成候选 -> 审核

---

## 5. 功能需求（FR）

## 5.1 认证与会话
| ID | Requirement (shall) | Priority | 验收 |
|---|---|---|---|
| FR-AUTH-001 | 系统 shall 支持账号密码登录 | Must | 登录成功返回 authenticated=true |
| FR-AUTH-002 | 系统 shall 支持 7 天会话保持 | Must | 刷新页面不丢登录态 |
| FR-AUTH-003 | 系统 shall 对登录失败返回可区分错误 | Must | 凭证错/网络错/服务错可见 |
| FR-AUTH-004 | 系统 shall 在会话失效时跳转登录且提示原因 | Must | 无白屏 |

## 5.2 任务与流程编排
| ID | Requirement (shall) | Priority | 验收 |
|---|---|---|---|
| FR-TASK-001 | 创建接口 shall 在上传完成后立即返回项目并跳转工作台 | Must | 2 秒内进入工作台 |
| FR-TASK-002 | 每步 shall 只有 1 个主 CTA | Must | 页面检查通过 |
| FR-TASK-003 | 异步操作 shall 显示提交中/执行中/成功/失败 | Must | 状态词统一 |
| FR-TASK-004 | 每条任务 shall 展示风险标签和下一步提示 | Must | 任务列表可见 |
| FR-TASK-005 | 批量任务 shall 支持“重试失败项”和“单任务重试” | Must | 按钮可用 |

## 5.3 商品棚拍工坊
| ID | Requirement (shall) | Priority | 验收 |
|---|---|---|---|
| FR-PI-001 | 创建页 shall 提供产出预期卡 | Must | 首屏可见 |
| FR-PI-002 | 方案生成 shall 支持高镜头数补齐 | Must | 镜头数不缺失 |
| FR-PI-003 | 结果页 shall 以批量动作为主 | Must | 一键入选/分享/下载可见 |
| FR-PI-004 | 单张微调 shall 为次级入口 | Should | 默认不抢主路径 |

## 5.4 模特精修工坊
| ID | Requirement (shall) | Priority | 验收 |
|---|---|---|---|
| FR-MR-001 | 上传 N 张主图 shall 展示 N 张素材 | Must | 不重复不丢失 |
| FR-MR-002 | 身份确认 shall 提供三模式（使用上传/精修上传/生成新模特） | Must | 三模式可触发 |
| FR-MR-003 | 未确认锚点 shall 禁止进入批量精修 | Must | 主按钮禁用且有原因 |
| FR-MR-004 | 批量执行页 shall 显示自动刷新状态和手动刷新 | Must | 5 秒自动回填可见 |
| FR-MR-005 | `reviewing` 状态 shall 计入完成，不计入排队 | Must | 统计口径正确 |
| FR-MR-006 | “执行中”列 shall 仅包含真实 running/queued 项 | Must | 无假执行中 |
| FR-MR-007 | 原图比例模式 shall 不传分辨率 | Must | 请求参数检查通过 |

## 5.5 多角度展品工坊
| ID | Requirement (shall) | Priority | 验收 |
|---|---|---|---|
| FR-MA-001 | 工坊 shall 只展示机位控制相关参数 | Must | 无脚本/视频字段 |
| FR-MA-002 | 单次生成 shall 输出当前机位单张图 | Must | 结果数量正确 |

## 5.6 讲解视频工坊
| ID | Requirement (shall) | Priority | 验收 |
|---|---|---|---|
| FR-IV-001 | Step2 shall 前置脚本预览与镜头摘要 | Must | 进入即见脚本 |
| FR-IV-002 | 未确认脚本 shall 禁止生成视频 | Must | 门禁生效 |

## 5.7 15 秒短片工坊
| ID | Requirement (shall) | Priority | 验收 |
|---|---|---|---|
| FR-QV-001 | 工坊 shall 默认 15 秒节奏模板 | Must | 创建默认值正确 |
| FR-QV-002 | 页面 shall 仅保留必要视频参数 | Should | 无图片参数混入 |

## 5.8 资产中台与样片墙
| ID | Requirement (shall) | Priority | 验收 |
|---|---|---|---|
| FR-ASSET-001 | 资产中台 shall 提供任务/素材/样片三视图 | Must | 三 tab 可切换 |
| FR-ASSET-002 | 用户可见文案 shall 去开发语义 | Must | 不出现 uploaded/generated/kind |
| FR-ASSET-003 | 样片墙 shall 仅展示主动分享内容 | Must | 无自动灌入 |
| FR-ASSET-004 | 样片 shall 支持一键拍同款创建任务 | Should | remix 可用 |

## 5.9 用户与积分
| ID | Requirement (shall) | Priority | 验收 |
|---|---|---|---|
| FR-USER-001 | 系统 shall 支持 admin/operator/member 角色 | Must | 权限差异生效 |
| FR-USER-002 | member shall 仅可访问本人项目 | Must | 越权返回 403 |
| FR-BILL-001 | 积分页 shall 展示概览 + 经营结论 + 明细折叠 | Must | 结构存在 |
| FR-BILL-002 | 生成扣分 shall 按成功产物数结算 | Must | 无预扣 |
| FR-BILL-003 | 充值 shall 处于预留状态并受开关控制 | Must | 前台不开放实充 |

---

## 6. 业务规则（BR）

| ID | 规则 |
|---|---|
| BR-001 | 每步仅一个主 CTA，其他动作降级 |
| BR-002 | 批量任务每个预期项必须进入终态 |
| BR-003 | 创建前前端直传 OSS，后端仅接 URL |
| BR-004 | 批量上传 object key 必须唯一 |
| BR-005 | 模特工坊身份确认先于批量执行 |
| BR-006 | 原图比例模式不传分辨率参数 |
| BR-007 | 任务列表必须显示风险 + 下一步 |
| BR-008 | 日志默认折叠，不得压主操作区 |

---

## 7. 数据与状态模型要求

## 7.1 关键实体
- Project：项目主状态
- Asset：素材与结果
- Batch：模特批量聚合视图
- User：账号信息
- Ledger：积分流水

## 7.2 状态定义
- 项目：draft/scripted/running/reviewing/completed/failed
- 资产：pending/ready/reviewed/rejected/failed
- 批次统计：total/done/failed/running/queued

## 7.3 一致性规则
1. `done + failed + running + queued = total`
2. `reviewing` 视为 done 侧，不可计入 queued
3. 批量列分配与统计口径必须一致

---

## 8. 接口需求（关键清单）

## 8.1 认证
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me`
- `POST /api/v1/auth/register`

## 8.2 任务
- `POST /api/v1/projects`
- `GET /api/v1/projects/{id}`
- `GET /api/v1/projects/{id}/progress`
- `GET /api/v1/projects/{id}/assets`
- `POST /api/v1/projects/{id}/retry`

## 8.3 模特批量
- `GET /api/v1/tools/model_retouch/batches/{batchId}`
- `POST /api/v1/tools/model_retouch/batches/{batchId}/identity/generate-candidate`
- `POST /api/v1/tools/model_retouch/batches/{batchId}/identity/confirm`
- `POST /api/v1/tools/model_retouch/batches/{batchId}/identity/upload`
- `POST /api/v1/tools/model_retouch/batches/{batchId}/identity/clear-uploaded`
- `POST /api/v1/tools/model_retouch/batches/{batchId}/generate`
- `POST /api/v1/tools/model_retouch/batches/{batchId}/retry`

## 8.4 运营与积分
- `GET /api/v1/showcase/assets`
- `POST /api/v1/showcase/remix`
- `POST /api/v1/projects/{id}/share`
- `GET /api/v1/billing/me`
- `GET /api/v1/billing/ledger`
- `POST /api/v1/billing/adjust`

---

## 9. 非功能需求（NFR）

| ID | 需求 | 指标 |
|---|---|---|
| NFR-PERF-001 | 创建后跳转时延 | p95 <= 2s |
| NFR-PERF-002 | 批量页刷新节奏 | 5s 自动轮询 |
| NFR-REL-001 | 关键链路可恢复 | 每个失败有重试入口 |
| NFR-OBS-001 | 可观测性 | request_id + stage + result + error_code |
| NFR-SEC-001 | 会话安全 | HttpOnly/SameSite/Secure（按环境） |
| NFR-MTN-001 | 变更可维护 | 文档与代码同步更新 |

---

## 10. 验证与验收

## 10.1 自动化验收
- `npm --prefix frontend run build`
- `python3 -m ruff check app tests`
- `python3 -m pytest -q`

## 10.2 关键人工走查（Playwright）
1. 登录 -> 工具总览
2. 商品工坊创建到选片分享
3. 模特工坊 9 图上传 -> 身份确认 -> 批量执行 -> 单任务重试
4. 多角度机位控制与单张输出
5. 资产中台三视图与样片拍同款

## 10.3 放行条件
- 所有 Must 级 FR 通过
- 所有 P0 场景通过
- 无 P0/P1 阻断缺陷

---

## 11. 追踪矩阵（摘要）

| 业务目标 | 场景 | FR | 接口 | 验收 |
|---|---|---|---|---|
| BO-01 快速交付 | BS-001/BS-002 | FR-TASK-001 FR-MR-004 | projects/create, batch/generate | 创建时延+执行回填 |
| BO-02 状态可见 | BS-002 | FR-TASK-003 FR-MR-006 | batch/summary | 无假执行中 |
| BO-03 复用沉淀 | BS-001/BS-003 | FR-ASSET-003 FR-ASSET-004 | showcase/assets, remix | 样片闭环可用 |

---

## 12. 变更控制

1. 新需求必须先进入本 SRS（新增 ID）再排期。
2. 变更必须说明影响：接口、前端流程、测试用例。
3. 未更新 SRS 的需求默认不允许开发与上线。

