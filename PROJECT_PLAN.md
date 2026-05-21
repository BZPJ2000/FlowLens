# PoltAIshow — 代码数据流可视化分析平台

## 项目规划文档

> 版本: v1.0 | 日期: 2026-05-16 | 状态: 规划阶段

---

## 目录

1. [项目定位与核心价值](#1-项目定位与核心价值)
2. [业务逻辑分析](#2-业务逻辑分析)
3. [用户故事与用例](#3-用户故事与用例)
4. [实体关系建模](#4-实体关系建模)
5. [数据库设计](#5-数据库设计)
6. [技术选型](#6-技术选型)
7. [MVP 范围定义](#7-mvp-范围定义)
8. [开发阶段规划](#8-开发阶段规划)
9. [API 设计](#9-api-设计)
10. [前端规划](#10-前端规划)
11. [可视化方案](#11-可视化方案)
12. [风险与注意事项](#12-风险与注意事项)

---

## 1. 项目定位与核心价值

### 一句话描述

> 导入任意项目源码，AI 自动解析每个文件的作用、函数间的数据流向、变量类型，生成可视化数据流图 + 完整架构报告 + 智能问答。

### 解决什么痛点

| 痛点 | 核心原因 | 本项目的解决方式 |
|------|----------|-----------------|
| AI 生成的项目看不懂 | 不是你写的，脑子没地图 | AI 读完所有代码后生成完整解释报告 |
| 不知道怎么改代码 | 不知道改一个函数会影响哪些地方 | 数据流图显示所有连接关系 |
| 改了一处导致别处出错 | 不知道变量类型和依赖关系 | 图上标注数据类型和传入传出值 |
| 领导问项目细节答不上来 | 架构全在 AI 脑子里 | 可视化大图 + 文字报告一目了然 |
| 维护困难 | 不知道数据从哪来、到哪去 | 数据流动画追踪，从起点到终点 |

### 与 GitNexus 的差异

| 维度 | GitNexus | PoltAIshow |
|------|----------|------------|
| 粒度 | 文件级 | **函数级 / 变量级** |
| 关系展示 | 依赖关系 | **数据流向 + 数据类型** |
| 可视化 | 知识图谱节点 | **数据流动画 + 输入输出端口** |
| AI 能力 | MCP 工具 | **自动报告 + 问答 + 架构诊断** |
| 输入输出 | 无 | **每个函数标注输入参数类型和返回类型** |

---

## 2. 业务逻辑分析

### 2.1 核心业务流程

```
用户导入项目
    │
    ▼
┌─────────────┐    ┌──────────────┐    ┌────────────────┐
│ 1. 源码解析  │───▶│ 2. AI 理解    │───▶│ 3. 关系构建     │
│ 提取文件结构 │    │ 解释每个文件  │    │ 建立数据流连接  │
│ 提取函数定义 │    │ 提取输入输出  │    │ 标注变量类型    │
│ 提取导入语句 │    │ 总结架构模式  │    │ 构建依赖图      │
└─────────────┘    └──────────────┘    └────────────────┘
                                              │
                    ┌─────────────────────────┘
                    ▼
┌───────────┐  ┌───────────┐  ┌───────────────┐
│ 4a. 可视化 │  │ 4b. 报告  │  │ 4c. 智能问答   │
│ 数据流图   │  │ 架构文档  │  │ 自然语言查询   │
│ 动画追踪   │  │ 每个文件  │  │ "这个函数改了  │
│ 交互缩放   │  │ 的详细解释│  │  会影响什么?"  │
└───────────┘  └───────────┘  └───────────────┘
```

### 2.2 核心业务规则

**BR-001: 源码解析规则**
- 只解析源码文件（排除 node_modules、.git、dist、build、缓存文件等）
- 支持常见语言：JavaScript/TypeScript、Python、Go、Java、Rust、C/C++ 等
- 提取：文件路径、函数定义、类定义、导入语句、导出语句、注释

**BR-002: AI 分析规则**
- 每个文件提交给 AI，要求输出：
  - 该文件的核心作用（一句话）
  - 详细作用解释（一段话）
  - 输入：该文件导入了哪些外部变量/函数，它们的类型是什么
  - 输出：该文件导出了哪些变量/函数，它们的类型是什么
  - 内部数据结构定义
- AI 分析结果必须结构化（JSON），不能是纯文本

**BR-003: 关系构建规则**
- 导入语句 = 连接线（Edge）
- 连线标注 = 导入的变量名 + 类型 + 来源文件
- 文件 = 节点（Node）
- 函数 = 子节点（Port），位于节点边缘
- 数据流方向 = 从导出方指向导入方

**BR-004: 可视化规则**
- 节点显示为带端口的方框
- 连线从导出端口指向导入端口
- 连线标注变量名和数据类型
- 鼠标悬停显示详细信息
- 点击文件节点展开/折叠内部函数
- 数据流动画：小光点从数据源头沿连线流动到终点

**BR-005: 报告生成规则**
- 必须包含：
  - 项目总览（技术栈、文件数量、架构模式）
  - 每个文件的作用解释
  - 核心数据流路径描述
  - 架构问题诊断（循环依赖、未使用导出、类型不匹配等）
- 篇幅可长，但结构清晰，有目录索引

**BR-006: 通用性规则**
- 不限制项目类型：前端、后端、CLI工具、深度学习、脚本集合均可
- 语言无关：通过 Tree-sitter 支持多语言解析
- 不依赖特定框架

### 2.3 权限与安全

- 用户可以上传压缩包或输入 GitHub URL
- 临时会话：分析结果在服务器存储 **24 小时**后自动清理
- 可选：用户登录后可以保存分析历史
- 不上传源码到第三方 AI 服务（用户可配置 API Key）

---

## 3. 用户故事与用例

### 3.1 主要用户角色

| 角色 | 场景 |
|------|------|
| AI Coding 开发者 | 用 AI 生成了一个项目，想快速理解它 |
| 接手他人项目的开发者 | 接手项目后需要快速建立心理地图 |
| 技术负责人 | 审查 AI 生成代码的架构质量 |
| 学习者 | 想了解开源项目的数据流向 |

### 3.2 核心用例

**UC-01: 导入项目并查看数据流图**
```
前置条件：用户有一个 GitHub 项目地址或 zip 文件
主流程：
  1. 用户输入 GitHub URL 或上传 zip
  2. 系统解析源码，显示进度条
  3. 系统调用 AI 分析每个文件
  4. 系统构建数据流关系图
  5. 用户看到可视化画布，可以拖拽、缩放
  6. 数据流小光点自动演示数据流向
  7. 用户点击任意节点查看详情
```

**UC-02: 生成架构报告**
```
前置条件：项目已分析完成
主流程：
  1. 用户点击"生成报告"
  2. 系统生成结构化 Markdown 报告
  3. 报告包含：项目总览、文件清单、数据流说明、架构诊断
  4. 用户可下载或在线浏览
```

**UC-03: 智能问答**
```
前置条件：项目已分析完成
主流程：
  1. 用户在对话框输入问题
  2. 系统基于已分析的代码上下文回答
  3. 回答引用的文件和函数高亮显示在图中
```

---

## 4. 实体关系建模

### 4.1 核心实体

```
┌─────────────────┐       ┌─────────────────┐
│    Project      │       │    Analysis     │
│─────────────────│       │─────────────────│
│ id (PK)         │──1:N──│ id (PK)         │
│ name            │       │ project_id (FK) │
│ source_type     │       │ status          │
│ source_url      │       │ created_at      │
│ file_count      │       │ completed_at    │
│ created_at      │       │ expires_at      │
└─────────────────┘       └─────────────────┘
                                    │
                                    │ 1:N
                                    ▼
┌─────────────────┐       ┌─────────────────┐
│   FileNode      │       │   DataEdge      │
│─────────────────│       │─────────────────│
│ id (PK)         │       │ id (PK)         │
│ analysis_id(FK) │──1:N──│ analysis_id(FK) │
│ path            │       │ from_node (FK)  │
│ language        │       │ to_node (FK)    │
│ summary         │       │ from_port       │
│ detail_explain  │       │ to_port         │
│ imports_json    │       │ variable_name   │
│ exports_json    │       │ data_type       │
│ functions_json  │       │ edge_type       │
└─────────────────┘       └─────────────────┘
        │
        │ 1:N
        ▼
┌─────────────────┐       ┌─────────────────┐
│  FunctionPort   │       │   ChatSession   │
│─────────────────│       │─────────────────│
│ id (PK)         │       │ id (PK)         │
│ file_node_id(FK)│       │ analysis_id(FK) │
│ name            │       │ created_at      │
│ params_json     │       └─────────────────┘
│ return_type     │              │
│ is_exported     │              │ 1:N
└─────────────────┘              ▼
                        ┌─────────────────┐
                        │  ChatMessage    │
                        │─────────────────│
                        │ id (PK)         │
                        │ session_id (FK) │
                        │ role            │
                        │ content         │
                        │ referenced_nodes│
                        └─────────────────┘
```

### 4.2 实体关系总结

| 关系 | 类型 | 说明 |
|------|------|------|
| Project → Analysis | 1:N | 一个项目可以被多次分析 |
| Analysis → FileNode | 1:N | 一次分析包含多个文件节点 |
| Analysis → DataEdge | 1:N | 一次分析包含多条数据边 |
| FileNode → FileNode | M:N | 通过 DataEdge 连接 |
| FileNode → FunctionPort | 1:N | 一个文件包含多个函数端口 |
| DataEdge.from_port | N:1 | 边从 FunctionPort 出发 |
| DataEdge.to_port | N:1 | 边指向 FunctionPort |
| Analysis → ChatSession | 1:N | 一次分析有多个对话 |
| ChatSession → ChatMessage | 1:N | 一个对话有多条消息 |

---

## 5. 数据库设计

> 注意：先建表，后写代码。表关系确保正确后再写 API。

### 5.1 表设计

```sql
-- ============================================
-- 表 1: projects (项目)
-- ============================================
CREATE TABLE projects (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(255) NOT NULL,          -- 项目名
    source_type     VARCHAR(20) NOT NULL,           -- 'github' | 'upload'
    source_url      TEXT,                           -- GitHub URL（如果是github类型）
    storage_path    TEXT,                           -- 解压后的存储路径
    file_count      INTEGER DEFAULT 0,
    total_size_kb   INTEGER DEFAULT 0,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- ============================================
-- 表 2: analyses (分析任务)
-- ============================================
CREATE TABLE analyses (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    status          VARCHAR(20) DEFAULT 'pending', -- pending|parsing|analyzing|building|completed|failed
    error_message   TEXT,
    progress_pct    INTEGER DEFAULT 0,             -- 0-100
    created_at      TIMESTAMP DEFAULT NOW(),
    completed_at    TIMESTAMP,
    expires_at      TIMESTAMP DEFAULT (NOW() + INTERVAL '24 hours')
);

-- ============================================
-- 表 3: file_nodes (文件节点)
-- ============================================
CREATE TABLE file_nodes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_id     UUID NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
    file_path       VARCHAR(1000) NOT NULL,         -- 相对路径
    file_name       VARCHAR(255) NOT NULL,          -- 文件名
    language        VARCHAR(50),                    -- 编程语言
    content_hash    VARCHAR(64),                    -- 文件内容 SHA256（用于去重/缓存）
    summary         VARCHAR(500),                   -- AI 生成的一句话总结
    detail_explain  TEXT,                           -- AI 生成的详细解释
    imports_json    JSONB DEFAULT '[]',             -- 导入列表 [{var, source, type}]
    exports_json    JSONB DEFAULT '[]',             -- 导出列表 [{var, type}]
    functions_json  JSONB DEFAULT '[]',             -- 函数列表 [{name, params, return_type}]
    raw_content     TEXT,                           -- 原始源码（清理用，24h后删除）
    created_at      TIMESTAMP DEFAULT NOW()
);

-- 索引
CREATE INDEX idx_file_nodes_analysis ON file_nodes(analysis_id);
CREATE INDEX idx_file_nodes_path ON file_nodes(analysis_id, file_path);

-- ============================================
-- 表 4: data_edges (数据边/连接)
-- ============================================
CREATE TABLE data_edges (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_id     UUID NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
    from_file_id    UUID REFERENCES file_nodes(id) ON DELETE CASCADE,
    to_file_id      UUID REFERENCES file_nodes(id) ON DELETE CASCADE,
    from_port_name  VARCHAR(255),                   -- 来源端口名（函数名/变量名）
    to_port_name    VARCHAR(255),                   -- 目标端口名
    variable_name   VARCHAR(255) NOT NULL,          -- 传递的变量名
    data_type       VARCHAR(255),                   -- 数据类型
    edge_type       VARCHAR(20) DEFAULT 'import',   -- 'import' | 'call' | 'export'
    metadata_json   JSONB DEFAULT '{}'
);

CREATE INDEX idx_data_edges_analysis ON data_edges(analysis_id);
CREATE INDEX idx_data_edges_from ON data_edges(from_file_id);
CREATE INDEX idx_data_edges_to ON data_edges(to_file_id);

-- ============================================
-- 表 5: function_ports (函数端口)
-- ============================================
CREATE TABLE function_ports (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_node_id    UUID NOT NULL REFERENCES file_nodes(id) ON DELETE CASCADE,
    name            VARCHAR(255) NOT NULL,          -- 函数名
    params_json     JSONB DEFAULT '[]',             -- 参数列表 [{name, type}]
    return_type     VARCHAR(255),                   -- 返回值类型
    is_exported     BOOLEAN DEFAULT FALSE,
    is_imported     BOOLEAN DEFAULT FALSE,
    position        INTEGER DEFAULT 0               -- 在文件节点上的排列位置
);

CREATE INDEX idx_function_ports_file ON function_ports(file_node_id);

-- ============================================
-- 表 6: chat_sessions (对话会话)
-- ============================================
CREATE TABLE chat_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_id     UUID NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
    title           VARCHAR(255) DEFAULT '新对话',
    created_at      TIMESTAMP DEFAULT NOW()
);

-- ============================================
-- 表 7: chat_messages (对话消息)
-- ============================================
CREATE TABLE chat_messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role            VARCHAR(20) NOT NULL,           -- 'user' | 'assistant'
    content         TEXT NOT NULL,
    referenced_nodes JSONB DEFAULT '[]',            -- 引用的文件节点 ID 列表
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_chat_messages_session ON chat_messages(session_id);

-- ============================================
-- 表 8: analysis_reports (分析报告)
-- ============================================
CREATE TABLE analysis_reports (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_id     UUID NOT NULL UNIQUE REFERENCES analyses(id) ON DELETE CASCADE,
    content_md      TEXT,                           -- 完整 Markdown 报告
    architecture_summary TEXT,                      -- 架构摘要
    issue_count     INTEGER DEFAULT 0,              -- 发现的问题数
    generated_at    TIMESTAMP DEFAULT NOW()
);
```

### 5.2 扩展规划（MVP 之后）

```sql
-- 用户系统（Phase 2）
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) UNIQUE,
    password_hash   VARCHAR(255),
    api_key_openai  VARCHAR(255),                   -- 用户自己的 API Key（加密存储）
    created_at      TIMESTAMP DEFAULT NOW()
);

-- 项目归属于用户
ALTER TABLE projects ADD COLUMN user_id UUID REFERENCES users(id);
```

---

## 6. 技术选型

### 6.1 后端

| 组件 | 技术选择 | 原因 |
|------|---------|------|
| 语言 | Python 3.12+ | AI/LLM 生态最好，代码解析库丰富 |
| Web 框架 | FastAPI | 异步支持好，自动生成 API 文档 |
| 数据库 | PostgreSQL 16 | JSONB 支持好，适合存储分析结果 |
| 缓存/队列 | Redis + Celery | 异步处理分析任务 |
| 代码解析 | Tree-sitter (via tree-sitter Python binding) | 多语言支持，增量解析 |
| AI SDK | litellm (统一接口) | 支持 OpenAI / Anthropic / 国产模型 |
| 文件存储 | 本地磁盘 + MinIO（可选） | MVP 阶段本地存储即可 |

### 6.2 前端

| 组件 | 技术选择 | 原因 |
|------|---------|------|
| 框架 | React 18 + TypeScript | 生态丰富，可视化库多 |
| 构建工具 | Vite | 快 |
| 可视化画布 | React Flow (reactflow) | 节点/边/端口/动画开箱即用 |
| UI 组件 | shadcn/ui + TailwindCSS | 现代、可定制 |
| 代码展示 | Shiki | 语法高亮，支持多语言 |
| 报告展示 | 自定义 Markdown 渲染 | 可能用 react-markdown |
| 状态管理 | Zustand | 轻量 |

### 6.3 为什么不直接用 GitNexus 二次开发？

1. GitNexus 是 Node.js/TypeScript 全栈，AI 生态不如 Python
2. GitNexus 侧重知识图谱（knowledge graph），我们侧重数据流（data flow）
3. 我们的核心差异化（函数级端口、数据流动画、类型标注）需要从底层重构
4. 可以借鉴它的 Tree-sitter 解析思路和 KuzuDB 方案，但不基于它开发

---

## 7. MVP 范围定义

### MVP 必须包含

| 功能 | 描述 | 优先级 |
|------|------|--------|
| GitHub URL 导入 | 输入 URL，自动拉取源码 | P0 |
| Zip 上传导入 | 上传压缩包解析 | P0 |
| 源码解析 | Tree-sitter 提取文件结构、import/export、函数定义 | P0 |
| AI 分析（单文件） | 每个文件调用 AI 获取：作用、输入输出、数据类型 | P0 |
| 数据流关系图 | 可视化节点和连线，支持拖拽缩放 | P0 |
| 数据类型标注 | 连线上显示变量名和类型 | P0 |
| 数据流动画 | 小光点沿连线流动 | P1 |
| 架构报告生成 | Markdown 格式，包含所有文件解释 | P1 |
| 智能问答 | 基于分析结果的自然语言对话 | P1 |

### MVP 不包含

| 功能 | 原因 | 计划 |
|------|------|------|
| 用户登录/注册 | MVP 只需匿名使用 | Phase 2 |
| 分析历史保存 | 24小时自动过期 | Phase 2 |
| 多语言高级解析 | 先支持 TS/JS/Python | Phase 2 |
| 实时协作 | 单人使用 | Phase 3 |
| 对比分析（两个版本） | 复杂度高 | Phase 3 |

---

## 8. 开发阶段规划

### Phase 0: 项目初始化（✅ 已完成）

- [x] 初始化后端项目结构（FastAPI + PostgreSQL + Redis）
- [x] 初始化前端项目结构（Vite + React + TypeScript）
- [x] Docker Compose 开发环境（PostgreSQL + Redis）
- [ ] 基础 CI/CD（GitHub Actions: lint + test）
- [x] `.gitignore`、`README.md`、环境变量模板

### Phase 1: 业务逻辑层（✅ 已完成）

> 注意：这一阶段 **不写一行数据库代码，不写一行前端代码**

- [x] **Step 1.1: 定义数据模型（纯 Python dataclasses/Pydantic）**
  - Project、Analysis、FileNode、DataEdge、FunctionPort 等
  - 先定义类型，再定义关系
  - 用 Pydantic 做输入验证

- [x] **Step 1.2: 源码解析引擎**
  - Tree-sitter 集成，支持 TypeScript/JavaScript/Python
  - 提取：文件树、import/export 语句、函数签名、类定义
  - 输出 AST 摘要（不交给 AI 的纯解析部分）
  - **实现：** `parser.py` 支持 14 种语言（TS/JS/Python/Go/Java/C/C++/C#/Rust/Ruby/Swift/Kotlin/Vue/Svelte/Bash）

- [x] **Step 1.3: AI 分析引擎**
  - 设计 Prompt 模板（系统提示词 + 每个文件的分析提示词）
  - Prompt 必须要求输出结构化 JSON
  - 批量分析 + 并发控制（限流、重试）
  - 上下文压缩策略：先解析 AST 摘要 → 把摘要发给 AI → AI 基于摘要分析
  - **实现：** `ai_engine.py` + `rule_analyzer.py`（零 LLM 调用的规则分析器）

- [x] **Step 1.4: 关系构建引擎**
  - 输入：所有文件的 AI 分析结果
  - 输出：Node 列表 + Edge 列表
  - 匹配规则：import 的变量名匹配 export 的变量名 → 建立连接
  - 类型推导：从导出方拿到类型，标注在边上
  - **实现：** `graph_builder.py`

- [x] **Step 1.5: 单元测试**
  - 准备 2-3 个小项目（TypeScript 前端项目、Python 后端项目、混合项目）
  - 测试解析准确性
  - 测试关系构建准确性
  - **状态：** 107 个测试全部通过

### Phase 2: 数据库层（✅ 已完成）

> 注意：基于 Phase 1 的实体模型建表

- [x] **Step 2.1: 创建数据库迁移脚本**
  - 使用 Alembic（Python SQLAlchemy 迁移工具）
  - 按 5.1 节表设计创建所有表
  - **实现：** `backend/app/db/migrations/`

- [x] **Step 2.2: 实现 Repository 层**
  - CRUD 封装，与业务逻辑解耦
  - 每个表对应一个 Repository 类
  - **实现：** `backend/app/db/repository.py`

- [x] **Step 2.3: 数据持久化集成**
  - 将 Phase 1 的解析结果写入数据库
  - JSONB 字段正确序列化/反序列化
  - TTL 清理任务（24小时过期数据）
  - **实现：** `backend/app/db/models.py` + `database.py`

### Phase 3: API 层（✅ 已完成）

> 注意：这一阶段不写前端代码，用 Swagger UI / curl 测试

- [x] **Step 3.1: 核心 API 实现**
  - `POST /api/projects/import` — 导入项目（GitHub URL 或上传 zip）
  - `GET /api/analyses/{id}/status` — 查询分析进度（支持 SSE）
  - `GET /api/analyses/{id}/graph` — 获取完整图数据（nodes + edges）
  - `GET /api/analyses/{id}/files/{file_id}` — 获取单个文件详情
  - `GET /api/analyses/{id}/report` — 获取/生成分析报告
  - `POST /api/analyses/{id}/chat` — 发送对话消息
  - `GET /api/analyses/{id}/chat/{session_id}` — 获取对话历史
  - **实现：** `backend/app/api/routes.py`

- [x] **Step 3.2: 异步任务**
  - 分析任务放入 Celery 队列
  - 进度通过 WebSocket/SSE 推送给前端
  - 任务状态机：pending → parsing → analyzing → building → completed/failed
  - **实现：** `backend/app/services/progress_manager.py`

- [x] **Step 3.3: API 测试**
  - 用 pytest + httpx 写集成测试
  - 测试完整的导入→分析→查询流程
  - **实现：** `backend/tests/test_api.py`

### Phase 4: 前端层（✅ 已完成）

> 注意：这一阶段才开始写前端代码

- [x] **Step 4.1: 项目导入页**
  - GitHub URL 输入框 + 粘贴按钮
  - 拖拽上传 zip 区域
  - 导入进度显示
  - **实现：** `frontend/src/pages/ImportPage.tsx`

- [x] **Step 4.2: 数据流可视化画布**
  - React Flow 集成
  - 自定义节点组件（显示文件名、一句话总结）
  - 自定义边组件（显示变量名和数据类型）
  - 自定义端口组件（函数参数/返回值的接入点）
  - 画布交互：拖拽、缩放、小地图、自动布局
  - 数据流动画：光点沿连线流动
  - **实现：** `frontend/src/components/graph/` (FlowCanvas, FileNode, DataFlowEdge, FunctionSubNode, MethodSubNode 等)

- [x] **Step 4.3: 文件详情面板**
  - 点击节点弹出侧边栏
  - 显示：详细解释、函数列表、导入/导出列表
  - 源码高亮显示
  - **实现：** `frontend/src/components/common/DetailPanel.tsx`

- [x] **Step 4.4: 架构报告页**
  - Markdown 渲染
  - 目录导航
  - 下载 PDF/Markdown
  - **实现：** `frontend/src/pages/ReportPage.tsx`

- [x] **Step 4.5: 智能问答面板**
  - 聊天界面
  - 消息中引用的文件/函数可以点击跳转到图中
  - 流式输出（SSE）
  - **实现：** `frontend/src/components/chat/ChatPanel.tsx`

### Phase 5: 扩展与优化（🚧 进行中）

- [x] 更多语言支持（Go、Java、Rust）
  - **已支持：** 14 种语言（TS/JS/Python/Go/Java/C/C++/C#/Rust/Ruby/Swift/Kotlin/Vue/Svelte/Bash）
- [ ] 用户系统
- [ ] 分析历史保存
- [ ] 对比分析
- [x] 架构问题自动诊断（循环依赖检测、类型不匹配警告等）
  - **已实现：** 循环依赖检测、类型不匹配、重复导出、高度耦合检测
- [x] **P0 功能：GraphML 导出 + 变更影响分析**
  - **实现：** `backend/app/core/graphml_exporter.py` + 变更影响分析 API
- [x] **P1 功能：编辑器 Deep Link + 自包含 HTML 导出**
  - **实现：** `backend/app/core/html_exporter.py` + VSCode/Cursor deep link 支持
- [x] **P2 功能：MCP 协议集成 + 函数内部控制流图**
  - **实现：** `backend/mcp_server.py` + `backend/app/core/cfg_generator.py`

---

## 9. API 设计

### 9.1 API 清单

```
POST   /api/v1/projects/import          # 导入项目
  Request:  { source_type: "github", url: "..." }
            OR multipart/form-data { file: zip }
  Response: { project_id, analysis_id, status: "pending" }

GET    /api/v1/analyses/{id}            # 获取分析详情
  Response: { id, status, progress_pct, file_count, ... }

GET    /api/v1/analyses/{id}/stream     # SSE 进度流
  Event:   { type: "progress", pct: 45, message: "分析中..." }

GET    /api/v1/analyses/{id}/graph      # 获取图数据
  Response: {
    nodes: [{ id, path, name, language, summary, ports: [...] }],
    edges: [{ id, from, to, fromPort, toPort, variableName, dataType }]
  }

GET    /api/v1/analyses/{id}/files/{fid} # 文件详情
  Response: { ...file_node 全部字段, raw_content }

GET    /api/v1/analyses/{id}/report     # 获取报告
  Response: { content_md, architecture_summary, issue_count }

POST   /api/v1/analyses/{id}/chat       # 发送消息
  Request:  { session_id?, message: "..." }
  Response: { session_id, reply: "...", referenced: [...] }
  (支持 SSE 流式输出)

GET    /api/v1/analyses/{id}/chat/sessions  # 对话列表

GET    /api/v1/analyses/{id}/chat/{sid}     # 对话历史
```

### 9.2 关键设计决策

- **异步分析**：导入后立即返回 analysis_id，前端通过 SSE 轮询进度
- **图数据一次返回**：graph 端点返回全部 nodes + edges（MVP 阶段项目不会太大）
- **AI 配置**：用户可在请求头携带 API Key（X-LLM-API-Key），不存服务器
- **24 小时过期**：通过数据库 expires_at 字段 + 定时任务清理

---

## 10. 前端规划

### 10.1 页面路由

```
/                          → 首页（导入页）
/analysis/:id              → 可视化画布（主界面）
/analysis/:id/report       → 架构报告页
/analysis/:id/chat         → 智能问答（侧边栏/独立页）
```

### 10.2 主界面布局

```
┌─────────────────────────────────────────────────────────────┐
│  Top Bar: 项目名 | 进度 | [查看报告] [问答] [导出]          │
├──────────────────────────────────────────────┬──────────────┤
│                                              │              │
│          数据流可视化画布                      │  详情面板     │
│          (React Flow)                        │  (可收起)    │
│                                              │              │
│   ┌──────┐    name: User     ┌──────┐       │  文件名:      │
│   │auth  │────:User──────▶  │ App  │       │  auth.ts     │
│   │ .ts  │    type:UserDto  │ .tsx │       │              │
│   └──────┘                  └──────┘       │  作用:        │
│        │                        │          │  处理用户认证  │
│        │ name: login           │          │              │
│        │ type: (u,p)=>Promise  │          │  函数:        │
│        ▼                        ▼          │  - login()   │
│   ┌──────┐                  ┌──────┐       │  - logout()  │
│   │ api  │                  │Home  │       │  - getToken()│
│   │ .ts  │                  │Page  │       │              │
│   └──────┘                  └──────┘       │              │
│                                              │              │
│   💡 小光点从 api.ts 沿连线流向 HomePage     │              │
│                                              │              │
├──────────────────────────────────────────────┴──────────────┤
│  Bottom Bar: 节点数: 42 | 连接数: 87 | 语言: TS, Python     │
└─────────────────────────────────────────────────────────────┘
```

### 10.3 核心技术实现要点

- **React Flow 自定义节点**：左侧显示输入端口（导入的变量），右侧显示输出端口（导出的变量）
- **端口颜色编码**：string=绿, number=蓝, function=紫, object=橙, unknown=灰
- **连线标签**：显示 `变量名: 类型`，如 `userData: UserDto`
- **数据流动画**：使用 React Flow 的 `<BaseEdge>` + CSS animation 实现光点流动
- **自动布局**：使用 dagre 或 elkjs 进行有向图自动布局

---

## 11. 可视化方案

### 11.1 推荐方案：React Flow

| 需求 | React Flow 能力 | 适配方式 |
|------|----------------|---------|
| 有向图 | ✅ 原生支持 | — |
| 自定义节点 | ✅ 完全可定制 | 自定义 HTML/React 组件 |
| 端口/Handle | ✅ 内置 Handle 组件 | 左侧 Target Handle，右侧 Source Handle |
| 连线标签 | ✅ Edge Label | 显示变量名+类型 |
| 动态动画 | ✅ 支持 CSS 动画 | Edge 上叠加动画元素 |
| 缩放拖拽 | ✅ 原生支持 | — |
| 自动布局 | 需结合 dagre/elkjs | 计算坐标后设置节点位置 |
| 性能 | ✅ 虚拟化渲染 | 百级节点流畅，千级节点需优化 |

### 11.2 数据流动画实现

```
概念：
- 每条连线（Edge）是一个 path（SVG path）
- 在 Edge 上叠加一个 animated circle
- Circle 沿着 path 从 source 移动到 target
- 使用 SVG stroke-dasharray + stroke-dashoffset 动画
- 也使用 CSS offset-path 动画（现代浏览器）

效果：
- 光点持续从数据源沿连线流向目标
- 有多个光点表示多条数据流同时进行
- 用户可以点击"播放/暂停"数据流动画
- 速度可调（慢速/正常/快速）
```

### 11.3 备选方案

如果 React Flow 不满足需求：
- **Cytoscape.js**：更强大的图算法，但 React 集成不如 React Flow 原生
- **G6 (AntV)**：蚂蚁金服出品，大图性能好，图算法丰富，但文档以中文为主
- **自研 Canvas 方案**：最灵活但工作量最大，MVP 阶段不推荐

---

## 12. 风险与注意事项

### 12.1 关键风险

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| AI 分析质量不稳定 | 高 | Prompt 工程 + 结构化输出要求 + 重试机制 |
| AI 调用成本高 | 中 | 先用 AST 摘要压缩上下文，减少 token 消耗 |
| 大项目解析慢 | 中 | 并发分析 + 增量解析 + 文件数量限制（MVP: 200 文件） |
| 关系构建不准确 | 高 | 多轮验证 + 人工纠错接口 + 名称匹配+类型匹配双重校验 |
| 前端大图性能 | 中 | React Flow 虚拟化 + 默认折叠内部函数 + 视口裁剪 |

### 12.2 开发纪律

1. **严格按阶段顺序执行**：Phase 1 → Phase 2 → Phase 3 → Phase 4，不可跳跃
2. **先业务逻辑，再数据库**：Phase 1 用纯 Pydantic 模型，不碰数据库
3. **先数据库，再 API**：Phase 2 建表完成后才开始写 API
4. **先 API，再前端**：Phase 3 API 全部可用后才开始前端
5. **先 MVP，再扩展**：不要过早优化、不要过早加功能
6. **表关系优于代码**：如果发现表设计有问题，先改表再改代码
7. **每个 Phase 结束必须 Review**：确认无问题后再进入下一 Phase

### 12.3 AI 上下文优化策略

这是本项目最关键的工程挑战之一：**如何让 AI 高效理解整个项目而不消耗天量 token？**

**三层压缩策略：**

```
Layer 1: AST 解析（零 token 消耗）
    ├─ Tree-sitter 提取：import/export、函数签名、类结构
    └─ 输出：结构化摘要 JSON（100-500 tokens/文件）

Layer 2: 文件级 AI 分析（低 token 消耗）
    ├─ 输入：Layer 1 摘要 + 文件源码（截断到 2000 行）
    ├─ 输出：{ summary, detail, imports[], exports[], functions[] }
    └─ 输出约 200-500 tokens/文件

Layer 3: 项目级 AI 理解（中等 token 消耗）
    ├─ 输入：所有文件的 Layer 2 输出（不是原始源码）
    ├─ 输出：架构总结 + 数据流连接 + 问题诊断
    └─ 输出约 2000-5000 tokens

Layer 4: 问答（按需 token 消耗）
    ├─ 输入：用户问题 + 相关文件的 Layer 2 输出（RAG 检索）
    └─ 输出：回答 + 引用
```

**关键原则**：只把分析结果发给 AI，不要把原始源码反复发。

---

## 附录 A: 开发环境搭建

```bash
# 后端
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install fastapi uvicorn sqlalchemy asyncpg redis celery \
            tree-sitter litellm pydantic alembic

# 前端
cd frontend
npm create vite@latest . -- --template react-ts
npm install reactflow @reactflow/core zustand react-markdown shiki
npm install tailwindcss @tailwindcss/vite
```

## 附录 B: 目录结构规划

```
PoltAIshow/
├── backend/
│   ├── app/
│   │   ├── models/          # Pydantic 模型（Phase 1）
│   │   ├── core/            # 解析引擎、AI引擎、关系引擎（Phase 1）
│   │   ├── db/              # 数据库模型 + Repository（Phase 2）
│   │   │   └── migrations/  # Alembic 迁移
│   │   ├── api/             # FastAPI 路由（Phase 3）
│   │   ├── tasks/           # Celery 任务
│   │   └── services/        # 业务服务层
│   ├── tests/
│   ├── alembic.ini
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/           # 页面组件
│   │   ├── components/      # 通用组件
│   │   │   ├── graph/       # React Flow 相关组件
│   │   │   ├── chat/        # 对话组件
│   │   │   └── report/      # 报告组件
│   │   ├── stores/          # Zustand 状态
│   │   ├── api/             # API 调用
│   │   └── types/           # TypeScript 类型
│   └── package.json
├── docker-compose.yml       # PostgreSQL + Redis
├── PROJECT_PLAN.md          # 本文档
└── 想法.txt                 # 原始想法
```

---

> **核心原则重申**：业务逻辑 → 表关系 → 数据库 → API → 前端。每步到位再走下一步。先 MVP，后扩展。
