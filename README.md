# Folio

**Let your ideas unfold.** 从一段想法、一份文档开始，制作清晰、耐看、可编辑的演示文稿。

Folio 是原 PPTMaker 项目的新品牌。界面采用纸白、墨绿与浅灰绿侧栏；制作、设置、历史、个人中心共用一套设计语言。目录名与已有数据库文件名保留兼容，旧项目无需迁移。

## 现在可以做什么

- 输入文字，或导入 PDF、DOCX、Markdown、TXT；单文件最大 10 MiB。
- 设置 1–50 页、受众、六种演示风格以及封面、目录、总结和图表选项。
- 自动整理材料、规划大纲、并行制作、检查排版、导出可编辑 `.pptx`；逐页查看预览、正文与演讲备注。
- 在工作空间搜索、排序、收藏、重命名、添加标签、归档与恢复历史演示；打开已完成演示直接预览和下载，不重新调用模型。
- 管理可持久化的本地个人资料、默认风格和页数；查看后端配置的会员状态与权益、真实 Token 用量、缓存命中和月度输出预算。

当前每个服务实例共享一个本地账号。联系邮箱仅记录资料，不是登录凭据。Local / Plus 状态由管理员配置，未接入在线登录、支付或服务商余额查询。

## 本地启动

要求：Python 3.10+、Node.js 18+。以下命令从仓库根目录开始，在两个终端中运行。

后端：

```powershell
cd backend
python -m pip install -e ".[dev]"
Copy-Item .env.example .env  # 仅首次使用；已有配置不要覆盖
# 编辑 .env 中的模型服务与 API Key
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

前端：

```powershell
cd frontend
npm ci
npm run dev -- --host 127.0.0.1
```

打开 http://127.0.0.1:5173 。FastAPI 文档在 http://127.0.0.1:8000/docs ，健康检查为 `/health`。后端根路径返回服务信息，**不会直接提供前端网页**。Vite 代理 `/api`、`/ws`、`/storage` 到后端；可用 `VITE_BACKEND_HOST`、`VITE_BACKEND_WS_HOST` 修改开发代理地址。

## 配置

完整示例见 [backend/.env.example](backend/.env.example)。`.env` 按后端包的绝对位置读取，修改后重启后端。

| 配置 | 含义 |
|---|---|
| `LLM_PROVIDER` | `openai` 或 `anthropic`；兼容接口使用 `openai` |
| `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `OPENAI_MODEL` | 模型凭据、地址、名称；不要提交真实密钥 |
| `OPENAI_MAX_TOKENS` | 单次输出硬上限；各步骤还会应用更小的预算 |
| `PPT_CONCURRENCY` | 逐页并行度，默认 3，上限 8 |
| `PPT_MAX_REVIEW_ROUNDS` | 检查轮数，默认 2 |
| `PPT_REVIEW_MODE` | 默认 `local`；`vision` 需要支持图片的模型 |
| `DEEPSEEK_REASONING_EFFORT` | 普通改写默认 `none`，可按角色覆盖 |
| `LLM_JSON_MODE` | `auto` / `on` / `off`，兼容网关需确认支持 |
| `FOLIO_MEMBERSHIP` | `local` / `plus`，后端管理本地会员标识 |
| `FOLIO_MEMBERSHIP_EXPIRES_AT` | 可选 ISO 到期时间；到期后取消 VIP 状态 |
| `FOLIO_MONTHLY_OUTPUT_LIMIT` | UTC 月度输出 Token 预算，`0` 表示不设上限 |
| `FOLIO_DB` | 可选 SQLite 路径；未设置时沿用 `PPTMAKER_DB` 或 `storage/pptmaker.sqlite3` |
| `STORAGE_PATH` | PPTX、PNG 存储目录，默认后端工作目录下的 `storage` |

额度是本地预算，不能代表供应商账户余额。并行调用会先原子预留该步骤的输出预算，返回后按实际用量结算。剩余额度不足以支持一次完整步骤时，该步骤不会发送模型请求。

