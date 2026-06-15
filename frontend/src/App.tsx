import "@xyflow/react/dist/style.css";

import {
  Background,
  Controls,
  MarkerType,
  MiniMap,
  ReactFlow,
  useReactFlow,
  type Edge,
  type Node,
} from "@xyflow/react";
import * as dagre from "dagre";
import {
  ArrowRight,
  Boxes,
  BrainCircuit,
  CheckSquare2,
  CheckCircle2,
  CircleAlert,
  Code2,
  FileCode2,
  FileArchive,
  Filter,
  Folder,
  FolderOpen,
  GitFork,
  Link2,
  Loader2,
  MessageSquare,
  Network,
  PackageSearch,
  PanelRightOpen,
  Play,
  RefreshCcw,
  Route,
  Search,
  Send,
  Square,
  Upload,
  X,
} from "lucide-react";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type DragEvent,
  type MouseEvent as ReactMouseEvent,
} from "react";
import { api } from "./api/client";
import {
  buildProjectGraphModel,
  getGraphStats,
  getReachableSubgraph,
  getSymbolNeighborhood,
  type ProjectGraphModel,
  type SymbolNode,
  type TraceEdge,
  type TraceEdgeKind,
} from "./lib/graphModel";
import type { AnalysisProgress, AnalysisStatus, DataFlowGraph, ProjectFile, SourceFile } from "./types";

type ImportMode = "local" | "url" | "archive";
type SymbolFilter = "all" | "function" | "method" | "class";
type ChatMessage = { role: "user" | "assistant"; content: string };
type ScopeSelection = { path: string; kind: "root" | "folder" | "file"; label: string } | null;
type SourcePreview = {
  symbolId: string;
  title: string;
  filePath: string;
  startLine: number | null;
  endLine: number | null;
  source: SourceFile | null;
  loading: boolean;
  error: string;
};
type FileTreeNode = {
  id: string;
  name: string;
  path: string;
  kind: "root" | "folder" | "file";
  file?: ProjectFile;
  fileCount: number;
  symbolCount: number;
  children: FileTreeNode[];
};

const EDGE_COLOR: Record<TraceEdgeKind, string> = {
  call: "#4f9fd8",
  arg: "#d9a441",
  return: "#63b383",
  unknown: "#7d8794",
};

const EDGE_LABEL: Record<TraceEdgeKind, string> = {
  call: "调用",
  arg: "传参",
  return: "返回",
  unknown: "关系",
};

const NODE_COLOR = {
  function: "#4f9fd8",
  method: "#63b383",
  class: "#d9a441",
};

const SYMBOL_NODE_WIDTH = 206;
const SYMBOL_NODE_HEIGHT = 38;

