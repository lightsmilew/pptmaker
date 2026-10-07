# Folio API 与事件协议

更新：2026-10-07。开发 API 位于 `http://127.0.0.1:8000`；Vite 前端通过同源代理访问。接口没有公网用户鉴权，每个服务实例共享本地身份。服务运行时的 OpenAPI `/docs` 为字段约束的权威来源。

## REST

### 创建项目

`POST /api/v1/projects`

```json
{
  "spec": {"topic":"季度研究报告","page_count":8,"style":"学术简约","audience":"研究生","needs_cover":true,"needs_toc":true,"needs_summary":true,"needs_chart":false},
  "user_input":"参考内容与制作要求"
}
```

`spec`、`user_input`、`uploaded_files` 可选。创建页数必须是 1–50 的整数。`spec` 未提供时采用本地账号默认风格和页数。返回完整项目初始快照（HTTP 200），不会仅因为创建就调用模型。

快照主要字段：`id`、`spec`、`user_input`、`status`、`current_step`、`progress`、`error`、`outline`、`pages`、`workflow`、`created_at`、`updated_at`。页面保存 `content`（标题、副标题、短标题/说明、图表/表格、备注）、`layout`、`preview`、`review`、`status`、`iteration` 等。

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

返回 `filename`、`content`、`content_preview`（前 500 字）。非支持格式、超限和损坏文档返回 400；该接口不会自动创建项目。PDF 为文本提取，无 OCR。

### 个人中心

`GET /api/v1/account` 返回四部分：

- `profile`：`account_id`、`display_name`、`email`、`company`、`occupation`、`bio`、`timezone`、`created_at`、`updated_at`（保存后）和 `preferences`。
- `membership`：`tier`、`name`、`is_vip`、`status`、`expires_at`、`managed_by`、`billing_mode`、`features`、`limits`。
- `usage`：持久化月度统计，字段见下文。
- `account`：`mode=local`、`status=active`、`email_verified=false`、`provider_host`、`model`、`provider_connected`、`authentication=local_workspace`。只返回主机名，不返回密钥或带凭据的 URL。

`PATCH /api/v1/account/profile` 允许：

```json
{"display_name":"创作者","email":"author@example.com","company":"工作室","occupation":"研究员","bio":"关注清晰表达。","timezone":"Asia/Shanghai","preferences":{"style":"学术简约","page_count":8}}
```

称呼 1–40 字且不能纯空白，邮箱至多 254 字且校验格式，机构 80 字、职业 60 字、简介 200 字。时区允许上海、UTC、东京、伦敦、纽约对应的 IANA 名称。偏好允许六种风格、1–50 页、语言标记 `zh-CN` / `en`；语言标记目前仅存储，不提供完整英文界面。嵌套偏好按字段合并。

禁止通过资料接口更改 `account_id`、`created_at`、VIP、会员额度等；未知字段返回 422。返回更新后的完整 account view。

`GET /api/v1/account/membership` 返回会员部分；状态由环境 `FOLIO_MEMBERSHIP`、`FOLIO_MEMBERSHIP_EXPIRES_AT` 配置，已到期 Plus 不再有 VIP 标记。目前两档均保留基础本地创作权益，没有会员购买接口。

`GET /api/v1/account/usage` 返回：

```json
{
  "period":"2026-10","period_start":"2026-10-01T00:00:00+00:00","resets_at":"2026-11-01T00:00:00+00:00",
  "calls":0,"lifetime_calls":0,"input_tokens":0,"output_tokens":0,"cached_input_tokens":0,
  "reasoning_tokens":0,"successful_calls":0,"response_cache_hits":0,"duration_ms":0,
  "provider_cache_hit_rate":null,"daily":[],
  "quota":{"unit":"output_tokens","limit":null,"used":0,"reserved":0,"remaining":null,"source":"local_budget","is_unlimited":true}
}
```

`daily` 条目含 `date`、`output_tokens`、`calls`，只列有记录的 UTC 日期。供应商输入缓存比例为 cached/input，没有输入时为 null；进程内响应缓存命中单独计数。调用数包含失败与结果缓存命中，成功数包括成功复用。账本从启用功能后累计，不回填旧进程的记录。

`FOLIO_MONTHLY_OUTPUT_LIMIT` 为本地输出预算，默认不限。每次模型请求原子预留完整步骤预算，返回后结算实际输出；不足时抛出额度错误并且不调用 SDK。模型未报告的计数按可获取信息记录，无法据此查询服务商实际余额。

### 诊断与文件

`GET /api/v1/llm/usage?project_id={id}` 是当前进程最近 2000 次调用的诊断视图；`recent_calls` 最多 100 条。和持久化账号账本不同，重启会清空此诊断窗口。`duration_ms` 为各调用时长之和，不是并行项目墙钟时间。

`GET /storage/{project_id}.pptx` 下载；`GET /storage/previews/{project_id}/{page_id}/iteration-01.png` 等路径读取预览。接口返回的实际路径为准。`GET /health` 返回健康状态；`GET /` 返回 Folio Studio 服务信息。

## WebSocket

连接 `/ws/{project_id}`，服务器首先发送 `initial_state`。消息格式均为 JSON：

```json
{"type":"plan_outline","data":{}}
```

| 客户端命令 | `data` | 行为 |
|---|---|---|
| `parse_input` | 可省略 | 解析原文，保留明确表单设置 |
| `plan_outline` | 可省略 | 生成大纲与待制作页面 |
| `generate_parallel` | 可省略 | 并行写作、设计、检查、有限修订并导出 |
| `render_pptx` | 可省略 | 从当前页面重新导出，不重新写作 |
| `update_spec` | `{"patch":{…}}` | 修改当前项目配置 |
| `update_page` | `{"page_id":"page-01","patch":{…}}` | 修改页数据并标记 editing；需重新导出，旧 PNG 不自动重绘 |
| `trigger_review` | `{"page_id":"page-01"}` | 按配置检查指定页 |
| `delete_project` | 可省略 | 删除项目记录，永久操作；网页未提供该入口 |
| `ping` | 可省略 | 返回 pong，不等待生成队列 |

网页自动顺序为创建 → 连接 → parse → plan → 收到 planned 后 generate。恢复历史 planned 状态时需用户点击继续制作，不自动发送 generate。

| 服务端事件 | 主要内容 |
|---|---|
| `initial_state` | 完整项目快照 |
| `state_patch` | 全量或部分项目字段，客户端合并 |
| `progress` | `step`、`progress`、`message` |
| `parallel_status` | 总页数、完成数、失败数、页状态映射 |
| `page_updated` | `page_id`、`status`、`iteration`、可选 preview / review |
| `preview_ready` | `page_id`、`image_path`、`iteration` |
| `review_completed` | `page_id`、`method`、`status`、`score`、`issues`、`suggestions` |
| `completed` | 成功导出后的 `download_url` |
| `error` | `message` |
| `pong` | 时间戳 |

项目状态包含 idle、parsing、parsed、planning、planned、generating、reviewing、rendering、editing、completed、failed。页面状态包含 pending、writing、designing、rendering、reviewing、revising、completed、failed。

同一连接的工作命令排队执行，断开后前端会重连；连接关闭会取消当前制作并将未完成任务标为可重试（尚未实现脱离连接的后台任务）；持久快照用于恢复展示，后台不提供多实例任务协调。服务重启时未结束的制作转为 failed，可显式重试。
