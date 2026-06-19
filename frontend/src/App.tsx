import "@xyflow/react/dist/style.css";

import {
  Background,
  Controls,
  Handle,
  MiniMap,
  Position,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import * as dagre from "dagre";
import {
  AlertCircle,
  Archive,
  Boxes,
  Braces,
  ChevronRight,
  CircleDot,
  Code2,
  FileCode2,
  Folder,
  FolderTree,
  GitPullRequestArrow,
  History,
  Layers3,
  Loader2,
  LocateFixed,
  Network,
  PanelRight,
  Play,
  RefreshCcw,
  Search,
  Variable,
  X,
} from "lucide-react";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type DragEvent,
  type ReactNode,
} from "react";

import { api } from "./api/client";
import {
  buildCodeGraphModel,
  getGraphStats,
  getNodeNeighborhood,
  searchNodes,
  type CodeEdgeKind,
  type CodeGraphEdge,
  type CodeGraphModel,
  type CodeGraphNode,
  type CodeNodeKind,
} from "./lib/graphModel";
import type {
  AnalysisProgress,
  AnalysisStatus,
  DataFlowGraph,
  ProjectFile,
  ProjectSummary,
  SourceFile,
} from "./types";

type ImportMode = "local" | "archive";
type GraphView = "overview" | "files" | "symbols" | "data";
type TreeNode = {
  id: string;
  name: string;
  path: string;
  kind: "folder" | "file";
  file?: ProjectFile;
  fileCount: number;
  symbolCount: number;
  children: TreeNode[];
};
type SourcePreview = {
  nodeId: string;
  title: string;
  filePath: string;
  startLine: number | null;
  endLine: number | null;
  source: SourceFile | null;
  loading: boolean;
  error: string;
};
type FlowNodeData = {
  codeNode: CodeGraphNode;
  selected: boolean;
  related: boolean;
  onOpenSource: (node: CodeGraphNode) => void;
};

const DEFAULT_SOURCE_PATH = "E:\\Github_Project\\FlowLens";

const KIND_NAME: Record<CodeNodeKind, string> = {
  folder: "目录",
  file: "文件",
  class: "类",
  function: "函数",
  method: "方法",
  variable: "变量",
};

const EDGE_NAME: Record<CodeEdgeKind, string> = {
  contains: "包含",
  call: "调用",
  arg: "传参",
  return: "返回",
  unresolved: "未解析",
  reference: "引用",
};

const KIND_ICON: Record<CodeNodeKind, ReactNode> = {
  folder: <Folder size={15} />,
  file: <FileCode2 size={15} />,
  class: <Boxes size={15} />,
  function: <Code2 size={15} />,
  method: <Braces size={15} />,
  variable: <Variable size={15} />,
};

const VIEW_META: Record<
  GraphView,
  {
    label: string;
    description: string;
    nodeKinds: CodeNodeKind[];
    edgeKinds: CodeEdgeKind[];
    budget: number;
  }
> = {
  overview: {
    label: "总览",
    description: "目录、文件，以及聚合后的文件依赖关系。",
    nodeKinds: ["folder", "file"],
    edgeKinds: ["contains", "call", "unresolved", "reference"],
    budget: 120,
  },
  files: {
    label: "文件",
    description: "目录层级、文件、类，以及文件归属结构。",
    nodeKinds: ["folder", "file", "class"],
    edgeKinds: ["contains", "call", "unresolved", "reference"],
    budget: 150,
  },
  symbols: {
    label: "符号",
    description: "脚本内的类、函数、方法，以及调用、传参和返回关系。",
    nodeKinds: ["file", "class", "function", "method", "variable"],
    edgeKinds: ["contains", "call", "arg", "return", "unresolved", "reference"],
    budget: 240,
  },
  data: {
    label: "数据",
    description: "函数、变量、参数传递和返回值流向。",
    nodeKinds: ["file", "function", "method", "variable"],
    edgeKinds: ["arg", "return"],
    budget: 180,
  },
};

