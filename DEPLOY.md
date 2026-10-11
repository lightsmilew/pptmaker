# Folio 发布包部署指南

更新：2026-10-09。本文以 **Ubuntu 24.04 / Debian、Nginx、systemd 和域名 `lightsmile.ink`** 为例。生产步骤从构建后的发布包执行，服务器无需克隆仓库、安装 Node 或运行 Vite。

Folio 使用一个后端 worker：生成任务、项目缓存与实时广播仍在进程内。后端 wheel 是可安装的 Python 包，仍需 Python 3.10+，不是无需运行环境的独立二进制程序。wheel 可包含 Python 模块；生产不使用 editable 安装或源码目录启动。

## 1. 在开发机构建发布包

构建机需要 Python 3.10+（含 pip）、Node.js 18+ 和 npm。首次构建需要访问 npm / Python 包索引。以下命令从仓库根目录执行。

你的证书放在本地 `deploy/`：

```text
deploy/
  lightsmile.ink.pem   # PEM 站点证书，建议包含中间证书链
  lightsmile.ink.key   # 与证书匹配、可非交互加载的私钥
```

脚本验证证书 / 私钥可匹配加载，不打印私钥。不复制后端 `.env`、数据库、上传资料、测试目录、node_modules 或 Git 元数据。`deploy/` 和输出 `dist/` 被 Git 忽略。

Windows：

```powershell
python scripts/build.py --domain lightsmile.ink --release-name folio-0.1.0-r1
# 等价入口：
# .\scripts\build.bat --domain lightsmile.ink --release-name folio-0.1.0-r1
```

Linux / macOS：

```bash
bash scripts/build.sh --domain lightsmile.ink --release-name folio-0.1.0-r1
```

默认执行 `npm ci`、TypeScript / Vite 构建、后端 wheel 构建、模板渲染和归档。已有依赖且无需重装时可加 `--skip-npm-ci`。省略 `--release-name` 生成含 UTC 时间的唯一名字；相同名称的发布包不覆盖，下一次使用 `folio-0.1.0-r2` 等新名字。

```text
dist/
  folio-0.1.0-r1.zip
  folio-0.1.0-r1.zip.sha256
  folio-0.1.0-r1.tar.gz
  folio-0.1.0-r1.tar.gz.sha256
  folio-0.1.0-r1/
    backend/folio_studio-0.1.0-py3-none-any.whl
    frontend/index.html, assets/, folio-mark.svg, ...
    deployment/install.sh
    deployment/folio.env.example
    deployment/folio.service
    deployment/nginx/folio.conf
    deployment/nginx/folio-http.conf
    tls/lightsmile.ink.pem
    tls/lightsmile.ink.key
    release.json
    SHA256SUMS
    DEPLOY.md
```

Nginx 域名、证书路径及生产 Origin 按 `--domain` 渲染。**含证书的包包含私钥，只通过受控方式传到自己的服务器，不上传公共 Release、网盘或静态网站目录。**分享不含证书的安装包可用 `--without-certificates --domain lightsmile.ink`；部署前另行安装 TLS 文件。

可选离线包：在与目标服务器 **相同 Linux / CPU / Python 版本** 的环境加 `--bundle-dependencies`，附带 `wheelhouse/`，安装脚本使用 `--no-index`。默认包只包含应用 wheel，安装时从包索引解析依赖；依赖范围来自 pyproject.toml，目前没有完整跨平台依赖锁。Windows 构建的普通应用包可用于 Linux，Windows 的依赖 wheelhouse 不可用于 Linux。

## 2. 准备服务器与 DNS

通过 SSH 登录自己的 Linux 服务器，账号需要 sudo。将 `lightsmile.ink` 的 A 记录指向公网 IPv4；只有配置 IPv6 监听与防火墙后才添加 AAAA 记录。

