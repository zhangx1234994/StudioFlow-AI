# UX P0 执行检查单（Sprint UX-01）

> 关联文档：  
> - `/Volumes/MAC 1/shipin/docs/ux/USER_STORY_EXECUTION_BACKLOG_2026-03-05.md`  
> - `/Volumes/MAC 1/shipin/docs/ux/UX_P0_SPRINT_PLAN_2026-03-05.md`

## A. 实施项
- [x] UX-P0-01 首屏产出预期卡（五工坊）
- [x] UX-P0-02 任务区优先队列（S3/S5/S6）
- [x] UX-P0-03 首页/资产破图兜底
- [x] UX-P0-04 用户管理异常优先视图
- [x] UX-P0-05 积分中心概览优先
- [x] UX-P0-06 单主 CTA + 状态统一
- [x] UX-P0-07 继续上次任务入口

## B. 质量门槛
- [x] `python3 -m ruff check app tests`
- [x] `python3 -m pytest -q`
- [x] `npm --prefix frontend run build`
- [ ] Playwright：U1/U3/U7/U8 四条关键路径通过

## C. 体验门槛
- [ ] 首屏 3 秒可读“产出预期”
- [x] 回访用户 10 秒可进入上次任务
- [ ] 客服 60 秒可定位异常账号
- [x] 积分页首屏不再是超长流水
- [ ] 全站无红色破图占位
