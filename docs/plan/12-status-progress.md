# 12 状态机与进度标准

## 项目状态机（Project）
- draft：创建完成，未生成方案
- scripted：方案/执行方案已就绪
- rendering：生成进行中
- completed：交付完成
- failed：失败并停止

## 任务状态机（TaskRun）
- queued：排队中
- running：执行中
- reviewing：待审核/待选片
- done：完成
- failed：失败

## 阶段映射（工具统一）
- plan：方案生成阶段
- prompt：执行方案整理
- generate：生成中
- review：人工审核/选片

## 进度算法（统一口径）
- 进度由后端统一计算，前端只显示
- 按阶段权重加权
- 无产物时不允许“completed”

## 失败与重试策略
- 失败原因必须可见（错误码+文案）
- 从失败阶段重试（不回退已完成阶段）

## 文案口径
- 不暴露内部状态名（scripted/prompt）
- 对用户显示中文状态（方案已就绪/生成中/待确认）
