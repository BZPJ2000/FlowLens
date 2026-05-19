import { useCallback, useMemo, useEffect, memo, useRef } from "react";
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  useReactFlow,
  type Node,
  type Edge,
  BackgroundVariant,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import FileGroupNode from "./FileGroupNode";
import FunctionSubNode from "./FunctionSubNode";
import ClassGroupNode from "./ClassGroupNode";
import MethodSubNode from "./MethodSubNode";
import DataFlowEdge from "./DataFlowEdge";
import { computeLayout } from "./layout";
import { useGraphStore } from "../../stores/graphStore";

const nodeTypes = {
  fileGroup: FileGroupNode,
  functionSub: FunctionSubNode,
  classGroup: ClassGroupNode,
  methodSub: MethodSubNode,
} as const;
const edgeTypes = { dataFlow: DataFlowEdge } as const;

// ── Helpers ─────────────────────────────────────

function getNeighborIds(nodeId: string, edges: Edge[]): Set<string> {
  const neighbors = new Set<string>([nodeId]);
  edges.forEach((e) => {
    if (e.source === nodeId) neighbors.add(e.target);
    if (e.target === nodeId) neighbors.add(e.source);
  });
  return neighbors;
}

function getConnectedPath(
  startNodeId: string,
  edges: Edge[],
  maxDepth = 8,
): Set<string> {
  const pathSet = new Set<string>([startNodeId]);
  let frontier = new Set<string>([startNodeId]);

  for (let depth = 0; depth < maxDepth && frontier.size > 0; depth++) {
    const nextFrontier = new Set<string>();
    for (const nid of frontier) {
      for (const e of edges) {
        if (e.source === nid && !pathSet.has(e.target)) {
          pathSet.add(e.target);
          nextFrontier.add(e.target);
        }
        if (e.target === nid && !pathSet.has(e.source)) {
          pathSet.add(e.source);
          nextFrontier.add(e.source);
        }
      }
    }
    frontier = nextFrontier;
  }

  return pathSet;
}

// ── Component ───────────────────────────────────