export default function App() {
  const [importMode, setImportMode] = useState<ImportMode>("local");
  const [sourceText, setSourceText] = useState("E:\\Github_Project\\PoltAIshow");
  const [analysisId, setAnalysisId] = useState<string | null>(null);
  const [status, setStatus] = useState<AnalysisStatus | "idle">("idle");
  const [progress, setProgress] = useState<AnalysisProgress | null>(null);
  const [graph, setGraph] = useState<DataFlowGraph | null>(null);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [scopeSelection, setScopeSelection] = useState<ScopeSelection>(null);
  const [symbolFilter, setSymbolFilter] = useState<SymbolFilter>("all");
  const [edgeFilters, setEdgeFilters] = useState<Record<TraceEdgeKind, boolean>>({
    call: true,
    arg: true,
    return: true,
    unknown: true,
  });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [traceRootId, setTraceRootId] = useState<string | null>(null);
  const [showFullGraph, setShowFullGraph] = useState(false);
  const [sourcePreview, setSourcePreview] = useState<SourcePreview | null>(null);
  const [chatInput, setChatInput] = useState("");
  const [chatSessionId, setChatSessionId] = useState<string | null>(null);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const model = useMemo(() => buildProjectGraphModel(graph), [graph]);
  const stats = useMemo(() => getGraphStats(model), [model]);
  const fileTree = useMemo(() => buildFileTree(model.projectFiles), [model.projectFiles]);
  const symbolById = useMemo(
    () => new Map(model.symbols.map((symbol) => [symbol.id, symbol])),
    [model.symbols],
  );

  const selectedSymbol = selectedId ? symbolById.get(selectedId) ?? null : null;
  const selectedSymbols = useMemo(
    () =>
      [...selectedIds]
        .map((id) => symbolById.get(id))
        .filter((symbol): symbol is SymbolNode => Boolean(symbol)),
    [selectedIds, symbolById],
  );
  const selectedNeighborhood = useMemo(
    () => getSymbolNeighborhood(model, selectedId),
    [model, selectedId],
  );
  const traceReachable = useMemo(
    () => (traceRootId ? getReachableSubgraph(model, traceRootId, 4) : null),
    [model, traceRootId],
  );

  const visibleSymbols = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return model.symbols.filter((symbol) => {
      if (!symbolMatchesScope(symbol, scopeSelection)) return false;
      if (symbolFilter !== "all" && symbol.kind !== symbolFilter) return false;
      if (!normalizedQuery) return true;
      return [
        symbol.name,
        symbol.qualifiedName,
        symbol.fileName,
        symbol.filePath,
        symbol.parentClassName ?? "",
      ]
        .join(" ")
        .toLowerCase()
        .includes(normalizedQuery);
    });
  }, [model.symbols, query, scopeSelection, symbolFilter]);

  const visibleSymbolIds = useMemo(
    () => new Set(visibleSymbols.map((symbol) => symbol.id)),
    [visibleSymbols],
  );

  const visibleEdges = useMemo(
    () =>
      model.edges.filter(
        (edge) =>
          edgeFilters[edge.kind] &&
          visibleSymbolIds.has(edge.sourceId) &&
          visibleSymbolIds.has(edge.targetId),
      ),
    [edgeFilters, model.edges, visibleSymbolIds],
  );

  const selectedRelationEdges = useMemo(
    () =>
      visibleEdges.filter(
        (edge) => selectedIds.has(edge.sourceId) && selectedIds.has(edge.targetId),
      ),
    [selectedIds, visibleEdges],
  );

  const canvasSymbolIds = useMemo(() => {
    if (traceReachable) return traceReachable;
    if (selectedIds.size > 1) {
      const relationIds = new Set(selectedIds);
      const hasDirectRelations = selectedRelationEdges.length > 0;
      if (hasDirectRelations) return relationIds;
      for (const edge of visibleEdges) {
        if (selectedIds.has(edge.sourceId) || selectedIds.has(edge.targetId)) {
          relationIds.add(edge.sourceId);
          relationIds.add(edge.targetId);
        }
      }
      return relationIds;
    }
    if (showFullGraph || !selectedId) return visibleSymbolIds;
    return selectedNeighborhood.relatedIds;
  }, [
    selectedId,
    selectedIds,
    selectedNeighborhood.relatedIds,
    selectedRelationEdges.length,
    showFullGraph,
    traceReachable,
    visibleEdges,
    visibleSymbolIds,
  ]);

  const canvasSymbols = useMemo(
    () => visibleSymbols.filter((symbol) => canvasSymbolIds.has(symbol.id)),
    [canvasSymbolIds, visibleSymbols],
  );

  const canvasEdges = useMemo(
    () =>
      visibleEdges.filter(
        (edge) => canvasSymbolIds.has(edge.sourceId) && canvasSymbolIds.has(edge.targetId),
      ),
    [canvasSymbolIds, visibleEdges],
  );

  const flowNodes = useMemo(
    () =>
      layoutNodes(
        canvasSymbols,
        canvasEdges,
        selectedId,
        selectedIds,
        selectedNeighborhood.relatedIds,
        traceReachable,
      ),
    [
      canvasEdges,
      canvasSymbols,
      selectedId,
      selectedIds,
      selectedNeighborhood.relatedIds,
      traceReachable,
    ],
  );

  const flowEdges = useMemo(
    () => layoutEdges(canvasEdges, selectedId, selectedIds, traceReachable),
    [canvasEdges, selectedId, selectedIds, traceReachable],
  );

  useEffect(() => {
    if (visibleSymbols.length === 0) {
      if (selectedId) setSelectedId(null);
      if (selectedIds.size > 0) setSelectedIds(new Set());
      return;
    }
    if (!selectedId || !visibleSymbolIds.has(selectedId)) {
      const nextId = visibleSymbols[0].id;
      setSelectedId(nextId);
      setSelectedIds(new Set([nextId]));
      return;
    }
    setSelectedIds((previous) => {
      const next = new Set([...previous].filter((id) => visibleSymbolIds.has(id)));
      if (!next.has(selectedId)) next.add(selectedId);
      return sameStringSet(previous, next) ? previous : next;
    });
  }, [selectedId, selectedIds.size, visibleSymbolIds, visibleSymbols]);

  useEffect(() => {
    if (!sourcePreview) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setSourcePreview(null);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [sourcePreview]);

  const loadGraph = useCallback(async (id: string) => {
    const payload = await api.getGraph(id);
    setGraph(payload);
    setStatus("completed");
    setProgress((previous) => ({
      ...(previous ?? {}),
      status: "completed",
      progress_pct: 100,
      message: "分析完成",
    }));
  }, []);

  const watchAnalysis = useCallback(
    (id: string) => {
      let completed = false;
      const events = api.streamProgress(
        id,
        (next) => {
          setProgress(next);
          setStatus(next.status);
          if (next.status === "completed") {
            completed = true;
            events.close();
            loadGraph(id).catch((err: unknown) => {
              setError(err instanceof Error ? err.message : "读取图数据失败");
            });
          }
          if (next.status === "failed") {
            completed = true;
            events.close();
            setError(next.error_message || next.message || "分析失败");
          }
        },
        () => {
          if (!completed) {
            pollAnalysis(id, loadGraph, setProgress, setStatus, setError);
          }
        },
      );
    },
    [loadGraph],
  );

  const startAnalysis = useCallback(
    async (file?: File) => {
      setError("");
      setGraph(null);
      setSelectedId(null);
      setSelectedIds(new Set());
      setTraceRootId(null);
      setShowFullGraph(false);
      setSourcePreview(null);
      setStatus("pending");
      setProgress({ status: "pending", progress_pct: 0, message: "正在提交项目" });
      try {
        const result =
          file != null
            ? await api.importArchive(file)
            : importMode === "url"
              ? await api.importFromUrl(sourceText.trim())
              : await api.importLocalPath(sourceText.trim());
        setAnalysisId(result.analysis_id);
        watchAnalysis(result.analysis_id);
      } catch (err: unknown) {
        setStatus("failed");
        setError(err instanceof Error ? err.message : "导入失败");
      }
    },
    [importMode, sourceText, watchAnalysis],
  );

  const onDrop = useCallback(
    (event: DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      setDragOver(false);
      const file = event.dataTransfer.files[0];
      if (!file) return;
      startAnalysis(file);
    },
    [startAnalysis],
  );

  const selectSymbol = useCallback((id: string, append = false) => {
    if (append) {
      setTraceRootId(null);
      setSelectedIds((previous) => {
        const next = new Set(previous);
        if (next.has(id)) {
          next.delete(id);
          if (selectedId === id) {
            const fallback = next.values().next().value as string | undefined;
            setSelectedId(fallback ?? null);
          }
        } else {
          next.add(id);
          setSelectedId(id);
        }
        return next;
      });
      setShowFullGraph(false);
      return;
    }
    setSelectedId(id);
    setTraceRootId(null);
    setSelectedIds(new Set([id]));
  }, [selectedId]);

  const clearMultiSelect = useCallback(() => {
    if (selectedId) {
      setSelectedIds(new Set([selectedId]));
    } else {
      setSelectedIds(new Set());
    }
  }, [selectedId]);

  const openSourceForSymbol = useCallback(
    async (symbol: SymbolNode) => {
      if (!analysisId) return;
      setSourcePreview({
        symbolId: symbol.id,
        title: symbol.qualifiedName,
        filePath: symbol.filePath,
        startLine: symbol.startLine,
        endLine: symbol.endLine,
        source: null,
        loading: true,
        error: "",
      });
      try {
        const source = await api.getSource(
          analysisId,
          symbol.filePath,
          symbol.startLine,
          symbol.endLine,
        );
        setSourcePreview((previous) =>
          previous?.symbolId === symbol.id
            ? {
                ...previous,
                source,
                loading: false,
                error: "",
              }
            : previous,
        );
      } catch (err: unknown) {
        setSourcePreview((previous) =>
          previous?.symbolId === symbol.id
            ? {
                ...previous,
                loading: false,
                error: err instanceof Error ? err.message : "读取源码失败",
              }
            : previous,
        );
      }
    },
    [analysisId],
  );

  useEffect(() => {
    const onOpenSource = (event: Event) => {
      const symbolId = (event as CustomEvent<string>).detail;
      const symbol = symbolById.get(symbolId);
      if (symbol) void openSourceForSymbol(symbol);
    };
    window.addEventListener("poltaishow:open-source", onOpenSource);
    return () => window.removeEventListener("poltaishow:open-source", onOpenSource);
  }, [openSourceForSymbol, symbolById]);

  const handleNodeSelect = useCallback(
    (id: string, event: ReactMouseEvent) => {
      selectSymbol(id, event.ctrlKey || event.metaKey || event.shiftKey);
    },
    [selectSymbol],
  );

  const handleNodeOpen = useCallback(
    (id: string) => {
      const symbol = symbolById.get(id);
      if (symbol) void openSourceForSymbol(symbol);
    },
    [openSourceForSymbol, symbolById],
  );

  const sendChat = useCallback(async () => {
    if (!analysisId || !chatInput.trim() || chatLoading) return;
    const message = chatInput.trim();
    setChatInput("");
    setChatLoading(true);
    setChatMessages((items) => [...items, { role: "user", content: message }]);
    try {
      const response = await api.sendMessage(
        analysisId,
        message,
        chatSessionId,
        [...selectedIds],
      );
      setChatSessionId(response.session_id);
      setChatMessages((items) => [
        ...items,
        { role: "assistant", content: response.reply },
      ]);
    } catch (err: unknown) {
      setChatMessages((items) => [
        ...items,
        {
          role: "assistant",
          content: err instanceof Error ? err.message : "AI 问答失败",
        },
      ]);
    } finally {
      setChatLoading(false);
    }
  }, [analysisId, chatInput, chatLoading, chatSessionId, selectedIds]);

  const isBusy =
    status === "pending" ||
    status === "parsing" ||
    status === "analyzing" ||
    status === "building";

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand">
          <Network size={20} />
          <div>
            <strong>PoltAIshow</strong>
            <span>项目静态流分析工作台</span>
          </div>
        </div>
        <ImportControls
          mode={importMode}
          setMode={setImportMode}
          source={sourceText}
          setSource={setSourceText}
          busy={isBusy}
          onStart={() => void startAnalysis()}
          onArchiveClick={() => fileInputRef.current?.click()}
        />
        <input
          ref={fileInputRef}
          type="file"
          accept=".zip,.tar.gz,.tgz"
          hidden
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) void startAnalysis(file);
            event.currentTarget.value = "";
          }}
        />
      </header>

      <section className="status-strip">
        <ProgressState
          status={status}
          progress={progress}
          error={error}
          busy={isBusy}
        />
        <div className="stat-row">
          <Metric label="文件" value={stats.fileCount} />
          <Metric label="符号" value={stats.symbolCount} />
          <Metric label="类" value={stats.classCount} />
          <Metric label="函数" value={stats.functionCount} />
          <Metric label="方法" value={stats.methodCount} />
          <Metric label="关系" value={stats.edgeCount} />
          <Metric label="跨文件" value={stats.crossFileCount} />
        </div>
      </section>

      <section
        className={`workspace ${dragOver ? "drop-active" : ""}`}
        onDragOver={(event) => {
          event.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
      >
        <aside className="left-panel">
          <FilterPanel
            query={query}
            setQuery={setQuery}
            symbolFilter={symbolFilter}
            setSymbolFilter={setSymbolFilter}
            edgeFilters={edgeFilters}
            setEdgeFilters={setEdgeFilters}
            stats={stats}
          />
          <ProjectTree
            tree={fileTree}
            selectedScope={scopeSelection}
            onSelectScope={setScopeSelection}
          />
          <SymbolIndex
            symbols={visibleSymbols}
            edges={visibleEdges}
            selectedId={selectedId}
            selectedIds={selectedIds}
            onSelect={selectSymbol}
            onOpen={openSourceForSymbol}
          />
        </aside>

        <section className="canvas-panel">
          <CanvasToolbar
            model={model}
            visibleSymbols={canvasSymbols}
            visibleEdges={canvasEdges}
            selectedSymbol={selectedSymbol}
            selectedSymbols={selectedSymbols}
            traceRootId={traceRootId}
            setTraceRootId={setTraceRootId}
            showFullGraph={showFullGraph}
            setShowFullGraph={setShowFullGraph}
            onClearMultiSelect={clearMultiSelect}
          />
          <div className="flow-frame">
            {graph ? (
              <SymbolFlowCanvas
                nodes={flowNodes}
                edges={flowEdges}
                onNodeSelect={handleNodeSelect}
                onNodeOpen={handleNodeOpen}
                onSelectionChange={(ids) => {
                  if (ids.size === 0) return;
                  if (sameStringSet(ids, selectedIds)) return;
                  setTraceRootId(null);
                  setSelectedIds(ids);
                  const nextPrimary = ids.values().next().value as string | undefined;
                  setSelectedId(nextPrimary ?? null);
                  if (ids.size > 1) setShowFullGraph(false);
                }}
              />
            ) : (
              <EmptyCanvas busy={isBusy} />
            )}
          </div>
        </section>

        <aside className="right-panel">
          <Inspector
            symbol={selectedSymbol}
            selectedSymbols={selectedSymbols}
            model={model}
            neighborhood={selectedNeighborhood}
            onSelect={(id) => selectSymbol(id, false)}
            onOpenSource={openSourceForSymbol}
            onTraceFrom={(id) => setTraceRootId(id)}
          />
        </aside>
      </section>

      {sourcePreview && (
        <SourcePreviewModal
          preview={sourcePreview}
          onClose={() => setSourcePreview(null)}
        />
      )}

      <section className="ai-console">
        <div className="console-head">
          <div>
            <BrainCircuit size={16} />
            <span>AI 项目问答</span>
          </div>
          <small>
            {analysisId
              ? `analysis ${analysisId.slice(0, 8)} · 选中 ${selectedIds.size} 个符号`
              : "等待分析"}
          </small>
        </div>
        <div className="console-body">
          {chatMessages.length === 0 ? (
            <div className="console-empty">
              可以直接问：这个项目有哪些入口？某个函数的传值链路是什么？哪些模块耦合最重？
            </div>
          ) : (
            chatMessages.map((message, index) => (
              <div key={index} className={`chat-line ${message.role}`}>
                <span>{message.role === "user" ? "你" : "AI"}</span>
                <p>{message.content}</p>
              </div>
            ))
          )}
        </div>
        <div className="console-input">
          <input
            value={chatInput}
            onChange={(event) => setChatInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") void sendChat();
            }}
            disabled={!analysisId || chatLoading}
            placeholder="问这个项目的结构、调用、传值关系；会带上当前选中的符号"
          />
          <button
            type="button"
            onClick={() => void sendChat()}
            disabled={!analysisId || !chatInput.trim() || chatLoading}
            aria-label="发送问题"
          >
            {chatLoading ? <Loader2 size={16} className="spin" /> : <Send size={16} />}
          </button>
        </div>
      </section>
    </main>
  );
}

