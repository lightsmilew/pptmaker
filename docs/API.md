# Folio API 与事件协议

更新：2026-10-09。开发 API 位于 `http://127.0.0.1:8000`，前端同源访问。账号、项目、附件、用量和额度在服务端按用户隔离。业务 REST 和文件未登录返回 401，其他用户的项目返回 404。OpenAPI `/docs` 为字段约束来源。

## 发布环境与同源代理

生产通过已安装的 `folio-server --env-file /etc/folio/runtime/folio.env` 启动单 worker。默认域名为 lightsmile.ink；Nginx 将 /api/、/ws/、/storage/ 和 /health 原路径代理至 127.0.0.1:8000，传递 Cookie / Origin 和 WebSocket Upgrade。前端使用同源 URL，不能通过 VITE_BACKEND_HOST 改变生产连接地址。

公开站点不直接暴露数据库 / 文件目录。/storage 仍执行后端认证；部署模板默认不公开 /docs 和 /openapi.json，可通过服务器本机查看。HTTP 重定向 HTTPS，Cookie Secure 与 FOLIO_ALLOWED_ORIGINS=https://lightsmile.ink 对齐。安装包和代理步骤见 [DEPLOY.md](../DEPLOY.md)，REST / WebSocket 消息格式不因打包而改变。

管理 API 位于 `/api/v1/admin`，使用独立管理员 Cookie 与会话。`folio-create-admin --env-file /etc/folio/runtime/folio.env` 创建新管理账号；`folio-manage-user` 保留离线调整用户权益，资料 PATCH 不能授予权限。

完整管理契约、字段与限制见 [ADMIN_API.md](ADMIN_API.md)，包含认证、账号、四级会员、.env、模型目录、供应商余额、Token 汇总与分页活动记录。

## 认证与会话

| 方法 | 路径 | 请求与响应 |
|---|---|---|
| POST | `/api/v1/auth/register` | `email`、`password`、`display_name`；201，注册并登录 |
| POST | `/api/v1/auth/login` | `email`、`password`；200 |
| GET | `/api/v1/auth/session` | 当前账号与 CSRF token；未登录 401 |
| POST | `/api/v1/auth/logout` | 撤销当前会话，清 Cookie，关闭该会话 WebSocket；204 |
| POST | `/api/v1/auth/password` | `current_password`、`new_password`；撤销所有旧会话，创建新的当前会话 |

注册、登录和密码修改成功返回 `{"account":{…},"csrf_token":"…"}`。服务端设置 `folio_session` Cookie：HttpOnly、SameSite=Strict，生产启用 `FOLIO_COOKIE_SECURE=true`。默认 7 天有效（`FOLIO_SESSION_DAYS`，1–30），令牌只以 SHA-256 摘要保存到服务器。客户端不在 localStorage 存凭据。

邮箱去空白并规范为小写，唯一且格式有效；密码 10–128 字符；注册称呼 1–40 字且非空白。密码以随机盐 scrypt 散列保存。重复邮箱 409，邮箱 / 密码错误 401，无效字段 422，超限 429。15 分钟内同 IP 最多 60 次、同邮箱最多 20 次认证尝试。

注册 / 登录需要 `X-Folio-Request: 1`。其余修改接口均需要 Cookie 与 `X-CSRF-Token`（取登录 / 注册 / GET session 响应），无效返回 403。浏览器 Origin 必须在 `FOLIO_ALLOWED_ORIGINS` 中；业务响应 `Cache-Control: no-store`。登录邮箱 `account.login_email` 与可修改的联系邮箱 `profile.email` 分开。邮件验证、第三方登录、找回密码与在线支付尚未接入。

## REST

### 创建项目

`POST /api/v1/projects`

```json
{
  "spec": {"topic":"季度研究报告","page_count":8,"style":"学术简约","audience":"研究生","needs_cover":true,"needs_toc":true,"needs_summary":true,"needs_chart":false,"layout_mode":"auto","content_density":"balanced","notes":"保留原文证据"},
  "user_input":"参考内容与制作要求"
}
```

`spec`、`user_input`、`uploaded_files` 可选。页数 1–50 整数，创建和 WS 修改共用校验；`spec` 未提供时采用当前账号的服务端偏好。附件为 `[{"upload_id":"upload_…"}]`，仅接受本人已上传文件，正文从服务端读取并避免重复追加。返回完整初始快照（200），含服务端生成的 `owner_id`，客户端不能指定归属；仅创建不会调用模型。

快照主要字段：`id`、`spec`、`user_input`、`status`、`current_step`、`progress`、`error`、`outline`、`pages`、`workflow`、`created_at`、`updated_at`。页面保存 `content`（标题、副标题、短标题/说明、图表/表格、备注）、`layout`、`preview`、`review`、`status`、`iteration` 等。

