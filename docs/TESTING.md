# Testing

## Backend And Analysis Core

Run from the repository root:

```powershell
python -m pytest -q -p no:cacheprovider
```

Current pytest coverage:

```text
backend/tests/test_import_api.py          local/file:// import and archive upload
backend/tests/test_project_api.py         project list, delete, and reanalyze
backend/tests/test_chat_api.py            static fallback, selected symbols, stream, LLM branch
backend/tests/test_source_report_api.py   source preview and report endpoints
backend/tests/test_llm.py                 DeepSeek/OpenAI-compatible config and payload
backend/tests/test_api.py                 end-to-end API smoke path
tests/contracts/                         static graph contract serialization
tests/static_flow/                       Python adapter, Tree-sitter adapter, scanner, frontend payload
tests/cli/                               CLI JSON and DOT export behavior
```

If the Windows temp directory is blocked in the current shell, use a project-local temp directory:

```powershell
New-Item -ItemType Directory -Force .pytest_tmp_active | Out-Null
$env:TMP="E:\Github_Project\PoltAIshow\.pytest_tmp_active"
$env:TEMP="E:\Github_Project\PoltAIshow\.pytest_tmp_active"
python -m pytest -q -p no:cacheprovider
```

## Frontend

```powershell
cd frontend
npm test
npm run build
```

`npm test` compiles the frontend graph-model tests into `frontend/.test-build/`
and runs them with Node's built-in test runner. It does not require a browser.

Current frontend test coverage:

```text
frontend/tests/graphModel.test.ts         symbol expansion, edge labels, stats, neighborhood, reachability
```

## Self Scan

```powershell
python resources/scripts/function_analyzer.py . --limit-symbols 10
```

This validates that the project scanner can parse this repository as a target project.