function SymbolFlowCanvas({
  nodes,
  edges,
  onNodeSelect,
  onNodeOpen,
  onSelectionChange,
}: {
  nodes: Node[];
  edges: Edge[];
  onNodeSelect: (id: string, event: ReactMouseEvent) => void;
  onNodeOpen: (id: string) => void;
  onSelectionChange: (ids: Set<string>) => void;
}) {
  const nodeKey = useMemo(() => nodes.map((node) => node.id).join("|"), [nodes]);
  const lastClickRef = useRef<{ id: string; time: number } | null>(null);

  return (
    <div
      className="flow-capture"
      onDoubleClickCapture={(event) => {
        const target = event.target as HTMLElement;
        const nodeElement = target.closest(".react-flow__node[data-id]");
        const nodeId = nodeElement?.getAttribute("data-id");
        if (nodeId) onNodeOpen(nodeId);
      }}
    >
      <ReactFlow
        key={nodeKey}
        nodes={nodes}
        edges={edges}
        fitView
        fitViewOptions={{ padding: 0.24, maxZoom: 1.15 }}
        minZoom={0.08}
        maxZoom={1.6}
        multiSelectionKeyCode={["Control", "Meta", "Shift"]}
        selectionKeyCode={null}
        selectionOnDrag
        panOnDrag={[1, 2]}
        selectNodesOnDrag={false}
        onNodeClick={(event, node) => {
          const now = window.performance.now();
          const previous = lastClickRef.current;
          onNodeSelect(node.id, event);
          if (previous?.id === node.id && now - previous.time < 520) {
            lastClickRef.current = null;
            onNodeOpen(node.id);
            return;
          }
          lastClickRef.current = { id: node.id, time: now };
        }}
        onNodeDoubleClick={(_, node) => onNodeOpen(node.id)}
        onSelectionChange={({ nodes: selectedNodes }) => {
          onSelectionChange(new Set(selectedNodes.map((node) => node.id)));
        }}
        proOptions={{ hideAttribution: true }}
      >
        <AutoFit nodes={nodes} />
        <Background color="#263241" gap={22} size={1} />
        <Controls position="bottom-left" />
        <MiniMap
          pannable
          zoomable
          position="bottom-right"
          nodeColor={(node) => String(node.data?.color ?? "#7d8794")}
          maskColor="rgba(13, 17, 23, .72)"
        />
      </ReactFlow>
    </div>
  );
}

