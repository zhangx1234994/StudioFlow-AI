# AI摄影棚

AI摄影棚是面向电商素材团队的生成工作台，提供 5 个独立工具：

1. `intro-video` 转化讲解视频工坊
2. `product-image` 商品棚拍出图工坊
3. `model-retouch` 模特人像精修工坊
4. `quick-video-15s` 15秒场景短片工坊
5. `multi-angle-camera` 多角度展品工坊

系统采用 **FastAPI + Next.js** 单端口集成：
- 后端 API：`/api/v1/*`
- 前端入口：`/app/*`
- 旧入口（`/tools`、`/assets`、`/login` 等）已重定向到 `/app/*`

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
npm --prefix frontend install
./scripts/dev_service.sh up
```

登录：`admin / admin123`

访问地址：
- 工具箱首页: `http://127.0.0.1:5005/app/tools`
- 素材库: `http://127.0.0.1:5005/app/assets`
- 健康检查: `http://127.0.0.1:5005/healthz`

## Frontend Architecture

- `frontend/` 使用 Next.js App Router（静态导出）
- 构建产物输出到 `frontend/out`
- FastAPI 通过 `/app/{path}` fallback 返回 `frontend/out/index.html`

## Backend Architecture

- `app/main.py`：路由、鉴权、静态托管、工具 API
- `app/services/`：VL 规划、提示词编译、图视频生成编排
- `app/store.py`：本地 JSON 持久化（当前测试环境）
- `data/uploads` / `data/renders`：上传与生成素材

## Environment Variables

从 `.env.example` 复制到 `.env`。

关键变量：
- `MVP_USE_MOCK_PROVIDERS=true`：本地 mock 模式（默认建议）
- `MVP_VOLC_API_KEY`：火山 VL（也兼容读取 `ARK_API_KEY`）
- `MVP_VOLC_MODEL`：VL 模型名（默认 `doubao-seed-2-0-mini`）
- `MVP_KIE_API_KEY`：KIE 图/视频接口
- `MVP_AUTH_ENABLED=true`：启用登录态鉴权
- `MVP_ALLOW_BACKGROUND_TASKS=true`：启用后台异步任务

## Validation Commands

```bash
python3 -m ruff check app tests
python3 -m pytest -q
npm --prefix frontend run build
```

## Docs

Start here: `docs/INDEX.md` — documentation hub, file map, and ownership.

## Vercel Notes

仓库已包含 `api/index.py`、`vercel.json` 与 `requirements.txt`，可直接通过 Git 接入 Vercel。

### Deploy 流程

1. 在 Vercel 里 `Add New Project`，选择本仓库。
2. Framework 保持 `Other`（无需改 Root Directory）。
3. Build Command 使用仓库内配置：`npm --prefix frontend ci && npm --prefix frontend run build`。
4. 部署后访问：`/app/tools`。

### 必填环境变量（Vercel）

- `MVP_USE_MOCK_PROVIDERS`（测试建议先设 `true`）
- `MVP_AUTH_ENABLED`
- `MVP_ADMIN_USERNAME`
- `MVP_ADMIN_PASSWORD`
- `MVP_AUTH_SECRET`
- `MVP_VOLC_API_KEY`
- `MVP_VOLC_MODEL`（建议 `doubao-seed-2-0-mini`）
- `MVP_KIE_API_KEY`
- `MVP_OSS_ACCESS_KEY`
- `MVP_OSS_SECRET_KEY`
- `MVP_OSS_BUCKET`
- `MVP_OSS_REGION`
- `MVP_OSS_ENDPOINT`
- `MVP_OSS_PUBLIC_DOMAIN`
- `MVP_OSS_ROOT_PREFIX`

说明：Vercel 环境会自动把本地存储切到 `/tmp/photo2video-data`；长期素材与结果请使用 OSS。