`pages[].review` 包含 `method`（`local_geometry` / `local_geometry_fallback` / `vision`）、`status`（`approved` / `needs_revision` / `blocked` / `failed`）、`score`、`issues`、`suggestions` 和可空的 `warning`。页面 `status=completed` 表示已有可用输出，不等于 `review.status=approved`；整份演示可完成并提供下载，同时保留待调整建议。视觉检查异常回退本地排版检查时，`warning` 明确说明尚未通过视觉复核。

### 搜索与分页

`GET /api/v1/projects`

| 参数 | 默认值 | 说明 |
|---|---|---|
| `q` | 空 | 标题 / 受众 / 风格 / 标签匹配，不区分大小写；最多取前 200 字 |
| `status` | `all` | `all` / `draft` / `completed` / `failed`；draft 排除完成和失败 |
| `favorite` | 未设置 | 可选布尔值 |
| `archived` | `false` | 选择未归档或归档集合 |
| `sort` | `updated` | `updated` / `created` / `title` |
| `page` | `1` | 从 1 开始 |
| `page_size` | `12` | 1–50 |

```json
{"projects":[],"total":0,"page":1,"page_size":12}
```

列表条目为摘要，不含原文或整份页内容：`id`、`title`、`audience`、`style`、`status`、`page_count`、`completed_pages`、`favorite`、`archived`、`tags`、`created_at`、`updated_at`、`preview_url`、`download_url`、`file_size`。只有项目已完成且 PPTX 文件存在时才返回下载链接和文件大小。

### 项目详情与元数据

`GET /api/v1/projects/{id}` 返回完整快照，并补充 `download_url`；不存在返回 404。刷新演示页用此接口恢复，不需重新规划。

`PATCH /api/v1/projects/{id}`：

```json
{"title":"新的历史标题","favorite":true,"archived":false,"tags":["研究","季度"]}
```

字段均可选，未知字段禁止。标题 1–120 字，不允许纯空白；标签最多 8 个，每个去空白后 1–24 字并去重。返回新的项目摘要。重命名仅修改项目主题，已生成幻灯片不会被重写。归档 / 恢复不会删除内容或取消制作。

`GET /api/v1/workspace` 返回 `name`、`mode`、`stats` 与最近 4 个未归档摘要；统计含 `total`、`completed`、`favorites`、`in_progress`、`archived`、`pages`、`storage_bytes`。

### 文档导入

`POST /api/v1/upload/parse`：`multipart/form-data` 的 `file` 字段，最大 10 MiB。支持 `.pdf`、`.docx`、`.md`、`.markdown`、`.txt`，不支持 `.doc`。

返回 `upload_id`、`filename`、`size`（实际字节数）、`content`、`content_preview`（前 500 字）。网页只保留 ID / 名称 / 大小，不拼接全文；创建时后端读取所属附件并去重，同一附件 ID 只加入一次材料。原始文件写入服务端 `uploads/{user_id}/{upload_id}/original.{ext}`，提取文本与归属写数据库。格式不支持、超限、空文本、损坏文档为 400；不自动创建项目；PDF 无 OCR。此接口需要 Cookie 与 CSRF，原始附件没有公开下载路径。

### 个人中心

`GET /api/v1/account` 返回四部分：

- `profile`：`account_id`、`display_name`、`email`、`company`、`occupation`、`bio`、`timezone`、`created_at`、`updated_at`（保存后）和 `preferences`。
- `membership`：`tier`、`name`、`is_vip`、`status`、`expires_at`、`managed_by`、`billing_mode`、`features`、`limits`。
- `features` 中的风格数量来自当前后端风格目录，不单独维护过期数量。
- `usage`：持久化月度统计，字段见下文。
- `account`：`mode=server`、`status=active`、`login_email`、`email_verified=false`、`provider_host`、`model`、`provider_connected`、`authentication=server_session`。只返回模型主机名，不返回密钥或带凭据的 URL；`workspace.mode` 同样为 server。

`PATCH /api/v1/account/profile` 允许：

```json
{"display_name":"创作者","email":"author@example.com","company":"工作室","occupation":"研究员","bio":"关注清晰表达。","timezone":"Asia/Shanghai","preferences":{"style":"学术简约","page_count":8}}
```

称呼 1–40 字且不能纯空白，邮箱至多 254 字且校验格式，机构 80 字、职业 60 字、简介 200 字。时区允许上海、UTC、东京、伦敦、纽约对应的 IANA 名称。偏好允许目录中的 16 种风格、1–50 页、`layout_mode`、`content_density`、语言标记 `zh-CN` / `en`；语言标记目前仅存储，不提供完整英文界面。嵌套偏好按字段合并。

