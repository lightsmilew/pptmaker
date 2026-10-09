# Folio 测试与验收

更新：2026-10-09。测试命令从对应 backend / frontend 目录执行。自动测试默认使用模拟模型，不应触发真实付费调用。

## 自动回归

```powershell
# backend
python -m pip install -e ".[dev]"
python -m pytest -q -p no:cacheprovider
# frontend
npm ci
npm test
npm run build
```

backend 的 pytest 启动时为 `FOLIO_DB` 和兼容 `PPTMAKER_DB` 指定唯一测试数据库，并把临时产物放到 `backend/storage/test-runs/`，不会修改实际历史。账号测试另使用独立临时账本。测试缓存在部分 Windows 环境权限受限，可用 `-p no:cacheprovider` 避免写入原 `.pytest_cache`。

当前回归覆盖：

- 内容结构与 JSON 合约、模型配置、Parser / Planner / Writer、受控修订与工作流编译。
- 共享 slide scene 的换行、几何、深色主题、PNG 与 PPTX 内容，以及可编辑图表和表格。
- WebSocket 命令顺序、状态广播、完整失败表达与有效导出。
- 草稿跨页面保留、页数 / 主题提交、共享侧栏导航、账号资料保存后更新身份。
- 历史读取不自动生成、搜索 / 收藏 / 归档 / 恢复 / 分页、有效文件链接、重启中断恢复。
- 账号和偏好持久化、输入校验、VIP 字段不可由资料 API 提权、会员到期。
- 用量幂等记录、重启后统计、原子并发预算预留、额度不足时 SDK 未被调用。

多用户版本还需覆盖真实 Cookie 会话、CSRF / Origin 校验、双账号的 REST / WebSocket / 文件隔离、附件归属、独立用量与并发额度、服务重载后的资料 / 会话 / 账本 / 项目保留，以及公开页登录、退出与页面任意位置文件拖放。不能仅用样式测试代替功能验收。

## 浏览器验收

启动前后端，访问 http://127.0.0.1:5173 。

1. 主页输入一段内容，切换设置，修改页数 / 主题 / 目录开关，再返回；正文与设置保留。
2. 点击保存为默认值，刷新后默认主题和页数保留；其他会话选项不宣称持久。
3. 创建演示后显示同一侧栏、纸白 / 墨绿控件、紧凑进度与页列表；过程不弹出每页一条成功提示。
4. 已生成页有 16:9 预览；正文、备注可查看；上一页 / 下一页可切换。导出完成有下载按钮，只有点击按钮才下载。
5. 工作空间显示真实历史，搜索标题 / 标签、收藏、分页、归档后恢复；打开或刷新已完成演示不会新调用模型。
6. 个人中心保存称呼 / 邮箱 / 机构，刷新后保留；用量来自后台，空用量明确表示尚无记录。
7. 会员状态和有效期按环境配置显示；不能在浏览器资料表单中自授 VIP。
8. 后端设置小于一次步骤预算的 `FOLIO_MONTHLY_OUTPUT_LIMIT`，只在隔离测试环境验证请求被拒绝；不要改动实际账号来跑额度测试。
9. 检查 1440px 桌面和 390px 手机：无水平溢出，菜单可开关，长标题不挤出按钮，表单标签和键盘焦点可见。
10. 有排版建议时先自动调整；达到调整上限后仍能下载，展开逐页问题并点击“继续调整问题页”，已完成且通过的页面应保留。检查建议与实际生成错误分开显示；视觉复核回退时不得显示视觉通过。

临时改动的测试资料 / 收藏状态 / 默认偏好应恢复。真实生成的验收项目可以留在历史中供复查。

## 不调用模型的样张

在仓库根目录运行：

```powershell
python scripts/preview_styles.py
```

产物位于 `storage/design_samples/`，提供全部 16 种风格的可编辑 PPTX 与 PNG。检查文字是否裁切、正文顺序、颜色对比、图表 / 表格对象。当前 PNG 是共享场景预览，未通过 Office / LibreOffice 对所有最终 PPTX 做逐页渲染；不同字体环境仍可能产生差异。

## 真实生成与用量记录

真实验收会使用 `.env` 的模型并产生费用。只使用无敏感数据的短材料，生成小型演示，记录项目 ID、墙钟时间、实际 SDK Token、缓存输入、有效下载和 PPTX 对象。不能把单次示例的速度或缓存比例当成普遍保证。

