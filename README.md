# PoltAIshow

PoltAIshow 是一个“项目级代码结构与传值关系可视化”工具。它的目标不是只分析单个脚本，而是导入一个完整项目后，自动解析项目里的文件、类、函数、方法、调用关系、参数传递关系和返回值接收关系，再交给前端做可视化，并允许用户基于选中的代码节点向 AI 提问。

核心流程：

```text
导入项目 -> 后端静态分析 -> 统一图谱数据 -> 前端可视化 -> AI 结合图谱问答
```

当前版本已经是一个可以运行的前后端项目：

- 后端：FastAPI 服务，负责导入本地项目或压缩包、执行静态分析、提供图谱/源码/报告/聊天接口。
- 分析核心：使用统一的数据模型描述函数、类、方法、调用边、传参边、返回边。
- 多语言适配：Python 使用标准库 `ast`；JavaScript / TypeScript / JSX / TSX 使用 Tree-sitter。
- 前端：React + Vite，可查看文件树、符号节点、调用/传值/返回连线、源码预览和选区上下文。
- AI：已接入 OpenAI-compatible 接口，默认按 DeepSeek 配置读取；未配置或调用失败时会回退到本地图谱摘要。

## 项目结构

```text
PoltAIshow/
  backend/                  FastAPI 后端服务
  backend/app/              API、分析任务、图谱转换、LLM 接入、内存状态
  backend/tests/            后端 API 和 LLM 测试

  frontend/                 React/Vite 前端项目
  frontend/src/             前端页面、API client、图谱模型
  frontend/tests/           前端 graph model 测试

  contracts/static_flow/    后端统一静态图谱数据结构
  modules/static_flow/      项目扫描器、Python 适配器、Tree-sitter 适配器、导出器、报告器
  tests/                    分析核心、合同模型、CLI 测试

  resources/scripts/        暂时不放根目录的辅助脚本
  resources/fixtures/       小型示例/测试 fixture
  docs/                     使用、测试、环境、结构说明
  logs/                     本地运行日志，Git 忽略
  _archive/                 旧代码和运行产物归档，Git 忽略
```

根目录只保留项目级文件：

```text
.env.example
.gitignore
README.md
pyproject.toml
conftest.py
backend/
frontend/
contracts/
modules/
tests/
resources/
docs/
logs/
```

## 环境要求

建议环境：

```text
Python >= 3.10
Node.js >= 20
npm
```

后端 Python 依赖在：

```text
backend/requirements.txt
```

前端依赖在：

```text
frontend/package.json
frontend/package-lock.json
```

## 配置 DeepSeek

项目根目录提供了示例配置：

```powershell
Copy-Item .env.example .env
```

`.env` 内容格式：

```text
POLTAISHOW_LLM_ENABLED=true
TEXT_AI_BASE_URL=https://api.deepseek.com
TEXT_AI_API_KEY=replace-with-your-key
TEXT_AI_MODEL=deepseek-chat
```

也支持 DeepSeek 风格别名：

```text
DEEPSEEK_BASE_URL
DEEPSEEK_API_KEY
DEEPSEEK_MODEL
```

如果你已有别的项目里的 `.env`，可以直接指定：

```powershell
$env:POLTAISHOW_ENV_FILE="E:\Github_Project\Papyrus\.env"
```

注意：

- `.env` 不要上传 GitHub。
- `.env.example` 可以上传。
- 如果不配置 DeepSeek，聊天功能仍然可用，但回答会来自本地静态图谱摘要，不会请求大模型。

## 启动后端

在项目根目录执行：

```powershell
python -m pip install -r backend/requirements.txt
python backend/run_dev.py
```

默认后端地址：

```text
http://127.0.0.1:8879
```

健康检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8879/health
```

后端日志会写入：

```text
logs/backend-uvicorn.log
```

## 启动前端

打开另一个终端：

```powershell
cd frontend
npm install
npm run dev -- --host 127.0.0.1
```

默认前端地址：

```text
http://127.0.0.1:5173
```

前端会把 `/api` 请求代理到：

```text
http://127.0.0.1:8879
```

## 使用方式

进入前端页面后，可以导入：

```text
E:\path\to\project
file:///E:/path/to/project
```

也可以上传压缩包：

```text
.zip
.tar.gz
.tgz
```

当前不支持直接粘贴 GitHub 地址自动 clone。远程仓库导入是后续功能。

## 前端可视化能力

当前前端是围绕“符号关系”和“传值关系”重做过的工作台：

- 左侧：项目文件树、模块过滤、符号类型过滤、边类型过滤、符号索引。
- 中间：函数、类、方法组成的关系图。
- 图上边：显示调用、实参到形参、返回值到接收变量等关系。
- 右侧：查看选中符号的文件、行号、参数、返回类型、入边、出边。
- 双击节点：打开源码预览窗口，定位到对应代码块。
- Ctrl / Shift 点击：多选符号。
- 框选：批量选择图上的符号。
- 底部聊天：把当前选中的符号上下文一起交给 AI。

静态传值边示例：

```text
caller 函数里的实参 -> callee 函数的形参
callee.return -> caller 里的接收变量
```

当前显示的是静态表达式级别的传值关系，不是运行时真实数值变化。

## 后端 API 概览

导入本地项目：

```powershell
$body = @{
  source_type = "local"
  source_url = "E:\path\to\project"
} | ConvertTo-Json