云安全组 / 防火墙开放 SSH 管理端口、TCP 80 和 443。API 只监听 127.0.0.1:8000，不开放公网 8000；生产不用 5173。

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nginx openssl fonts-noto-cjk tesseract-ocr tesseract-ocr-chi-sim tesseract-ocr-eng
python3 --version
sudo systemctl enable --now nginx
getent ahostsv4 lightsmile.ink
```

`fonts-noto-cjk` 用于中文 PNG 预览，绘制器读取 `/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc`。PPTX 不嵌入字体，打开演示的电脑仍需相应字体。

创建独立服务账号与目录（首次）：

```bash
id folio >/dev/null 2>&1 || sudo useradd --system --user-group --home-dir /var/lib/folio --shell /usr/sbin/nologin folio
sudo install -d -m 0755 /opt/folio/releases
sudo install -d -m 0750 -o root -g folio /etc/folio
sudo install -d -m 0700 -o root -g root /etc/folio/tls
sudo install -d -m 0700 -o folio -g folio /var/lib/folio
sudo install -d -m 0700 -o folio -g folio /var/lib/folio/storage
```

| 目录 | 用途 |
|---|---|
| `/opt/folio/releases/<发布名>` | 每次发布独立安装包与 venv，由 root 管理 |
| `/opt/folio/current` | 当前发布的符号链接 |
| `/etc/folio/runtime/folio.env` | 生产配置，folio 专属可写目录；管理页可更新允许的运行项 |
| `/etc/folio/tls` | Nginx 使用的证书与私钥 |
| `/var/lib/folio/folio.sqlite3` | 用户、会话、项目与用量数据库 |
| `/var/lib/folio/storage` | PPTX、预览、上传原文件等持久数据 |

## 3. 上传、校验与安装

开发机上传到自己的服务器，替换实际 SSH 账号与地址：

```powershell
scp dist/folio-0.1.0-r1.tar.gz dist/folio-0.1.0-r1.tar.gz.sha256 deploy@YOUR_SERVER_IP:/tmp/
```

服务器上：

```bash
FOLIO_RELEASE=folio-0.1.0-r1
cd /tmp
chmod 600 "$FOLIO_RELEASE.tar.gz"
sha256sum --check "$FOLIO_RELEASE.tar.gz.sha256"
sudo tar -xzf "$FOLIO_RELEASE.tar.gz" -C /opt/folio/releases
FOLIO_RELEASE_DIR="/opt/folio/releases/$FOLIO_RELEASE"
sudo bash "$FOLIO_RELEASE_DIR/deployment/install.sh"
```

安装脚本先校验 `SHA256SUMS`，再建立该发布专用 `.venv`，安装 wheel 和运行依赖，执行 `pip check`。失败时先解决网络 / 依赖问题；成功前不要切换 current。重试安装需使用新的发布目录，不覆盖已有 venv。

包索引下载较慢时，可只为这次安装指定 HTTPS 镜像，避免改变系统全局配置。例如 [清华镜像站官方说明](https://mirrors.tuna.tsinghua.edu.cn/help/pypi/) 提供的地址：

```bash
# 替代上面的安装命令；尚未创建 .venv 时使用。
sudo env PIP_INDEX_URL=https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple bash "$FOLIO_RELEASE_DIR/deployment/install.sh"
```

确保静态资源可被 Nginx 读取，TLS 源目录仅 root 可读：

```bash
sudo chmod 755 "$FOLIO_RELEASE_DIR"
sudo find "$FOLIO_RELEASE_DIR/frontend" -type d -exec chmod 755 {} \;
sudo find "$FOLIO_RELEASE_DIR/frontend" -type f -exec chmod 644 {} \;
sudo chmod 700 "$FOLIO_RELEASE_DIR/tls"
```

不含证书的包跳过最后一行，按第 5 节另外安装证书。

## 4. 配置后端与 systemd

首次复制配置，已有生产配置不要覆盖：

```bash
sudo install -d -m 0700 -o folio -g folio /etc/folio/runtime
sudo test -f /etc/folio/runtime/folio.env || sudo install -m 0600 -o folio -g folio "$FOLIO_RELEASE_DIR/deployment/folio.env.example" /etc/folio/runtime/folio.env
sudoedit /etc/folio/runtime/folio.env
```

至少检查以下值，API Key 在服务器自行填写：

```dotenv
DEBUG=false
STORAGE_PATH=/var/lib/folio/storage
FOLIO_DB=/var/lib/folio/folio.sqlite3
LLM_PROVIDER=openai
OPENAI_API_KEY=填写真实密钥
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_MODEL=deepseek-flash
OPENAI_MAX_TOKENS=12000
PPT_CONCURRENCY=3
PPT_REVIEW_MODE=local
PPT_MAX_REVIEW_ROUNDS=2
FOLIO_COOKIE_SECURE=true
FOLIO_ALLOWED_ORIGINS=https://lightsmile.ink
FOLIO_SESSION_DAYS=7
FOLIO_MONTHLY_OUTPUT_LIMIT=0
```

模型地址 / 名称需供应商支持。Anthropic 配置 `LLM_PROVIDER=anthropic` 及 `ANTHROPIC_API_KEY`、`ANTHROPIC_MODEL`、`ANTHROPIC_BASE_URL`。认证用户额度来自会员方案或账号独立额度；`FOLIO_MONTHLY_OUTPUT_LIMIT` 仅用于无用户身份的离线调用。默认 local 检查不调用视觉模型。

`folio-server --env-file` 在导入应用前加载指定配置，已有进程环境变量优先。生产使用绝对数据路径，升级不会因 wheel 目录变化而生成另一数据库。服务固定单 worker、不启用 reload，只信任本机 Nginx 的代理头。

首次激活与启动：

```bash
sudo ln -s "$FOLIO_RELEASE_DIR" /opt/folio/current
sudo install -m 0644 "$FOLIO_RELEASE_DIR/deployment/folio.service" /etc/systemd/system/folio.service
sudo systemctl daemon-reload
sudo systemctl enable --now folio
sudo systemctl status folio --no-pager
curl --fail http://127.0.0.1:8000/health
```

应返回 `{"status":"healthy"}`。日志：

```bash
sudo journalctl -u folio -n 100 --no-pager
sudo journalctl -u folio -f
```

服务账号可写 `/var/lib/folio` 与 `/etc/folio/runtime`；systemd 限制其他路径写入。前者保存应用数据，后者允许管理页原子更新运行配置。重启 / 升级会中断制作，启动后未完成任务变为可重试，已有页面、历史与用量保留。

## 5. 安装你的域名证书

当前包已包含 `lightsmile.ink.pem` 与 `.key`，无需 Certbot：

```bash
sudo install -m 0644 -o root -g root "$FOLIO_RELEASE_DIR/tls/lightsmile.ink.pem" /etc/folio/tls/lightsmile.ink.pem
sudo install -m 0600 -o root -g root "$FOLIO_RELEASE_DIR/tls/lightsmile.ink.key" /etc/folio/tls/lightsmile.ink.key
sudo openssl x509 -in /etc/folio/tls/lightsmile.ink.pem -noout -dates -ext subjectAltName
sudo openssl x509 -in /etc/folio/tls/lightsmile.ink.pem -noout -checkend 0
```

确认 SAN 覆盖 lightsmile.ink，证书仍有效。PEM 应含站点证书及必要的中间证书，仅有叶证书可能导致浏览器链验证失败。构建校验匹配关系，不替代有效期、域名与可信链验收。加密私钥需准备可非交互启动的服务器配置；脚本不收集或打印解密密码。

私钥不进入 frontend。Nginx 只将 frontend 作为网站根目录；数据库、上传目录、release 根目录和 tls 目录不得公开为 alias。

## 6. 配置 Nginx 和 HTTPS

使用 **包内已替换域名的模板**，不是仓库中含 `@@DOMAIN@@` 的原始模板：

```bash
sudo install -m 0644 "$FOLIO_RELEASE_DIR/deployment/nginx/folio.conf" /etc/nginx/sites-available/folio
sudo ln -s /etc/nginx/sites-available/folio /etc/nginx/sites-enabled/folio
sudo nginx -t
sudo systemctl reload nginx
curl -I http://lightsmile.ink
curl --fail https://lightsmile.ink/health
```

HTTP 应重定向 HTTPS，HTTPS /health 返回 healthy。sites-enabled/folio 已存在时保留链接，只更新 sites-available/folio。其他站点不要删除；同域名冲突需调整后再 `nginx -t`。

模板包含：

- 静态首页及前端路由回退 index.html；版本化 assets 长期缓存，index.html 重新验证。
- `/api/` 保留路径转发，传递 Host、协议与真实客户端 IP。
- `/ws/` 传递 Upgrade / Connection，HTTP/1.1，读写超时 3600 秒。
- `/storage/` 转发后端验证 Cookie 与归属，绝不公开磁盘；`/health` 用于探活。
- 11 MiB 请求体上限，为 10 MiB 附件及 multipart 留出空间。
- TLS 1.2 / 1.3；Cookie / Origin 原样传递，前后端同源 `https://lightsmile.ink`。

