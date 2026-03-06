# 运行与排错手册

## 本地启动
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
npm --prefix frontend install
npm --prefix frontend run build
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 5005
```

## 根治“服务总是掉线”的标准做法

### 本地（macOS/Linux）
不要再用一次性 `nohup` 或临时后台命令。统一使用仓库自带服务脚本：

```bash
# 构建前端 + 常驻启动（screen 托管）
./scripts/dev_service.sh up

# 查看状态
./scripts/dev_service.sh status

# 重启（会先构建前端）
./scripts/dev_service.sh restart

# 查看实时日志
./scripts/dev_service.sh logs
```

说明：
- 脚本会使用 `screen` 托管 uvicorn，终端断开后服务仍保持运行。
- 脚本会做健康检查，启动失败会直接回显最近日志，避免“假启动”。

### 服务器（Linux 生产）
使用 `systemd` 管理进程，禁止手工后台运行：

```bash
cd /opt/studioflow-ai
sudo ./deploy/systemd/install.sh /opt/studioflow-ai
sudo systemctl status studioflow-ai.service
sudo journalctl -u studioflow-ai.service -f
```

说明：
- `Restart=always`，进程异常退出会自动拉起。
- 开机自启动，避免重启机器后服务丢失。

## 存储后端（当前实现）
- 默认不是 PostgreSQL/MySQL，而是 `InMemoryStore + 持久化`：
  - 本地：`data/state/store.json`
  - 可选：Redis（`MVP_STORE_BACKEND=redis`）
  - 可选：OSS 对象存储（`MVP_STORE_BACKEND=oss`）
- 本地模式默认开启异步写盘：`MVP_STORE_ASYNC_PERSIST=true`

## 常见问题
1) 前端白屏
- 确认 `frontend/out/index.html` 是否存在
- 查看浏览器控制台报错

2) OSS 直传失败
- 检查 `/api/v1/oss/sign` 是否 200
- 检查 OSS 公共域名和权限

3) 创建任务慢
- 前端应先直传 OSS
- 后端只收 URL，不阻塞创建

4) 选片“入选/分享”响应慢
- 检查是否启用 `MVP_STORE_ASYNC_PERSIST=true`
- `data/state/store.json` 过大时，建议切换到 `redis` 后端

## 日志
- 主要日志：`/Volumes/MAC 1/shipin/data/logs/app.log`
