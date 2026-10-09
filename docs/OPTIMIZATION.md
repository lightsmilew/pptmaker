# Agent、生成费用与视觉设计优化

核查日期：2026-10-07。以下结论来自代码检查、官方资料、回归测试和一次真实的 DeepSeek 生成。实际密钥和原始材料未写入文档。

## 结论与研究依据

JSON 不是主要瓶颈。原流程让模型为每页重复输出内容、整套 master/颜色/字体/坐标和评审说明，评审失败后再输出修订计划和新布局。输出规模和串行请求次数都偏大。JSON 仍适合机器校验；应压缩字段，并把可确定的绘图工作交给代码。

- [OpenAI Latency optimization](https://developers.openai.com/api/docs/guides/latency-optimization)：减少输出 token 和请求数量、并行独立任务，是降低延迟的主要手段。
- [Anthropic Managed Agents](https://www.anthropic.com/engineering/managed-agents)：当前架构强调模型、执行环境和持久会话的分离。对这个项目的适用点是让模型组织内容，让持久项目状态保存完整材料，让工具负责绘制，而不是增加更多模型角色。
- [Anthropic Context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)：按任务取相关材料，减少无关上下文。本项目使用本地词汇检索选取长文片段，完整来源仍保存在项目中。
- [LangGraph workflows and agents](https://docs.langchain.com/oss/python/langgraph/workflows-agents)：PPT 的流程和交付物已知，适合受控工作流。这里采用规划、并行内容写作、本地排版、本地校验、有限修订，未引入额外自治循环。

这是一种针对 PPT 工作负载的选择，不能称为适用于所有任务的唯一“最先进架构”。

## 发现并修复的问题

| 问题 | 影响 | 改动 |
|---|---|---|
| 每次调用重建 SDK 客户端 | 连接复用不足 | 按角色和配置复用客户端，初始化加锁 |
| Designer 每页输出完整主题和几何 | 输出费用高、坐标不稳定 | 改为本地模板与统一主题 |
| Writer 重复标题、副标题、空字段及讲稿 | 输出冗余 | 输出 `items: [[短标题,解释]]`，本地补全；讲稿默认关闭 |
| 整篇制作指令干扰当前页 | 图表页写成另一页的表格 | 将 reference 与 page 分开，明确只生成当前页；真实调用复核 A=20、B=32 |
| deepseek-flash 默认推理 | 简单写作仍产生推理 token 和延迟 | 普通步骤默认 `reasoning_effort=none`，允许角色覆盖 |
| 评审没有发送真正图片，失败仍默认通过 | 评分与实际视觉无关 | 默认本地边界/重叠/对比度/溢出检查；可选真实图片复核，不可用时明确标记回退本地检查 |
| 修订计划被后续 Designer 覆盖，坐标没有生效 | 重试无收益 | 布局修订直接应用模板后重绘；内容问题才回到 Writer |
| LangGraph 内容修订后再次 Writer | 重复生成与计费 | 修订后直接进入 Designer |
| 每页最多多轮评审，计数重复增加 | 延迟和费用失控 | 初次检查后默认最多两次调整；优先本地测量修复，剩余内容问题才调用 Writer |
| 原生导出和 matplotlib 预览分别排版 | 换行、字号、正文不一致 | 两者使用同一份以英寸计量的 scene |
| 绘图优先 key_points，遗漏 bullet_points | 最终 PPT 缺失说明 | 保留标题与解释配对，按连续顺序分栏 |
| 图表/表格数据没有完整保存与恢复 | 预览有数据，最终导出丢失 | 保存/恢复 evidence、layout、preview、review；增加实际 PPTX 回归检查 |
| 完成消息先于导出，前端重复导出 | 下载链接尚不存在、重复工作 | 导出成功后再发送 URL；已有链接直接下载 |
| 同步 LLM 节点阻塞异步服务器 | 等待期间连接不响应 | 节点放入线程、命令按顺序排队，ping 独立响应 |

默认 WebSocket 路径的请求数约为 `2 + 需要写正文的页数`：Parser 和 Planner 各一次，封面/目录/结束页无需 Writer。格式修复或内容修订会增加请求；启用 vision 会增加图片复核。备用 LangGraph 入口仍保留全局语义复核，因此其请求数可能多一次，不能混用两条路径的统计。

## Token 与缓存

Writer 的预算为 1000 token（文字页）或 1400（图表/表格页），Parser 为 650，图片复核为 650。Planner 按 `max(2200, 页数 × 240)` 分配上限；大纲不再强制输出副标题与目的描述。`OPENAI_MAX_TOKENS` / `ANTHROPIC_MAX_TOKENS` 是这些预算的总上限，不是要求模型每次用完；示例设置 12000 是为允许 50 页大纲，普通写作仍只允许 1000/1400。

缓存有两层，指标必须区分：

1. 供应商前缀缓存：系统提示、共用主题和原文放在页面变量之前。DeepSeek 的 `prompt_cache_hit_tokens` 与 OpenAI 的 `cached_tokens` 都会被读取。命中率为缓存输入 token / 全部输入 token。
2. 进程内响应缓存：相同请求直接复用结果，10 分钟 TTL、最多 128 条、每条最多 64 KiB，键包含配置、模型、凭据的哈希、输入与有效参数。内容修订不走此缓存；截断输出不缓存。

[OpenAI Prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching) 和 [DeepSeek Context caching](https://api-docs.deepseek.com/guides/kv_cache/) 都依赖可复用的输入前缀。缓存降低的是输入成本；不能抵消重复生成的输出费用。短输入、首次请求、不同内容/模型和过期都会影响命中，不能保证高比例，也不应该为了命中而填充无意义文本。

对 DeepSeek 的推理默认与控制方式，参考 [Thinking mode](https://api-docs.deepseek.com/guides/thinking_mode/) 和 [Chat completion API](https://api-docs.deepseek.com/api/create-chat-completion/)。关闭推理适用于这里普通的内容改写和结构提取；复杂推导可单独为 Planner 打开。

```dotenv
PPT_CONCURRENCY=3
PPT_MAX_REVIEW_ROUNDS=2
PPT_REVIEW_MODE=local
DEEPSEEK_REASONING_EFFORT=none
LLM_JSON_MODE=auto
# 可选：仅对规划使用更强模型或推理
# OPENAI_PLANNER_MODEL=deepseek-v4-pro
# DEEPSEEK_PLANNER_EFFORT=low
```

JSON mode 自动用于官方 OpenAI 和 DeepSeek；其他兼容网关需设置 `LLM_JSON_MODE=on` 确认支持。OpenAI 的 `LLM_PROMPT_CACHE_KEY=on`、Anthropic 的 `ANTHROPIC_PROMPT_CACHE=on` 是可选能力开关，默认关闭以兼容不同网关。配置见 `backend/.env.example`，没有修改你的实际密钥文件；环境变更需重启后端。

查看项目诊断：`GET /api/v1/llm/usage?project_id=项目ID`，保留当前进程最近 2000 次调用，重启会重置。个人中心使用 `GET /api/v1/account/usage` 的 SQLite 持久账本，按 UTC 月份统计，重启后仍可读取；均不保存提示、内容或密钥。`duration_ms` 为调用时长之和，含并行调用，不能当成项目墙钟时间。

## PPT 与主页设计

参考 [Pitch templates](https://pitch.com/templates/) 的 editorial/minimal 模板方向，以及 [Pitch slide styles](https://help.pitch.com/en/articles/4059534-create-your-own-slide-style) 的统一字体/颜色/层级原则。实现采用自己的模板，没有复制或打包第三方收费模板。

`slide_scene.py` 集中管理画布、配色、文字测量、换行、标题层级和单/双/三栏、封面、图表、表格。主题包括商务简约、学术简约、科技风等六种。默认纸白与墨绿，深色主题修正为浅色正文，减少高饱和背景、装饰和卡片堆叠。表格下方保留重点解释；没有真实图表数据时改用完整文字版式。

`pptx_generator.py` 将 scene 导出为可编辑的文本、形状、原生图表和表格；`preview_renderer.py` 从同一 scene 生成 1600×900 PNG。文字使用相同换行和位置，但 PowerPoint 的字体替换、原生图表坐标轴与表格细节可能不同。当前环境已核对 PNG 与 PPTX 内容/对象结构，未通过 Office 或 LibreOffice 对最终 PPTX 做逐页渲染。外部 PPTX 母版导入尚未支持，会明确报错。

主页参考 [Linear 的界面重设计](https://linear.app/now/how-we-redesigned-the-linear-ui) 的低噪声、层级和一致排布原则，复现为纸白工作台、浅灰绿侧栏、简洁导航、文档输入区和可选模板样张。设置、上传、示例和风格选择接入真实逻辑；没有装饰性的假入口。桌面与 390px 手机视口已检查，手机布局没有水平溢出。生成过程中只挂载选中页的完整预览，用户可通过页列表选择当前页面。

输入内容、上传记录和设置使用同一份草稿状态，切换到设置再返回时不会丢失已写内容。增加了切换设置并实际提交页数/风格的前端回归测试。

运行 `python scripts/preview_styles.py` 可在不调用 API 的情况下生成三套 4 页可编辑 PPTX 与样张，输出在 `storage/design_samples/`。

## 验证记录

- 原优化轮回归：后端 288 项通过；两个原有调试测试返回 bool 的 warning 仍存在。测试 SQLite 与临时文件隔离，不写入实际项目历史。
- 原优化轮回归：前端 80 项通过；`npm run build` 成功。
- 最终真实生成：4 页，墙钟时间 8.0 秒、5 次 LLM 调用、2741 输入 token、862 输出 token、0 推理 token、768 缓存输入 token，输入缓存命中率约 28.0%，PPTX 下载 HTTP 200。实际 PPTX 包含 1 个原生图表和 1 个原生表格，图表系列数值确认为 `[20,32]`。
- 最终记录位于 `storage/design_samples/final-live-verification.json`。供应商已见过部分相同测试材料，因此这次不是全冷缓存测试；较早冷请求为 902 输出 token、5.7% 输入缓存命中，记录在 `live-usage.json`。两次提示和材料不同，不能据此宣称优化前后费用、速度或缓存改善百分比，也不能把 8.0 秒当作所有任务的耗时保证。
- 本地检查分数反映检测到的几何问题，不是审美评分或事实校验。前端已明确标为“排版检查”，图片复核另标为“视觉复核”。

## Folio 品牌与工作空间更新

以下为上一轮本地身份版本的历史验收。本轮现行版本已经改为服务端多用户，接口与部署以 README / API / DEPLOY 为准。

产品已重命名为 Folio，主标题为 “Folio — Let your ideas unfold.”，三页形 Logo 与 favicon 统一。设置、历史、个人中心和演示预览全部复用主页的纸白 / 墨绿布局，未来页面规则写入 `docs/DESIGN_SYSTEM.md` 和 `AGENTS.md`。

历史列表只请求摘要，按需获取完整正文；打开旧 planned 项目不会自动生成，恢复 completed 项目不会自动下载。移除逐页成功 toast，修复旧 WebSocket 消息污染新项目、部分 state_patch 被完整替换以及切换项目后复用旧下载链接的问题。服务重启后将未结束的任务标为可重试。

本地账号持久化资料与默认偏好；会员由服务配置，资料接口禁止提权。输出预算在 SDK 调用之前通过 SQLite 原子预留，并行调用不能超分配，按实际结果结算。预算不代表第三方余额。

本轮真实 4 页 Folio 演示：6 次调用、3235 输入 Tokens、949 输出 Tokens；个人中心持久账本中的输出也是 949，已导出可编辑 PPTX。记录在 `storage/design_samples/folio-live-verification.json`。材料不同，不能与原实测直接计算改善百分比。

最终本轮回归：后端 307 项、前端 85 项通过，前端生产构建成功。桌面与 390px 手机已检查四个业务页，未见水平溢出；已验证搜索、收藏、归档、恢复，以及后端重启后历史与账本保留。截图在 `storage/design_samples/folio-*.png`。

## 服务端多用户与公开首页（2026-10-08）

公开首页独立于登录后工作台，包含产品说明、主题样张、三步流程、场景、FAQ 与登录 / 注册。产品仍沿用纸白、浅灰绿与墨绿，不添加虚构评价或增长数字。

服务端保存唯一邮箱用户、随机盐密码散列、可撤销 Cookie 会话、资料与偏好；REST、WebSocket、PNG / PPTX 和参考文件都验证归属。用量、预算预留和进程内结果缓存按用户隔离，生成线程继承项目用户上下文。工作台可将文档拖入页面任意位置，原文件和提取文本保存在后端。

独立真实验收：两页、2 次调用、440 输出 Tokens，另一个账号用量为 0；重启后资料、附件、演示和账本保留，其他账号下载为 404。此例只有封面与目录，不据此计算普通正文演示的成本。最终后端 320 项、前端 91 项通过，生产构建成功。细节见 TESTING，现行 API / 部署以对应文档为准。
