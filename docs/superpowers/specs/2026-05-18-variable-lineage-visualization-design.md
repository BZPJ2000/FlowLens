# Variable Lineage Visualization Design

Date: 2026-05-18

## Decision

Rebuild the main visualization around variables and data objects, not files.

The existing file-card dependency graph is kept only as compatibility data for reports and simple overview features. The new primary graph is a variable lineage graph: files become lanes, functions become processing stations, and variables become the visible subjects that connect the whole project.

This follows the product goal: help a developer understand how an AI-generated project actually runs by seeing where data is created, passed, modified, split, merged, returned, imported, exported, and consumed.

## Why The Current Graph Fails

The current backend model is centered on `GraphNode`, where each node is a file. Variables are stored as ports and edge labels. The current frontend layout then tries to place file cards, internal functions, class containers, and cross-file edges in the same compact graph.

That shape conflicts with the real requirement:

- A function with multiple arguments must receive multiple separate variable lines.
- Internal script flow matters as much as import/export flow.
- Cross-file flow must not jump directly from one internal function to another file's internal function.
- Showing all variables while avoiding edge overlap requires more space, not tighter packing.
- File names and function names are context; variable names and variable movement are the core content.

So the fix is not a better file-card layout. The model must change.

## Product Shape

The default view is a large scrollable and zoomable data circuit map.

The user accepts a very large canvas. The priority order is:

1. Show all source variables and data objects.
2. Keep variable names and types readable.
3. Keep lines separated enough to trace.
4. Preserve execution/data-flow direction.
5. Use search, focus, minimap, and playback to navigate the scale.

The graph is not optimized to fit one screen. Compactness is secondary to clarity.

## Visual Model

### Layer 1: File Lanes

Files are displayed as horizontal lanes or grouped bands. A file lane shows:

- file name
- relative path
- language
- architecture role when available
- entry/exit marker when relevant

Files are ordered top-to-bottom by dependency and inferred execution flow. Parallel files may share the same stage band, but must keep separate lanes.

### Layer 2: Processing Stations

Functions, methods, module-level blocks, imports, and exports are displayed as stations inside a file lane.

Stations are not the main subject. They exist to explain what happens to variables:

- parameter intake
- assignment
- call
- return
- destructuring
- field write
- object assembly
- export/import boundary

Constructors and lifecycle noise such as `__init__`, `constructor`, generated files, config files, tests, and build output continue to be filtered unless the parser can prove they are core application flow.

### Layer 3: Variable Tracks

Variables are the primary nodes.

A variable identity is scope-aware:

```text
file_path + scope_kind + scope_name + variable_name + occurrence
```

Examples:

```text
src/api/client.ts::function:request::data::1
src/stores/user.ts::module::<module>::token::1
src/model.py::method:UserService.load::result::2
```

This prevents unrelated variables with the same name from merging.

Each variable node displays:

- variable name
- data type when known
- source location when known
- owning file
- owning function or method
- semantic label from AI when available

AI labels can group or explain variables, but they do not create edges. Edges must come from parser evidence or deterministic graph construction.

## Lineage Data Model

Add a new graph payload alongside the existing file graph:

```text
VariableLineageGraph
  variables: VariableNode[]
  operations: OperationNode[]
  edges: VariableEdge[]
  lanes: FileLane[]
  play_steps: FlowStep[]
  warnings: LineageWarning[]
```

### VariableNode

```text
id
name
data_type
file_path
scope_kind: module | function | method | class
scope_name
line_start
line_end
semantic_group
is_external
is_entry
is_exit
fields[]
```

### OperationNode

```text
id
operation_type:
  import | export | parameter | assignment | call | return |
  destructure | field_write | object_build | merge | unknown_transform
label
file_path
scope_name
line
callee_name
```

### VariableEdge

```text
id
source_id
target_id
source_handle
target_handle
variable_name
data_type
edge_type:
  creates | assigns | passes_arg | returns | imports | exports |
  destructures | writes_field | builds_object | merges | consumes
argument_index
field_path
label
evidence
```

`evidence` records why the edge exists: import match, function call argument, assignment statement, return statement, AI fallback, or unknown fallback.

### FlowStep

```text
id
order
file_path
operation_id
active_variable_ids[]
active_edge_ids[]
description
```

Playback uses `FlowStep`, not arbitrary node order.

## Parser Strategy

The first implementation should support TypeScript, JavaScript, and Python deeply enough to satisfy the visual goal.

### TypeScript / JavaScript

Extend the existing Babel parser helper to extract:

- variable declarations
- assignment expressions
- function parameters
- call expressions with argument order
- return statements
- import/export bindings
- destructuring patterns
- object literals used as assembly points
- member writes such as `obj.field = value`

### Python

Extend the existing Python AST path to extract:

- assignments
- annotated assignments
- function parameters
- call expressions with argument order
- return statements
- imports
- destructuring assignment where AST exposes tuple/list targets
- attribute writes such as `obj.field = value`

### Other Languages