export default function App() {
  const [importMode, setImportMode] = useState<ImportMode>("local");
  const [sourcePath, setSourcePath] = useState(DEFAULT_SOURCE_PATH);
  const [analysisId, setAnalysisId] = useState<string | null>(null);
  const [status, setStatus] = useState<AnalysisStatus | "idle">("idle");
  const [progress, setProgress] = useState<AnalysisProgress | null>(null);
  const [graph, setGraph] = useState<DataFlowGraph | null>(null);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [graphView, setGraphView] = useState<GraphView>("overview");
  const [focusedPath, setFocusedPath] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showInspector, setShowInspector] = useState(true);
  const [sourcePreview, setSourcePreview] = useState<SourcePreview | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const model = useMemo(() => buildCodeGraphModel(graph), [graph]);
  const stats = useMemo(() => getGraphStats(model), [model]);
  const tree = useMemo(() => buildTree(model.projectFiles), [model.projectFiles]);
  const visibleModel = useMemo(
    () => projectModelForView(model, graphView, query, focusedPath, selectedId),
    [focusedPath, graphView, model, query, selectedId],
  );
  const visibleNodeIds = useMemo(
    () => new Set(visibleModel.nodes.map((node) => node.id)),
    [visibleModel.nodes],
  );
  const nodeById = useMemo(() => new Map(model.nodes.map((node) => [node.id, node])), [model.nodes]);
  const selectedNode = selectedId ? nodeById.get(selectedId) ?? null : null;
  const neighborhood = useMemo(() => getNodeNeighborhood(model, selectedId), [model, selectedId]);
  const searchResults = useMemo(() => searchNodes(model, query), [model, query]);
  const hasGraph = model.nodes.length > 0;
  const progressValue = progress?.progress_pct ?? (status === "completed" ? 100 : 0);

  useEffect(() => {
    void refreshProjects();
  }, []);

  useEffect(() => {
    if (!selectedId || visibleNodeIds.has(selectedId)) return;
    setSelectedId(visibleModel.nodes[0]?.id ?? null);
  }, [selectedId, visibleModel.nodes, visibleNodeIds]);

  useEffect(() => {
    if (!sourcePreview) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setSourcePreview(null);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [sourcePreview]);

  const refreshProjects = useCallback(async () => {
    try {
      setProjects(await api.listProjects());
    } catch {
      setProjects([]);
    }
  }, []);

  const loadGraph = useCallback(async (id: string) => {
    const payload = await api.getGraph(id);
    setGraph(payload);
    setStatus("completed");
    setProgress({
      id,
      status: "completed",
      progress_pct: 100,
      message: "图谱已就绪",
      file_count: payload.project_files?.length ?? payload.nodes.length,
    });
    setSelectedId(null);
    setFocusedPath(null);
  }, []);

  const watchAnalysis = useCallback(
    (id: string) => {
      let closed = false;
      const events = api.streamProgress(
        id,
        (next) => {
          setProgress(next);
          setStatus(next.status);
          if (next.status === "completed") {
            closed = true;
            events.close();
            loadGraph(id).catch((err: unknown) => {
              setError(err instanceof Error ? err.message : "读取图谱失败");
              setStatus("failed");
            });
            void refreshProjects();
          }
          if (next.status === "failed") {
            closed = true;
            events.close();
            setError(next.error_message || next.message || "分析失败");
            void refreshProjects();
          }
        },
        () => {
          if (!closed) {
            void pollAnalysis(id, loadGraph, setProgress, setStatus, setError, refreshProjects);
          }
        },
      );
    },
    [loadGraph, refreshProjects],
  );

  const startImport = useCallback(
    async (file?: File) => {
      setError("");
      setGraph(null);
      setSelectedId(null);
      setFocusedPath(null);
      setStatus("pending");
      setProgress({ status: "pending", progress_pct: 0, message: "正在提交分析任务" });
      try {
        const result = file ? await api.importArchive(file) : await api.importLocalPath(sourcePath.trim());
        setAnalysisId(result.analysis_id);
        watchAnalysis(result.analysis_id);
      } catch (err: unknown) {
        setStatus("failed");
        setError(err instanceof Error ? err.message : "导入失败");
      }
    },
    [sourcePath, watchAnalysis],
  );

  const loadExistingAnalysis = useCallback(
    async (id: string) => {
      setError("");
      setAnalysisId(id);
      setStatus("building");
      setProgress({ id, status: "building", progress_pct: 80, message: "正在读取历史图谱" });
      try {
        await loadGraph(id);
      } catch (err: unknown) {
        setStatus("failed");
        setError(err instanceof Error ? err.message : "读取历史图谱失败");
      }
    },
    [loadGraph],
  );

  const onDrop = useCallback(
    (event: DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      setDragOver(false);
      const file = event.dataTransfer.files[0];
      if (file) {
        setImportMode("archive");
        void startImport(file);
      }
    },
    [startImport],
  );

  const focusFolder = useCallback((path: string | null) => {
    setFocusedPath((current) => (current === path ? null : path));
    setGraphView("files");
    setSelectedId(path ? `folder:${path}` : null);
  }, []);

  const focusFile = useCallback((file: ProjectFile) => {
    setFocusedPath(file.file_path);
    setGraphView("symbols");
    setSelectedId(file.id);
  }, []);

  const openSource = useCallback(
    async (node: CodeGraphNode) => {
      if (!analysisId || !node.filePath) return;
      setSourcePreview({
        nodeId: node.id,
        title: node.qualifiedName || node.label,
        filePath: node.filePath,
        startLine: node.startLine ?? null,
        endLine: node.endLine ?? null,
        source: null,
        loading: true,
        error: "",
      });
      try {
        const source = await api.getSource(
          analysisId,
          node.filePath,
          node.startLine ?? undefined,
          node.endLine ?? undefined,
        );
        setSourcePreview((current) =>
          current?.nodeId === node.id ? { ...current, source, loading: false, error: "" } : current,
        );
      } catch (err: unknown) {
        setSourcePreview((current) =>
          current?.nodeId === node.id
            ? {
                ...current,
                loading: false,
                error: err instanceof Error ? err.message : "读取源码失败",
              }
            : current,
        );
      }
    },
    [analysisId],
  );

  return (
    <main className="app-shell">
      <aside className="left-rail">
        <div className="brand-block">
          <div className="brand-mark">
            <Network size={18} />
          </div>
          <div>
            <strong>FlowLens</strong>
            <span>代码图谱工作台</span>
          </div>
        </div>

        <section
          className={`import-block ${dragOver ? "drag-over" : ""}`}
          onDragOver={(event) => {
            event.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
        >
          <div className="section-head">
            <span>
              <Play size={14} />
              分析项目
            </span>
            <button className="icon-button" onClick={refreshProjects} title="刷新历史">
              <RefreshCcw size={14} />
            </button>
          </div>

          <div className="mode-tabs">
            <button className={importMode === "local" ? "active" : ""} onClick={() => setImportMode("local")}>
              本地路径
            </button>
            <button className={importMode === "archive" ? "active" : ""} onClick={() => setImportMode("archive")}>
              压缩包
            </button>
          </div>

          {importMode === "local" ? (
            <div className="import-row">
              <input value={sourcePath} onChange={(event) => setSourcePath(event.target.value)} />
              <button className="primary-action" onClick={() => void startImport()}>
                <GitPullRequestArrow size={15} />
                分析
              </button>
            </div>
          ) : (
            <button className="upload-target" onClick={() => fileInputRef.current?.click()}>
              <Archive size={16} />
              选择 .zip/.tar.gz
            </button>
          )}

          <input
            ref={fileInputRef}
            type="file"
            accept=".zip,.tar,.gz,.tgz"
            hidden
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) void startImport(file);
            }}
          />
          <ProgressMeter status={status} value={progressValue} message={progress?.message || error} />
        </section>

        <section className="history-block">
          <div className="section-head">
            <span>
              <History size={14} />
              历史项目
            </span>
            <small>{projects.length}</small>
          </div>
          <div className="history-list">
            {projects.slice(0, 10).map((project) => (
              <button
                key={project.project_id}
                className={
                  project.latest_analysis?.analysis_id === analysisId ? "history-item active" : "history-item"
                }
                onClick={() => {
                  const id = project.latest_analysis?.analysis_id;
                  if (id) void loadExistingAnalysis(id);
                }}
              >
                <strong>{project.name}</strong>
                <span>
                  {project.file_count} 个文件 · {project.latest_analysis ? statusLabel(project.latest_analysis.status) : "暂无分析"}
                </span>
              </button>
            ))}
            {projects.length === 0 ? <p className="empty-copy">暂无历史项目。</p> : null}
          </div>
        </section>

        <section className="tree-block">
          <div className="section-head">
            <span>
              <FolderTree size={14} />
              项目文件树
            </span>
            <small>{stats.fileCount}</small>
          </div>
          <div className="tree-scroll">
            {tree.children.length ? (
              <TreeView
                nodes={tree.children}
                focusedPath={focusedPath}
                onFocusFolder={focusFolder}
                onSelectFile={focusFile}
              />
            ) : (
              <p className="empty-copy">导入项目后查看目录和文件。</p>
            )}
          </div>
        </section>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div className="search-box">
            <Search size={16} />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="搜索文件、类、函数、变量、路径"
            />
            {query ? (
              <button className="icon-button" onClick={() => setQuery("")} title="清空搜索">
                <X size={14} />
              </button>
            ) : null}
          </div>

          <div className="toolbar-group">
            <ViewButton current={graphView} value="overview" onChange={setGraphView} icon={<Layers3 size={14} />} />
            <ViewButton current={graphView} value="files" onChange={setGraphView} icon={<FolderTree size={14} />} />
            <ViewButton current={graphView} value="symbols" onChange={setGraphView} icon={<Code2 size={14} />} />
            <ViewButton current={graphView} value="data" onChange={setGraphView} icon={<Variable size={14} />} />
          </div>

          <button
            className={`panel-toggle ${showInspector ? "active" : ""}`}
            onClick={() => setShowInspector((value) => !value)}
          >
            <PanelRight size={15} />
            检查器
          </button>
        </header>

        <div className="status-strip">
          <Metric label="目录" value={stats.folderCount} />
          <Metric label="文件" value={stats.fileCount} />
          <Metric label="类" value={stats.classCount} />
          <Metric label="函数" value={stats.functionCount + stats.methodCount} />
          <Metric label="变量" value={stats.variableCount} />
          <Metric label="关系" value={stats.edgeCount} />
          <div className="strip-note">
            {hasGraph
              ? `${VIEW_META[graphView].label}: ${visibleModel.nodes.length} nodes / ${visibleModel.edges.length} edges`
              : "等待项目图谱生成。"}
          </div>
        </div>

        <div className={showInspector ? "main-grid with-inspector" : "main-grid"}>
          <section className="canvas-column">
            <div className="canvas-toolbar">
              <div>
                <strong>{focusedPath ? "脚本详情" : VIEW_META[graphView].label}</strong>
                <span>{focusedPath ? `当前脚本/目录：${focusedPath}` : VIEW_META[graphView].description}</span>
              </div>
              <ViewLegend view={graphView} />
            </div>

            <div className="canvas-frame">
              {hasGraph ? (
                <ReactFlowProvider>
                  <GraphCanvas
                    key={`${graphView}:${focusedPath ?? "root"}:${query}`}
                    model={visibleModel}
                    selectedId={selectedId}
                    relatedIds={neighborhood.relatedIds}
                    onSelect={setSelectedId}
                    onOpenSource={openSource}
                  />
                </ReactFlowProvider>
              ) : (
                <EmptyCanvas error={error} status={status} />
              )}
            </div>
          </section>

          {showInspector ? (
            <aside className="inspector-panel">
              <Inspector
                node={selectedNode}
                model={model}
                neighborhood={neighborhood}
                searchResults={searchResults}
                query={query}
                onSelect={setSelectedId}
                onOpenSource={openSource}
              />
            </aside>
          ) : null}
        </div>
      </section>

      {sourcePreview ? <SourceModal preview={sourcePreview} onClose={() => setSourcePreview(null)} /> : null}
    </main>
  );
}

