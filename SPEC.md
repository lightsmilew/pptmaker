# PPT-Making Agent 系统规格说明书

## 1. 概念与愿景

一个智能化的 PPT 生成助手，通过多 Agent 协作和结构化工作流，将用户的自然语言需求转化为精美的演示文稿。系统采用**规划-分解-执行-校验-修正**的 Agent 范式，确保每一页内容精准、版式美观、全局一致。

核心体验：**输入即所得**——用户只需描述需求，系统自动完成从大纲规划到最终文件交付的全部流程，支持迭代修改和增量更新。

---

## 2. 设计语言

### 2.1 美学方向
**极简科技风**——以深色主题为基底，配合渐变蓝紫色调，营造专业、智能的工具感。界面元素采用毛玻璃效果，层次分明。

### 2.2 配色方案
```
主色调 (Primary):     #6366F1 (Indigo-500)
次要色 (Secondary):   #8B5CF6 (Violet-500)
强调色 (Accent):      #06B6D4 (Cyan-500)
成功色 (Success):     #10B981 (Emerald-500)
警告色 (Warning):     #F59E0B (Amber-500)
错误色 (Error):       #EF4444 (Red-500)
背景色 (Background):  #0F172A (Slate-900)
次背景 (Surface):     #1E293B (Slate-800)
边框色 (Border):      #334155 (Slate-700)
文本主色:             #F1F5F9 (Slate-100)
文本次色:             #94A3B8 (Slate-400)
```

### 2.3 字体系统
- **标题字体**: Inter (700) - 现代无衬线，清晰专业
- **正文字体**: Inter (400, 500) - 高可读性
- **代码/数据**: JetBrains Mono - 等宽字体用于技术内容
- **中文字体**: Noto Sans SC - 支持完整中文显示

### 2.4 空间系统
- 基础单位: 4px
- 间距梯度: 4, 8, 12, 16, 24, 32, 48, 64px
- 圆角: sm(6px), md(8px), lg(12px), xl(16px)
- 阴影: 轻柔的层叠阴影营造深度感

### 2.5 动效哲学
- **过渡动画**: 300ms ease-out，流畅但不拖沓
- **微交互**: 按钮悬停放大 1.02x，背景色渐变
- **加载状态**: 脉冲动画 + 进度文字描述
- **状态切换**: 淡入淡出，避免突兀

### 2.6 图标系统
使用 Lucide React 图标库，保持一致的 24px 尺寸和 1.5px 线宽。

---

## 3. 布局与结构

