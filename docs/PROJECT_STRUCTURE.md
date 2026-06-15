# Project Structure

This repository is a front/back static project analysis tool.

```text
PoltAIshow/
  backend/                  FastAPI service, import API, graph API, source preview API, chat API
  contracts/static_flow/    language-neutral graph data model
  frontend/                 React/Vite visualization workspace
  modules/static_flow/      project scanner, language adapters, report and graph exporters
  tests/                    static analysis and contract tests
  backend/tests/            backend API tests
  docs/                     project usage, testing, environment, and structure docs
  resources/scripts/        auxiliary CLI scripts
  resources/fixtures/       small parser sanity fixtures
  logs/                     local runtime logs, ignored by Git
```

## Active Code

- `backend/app/main.py`: HTTP API entry point.
- `backend/app/analyzer.py`: connects the API to the static analysis core.
- `backend/app/graph_adapter.py`: converts the backend graph into frontend payloads.
- `backend/app/llm.py`: DeepSeek/OpenAI-compatible text chat integration.
- `frontend/src/App.tsx`: current single-workspace visualization UI.
- `frontend/src/lib/graphModel.ts`: frontend graph expansion and layout model.
- `modules/static_flow/project_analyzer.py`: whole-project scanner and analysis orchestration.
- `modules/static_flow/python_adapter.py`: Python `ast` adapter.
- `modules/static_flow/tree_sitter_adapter.py`: Tree-sitter adapter for JS/TS/TSX/JSX.
- `resources/scripts/function_analyzer.py`: CLI summary/details/JSON export.
- `resources/scripts/script_graph.py`: CLI DOT/PNG export.

## Local Or Generated Files

These should not be uploaded:

```text
.env
.pytest_cache/
.pytest_tmp*/
.superpowers/
__pycache__/
frontend/node_modules/
frontend/dist/
frontend/.test-build/
logs/*.log
*.log
```

They are ignored by `.gitignore` and can be regenerated.

## Archive

`_archive/frontend-legacy-visualization-20260614/` contains the old frontend moved aside for reference. It is intentionally ignored by Git.
