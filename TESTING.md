# Folio 测试与验收

更新：2026-10-07。测试命令从对应 backend / frontend 目录执行。自动测试默认使用模拟模型，不应触发真实付费调用。

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

本轮最终回归：后端 307 项、前端 85 项通过，`npm run build` 成功。数量随功能增加变化，不用测试数本身代替功能验收。

## 浏览器验收

启动前后端，访问 http://127.0.0.1:5173 。

1. 主页输入一段内容，切换设置，修改页数 / 主题 / 目录开关，再返回；正文与设置保留。
2. 点击保存为默认值，刷新后默认主题和页数保留；其他会话选项不宣称持久。
3. 创建演示后显示同一侧栏、纸白 / 墨绿控件、紧凑进度与页列表；过程不弹出每页一条成功提示。
4. 已生成页有 16:9 预览；正文、备注可查看；上一页 / 下一页可切换。导出完成有下载按钮，新创建任务自动下载一次。
5. 工作空间显示真实历史，搜索标题 / 标签、收藏、分页、归档后恢复；打开或刷新已完成演示不会新调用模型。
6. 个人中心保存称呼 / 邮箱 / 机构，刷新后保留；用量来自后台，空用量明确表示尚无记录。
7. 会员状态和有效期按环境配置显示；不能在浏览器资料表单中自授 VIP。
8. 后端设置小于一次步骤预算的 `FOLIO_MONTHLY_OUTPUT_LIMIT`，只在隔离测试环境验证请求被拒绝；不要改动实际账号来跑额度测试。
9. 检查 1440px 桌面和 390px 手机：无水平溢出，菜单可开关，长标题不挤出按钮，表单标签和键盘焦点可见。

临时改动的测试资料 / 收藏状态 / 默认偏好应恢复。真实生成的验收项目可以留在历史中供复查。

## 不调用模型的样张

在仓库根目录运行：

```powershell
python scripts/preview_styles.py
```

产物位于 `storage/design_samples/`，提供商务简约、学术简约、科技风的可编辑 PPTX 与 PNG。检查文字是否裁切、正文顺序、颜色对比、图表 / 表格对象。当前 PNG 是共享场景预览，未通过 Office / LibreOffice 对所有最终 PPTX 做逐页渲染；不同字体环境仍可能产生差异。

## 真实生成与用量记录

真实验收会使用 `.env` 的模型并产生费用。只使用无敏感数据的短材料，生成小型演示，记录项目 ID、墙钟时间、实际 SDK Token、缓存输入、有效下载和 PPTX 对象。不能把单次示例的速度或缓存比例当成普遍保证。

已有研究验证：`storage/design_samples/final-live-verification.json`，4 页、8.0 秒、5 次调用、862 输出 Tokens，含真实原生图表与表格。

本轮品牌与账号验证：`storage/design_samples/folio-live-verification.json`，4 页，6 次调用，949 输出 Tokens、3235 输入 Tokens；账号持久账本记录同样的 949 输出 Tokens，PPTX 已生成且可下载。重启后账本仍为 949 输出 Tokens，打开 / 刷新历史项目未产生新调用，文件下载 HTTP 200。

截图保存在 `storage/design_samples/folio-*.png`，包括设置、工作空间、演示与个人中心的桌面和手机视图。该目录按默认规则不提交 Git。

## 已知测试警告

两个原有调试用例返回 bool，pytest 会报告 `PytestReturnNotNoneWarning`；另外本机 requests 依赖组合会给出版本提示。这些不是本轮功能失败，但不应据此声称整个环境毫无警告。