### 3.1 整体布局
```
┌─────────────────────────────────────────────────────────────┐
│  顶部导航栏 (64px)                                           │
│  Logo | 项目名称 | 状态指示器 | 操作按钮                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────┐  ┌─────────────────────────────────┐  │
│  │                 │  │                                 │  │
│  │  左侧边栏       │  │  主内容区                        │  │
│  │  (280px)       │  │  (flex-1)                       │  │
│  │                 │  │                                 │  │
│  │  - 输入区       │  │  - 工作流程可视化                │  │
│  │  - 项目配置     │  │  - PPT 预览                      │  │
│  │  - 页面列表     │  │  - 详情编辑                      │  │
│  │                 │  │                                 │  │
│  └─────────────────┘  └─────────────────────────────────┘  │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  底部状态栏 (32px) - 处理进度 | 错误提示 | 版本信息          │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 页面结构
1. **首页/输入页** - 用户输入需求的主入口
2. **规划页** - 显示生成的大纲，可编辑调整
3. **编辑页** - 逐页查看和修改 PPT 内容
4. **预览页** - 最终 PPT 预览和导出

### 3.3 响应式策略
- 桌面端 (≥1280px): 完整三栏布局
- 平板端 (768-1279px): 双栏布局，侧边栏可折叠
- 移动端 (<768px): 单栏堆叠，底部导航

---

## 4. 功能与交互

### 4.1 核心功能流程

#### 4.1.1 需求输入
- **方式**: 多行文本输入，支持粘贴 Markdown 大纲
- **快捷键**: Ctrl+Enter 开始生成
- **示例提示**: 点击可插入示例需求
- **文件上传**: 支持拖拽上传 PDF/Word/旧 PPT 文件
- **实时解析**: 显示识别出的关键信息（主题、页数、风格）

#### 4.1.2 智能规划
- **自动解析**: 识别用户意图，提取主题、受众、页数等
- **大纲生成**: 生成结构化页面列表
- **可编辑**: 点击大纲项可直接修改
- **拖拽排序**: 页面可拖拽调整顺序
- **增减页面**: 支持插入新页面或删除现有页面

#### 4.1.3 逐页生成
- **循环生成**: 页面逐个生成，非一次性输出
- **实时预览**: 生成完成的页面可立即预览
- **状态显示**: 当前生成页面、进度百分比
- **中止功能**: 可随时中止生成过程

#### 4.1.4 内容编辑
- **选中编辑**: 点击页面卡片进入编辑模式
- **双栏编辑**: 左侧内容编辑，右侧预览
- **内容校验**: 自动检查要点数量、文字长度
- **版式切换**: 一键更换页面版式模板

#### 4.1.5 导出交付
- **格式选择**: 仅支持 .pptx 导出
- **自定义文件名**: 默认使用主题名
- **下载按钮**: 一键下载到本地
- **预览新窗口**: 在新窗口打开完整预览

### 4.2 交互细节

#### 输入框
- placeholder 显示示例提示
- focus 时边框变为主色调
- 实时字数统计
- 支持 Ctrl+V 粘贴多行内容

#### 按钮
- hover: 背景色加深，scale 1.02
- active: scale 0.98
- disabled: 透明度 50%，cursor not-allowed
- loading: 显示旋转图标 + 文字

#### 页面卡片
- hover: 边框变亮，显示操作按钮
- selected: 主色调边框，背景微亮
- 拖拽时: 阴影加深，透明度 0.8

#### 进度条
- 分段显示: 解析 → 规划 → 生成 → 导出
- 当前步骤高亮，已完成步骤打勾
- 显示预估剩余时间

### 4.3 错误处理

| 场景 | 处理方式 |
|------|---------|
| API 调用失败 | 显示重试按钮，保留输入内容 |
| 文件解析失败 | 提示支持格式，提供手动输入选项 |
| 页数超出限制 | 提示最大页数，建议精简内容 |
| 网络中断 | 自动保存状态，断点续传 |

### 4.4 空状态设计
- 首页: 显示引导动画 + 示例卡片
- 页面列表: "还没有页面，点击上方按钮添加"
- 预览区: "选择或生成页面后在此预览"

---

## 5. 组件清单

### 5.1 导航组件
| 组件 | 状态 | 说明 |
|------|------|------|
| NavBar | default, scrolled | 顶部导航栏，滚动后添加阴影 |
| StepIndicator | step 0-3, active, completed | 工作流程步骤指示器 |
| TabNav | active, hover | 标签页导航 |

### 5.2 输入组件
| 组件 | 状态 | 说明 |
|------|------|------|
| TextArea | default, focus, error, disabled | 多行文本输入 |
| FileUpload | empty, hover, uploading, success, error | 文件拖拽上传区 |
| Select | default, open, selected | 下拉选择器 |
| Switch | on, off, disabled | 开关切换 |
| NumberInput | default, focus, error | 数字输入框 |

### 5.3 显示组件
| 组件 | 状态 | 说明 |
|------|------|------|
| PageCard | default, hover, selected, editing | 页面卡片 |
| OutlineItem | default, hover, editing | 大纲条目 |
| Badge | info, success, warning, error | 状态徽章 |
| ProgressBar | determinate, indeterminate | 进度条 |
| Toast | info, success, warning, error | 提示消息 |

### 5.4 反馈组件
| 组件 | 状态 | 说明 |
|------|------|------|
| Button | default, hover, active, loading, disabled | 按钮 |
| IconButton | default, hover, active, disabled | 图标按钮 |
| Tooltip | top, bottom, left, right | 提示气泡 |
| Modal | open, closing | 模态框 |
| Skeleton | animated | 骨架屏 |

---

## 6. 技术架构

### 6.1 技术栈

#### 后端 (Agent Core)
- **运行时**: Python 3.10+
- **Agent 框架**: LangGraph
- **大模型**: OpenAI GPT-4 / Claude 3.5 (可配置)
- **PPT 生成**: python-pptx
- **文档解析**: PyPDF2, python-docx
- **HTTP 服务**: FastAPI
- **异步任务**: asyncio + aiofiles

#### 前端 (UI Client)
- **框架**: React 18 + TypeScript
- **构建工具**: Vite
- **UI 组件**: shadcn/ui (基于 Radix)
- **样式**: Tailwind CSS
- **状态管理**: Zustand
- **HTTP 客户端**: fetch API
- **图标**: Lucide React

### 6.2 系统架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                         前端客户端 (React)                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │  输入面板   │  │  预览面板   │  │  编辑面板   │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP/WebSocket
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                       后端服务 (FastAPI)                          │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │                   LangGraph State Machine                │     │
│  │  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────┐  │     │
│  │  │ Planner │───▶│ Writer  │───▶│Designer │───▶│Critic│  │     │
│  │  │  Node   │    │  Node   │    │  Node   │    │Node │  │     │
│  │  └─────────┘    └─────────┘    └─────────┘    └─────┘  │     │
│  │       │                              │            │     │     │
│  │       └──────────────────────────────┴────────────┘     │     │
│  │                     (状态流转)                            │     │
│  └─────────────────────────────────────────────────────────┘     │
│                              │                                   │
│  ┌────────────────────────────┴────────────────────────────┐     │
│  │                      工具能力集                          │     │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐ │     │
│  │  │文档解析器│  │PPT渲染器 │  │图表生成器│  │素材检索│ │     │
│  │  └──────────┘  └──────────┘  └──────────┘  └────────┘ │     │
│  └─────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────┘
```