公网 `/docs` 和 `/openapi.json` 默认不代理；从服务器本机访问 `http://127.0.0.1:8000/docs`，或通过 SSH 端口转发查看。VITE_BACKEND_HOST 只改变开发代理，生产连接由 Nginx 管理。WS 规则依据 [Nginx 官方文档](https://nginx.org/en/docs/http/websocket.html)。

## 7. 生产验收

1. 打开 https://lightsmile.ink，证书可信、Folio 首页 / Logo 正常，HTTP 跳 HTTPS。
2. 注册验收账号，检查工作空间、创作方案、个人中心、16 种风格与资料保存。
3. 上传 / 拖入参考文档，创建 4 页演示，确认 WS 状态 101。真实制作会产生模型费用。
4. 制作时刷新 / 关闭页面，后端继续；重连恢复状态。完成后手动下载，不自动下载。
5. PNG / PPTX 可下载，预算与用量更新；第二账号不能读第一账号的项目与文件。
6. 已完成演示打开不重复调用模型；重启后历史保留，未完成制作可显式重试。
7. 390px 手机布局无横向溢出，菜单、表单和预览可操作。

health 只表示进程可用，不代表 API Key、余额、磁盘或完整生成链路可用。

## 8. 初始化独立管理员与会员管理（无需源码）

管理员不从用户首页登录，也不从已有用户提升身份。首次部署后创建**新邮箱的专用账号**；命令生成随机密码并写入指定的新文件，不接受命令行明文密码，不覆盖已有邮箱或凭据文件。

```bash
sudo -u folio /opt/folio/current/.venv/bin/folio-create-admin --env-file /etc/folio/runtime/folio.env --email admin@lightsmile.ink --credentials-file /var/lib/folio/admin-bootstrap.txt
sudo cat /var/lib/folio/admin-bootstrap.txt
```

访问 `https://lightsmile.ink/#/admin/login`，用文件内的账号登录，在“管理账号”修改初始密码，然后移除该凭据文件。管理页面：概览、账号管理、会员权益、模型与环境、用量与额度、活动记录、用户沟通。普通用户 Cookie 与管理 Cookie 分开，管理接口需要管理员身份及 CSRF 校验。

`.env` 修改需要 `/etc/folio/runtime` 可写，以及 systemd 的 `ReadWritePaths=/var/lib/folio /etc/folio/runtime`。目录归 folio、权限 0700，文件 0600；不要开放 `/etc/folio/tls` 或整个 `/etc/folio` 的写权限。CLI 的 `--env-file` 自动指定管理页使用的配置文件。模型参数保存后立即应用，正在制作时拒绝修改；数据库、文件目录、来源白名单和 HTTPS 安全设置仍需离线编辑并重启服务。配置页的密钥永不回传，普通页面不能读取配置。

新用户默认普通会员（50,000 月度输出 Token、最多 20 页、单份并行 1 页）；Plus（150,000 / 35 页 / 2）、Pro（500,000 / 50 页 / 3）、Studio（2,000,000 / 50 页 / 6）。实际并行不超过全局 `PPT_CONCURRENCY`。方案可在管理页修改；用户可单独配置额度或到期时间，到期恢复普通权益。所有限额由后端执行；无在线支付和自动续费。

“用量与额度”提供持久调用统计，DeepSeek 官方接口可查询真实余额；其他接口明确显示不支持余额查询。日志包含登录结果 / IP / User-Agent、操作与制作阶段，不记录密码、密钥、提示词和模型正文。启用前的登录与活动不会伪造补齐，现有项目可在生成记录中查看。

应急时还可以使用 CLI 调整已经注册的普通用户：

```bash
sudo -u folio /opt/folio/current/.venv/bin/folio-manage-user --env-file /etc/folio/runtime/folio.env --email author@example.com --tier plus --monthly-output-limit 100000
sudo -u folio /opt/folio/current/.venv/bin/folio-manage-user --env-file /etc/folio/runtime/folio.env --email author@example.com --expires-at 2027-01-01T00:00:00+00:00
```

`--tier` 支持 basic / plus / pro / studio；`--expires-at none` 清除到期，`--monthly-output-limit 0` 不限，未传字段保持原值。恢复方案默认额度请在管理页关闭账号独立额度。开发时从 `backend` 目录运行 `python ../scripts/create_admin.py --env-file .env` 或 `python ../scripts/manage_user.py --env-file .env`，并补齐各自必填参数；这样与开发服务使用同一配置和数据库。

## 9. 升级、回滚与续期

先备份并等待活跃制作结束。用新发布名构建、上传、解压并安装到新目录；.env、证书与数据保持独立。

```bash
FOLIO_RELEASE=folio-0.1.0-r2
FOLIO_RELEASE_DIR="/opt/folio/releases/$FOLIO_RELEASE"
# 先按第 3 节完成新包校验、解压、安装及权限检查。
readlink -f /opt/folio/current
sudo systemctl stop folio
sudo ln -s "$FOLIO_RELEASE_DIR" /opt/folio/current.next
sudo mv -Tf /opt/folio/current.next /opt/folio/current
sudo systemctl start folio
sudo nginx -t
sudo systemctl reload nginx
curl --fail https://lightsmile.ink/health
```

记录切换前路径，如 /opt/folio/releases/folio-0.1.0-r1。回滚同样停服务，让 current.next 指向旧发布，原子替换 current，启动并 reload Nginx。不要在共享 venv 中直接降级，保留各发布独立依赖。

代码回滚不会撤销数据库结构变化；跨版本结构变更需恢复数据库备份及对应产物。没有通用 schema downgrade 工具，不能保证任意旧版本直接读新数据库。

证书续期：从供应商获取新文件，检查域名、日期与匹配关系，按第 5 节的路径 / 权限替换，nginx -t 后 reload。项目不自动续签你的证书；替换证书不必重启后端。

## 10. 数据备份与恢复

数据库和整个 storage 必须一起备份，配置 / 证书也保存在受控位置。下例先停服务，保持快照与产物一致；不要仅复制正在写入的 SQLite 主文件而漏掉 WAL。

```bash
FOLIO_BACKUP="/var/backups/folio/$(date -u +%Y%m%dT%H%M%SZ)"
sudo install -d -m 0700 "$FOLIO_BACKUP"
sudo systemctl stop folio
sudo tar -czf "$FOLIO_BACKUP/data.tar.gz" -C /var/lib/folio .
sudo tar -czf "$FOLIO_BACKUP/config-and-tls.tar.gz" -C /etc/folio .
sudo chmod 600 "$FOLIO_BACKUP"/*.tar.gz
sudo systemctl start folio
```

确认 tar 成功再继续。备份失败时先恢复服务，再处理磁盘 / 权限。恢复时停服务，保存当前目录，将对应数据恢复到 /var/lib/folio、配置恢复到 /etc/folio，恢复 folio 数据目录所有权及 0700 / 0640 / 0600 权限，再启动并检查历史文件。

归档仅标记，不释放磁盘。用量、会话、预算预留在数据库；结果与诊断缓存仍在内存。不要只将持久数据放在临时容器层。

## 11. 故障排查

| 现象 | 处理 |
|---|---|
| Nginx 502 | systemctl status folio、journalctl、本机 8000/health；current/.venv 是否已安装 |
| 证书 / 配置错误 | nginx -t；私钥权限、证书路径、SAN、日期与中间证书链 |
| WS 403 / 登录失效 | 域名与 HTTPS Origin 完全一致；Secure Cookie、Host / Origin 未改写 |
| WS 空闲后断开 | Upgrade / Connection 和读写超时；重连应恢复后台状态 |
| 上传 413 | Nginx 32m；创作资料10 MiB；沟通图片5 MiB / 文件10 MiB，总共最多3个附件 |
| API 收到 HTML | /api 被前端回退覆盖；proxy_pass 不加尾部斜杠 |
| 中文预览方框 | fonts-noto-cjk 与字体可读性，安装后重启 |
| 空历史 / 下载 404 | 绝对 FOLIO_DB / STORAGE_PATH、所有权及文件是否被移动 |
| pip 安装失败 | Python、包索引网络及目标平台；离线包需匹配 Linux / Python / CPU |
| 检查有建议 | 建议不阻止可用导出；自动调整 1–4 次，视觉异常回退本地检查 |

当前没有跨进程任务队列，不启用多个 worker / 多实例。打包成功不等于目标 Linux 上 Nginx、systemd、DNS、证书链及模型服务已通过部署验收。

## 12. 其他域名可选 Certbot

lightsmile.ink 使用你提供的证书，无需此步骤。其他域名没有证书时可按 [Certbot 官方指引](https://certbot.eff.org/instructions?ws=nginx&os=snap) 安装，DNS 正确且 80 端口可达后申请：

```bash
# 先用相应域名构建包，临时安装包内 folio-http.conf 为 Nginx 站点。
sudo snap install --classic certbot
sudo /snap/bin/certbot certonly --nginx -d YOUR_DOMAIN
sudo /snap/bin/certbot renew --dry-run
```

正式 folio.conf 的证书路径改为 `/etc/letsencrypt/live/YOUR_DOMAIN/fullchain.pem` 和 privkey.pem，nginx -t 后 reload。续期成功后通过 Certbot deploy hook reload Nginx，不引用不会自动更新的证书副本。

## 本地开发

开发仍可从源码运行：backend 安装 `python -m pip install -e ".[dev]"`，首次配置 backend/.env，运行 `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`；frontend 中 npm ci 后 npm run dev。Vite 代理 /api、/ws、/storage。生产使用本文发布包。

## lightsmile.ink 实际部署

2026-10-09 已通过 SSH 部署到 Ubuntu 22.04 / Python 3.10.12。公网入口为 [Folio](https://lightsmile.ink)，独立管理员入口为 [管理中心](https://lightsmile.ink/#/admin/login)。当前安装目录、维护命令、验收结果与证书期限见 [运行记录](docs/OPERATIONS.md)。凭据和真实 API Key 不写入文档或发布包。


### 图文沟通与在线通知

新版安装包包含支持消息表；应用首次访问时幂等创建，不修改已有账号和历史演示。继续备份完整 SQLite 数据库与 storage（包括 support 图片目录）。Nginx 的 `/api/` 代理关闭缓冲以即时发送 SSE；API 也返回 `X-Accel-Buffering: no`。保留 Cookie、Origin 转发，勿把管理预览或沟通图片 alias 为静态目录。`client_max_body_size 32m` 容纳3个10 MiB文件及 multipart 字段，后端仍逐个校验图片5 MiB / 其他文件10 MiB。

验收时用隔离账号分别登录用户端与独立管理端：发送图文、确认管理员离线收件、互发消息、离开沟通页验证站内提示、重新打开确认未读清零。管理端在活动记录的生成记录查看预览并显式下载，普通账号访问管理 URL 应401，其他用户访问图片应404。SSE 连接每2秒同步数据库状态；断线自动重连，注销或撤销会话会结束连接。站内通知不等于离线设备推送。


安装版 `folio-server` 将优雅关闭等待限制为10秒，避免在线 SSE 长连接无限阻塞维护重启。更新前仍应确认没有演示制作任务；超时会终止未关闭的连接，浏览器会自动重连。


### 截图与文档粘贴

安装依赖步骤已包含 Tesseract 和 `chi_sim` / `eng` 数据。用 `tesseract --list-langs` 确认两个语言；参考截图的中英文 OCR 在后端本机运行，不增加模型调用。Windows 开发安装官方文档推荐的 Tesseract 构建，加入 PATH，或通过进程环境 `TESSERACT_CMD` 指向可执行文件；默认也检测 Program Files/Tesseract-OCR。未安装、识别失败或超时时图片仍可上传，界面提示补充要求。参见 [Tesseract 安装说明](https://tesseract-ocr.github.io/tessdoc/Installation.html)。

备份 storage/support 的 `.jpg` 与 `.bin` 文件和完整 SQLite；新附件表幂等创建，旧图片消息继续有效。附件下载只走用户/管理鉴权接口，不公开 support 目录。SSE 连接长期存在，安装 CLI 的优雅关闭上限10秒，发布后核对服务与 HTTPS health。

### 主题图库与公告随包部署

后端 wheel 内包含 `app/assets/photos/catalog.json` 与42张 JPEG，安装时一并解包；运行时不需要联网下载图片，也无需图片搜索密钥。不得删除该目录。来源与许可随包文档 `docs/IMAGE_SOURCES.md`，原图署名同时写入 PPTX 备注。公告表与每日隐藏记录自动在原有 Folio SQLite 数据库中创建，继续备份 `/var/lib/folio`；无需另建数据库或手工迁移旧数据。新功能不要求增加 Nginx 路径或改变现有安全 Cookie/CSRF 设置。

当前线上版本为 `folio-0.1.0-r13-mobile-controls-images`，r13 备份 `/var/backups/folio/20261011-r13`，旧版本 r12 保留可回滚。42张图库、公告权限与每日记录已通过独立安装和数据库验收；正式服务健康，既有演示和账号保留，详见 docs/OPERATIONS.md。

### 轻量图片与移动顶栏

r13安装包包含Logo顶部导航、英文标签标题和统一按钮。参考图/沟通图上传前按用途压缩；后端仍负责验证图片与消息权限。沟通图片新增`.thumb.webp`派生文件，与原`.jpg`/附件`.bin`及SQLite一起备份；旧消息第一次授权查看时自动补建，无需迁移表结构。图片private,no-cache/ETag只在鉴权后重用，Nginx不得对/api私有内容配置公共缓存。运行依赖沿用Pillow（含WebP）与Tesseract，无新增服务或密钥。