function AutoFit({ nodes }: { nodes: Node[] }) {
  const { fitView } = useReactFlow();
  const nodeKey = useMemo(() => nodes.map((node) => node.id).join("|"), [nodes]);

  useEffect(() => {
    const handle = window.setTimeout(() => {
      void fitView({ padding: 0.24, duration: 180, maxZoom: 1.15 });
    }, 80);
    return () => window.clearTimeout(handle);
  }, [fitView, nodeKey]);

  return null;
}

function ImportControls(props: {
  mode: ImportMode;
  setMode: (mode: ImportMode) => void;
  source: string;
  setSource: (value: string) => void;
  busy: boolean;
  onStart: () => void;
  onArchiveClick: () => void;
}) {
  return (
    <div className="import-controls">
      <div className="segmented" role="tablist" aria-label="导入方式">
        <button
          className={props.mode === "local" ? "active" : ""}
          onClick={() => props.setMode("local")}
          type="button"
        >
          <PackageSearch size={14} />
          本地路径
        </button>
        <button
          className={props.mode === "url" ? "active" : ""}
          onClick={() => props.setMode("url")}
          type="button"
        >
          <Link2 size={14} />
          file://
        </button>
        <button
          className={props.mode === "archive" ? "active" : ""}
          onClick={() => props.setMode("archive")}
          type="button"
        >
          <FileArchive size={14} />
          压缩包
        </button>
      </div>
      {props.mode === "archive" ? (
        <button
          className="primary-action"
          onClick={props.onArchiveClick}
          disabled={props.busy}
          type="button"
        >
          <Upload size={15} />
          选择文件
        </button>
      ) : (
        <>
          <input
            value={props.source}
            onChange={(event) => props.setSource(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") props.onStart();
            }}
            placeholder={props.mode === "url" ? "file:///E:/path/to/project" : "E:\\path\\to\\project"}
            disabled={props.busy}
          />
          <button
            className="primary-action"
            onClick={props.onStart}
            disabled={props.busy || !props.source.trim()}
            type="button"
          >
            {props.busy ? <Loader2 size={15} className="spin" /> : <Play size={15} />}
            解析
          </button>
        </>
      )}
    </div>
  );
}

