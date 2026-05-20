# Project Instructions for AI Agents

This file provides instructions and context for AI coding agents working on this project.

<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:7510c1e2 -->
## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and commands.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

### Rules

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Run `bd prime` for detailed command reference and session close protocol
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files

**Architecture in one line:** issues live in a local Dolt DB; sync uses `refs/dolt/data` on your git remote; `.beads/issues.jsonl` is a passive export. See https://github.com/gastownhall/beads/blob/main/docs/SYNC_CONCEPTS.md for details and anti-patterns.

## Session Completion

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds
<!-- END BEADS INTEGRATION -->


## Build & Test

```bash
# Backend
cd backend
pip install -r requirements.txt
python -m pytest tests/ -v

# Frontend
cd frontend
npm install
npx tsc --noEmit --skipLibCheck
```

## Architecture Overview

PoltAIshow — 代码数据流可视化分析平台。导入任意项目源码，自动解析函数/类/数据流，生成可视化数据流图 + 架构报告 + 智能问答。

**目录结构：**
```
backend/   — FastAPI + PostgreSQL + Redis, Pydantic 模型, 纯规则分析器
frontend/  — React 18 + TypeScript + Vite + ReactFlow + TailwindCSS
```

**核心 Pipeline（Phase 1-2 已完成）：**
1. `parser.py` — 多语言源码解析（TS/JS/Python/Go/Java/C/C++/C#/Rust/Ruby/Swift/Kotlin/Vue/Svelte/Bash）
2. `rule_analyzer.py` — 纯规则分析器（Zero LLM），ParseResult → AIFileAnalysis
3. `graph_builder.py` — 关系构建引擎（import 边、跨文件调用边、端口→函数边）
4. `analyzer.py` — 分析编排服务，串联所有步骤
5. `report_generator.py` — Markdown 架构报告生成

**当前开发阶段：** Phase 2 完成（数据库层），Phase 3 待开始（API 层）。

## Conventions & Patterns

- 文件名按架构角色分类：controller/service/model/util/config/middleware/hook/store/view
- 所有语言解析用纯正则（零外部依赖），不依赖 tree-sitter
- 前端 dark theme，色板: bg `#06060a`, accent `#7c3aed`, text `#f5f5f7`
- Pydantic 模型定义在 `backend/app/models/schemas.py`
- 数据库用 SQLAlchemy async + PostgreSQL，Repository 模式
