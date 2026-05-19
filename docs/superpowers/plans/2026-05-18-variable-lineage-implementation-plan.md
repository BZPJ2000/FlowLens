# Variable Lineage Visualization Implementation Plan

Date: 2026-05-18

Source spec: `docs/superpowers/specs/2026-05-18-variable-lineage-visualization-design.md`

Status: planning only. Do not implement until this plan is approved.

## Goal

Replace the primary visualization direction with a variable-first lineage graph.

The implementation must not try to repair the old file-card graph into this shape. The old graph can remain for compatibility, but the new default visualization needs its own backend payload, layout algorithm, and React components.

## Non-Goals For First Pass

- Do not build a full compiler-grade control flow graph.
- Do not attempt perfect dataflow for every supported language.
- Do not remove the existing `/graph` endpoint.
- Do not delete existing graph components until the lineage canvas is working.
- Do not hide variables in the default view to make the graph look compact.

## Phase 1: Backend Lineage Schemas

Purpose: define the contract before extracting or rendering data.

Files to change:

- `backend/app/models/schemas.py`
- `frontend/src/types/index.ts`
- `backend/tests/test_lineage_schemas.py` or extend existing schema tests

Add backend schemas:

- `VariableNode`
- `OperationNode`
- `VariableEdge`
- `FileLane`
- `FlowStep`
- `LineageWarning`
- `VariableLineageGraph`
- enum fields for operation type, edge type, scope kind, evidence type

Add matching frontend TypeScript interfaces.

Acceptance checks:

- Backend schemas serialize to JSON without UUID/date surprises.
- Frontend types match backend field names exactly.
- Empty graph is valid.
- Unknown/fallback fields are explicit, not implicit `any`.

Risk:

- If this contract is too vague, implementation will drift back to file nodes.

## Phase 2: Parser Event Extraction

Purpose: collect variable-level events from source code.

Files to change:

- `backend/app/models/schemas.py`
- `backend/app/core/parser.py`
- `backend/app/core/ts_ast_parser.mjs`
- `backend/tests/test_parser.py`
- new focused parser fixtures inside tests if useful

Add parse output:

- `VariableEvent` or equivalent statement-level event model
- variable declarations
- assignments
- function parameters
- call expressions with argument order
- return statements
- import/export bindings
- destructuring targets
- object literal assembly
- member/field writes

TypeScript/JavaScript:

- Use Babel AST in `ts_ast_parser.mjs`.
- Include source line and scope name for each event.
- Preserve argument index for calls.
- Preserve destructuring field names where practical.

Python:

- Use Python `ast`.
- Extract `Assign`, `AnnAssign`, `FunctionDef`, `AsyncFunctionDef`, `Call`, `Return`, `Import`, `ImportFrom`, tuple/list destructuring, and attribute writes.

Other languages:

- Continue returning function/import/export level data.
- Add fallback events only where safe.

Acceptance checks:

- A TS function call `foo(a, b, c)` yields three argument events.
- A Python call `foo(a, b)` yields two argument events.
- Same variable name in two functions gets two different scopes.
- Destructuring records the parent and child names.
- Parser does not include config/test/generated files already filtered by source scanner.

Risk:

- Parser event extraction can grow large. Keep the event model narrow and aimed at visualization, not semantic execution.

## Phase 3: Lineage Builder

Purpose: transform parse events into the variable-first graph.

Files to add/change:

- `backend/app/core/lineage_builder.py`
- `backend/tests/test_lineage_builder.py`
- `backend/app/services/analyzer.py`

Responsibilities:

- Build deterministic variable IDs:
  `file_path + scope_kind + scope_name + variable_name + occurrence`
- Build file lanes from parsed files.
- Build operation nodes for import, export, parameter, assignment, call, return, destructure, field write, object build, merge, unknown transform.
- Build variable edges through operation nodes.
- Convert function call arguments into one edge per argument.
- Connect import/export boundaries without cross-file internal-function direct edges.
- Use AI analysis for labels/groups/descriptions only.
- Emit warnings for weak or missing evidence.
- Generate `FlowStep[]` for playback.

Acceptance checks:

