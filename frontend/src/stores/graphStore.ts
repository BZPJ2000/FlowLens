import { create } from "zustand";
import type {
  AnalysisStatus,
  DataFlowGraph,
  GraphNode,
  GraphEdge,
  AIFileAnalysis,
  AnalysisReport,
} from "../types";

interface GraphState {
  // 分析状态
  analysisId: string | null;
  status: AnalysisStatus;
  progressPct: number;
  progressMessage: string;

  // 图数据
  graph: DataFlowGraph | null;
  selectedNodeId: string | null;
  selectedFileDetail: AIFileAnalysis | null;

  // 报告
  report: AnalysisReport | null;

  // UI 状态
  showDetailPanel: boolean;
  showChatPanel: boolean;
  showLegend: boolean;
  dataFlowAnimating: boolean;
  dataFlowSpeed: number;

  // 搜索 & 路径追踪
  searchQuery: string;
  focusNodeId: string | null;
  tracedNodeId: string | null;

  // 动画播放
  isPlaying: boolean;
  playingNodeId: string | null;
  playOrder: string[]; // 拓扑排序的文件节点 ID 列表

  // Actions
  setAnalysisId: (id: string) => void;
  setProgress: (pct: number, message: string, status: AnalysisStatus) => void;
  setGraph: (graph: DataFlowGraph) => void;
  selectNode: (nodeId: string | null) => void;
  setFileDetail: (detail: AIFileAnalysis | null) => void;
  setReport: (report: AnalysisReport) => void;
  toggleDetailPanel: () => void;
  toggleChatPanel: () => void;
  toggleLegend: () => void;
  toggleDataFlowAnimation: () => void;
  setDataFlowSpeed: (speed: number) => void;
  setSearchQuery: (query: string) => void;
  setFocusNodeId: (id: string | null) => void;
  setTracedNodeId: (id: string | null) => void;

  // 动画播放 actions
  startPlay: (order: string[]) => void;
  stopPlay: () => void;
  setPlayingNodeId: (id: string | null) => void;
  setPlayOrder: (order: string[]) => void;
}

export const useGraphStore = create<GraphState>((set) => ({
  analysisId: null,
  status: "pending",
  progressPct: 0,
  progressMessage: "",

  graph: null,
  selectedNodeId: null,
  selectedFileDetail: null,

  report: null,

  showDetailPanel: false,
  showChatPanel: false,
  showLegend: false,
  dataFlowAnimating: true,
  dataFlowSpeed: 1,

  searchQuery: "",
  focusNodeId: null,
  tracedNodeId: null,

  isPlaying: false,
  playingNodeId: null,
  playOrder: [],

  setAnalysisId: (id) => set({ analysisId: id }),

  setProgress: (pct, message, status) =>
    set({ progressPct: pct, progressMessage: message, status }),

  setGraph: (graph) => set({ graph }),

  selectNode: (nodeId) =>
    set({
      selectedNodeId: nodeId,
      showDetailPanel: nodeId !== null,
      selectedFileDetail: null,
    }),

  setFileDetail: (detail) => set({ selectedFileDetail: detail }),

  setReport: (report) => set({ report }),

  toggleDetailPanel: () =>
    set((s) => ({ showDetailPanel: !s.showDetailPanel })),

  toggleChatPanel: () =>
    set((s) => ({ showChatPanel: !s.showChatPanel })),

  toggleLegend: () =>
    set((s) => ({ showLegend: !s.showLegend })),

  toggleDataFlowAnimation: () =>
    set((s) => ({ dataFlowAnimating: !s.dataFlowAnimating })),

  setDataFlowSpeed: (speed) => set({ dataFlowSpeed: speed }),

  setSearchQuery: (query) => set({ searchQuery: query }),

  setFocusNodeId: (id) => set({ focusNodeId: id }),

  setTracedNodeId: (id) => set({ tracedNodeId: id }),

  startPlay: (order) => set({ isPlaying: true, playOrder: order, playingNodeId: order[0] || null }),

  stopPlay: () => set({ isPlaying: false, playingNodeId: null }),

  setPlayingNodeId: (id) => set({ playingNodeId: id }),

  setPlayOrder: (order) => set({ playOrder: order }),
}));
