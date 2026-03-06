# 05 设计系统与 UI 规范

## 视觉基线
- 主色（蓝）
- 辅助色（灰/浅蓝）
- 状态色（成功/警告/错误）
- 字体层级（标题/正文/辅助）
- 间距体系（4/8/12/16/24/32）

## 组件库
- Button：主/次/幽灵/危险/加载/禁用
- Card：默认/高亮/错误/选中
- Table：任务列表
- Form：输入/选择/上传
- Stepper：步骤引导
- Badge：状态/标签
- Banner/Toast：状态反馈
- Empty/Skeleton：空态/加载

## 布局规范
- 侧边栏宽度默认收紧（给主操作区留空间）
- 主操作区单一主 CTA
- 日志区默认折叠

## 文案统一
- submitting / running / success / failed 状态文案统一

## 可访问性（最低标准）
- 对比度符合 WCAG 2.2 AA
- 焦点态明显可见
- 表单标签始终可见

## 关键页面布局说明（文字线框）
- 工具箱首页：左侧工具栏 + 右侧样片墙与入口卡片
- 任务中心：上部看板 + 下部任务列表
- 工作台：左侧步骤导航 + 右侧主操作区（单主 CTA）

## Design Tokens（建议值）
### Color
- Primary: #2563EB
- Primary Hover: #1D4ED8
- Primary Active: #1E40AF
- Text Main: #0F172A
- Text Sub: #475569
- Border: #E2E8F0
- Surface: #FFFFFF
- Surface Alt: #F8FAFC
- Success: #16A34A
- Warning: #F59E0B
- Error: #EF4444

### Typography
- H1: 24px / 32px / 600
- H2: 20px / 28px / 600
- Body: 14px / 22px / 400
- Caption: 12px / 18px / 400

### Spacing / Radius / Shadow
- Spacing scale: 4 / 8 / 12 / 16 / 24 / 32
- Radius: 8 (cards), 6 (inputs), 999 (badges)
- Shadow: 0 4px 16px rgba(15, 23, 42, 0.08)

## 组件状态（必须支持）
### Button
- default / hover / active / disabled / loading
### Input
- default / focus / error / disabled
### Card
- default / hover / selected / disabled / error
### Banner
- info / success / warning / error