- A function with N args has N separate `passes_arg` edges.
- Cross-file edges connect boundary variables, not internal function nodes.
- Assignment creates a target variable and an assignment operation.
- Return creates a return operation and output variable.
- Same-named variables in different scopes are separate.
- Builder output is stable across repeated runs on the same input.

Risk:

- Import/export matching from existing graph builder may be tempting to reuse directly. Reuse helper logic only where it supports variable boundaries.

## Phase 4: Persistence And API

Purpose: expose lineage graph without breaking existing API.

Files to change:

- `backend/app/db/models.py`
- `backend/app/db/repository.py`
- `backend/app/db/migrations/versions/003_lineage_graph.py`
- `backend/app/services/analyzer.py`
- `backend/app/api/routes.py`
- `backend/tests/test_db_models.py`
- `backend/tests/test_analyzer.py`

Add storage:

- Prefer one JSON/LONGTEXT column or table for the first version:
  `analysis_lineage_graphs`
  - `id`
  - `analysis_id`
  - `content_json`
  - `generated_at`

Add API:

```text
GET /api/v1/analyses/{analysis_id}/lineage-graph
```

Behavior:

- Return 404 if analysis does not exist.
- Return 404 or empty valid lineage graph if lineage was not generated; choose one behavior and document it in tests.
- Existing `/graph` remains unchanged.
- Failed analysis must rollback before recording failed state, following the earlier transaction fix pattern.

Acceptance checks:

- Completed analysis can return lineage graph.
- Old `/graph` endpoint still works.
- Large graph JSON persists without MySQL text truncation.
- API response matches frontend type names.

Risk:

- MySQL field size. Use `LONGTEXT` or JSON type that can handle large graphs.

## Phase 5: Frontend Store And Data Loading

Purpose: load lineage graph beside existing graph state.

Files to change:

- `frontend/src/types/index.ts`
- `frontend/src/stores/graphStore.ts`
- `frontend/src/api/client.ts`
- `frontend/src/pages/ReportPage.tsx`

Add state:

- `lineageGraph`
- `selectedVariableId`
- `selectedOperationId`
- `lineageFocusId`
- `activeFlowStepId`
- `lineagePlayOrder`
- loading/error state for lineage endpoint

Behavior:

- On completed analysis, fetch `/lineage-graph`.
- If lineage fetch succeeds, show lineage canvas as default.
- If lineage fetch fails because endpoint data is missing, fall back to existing `FlowCanvas` with a visible warning.

Acceptance checks:

- Existing import/progress flow still works.
- Existing report and chat panels are not broken.
- Default view switches to lineage graph only when payload exists.

Risk:

- UI can become confused if both graph types share selection IDs. Keep lineage selection separate.

## Phase 6: Lineage Layout Engine

Purpose: produce large, readable coordinates and routed edges.

Files to add:

- `frontend/src/components/lineage/lineageLayout.ts`
- `frontend/src/components/lineage/routeEdges.ts`
- `frontend/src/components/lineage/layoutTypes.ts`

Rules:

- Y axis: file lanes and variable tracks.
- X axis: operation order and variable lifetime stage.
- Each file lane grows vertically with variable count.
- Each variable gets a stable track.
- Operation nodes sit on the timeline inside file lanes.
- Cross-file edges use reserved corridors between file lanes.
- Parallel edges receive deterministic offsets.
- Do not try to fit graph into one viewport.

Acceptance checks:

- No two variable nodes start with the exact same coordinates.
- Parallel edges between similar points get different offsets.
- File lane height increases with variable count.
- Layout is deterministic for the same graph.
- Large graph produces large canvas, not unreadable overlap.

Risk:

- ReactFlow edge rendering may still visually overlap if paths are too close. Routing needs explicit channel spacing, not just Bezier curves.

## Phase 7: Lineage Rendering Components

Purpose: render the new graph clearly.

Files to add:

