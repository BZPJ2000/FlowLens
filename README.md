# PoltAIshow

PoltAIshow is a project-level static flow viewer.

The product loop is:

```text
import project -> backend static analysis -> graph payload -> frontend visualization -> AI Q&A
```

The current implementation is a working thin slice:

- Backend: FastAPI service that analyzes a local project path or uploaded archive.
- Analysis core: language-neutral graph contracts, a Python AST adapter, and a Tree-sitter adapter for TypeScript/TSX/JavaScript/JSX. It extracts files, classes, functions, methods, calls, argument flow, return flow, and unresolved calls.
- Frontend: React/Vite trace-first workspace that expands the backend payload into function/class/method nodes, relation edges, filters, an inspector, and AI Q&A.
- AI: OpenAI-compatible text chat is wired for DeepSeek through `TEXT_AI_*` environment variables, with static graph fallback when it is not configured or unavailable.

## Repository Layout

```text
backend/                  FastAPI API around the analysis core
frontend/                 React/Vite trace-first graph UI
contracts/static_flow/    language-neutral static graph contracts
modules/static_flow/      scanner, Python adapter, graph exporters, reports
tests/                    analysis core tests
backend/tests/            backend API tests
resources/scripts/        auxiliary CLI scripts
resources/fixtures/       small parser sanity fixtures
logs/                     local runtime logs, ignored by Git
docs/ENVIRONMENT.md       environment and DeepSeek configuration
docs/PROJECT_STRUCTURE.md repository structure and active code map
docs/TESTING.md           test/build/self-scan commands
docs/USAGE.md             CLI, API, and web app usage notes
```

Old frontend code was moved to `_archive/frontend-legacy-visualization-20260614/` instead of being deleted.

## Run The App

Backend, from the repository root:

```powershell
python -m pip install -r backend/requirements.txt
python backend/run_dev.py
```

Optional DeepSeek config:

```powershell
Copy-Item .env.example .env
# Fill TEXT_AI_API_KEY, or point to an existing env file:
$env:POLTAISHOW_ENV_FILE="E:\Github_Project\Papyrus\.env"
```

The backend listens on:

```text
 http://127.0.0.1:8879
```

Frontend:

```powershell
cd frontend
npm install
npm run dev -- --host 127.0.0.1
```

Open:

```text
http://127.0.0.1:5173
```

The frontend proxies `/api` to the backend on port `8879`.

## Import A Project

For the lightweight backend, the import bar accepts an existing local path or `file://` path:

```text
E:\path\to\project
file:///E:/path/to/project
```

Archive upload supports:

- `.zip`
- `.tar.gz`
- `.tgz`

Direct remote GitHub cloning is a follow-up backend feature, not part of the current thin slice.

## Visualization Model

The backend currently returns a file-oriented graph payload. The frontend turns that payload into a symbol-oriented view:

- Node: class, function, or method.
- Edge: call, argument flow, return flow, or unknown relation.
- Left panel: module/type/edge filters and symbol index.
- Center canvas: project-wide symbol graph with visible call, argument, and return labels.
- Right panel: selected symbol, parameters, incoming/outgoing value edges, and downstream trace entry.
- Bottom panel: graph-aware AI Q&A. Ctrl/Shift multi-select or box-select symbols before asking to include that selected context.

## CLI Use

Analyze the current project:

```powershell
python resources/scripts/function_analyzer.py .
```

Analyze another project:

```powershell
python resources/scripts/function_analyzer.py E:\path\to\project
```

Show all flow details:

```powershell
python resources/scripts/function_analyzer.py E:\path\to\project --details
```

Write the full static graph payload:

```powershell
python resources/scripts/function_analyzer.py E:\path\to\project --json project-flow.json
```

Export DOT/PNG:

```powershell
python resources/scripts/script_graph.py E:\path\to\project project_flow
```

## Test

Backend and analysis core:

```powershell
python -m pytest -q -p no:cacheprovider
```

Frontend:

```powershell
cd frontend
npm run build
```

## Current Limits

- Implemented adapters: Python via `ast`; TypeScript/TSX/JavaScript/JSX via Tree-sitter TypeScript grammar.
- Java/Go/Rust are planned through the same adapter contract, but their Tree-sitter language packages and extractors are not wired yet.
- Static analysis does not execute the target project, so runtime values are not known.
- Dynamic calls such as `getattr()` and framework dispatch can become unresolved edges.
- Runtime value changes are not captured yet; the current graph shows static value expressions and transfer edges.
- The chat panel uses DeepSeek when `POLTAISHOW_LLM_ENABLED=true` and `TEXT_AI_API_KEY` is available; otherwise it falls back to local graph-based answers.
- The backend stores analysis state in memory; restarting the backend clears history.
