import { Position, type Node, type Edge } from "@xyflow/react";
import type { GraphNode as GNode, GraphEdge as GEdge } from "../../types";
import { getBestConnectionSide } from "./portLayout";
import { hierarchicalLayout } from "./hierarchicalLayout";

// ── Sizing Constants ─────────────────────────
const FILE_HEADER_H = 36;
const FILE_FOOTER_H = 26;
const FILE_PADDING = 16;
const FN_W = 240;
const FN_MIN_H = 52;
const FN_PARAM_H = 20;
const CLASS_W = 240;
const CLASS_MIN_H = 60;
const METHOD_H = 64;
const ITEM_GAP = 40;         // 增加函数间距，为内部连线留出空间
const PORT_ROW_H = 18;       // per port row in sidebar
const PORT_SIDEBAR_MIN_W = 100;
const MAX_CONTENT_W = 900;   // max node width before wrapping
const MIN_CONTENT_W = 280;
const ROW_GAP = 72;          // vertical gap between rows
const CARD_GAP = 56;         // horizontal gap between cards
const CANVAS_PADDING = 48;
const CANVAS_MAX_W = 1600;   // effective canvas width

// ── Types ────────────────────────────────────
interface LayoutNode extends Node {
  parentId?: string;
  extent?: "parent";
}

interface LayoutEdge extends Edge {
  data: {
    variable_name: string;
    data_type: string;
    label: string;
    edge_type: "import" | "call" | "export" | "port_to_function" | "function_to_port";
    animating: boolean;
    isDimmed: boolean;
    isPathHighlighted: boolean;
    sourceSide: Position;
    targetSide: Position;
    edgeOffsetX: number;
    edgeOffsetY: number;
  };
}

interface ItemInfo {
  kind: "function" | "class";
  id: string;
  name: string;
  height: number;
  width: number;
  fnParams?: { name: string; type: string }[];
  fnReturnType?: string;
  fnIsExported?: boolean;
  fnIsAsync?: boolean;
  clsMethods?: MethodMeta[];
}

interface MethodMeta {
  id: string; name: string;
  params: { name: string; type: string }[];
  return_type: string;
  is_exported: boolean; is_async: boolean;
  description: string;
}

interface CardBox {
  nodeId: string;
  gNode: GNode;
  items: ItemInfo[];
  naturalW: number;    // natural width from content
  naturalH: number;    // natural height from content
  placedW: number;     // actual width after row distribution
  placedH: number;     // actual height = row height
  placedX: number;
  placedY: number;
  gridCols: number;
  gridRows: number;
}

// ── Filter: skip noise functions ──────────────
const SKIP_FN_NAMES = new Set([
  "init", "__init__", "constructor", "__new__",
  "__del__", "__repr__", "__str__", "__call__",
  "dealloc", "awake", "start", "onEnable", "onDisable",
]);

function isRelevantFunction(name: string): boolean {
  return !SKIP_FN_NAMES.has(name) && !name.startsWith("__") && !name.startsWith("_");
}

// ── Size Calculations ────────────────────────

function fnHeight(params: number): number {
  return Math.max(FN_MIN_H, 28 + params * FN_PARAM_H + 18);
}

function classHeight(methods: { params?: { name: string; type: string }[] }[]): number {
  // Must match the actual layout logic in class sub-node creation
  const CLASS_HEADER = 40; // class header + "N methods" line
  const CLASS_METHOD_GAP = 8;
  const CLASS_PADDING_BOTTOM = 12;
  if (methods.length === 0) return CLASS_MIN_H;
  let totalH = CLASS_HEADER;
  for (const m of methods) {
    const paramCount = m.params?.length || 0;
    const mH = Math.max(FN_MIN_H, 28 + paramCount * FN_PARAM_H + 18);
    totalH += mH + CLASS_METHOD_GAP;
  }
  totalH += CLASS_PADDING_BOTTOM;
  return Math.max(CLASS_MIN_H, totalH);
}

function estimateTextW(text: string, size: number): number {
  return text.length * size * 0.55 + 12;
}

