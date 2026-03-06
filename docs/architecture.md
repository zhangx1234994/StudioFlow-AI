# 架构与模块说明

## 总览
- **前端**：Next.js App Router（静态导出）
- **后端**：FastAPI（单端口服务）
- **集成方式**：FastAPI 挂载 `frontend/out`，前端入口 `/app/*`
- **存储**：本地 JSON / OSS / Redis（按配置切换）

## 关键目录
- 后端入口：`/Volumes/MAC 1/shipin/app/main.py`
- 服务编排：`/Volumes/MAC 1/shipin/app/services/`
- 数据模型：`/Volumes/MAC 1/shipin/app/schemas.py`
- 状态存储：`/Volumes/MAC 1/shipin/app/store.py`
- 前端入口：`/Volumes/MAC 1/shipin/frontend/app/page.jsx`

## 请求主链路
1. 前端提交表单 → `POST /api/v1/projects`
2. 后端创建 Project + Asset + 初始状态
3. 进入工作台后按步骤调用：
   - `/plan`（方案）
   - `/derive-prompts`（提示词）
   - `/generate-images` or `/generate-videos`
   - `/review`

## OSS 直传
- 前端先调用 `/api/v1/oss/sign`
- 直传后仅提交 `image_public_url` 给后端
- 后端只负责记录与编排，不阻塞创建流程

## 状态与进度
- 状态标准见：`/Volumes/MAC 1/shipin/docs/status-progress-standard.md`
