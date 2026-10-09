# Folio 部署与数据维护

更新：2026-10-08。Folio 由公开首页、注册 / 登录、React 工作台和 FastAPI 后端组成。支持多用户，各账号资料、作品、附件、用量与额度存入服务端。生成队列、连接和项目缓存仍在进程内，因此使用 **一个后端 worker**。

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

固定后端工作目录为 `backend`，或使用绝对 `STORAGE_PATH` / `FOLIO_DB`。默认数据库路径仍为 `backend/storage/pptmaker.sqlite3`，实际数据在服务端；新账号不会继承原共享记录。指定新数据库路径会形成全新账号与工作空间集合，不自动复制数据。正式部署建议指定持久磁盘路径。

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

示例 Nginx 配置。公开首页可匿名访问，业务 API / WebSocket / 文件由 FastAPI 验证 Cookie、CSRF、Origin 和归属。部署使用 HTTPS，`FOLIO_COOKIE_SECURE=true`，`FOLIO_ALLOWED_ORIGINS=https://folio.example.com`（改成真实域名）。前后端保持同源，代理传递 Cookie 和 Origin，不将 `/storage` 配为公开静态磁盘目录。

```nginx
server {
    listen 443 ssl;
    server_name folio.example.com;
    root /opt/folio/frontend/dist;
    index index.html;
    client_max_body_size 11m;

    # 配置真实 TLS 证书；Cookie 与 Origin 默认会转发到后端。
    # /storage 必须经过后端验证，不能 alias 为公开磁盘目录。

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

## 4. 服务端账号、会员与预算

```dotenv
FOLIO_SESSION_DAYS=7
FOLIO_COOKIE_SECURE=true
FOLIO_ALLOWED_ORIGINS=https://folio.example.com
FOLIO_MONTHLY_OUTPUT_LIMIT=0
PPT_CONCURRENCY=3
PPT_REVIEW_MODE=local
```

开发环境通过 `.env.example` 的 localhost Origin 和 `FOLIO_COOKIE_SECURE=false` 使用 HTTP。生产必须改为自己的 HTTPS Origin 和 Secure Cookie，配置变更后重启。不要使用通配符 Origin。

用户从公开首页注册，默认 Folio Basic，不会继承旧共享账号的数据；本次不做旧数据迁移。登录邮箱不能通过资料 API 改写；注册、登录有限流，退出会话立即撤销，修改密码会撤销其他设备旧会话。会话、随机盐密码散列、账号资料都在服务器，不依赖浏览器持久存储。

管理员从仓库根目录配置已注册用户：

```powershell
python scripts/manage_user.py --email author@example.com --tier plus --monthly-output-limit 100000
python scripts/manage_user.py --email author@example.com --expires-at 2027-01-01T00:00:00+00:00
```

可用 `--tier basic` 取消 Plus，`--expires-at none` 清除到期时间，`--monthly-output-limit 0` 不限，未传字段保持原值。脚本读取同一后端 `.env` / 数据库，每个用户独立配置，保存后查询即生效；无需通过网页伪造权益。Basic / Plus 均提供当前基础功能，尚未接入邮件验证、找回密码、在线支付或自动续费。

月度预算使用 UTC 自然月，用户级预算优先于 `FOLIO_MONTHLY_OUTPUT_LIMIT` 默认值，0 不限。调用先原子预留完整预算，再按实际输出结算，30 分钟后释放未完成预留。不同用户独立扣减，重启不会清空账本；进程内结果缓存和调用诊断会清空。模型由服务管理员配置，额度不是供应商余额。

## 5. 数据与备份

数据库和整个产物目录需要持久磁盘并一起备份：数据库含 users、sessions、projects、uploads、usage_ledger、output_reservations；产物含 PPTX、previews 和 uploads 原文件。用户不应能直接读取服务器磁盘 / 数据库。前端保存的是临时草稿；正式账号、作品、附件和用量都来自后端。不要把 `.env`、数据库或凭据提交 Git，也不要把持久数据只留在临时容器层。

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
2. 前端显示 Folio 新 Logo，侧栏可打开工作空间、创作方案、个人中心；设计目录显示 16 种风格。
3. 资料保存并刷新后保留；会员配置与预算显示正确，不返回密钥。
4. 创建 4 页演示，WebSocket 正常，完成后出现手动下载按钮，不自动下载；PNG 可读，用量更新。
   制作中刷新 / 关闭页面，后端应继续完成；重连恢复状态和有效下载链接。已完成项目再次点击继续不增加模型调用，同一项目运行中重复提交不创建并发副本。
5. 重启后旧演示可打开且不会自动重新制作；正在制作的任务变为可重试。
6. 390px 手机布局无水平溢出，菜单、表单和预览可操作。

连接失败：确认 `/ws` 代理、Upgrade 头、端口和模型配置；配置变更需重启。下载 404：确认固定 `STORAGE_PATH` 和产物是否被搬走。空历史：检查 `FOLIO_DB` 是否指向原数据库。额度不足：查看预留和输出上限，别通过给浏览器伪造额度解决。多 worker / 多实例可能导致状态与广播不一致，应先增加持久任务队列和跨进程事件，再扩展部署。

页面检查建议不会阻止可用演示导出：`PPT_MAX_REVIEW_ROUNDS` 是初次检查后的调整次数，默认 2，限制 1–4。视觉复核异常会回退本地检查并保留警告；未消除的建议可在制作页继续调整。若实际写作 / 绘制 / 导出失败，重试会复用已有内容并跳过已完成且通过的页面；`generate_parallel` 的 `force=true` 才重新制作全部页面。

网页以 `run_workflow` 提交一次意图，后端编排剩余步骤。开始 / 继续、调整、导出使用单进程后台任务，浏览器断开不会取消；部署重启仍会中断，启动时恢复为可重试。需要跨进程可靠执行时须增加持久任务队列；当前不要启用多个 worker。低层 parse / plan 兼容命令仍绑定连接，不用于网页自动编排。