Invoke-RestMethod http://127.0.0.1:8879/api/v1/projects/import `
  -Method Post `
  -ContentType "application/json" `
  -Body $body
```

获取分析状态：

```powershell
Invoke-RestMethod http://127.0.0.1:8879/api/v1/analyses/<analysis_id>
```

获取图谱：

```powershell
Invoke-RestMethod http://127.0.0.1:8879/api/v1/analyses/<analysis_id>/graph
```

获取源码窗口：

```powershell
Invoke-RestMethod "http://127.0.0.1:8879/api/v1/analyses/<analysis_id>/source?file_path=E:\path\to\file.py&start_line=1&end_line=30"
```

向 AI 提问：

```powershell
$body = @{
  session_id = $null
  message = "解释这些函数之间的调用和传值关系"
  selected_symbol_ids = @()
} | ConvertTo-Json

Invoke-RestMethod http://127.0.0.1:8879/api/v1/analyses/<analysis_id>/chat `
  -Method Post `
  -ContentType "application/json" `
  -Body $body
```

## CLI 辅助脚本

辅助脚本不放根目录，统一放在：

```text
resources/scripts/
```

分析当前项目：

```powershell
python resources/scripts/function_analyzer.py .
```

分析其他项目：

```powershell
python resources/scripts/function_analyzer.py E:\path\to\project
```

显示完整细节：

```powershell
python resources/scripts/function_analyzer.py E:\path\to\project --details
```

导出完整 JSON 图谱：

```powershell
python resources/scripts/function_analyzer.py E:\path\to\project --json project-flow.json
```

导出 DOT / PNG：

```powershell
python resources/scripts/script_graph.py E:\path\to\project project_flow
```

如果以后按 Python 包安装，也可以使用 `pyproject.toml` 里定义的命令：

```powershell
poltaishow E:\path\to\project
poltaishow-graph E:\path\to\project project_flow
```

## 测试

后端和分析核心：

```powershell
python -m pytest -q -p no:cacheprovider
```

前端测试：

```powershell
cd frontend
npm test
```

前端生产构建：

```powershell
cd frontend
npm run build
```

自扫描：

```powershell
python resources/scripts/function_analyzer.py . --limit-symbols 10
```

当前测试覆盖：

```text
backend/tests/              后端导入、项目、源码、报告、聊天、LLM
tests/static_flow/          Python / Tree-sitter / 扫描器 / 前端图谱转换
tests/contracts/            静态图谱合同模型序列化
tests/cli/                  CLI JSON 和 DOT 导出
frontend/tests/             前端 graph model
```

最近一次验证结果：

```text
python -m pytest -q -p no:cacheprovider
36 passed

cd frontend
npm test
4 passed

cd frontend
npm run build
passed
```

## 当前支持的语言

已实现：

```text
Python       ast
JavaScript   Tree-sitter TypeScript grammar
TypeScript   Tree-sitter TypeScript grammar
JSX          Tree-sitter TSX grammar
TSX          Tree-sitter TSX grammar
```

规划中：

```text
Java
Go
Rust
```

项目的核心设计是：

```text
多语言前端解析器 -> 统一中间结构 -> 统一分析/可视化
```

也就是说，每种语言只需要把自己的 AST/CST 映射到统一的 `StaticProjectGraph` 模型，后面的分析和前端展示不需要关心源码语言。

## 当前限制

- 这是静态分析工具，不会执行被分析项目。
- 因此当前不能看到真实运行时数值变化，只能看到表达式级传值关系。
- Python 动态调用，例如 `getattr()`、猴子补丁、运行时 import，可能无法解析到准确目标。
- 前端框架的生命周期、路由约定、依赖注入等动态分发，目前只能部分表现为静态边或未解析边。
- Java / Go / Rust 的 Tree-sitter 适配器还没有接入。
- 后端分析状态暂存在内存里，重启后端后历史分析记录会丢失。
- 远程 GitHub 仓库直接导入还未实现。

## 相关文档

```text
docs/ENVIRONMENT.md         环境和 DeepSeek 配置
docs/PROJECT_STRUCTURE.md   项目结构说明
docs/TESTING.md             测试说明
docs/USAGE.md               API、CLI、前端使用说明
docs/MANIFEST.md            GitHub 上传清单
```