function ProgressState(props: {
  status: AnalysisStatus | "idle";
  progress: AnalysisProgress | null;
  error: string;
  busy: boolean;
}) {
  const pct = props.progress?.progress_pct ?? 0;
  const message =
    props.error ||
    props.progress?.message ||
    (props.status === "idle" ? "输入项目路径或上传压缩包后开始解析" : "准备中");
  return (
    <div className={`progress-state ${props.error ? "error" : props.status}`}>
      <div className="state-copy">
        {props.error ? (
          <CircleAlert size={16} />
        ) : props.status === "completed" ? (
          <CheckCircle2 size={16} />
        ) : props.busy ? (
          <Loader2 size={16} className="spin" />
        ) : (
          <Route size={16} />
        )}
        <span>{message}</span>
      </div>
      <div className="progress-track" aria-label="分析进度">
        <div style={{ width: `${Math.max(props.busy ? 4 : 0, pct)}%` }} />
      </div>
      <small>{Math.round(pct)}%</small>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function FilterPanel(props: {
  query: string;
  setQuery: (value: string) => void;
  symbolFilter: SymbolFilter;
  setSymbolFilter: (value: SymbolFilter) => void;
  edgeFilters: Record<TraceEdgeKind, boolean>;
  setEdgeFilters: (value: Record<TraceEdgeKind, boolean>) => void;
  stats: ReturnType<typeof getGraphStats>;
}) {
  return (
    <section className="panel-section">
      <div className="section-title">
        <Filter size={14} />
        <span>筛选</span>
      </div>
      <label className="search-field">
        <Search size={14} />
        <input
          value={props.query}
          onChange={(event) => props.setQuery(event.target.value)}
          placeholder="搜索函数、类、文件..."
        />
        {props.query && (
          <button type="button" onClick={() => props.setQuery("")} aria-label="清空搜索">
            <X size={13} />
          </button>
        )}
      </label>
      <div className="segmented compact" role="tablist" aria-label="符号类型">
        {(["all", "function", "method", "class"] as SymbolFilter[]).map((kind) => (
          <button
            key={kind}
            className={props.symbolFilter === kind ? "active" : ""}
            onClick={() => props.setSymbolFilter(kind)}
            type="button"
          >
            {kindLabel(kind)}
          </button>
        ))}
      </div>
      <div className="edge-toggles">
        {(["call", "arg", "return", "unknown"] as TraceEdgeKind[]).map((kind) => (
          <button
            key={kind}
            type="button"
            className={props.edgeFilters[kind] ? "active" : ""}
            onClick={() =>
              props.setEdgeFilters({
                ...props.edgeFilters,
                [kind]: !props.edgeFilters[kind],
              })
            }
          >
            <span style={{ backgroundColor: EDGE_COLOR[kind] }} />
            {EDGE_LABEL[kind]}
          </button>
        ))}
      </div>
      <div className="edge-breakdown">
        <span>调用 {props.stats.callCount}</span>
        <span>传参 {props.stats.argCount}</span>
        <span>返回 {props.stats.returnCount}</span>
      </div>
    </section>
  );
}

function ProjectTree(props: {
  tree: FileTreeNode;
  selectedScope: ScopeSelection;
  onSelectScope: (scope: ScopeSelection) => void;
}) {
  return (
    <section className="panel-section project-tree-panel">
      <div className="section-title">
        <FolderOpen size={14} />
        <span>项目文件树</span>
        <small>{props.tree.fileCount}</small>
      </div>
      <button
        type="button"
        className={`tree-row root ${props.selectedScope == null ? "active" : ""}`}
        onClick={() => props.onSelectScope(null)}
      >
        <FolderOpen size={14} />
        <span>整个项目</span>
        <small>{props.tree.symbolCount}</small>
      </button>
      <div className="tree-scroll">
        {props.tree.children.length === 0 ? (
          <p className="muted-copy">解析后显示目录结构</p>
        ) : (
          props.tree.children.map((node) => (
            <TreeNode
              key={node.id}
              node={node}
              depth={0}
              selectedScope={props.selectedScope}
              onSelectScope={props.onSelectScope}
            />
          ))
        )}
      </div>
    </section>
  );
}

function TreeNode(props: {
  node: FileTreeNode;
  depth: number;
  selectedScope: ScopeSelection;
  onSelectScope: (scope: ScopeSelection) => void;
}) {
  const { node } = props;
  const isActive =
    props.selectedScope?.path === node.path && props.selectedScope?.kind === node.kind;
  const visibleChildren =
    props.depth >= 3 && node.kind === "folder"
      ? node.children.filter((child) => child.symbolCount > 0).slice(0, 28)
      : node.children.slice(0, 80);
  const hiddenCount = node.children.length - visibleChildren.length;
  return (
    <div className="tree-node">
      <button
        type="button"
        className={`tree-row ${node.kind} ${isActive ? "active" : ""} ${node.symbolCount === 0 ? "empty" : ""}`}
        style={{ paddingLeft: 8 + props.depth * 14 }}
        onClick={() =>
          props.onSelectScope({
            path: node.path,
            kind: node.kind,
            label: node.name,
          })
        }
        title={node.path || node.name}
      >
        {node.kind === "file" ? <FileCode2 size={13} /> : <Folder size={13} />}
        <span>{node.name}</span>
        <small>{node.symbolCount || node.fileCount}</small>
      </button>
      {node.kind === "folder" && visibleChildren.length > 0 && (
        <div>
          {visibleChildren.map((child) => (
            <TreeNode
              key={child.id}
              node={child}
              depth={props.depth + 1}
              selectedScope={props.selectedScope}
              onSelectScope={props.onSelectScope}
            />
          ))}
          {hiddenCount > 0 && (
            <div className="tree-more" style={{ paddingLeft: 24 + props.depth * 14 }}>
              +{hiddenCount} more
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function SymbolIndex(props: {
  symbols: SymbolNode[];
  edges: TraceEdge[];
  selectedId: string | null;
  selectedIds: Set<string>;
  onSelect: (id: string, append?: boolean) => void;
  onOpen: (symbol: SymbolNode) => void;
}) {
  const degree = useMemo(() => {
    const counts = new Map<string, number>();
    for (const edge of props.edges) {
      counts.set(edge.sourceId, (counts.get(edge.sourceId) ?? 0) + 1);
      counts.set(edge.targetId, (counts.get(edge.targetId) ?? 0) + 1);
    }
    return counts;
  }, [props.edges]);

  return (
    <section className="panel-section symbol-list">
      <div className="section-title">
        <Code2 size={14} />
        <span>函数 / 类 / 方法</span>
        <small>{props.symbols.length}</small>
      </div>
      <div className="symbol-scroll">
        {props.symbols.length === 0 ? (
          <p className="muted-copy">没有匹配的符号</p>
        ) : (
          props.symbols.map((symbol) => (
            <button
              key={symbol.id}
              type="button"
              className={[
                "symbol-row",
                props.selectedId === symbol.id ? "active" : "",
                props.selectedIds.has(symbol.id) ? "checked" : "",
              ].join(" ")}
              onClick={(event) => props.onSelect(symbol.id, event.ctrlKey || event.metaKey || event.shiftKey)}
              onDoubleClick={() => props.onOpen(symbol)}
            >
              <span
                className="symbol-check"
                onClick={(event) => {
                  event.stopPropagation();
                  props.onSelect(symbol.id, true);
                }}
                aria-hidden="true"
              >
                {props.selectedIds.has(symbol.id) ? <CheckSquare2 size={13} /> : <Square size={13} />}
              </span>
              <span
                className={`symbol-kind ${symbol.kind}`}
                title={kindLabel(symbol.kind)}
              />
              <span className="symbol-text">
                <strong>{symbol.name}</strong>
                <small>
                  {symbol.fileName}
                  {symbol.startLine ? `:${symbol.startLine}` : ""}
                </small>
              </span>
              <span className="degree">{degree.get(symbol.id) ?? 0}</span>
            </button>
          ))
        )}
      </div>
    </section>
  );
}

function CanvasToolbar(props: {
  model: ProjectGraphModel;
  visibleSymbols: SymbolNode[];
  visibleEdges: TraceEdge[];
  selectedSymbol: SymbolNode | null;
  selectedSymbols: SymbolNode[];
  traceRootId: string | null;
  setTraceRootId: (id: string | null) => void;
  showFullGraph: boolean;
  setShowFullGraph: (value: boolean) => void;
  onClearMultiSelect: () => void;
}) {
  const modeLabel = props.traceRootId
    ? "追踪"
    : props.selectedSymbols.length > 1
      ? `多选 ${props.selectedSymbols.length}`
      : props.showFullGraph
        ? "全图"
        : "邻域";
  return (
    <div className="canvas-toolbar">
      <div className="toolbar-title">
        <GitFork size={16} />
        <span>符号传值图</span>
        <small>
          {modeLabel} · {props.visibleSymbols.length} nodes / {props.visibleEdges.length} edges
        </small>
      </div>
      <div className="toolbar-actions">
        <button
          type="button"
          disabled={props.selectedSymbols.length <= 1}
          onClick={props.onClearMultiSelect}
        >
          <X size={14} />
          取消多选
        </button>
        <button
          type="button"
          disabled={Boolean(props.traceRootId) || props.selectedSymbols.length > 1}
          onClick={() => props.setShowFullGraph(!props.showFullGraph)}
          className={props.showFullGraph ? "active" : ""}
        >
          <Network size={14} />
          {props.showFullGraph ? "邻域" : "全图"}
        </button>
        <button
          type="button"
          disabled={!props.selectedSymbol}
          onClick={() => {
            props.setShowFullGraph(false);
            if (props.selectedSymbol) props.setTraceRootId(props.selectedSymbol.id);
          }}
          className={props.traceRootId ? "active" : ""}
        >
          <Route size={14} />
          追踪
        </button>
        <button
          type="button"
          disabled={!props.traceRootId}
          onClick={() => props.setTraceRootId(null)}
        >
          <RefreshCcw size={14} />
          退出追踪
        </button>
      </div>
    </div>
  );
}

function EmptyCanvas({ busy }: { busy: boolean }) {
  return (
    <div className="empty-canvas">
      {busy ? <Loader2 size={28} className="spin" /> : <Boxes size={32} />}
      <strong>{busy ? "正在解析项目" : "等待项目图"}</strong>
      <span>支持本地目录路径和项目压缩包；后端完成后这里会显示函数级关系图。</span>
    </div>
  );
}

function Inspector(props: {
  symbol: SymbolNode | null;
  selectedSymbols: SymbolNode[];
  model: ProjectGraphModel;
  neighborhood: ReturnType<typeof getSymbolNeighborhood>;
  onSelect: (id: string) => void;
  onOpenSource: (symbol: SymbolNode) => void;
  onTraceFrom: (id: string) => void;
}) {
  if (!props.symbol) {
    return (
      <section className="inspector empty">
        <MessageSquare size={18} />
        <span>选择画布上的函数、类或方法查看关系。</span>
      </section>
    );
  }

  const { symbol } = props;
  const related = [...props.neighborhood.relatedIds].length - 1;
  return (
    <section className="inspector">
      <div className="inspector-head">
        <span className={`symbol-kind large ${symbol.kind}`} />
        <div>
          <h2>{symbol.name}</h2>
          <p>{kindLabel(symbol.kind)} · {symbol.fileName}</p>
        </div>
      </div>

      <div className="detail-grid">
        <DetailItem label="模块" value={symbol.folderPath} />
        <DetailItem label="语言" value={symbol.language} />
        <DetailItem label="角色" value={symbol.role} />
        <DetailItem
          label="位置"
          value={symbol.startLine ? `${symbol.fileName}:${symbol.startLine}` : symbol.fileName}
        />
      </div>

      {props.selectedSymbols.length > 1 && (
        <div className="multi-selection">
          <h3>已选 {props.selectedSymbols.length} 个符号</h3>
          {props.selectedSymbols.slice(0, 12).map((item) => (
            <button key={item.id} type="button" onClick={() => props.onSelect(item.id)}>
              <span className={`symbol-kind ${item.kind}`} />
              <strong>{item.name}</strong>
              <small>{item.fileName}</small>
            </button>
          ))}
        </div>
      )}

      {symbol.parentClassName && (
        <button
          type="button"
          className="inline-link"
          onClick={() => symbol.parentClassId && props.onSelect(symbol.parentClassId)}
        >
          所属类 <ArrowRight size={13} /> {symbol.parentClassName}
        </button>
      )}

      <div className="params">
        <h3>参数</h3>
        {symbol.params.length === 0 ? (
          <p className="muted-copy">无参数或未识别</p>
        ) : (
          symbol.params.map((param) => (
            <span key={`${symbol.id}-${param.name}`}>
              {param.name}: {param.type || "Unknown"}
            </span>
          ))
        )}
      </div>

      <button
        type="button"
        className="trace-button"
        onClick={() => props.onTraceFrom(symbol.id)}
      >
        <Route size={14} />
        从这里追踪下游
      </button>
      <button
        type="button"
        className="trace-button secondary"
        onClick={() => props.onOpenSource(symbol)}
      >
        <PanelRightOpen size={14} />
        查看源码
      </button>

      <RelationshipList
        title={`流入 ${props.neighborhood.incoming.length}`}
        edges={props.neighborhood.incoming}
        symbolById={new Map(props.model.symbols.map((item) => [item.id, item]))}
        direction="incoming"
        onSelect={props.onSelect}
      />
      <RelationshipList
        title={`流出 ${props.neighborhood.outgoing.length}`}
        edges={props.neighborhood.outgoing}
        symbolById={new Map(props.model.symbols.map((item) => [item.id, item]))}
        direction="outgoing"
        onSelect={props.onSelect}
      />

      <p className="inspector-foot">
        关联符号 {related} 个。当前值变化只能显示静态表达式名；运行时数值变化需要后续接入 tracing 或测试执行。
      </p>
    </section>
  );
}

function DetailItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span>{label}</span>
      <strong title={value}>{value}</strong>
    </div>
  );
}

function RelationshipList(props: {
  title: string;
  edges: TraceEdge[];
  symbolById: Map<string, SymbolNode>;
  direction: "incoming" | "outgoing";
  onSelect: (id: string) => void;
}) {
  return (
    <div className="relationship-block">
      <h3>{props.title}</h3>
      {props.edges.length === 0 ? (
        <p className="muted-copy">没有关系</p>
      ) : (
        props.edges.slice(0, 24).map((edge) => {
          const nextId = props.direction === "incoming" ? edge.sourceId : edge.targetId;
          const next = props.symbolById.get(nextId);
          return (
            <button
              key={edge.id}
              type="button"
              onClick={() => props.onSelect(nextId)}
              className="relationship-row"
            >
              <span style={{ backgroundColor: EDGE_COLOR[edge.kind] }} />
              <strong>{next?.name ?? nextId}</strong>
              <small>{edgeLabel(edge)}</small>
            </button>
          );
        })
      )}
    </div>
  );
}

function SourcePreviewModal(props: {
  preview: SourcePreview;
  onClose: () => void;
}) {
  const { preview } = props;
  const lines = preview.source?.content.split(/\r?\n/) ?? [];
  const focusStart = preview.startLine ?? preview.source?.start_line ?? 1;
  const focusEnd = preview.endLine ?? preview.source?.end_line ?? focusStart;
  const preRef = useRef<HTMLPreElement | null>(null);

  useEffect(() => {
    if (!preview.source || !preRef.current) return;
    const lineHeight = 20;
    preRef.current.scrollTop = Math.max(0, (focusStart - 4) * lineHeight);
  }, [focusStart, preview.source]);

  return (
    <div className="source-backdrop" onMouseDown={props.onClose}>
      <section
        className="source-modal"
        onMouseDown={(event) => event.stopPropagation()}
        aria-label="源码位置"
      >
        <header className="source-head">
          <div>
            <strong>{preview.title}</strong>
            <span>
              {preview.filePath}
              {preview.startLine ? `:${preview.startLine}-${preview.endLine ?? preview.startLine}` : ""}
            </span>
          </div>
          <button type="button" onClick={props.onClose} aria-label="关闭源码窗口">
            <X size={15} />
          </button>
        </header>
        {preview.loading ? (
          <div className="source-state">
            <Loader2 size={18} className="spin" />
            <span>正在读取源码</span>
          </div>
        ) : preview.error ? (
          <div className="source-state error">
            <CircleAlert size={18} />
            <span>{preview.error}</span>
          </div>
        ) : (
          <pre ref={preRef} className="source-code">
            {lines.map((line, index) => {
              const lineNumber = index + 1;
              const highlighted = lineNumber >= focusStart && lineNumber <= focusEnd;
              return (
                <div
                  key={lineNumber}
                  className={`source-line ${highlighted ? "focus" : ""}`}
                >
                  <span className="line-number">{lineNumber}</span>
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

function layoutNodes(
  symbols: SymbolNode[],
  edges: TraceEdge[],
  selectedId: string | null,
  selectedIds: Set<string>,
  relatedIds: Set<string>,
  traceReachable: Set<string> | null,
): Node[] {
  const incoming = new Map<string, number>();
  const outgoing = new Map<string, number>();
  for (const edge of edges) {
    incoming.set(edge.targetId, (incoming.get(edge.targetId) ?? 0) + 1);
    outgoing.set(edge.sourceId, (outgoing.get(edge.sourceId) ?? 0) + 1);
  }

  const visibleSymbols = symbols.filter((symbol) => !traceReachable || traceReachable.has(symbol.id));
  const visibleIds = new Set(visibleSymbols.map((symbol) => symbol.id));
  const visibleEdges = edges.filter(
    (edge) => visibleIds.has(edge.sourceId) && visibleIds.has(edge.targetId),
  );
  const components = connectedComponents(visibleSymbols, visibleEdges);
  const positions = layoutComponents(components, visibleEdges);

  return visibleSymbols.map((symbol) => {
    const position = positions.get(symbol.id) ?? { x: 0, y: 0 };
    const isSelected = symbol.id === selectedId;
    const isMultiSelected = selectedIds.has(symbol.id);
    const isRelated = relatedIds.has(symbol.id);
    const muted =
      selectedIds.size > 1
        ? !isMultiSelected && !isRelated
        : selectedId != null && !isRelated;
    return {
      id: symbol.id,
      type: "default",
      position,
      selected: isMultiSelected,
      data: {
        label: (
          <div
            className={[
              "flow-node",
              symbol.kind,
              isSelected ? "selected" : "",
              isMultiSelected ? "multi-selected" : "",
              isRelated ? "related" : "",
              muted ? "muted" : "",
            ].join(" ")}
            onDoubleClick={(event) => {
              event.stopPropagation();
              window.dispatchEvent(
                new CustomEvent("poltaishow:open-source", { detail: symbol.id }),
              );
            }}
          >
            <span className="node-glyph">{symbolKindInitial(symbol.kind)}</span>
            <span className="node-main">
              <strong title={symbol.qualifiedName}>{symbol.name}</strong>
              <small title={symbol.filePath}>{symbol.folderPath}</small>
            </span>
            <span className="node-degree">
              {incoming.get(symbol.id) ?? 0}/{outgoing.get(symbol.id) ?? 0}
            </span>
          </div>
        ),
        color: NODE_COLOR[symbol.kind],
      },
      style: {
        width: SYMBOL_NODE_WIDTH,
        height: SYMBOL_NODE_HEIGHT,
        background: "transparent",
        border: "none",
        padding: 0,
      },
    };
  });
}

function connectedComponents(symbols: SymbolNode[], edges: TraceEdge[]) {
  const symbolById = new Map(symbols.map((symbol) => [symbol.id, symbol]));
  const adjacency = new Map<string, Set<string>>();
  for (const symbol of symbols) {
    adjacency.set(symbol.id, new Set());
  }
  for (const edge of edges) {
    adjacency.get(edge.sourceId)?.add(edge.targetId);
    adjacency.get(edge.targetId)?.add(edge.sourceId);
  }

  const seen = new Set<string>();
  const components: SymbolNode[][] = [];
  for (const symbol of symbols) {
    if (seen.has(symbol.id)) continue;
    const stack = [symbol.id];
    const component: SymbolNode[] = [];
    seen.add(symbol.id);
    while (stack.length > 0) {
      const current = stack.pop()!;
      const item = symbolById.get(current);
      if (item) component.push(item);
      for (const next of adjacency.get(current) ?? []) {
        if (!seen.has(next)) {
          seen.add(next);
          stack.push(next);
        }
      }
    }
    components.push(component);
  }

  return components.sort((a, b) => b.length - a.length);
}

function layoutComponents(components: SymbolNode[][], edges: TraceEdge[]) {
  const positions = new Map<string, { x: number; y: number }>();
  const componentGapX = 120;
  const componentGapY = 96;
  const rowWidthLimit = 2600;
  let cursorX = 36;
  let cursorY = 36;
  let rowHeight = 0;

  for (const component of components) {
    const layout = layoutSingleComponent(component, edges);
    if (cursorX > 36 && cursorX + layout.width > rowWidthLimit) {
      cursorX = 36;
      cursorY += rowHeight + componentGapY;
      rowHeight = 0;
    }

    for (const [symbolId, point] of layout.positions) {
      positions.set(symbolId, {
        x: cursorX + point.x,
        y: cursorY + point.y,
      });
    }

    cursorX += layout.width + componentGapX;
    rowHeight = Math.max(rowHeight, layout.height);
  }

  return positions;
}

function layoutSingleComponent(component: SymbolNode[], edges: TraceEdge[]) {
  if (component.length === 1) {
    return {
      width: SYMBOL_NODE_WIDTH,
      height: SYMBOL_NODE_HEIGHT,
      positions: new Map([[component[0].id, { x: 0, y: 0 }]]),
    };
  }

  const componentIds = new Set(component.map((symbol) => symbol.id));
  const componentEdges = edges.filter(
    (edge) => componentIds.has(edge.sourceId) && componentIds.has(edge.targetId),
  );
  const graph = new dagre.graphlib.Graph();
  graph.setDefaultEdgeLabel(() => ({}));
  graph.setGraph({
    rankdir: "LR",
    align: "UL",
    nodesep: 42,
    ranksep: 96,
    edgesep: 18,
    marginx: 0,
    marginy: 0,
  });
  for (const symbol of component) {
    graph.setNode(symbol.id, {
      width: SYMBOL_NODE_WIDTH,
      height: SYMBOL_NODE_HEIGHT,
    });
  }
  for (const edge of componentEdges) {
    graph.setEdge(edge.sourceId, edge.targetId);
  }
  dagre.layout(graph);

  const positions = new Map<string, { x: number; y: number }>();
  let minX = Number.POSITIVE_INFINITY;
  let minY = Number.POSITIVE_INFINITY;
  let maxX = Number.NEGATIVE_INFINITY;
  let maxY = Number.NEGATIVE_INFINITY;
  for (const symbol of component) {
    const node = graph.node(symbol.id) as { x: number; y: number } | undefined;
    const x = (node?.x ?? 0) - SYMBOL_NODE_WIDTH / 2;
    const y = (node?.y ?? 0) - SYMBOL_NODE_HEIGHT / 2;
    positions.set(symbol.id, { x, y });
    minX = Math.min(minX, x);
    minY = Math.min(minY, y);
    maxX = Math.max(maxX, x + SYMBOL_NODE_WIDTH);
    maxY = Math.max(maxY, y + SYMBOL_NODE_HEIGHT);
  }

  for (const [symbolId, point] of positions) {
    positions.set(symbolId, {
      x: point.x - minX,
      y: point.y - minY,
    });
  }

  return {
    width: Math.max(SYMBOL_NODE_WIDTH, maxX - minX),
    height: Math.max(SYMBOL_NODE_HEIGHT, maxY - minY),
    positions,
  };
}

function layoutEdges(
  edges: TraceEdge[],
  selectedId: string | null,
  selectedIds: Set<string>,
  traceReachable: Set<string> | null,
): Edge[] {
  return edges
    .filter((edge) => !traceReachable || (traceReachable.has(edge.sourceId) && traceReachable.has(edge.targetId)))
    .map((edge) => {
      const highlighted =
        selectedIds.size > 1
          ? selectedIds.has(edge.sourceId) && selectedIds.has(edge.targetId)
          : selectedId != null && (edge.sourceId === selectedId || edge.targetId === selectedId);
      const color = EDGE_COLOR[edge.kind];
      return {
        id: edge.id,
        source: edge.sourceId,
        target: edge.targetId,
        type: "smoothstep",
        animated: edge.kind === "arg" || highlighted,
        label: edgeLabel(edge),
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color,
          width: 14,
          height: 14,
        },
        style: {
          stroke: color,
          strokeWidth: highlighted ? 3.4 : edge.kind === "call" ? 2.2 : 2,
          opacity: selectedId == null || highlighted ? 0.96 : 0.36,
        },
        labelStyle: {
          fill: "#e7edf4",
          fontSize: 11,
          fontWeight: 700,
        },
        labelBgStyle: {
          fill: "#0b1017",
          fillOpacity: 0.94,
        },
        labelBgPadding: [7, 4] as [number, number],
      };
    });
}

function edgeLabel(edge: TraceEdge): string {
  if (edge.kind === "arg") {
    return `${edge.sourceSlot || edge.variableName || "arg"} -> ${edge.targetSlot || "param"}`;
  }
  if (edge.kind === "return") {
    return `${edge.sourceSlot || "return"} -> ${edge.targetSlot || edge.variableName || "result"}`;
  }
  if (edge.kind === "call") {
    return edge.label && edge.label !== "call" ? "调用" : EDGE_LABEL.call;
  }
  return edge.label || EDGE_LABEL[edge.kind];
}

function kindLabel(kind: SymbolFilter | SymbolNode["kind"]) {
  if (kind === "all") return "全部";
  if (kind === "function") return "函数";
  if (kind === "method") return "方法";
  return "类";
}

function symbolKindInitial(kind: SymbolNode["kind"]) {
  if (kind === "function") return "F";
  if (kind === "method") return "M";
  return "C";
}

function buildFileTree(files: ProjectFile[]): FileTreeNode {
  const root: FileTreeNode = {
    id: "root",
    name: "project",
    path: "",
    kind: "root",
    fileCount: 0,
    symbolCount: 0,
    children: [],
  };
  const folderByPath = new Map<string, FileTreeNode>([["", root]]);

  for (const file of files) {
    const relativeParts = splitPath(file.folder_path);
    let parent = root;
    let currentPath = "";
    for (const part of relativeParts) {
      currentPath = currentPath ? `${currentPath}/${part}` : part;
      let folder = folderByPath.get(currentPath);
      if (!folder) {
        folder = {
          id: `folder:${currentPath}`,
          name: part,
          path: currentPath,
          kind: "folder",
          fileCount: 0,
          symbolCount: 0,
          children: [],
        };
        folderByPath.set(currentPath, folder);
        parent.children.push(folder);
      }
      parent = folder;
    }
    parent.children.push({
      id: `file:${file.file_path}`,
      name: file.file_name,
      path: file.file_path,
      kind: "file",
      file,
      fileCount: 1,
      symbolCount: file.symbol_count,
      children: [],
    });
  }

  accumulateTree(root);
  sortTree(root);
  return root;
}

function splitPath(path: string): string[] {
  if (!path || path === "(root)") return [];
  return path.replace(/\\/g, "/").split("/").filter(Boolean);
}

function accumulateTree(node: FileTreeNode): { files: number; symbols: number } {
  if (node.kind === "file") {
    return { files: 1, symbols: node.symbolCount };
  }
  let fileCount = 0;
  let symbolCount = 0;
  for (const child of node.children) {
    const result = accumulateTree(child);
    fileCount += result.files;
    symbolCount += result.symbols;
  }
  node.fileCount = fileCount;
  node.symbolCount = symbolCount;
  return { files: fileCount, symbols: symbolCount };
}

function sortTree(node: FileTreeNode) {
  node.children.sort((a, b) => {
    if (a.kind !== b.kind) return a.kind === "folder" ? -1 : 1;
    if (a.symbolCount !== b.symbolCount) return b.symbolCount - a.symbolCount;
    return a.name.localeCompare(b.name);
  });
  for (const child of node.children) sortTree(child);
}

function symbolMatchesScope(symbol: SymbolNode, scope: ScopeSelection): boolean {
  if (!scope || scope.kind === "root") return true;
  if (scope.kind === "file") {
    return normalizePath(symbol.filePath) === normalizePath(scope.path);
  }
  const folder = normalizeRelativePath(symbol.folderPath);
  const selected = normalizeRelativePath(scope.path);
  return folder === selected || folder.startsWith(`${selected}/`);
}

function normalizePath(value: string): string {
  return value.replace(/\\/g, "/").toLowerCase();
}

function normalizeRelativePath(value: string): string {
  const normalized = normalizePath(value);
  return normalized === "(root)" ? "" : normalized.replace(/^\/+|\/+$/g, "");
}

function sameStringSet(left: Set<string>, right: Set<string>): boolean {
  if (left.size !== right.size) return false;
  for (const item of left) {
    if (!right.has(item)) return false;
  }
  return true;
}

async function pollAnalysis(
  id: string,
  loadGraph: (id: string) => Promise<void>,
  setProgress: (progress: AnalysisProgress) => void,
  setStatus: (status: AnalysisStatus) => void,
  setError: (message: string) => void,
) {
  for (let attempt = 0; attempt < 60; attempt += 1) {
    await new Promise((resolve) => window.setTimeout(resolve, 1000));
    try {
      const next = await api.getAnalysis(id);
      setProgress(next);
      setStatus(next.status);
      if (next.status === "completed") {
        await loadGraph(id);
        return;
      }
      if (next.status === "failed") {
        setError(next.error_message || next.message || "分析失败");
        return;
      }
    } catch {
      if (attempt > 5) {
        setError("无法连接后端进度接口");
        return;
      }
    }
  }
}