function GraphCanvas({
  model,
  selectedId,
  relatedIds,
  onSelect,
  onOpenSource,
}: {
  model: CodeGraphModel;
  selectedId: string | null;
  relatedIds: Set<string>;
  onSelect: (id: string) => void;
  onOpenSource: (node: CodeGraphNode) => void;
}) {
  const flow = useReactFlow();
  const nodeById = useMemo(() => new Map(model.nodes.map((node) => [node.id, node])), [model.nodes]);
  const nodeTypes = useMemo(() => ({ codeNode: CodeFlowNode }), []);
  const { nodes, edges } = useMemo(
    () => toFlowElements(model, selectedId, relatedIds, onOpenSource),
    [model, onOpenSource, relatedIds, selectedId],
  );

  useEffect(() => {
    const minReadableZoom = model.nodes.length > 90 ? 0.38 : 0.28;
    const timer = window.setTimeout(
      () => flow.fitView({ padding: 0.14, duration: 220, minZoom: minReadableZoom }),
      80,
    );
    return () => window.clearTimeout(timer);
  }, [flow, model.nodes.length, nodes.length, edges.length]);

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      fitView
      minZoom={0.32}
      maxZoom={1.8}
      onNodeClick={(_, node) => onSelect(node.id)}
      onNodeDoubleClick={(event, node) => {
        event.preventDefault();
        const codeNode = (node.data as { codeNode?: CodeGraphNode }).codeNode ?? nodeById.get(node.id);
        if (codeNode?.filePath) {
          onOpenSource(codeNode);
        }
      }}
      nodeTypes={nodeTypes}
      nodesDraggable
      nodesConnectable={false}
      elementsSelectable
    >
      <Background gap={28} size={1} color="#27313b" />
      <Controls position="bottom-left" />
      <MiniMap
        position="bottom-right"
        pannable
        zoomable
        nodeColor={(node) => String(node.data?.color ?? "#718096")}
        maskColor="rgba(6, 10, 15, 0.72)"
      />
    </ReactFlow>
  );
}