已有研究验证：`storage/design_samples/final-live-verification.json`，4 页、8.0 秒、5 次调用、862 输出 Tokens，含真实原生图表与表格。

本轮品牌与账号验证：`storage/design_samples/folio-live-verification.json`，4 页，6 次调用，949 输出 Tokens、3235 输入 Tokens；账号持久账本记录同样的 949 输出 Tokens，PPTX 已生成且可下载。重启后账本仍为 949 输出 Tokens，打开 / 刷新历史项目未产生新调用，文件下载 HTTP 200。

截图保存在 `storage/design_samples/folio-*.png`，包括设置、工作空间、演示与个人中心的桌面和手机视图。该目录按默认规则不提交 Git。

## 多用户版本最终验收（2026-10-08）

后端 **320 项**、前端 **91 项**通过，生产构建成功。后端 API 测试使用真实 Cookie 与 CSRF，没有绕过认证；账号 / 附件 / 历史测试均使用独立数据库与临时文件目录。

浏览器检查了 1440px 桌面与 390px 手机公开首页、注册、工作台、演示预览与个人中心；已验证注册自动登录、文档选择上传、真实两页生成、私有预览 / 下载、第二账号空历史与他人项目 404、退出后另一标签页同步回到登录。任意页面位置拖放、文件校验和文本拖拽不受影响，由 `AuthAndDrop.test.tsx` 验证；没有声称用浏览器工具从系统文件管理器完成原生拖拽。

独立验收库 `backend/storage/browser-auth-verification.sqlite3`，文件目录 `backend/storage/browser-auth-assets`；账号仅用于本次验证。真实两页生成 2 次调用、440 输出 Tokens，重启后保留同样账本、附件和项目，另一个用户为 0 调用 / 0 输出，不能下载该项目。记录为 `storage/design_samples/folio-auth-live-verification.json`。管理员脚本也已验证仅修改指定用户的 VIP 和 500 Tokens 预算。

截图：`folio-public-desktop.png`、`folio-register-mobile.png`、`folio-server-account-desktop.png`，位于 `storage/design_samples/`。完成后本地预览恢复默认数据库，验收账号与产物不进入默认工作空间。按用户要求未迁移旧共享账号数据。

## 原有测试警告

两个原有调试用例返回 bool，pytest 会报告 `PytestReturnNotNoneWarning`；另外本机 requests 依赖组合会给出版本提示。这些不是本轮功能失败，但不应据此声称整个环境毫无警告。

## 创作方案与多样布局验收（2026-10-08）

后端 **343 项**通过，前端 **94 项**通过，生产构建成功。新增覆盖 16 种风格 × 四种编排的文本保留 / 对比 / 几何检查、语义优先、相邻通用页面变化、并行单页任务的整篇页序、原生可编辑 PPTX、额外模型分组合并、密度预算、设计目录认证、默认偏好和非法枚举。前端验证方案选项带入创建、默认方案保存、只有点击下载按钮才下载、重试清除旧错误。

`scripts/preview_styles.py` 生成全部 16 种风格的 PNG / PPTX 样张，无模型调用；已查看不同封面与内容结构。浏览器检查 1440px 桌面和 390px 手机创作方案、公开首页、工作台和真实六页演示。手机文档宽 382px，小于 390px 视口，没有横向溢出。

真实验收使用独立数据库 `backend/storage/browser-design-verification.sqlite3` 与独立文件目录。演示 `proj_eca187f3cc9f` 在模型返回超过原上限的 6 组内容后先失败，保留式合并修复后重试成功；六页分别使用 cover / timeline / cards_grid / timeline / three_column / cover，原生导出文字完整，点击按钮下载成功（HTTP 200）。该账号实际累计 10 次调用、1479 输出 Tokens，包含首次失败和重试；这不是正常生成成本基准。记录在 `storage/design_samples/folio-direction-live-verification.json`，不含凭据。

README 截图位于可提交的 `docs/images/`，均为独立验收账号的真实界面；`creative-direction-mobile.png` 为手机全页。完成后恢复默认预览数据库。不会在界面宣传服务端持久存储；对应技术说明只留在文档。

## 统一表单控件验收（2026-10-08）

前端 **99 项**通过，生产构建成功。`Controls.test.tsx` 验证自定义下拉菜单的键盘选择、Esc、焦点返回、禁用选项、表单值，以及数字控件的加减、上下限、空值编辑、失焦校正、禁用 / 只读和小数步长；页面集成测试验证目录枚举进入创建请求与默认方案。