禁止通过资料接口更改 `account_id`、`created_at`、VIP、会员额度等；未知字段返回 422。返回更新后的完整 account view。

`GET /api/v1/account/membership` 返回当前用户会员：注册默认普通会员 basic，支持 plus / pro / studio，管理员通过管理页设置等级与到期。返回新增 `effective_tier`；到期后原 `tier` 保留、`status=expired`，实际 name / limits / 方案额度恢复 basic。默认页数上限 20 / 35 / 50 / 50，单份并行 1 / 2 / 3 / 6（同时受全局上限约束）。`managed_by=server_configuration`，`billing_mode=server_provider`；无购买接口。账号视图的 `account.role` 为 user 或 admin，不由资料接口修改。

`GET /api/v1/account/usage` 返回：

```json
{
  "period":"2026-10","period_start":"2026-10-01T00:00:00+00:00","resets_at":"2026-11-01T00:00:00+00:00",
  "calls":0,"lifetime_calls":0,"input_tokens":0,"output_tokens":0,"cached_input_tokens":0,
  "reasoning_tokens":0,"successful_calls":0,"response_cache_hits":0,"duration_ms":0,
  "provider_cache_hit_rate":null,"daily":[],
  "quota":{"unit":"output_tokens","limit":null,"used":0,"reserved":0,"remaining":null,"source":"server_budget","is_unlimited":true}
}
```

`daily` 条目含 `date`、`output_tokens`、`calls`，只列有记录的 UTC 日期。供应商输入缓存比例为 cached/input，没有输入时为 null；进程内响应缓存命中单独计数。调用数包含失败与结果缓存命中，成功数包括成功复用。账本从启用功能后累计，不回填旧进程的记录。

用户独立 output_limit 优先，否则使用有效会员方案的 monthly_output_limit（默认 50,000 / 150,000 / 500,000 / 2,000,000），0 不限；FOLIO_MONTHLY_OUTPUT_LIMIT 仅用于无用户身份的离线兼容调用。账本、预留、进程内结果缓存按用户隔离，生成线程继承归属。请求前原子预留完整预算，返回后按实际输出结算，不足不调用 SDK。该额度不是服务商余额。REST 创建 / 默认页数保存及 WS 设置 / 制作均校验会员页数，超出返回 403 或 error 事件。

### 诊断与文件

`GET /api/v1/llm/usage?project_id={id}` 从当前进程最近 2000 次调用中筛选当前用户记录，指定项目也校验归属；`recent_calls` 最多 100 条。重启会清空诊断窗口，不清空持久账本。`duration_ms` 是调用时长之和，不是并行项目墙钟时间。

`GET /storage/{project_id}.pptx` 下载；`GET /storage/previews/{project_id}/{page_id}/iteration-01.png` 等路径读取预览。接口返回的实际路径为准。`GET /health` 返回健康状态；`GET /` 返回 Folio Studio 服务信息。

## WebSocket

连接 `/ws/{project_id}`，验证 Cookie、Origin 和项目归属，再发送 `initial_state`。未登录关闭码 4401，无权 / 不存在 4404，不可信 Origin 4403；每个排队命令执行前再次校验会话。消息为 JSON：

```json
{"type":"plan_outline","data":{}}
```

| 客户端命令 | `data` | 行为 |
|---|---|---|
| `run_workflow` | 可省略 | 后端依据持久状态选择剩余步骤；新项目开始、历史项目继续或重新导出 |
| `parse_input` | 可省略 | 解析原文，保留明确表单设置 |
| `plan_outline` | 可省略 | 生成大纲与待制作页面 |
| `generate_parallel` | 可省略，或 `{"force":true}` | 制作 / 继续调整并导出；默认跳过已完成且通过的页面，force 重新制作全部页面 |
| `render_pptx` | 可省略 | 从当前页面重新导出，不重新写作 |
| `update_spec` | `{"patch":{…}}` | 修改当前项目配置 |
| `update_page` | `{"page_id":"page-01","patch":{…}}` | 修改页数据并标记 editing；需重新导出，旧 PNG 不自动重绘 |
| `trigger_review` | `{"page_id":"page-01"}` | 按配置检查指定页 |
| `delete_project` | 可省略 | 删除项目记录，永久操作；网页未提供该入口 |
| `ping` | 可省略 | 返回 pong，不等待生成队列 |

网页顺序为创建 → 连接 → 发送一次 `run_workflow`。后端自动串联 parse / plan / generate；已有大纲时复用，已完成且文件存在时返回已有下载链接，editing 或已完成但文件丢失时重新导出。恢复历史项目只订阅状态，需用户点击继续制作才提交指令，打开 / 刷新不会新增模型调用。