function Inspector({
  node,
  model,
  neighborhood,
  searchResults,
  query,
  onSelect,
  onOpenSource,
}: {
  node: CodeGraphNode | null;
  model: CodeGraphModel;
  neighborhood: ReturnType<typeof getNodeNeighborhood>;
  searchResults: CodeGraphNode[];
  query: string;
  onSelect: (id: string) => void;
  onOpenSource: (node: CodeGraphNode) => void;
}) {
  const nodeById = useMemo(() => new Map(model.nodes.map((item) => [item.id, item])), [model.nodes]);

  if (!node) {
    return (
      <div className="inspector empty">
        <CircleDot size={22} />
        <strong>选择一个节点</strong>
        <span>点击节点查看直接关系；双击文件、类、函数或方法可定位源码。</span>
        {query.trim() ? (
          <div className="search-results">
            {searchResults.map((result) => (
              <button key={result.id} onClick={() => onSelect(result.id)}>
                <span>{KIND_NAME[result.kind]}</span>
                <strong>{result.label}</strong>
                <small>{result.subtitle}</small>
              </button>
            ))}
          </div>
        ) : null}
      </div>
    );
  }

  const relatedEdges = [...neighborhood.outgoing, ...neighborhood.incoming].slice(0, 80);

  return (
    <div className="inspector">
      <div className="inspector-title">
        <div className={`inspector-icon ${node.kind}`}>{KIND_ICON[node.kind]}</div>
        <div>
          <span>{KIND_NAME[node.kind]}</span>
          <h2>{node.label}</h2>
          <p>{node.qualifiedName || node.filePath || node.folderPath || node.subtitle}</p>
        </div>
      </div>

      <div className="detail-grid">
        <Detail label="语言" value={node.language || "-"} />
        <Detail label="角色" value={node.role || "-"} />
        <Detail label="符号数" value={node.symbolCount ?? "-"} />
        <Detail label="关系数" value={node.edgeCount} />
      </div>

      {node.params?.length ? (
        <section className="detail-section">
          <h3>参数</h3>
          <div className="chips">
            {node.params.map((param) => (
              <span key={`${param.name}:${param.type}`}>
                {param.name}: {param.type || "Unknown"}
              </span>
            ))}
          </div>
        </section>
      ) : null}

      {node.returnType ? (
        <section className="detail-section">
          <h3>返回/类型</h3>
          <code>{node.returnType}</code>
        </section>
      ) : null}

      {node.filePath ? (
        <section className="detail-section">
          <h3>位置</h3>
          <p className="path-copy">{node.filePath}</p>
          <div className="button-row">
            <button onClick={() => void onOpenSource(node)}>
              <LocateFixed size={14} />
              定位源码
            </button>
          </div>
        </section>
      ) : null}

      {node.kind === "file" ? (
        <FileContents node={node} model={model} onSelect={onSelect} />
      ) : null}

      <section className="detail-section relations">
        <h3>直接关系</h3>
        {relatedEdges.length ? (
          relatedEdges.map((edge) => {
            const isOutgoing = edge.source === node.id;
            const otherId = isOutgoing ? edge.target : edge.source;
            const other = nodeById.get(otherId);
            return (
              <button key={edge.id} onClick={() => onSelect(otherId)}>
                <i className={edge.kind} />
                <div>
                  <strong>
                    {isOutgoing ? "out" : "in"} · {EDGE_NAME[edge.kind]}
                  </strong>
                  <span>{other?.label ?? otherId}</span>
                </div>
                <small>{edge.lineNumber ? `L${edge.lineNumber}` : edge.label}</small>
              </button>
            );
          })
        ) : (
          <p className="empty-copy">没有直接关系。</p>
        )}
      </section>
    </div>
  );
}