### 6.3 LangGraph 状态机设计

#### State 结构
```python
class PPTProjectState(TypedDict):
    # 项目规格
    spec: PPTProjectSpec
    
    # 全局状态
    status: str  # idle, parsing, planning, generating, editing, exporting
    current_step: str
    error: Optional[str]
    
    # 页面数据
    pages: List[PageData]
    current_page_index: int
    
    # 记忆存储
    memory: ProjectMemory
    user_preferences: UserPreferences
```

#### 节点定义
```python
nodes = {
    "parse_input": 解析用户输入,
    "plan_outline": 生成大纲规划,
    "generate_page": 逐页生成内容,
    "design_layout": 设计页面版式,
    "critic_review": 评审校验,
    "render_pptx": 渲染最终文件,
    "handle_error": 错误处理
}

edges = {
    START: "parse_input",
    "parse_input": {"success": "plan_outline", "failure": "handle_error"},
    "plan_outline": {"success": "generate_page", "failure": "handle_error"},
    "generate_page": {"success": "design_layout", "failure": "handle_error"},
    "design_layout": {"success": "critic_review", "failure": "handle_error"},
    "critic_review": {"retry": "generate_page", "approve": END},
    "handle_error": {"retry": LAST_NODE, "abort": END}
}
```

### 6.4 API 设计

#### REST Endpoints
```
POST   /api/v1/projects              创建新项目
GET    /api/v1/projects/{id}         获取项目详情
PUT    /api/v1/projects/{id}         更新项目
DELETE /api/v1/projects/{id}         删除项目

POST   /api/v1/projects/{id}/parse   解析输入
POST   /api/v1/projects/{id}/plan   生成规划
POST   /api/v1/projects/{id}/generate/{page_id}  生成单页
POST   /api/v1/projects/{id}/render  渲染导出

GET    /api/v1/projects/{id}/pages   获取页面列表
PUT    /api/v1/projects/{id}/pages/{page_id}  更新页面
DELETE /api/v1/projects/{id}/pages/{page_id}  删除页面

GET    /api/v1/templates             获取模板列表
GET    /api/v1/templates/{id}        获取模板详情
```

#### WebSocket Events
```
ws://server/ws/{project_id}

Events:
- status_update: {"step": "generating", "progress": 45, "message": "正在生成第3页..."}
- page_generated: {"page_id": 3, "preview_url": "..."}
- error: {"code": "PARSE_FAILED", "message": "..."}
- completed: {"download_url": "..."}
```

### 6.5 数据模型

#### PPTProjectSpec
```python
class PPTProjectSpec(BaseModel):
    topic: str                           # 主题
    audience: str = "通用"               # 受众
    page_count: int = 8                  # 目标页数
    style: str = "商务简约"              # 风格
    needs_cover: bool = True             # 需封面
    needs_toc: bool = True               # 需目录
    needs_summary: bool = True           # 需总结
    needs_chart: bool = False            # 需图表
    notes: str = ""                      # 特殊要求
```

#### PageData
```python
class PageData(BaseModel):
    page_id: int
    page_type: str                       # cover, toc, content, chart, conclusion, reference
    title: str
    subtitle: Optional[str] = ""
    purpose: str                         # 本页作用
    
    # 内容结构
    key_points: List[str]                # 要点列表
    bullet_points: List[str]             # 详细要点
    table_data: Optional[dict] = None    # 表格数据
    chart_data: Optional[dict] = None     # 图表数据
    speaker_notes: Optional[str] = ""    # 演讲备注
    
    # 版式结构
    layout: str                           # 布局类型
    elements: List[LayoutElement]        # 布局元素
    
    # 元数据
    created_at: datetime
    updated_at: datetime
    status: str                          # pending, generating, completed, error
```