`generate_parallel.data.force` 如提供必须是布尔值，默认 false。初次检查后最多调整 `PPT_MAX_REVIEW_ROUNDS` 次（默认 2，1–4），先用实际内容测量选择本地布局，必要时才改写内容；不会因为一轮分数降低提前放弃剩余调整。调整未通过或出错时保留最佳可用内容 / 布局 / 预览和真实检查建议，仍导出并发送 `completed`；实际未能生成页面、导出失败或取消才返回失败。再次生成会复用带建议的页面、重绘预览并复查；已完成且通过的页面不产生额外写作调用。`trigger_review` 也不会把已有可用页面仅因建议而降为生成失败。

`update_spec.patch` 仅接受 topic / audience / page_count / style / needs_cover / needs_toc / needs_summary / needs_chart / notes / layout_mode / content_density；`update_page.patch` 仅接受 content / layout / title / page_type / status，不接受文件路径、page_id、preview 或 review。创建与修改不能绕过页数上限。

| 服务端事件 | 主要内容 |
|---|---|
| `initial_state` | 完整项目快照 |
| `state_patch` | 全量或部分项目字段，客户端合并 |
| `progress` | `step`、`progress`、`message` |
| `parallel_status` | 总页数、完成数、失败数、页状态映射 |
| `page_updated` | `page_id`、`status`、`iteration`、可选 preview / review |
| `preview_ready` | `page_id`、`image_path`、`preview`（实际 image_path / width / height / rendered_at）、`iteration` |
| `review_completed` | `page_id`、`method`、`status`、`score`、`issues`、`suggestions`、可空的 `warning` |
| `completed` | 成功导出后的 `download_url` |
| `error` | `message` |
| `pong` | 时间戳 |

项目状态包含 idle、parsing、parsed、planning、planned、generating、reviewing、rendering、editing、completed、failed。页面状态包含 pending、writing、designing、rendering、reviewing、revising、completed、failed。

`run_workflow`、`generate_parallel`、`render_pptx` 提交后由后端任务持有，事件广播给该项目当前已认证连接；关闭连接不取消这些任务，重连可获取含实际 `download_url` 的完整快照。`initial_state` / `state_patch` 与 REST 共用文件可用性判断，未完成或文件不存在时链接为 null。相同项目运行中再次提交复用现有任务，force 不会在运行中并发启动另一份生成；此时 `update_spec` / `update_page` / `delete_project` 被拒绝。

低层 `parse_input` / `plan_outline` 保留连接内排队兼容行为，网页不使用它们串联流程。任务和广播仍只在单 worker 进程内，没有持久任务队列或多实例协调；服务重启时未结束制作转为 failed，保留页面，可显式重试。已授权的后台任务不会仅因退出登录而取消，但退出会撤销会话并关闭实时连接；再次读取必须重新认证。

认证实现参考：[OWASP 会话管理](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)、[OWASP CSRF 防护](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)、[Python hashlib](https://docs.python.org/3/library/hashlib.html)。这些链接说明设计依据，不代表项目已经完成第三方安全审计。

## 设计目录与创作方案

`GET /api/v1/design/catalog` 需要有效登录，返回 `styles`（16 项）、`layout_modes`（4 项）和 `densities`（3 项）。风格字段：`name`、`category`、`description`、`family`、`primary`、`secondary`、`text`、`background`；编排 / 密度字段：`id`、`name`、`description`。网页风格目录以此为来源。

创建和 `update_spec` 共同接受 `layout_mode: auto | editorial | structured | spotlight` 与 `content_density: airy | balanced | compact`；省略时分别为 `auto`、`balanced`。`style` 为目录中中文名称，创建也兼容生成器旧别名；未知风格 / 枚举返回 422，WS 更新则发出错误事件。`notes` 最多 4000 字符。

前端自定义下拉菜单传递目录中的原始 `id` / `name`，不把显示标签当作新枚举；页数加减与输入共用 1–50 整数约束。控件样式变化不改变 REST / WebSocket 请求格式，服务端仍独立校验输入。

`PATCH /api/v1/account/profile` 的 `preferences` 可合并保存 `style`、`page_count`、`layout_mode`、`content_density`。用户不能指定颜色、字体路径或绘制代码。实际导出的布局选择保存在 `pages[].layout.layout_json`，包含 `layout_type`、`template_version: 3` 和 measured placeholders。PNG 与 PPTX 使用相同结构。

工作流完成时继续发送 `completed` 事件，其 `data.download_url` 指向导出文件。前端只显示下载按钮，不自动获取该文件。只有点击下载才请求私有 `/storage/…pptx`。