function ViewButton({
  current,
  value,
  onChange,
  icon,
}: {
  current: GraphView;
  value: GraphView;
  onChange: (value: GraphView) => void;
  icon: ReactNode;
}) {
  return (
    <button className={current === value ? "active" : ""} onClick={() => onChange(value)} title={VIEW_META[value].description}>
      {icon}
      {VIEW_META[value].label}
    </button>
  );
}

function FileContents({
  node,
  model,
  onSelect,
}: {
  node: CodeGraphNode;
  model: CodeGraphModel;
  onSelect: (id: string) => void;
}) {
  const symbols = model.symbols
    .filter((symbol) => symbol.fileId === node.id || symbol.filePath === node.filePath)
    .sort((a, b) => {
      const lineA = a.startLine ?? Number.MAX_SAFE_INTEGER;
      const lineB = b.startLine ?? Number.MAX_SAFE_INTEGER;
      return lineA - lineB || a.label.localeCompare(b.label);
    });
  const dataEdges = model.edges.filter((edge) => {
    if (edge.kind !== "arg" && edge.kind !== "return") return false;
    const source = model.nodes.find((item) => item.id === edge.source);
    const target = model.nodes.find((item) => item.id === edge.target);
    return source?.fileId === node.id || target?.fileId === node.id;
  });
  const nodeById = new Map(model.nodes.map((item) => [item.id, item]));

  return (
    <>
      <section className="detail-section file-symbols">
        <h3>脚本符号 ({symbols.length})</h3>
        <div className="file-list">
          {symbols.length ? (
            symbols.slice(0, 80).map((symbol) => (
              <button key={symbol.id} onClick={() => onSelect(symbol.id)}>
                <i className={symbol.kind} />
                <div>
                  <strong>{symbol.label}</strong>
                  <span>
                    {KIND_NAME[symbol.kind]}
                    {symbol.startLine ? ` · L${symbol.startLine}` : ""}
                  </span>
                </div>
              </button>
            ))
          ) : (
            <p className="empty-copy">这个脚本没有识别到函数、类或方法。</p>
          )}
        </div>
      </section>

      <section className="detail-section file-symbols">
        <h3>传值关系 ({dataEdges.length})</h3>
        <div className="file-list">
          {dataEdges.length ? (
            dataEdges.slice(0, 80).map((edge) => {
              const source = nodeById.get(edge.source);
              const target = nodeById.get(edge.target);
              return (
                <button key={edge.id} onClick={() => onSelect(edge.source)}>
                  <i className={edge.kind} />
                  <div>
                    <strong>{EDGE_NAME[edge.kind]}</strong>
                    <span>{`${source?.label ?? edge.source} -> ${target?.label ?? edge.target} · ${edge.label}`}</span>
                  </div>
                </button>
              );
            })
          ) : (
            <p className="empty-copy">这个脚本暂时没有解析到传参或返回值关系。</p>
          )}
        </div>
      </section>
    </>
  );
}

function ViewLegend({ view }: { view: GraphView }) {
  return (
    <div className="filter-popover">
      <span>节点</span>
      <div className="filter-pills">
        {VIEW_META[view].nodeKinds.map((kind) => (
          <button key={kind} className="active" disabled>
            {KIND_NAME[kind]}
          </button>
        ))}
      </div>
      <span>关系</span>
      <div className="filter-pills">
        {VIEW_META[view].edgeKinds.map((kind) => (
          <button key={kind} className="active" disabled>
            {EDGE_NAME[kind]}
          </button>
        ))}
      </div>
    </div>
  );
}

function TreeView({
  nodes,
  focusedPath,
  onFocusFolder,
  onSelectFile,
  depth = 0,
}: {
  nodes: TreeNode[];
  focusedPath: string | null;
  onFocusFolder: (path: string | null) => void;
  onSelectFile: (file: ProjectFile) => void;
  depth?: number;
}) {
  return (
    <>
      {nodes.map((node) => (
        <div key={node.id}>
          <button
            className={`tree-row ${focusedPath === node.path ? "active" : ""}`}
            style={{ paddingLeft: 8 + depth * 14 }}
            onClick={() => {
              if (node.kind === "file" && node.file) {
                onSelectFile(node.file);
              } else {
                onFocusFolder(node.path || null);
              }
            }}
          >
            {node.kind === "folder" ? <ChevronRight size={12} /> : <FileCode2 size={12} />}
            <span>{node.name}</span>
            <small>{node.kind === "folder" ? node.fileCount : node.symbolCount}</small>
          </button>
          {node.children.length ? (
            <TreeView
              nodes={node.children}
              focusedPath={focusedPath}
              onFocusFolder={onFocusFolder}
              onSelectFile={onSelectFile}
              depth={depth + 1}
            />
          ) : null}
        </div>
      ))}
    </>
  );
}

