# Folio 管理 API

更新：2026-10-09。统一前缀 `/api/v1/admin`。普通业务协议见 [API.md](API.md)，初始化与可写配置目录见 [DEPLOY.md](../DEPLOY.md)。

专用账号由 `folio-create-admin` 以新邮箱创建，role=admin，不提升已有用户。管理 Cookie 为 `folio_admin_session`，HttpOnly / SameSite=Strict、Path=/api/v1/admin，scope=admin；普通 Cookie / scope=user 与之不互通。普通登录拒绝管理身份，管理登录拒绝普通身份。登录需要 X-Folio-Request: 1 与允许的 Origin，限流沿用认证端点；其他接口需要管理 Cookie，写请求还需要 X-CSRF-Token。网页资料与会员等级不能修改 role。

| 方法 | 前缀下路径 | 请求 / 返回 |
|---|---|---|
| POST | `/login` | email、password（1–128 字，验证已有初始密码）；account、csrf_token 与管理 Cookie |
| GET | `/session` | account、csrf_token；无有效身份 401 |
| POST | `/logout` | 撤销当前会话 / Cookie；204 |
| POST | `/password` | current_password、new_password（10–128 字）；撤销全部管理会话并返回新会话 |
| GET | `/overview` | 真实账号、项目状态、UTC 当月 Token 与最近操作 |
| GET | `/users` | q、status=all/active/disabled、page、page_size（1–50）；分页 items |
| PATCH | `/users/{id}` | display_name、status、tier、expires_at（ISO/null）、monthly_output_limit（0/null/正整数） |
| POST | `/users/{id}/revoke-sessions` | 撤销普通用户全部会话 / WS；204 |
| POST | `/users/{id}/reset-password` | 随机 temporary_password，只返回一次，撤销会话 |
| GET | `/memberships` | items：tier、name、description、monthly_output_limit、max_pages、concurrency |
| PATCH | `/memberships/{tier}` | 完整方案除 tier 外字段；页数 1–50，并行 1–8，额度 0–1e9 |
| GET | `/config` | revision、fields、read_only；secret 字段 value 恒为空，仅报告 configured |
| PATCH | `/config` | revision（SHA256）、changes（允许配置项的字符串值）；返回新配置 |
| POST | `/provider/models` | 当前已保存连接的真实 models 目录，接口失败 502 |
| POST | `/provider/balance` | supported、available、balances、checked_at；不支持时明确 message |
| GET | `/usage` | period=YYYY-MM（UTC，默认当月）；summary、models、daily、provider_cache_hit_rate |
| GET | `/records` | kind=login/usage/generation/admin/calls、q、page、page_size；分页 items |
| GET | `/generations` | q、status（默认 all）、page、page_size；标题、邮箱、状态、页数、创建/更新时间 |

分页返回 `{items,total,page,page_size}`。用户列表只包含普通用户，不返回密码 / 会话。status、tier、display_name 不接受 null；expires_at=null 清除到期，monthly_output_limit=null 恢复方案额度、0 不限。停用撤销会话并取消制作任务；已经发送的调用仍可能产生真实用量。重置密码没有邮件发送，不允许通过用户接口修改管理员或登录邮箱。

默认普通 / Plus / Pro / Studio 分别为 50,000 / 150,000 / 500,000 / 2,000,000 月度输出 Token，20 / 35 / 50 / 50 页，单份并行 1 / 2 / 3 / 6 页。到期采用普通权益，独立额度优先；所有等级有现有导入、风格、工作空间、导出。模型请求前原子预留完整预算，不足不调用 SDK；REST / WS 校验页数，实际并行不超过全局限制。调整等级不清除当月已用量。

配置路径由 --env-file / FOLIO_ENV_FILE 指定，默认 backend/.env，浏览器不能指定路径。允许项：模型连接、API Key、默认 / 各阶段模型、温度、输出上限、并行、检查、超时、结构输出、缓存、注册开关与会话天数。字段范围由 GET /config 返回。密钥省略表示保持，显式空字符串表示清除；响应、日志不含密钥。保留无关项 / 注释并原子替换文件，应用运行环境、刷新 LLM 配置 / 连接 / 响应缓存。修订冲突 / 制作中返回 409，不可写返回 503。数据库 / 存储目录、HTTPS Cookie、Origin、监听地址保留离线管理，修改后重启。

DeepSeek 官方连接使用固定 [GET /user/balance](https://api-docs.deepseek.com/api/get-user-balance/)；balances 含 currency 与原始金额字符串 total_balance、granted_balance、topped_up_balance，不估算其他供应商余额。模型与余额请求不跟随重定向。应用额度独立于供应商余额，不按 Token 自动估计费用。

usage_ledger 新增 provider、usage_reported；旧记录缺失保持未知，未报告用量不估算。登录记录包含结果 / IP / User-Agent，操作只记录对象 / 字段名，制作阶段记录状态 / 页数。不保存提示词、模型正文、密码或密钥；启用前未采集事件不补造。管理员会话不能访问普通用户项目文件 / WebSocket。
