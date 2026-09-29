# PPTMaker 部署教程

本教程介绍如何将 PPTMaker 部署到生产环境。

## 目录

- [环境要求](#环境要求)
- [构建项目](#构建项目)
- [本地部署](#本地部署)
- [服务器部署](#服务器部署)
- [Docker 部署](#docker-部署)
- [Nginx 配置](#nginx-配置)
- [常见问题](#常见问题)

## 环境要求

- Node.js >= 18.0.0
- Python >= 3.10
- npm 或 yarn
- pip

## 构建项目

### Windows

```powershell
cd PPTMaker
scripts\build.bat
```

### Linux/Mac

```bash
cd PPTMaker
chmod +x scripts/build.sh
./scripts/build.sh
```

构建完成后，静态文件会在 `dist/frontend` 目录，后端代码在 `dist/app`。

## 本地部署

### 1. 安装后端依赖

```bash
cd dist
pip install -e .
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，填入你的 API Key
```

### 3. 启动服务

方式一：直接运行
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

方式二：使用 Gunicorn (推荐生产环境)
```bash
pip install gunicorn
gunicorn app.main:app --bind 0.0.0.0:8000 --workers 2
```

### 4. 访问应用

- 前端: http://localhost:8000
- API 文档: http://localhost:8000/docs

## 服务器部署

### Ubuntu/Debian 示例

#### 1. 安装系统依赖

```bash
sudo apt update
sudo apt install -y python3.10 python3-pip nginx certbot
```

#### 2. 创建服务用户

```bash
sudo useradd -m -s /bin/false pptmaker
sudo mkdir -p /opt/pptmaker
sudo cp -r dist/* /opt/pptmaker/
sudo chown -R pptmaker:pptmaker /opt/pptmaker
```

#### 3. 安装 Python 依赖

```bash
cd /opt/pptmaker
sudo -u pptmaker pip3 install -e .
```

#### 4. 配置 Systemd 服务

创建 `/etc/systemd/system/pptmaker.service`:

```ini
[Unit]
Description=PPTMaker Service
After=network.target

[Service]
User=pptmaker
Group=pptmaker
WorkingDirectory=/opt/pptmaker
Environment="PATH=/opt/pptmaker/venv/bin"
ExecStart=/opt/pptmaker/venv/bin/gunicorn app.main:app --bind 127.0.0.1:8000 --workers 2
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

#### 5. 启动服务

```bash
sudo systemctl daemon-reload
sudo systemctl enable pptmaker
sudo systemctl start pptmaker
```

#### 6. 配置 Nginx

创建 `/etc/nginx/sites-available/pptmaker`:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # 前端静态文件
    location / {
        root /opt/pptmaker/frontend;
        try_files $uri $uri/ /index.html;
    }

    # API 代理
    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_cache_bypass $http_upgrade;
    }

    # WebSocket 代理
    location /ws {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }
}
```

启用站点:

```bash
sudo ln -s /etc/nginx/sites-available/pptmaker /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

#### 7. 配置 HTTPS (可选)

```bash
sudo certbot --nginx -d your-domain.com
```

## Docker 部署

### 1. 创建 Dockerfile

在项目根目录创建 `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装 Node.js
RUN apt-get update && apt-get install -y curl && \
    curl -fsSL https://deb.nodesource.com/setup.sh | bash - && \
    apt-get install -y nodejs

# 复制文件
COPY . .

# 构建前端
RUN cd frontend && npm install && npm run build

# 安装 Python 依赖
RUN pip install -e .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 2. 创建 docker-compose.yml

```yaml
version: '3.8'

services:
  pptmaker:
    build: .
    ports:
      - "8000:8000"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    restart: unless-stopped
```

### 3. 启动

```bash
docker-compose up -d
```

## Nginx 配置

如果需要将前端构建产物直接嵌入后端，可以配置 Nginx 统一服务:

```nginx
server {
    listen 80;
    server_name your-domain.com;
    root /opt/pptmaker/frontend;
    index index.html;

    # 静态资源缓存
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # API 代理
    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # WebSocket
    location /ws {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # SPA 路由
    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

## 常见问题

### Q: 构建失败，提示缺少模块

确保在正确的目录下运行构建脚本，并安装所有依赖。

### Q: 前端显示 404

检查 Nginx 配置中的 `root` 路径是否正确指向前端构建目录。

### Q: API 请求跨域错误

确保后端 CORS 配置正确，或通过 Nginx 代理避免跨域。

### Q: WebSocket 连接失败

检查 Nginx 是否正确配置了 WebSocket 代理，包括 `Upgrade` 和 `Connection` 头。

### Q: 内存占用过高

- 减少 Gunicorn worker 数量
- 启用 Python 虚拟环境隔离依赖
- 监控并限制单个请求的资源使用

## 环境变量

| 变量名 | 描述 | 必需 |
|--------|------|------|
| OPENAI_API_KEY | OpenAI API Key | 是 |
| ANTHROPIC_API_KEY | Anthropic API Key | 否 |
| LOG_LEVEL | 日志级别 (debug/info/warning/error) | 否 |
| MAX_FILE_SIZE | 最大上传文件大小 (MB) | 否 |

## 监控

推荐使用以下工具监控应用:

- **PM2**: Node.js 进程管理 (用于前端静态文件服务)
- **Gunicorn**: Python WSGI 服务器
- **Prometheus + Grafana**: 指标监控
- **ELK Stack**: 日志收集和分析
