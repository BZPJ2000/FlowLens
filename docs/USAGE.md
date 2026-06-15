# Usage

## Web App

Start backend:

```powershell
python backend/run_dev.py
```

Enable DeepSeek:

```powershell
Copy-Item .env.example .env
# Fill TEXT_AI_API_KEY, or reuse an existing compatible env file:
$env:POLTAISHOW_ENV_FILE="E:\Github_Project\Papyrus\.env"
```

Start frontend:

```powershell
cd frontend
npm run dev -- --host 127.0.0.1
```

Open:

```text
http://127.0.0.1:5173
```

Import a local project path:

```text
E:\path\to\project
```

Or a local `file://` path:

```text
file:///E:/path/to/project
```

Archive upload supports `.zip`, `.tar.gz`, and `.tgz`.

## Frontend Workspace

The current frontend is a trace-first project workspace:

- Left: search, module/type filters, edge toggles, file tree, and symbol index.
- Center: class/function/method graph with visible call, argument, and return edges.
- Right: selected symbol inspector with parameters and incoming/outgoing relations.
- Bottom: AI Q&A based on the current static graph.

Selection behavior:

- Ctrl/Shift click symbols to multi-select.
- Drag a selection box on the graph to select multiple symbols.
- Double-click a symbol node to open the source preview at its code block.
- Ask AI after selecting symbols to include the selected context.
- If DeepSeek is configured, AI answers use the selected static graph context; otherwise the backend returns the local graph summary.

Current parser coverage:

- Python: `ast`
- TypeScript/TSX/JavaScript/JSX: Tree-sitter TypeScript grammar
- Java/Go/Rust: planned adapter slots, not wired yet

The `file://` import tab is for local `file:///E:/path/to/project` style paths. Direct remote GitHub clone is not implemented yet.

## API

Analyze a local path:

```powershell
$body = @{ source_type = "local"; source_url = "E:\path\to\project" } | ConvertTo-Json
Invoke-RestMethod http://127.0.0.1:8879/api/v1/projects/import -Method Post -ContentType "application/json" -Body $body
```

Get graph:

```powershell
Invoke-RestMethod http://127.0.0.1:8879/api/v1/analyses/<analysis_id>/graph
```

Ask a structure question:

```powershell
$body = @{ session_id = $null; message = "What are the call and value-flow relationships?"; selected_symbol_ids = @() } | ConvertTo-Json
Invoke-RestMethod http://127.0.0.1:8879/api/v1/analyses/<analysis_id>/chat -Method Post -ContentType "application/json" -Body $body
```

Ask with selected symbols:

```powershell
$body = @{
  session_id = $null
  message = "Explain these selected symbols"
  selected_symbol_ids = @("backend.app.main.chat", "backend.app.main.answer_question")
} | ConvertTo-Json
Invoke-RestMethod http://127.0.0.1:8879/api/v1/analyses/<analysis_id>/chat -Method Post -ContentType "application/json" -Body $body
```

## CLI

Analyze a project:

```powershell
python resources/scripts/function_analyzer.py E:\path\to\project
```

Full details:

```powershell
python resources/scripts/function_analyzer.py E:\path\to\project --details
```

JSON export:

```powershell
python resources/scripts/function_analyzer.py E:\path\to\project --json project-flow.json
```

DOT and PNG export:

```powershell
python resources/scripts/script_graph.py E:\path\to\project project_flow
```

## Large Projects

```powershell
python resources/scripts/function_analyzer.py E:\path\to\project --workers 8 --max-file-size-kb 1024 --exclude-dir vendor
```

Useful flags:

- `--workers`: parser worker count
- `--max-file-size-kb`: skip very large source files; `0` disables the limit
- `--exclude-dir`: skip a directory name; repeat for multiple names
- `--limit-symbols`: cap summary symbol output; `0` disables the limit

Default excluded directories include hidden directories, `_archive`, `node_modules`, `dist`, `build`, and common cache folders.
