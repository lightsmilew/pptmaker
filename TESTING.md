# 测试文档 (Testing Guide)

本项目使用前后端分离的测试策略，保证整个生成流程的健壮性。

## 概览

| 套件 | 框架 | 数量 | 入口 |
|------|------|------|------|
| 后端单元/契约/集成 | `pytest` + `pytest-asyncio` | 261 | `backend/tests/` |
| 前端单元/组件 | `vitest` + `@testing-library/react` | 110 | `frontend/src/__tests__/` |
| **总计** | — | **371** | — |

---

## 后端测试

### 目录结构

```
backend/tests/
├── conftest.py                 # 共享 fixtures (MockLLMClient, temp storage, sample specs)
├── contracts/                  # JSON 处理、Schema、Validator、StructuredLLM、Errors
│   ├── test_json_utils.py
│   ├── test_schemas.py
│   ├── test_validators.py
│   ├── test_structured_llm.py
│   └── test_errors.py
├── models/                     # 数据模型
│   ├── test_project.py
│   ├── test_page.py
│   ├── test_iteration.py
│   └── test_review.py
├── agent/                      # Agent 节点 (parser / planner / writer / designer / critic / finalizer)
│   ├── test_state_v2.py
│   └── nodes/
│       ├── test_parser.py
│       ├── test_planner.py
│       ├── test_writer.py
│       ├── test_designer.py
│       ├── test_preview_critic.py
│       └── test_revision_finalize_global.py
├── api/                        # REST API & WebSocket
│   ├── test_memory.py
│   ├── test_routes.py
│   └── test_websocket.py
└── integration/                # 端到端 + LangGraph
    ├── test_e2e_flow.py
    └── test_graph.py
```

### 关键覆盖点

- **JSON 解析与校验**：`extract_json_from_text` / `parse_llm_json` / 严格 Pydantic 校验
- **LangGraph 状态机**：`create_initial_state` / `route_page_review` / `route_after_finalize` / 迭代回路
- **并行生成**：批量 `page_updated` 事件 → 状态合并 → 进度计算
- **REST API**：projects CRUD、parse / plan / generate-parallel、render、templates、LLM config
- **WebSocket**：`ConnectionManager` 与 `page_updated` / `preview_ready` / `review_completed` 广播
- **画布语义校验**：13.333"×7.5" 边界、字号范围、颜色阈值
- **评审打分**：score ≥ 85 通过、revisions、priority 分级

### 运行

```bash
cd backend
pip install -r requirements.txt
pytest                     # 全部测试
pytest -m unit             # 仅单元测试
pytest tests/integration/  # 仅集成
pytest -k "parser"         # 按名称过滤
pytest --cov=app           # 覆盖率报告
```

### Mock LLM 模式

`conftest.py` 提供了 `MockLLMClient` 与 `mock_llm_with_responses` fixture，按调用顺序返回预设 JSON：

```python
def test_parser(mock_llm_with_responses):
    mock_llm_with_responses([{"topic": "AI", "page_count": 6}])
    state = parser_node(build_state())
    assert state["requirements"]["topic"] == "AI"
```

由于子节点使用 `from ...llm import get_llm_client` 本地导入，fixture 同时打补丁 `app.llm.get_llm_client` 与各 `app.agent.nodes.*.get_llm_client`，保证所有调用都命中 mock。

---

## 前端测试

### 目录结构

```
frontend/src/
├── test/
│   └── setup.ts              # jsdom 初始化、@testing-library/jest-dom
└── __tests__/
    ├── client.test.ts         # API 客户端：所有 REST 端点、上传、错误处理
    ├── projectStore.test.ts   # Zustand 状态机：actions、并行状态、WebSocket 事件
    └── PPTPreview.test.tsx    # 组件：Preview / Thumbnail / ParallelProgress
```

### 关键覆盖点

- **API 客户端**：
  - 所有 REST 端点（projects / pages / generate / render / templates / LLM config / upload）
  - 请求体序列化、Header 设置、错误回退 (`detail` 字段 / 通用 `Request failed` / HTTP status)
  - `getDownloadUrl` / `getPreviewUrl` (with/without iteration)
  - `createWebSocket` (`ws://` vs `wss://` 协议选择)
- **Zustand 状态机**：
  - `createProject` / `loadProject` / `updateSpec` / `parseInput` / `generatePlan` / `generatePPT` / `generatePPTParallel` / `updatePage` / `renderPPTX`
  - `updatePageFromEvent` 模拟 WebSocket `page_updated` 事件 → 状态合并 + 进度计算
  - 并行状态初始化与失败计数
  - `setStatus` / `setError` / `clearProject` 同步操作
  - `useExamples` 示例项目元数据完整性
- **组件 (PPTPreview)**：
  - 空状态占位符、`title` / `subtitle` / `key_points` / `bullet_points` 内容渲染
  - 旧字段兼容 (`page.title` / `page.content?.title`)
  - 状态徽章颜色（≥85 绿 / ≥70 黄 / 其它红）
  - 迭代徽章 (`iteration > 1` 时显示)
  - 预览图片加载、Windows 路径转 URL、显示开关
  - 评审问题分严重度染色、20 字符截断、`+N more` 溢出
  - `SlideThumbnail` 状态边框、激活环、✓/✗ 标记、评分角标
  - `ParallelGenerationProgress` 进度条、网格单元、失败指示

### 运行

```bash
cd frontend
npm install
npm test                  # 一次性运行
npm run test:watch        # 监听模式
npm run test:coverage     # 覆盖率报告
```

### Mock 模式

`@/api/client` 通过 `vi.mock` 完全替换，测试中所有 store action 触发的网络请求都被截获：

```ts
vi.mock('@/api/client', () => ({
  api: { /* mock 方法 */ },
}));

mockedApi.generatePPTParallel.mockResolvedValueOnce({
  message: 'started', project_id: 'p1', parallel: true, page_count: 4,
});
```

---

## CI 集成建议

```yaml
# .github/workflows/test.yml (示例)
- name: Backend tests
  run: |
    cd backend
    pip install -r requirements.txt
    pytest --tb=short

- name: Frontend tests
  run: |
    cd frontend
    npm ci
    npm test
```

## 添加新测试

### 后端
1. 选择合适子目录（`contracts/` / `models/` / `agent/nodes/` / `api/` / `integration/`）
2. 复用 `conftest.py` 中的 fixture (`mock_llm` / `mock_llm_with_responses` / `sample_spec`)
3. 若需新的样例数据，扩展 `conftest.py` 而非在测试中硬编码

### 前端
1. 在 `src/__tests__/` 创建 `<name>.test.ts` 或 `<name>.test.tsx`
2. 使用 `vi.mock('@/api/client')` 隔离网络
3. 优先使用 `screen.getByRole` / `getByText` 查询，避免依赖 CSS class