#### LayoutElement
```python
class LayoutElement(BaseModel):
    type: str           # title, text, image, chart, table, icon
    position: tuple    # (x, y) 百分比
    size: tuple         # (width, height) 百分比
    style: dict         # 样式配置
```

### 6.6 项目目录结构
```
PPTMaker/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI 入口
│   │   ├── config.py               # 配置管理
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── routes.py           # API 路由
│   │   │   └── websocket.py        # WebSocket 处理
│   │   ├── agent/
│   │   │   ├── __init__.py
│   │   │   ├── state.py            # 状态定义
│   │   │   ├── graph.py            # LangGraph 定义
│   │   │   ├── nodes/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── parser.py       # 解析节点
│   │   │   │   ├── planner.py      # 规划节点
│   │   │   │   ├── writer.py       # 写作节点
│   │   │   │   ├── designer.py     # 设计节点
│   │   │   │   ├── critic.py       # 评审节点
│   │   │   │   └── renderer.py     # 渲染节点
│   │   │   └── prompts/
│   │   │       ├── planner.md
│   │   │       ├── writer.md
│   │   │       ├── designer.md
│   │   │       └── critic.md
│   │   ├── tools/
│   │   │   ├── __init__.py
│   │   │   ├── document_parser.py  # 文档解析工具
│   │   │   ├── pptx_generator.py   # PPT 生成工具
│   │   │   ├── chart_generator.py  # 图表生成工具
│   │   │   └── material_search.py  # 素材检索工具
│   │   ├── storage/
│   │   │   ├── __init__.py
│   │   │   ├── memory.py           # 内存存储
│   │   │   └── templates.py        # 模板库
│   │   └── models/
│   │       ├── __init__.py
│   │       ├── project.py          # 项目模型
│   │       └── page.py             # 页面模型
│   ├── requirements.txt
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── index.css
│   │   ├── api/
│   │   │   └── client.ts          # API 客户端
│   │   ├── components/
│   │   │   ├── ui/                # 基础 UI 组件
│   │   │   ├── layout/            # 布局组件
│   │   │   ├── input/             # 输入组件
│   │   │   ├── preview/           # 预览组件
│   │   │   └── editor/            # 编辑组件
│   │   ├── hooks/
│   │   │   ├── useProject.ts
│   │   │   └── useWebSocket.ts
│   │   ├── stores/
│   │   │   └── projectStore.ts    # Zustand store
│   │   ├── types/
│   │   │   └── index.ts           # 类型定义
│   │   └── utils/
│   │       └── helpers.ts
│   ├── public/
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── tailwind.config.js
├── SPEC.md
└── README.md
```

---

## 7. 实现优先级

### Phase 1: 核心框架 (MVP)
- [ ] 后端项目结构搭建
- [ ] LangGraph 状态机实现
- [ ] 基础 API 路由
- [ ] 前端项目搭建
- [ ] 需求输入界面
- [ ] 单页生成流程

### Phase 2: 完整功能
- [ ] 多页批量生成
- [ ] 页面编辑功能
- [ ] PPT 导出下载
- [ ] WebSocket 实时更新
- [ ] 模板系统

### Phase 3: 增强功能
- [ ] 文档解析支持
- [ ] 图表生成
- [ ] 素材检索
- [ ] 用户偏好记忆
- [ ] 迭代修改

---

## 8. 验收标准

### 功能验收
- [ ] 用户输入自然语言需求，系统生成对应页数的 PPT 大纲
- [ ] 点击生成后，逐页显示生成进度
- [ ] 生成的 PPT 可预览、可编辑、可导出
- [ ] 修改某一页不影响其他页面
- [ ] 导出文件为标准 .pptx 格式，可用 PowerPoint 打开

### 性能验收
- [ ] 单页生成时间 < 10 秒
- [ ] 8 页 PPT 生成时间 < 60 秒
- [ ] 前端首屏加载 < 2 秒
- [ ] API 响应时间 < 500ms

### 体验验收
- [ ] 界面加载无白屏
- [ ] 操作反馈 < 100ms
- [ ] 错误提示明确，用户知道如何解决
- [ ] 移动端基本可用