## API 概览

生成操作走双向 WebSocket `ws://127.0.0.1:8000/ws/{project_id}`，REST 负责创建、历史和账号查询。完整字段与消息见 [API 文档](docs/API.md)。

| 方法 | 路径 | 用途 |
|---|---|---|
| POST | `/api/v1/projects` | 创建项目，返回完整初始快照 |
| GET | `/api/v1/projects` | 搜索、筛选、排序、分页的历史摘要 |
| GET | `/api/v1/projects/{id}` | 恢复完整项目及有效下载链接 |
| PATCH | `/api/v1/projects/{id}` | 标题、收藏、归档、标签 |
| GET | `/api/v1/workspace` | 历史数量、完成、收藏、页面与存储统计 |
| POST | `/api/v1/upload/parse` | multipart 文档文本提取 |
| GET | `/api/v1/account` | 本地资料、会员、用量与连接概况 |
| PATCH | `/api/v1/account/profile` | 修改个人资料和默认偏好 |
| GET | `/api/v1/account/usage` | 持久化月度用量与额度 |
| GET | `/api/v1/account/membership` | 当前会员状态与权益 |
| GET | `/api/v1/llm/usage?project_id={id}` | 当前进程的调用诊断 |
| GET | `/storage/{filename}` | 下载 PPTX 或读取 PNG 预览 |

不存在 `/projects/{id}/generate`、`/parse`、`/plan` 等生成 REST 接口；对应命令为 `parse_input`、`plan_outline`、`generate_parallel`、`render_pptx`。

## 结构与生成原理

```text
frontend/src/
  App.tsx                         Hash 导航与新项目自动流程
  components/layout/StudioShell   全页共用侧栏、品牌、导航
  components/layout/*Page         设置、工作空间、账号、演示预览
  stores/projectStore.ts          草稿、项目、WebSocket 命令
backend/app/
  api/routes.py                   创建、列表、上传、诊断
  api/workspace.py                历史详情、元数据、账号
  api/websocket.py                队列与生成流程
  agent/nodes/                    内容规划与受控检查
  tools/slide_scene.py             PNG 与 PPTX 共用排版
  tools/pptx_generator.py          可编辑原生对象导出
  llm/                            SDK 复用、缓存、真实用量
  storage/                        SQLite 项目、账号、用量账本
```

模型负责内容，代码负责排版。紧凑 JSON 保留校验能力；封面、目录与结束页复用大纲，Designer 默认采用本地模板，Critic 默认检查几何与可读性。预览和导出共享英寸坐标、文本换行、字号与配色。浏览器只挂载当前页的完整预览。

项目、个人资料与用量写入 SQLite；进程重启后可以恢复历史。连接关闭会取消当前制作；页面内导航仍保留当前连接。中断的制作标记为可重试，保留材料与页面，用户点击后才重新制作。结果缓存是进程内缓存，重启会失效；月度用量不会失效。

## 验证与文档

```powershell
# backend
python -m pytest -q -p no:cacheprovider
# frontend
npm test
npm run build
```

不调用模型的 PPT 样张：从仓库根目录运行 `python scripts/preview_styles.py`，输出到 `storage/design_samples/`。真实生成会使用已配置的模型服务并产生调用费用。

- [当前需求与规格](SPEC.md)
- [设计系统与新页面约定](docs/DESIGN_SYSTEM.md)
- [API 与 WebSocket 协议](docs/API.md)
- [优化研究、缓存与费用实测](docs/OPTIMIZATION.md)
- [部署与备份](DEPLOY.md)
- [测试与验收](TESTING.md)

目前不包含在线支付、多租户鉴权、扫描 PDF OCR、外部 PPTX 母版导入和浏览器内完整幻灯片编辑。PNG 是轻量预览，PowerPoint 字体替换、原生图表轴线与表格细节可能产生差异。生产部署需采用单个后端 worker，并在外层配置访问控制，详见部署说明。