const FlowCanvas = memo(() => {
  const graph = useGraphStore((s) => s.graph);
  const selectNode = useGraphStore((s) => s.selectNode);
  const selectedNodeId = useGraphStore((s) => s.selectedNodeId);
  const toggleDetailPanel = useGraphStore((s) => s.toggleDetailPanel);
  const searchQuery = useGraphStore((s) => s.searchQuery);
  const focusNodeId = useGraphStore((s) => s.focusNodeId);
  const setFocusNodeId = useGraphStore((s) => s.setFocusNodeId);
  const tracedNodeId = useGraphStore((s) => s.tracedNodeId);
  const setTracedNodeId = useGraphStore((s) => s.setTracedNodeId);
  const isPlaying = useGraphStore((s) => s.isPlaying);
  const playingNodeId = useGraphStore((s) => s.playingNodeId);
  const playOrder = useGraphStore((s) => s.playOrder);
  const setPlayingNodeId = useGraphStore((s) => s.setPlayingNodeId);
  const setPlayOrder = useGraphStore((s) => s.setPlayOrder);
  const stopPlay = useGraphStore((s) => s.stopPlay);

  const { setCenter } = useReactFlow();
  const canvasRef = useRef<HTMLDivElement>(null);

  // Compute flex-wrap adaptive layout
  const initialLayout = useMemo(() => {
    if (!graph || !graph.nodes || graph.nodes.length === 0) {
      return { nodes: [] as Node[], edges: [] as Edge[], playOrder: [] as string[] };
    }
    const result = computeLayout(
      graph.nodes,
      graph.edges,
      graph.entry_points,
      graph.exit_points,
    );
    return {
      nodes: [...result.fileNodes, ...result.fnNodes],
      edges: result.edges,
      playOrder: result.playOrder,
    };
  }, [graph]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialLayout.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialLayout.edges);

  // Reset when graph changes
  useEffect(() => {
    setNodes(initialLayout.nodes);
    setEdges(initialLayout.edges);
    setPlayOrder(initialLayout.playOrder);
  }, [initialLayout, setEdges, setNodes, setPlayOrder]);

  // ── Focus on search match ──────────────────
  useEffect(() => {
    if (focusNodeId) {
      const nodeToFocus = nodes.find((n) => n.id === focusNodeId);
      if (nodeToFocus) {
        setCenter(
          nodeToFocus.position.x + (nodeToFocus.style?.width as number || 180) / 2,
          nodeToFocus.position.y + (nodeToFocus.style?.height as number || 40) / 2,
          { zoom: 0.7, duration: 600 },
        );
      }
      setTimeout(() => setFocusNodeId(null), 100);
    }
  }, [focusNodeId]);

  // ── Selection dimming ──────────────────────
  useEffect(() => {
    if (!selectedNodeId) {
      setNodes((nds) =>
        nds.map((n) => ({
          ...n,
          data: { ...n.data, isSelected: false, isDimmed: false, isPathHighlighted: false },
        })),
      );
      setEdges((eds) =>
        eds.map((e) => ({
          ...e,
          data: { ...e.data, isDimmed: false, isPathHighlighted: false },
        })),
      );
      return;
    }

    const neighbors = getNeighborIds(selectedNodeId, edges);

    setNodes((nds) =>
      nds.map((n) => ({
        ...n,
        data: {
          ...n.data,
          isSelected: n.id === selectedNodeId,
          isDimmed: !neighbors.has(n.id),
        },
      })),
    );

    setEdges((eds) =>
      eds.map((e) => ({
        ...e,
        data: {
          ...e.data,
          isDimmed: e.source !== selectedNodeId && e.target !== selectedNodeId,
        },
      })),
    );
  }, [selectedNodeId]);

  // ── Path tracing (double-click / trace mode) ──
  useEffect(() => {
    if (!tracedNodeId) return;

    const pathSet = getConnectedPath(tracedNodeId, edges);

    setNodes((nds) =>
      nds.map((n) => ({
        ...n,
        data: {
          ...n.data,
          isPathHighlighted: pathSet.has(n.id),
          isDimmed: !pathSet.has(n.id),
        },
      })),
    );

    setEdges((eds) =>
      eds.map((e) => ({
        ...e,
        data: {
          ...e.data,
          isPathHighlighted: pathSet.has(e.id),
          isDimmed: !pathSet.has(e.id),
        },
      })),
    );

    const timer = setTimeout(() => setTracedNodeId(null), 5000);
    return () => clearTimeout(timer);
  }, [tracedNodeId]);

  // ── Search dimming ────────────────────────
  useEffect(() => {
    if (!searchQuery || searchQuery.length < 1) {
      if (!selectedNodeId && !tracedNodeId) {
        setNodes((nds) =>
          nds.map((n) => ({ ...n, data: { ...n.data, isDimmed: false } })),
        );
        setEdges((eds) =>
          eds.map((e) => ({ ...e, data: { ...e.data, isDimmed: false } })),
        );
      }
      return;
    }

    const q = searchQuery.toLowerCase();
    const matchIds = new Set<string>();
    for (const n of nodes) {
      const name = String((n.data as Record<string, unknown>).name || "").toLowerCase();
      const fileName = String((n.data as Record<string, unknown>).file_name || "").toLowerCase();
      const dataType = String((n.data as Record<string, unknown>).data_type || "").toLowerCase();
      if (name.includes(q) || fileName.includes(q) || dataType.includes(q)) {
        matchIds.add(n.id);
      }
    }

    setNodes((nds) =>
      nds.map((n) => ({
        ...n,
        data: { ...n.data, isDimmed: !matchIds.has(n.id) },
      })),
    );

    const matchEdgeIds = new Set<string>();
    for (const e of edges) {
      if (matchIds.has(e.source) && matchIds.has(e.target)) {
        matchEdgeIds.add(e.id);
      }
    }
    setEdges((eds) =>
      eds.map((e) => ({
        ...e,
        data: { ...e.data, isDimmed: !matchEdgeIds.has(e.id) },
      })),
    );
  }, [searchQuery]);

  // ── Event handlers ────────────────────────
  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      selectNode(node.id);
      toggleDetailPanel();
    },
    [selectNode, toggleDetailPanel],
  );

  const onNodeDoubleClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      setTracedNodeId(node.id);
    },
    [setTracedNodeId],
  );

  const onEdgeClick = useCallback(
    (_: React.MouseEvent, edge: Edge) => {
      setTracedNodeId(edge.source);
    },
    [setTracedNodeId],
  );

  const onPaneClick = useCallback(() => {
    selectNode(null);
    setTracedNodeId(null);
  }, [selectNode, setTracedNodeId]);

  // ── Animation playback ───────────────────
  useEffect(() => {
    if (!isPlaying || !playingNodeId || playOrder.length === 0) return;

    // Highlight current playing node and its connected edges
    const currentIdx = playOrder.indexOf(playingNodeId);
    const connectedEdgeIds = new Set<string>();
    edges.forEach((e) => {
      if (e.source === playingNodeId || e.target === playingNodeId) {
        connectedEdgeIds.add(e.id);
      }
    });

    setNodes((nds) =>
      nds.map((n) => ({
        ...n,
        data: {
          ...n.data,
          isPathHighlighted: n.id === playingNodeId || n.parentId === playingNodeId,
          isDimmed: n.id !== playingNodeId && n.parentId !== playingNodeId,
        },
      })),
    );
    setEdges((eds) =>
      eds.map((e) => ({
        ...e,
        data: {
          ...e.data,
          isPathHighlighted: connectedEdgeIds.has(e.id),
          isDimmed: !connectedEdgeIds.has(e.id),
          animating: connectedEdgeIds.has(e.id),
        },
      })),
    );

    // Advance to next node after delay
    const timer = setTimeout(() => {
      const nextIdx = currentIdx + 1;
      if (nextIdx < playOrder.length) {
        setPlayingNodeId(playOrder[nextIdx]);
      } else {
        // Animation complete — reset
        stopPlay();
        setNodes((nds) =>
          nds.map((n) => ({ ...n, data: { ...n.data, isPathHighlighted: false, isDimmed: false } })),
        );
        setEdges((eds) =>
          eds.map((e) => ({ ...e, data: { ...e.data, isPathHighlighted: false, isDimmed: false, animating: true } })),
        );
      }
    }, 1500);

    return () => clearTimeout(timer);
  }, [isPlaying, playingNodeId, playOrder]);

  // ── Keyboard shortcuts ────────────────────
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        selectNode(null);
        setTracedNodeId(null);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [selectNode, setTracedNodeId]);

  // ── Export PNG ─────────────────────────────
  const handleExport = useCallback(() => {
    const svgEl = canvasRef.current?.querySelector(".react-flow__renderer svg");
    if (!svgEl) return;

    const svgData = new XMLSerializer().serializeToString(svgEl);
    const svgBlob = new Blob([svgData], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(svgBlob);

    const img = new Image();
    img.onload = () => {
      const canvas = document.createElement("canvas");
      canvas.width = img.width * 2;
      canvas.height = img.height * 2;
      const ctx = canvas.getContext("2d")!;
      ctx.scale(2, 2);
      ctx.fillStyle = "#06060a";
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0);
      URL.revokeObjectURL(url);

      canvas.toBlob((blob) => {
        if (!blob) return;
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = "poltai-pipeline.png";
        a.click();
      }, "image/png");
    };
    img.src = url;
  }, []);

  // ── Render ─────────────────────────────────
  return (
    <div ref={canvasRef} className="w-full h-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        onNodeDoubleClick={onNodeDoubleClick}
        onEdgeClick={onEdgeClick}
        onPaneClick={onPaneClick}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        fitView
        fitViewOptions={{ padding: 0.2, maxZoom: 0.9 }}
        minZoom={0.05}
        maxZoom={2}
        defaultEdgeOptions={{ type: "dataFlow", animated: false }}
        proOptions={{ hideAttribution: true }}
        deleteKeyCode={null}
        multiSelectionKeyCode={null}
      >
        <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#1e1e3a" />
        <Controls
          className="!bg-[#12121c] !border-[#1e1e3a] !rounded-lg !shadow-lg"
          position="bottom-right"
        />
        <MiniMap
          nodeColor={(n: Node) => {
            if (n.type === "fileGroup") return "#3b82f6";
            if (n.type === "functionSub") return "#60a5fa";
            if (n.type === "classGroup") return "#f59e0b";
            return "#475569";
          }}
          maskColor="rgba(6,6,10,0.7)"
          style={{ background: "#0f0f1a", borderRadius: 8 }}
          position="bottom-left"
        />
      </ReactFlow>

      {/* Export button */}
      <button
        onClick={handleExport}
        className="absolute top-3 right-3 z-10 flex items-center gap-1.5 text-[10px] px-2.5 py-1.5 rounded-lg border border-[#1e1e3a] bg-[#0a0a10]/90 backdrop-blur-sm text-[#6b7280] hover:text-[#a1a1aa] hover:border-[#2a2a4a] transition-all"
        title="Export PNG"
      >
        <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3" />
        </svg>
        Export
      </button>

      {/* Path trace indicator */}
      {tracedNodeId && (
        <div className="absolute top-3 left-1/2 -translate-x-1/2 z-10 flex items-center gap-2 text-[10px] px-3 py-1.5 rounded-full border border-[#7c3aed]/30 bg-[#7c3aed]/10 text-[#a78bfa] backdrop-blur-sm animate-fade-in">
          <span className="w-1.5 h-1.5 rounded-full bg-[#a78bfa] animate-pulse" />
          Trace mode
          <button
            onClick={() => setTracedNodeId(null)}
            className="ml-1 text-[#6b7280] hover:text-[#f5f5f7]"
          >
            Esc
          </button>
        </div>
      )}
    </div>
  );
});

FlowCanvas.displayName = "FlowCanvas";

const FlowCanvasWithProvider = () => (
  <ReactFlowProvider>
    <FlowCanvas />
  </ReactFlowProvider>
);
export default FlowCanvasWithProvider;