Other supported languages can initially fall back to:

- imports
- exports
- function signatures
- parameter-level edges
- return-level edges when available

They must still produce a lineage graph, but with `unknown_transform` operations where detailed statement parsing is not available.

## Edge Rules

These are hard rules:

- One function argument creates one `passes_arg` edge.
- A function with three input variables must show three incoming variable lines.
- A returned tuple may use one return edge only if the tuple/object contents are listed on the operation or expanded as fields.
- Cross-file flow connects file boundary variables, not internal function nodes across files.
- Internal file flow connects variables through operation nodes.
- Repeated parallel edges must receive separate routing lanes.
- Edges must not be hidden to reduce clutter in the default all-variable view.
- Filtering can dim or focus, but not silently remove data unless the user selects a filtered mode.

## Layout Rules

Use a dedicated lineage layout, not the existing `layout.ts` file-card algorithm.

The layout should use:

- Y axis for file lanes and parallel branches.
- X axis for variable lifetime stage and operation order.
- Dedicated per-variable tracks inside each lane.
- Reserved routing corridors between lanes and stations.
- Orthogonal or stepped paths with deterministic offsets.
- Wider spacing as edge count grows.

The layout must prefer clarity over canvas size. If a file has many variables, its lane becomes taller. If many edges cross between stages, the routing corridor becomes wider.

## Frontend Plan

Add a new graph surface:

```text
frontend/src/components/lineage/VariableLineageCanvas.tsx
```

Supporting modules:

```text
lineageLayout.ts
VariableNode.tsx
OperationNode.tsx
LineageEdge.tsx
LineageMiniMap.tsx
LineagePlaybackControls.tsx
LineageInspector.tsx
```

The current `FlowCanvas` can remain available as an overview, but the default completed-analysis view should use the new lineage canvas once the endpoint is available.

Interactions:

- search by variable, type, file, function, semantic group
- click variable to highlight upstream/downstream lineage
- double-click variable to focus full path
- click edge to show evidence and source location
- playback start/pause/stop
- minimap and fit-to-active-step
- dim unrelated graph elements during focus or playback

## Backend Plan

Add new schemas in `backend/app/models/schemas.py`.

Add a new builder:

```text
backend/app/core/lineage_builder.py
```

The builder consumes `ParseResult` and `AIFileAnalysis`, then emits `VariableLineageGraph`.

Add persistence either as:

- JSON column/table for the whole lineage graph per analysis, or
- normalized lineage tables if later querying requires it.

For the first version, JSON persistence is acceptable because the main consumer is the visualization endpoint.

Add endpoint:

```text
GET /api/v1/analyses/{analysis_id}/lineage-graph
```

The existing endpoint remains:

```text
GET /api/v1/analyses/{analysis_id}/graph
```

## AI Role

AI is useful for:

- summarizing a variable's meaning
- grouping semantically similar variables
- explaining unknown transforms
- enriching reports

AI is not allowed to invent edges as the primary source of truth. If AI proposes a connection, it must be marked as low-confidence evidence and rendered differently.

## Error Handling

If parsing fails for a file:

- keep the file lane
- show a warning marker
- use import/export/function-signature fallback if possible
- do not block the whole graph

If edge evidence is weak:

- keep the edge only if it is useful
- mark it as inferred or low confidence
- let the inspector explain the reason

If the graph is huge:

- do not truncate the default visualization data
- warn about scale
- keep rendering navigable through zoom, minimap, search, and focus

## Testing

Backend tests:

- TS/JS function call with multiple args creates multiple edges.
- Python call with multiple args creates multiple edges.
- Assignment creates a source variable, operation, and target variable.
- Return creates a return operation and output variable.
- Destructuring creates split variable edges.
- Cross-file import/export connects boundary variables only.
- Same variable name in two scopes creates two distinct variable IDs.
- Parser fallback still returns a valid lineage graph.

Frontend tests or verification:

- all variables from fixture appear in the canvas data
- parallel edges receive different route offsets
- search finds variable names and types
- clicking a variable highlights upstream/downstream paths
- playback activates `FlowStep` order, not raw node array order
- large fixture remains navigable with minimap and zoom

## Acceptance Criteria

The redesign is successful when:

- Variables, not files, are visually dominant.
- A function with N input variables shows N incoming lines.
- Internal script lines connect through statement-level operations.
- Cross-file lines do not jump directly from internal function to internal function.
- Same-named variables in different scopes are separate.
- The default view can be very large and still readable through navigation tools.
- Playback visually follows data movement from entry toward exits.
- The old file-card graph no longer controls the primary visualization direction.

## Implementation Order

1. Add lineage schemas and tests.
2. Extend parser output with statement-level variable events for TS/JS and Python.
3. Build `lineage_builder.py`.
4. Add persistence and `/lineage-graph` endpoint.
5. Add frontend lineage types and store state.
6. Build lineage layout and rendering components.
7. Add focus/search/playback interactions.
8. Make lineage canvas the default completed-analysis visualization.