// ── Topological Sort ─────────────────────────

function topoSort(nodes: GNode[], edges: GEdge[], entryPoints: string[]): Map<string, number> {
  const adj = new Map<string, Set<string>>();
  const inDeg = new Map<string, number>();
  const nodeIds = new Set(nodes.map((n) => n.id));
  for (const n of nodes) { adj.set(n.id, new Set()); inDeg.set(n.id, 0); }

  for (const e of edges) {
    if (
      e.source_node_id !== e.target_node_id &&
      nodeIds.has(e.source_node_id) &&
      nodeIds.has(e.target_node_id) &&
      !adj.get(e.source_node_id)?.has(e.target_node_id)
    ) {
      adj.get(e.source_node_id)?.add(e.target_node_id);
      inDeg.set(e.target_node_id, (inDeg.get(e.target_node_id) || 0) + 1);
    }
  }

  const queue: string[] = [];
  const queued = new Set<string>();
  for (const ep of entryPoints) {
    if (inDeg.get(ep) === 0 && !queued.has(ep)) { queue.push(ep); queued.add(ep); }
  }
  for (const [id, deg] of inDeg) {
    if (deg === 0 && !queued.has(id)) { queue.push(id); queued.add(id); }
  }
  if (queue.length === 0) {
    for (const n of nodes) { if (!queued.has(n.id)) { queue.push(n.id); queued.add(n.id); } }
  }

  const order = new Map<string, number>();
  const visited = new Set<string>();
  let idx = 0;
  while (queue.length > 0) {
    const nid = queue.shift()!;
    if (visited.has(nid)) continue;
    visited.add(nid);
    order.set(nid, idx++);
    for (const nb of adj.get(nid) || new Set<string>()) {
      const d = (inDeg.get(nb) || 1) - 1;
      inDeg.set(nb, d);
      if (d === 0 && !visited.has(nb) && !queued.has(nb)) {
        queue.push(nb);
        queued.add(nb);
      }
    }
  }
  for (const n of nodes) {
    if (!visited.has(n.id)) order.set(n.id, idx++);
  }
  return order;
}

// ── Main Layout ──────────────────────────────

/** Resolve the target handle for a function: match variable_name to param → in-{name}, else "call" */
function resolveTargetHandle(
  targetId: string,
  variableName: string,
  fnParamsMap: Map<string, Set<string>>,
): string {
  const params = fnParamsMap.get(targetId);
  if (params && variableName && params.has(variableName)) {
    return `in-${variableName}`;
  }
  return "call";
}

