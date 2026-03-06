# AI摄影棚 ISO 风格需求文档框架（SRS Framework）

> 参考标准：ISO/IEC/IEEE 29148:2018（Requirements Engineering）
> 说明：本框架用于项目内部需求冻结与验收，不代表第三方认证。

---

## 0. 文档控制（Document Control）

### 0.1 元数据
- 文档编号
- 版本号
- 生效日期
- 作者/评审人/批准人
- 变更记录（版本、日期、变更摘要）

### 0.2 文档状态
- Draft / Review / Baseline / Obsolete

### 0.3 适用范围
- 产品范围（Web/移动端/后端）
- 发布范围（v1.2/v1.3）

---

## 1. 引言（Introduction）

### 1.1 目的（Purpose）
明确本文档用于需求冻结、开发实施、测试验收、上线评审。

### 1.2 范围（Scope）
定义系统边界、包含功能、不包含功能。

### 1.3 术语与缩写（Terms, Acronyms, Abbreviations）
统一术语表：项目、批次、锚点、候选、终态等。

### 1.4 参考资料（References）
列出规范、架构、API、UX 文档。

---

## 2. 干系人与业务目标（Stakeholders & Business Goals）

### 2.1 干系人列表
- 运营、设计、前端、后端、测试、运维、财务、管理员

### 2.2 业务目标（Business Objectives）
- 用可量化指标定义目标（转化、效率、质量、稳定性）

### 2.3 成功指标（KPIs）
- 功能 KPI
- 体验 KPI
- 稳定性 KPI

---

## 3. 系统上下文与边界（System Context & Boundaries）

### 3.1 上下文图
- 用户端、后端服务、OSS、模型服务、部署平台

### 3.2 边界定义
- 系统内职责
- 外部依赖职责

### 3.3 假设与约束（Assumptions & Constraints）
- 网络、QPS、存储、权限、合规约束

---

## 4. 业务场景与用例（Business Scenarios & Use Cases）

### 4.1 场景目录
每个场景必须包含：
- 场景编号（BS-xxx）
- 参与角色
- 前置条件
- 触发条件
- 主成功流
- 备选流
- 异常流
- 成功标准
- 失败处置

### 4.2 用例追踪
场景 -> 功能需求 -> 接口 -> 测试用例

---

## 5. 功能需求（Functional Requirements）

### 5.1 编号规范
- FR-AUTH-xxx（认证）
- FR-TASK-xxx（任务编排）
- FR-PI-xxx（商品工坊）
- FR-MR-xxx（模特工坊）
- FR-MA-xxx（多角度）
- FR-IV-xxx（讲解视频）
- FR-QV-xxx（15秒短片）
- FR-ASSET-xxx（资产中台）
- FR-BILL-xxx（积分）
- FR-USER-xxx（用户）

### 5.2 单条需求模板
每条需求必须包含：
1. Requirement ID
2. Requirement Statement（使用 shall）
3. Rationale（为何存在）
4. Source（来源：用户/产品/法规/技术）
5. Priority（Must/Should/Could）
6. Verification Method（Test/Inspection/Analysis/Demo）
7. Acceptance Criteria（可验收标准）

---

## 6. 业务规则（Business Rules）

### 6.1 规则编号
- BR-001 ~ BR-xxx

### 6.2 规则模板
- 规则定义
- 生效范围
- 触发条件
- 执行动作
- 例外条件

---

## 7. 数据与状态模型（Data & State Models）

### 7.1 关键实体
- Project、Asset、Batch、Identity、User、Ledger

### 7.2 状态机定义
- 项目状态机
- 批次状态机
- 认证状态机

### 7.3 数据一致性规则
- 终态闭环、幂等、重试语义

---

## 8. 接口需求（Interface Requirements）

### 8.1 外部接口
- OSS、模型服务、部署环境

### 8.2 内部 API 需求
每个接口定义：
- 路径
- 方法
- 输入
- 输出
- 错误码
- 幂等性
- 超时与重试策略

---

## 9. 非功能需求（Non-functional Requirements）

### 9.1 性能
- 响应时间、吞吐、并发

### 9.2 可用性
- 故障恢复、重试、降级

### 9.3 可观测性
- 日志、指标、告警

### 9.4 安全
- 认证、授权、数据保护

### 9.5 可维护性
- 代码质量、文档同步、回归机制

---

## 10. 验证与验收（Verification & Validation）

### 10.1 验证矩阵
- 需求 ID -> 测试用例 ID -> 结果

### 10.2 通过门槛（DoD）
- 功能通过
- 自动化通过
- UX 走查通过

### 10.3 回归策略
- 每次变更的最小回归集

---

## 11. 追踪矩阵（Traceability Matrix）

至少覆盖以下链路：
- 业务目标 -> 场景 -> 功能需求 -> 接口 -> 测试 -> 发布项

---

## 12. 变更控制（Change Control）

### 12.1 需求变更流程
提出 -> 评审 -> 批准 -> 基线更新 -> 通知开发/测试

### 12.2 基线保护规则
- 未进入基线的需求不得进入开发排期。
- 基线变更必须包含验收影响分析。