function SourceModal({ preview, onClose }: { preview: SourcePreview; onClose: () => void }) {
  const lines = preview.source?.content.split("\n") ?? [];
  const start = preview.source?.start_line ?? 1;
  const focusedLineRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!preview.loading && focusedLineRef.current) {
      focusedLineRef.current.scrollIntoView({ block: "center" });
    }
  }, [preview.loading, preview.source?.content]);

  return (
    <div className="source-backdrop" onClick={onClose}>
      <section className="source-modal" onClick={(event) => event.stopPropagation()}>
        <header>
          <div>
            <strong>{preview.title}</strong>
            <span>{preview.filePath}</span>
          </div>
          <button className="icon-button" onClick={onClose}>
            <X size={16} />
          </button>
        </header>
        {preview.loading ? (
          <div className="source-state">
            <Loader2 size={18} className="spin" />
            正在读取源码
          </div>
        ) : preview.error ? (
          <div className="source-state error">
            <AlertCircle size={18} />
            {preview.error}
          </div>
        ) : (
          <pre className="source-code">
            {lines.map((line, index) => {
              const lineNumber = start + index;
              const focused =
                preview.startLine != null &&
                preview.endLine != null &&
                lineNumber >= preview.startLine &&
                lineNumber <= preview.endLine;
              return (
                <div
                  key={lineNumber}
                  ref={focused && lineNumber === preview.startLine ? focusedLineRef : undefined}
                  className={focused ? "source-line focus" : "source-line"}
                >
                  <span>{lineNumber}</span>
                  <code>{line || " "}</code>
                </div>
              );
            })}
          </pre>
        )}
      </section>
    </div>
  );
}

function ProgressMeter({
  status,
  value,
  message,
}: {
  status: AnalysisStatus | "idle";
  value: number;
  message?: string;
}) {
  return (
    <div className="progress-box">
      <div className="progress-head">
        <span className={`status-dot ${status}`} />
        <strong>{status === "idle" ? "未开始" : statusLabel(status)}</strong>
        <small>{Math.round(value)}%</small>
      </div>
      <div className="progress-track">
        <i style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
      </div>
      {message ? <p>{message}</p> : null}
    </div>
  );
}

function EmptyCanvas({ error, status }: { error: string; status: AnalysisStatus | "idle" }) {
  return (
    <div className="empty-canvas">
      {status !== "idle" && status !== "failed" ? <Loader2 size={32} className="spin" /> : <Network size={34} />}
      <strong>{error ? "图谱生成失败" : "导入项目后生成代码图谱"}</strong>
      <span>{error || "目录、文件、类、函数、变量和关系会显示在这里。"}</span>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value.toLocaleString()}</strong>
    </div>
  );
}

function statusLabel(status: AnalysisStatus | "idle"): string {
  return {
    idle: "未开始",
    pending: "排队中",
    parsing: "解析中",
    analyzing: "分析中",
    building: "构建中",
    completed: "完成",
    failed: "失败",
  }[status];
}

function Detail({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="detail">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function toFlowElements(
  model: CodeGraphModel,
  selectedId: string | null,
  relatedIds: Set<string>,
  onOpenSource: (node: CodeGraphNode) => void,
): { nodes: Node[]; edges: Edge[] } {
  const graph = new dagre.graphlib.Graph();
  graph.setDefaultEdgeLabel(() => ({}));
  graph.setGraph({ rankdir: "LR", ranksep: 78, nodesep: 34, edgesep: 16, marginx: 28, marginy: 28 });

  for (const node of model.nodes) {
    graph.setNode(node.id, nodeSize(node.kind));
  }
  for (const edge of model.edges) {
    graph.setEdge(edge.source, edge.target);
  }
  dagre.layout(graph);

  const nodes: Node[] = model.nodes.map((node) => {
    const positioned = graph.node(node.id) as { x: number; y: number } | undefined;
    const size = nodeSize(node.kind);
    const selected = node.id === selectedId;
    const related = relatedIds.has(node.id);
    return {
      id: node.id,
      position: {
        x: (positioned?.x ?? 0) - size.width / 2,
        y: (positioned?.y ?? 0) - size.height / 2,
      },
      type: "codeNode",
      data: {
        codeNode: node,
        selected,
        related,
        onOpenSource,
        color: nodeColor(node.kind),
      },
      width: size.width,
      height: size.height,
      className: `flow-card ${node.kind} ${selected ? "selected" : ""} ${related ? "related" : ""}`,
      style: {
        width: size.width,
        height: size.height,
        border: "none",
        background: "transparent",
        padding: 0,
      },
    };
  });

  const edges: Edge[] = model.edges.map((edge) => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    type: edge.kind === "contains" ? "smoothstep" : "default",
    animated: edge.kind === "call" || edge.kind === "arg" || edge.kind === "return",
    label: edge.kind === "contains" ? undefined : shortLabel(edge.label),
    className: `graph-edge ${edge.kind}`,
    style: {
      stroke: edgeColor(edge.kind),
      strokeWidth: edge.kind === "contains" ? 1.25 : 2.1,
      opacity: selectedId && (edge.source === selectedId || edge.target === selectedId) ? 1 : 0.78,
    },
    labelStyle: { fill: "#b9c4d0", fontSize: 10, fontWeight: 700 },
    labelBgStyle: { fill: "#0b1118", fillOpacity: 0.88 },
  }));

  return { nodes, edges };
}

function CodeFlowNode({ data }: NodeProps<Node<FlowNodeData>>) {
  const { codeNode: node, selected, related, onOpenSource } = data;
  return (
    <div
      className={`node-body nodrag nopan ${node.kind} ${selected ? "selected" : ""} ${related ? "related" : ""}`}
      title={node.filePath ? "双击定位源码" : undefined}
      onClick={(event) => {
        if (event.detail >= 2) {
          event.stopPropagation();
          if (node.filePath) onOpenSource(node);
        }
      }}
      onDoubleClick={(event) => {
        event.stopPropagation();
        if (node.filePath) onOpenSource(node);
      }}
    >
      <Handle type="target" position={Position.Left} />
      <div className="node-icon">{KIND_ICON[node.kind]}</div>
      <div className="node-text">
        <strong>{node.label}</strong>
        <span>{node.subtitle}</span>
      </div>
      <small>{node.edgeCount}</small>
      <Handle type="source" position={Position.Right} />
    </div>
  );
}

