# Folio 部署与数据维护

更新：2026-10-07。Folio 由 React 静态前端和 FastAPI 后端组成。当前适合个人 / 受控工作空间使用，生成队列、连接和活跃项目缓存仍在进程内，因此使用 **一个后端 worker**。

## 1. 本地开发

在仓库的 `backend` 中安装 `python -m pip install -e ".[dev]"`，首次复制 `.env.example` 到 `.env` 并配置模型。已有 `.env` 不要覆盖。

```powershell
# backend 终端
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
# frontend 终端
npm ci
npm run dev -- --host 127.0.0.1
```

访问 http://127.0.0.1:5173 。前端开发代理覆盖 `/api`、`/ws`、`/storage`。后端 `http://127.0.0.1:8000/` 是服务信息 JSON；`/docs` 是接口文档。

开发可以使用 `--reload`，但重载会中断制作；重启后历史标为需重试。长时间生成时使用无 reload 的单进程。

## 2. 生产构建与服务

```sh
cd frontend
npm ci
npm run build
# 将 frontend/dist 交给静态服务器
cd ../backend
python -m pip install -e .
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

固定后端工作目录为 `backend`，或使用绝对 `STORAGE_PATH` / `FOLIO_DB`。默认数据库在 `backend/storage/pptmaker.sqlite3`；保留旧文件名是为了兼容原历史。指定一个新数据库路径会形成新的工作空间，不会自动复制旧数据库。

前端生成包使用同源 `/api`、`/ws`、`/storage` URL；`VITE_BACKEND_HOST` 只改变 Vite 开发代理，不能替代生产反向代理。`vite preview` 只预览前端产物，不作为完整生产部署方案。

Linux 可使用 systemd（路径需按实际部署替换）：

```ini
[Unit]
Description=Folio Studio API
After=network.target

[Service]
User=folio
WorkingDirectory=/opt/folio/backend
EnvironmentFile=/opt/folio/backend/.env
ExecStart=/opt/folio/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
```

服务账号需能写数据库目录和产物目录，但不需要系统管理权限。Windows 可用已有服务管理器运行同样的单 worker 命令，保持固定工作目录。

## 3. 静态服务器与反向代理

示例 Nginx 配置，TLS 证书和访问控制按部署环境配置。所有页面、API、WebSocket、文件路径都应受同一访问控制保护，因为当前实例共享一个本地账号。

```nginx
server {
    listen 443 ssl;
    server_name folio.example.com;
    root /opt/folio/frontend/dist;
    index index.html;
    client_max_body_size 11m;

    # 在此配置 TLS 和受控访问，例如 auth_basic / 企业网关鉴权。
    # 不要只保护主页而让 API、WebSocket 和 /storage 公开。

    location / {
        try_files $uri $uri/ /index.html;
    }
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
    }
    location /ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
    location /storage/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_read_timeout 300s;
    }
}
```

浏览器在 HTTPS 下自动使用 WSS。静态服务器不能把 API 请求回退成 `index.html`；否则页面会收到 HTML 而非 JSON。WebSocket 必须传 Upgrade 头。

## 4. 本地账号、会员与预算

```dotenv
FOLIO_MEMBERSHIP=local
# plus 为管理员配置的本地 VIP 标记，非付款凭证
# FOLIO_MEMBERSHIP_EXPIRES_AT=2027-01-01T00:00:00+00:00
FOLIO_MONTHLY_OUTPUT_LIMIT=0
PPT_CONCURRENCY=3
PPT_REVIEW_MODE=local
```

这些字段由后端读取，客户端资料 API 不能修改权限。Plus 到期会失去 VIP 标记；当前两档保留本地版基础权益。没有登录注册、密码、邮箱认证、支付或自动续费服务。

月度输出预算使用 UTC 自然月，0 为不限。并行调用先原子预留各步骤的完整预算，再结算 SDK 返回的实际用量；未完成预留在 30 分钟后释放。重启不会清空使用账本，进程内响应缓存和调用诊断窗口会清空。预算不是服务商余额；配额不足时可由管理员修改预算并重启。

## 5. 数据与备份

需要一起保留数据库、PPTX 与 previews 子目录。数据库包含完整原文与作品、个人资料、Token 用量，产物目录含 PNG 和 PowerPoint。不要把 `.env` 或数据库提交到 Git。

SQLite 支持在线 backup；运行以下 Python 片段时工作目录为 backend，路径按实际配置设置：

```python
import sqlite3
from pathlib import Path
Path("backups").mkdir(exist_ok=True)
with sqlite3.connect("storage/pptmaker.sqlite3") as source:
    with sqlite3.connect("backups/folio.sqlite3") as destination:
        source.backup(destination)
```

另行复制产物目录。还原时停止服务，恢复数据库与对应产物，再启动同一工作目录的服务。归档只是标记，不释放磁盘空间；网页不提供永久删除，避免误删历史。

## 6. 部署验收与故障定位

1. `/health` 返回 healthy，`/docs` 显示 Folio Studio API。
2. 前端显示 Folio 新 Logo，侧栏可打开工作空间、设置、个人中心。
3. 资料保存并刷新后保留；会员配置与预算显示正确，不返回密钥。
4. 创建 4 页演示，WebSocket 正常，完成后 PPTX 可下载，PNG 可读，用量更新。
5. 重启后旧演示可打开且不会自动重新制作；正在制作的任务变为可重试。
6. 390px 手机布局无水平溢出，菜单、表单和预览可操作。

连接失败：确认 `/ws` 代理、Upgrade 头、端口和模型配置；配置变更需重启。下载 404：确认固定 `STORAGE_PATH` 和产物是否被搬走。空历史：检查 `FOLIO_DB` 是否指向原数据库。额度不足：查看预留和输出上限，别通过给浏览器伪造额度解决。多 worker / 多实例可能导致状态与广播不一致，应先增加持久任务队列和跨进程事件，再扩展部署。