- `frontend/src/components/lineage/VariableLineageCanvas.tsx`
- `frontend/src/components/lineage/FileLaneNode.tsx`
- `frontend/src/components/lineage/VariableNode.tsx`
- `frontend/src/components/lineage/OperationNode.tsx`
- `frontend/src/components/lineage/LineageEdge.tsx`
- `frontend/src/components/lineage/LineageInspector.tsx`
- `frontend/src/components/lineage/LineagePlaybackControls.tsx`
- `frontend/src/components/lineage/index.ts`

Rendering priorities:

- Variable name and type are visually dominant.
- Files are subdued lane backgrounds.
- Operations are readable processing stations.
- Edge labels show variable name/type/evidence when zoom allows.
- Unknown or inferred edges look different from parser-proven edges.
- Use existing dark UI direction, but avoid decorative gradients or visual noise.

Acceptance checks:

- Variables are easier to see than file names.
- Clicking variable opens inspector.
- Clicking edge shows evidence and line/source context.
- Minimap and controls work on large canvas.
- Text does not overflow inside nodes at typical desktop widths.

Risk:

- Over-styling can reduce readability. Keep the UI utilitarian.

## Phase 8: Focus, Search, And Playback

Purpose: make a huge graph usable.

Files to change/add:

- `frontend/src/components/lineage/VariableLineageCanvas.tsx`
- `frontend/src/components/lineage/LineagePlaybackControls.tsx`
- `frontend/src/stores/graphStore.ts`
- existing search UI where applicable

Interactions:

- Search by variable name, data type, file path, scope, semantic group.
- Click variable highlights upstream/downstream lineage.
- Double-click variable focuses the full variable path.
- Edge click highlights source and target variables plus operation evidence.
- Playback follows `FlowStep[]`, not node array order.
- Active step centers or pans into view.
- Stop playback restores normal graph brightness.

Acceptance checks:

- Search for a known variable dims unrelated content.
- Playback highlights active file lane, variables, operations, and edges.
- Playback can pause/stop without leaving stale dimmed state.
- Double-click path tracing works across file boundaries.

Risk:

- Existing `FlowCanvas` selection effects should not be reused blindly because they assume file-node IDs.

## Phase 9: Integration And Default View Switch

Purpose: make lineage graph the main product experience.

Files to change:

- `frontend/src/pages/ReportPage.tsx`
- `frontend/src/components/graph/FlowCanvas.tsx` only if needed for fallback labels
- `frontend/src/components/common/DetailPanel.tsx` or new lineage inspector route

Behavior:

- Completed analysis opens lineage canvas by default.
- Existing file graph can be accessible as "overview" if useful.
- If lineage graph missing, explain fallback rather than failing blank.

Acceptance checks:

- New analysis displays lineage view.
- Old analysis without lineage graph still displays old graph.
- No blank canvas on missing or partial data.

Risk:

- If old and new views both appear equally primary, product direction becomes unclear. Make lineage the default.

## Phase 10: Verification

Backend commands:

```text
cd backend
pytest
```

Frontend commands:

```text
cd frontend
npm run build
```

Manual verification:

- Upload or import a small TS/JS fixture with multiple function args.
- Confirm every argument line is visible.
- Confirm internal assignment/return flow appears.
- Confirm cross-file flow uses boundary variables.
- Confirm a large existing project is navigable through minimap/search/playback.

Optional browser verification:

- Start dev servers.
- Use Playwright screenshot checks for desktop and mobile-width view.
- Verify no blank canvas and no obvious text overlap.

## First Implementation Slice

The first actual coding slice should be small enough to prove the model:

1. Add schemas and frontend types.
2. Extract TS/JS and Python function parameters, calls, assignments, and returns as variable events.
3. Build lineage graph for a tiny fixture.
4. Add `/lineage-graph`.
5. Render a basic large lineage canvas with variable nodes, operation nodes, and edges.

Only after this slice passes should styling, playback, and advanced routing be expanded.

## Stop Conditions

Pause and review before continuing if:

- The lineage model starts representing files as primary nodes again.
- Parser logic needs language-specific complexity beyond the first-pass scope.
- Layout needs hidden filtering to remain readable.
- The graph cannot show one edge per function argument.
- MySQL storage truncates lineage payloads.
- Frontend canvas becomes blank or unresponsive on a 200-file project.