async function pollAnalysis(
  id: string,
  loadGraph: (id: string) => Promise<void>,
  setProgress: (progress: AnalysisProgress) => void,
  setStatus: (status: AnalysisStatus | "idle") => void,
  setError: (error: string) => void,
  refreshProjects: () => Promise<void>,
) {
  for (let index = 0; index < 160; index += 1) {
    await new Promise((resolve) => window.setTimeout(resolve, 1000));
    const progress = await api.getAnalysis(id);
    setProgress(progress);
    setStatus(progress.status);
    if (progress.status === "completed") {
      await loadGraph(id);
      await refreshProjects();
      return;
    }
    if (progress.status === "failed") {
      setError(progress.error_message || progress.message || "分析失败");
      await refreshProjects();
      return;
    }
  }
  setError("分析超时，请检查后端日志。");
  setStatus("failed");
}

function projectModelForView(
  model: CodeGraphModel,
  view: GraphView,
  query: string,
  focusedPath: string | null,
  selectedId: string | null,
): CodeGraphModel {
  if (!model.nodes.length) return model;

  const meta = VIEW_META[view];
  const normalizedQuery = query.trim().toLowerCase();
  const isFocusedFile = focusedPath ? model.files.some((node) => node.filePath === focusedPath || node.id === focusedPath) : false;
  const allowedKinds = new Set(meta.nodeKinds);
  const allowedEdges = new Set(meta.edgeKinds);
  const nodesById = new Map(model.nodes.map((node) => [node.id, node]));

  let nodes = model.nodes.filter((node) => {
    if (!allowedKinds.has(node.kind)) return false;
    if (focusedPath && !pathMatches(node, focusedPath)) return false;
    if (!normalizedQuery) return true;
    return nodeMatchesQuery(node, normalizedQuery);
  });

  if (!normalizedQuery && !focusedPath && !selectedId && nodes.length > meta.budget) {
    nodes = takeImportantNodes(nodes, meta.budget);
  }

  const nodeIds = new Set(nodes.map((node) => node.id));

  if (selectedId && nodesById.has(selectedId)) {
    nodeIds.add(selectedId);
    for (const edge of model.edges) {
      if (edge.source === selectedId || edge.target === selectedId) {
        const source = nodesById.get(edge.source);
        const target = nodesById.get(edge.target);
        if (source && allowedKinds.has(source.kind)) nodeIds.add(source.id);
        if (target && allowedKinds.has(target.kind)) nodeIds.add(target.id);
      }
    }
  }

  let edges = view === "overview" ? aggregateFileEdges(model.edges, nodesById) : model.edges;
  if (isFocusedFile && (view === "symbols" || view === "data")) {
    const scopePath = focusedPath;
    if (!scopePath) return model;
    const relatedEdges = edges.filter((edge) => {
      if (!allowedEdges.has(edge.kind)) return false;
      const source = nodesById.get(edge.source);
      const target = nodesById.get(edge.target);
      return Boolean(
        source && target && (pathMatches(source, scopePath) || pathMatches(target, scopePath)),
      );
    });
    for (const edge of relatedEdges) {
      const source = nodesById.get(edge.source);
      const target = nodesById.get(edge.target);
      if (source && allowedKinds.has(source.kind)) nodeIds.add(source.id);
      if (target && allowedKinds.has(target.kind)) nodeIds.add(target.id);
    }
    edges = relatedEdges.filter((edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target));
  } else {
    edges = edges.filter((edge) => allowedEdges.has(edge.kind) && nodeIds.has(edge.source) && nodeIds.has(edge.target));
  }

  if ((view === "symbols" || view === "data") && !focusedPath && !normalizedQuery && !selectedId && edges.length > 260) {
    edges = takeImportantEdges(edges, 260);
    const connected = new Set<string>();
    for (const edge of edges) {
      connected.add(edge.source);
      connected.add(edge.target);
    }
    nodes = nodes.filter((node) => connected.has(node.id)).slice(0, meta.budget);
  } else {
    nodes = [...nodeIds].map((id) => nodesById.get(id)).filter((node): node is CodeGraphNode => Boolean(node));
  }

  if (!edges.length && view !== "overview") {
    edges = model.edges.filter(
      (edge) => edge.kind === "contains" && nodeIds.has(edge.source) && nodeIds.has(edge.target),
    );
  }

  return {
    ...model,
    nodes,
    edges,
    folders: nodes.filter((node) => node.kind === "folder"),
    files: nodes.filter((node) => node.kind === "file"),
    symbols: nodes.filter((node) => node.kind === "class" || node.kind === "function" || node.kind === "method"),
    variables: nodes.filter((node) => node.kind === "variable"),
  };
}

function aggregateFileEdges(edges: CodeGraphEdge[], nodesById: Map<string, CodeGraphNode>): CodeGraphEdge[] {
  const output = new Map<string, CodeGraphEdge>();

  for (const edge of edges) {
    if (edge.kind === "contains") {
      const source = nodesById.get(edge.source);
      const target = nodesById.get(edge.target);
      if (source?.kind === "folder" || target?.kind === "folder" || target?.kind === "file") {
        output.set(edge.id, edge);
      }
      continue;
    }

    const sourceFile = owningFileId(nodesById.get(edge.source));
    const targetFile = owningFileId(nodesById.get(edge.target));
    if (!sourceFile || !targetFile || sourceFile === targetFile) continue;
    const id = `file-edge:${edge.kind}:${sourceFile}:${targetFile}`;
    const existing = output.get(id);
    if (existing) {
      output.set(id, { ...existing, label: `${existing.label}+` });
    } else {
      output.set(id, {
        id,
        source: sourceFile,
        target: targetFile,
        kind: edge.kind === "arg" || edge.kind === "return" ? "reference" : edge.kind,
        label: EDGE_NAME[edge.kind],
        dataType: edge.dataType,
        lineNumber: edge.lineNumber,
        original: edge.original,
      });
    }
  }

  return Array.from(output.values());
}

