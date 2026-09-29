# PPTMaker - AI-Powered PPT Generation Agent

一个基于多 Agent 协作的智能 PPT 生成系统，采用**规划-分解-执行-校验-修正**的 Agent 范式，将复杂 PPT 任务拆解成多个子步骤，每个步骤调用专用工具，降低大模型幻觉。

## 核心特性

- **多 Agent 协作**: Planner（规划）、Writer（写作）、Designer（设计）、Critic（评审）四个专业 Agent 协同工作
- **LangGraph 状态机**: 使用 LangGraph 实现复杂的多步骤、循环校验、增量修改的 Agent 任务
- **内容与版式解耦**: 同一套内容可切换不同版式模板
- **增量修改**: 支持只修改某一页，不影响其他页面
- **实时预览**: WebSocket 实时推送生成进度

## 技术架构

```
前端 (React + TypeScript + Tailwind)
        ↓ HTTP/WebSocket
后端 (FastAPI + LangGraph)
        ↓
   Agent 工作流
        ↓
工具能力集 (python-pptx, 文档解析)
```

## 快速开始

### 1. 启动后端服务

```bash
cd backend
pip install -e .
uvicorn app.main:app --reload --port 8000
```

### 2. 启动前端开发服务器

```bash
cd frontend
npm install
npm run dev
```

### 3. 打开浏览器

访问 http://localhost:5173

## 项目结构

```
PPTMaker/
├── backend/
│   ├── app/
│   │   ├── agent/           # Agent 核心
│   │   │   ├── nodes/        # 各节点实现
│   │   │   ├── state.py      # 状态定义
│   │   │   └── graph.py      # LangGraph 定义
│   │   ├── api/              # API 路由
│   │   ├── models/           # 数据模型
│   │   ├── tools/            # 工具集
│   │   └── storage/          # 记忆存储
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── components/       # React 组件
│   │   ├── stores/           # Zustand 状态
│   │   ├── hooks/            # 自定义 Hooks
│   │   └── api/              # API 客户端
│   └── package.json
└── SPEC.md                   # 规格说明
```

## Agent 工作流程

```
用户输入
    ↓
Parser (解析输入) → 提取规格
    ↓
Planner (规划大纲) → 生成页面列表
    ↓
For Each Page:
  ├→ Writer (生成内容) → 要点化输出
  ├→ Designer (设计版式) → 布局模板
  └→ Critic (评审校验) → 验证通过?
       ↓ Yes
  继续下一页
    ↓
Renderer (渲染导出) → PPTX 文件
```

## API 端点

| 方法 | 端点 | 描述 |
|------|------|------|
| POST | `/api/v1/projects` | 创建项目 |
| GET | `/api/v1/projects/{id}` | 获取项目 |
| POST | `/api/v1/projects/{id}/parse` | 解析输入 |
| POST | `/api/v1/projects/{id}/plan` | 生成大纲 |
| POST | `/api/v1/projects/{id}/generate` | 开始生成 |
| PUT | `/api/v1/projects/{id}/pages/{page_id}` | 更新页面 |
| POST | `/api/v1/projects/{id}/render` | 导出PPTX |
| WS | `/ws/{project_id}` | WebSocket |

## 环境变量

### 后端 (.env)

```env
OPENAI_API_KEY=sk-...      # OpenAI API Key (可选)
ANTHROPIC_API_KEY=sk-...   # Anthropic API Key (可选)
```

### 前端

无需配置，Vite 代理自动转发到后端。

## 设计原则

1. **结构化中间表示**: 不让大模型直接输出 PPT，使用 JSON 结构化描述
2. **分页迭代生成**: 不一次性生成全部页面，逐页生成降低幻觉
3. **内容版式分离**: 内容与布局解耦，支持模板切换
4. **Critic 校验**: 每页生成后强制校验，确保质量
5. **增量编辑**: 支持局部修改，不重新生成全部

## 后续扩展

- [ ] 支持文档解析 (PDF/Word)
- [ ] 图表生成集成
- [ ] 素材检索 API
- [ ] 多语言支持
- [ ] 演讲备注生成
- [ ] 动画支持

## License

MIT

## 部署

详细部署教程请参考 [DEPLOY.md](DEPLOY.md)。

### 快速打包

**Windows:**
```powershell
scripts\build.bat
```

**Linux/Mac:**
```bash
chmod +x scripts/build.sh
./scripts/build.sh
```

打包后的文件在 `dist/` 目录。
