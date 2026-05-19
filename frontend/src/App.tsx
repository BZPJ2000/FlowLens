import { useState, useCallback, useEffect } from "react";
import {
  ArrowLeft, FileText, MessageSquare, Pause, Play,
  Gauge, Search, Map, X, History,
} from "lucide-react";
import { FlowCanvas, LegendPanel } from "./components/graph";
import { DetailPanel } from "./components/common";
import { ChatPanel } from "./components/chat";
import HistorySidebar from "./components/common/HistorySidebar";
import { useGraphStore } from "./stores/graphStore";
import { api } from "./api/client";
import ImportPage from "./pages/ImportPage";
import ReportPage from "./pages/ReportPage";

type View = "import" | "visualize" | "report";

export default function App() {
  const [view, setView] = useState<View>("import");
  const [showHistory, setShowHistory] = useState(false);
  const analysisId = useGraphStore((s) => s.analysisId);
  const setAnalysisId = useGraphStore((s) => s.setAnalysisId);
  const setProgress = useGraphStore((s) => s.setProgress);
  const status = useGraphStore((s) => s.status);
  const progressPct = useGraphStore((s) => s.progressPct);
  const progressMessage = useGraphStore((s) => s.progressMessage);
  const graph = useGraphStore((s) => s.graph);
  const setGraph = useGraphStore((s) => s.setGraph);
  const isPlaying = useGraphStore((s) => s.isPlaying);
  const startPlay = useGraphStore((s) => s.startPlay);
  const stopPlay = useGraphStore((s) => s.stopPlay);
  const playOrder = useGraphStore((s) => s.playOrder);
  const speed = useGraphStore((s) => s.dataFlowSpeed);
  const setSpeed = useGraphStore((s) => s.setDataFlowSpeed);
  const showDetailPanel = useGraphStore((s) => s.showDetailPanel);
  const showChatPanel = useGraphStore((s) => s.showChatPanel);
  const showLegend = useGraphStore((s) => s.showLegend);
  const toggleLegend = useGraphStore((s) => s.toggleLegend);
  const toggleChatPanel = useGraphStore((s) => s.toggleChatPanel);
  const selectedNodeId = useGraphStore((s) => s.selectedNodeId);
  const searchQuery = useGraphStore((s) => s.searchQuery);
  const setSearchQuery = useGraphStore((s) => s.setSearchQuery);
  const setFocusNodeId = useGraphStore((s) => s.setFocusNodeId);

  const handleStart = useCallback(
    async (id: string) => {
      setView("visualize");
      setAnalysisId(id);

      // 立即加载图数据（ImportPage 已确认分析完成）
      const loadGraph = async () => {
        try {
          const graphData = await api.getGraph(id);
          if (graphData && graphData.nodes?.length > 0) {
            setGraph({
              nodes: graphData.nodes,
              edges: graphData.edges,
              entry_points: graphData.entry_points,
              exit_points: graphData.exit_points,
            });
            setProgress(100, "分析完成", "completed");
            return true;
          }
          return false;
        } catch {
          return false;
        }
      };

      if (await loadGraph()) return;

      // 如果图数据未就绪（极端情况），轮询等待
      const poll = setInterval(async () => {
        try {
          const analysis = await api.getAnalysis(id);
          if (analysis.status === "completed") {
            clearInterval(poll);
            await loadGraph();
          } else if (analysis.status === "failed") {
            clearInterval(poll);
          }
        } catch {
          // retry on next poll
        }
      }, 1500);
    },
    [setGraph, setAnalysisId, setProgress],
  );

  // Handle search → focus first match
  const handleSearchKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Enter" && graph && searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        // Search file nodes first
        let match = graph.nodes.find((n) => {
          const name = n.file_name.toLowerCase();
          const summary = n.summary.toLowerCase();
          return name.includes(q) || summary.includes(q) || n.file_path.toLowerCase().includes(q);
        });

        // If no file match, search functions
        if (!match) {
          for (const n of graph.nodes) {
            if (n.functions) {
              const fn = n.functions.find((f) =>
                f.name.toLowerCase().includes(q),
              );
              if (fn) {
                match = n; // Focus the parent file
                break;
              }
            }
          }
        }

        if (match) setFocusNodeId(match.id);
      }
    },
    [graph, searchQuery, setFocusNodeId],
  );

  if (view === "import") {
    return (
      <div className="w-full h-full flex bg-[#06060a]">
        <HistorySidebar onSelect={handleStart} />
        <div className="flex-1">
          <ImportPage onStart={handleStart} />
        </div>
      </div>
    );
  }

  if (view === "report") {
    return <ReportPage onBack={() => setView("visualize")} />;
  }

  const nodeCount = graph?.nodes.length || 0;
  const edgeCount = graph?.edges.length || 0;
  const isAnalyzing = status !== "completed" && status !== "failed";
  const isReady = status === "completed";

  return (
    <div className="w-full h-full flex flex-col bg-[#06060a]">
      {/* ── Top Bar ──────────────────────────── */}
      <div className="flex-shrink-0 h-10 bg-[#0a0a10] border-b border-[#1e1e3a] flex items-center justify-between px-3 gap-3">
        {/* Left section */}
        <div className="flex items-center gap-3 flex-shrink-0">
          <button
            onClick={() => setView("import")}
            className="flex items-center gap-1 text-xs text-[#a1a1aa] hover:text-[#f5f5f7] transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Import</span>
          </button>

          <span className="text-xs font-bold text-[#f5f5f7] tracking-tight">
            PoltAIshow
          </span>

          {/* Progress bar */}
          {isAnalyzing && (
            <div className="flex items-center gap-2 ml-2">
              <div className="w-24 h-1.5 bg-[#1a1a2e] rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-[#7c3aed] to-[#a78bfa] rounded-full transition-all duration-500 ease-out"
                  style={{ width: `${Math.max(2, progressPct)}%` }}
                />
              </div>
              <span className="text-[10px] text-[#6b7280] whitespace-nowrap max-w-[160px] truncate">
                {progressMessage || `${progressPct}%`}
              </span>
            </div>
          )}
        </div>

        {/* Center: Search */}
        {isReady && (
          <div className="flex-1 max-w-md">
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[#4b5563]" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={handleSearchKeyDown}
                placeholder="Search files..."
                className="w-full bg-[#12121c] border border-[#1e1e3a] rounded-lg pl-7 pr-7 py-1.5 text-[11px] text-[#f5f5f7] placeholder-[#4b5563] focus:outline-none focus:border-[#7c3aed]/50 focus:ring-1 focus:ring-[#7c3aed]/20 transition-all"
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery("")}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-[#4b5563] hover:text-[#a1a1aa]"
                >
                  <X className="w-3 h-3" />
                </button>
              )}
            </div>
          </div>
        )}

        {/* Right section */}
        <div className="flex items-center gap-1 flex-shrink-0">
          {/* Animation toggle */}
          <button
            onClick={() => {
              if (isPlaying) {
                stopPlay();
              } else if (graph) {
                const nodeIds = playOrder.length > 0 ? playOrder : graph.nodes.map((n) => n.id);
                startPlay(nodeIds);
              }
            }}
            disabled={!isReady}
            className={`flex items-center gap-1 text-[10px] px-2 py-1 rounded border transition-all ${
              isPlaying && isReady
                ? "border-[#7c3aed]/40 bg-[#7c3aed]/10 text-[#a78bfa]"
                : "border-[#1e1e3a] bg-[#12121c] text-[#6b7280] hover:text-[#a1a1aa]"
            } disabled:opacity-40 disabled:cursor-not-allowed`}
          >
            {isPlaying ? <Pause className="w-3 h-3" /> : <Play className="w-3 h-3" />}
            <span className="hidden sm:inline">{isPlaying ? "Stop" : "Play"}</span>
          </button>

          {/* Speed */}
          <div className="flex items-center gap-1 text-[10px] text-[#6b7280] border border-[#1e1e3a] rounded px-1.5 py-1">
            <Gauge className="w-3 h-3" />
            <select
              value={speed}
              onChange={(e) => setSpeed(Number(e.target.value))}
              className="bg-transparent text-[#a1a1aa] focus:outline-none text-[10px]"
            >
              <option value={0.5}>0.5x</option>
              <option value={1}>1x</option>
              <option value={2}>2x</option>
              <option value={3}>3x</option>
            </select>
          </div>

          {/* Legend toggle */}
          <button
            onClick={toggleLegend}
            disabled={!isReady}
            className={`flex items-center gap-1 text-[10px] px-2 py-1 rounded border transition-all ${
              showLegend
                ? "border-[#7c3aed]/40 bg-[#7c3aed]/10 text-[#a78bfa]"
                : "border-[#1e1e3a] bg-[#12121c] text-[#6b7280] hover:text-[#a1a1aa]"
            } disabled:opacity-40 disabled:cursor-not-allowed`}
          >
            <Map className="w-3 h-3" />
            <span className="hidden sm:inline">Legend</span>
          </button>

          {/* Report button */}
          <button
            onClick={() => setView("report")}
            disabled={!isReady}
            className="flex items-center gap-1 text-[10px] px-2 py-1 rounded border border-[#1e1e3a] bg-[#12121c] text-[#a1a1aa] hover:text-[#f5f5f7] hover:border-[#2a2a4a] disabled:opacity-40 disabled:cursor-not-allowed transition-all"
          >
            <FileText className="w-3 h-3" />
            <span className="hidden sm:inline">Report</span>
          </button>

          {/* Chat toggle */}
          <button
            onClick={toggleChatPanel}
            disabled={!isReady}
            className={`flex items-center gap-1 text-[10px] px-2 py-1 rounded border transition-all ${
              showChatPanel
                ? "border-[#7c3aed]/40 bg-[#7c3aed]/10 text-[#a78bfa]"
                : "border-[#1e1e3a] bg-[#12121c] text-[#a1a1aa] hover:text-[#f5f5f7] hover:border-[#2a2a4a]"
            } disabled:opacity-40 disabled:cursor-not-allowed`}
          >
            <MessageSquare className="w-3 h-3" />
            <span className="hidden sm:inline">AI</span>
          </button>

          {/* History toggle */}
          <button
            onClick={() => setShowHistory((v) => !v)}
            className={`flex items-center gap-1 text-[10px] px-2 py-1 rounded border transition-all ${
              showHistory
                ? "border-[#7c3aed]/40 bg-[#7c3aed]/10 text-[#a78bfa]"
                : "border-[#1e1e3a] bg-[#12121c] text-[#a1a1aa] hover:text-[#f5f5f7] hover:border-[#2a2a4a]"
            }`}
          >
            <History className="w-3 h-3" />
            <span className="hidden sm:inline">History</span>
          </button>
        </div>
      </div>

      {/* ── Main Canvas ───────────────────────── */}
      <div className="flex-1 flex overflow-hidden relative">
        {showHistory && <HistorySidebar onSelect={handleStart} />}
        <div className="flex-1 relative">
          <FlowCanvas />
          {/* Legend overlay */}
          <LegendPanel visible={showLegend} onClose={toggleLegend} />
        </div>
        {showDetailPanel && !showChatPanel && <DetailPanel />}
        {showChatPanel && <ChatPanel />}
      </div>

      {/* ── Bottom Bar ────────────────────────── */}
      <div className="flex-shrink-0 h-7 bg-[#0a0a10] border-t border-[#1e1e3a] flex items-center justify-between px-4 text-[10px] text-[#6b7280]">
        <div className="flex items-center gap-5">
          <span>
            Nodes: <span className="text-[#a1a1aa] font-mono">{nodeCount}</span>
          </span>
          <span>
            Edges: <span className="text-[#a1a1aa] font-mono">{edgeCount}</span>
          </span>
          {graph?.entry_points && graph.entry_points.length > 0 && (
            <span>
              Entry:{" "}
              <span className="text-green-400 font-mono">{graph.entry_points.length}</span>
            </span>
          )}
          {graph?.exit_points && graph.exit_points.length > 0 && (
            <span>
              Exit:{" "}
              <span className="text-red-400 font-mono">{graph.exit_points.length}</span>
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          {selectedNodeId && (
            <span className="text-[#a78bfa]">
              {graph?.nodes.find((n) => n.id === selectedNodeId)?.file_name}
            </span>
          )}
          {isAnalyzing && (
            <span className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-[#7c3aed] animate-pulse" />
              Analyzing...
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
