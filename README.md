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
npm --prefix frontend run build
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 12222
```

登录：`admin / admin123`

访问地址：
- 工具箱首页: `http://127.0.0.1:12222/app/tools`
- 素材库: `http://127.0.0.1:12222/app/assets`
- 健康检查: `http://127.0.0.1:12222/healthz`

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
- `MVP_VOLC_API_KEY`：火山 VL
- `MVP_KIE_API_KEY`：KIE 图/视频接口
- `MVP_AUTH_ENABLED=true`：启用登录态鉴权
- `MVP_ALLOW_BACKGROUND_TASKS=true`：启用后台异步任务

## Validation Commands

```bash
python3 -m ruff check app tests
python3 -m pytest -q
npm --prefix frontend run build
```

## Vercel Notes

仓库已包含 `api/index.py` 与 `vercel.json`，后续可通过 Git 接入 Vercel。
首发阶段建议继续使用 mock provider 验证全链路交互，再切换真实模型密钥与持久化方案。