function owningFileId(node: CodeGraphNode | undefined): string | null {
  if (!node) return null;
  if (node.kind === "file") return node.id;
  return node.fileId ?? null;
}

function takeImportantNodes(nodes: CodeGraphNode[], limit: number): CodeGraphNode[] {
  const priority: Record<CodeNodeKind, number> = {
    folder: 100,
    file: 78,
    class: 65,
    function: 52,
    method: 45,
    variable: 32,
  };
  return [...nodes]
    .sort((a, b) => {
      const scoreA = priority[a.kind] + a.edgeCount * 2 + (a.symbolCount ?? 0) * 0.25;
      const scoreB = priority[b.kind] + b.edgeCount * 2 + (b.symbolCount ?? 0) * 0.25;
      if (scoreB !== scoreA) return scoreB - scoreA;
      return a.label.localeCompare(b.label);
    })
    .slice(0, limit);
}

function takeImportantEdges(edges: CodeGraphEdge[], limit: number): CodeGraphEdge[] {
  const priority: Record<CodeEdgeKind, number> = {
    call: 80,
    arg: 72,
    return: 70,
    unresolved: 45,
    reference: 35,
    contains: 20,
  };
  return [...edges]
    .sort((a, b) => {
      const scoreA = priority[a.kind] + (a.lineNumber ? 1 : 0);
      const scoreB = priority[b.kind] + (b.lineNumber ? 1 : 0);
      if (scoreB !== scoreA) return scoreB - scoreA;
      return a.id.localeCompare(b.id);
    })
    .slice(0, limit);
}

function buildTree(files: ProjectFile[]): TreeNode {
  const root: TreeNode = {
    id: "root",
    name: "root",
    path: "",
    kind: "folder",
    fileCount: 0,
    symbolCount: 0,
    children: [],
  };

  for (const file of files) {
    const parts = normalizeFolder(file.folder_path).split("/").filter(Boolean);
    let cursor = root;
    cursor.fileCount += 1;
    cursor.symbolCount += file.symbol_count;
    let currentPath = "";

    for (const part of parts) {
      currentPath = currentPath ? `${currentPath}/${part}` : part;
      let child = cursor.children.find((item) => item.kind === "folder" && item.name === part);
      if (!child) {
        child = {
          id: `folder:${currentPath}`,
          name: part,
          path: currentPath,
          kind: "folder",
          fileCount: 0,
          symbolCount: 0,
          children: [],
        };
        cursor.children.push(child);
      }
      child.fileCount += 1;
      child.symbolCount += file.symbol_count;
      cursor = child;
    }

    cursor.children.push({
      id: file.id,
      name: file.file_name,
      path: file.file_path,
      kind: "file",
      file,
      fileCount: 1,
      symbolCount: file.symbol_count,
      children: [],
    });
  }

  sortTree(root);
  return root;
}

function sortTree(node: TreeNode): void {
  node.children.sort((a, b) => {
    if (a.kind !== b.kind) return a.kind === "folder" ? -1 : 1;
    return a.name.localeCompare(b.name);
  });
  for (const child of node.children) sortTree(child);
}

function nodeMatchesQuery(node: CodeGraphNode, query: string): boolean {
  return [
    node.label,
    node.subtitle,
    node.qualifiedName ?? "",
    node.filePath ?? "",
    node.folderPath,
    node.language ?? "",
    node.role ?? "",
  ]
    .join(" ")
    .toLowerCase()
    .includes(query);
}

function pathMatches(node: CodeGraphNode, path: string): boolean {
  const normalized = normalizeFolder(path);
  if (!path) return true;
  if (node.id === path || node.filePath === path || node.fileId === path) return true;
  if (node.folderPath === normalized) return true;
  if (normalized && node.folderPath.startsWith(`${normalized}/`)) return true;
  return false;
}

function nodeSize(kind: CodeNodeKind): { width: number; height: number } {
  if (kind === "folder") return { width: 172, height: 48 };
  if (kind === "file") return { width: 204, height: 56 };
  if (kind === "class") return { width: 190, height: 54 };
  if (kind === "variable") return { width: 150, height: 44 };
  return { width: 188, height: 50 };
}

function nodeColor(kind: CodeNodeKind): string {
  return {
    folder: "#7aa2f7",
    file: "#8bd5ca",
    class: "#f5a97f",
    function: "#eed49f",
    method: "#a6da95",
    variable: "#f0c6c6",
  }[kind];
}

function edgeColor(kind: CodeEdgeKind): string {
  return {
    contains: "#475569",
    call: "#7aa2f7",
    arg: "#f5a97f",
    return: "#a6da95",
    unresolved: "#ef4444",
    reference: "#9ca3af",
  }[kind];
}

function shortLabel(label: string): string {
  return label.length > 24 ? `${label.slice(0, 22)}...` : label;
}

function normalizeFolder(folderPath: string): string {
  return folderPath.replace(/\\/g, "/").replace(/^\.\/?/, "").replace(/\/$/, "");
}