export function computeLayout(
  graphNodes: GNode[], graphEdges: GEdge[],
  entryPoints: string[], exitPoints: string[],
): { fileNodes: LayoutNode[]; fnNodes: LayoutNode[]; edges: LayoutEdge[]; playOrder: string[] } {
  if (!graphNodes || graphNodes.length === 0) {
    return { fileNodes: [], fnNodes: [], edges: [], playOrder: [] };
  }

  const exitSet = new Set(exitPoints);
  const order = topoSort(graphNodes, graphEdges, entryPoints);

  // ── Build card boxes ──────────────────────
  const cards: CardBox[] = [];

  for (const gNode of graphNodes) {
    const items: ItemInfo[] = [];
    const ports = gNode.ports || [];
    const inputPorts = ports.filter((p) => p.direction === "input");
    const outputPorts = ports.filter((p) => p.direction === "output");

    for (const fn of gNode.functions || []) {
      if (!isRelevantFunction(fn.name)) continue;
      items.push({
        kind: "function", id: fn.id, name: fn.name,
        height: fnHeight(fn.params.length), width: FN_W,
        fnParams: fn.params, fnReturnType: fn.return_type,
        fnIsExported: fn.is_exported, fnIsAsync: fn.is_async,
      });
    }
    for (const cls of gNode.classes || []) {
      const methods = (cls.methods || [])
        .filter((m) => isRelevantFunction(m.name))
        .map((m) => ({
          id: m.id, name: m.name, params: m.params || [],
          return_type: m.return_type || "unknown",
          is_exported: m.is_exported || false, is_async: m.is_async || false,
          description: m.description || "",
        }));
      // Class container — height includes space for all methods
      const clsH = classHeight(methods);
      items.push({
        kind: "class", id: cls.id, name: cls.name,
        height: clsH, width: CLASS_W,
        clsMethods: methods,
      });
    }

    // ── Calculate natural width ──
    // Content width: flexible grid
    const itemCount = items.length;
    const maxItemW = itemCount > 0 ? Math.max(...items.map((i) => i.width)) : FN_W;
    const idealCols = Math.min(itemCount || 1, 3);
    const contentW = Math.min(
      idealCols * maxItemW + (idealCols - 1) * ITEM_GAP,
      MAX_CONTENT_W
    );

    // Port sidebars
    const maxInputW = inputPorts.length > 0
      ? Math.max(...inputPorts.map((p) => estimateTextW(p.name, 9) + estimateTextW(p.data_type, 7) + 24))
      : 0;
    const maxOutputW = outputPorts.length > 0
      ? Math.max(...outputPorts.map((p) => estimateTextW(p.name, 9) + estimateTextW(p.data_type, 7) + 24))
      : 0;
    const leftBarW = inputPorts.length > 0 ? Math.max(maxInputW, PORT_SIDEBAR_MIN_W) : 0;
    const rightBarW = outputPorts.length > 0 ? Math.max(maxOutputW, PORT_SIDEBAR_MIN_W) : 0;

    // Total card width = sidebar_left + content + sidebar_right + padding
    const cardW = Math.max(
      MIN_CONTENT_W,
      leftBarW + contentW + rightBarW + FILE_PADDING * 2 + (leftBarW ? 8 : 0) + (rightBarW ? 8 : 0)
    );
    const naturalW = Math.min(cardW, MAX_CONTENT_W + leftBarW + rightBarW + FILE_PADDING * 2);

    // ── Calculate natural height ──
    // Content height: grid rows
    const gridCols = itemCount > 0
      ? Math.min(itemCount, Math.min(3, Math.max(1, Math.floor((naturalW - leftBarW - rightBarW - FILE_PADDING * 2) / (maxItemW + ITEM_GAP)))))
      : 1;
    const gridRows = itemCount > 0 ? Math.ceil(itemCount / gridCols) : 0;
    const rowHeights: number[] = [];
    for (let r = 0; r < gridRows; r++) {
      let mh = 0;
      for (let c = 0; c < gridCols; c++) {
        const idx = r * gridCols + c;
        if (idx < itemCount) mh = Math.max(mh, items[idx].height);
      }
      rowHeights.push(mh || 60);
    }
    const contentH = itemCount > 0
      ? rowHeights.reduce((a, b) => a + b, 0) + (gridRows - 1) * ITEM_GAP
      : 60;

    // Port sidebars height
    const portAreaH = Math.max(
      inputPorts.length * PORT_ROW_H,
      outputPorts.length * PORT_ROW_H,
      0
    );
    const bodyH = Math.max(contentH, portAreaH) + FILE_PADDING * 2;
    const naturalH = FILE_HEADER_H + bodyH + FILE_FOOTER_H;

    cards.push({
      nodeId: gNode.id,
      gNode,
      items,
      naturalW,
      naturalH,
      placedW: naturalW,
      placedH: naturalH,
      placedX: 0,
      placedY: 0,
      gridCols,
      gridRows,
    });
  }

  // Sort cards by topological order
  cards.sort((a, b) => (order.get(a.nodeId) ?? 999) - (order.get(b.nodeId) ?? 999));

  // ── Use Hierarchical Layout ────────────────────────
  // 使用层次化布局算法计算节点位置
  const hierarchicalPositions = hierarchicalLayout(
    graphNodes,
    graphEdges,
    entryPoints,
    'horizontal' // 水平布局：从左到右
  );

  // 应用层次化布局的位置到 cards
  for (const card of cards) {
    const pos = hierarchicalPositions.get(card.nodeId);
    if (pos) {
      card.placedX = pos.x;
      card.placedY = pos.y;
      card.placedW = card.naturalW;
      card.placedH = card.naturalH;
    } else {
      // 如果没有计算出位置，使用默认位置
      card.placedX = CANVAS_PADDING;
      card.placedY = CANVAS_PADDING;
      card.placedW = card.naturalW;
      card.placedH = card.naturalH;
    }
  }

  // ── Create ReactFlow nodes ────────────────
  const fileNodes: LayoutNode[] = [];
  const fnNodes: LayoutNode[] = [];
  const fnPosMap = new Map<string, { x: number; y: number; parentId: string }>();

  // ── Create ReactFlow nodes ────────────────
  for (const card of cards) {
    const gNode = card.gNode;
    const { placedW, placedH, placedX, placedY, items, gridCols, gridRows } = card;
    const ports = gNode.ports || [];
    const inputPorts = ports.filter((p) => p.direction === "input");
    const outputPorts = ports.filter((p) => p.direction === "output");
    const itemCount = items.length;
    const relevantFns = (gNode.functions || []).filter((f) => isRelevantFunction(f.name));
    const fnCount = relevantFns.length;
    const classCount = gNode.classes?.length || 0;

    // Calculate sidebar widths for this card
    const maxInputW = inputPorts.length > 0
      ? Math.max(...inputPorts.map((p) => estimateTextW(p.name, 9) + estimateTextW(p.data_type, 7) + 24))
      : 0;
    const maxOutputW = outputPorts.length > 0
      ? Math.max(...outputPorts.map((p) => estimateTextW(p.name, 9) + estimateTextW(p.data_type, 7) + 24))
      : 0;
    const leftBarW = inputPorts.length > 0 ? Math.max(maxInputW, PORT_SIDEBAR_MIN_W) : 0;
    const rightBarW = outputPorts.length > 0 ? Math.max(maxOutputW, PORT_SIDEBAR_MIN_W) : 0;

    // Content area
    const contentAreaW = placedW - (leftBarW > 0 ? leftBarW + 8 : 0) - (rightBarW > 0 ? rightBarW + 8 : 0) - FILE_PADDING;
    const bodyH = placedH - FILE_HEADER_H - FILE_FOOTER_H;

    // Grid layout
    const itemColWidths: number[] = Array.from({ length: gridCols }, () => FN_W);
    const itemRowHeights: number[] = [];
    for (let r = 0; r < gridRows; r++) {
      let mh = 0;
      for (let c = 0; c < gridCols; c++) {
        const idx = r * gridCols + c;
        if (idx < itemCount) {
          mh = Math.max(mh, items[idx].height);
          itemColWidths[c] = Math.max(itemColWidths[c], items[idx].width);
        }
      }
      itemRowHeights.push(mh || 60);
    }
    const totalGridW = itemCount > 0
      ? itemColWidths.slice(0, gridCols).reduce((a, b) => a + b, 0) + (gridCols > 1 ? (gridCols - 1) * ITEM_GAP : 0)
      : FN_W;
    const totalGridH = itemRowHeights.reduce((a, b) => a + b, 0) + (gridRows > 1 ? (gridRows - 1) * ITEM_GAP : 0);

    const gridOffsetX = (leftBarW > 0 ? leftBarW + 8 : 0) + FILE_PADDING + Math.max(0, (contentAreaW - totalGridW) / 2);
    const gridOffsetY = FILE_HEADER_H + Math.max(0, (bodyH - totalGridH) / 2);

    const role = gNode.architecture_role || "";

    fileNodes.push({
      id: gNode.id,
      type: "fileGroup",
      position: { x: placedX, y: placedY },
      data: {
        file_name: gNode.file_name,
        folder_path: gNode.folder_path,
        language: gNode.language,
        summary: gNode.summary,
        architecture_role: role,
        ports,
        functions: relevantFns.map((f) => ({
          id: f.id, name: f.name, is_exported: f.is_exported, is_async: f.is_async,
          params: f.params, return_type: f.return_type,
        })),
        classes: gNode.classes || [],
        isSelected: false, isDimmed: false,
        isEntry: false, isExit: exitSet.has(gNode.id),
        isPathHighlighted: false,
        width: placedW, height: placedH,
        leftSidebarW: leftBarW, rightSidebarW: rightBarW,
        contentH: bodyH,
        functionCount: fnCount + classCount,
        exportedCount: relevantFns.filter((f) => f.is_exported).length
          + (gNode.classes || []).filter((c) => c.is_exported).length,
      },
      draggable: true, selectable: true,
      style: { width: placedW, height: placedH },
    });

    // ── Function/class sub-nodes ────────────
    if (itemCount > 0) {
      for (let j = 0; j < itemCount; j++) {
        const item = items[j];
        const r = Math.floor(j / gridCols);
        const c = j % gridCols;

        let colX = 0;
        for (let cc = 0; cc < c; cc++) colX += itemColWidths[cc] + ITEM_GAP;
        const rowFnCount = r === gridRows - 1 ? itemCount - r * gridCols : gridCols;
        if (rowFnCount < gridCols) {
          const partialW = itemColWidths.slice(0, rowFnCount).reduce((a, b) => a + b, 0) + (rowFnCount > 1 ? (rowFnCount - 1) * ITEM_GAP : 0);
          colX += Math.max(0, (totalGridW - partialW) / 2);
        }

        const itemX = gridOffsetX + colX;
        const rowYOff = itemRowHeights.slice(0, r).reduce((a, b) => a + b + ITEM_GAP, 0);
        const itemY = gridOffsetY + rowYOff + (itemRowHeights[r] - item.height) / 2;

        if (item.kind === "function") {
          fnNodes.push({
            id: item.id, type: "functionSub",
            position: { x: itemX, y: itemY },
            parentId: gNode.id, extent: "parent" as const,
            data: {
              name: item.name, params: item.fnParams || [],
              return_type: item.fnReturnType || "unknown",
              is_exported: item.fnIsExported || false,
              is_async: item.fnIsAsync || false,
              description: "",
              isDimmed: false, isSelected: false,
              isPathHighlighted: false, parentDimmed: false,
            },
            selectable: true, draggable: true,
            style: { width: item.width, height: item.height },
          });
          fnPosMap.set(item.id, {
            x: itemX + item.width / 2, y: itemY + item.height / 2, parentId: gNode.id,
          });
        } else if (item.kind === "class") {
          fnNodes.push({
            id: item.id, type: "classGroup",
            position: { x: itemX, y: itemY },
            parentId: gNode.id, extent: "parent" as const,
            data: {
              name: item.name, is_exported: item.clsMethods ? true : false,
              methods: item.clsMethods || [],
              isDimmed: false, parentDimmed: false,
              width: item.width, height: item.height,
            },
            selectable: true, draggable: true,
            style: { width: item.width, height: item.height },
          });
          // Create method sub-nodes inside the class, parented to class node
          const clsMethods = item.clsMethods || [];
          const METHOD_HEADER = 32; // class header height
          const METHOD_GAP = 8;
          let methodY = itemY + METHOD_HEADER;
          for (const m of clsMethods) {
            const mW = item.width - 16; // padding inside class
            const mH = Math.max(52, 28 + (m.params?.length || 0) * 20 + 18);
            fnNodes.push({
              id: m.id, type: "functionSub",
              position: { x: 8, y: methodY - itemY },
              parentId: item.id, extent: "parent" as const,
              data: {
                name: m.name, params: m.params || [],
                return_type: m.return_type || "unknown",
                is_exported: m.is_exported || false,
                is_async: m.is_async || false,
                description: "",
                isDimmed: false, isSelected: false,
                isPathHighlighted: false, parentDimmed: false,
              },
              selectable: true, draggable: true,
              style: { width: mW, height: mH },
            });
            fnPosMap.set(m.id, {
              x: 8 + mW / 2, y: (methodY - itemY) + mH / 2,
              parentId: item.id,
            });
            methodY += mH + METHOD_GAP;
          }
        }
      }
    }
  }

  // ── Helper: resolve absolute position through nested parent chain ──
  function getAbsolutePosition(
    node: { position: { x: number; y: number }; parentId?: string },
    all: { position: { x: number; y: number }; parentId?: string; id: string }[],
  ): { x: number; y: number } {
    let x = node.position.x;
    let y = node.position.y;
    let current = node as { position: { x: number; y: number }; parentId?: string; id: string } | undefined;
    while (current?.parentId) {
      const parent = all.find((n) => n.id === current!.parentId);
      if (!parent) break;
      x += parent.position.x;
      y += parent.position.y;
      current = parent;
    }
    return { x, y };
  }

  // ── Build edges ───────────────────────────
  const layoutEdges: LayoutEdge[] = [];
  const edgePairCount = new Map<string, number>();
  const edgePairIdx = new Map<string, number>();

  // Combined node list for position lookups
  const allNodes = [...fileNodes, ...fnNodes];

  // Map functionId → Set<paramName> for per-parameter edge routing
  const fnParamsMap = new Map<string, Set<string>>();
  for (const fn of fnNodes) {
    const params = (fn.data as Record<string, unknown>).params as { name: string }[] | undefined;
    if (params && params.length > 0) {
      fnParamsMap.set(fn.id, new Set(params.map((p) => p.name)));
    }
  }

  for (const e of graphEdges) {
    let srcId: string, tgtId: string;
    const isCrossFile = e.source_node_id !== e.target_node_id;

    if (isCrossFile) {
      if (e.edge_type === "call" && e.source_function_id && e.target_function_id) {
        srcId = e.source_function_id; tgtId = e.target_function_id;
      } else {
        srcId = e.source_node_id; tgtId = e.target_node_id;
      }
    } else if (e.edge_type === "port_to_function") {
      srcId = e.source_node_id; tgtId = e.target_function_id;
    } else if (e.edge_type === "function_to_port") {
      srcId = e.source_function_id; tgtId = e.target_node_id;
    } else {
      srcId = e.source_function_id || e.source_node_id;
      tgtId = e.target_function_id || e.target_node_id;
    }
    const key = `${srcId}->${tgtId}`;
    edgePairCount.set(key, (edgePairCount.get(key) || 0) + 1);
  }

  const existingIds = new Set([
    ...fileNodes.map((n) => n.id),
    ...fnNodes.map((n) => n.id),
  ]);

  for (const e of graphEdges) {
    let sourceId: string, targetId: string;
    let sourceHandle: string, targetHandle: string;

    const isCrossFile = e.source_node_id !== e.target_node_id;

    if (isCrossFile) {
      // ── Cross-file edges ──
      if (e.edge_type === "call" && e.source_function_id && e.target_function_id) {
        // Cross-file CALL: connect function→function if both exist as sub-nodes
        const srcFnExists = existingIds.has(e.source_function_id);
        const tgtFnExists = existingIds.has(e.target_function_id);
        sourceId = srcFnExists ? e.source_function_id : e.source_node_id;
        targetId = tgtFnExists ? e.target_function_id : e.target_node_id;
        sourceHandle = "out";
        targetHandle = tgtFnExists
          ? resolveTargetHandle(e.target_function_id, e.variable_name, fnParamsMap)
          : (e.target_port_id || "in");
      } else {
        // Cross-file IMPORT: connect file node ports
        sourceId = e.source_node_id;
        targetId = e.target_node_id;
        sourceHandle = e.source_port_id || "out";
        targetHandle = e.target_port_id || "in";
      }
    } else {
      // ── Intra-file edges: connect ports ↔ functions within same file ──
      if (e.edge_type === "port_to_function") {
        sourceId = e.source_node_id; targetId = e.target_function_id;
        sourceHandle = e.source_port_id;
        targetHandle = resolveTargetHandle(targetId, e.variable_name, fnParamsMap);
      } else if (e.edge_type === "function_to_port") {
        sourceId = e.source_function_id; targetId = e.target_node_id;
        sourceHandle = "out"; targetHandle = e.target_port_id;
      } else {
        // Intra-file function→function (sequential flow)
        sourceId = e.source_function_id || e.source_node_id;
        targetId = e.target_function_id || e.target_node_id;
        sourceHandle = "out";
        targetHandle = resolveTargetHandle(targetId, e.variable_name, fnParamsMap);
      }
    }

    if (existingIds.has(sourceId) && existingIds.has(targetId)) {
      const pairKey = `${sourceId}->${targetId}`;
      const idx = edgePairIdx.get(pairKey) || 0;
      const total = edgePairCount.get(pairKey) || 1;
      edgePairIdx.set(pairKey, idx + 1);

      // Smart direction: find source/target node positions and pick best side
      const srcNode = allNodes.find((n) => n.id === sourceId);
      const tgtNode = allNodes.find((n) => n.id === targetId);
      let sourceSide = Position.Right;
      let targetSide = Position.Left;
      let edgeOffsetX = 0;
      let edgeOffsetY = 0;

      if (e.edge_type === "port_to_function") {
        sourceSide = Position.Right; // 文件节点的输出端口在右侧
        targetSide = Position.Left;  // 函数节点的输入在左侧
      } else if (e.edge_type === "function_to_port") {
        sourceSide = Position.Right; // 函数节点的输出在右侧
        targetSide = Position.Right; // 文件节点的输入端口在右侧（同侧回流）
      } else if (srcNode && tgtNode) {
        const srcW = (srcNode.style?.width as number) || 240;
        const srcH = (srcNode.style?.height as number) || 60;
        const tgtW = (tgtNode.style?.width as number) || 240;
        const tgtH = (tgtNode.style?.height as number) || 60;
        // Recursively resolve absolute positions through nested parent chain
        const { x: srcX, y: srcY } = getAbsolutePosition(srcNode, allNodes);
        const { x: tgtX, y: tgtY } = getAbsolutePosition(tgtNode, allNodes);

        const best = getBestConnectionSide(srcX, srcY, srcW, srcH, tgtX, tgtY, tgtW, tgtH);
        sourceSide = best.sourceSide;
        targetSide = best.targetSide;
      }

      // 2D offset: spread parallel edges perpendicular to connection direction
      if (total > 1) {
        const spread = (idx - (total - 1) / 2) * 14;
        if (sourceSide === targetSide && (sourceSide === Position.Right || sourceSide === Position.Left)) {
          edgeOffsetX = spread;
        } else if (sourceSide === targetSide) {
          edgeOffsetY = spread;
        } else if (sourceSide === Position.Right || sourceSide === Position.Left) {
          // Horizontal connection → offset vertically
          edgeOffsetY = spread;
        } else {
          // Vertical connection → offset horizontally
          edgeOffsetX = spread;
        }
      }

      // Override handles for vertical connections
      if (
        e.edge_type !== "port_to_function" &&
        e.edge_type !== "function_to_port" &&
        (sourceSide === Position.Bottom || sourceSide === Position.Top)
      ) {
        sourceHandle = sourceSide === Position.Bottom ? "bottom" : "top";
        targetHandle = targetSide === Position.Top ? "top" : "bottom";
      }

      const lbl = e.label || `${e.variable_name}: ${e.data_type}` || e.variable_name;

      layoutEdges.push({
        id: e.id, source: sourceId, target: targetId,
        sourceHandle, targetHandle,
        type: "dataFlow",
        data: {
          variable_name: e.variable_name, data_type: e.data_type,
          label: lbl, edge_type: e.edge_type,
          animating: true, isDimmed: false, isPathHighlighted: false,
          sourceSide, targetSide,
          edgeOffsetX, edgeOffsetY,
        },
      });
    }
  }

  // Play order = file node IDs in topological order
  const playOrder = cards.map((c) => c.nodeId);

  return { fileNodes, fnNodes, edges: layoutEdges, playOrder };
}
