# GitHub Upload Manifest

Include these active project files and directories:

```text
.env.example
.gitignore
README.md
pyproject.toml
conftest.py
backend/
contracts/
docs/
frontend/
modules/
resources/
tests/
```

Do not upload generated or local-only folders:

```text
.env
.beads/
.claude/
.codegraph/
.pytest_cache/
.pytest_tmp/
.pytest_tmp_active/
.superpowers/
__pycache__/
*.egg-info/
dist/
build/
frontend/node_modules/
frontend/dist/
frontend/.test-build/
logs/*.log
*.log
```

Notes:

- `backend/` is the active lightweight FastAPI backend.
- `frontend/` is the active React/Vite trace-first visualization UI.
- `_archive/frontend-legacy-visualization-20260614/` contains the old frontend implementation that was moved aside instead of deleted.
- Current backend state is in memory; persistent storage is a later product decision.