浏览器在独立验收库和端口检查 1440px 桌面与 390px 手机：受众菜单长列表滚动，内容密度、排序和时区菜单的展开 / 选中，页数鼠标加减、1–50 上限禁用、上下键步进，以及工作台紧凑按钮。手机菜单位于视口内，工作台没有横向溢出。使用已有验收账号，未修改实际账号资料、会员或默认方案，本轮没有调用模型。

截图更新到 README 的 `workbench.png`、`creative-direction.png`、`creative-direction-mobile.png`；`folio-controls-desktop.png` / `folio-controls-mobile.png` 展示展开态。后端契约不变，额外验收服务在完成后关闭，用户原有服务保留。

## 检查建议与生成恢复验收（2026-10-09）

后端 **351 项**、前端 **100 项**通过，生产构建成功。`test_review_recovery.py` 验证初次检查后两次调整、短暂降分不会提前结束、调整失败恢复上一版、残留建议仍导出完整可编辑 PPTX、首次写作错误如实失败、重试跳过已通过页面，以及显式 force 重新制作全部页面。视觉不可用时明确标记本地检查回退；备用图工作流也保留真实建议而完成可用页面。

接口用例使用隔离数据库、真实 Cookie / CSRF / Origin：带建议的完成项目可从 REST 恢复，私有 PNG 和 PPTX 返回成功；旧流程因检查建议而标成失败的项目，可通过认证 WebSocket 复用页面继续复查，完成后清除错误和已解决的建议且没有额外写作调用。手动 `trigger_review` 保持可用页面完成状态并保存 / 广播警告。前端用例验证下载按钮保留、建议按需展开、“继续调整问题页”发送生成命令，且不会自动下载。

本轮未调用真实模型；独立界面验收示例仅模拟内容 / 视觉反馈，PNG / PPTX 由真实绘制与导出代码生成。浏览器控制工具启动失败，重置后仍不可用，因此本次新增提示区的 1440px 桌面和 390px 手机人工复查尚未完成，未新增截图，也未把先前页面截图当成本次验收证据。已有测试警告见上文。

## 后端编排与真实调用验收（2026-10-09）

后端 **362 项**、前端 **102 项**通过，生产构建成功。新增回归覆盖后端选择剩余步骤、前一步失败停止、完成文件复用 / 丢失后重新导出、重复提交避免重复写作、任务脱离连接运行，以及后台任务的事件广播。前端验证只提交一次 `run_workflow`、不自行改写生成状态或统计完成数、采用实际预览尺寸 / 时间、失效下载链接清除，以及文档独立列表与仅附件创建；表单和导航仍是前端界面职责。

真实模型验收使用隔离数据库 `backend/storage/browser-workflow-verification-1009.sqlite3` 与独立产物目录，不改动实际账号。演示 `proj_0cfdd72a38c7` 四页，11.96 秒，5 次调用，2699 输入 / **817 输出 Tokens**，供应商报告 384 缓存输入 Tokens。只发送一条 `run_workflow`，在 parsing 时主动断开 WebSocket；后端仍完成所有页面，PNG / PPTX 下载均为 HTTP 200，重连恢复下载链接，再次继续未新增调用或 Tokens。重复附件 ID 只组装一次，另一个账号读取演示和下载文件均为 404。

已直接查看四张真实 PNG：cover / cards_grid / timeline / stacked_rows，未见文字裁切或重叠；PPTX 对象验证四页存在。这里只验证共享预览及可编辑对象，没有使用 Office 逐页渲染，也没有以本地几何 100 分宣称审美或事实质量。记录和产物位于 `storage/design_samples/folio-server-workflow-live-verification.json`、`folio-server-workflow-live.pptx`、`folio-server-workflow-page-*.png`；记录不含凭据。

本轮同时尝试浏览器验收工具与 computer-use 的 Windows `@oai/sky` 入口，二者在执行初始化代码前均报告 `trusted Node process exited unexpectedly; kernel reset, rerun your request`；分别重置后仍失败。因而网页桌面 / 手机的真实视觉和原生点击验收仍未完成，未用静态样张或 DOM 单元测试冒充浏览器截图；需要恢复工具运行时后补验。上面的真实生成验证通过 HTTP / WebSocket 完成。
