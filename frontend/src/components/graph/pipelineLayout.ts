import type { Node, Edge } from "@xyflow/react";
import type { GraphNode as GNode, GraphEdge as GEdge, GraphPort } from "../../types";

// ── Pipeline Node Types ────────────────────────
export interface PipelineDataNode {
  id: string;
  name: string;
  data_type: string;
  isEntry: boolean;
  isExit: boolean;
}

export interface PipelineTransformNode {
  id: string;
  name: string;
  file_name: string;
  architecture_role: string;
  is_exported: boolean;
  is_async: boolean;
}

interface PipelineEdge {
  sourceId: string;
  targetId: string;
  variable_name: string;
  data_type: string;
}

// ── Layout Constants ───────────────────────────
const LAYER_GAP = 56;        // vertical gap between layers
const NODE_GAP_H = 32;       // horizontal gap between nodes in same layer
const DATA_NODE_EST_W = 180; // estimated data node width
const TRANSFORM_NODE_EST_W = 200; // estimated transform node width
const DATA_NODE_H = 34;
const TRANSFORM_NODE_H = 56;
const CANVAS_PADDING = 80;

// ── Main Pipeline Layout ───────────────────────

export function computePipelineLayout(
  graphNodes: GNode[],
  graphEdges: GEdge[],
  entryPoints: string[],
  exitPoints: string[],
): { nodes: Node[]; edges: Edge[] } {
  if (!graphNodes || graphNodes.length === 0) {
    return { nodes: [], edges: [] };
  }

  const entrySet = new Set(entryPoints);
  const exitSet = new Set(exitPoints);
  const nodeMap = new Map(graphNodes.map((n) => [n.id, n]));

  // ── Collect all data nodes (ports) and transform nodes (functions) ──
  const dataNodes = new Map<string, PipelineDataNode>();
  const transformNodes = new Map<string, PipelineTransformNode>();

  for (const gNode of graphNodes) {
    // Ports → data nodes
    for (const port of gNode.ports || []) {
      // Use deterministic ID based on name + direction
      const dataId = `data-${port.direction}-${port.name}`;
      if (!dataNodes.has(dataId)) {
        dataNodes.set(dataId, {
          id: dataId,
          name: port.name,
          data_type: port.data_type,
          isEntry: entrySet.has(gNode.id) && port.direction === "input",
          isExit: exitSet.has(gNode.id) && port.direction === "output",
        });
      }
      // Update entry/exit status
      const existing = dataNodes.get(dataId)!;
      if (entrySet.has(gNode.id) && port.direction === "input") existing.isEntry = true;
      if (exitSet.has(gNode.id) && port.direction === "output") existing.isExit = true;
    }

    // Functions → transform nodes
    for (const fn of gNode.functions || []) {
      transformNodes.set(fn.id, {
        id: fn.id,
        name: fn.name,
        file_name: gNode.file_name,
        architecture_role: gNode.architecture_role,
        is_exported: fn.is_exported,
        is_async: fn.is_async,
      });
    }
  }

  // ── Build adjacency: data ↔ transform ──
  // dataProducedBy[dataId] = set of transform IDs that produce this data
  // dataConsumedBy[dataId] = set of transform IDs that consume this data
  const dataProducedBy = new Map<string, Set<string>>();
  const dataConsumedBy = new Map<string, Set<string>>();
  const pipelineEdges: PipelineEdge[] = [];

  for (const e of graphEdges) {
    if (e.edge_type === "port_to_function") {
      // Port (data) → Function (transform)
      const port = findPort(graphNodes, e.source_node_id, e.source_port_id);
      if (port) {
        const dataId = `data-${port.direction}-${port.name}`;
        if (transformNodes.has(e.target_function_id)) {
          if (!dataConsumedBy.has(dataId)) dataConsumedBy.set(dataId, new Set());
          dataConsumedBy.get(dataId)!.add(e.target_function_id);
          pipelineEdges.push({
            sourceId: dataId,
            targetId: e.target_function_id,
            variable_name: e.variable_name,
            data_type: e.data_type,
          });
        }
      }
    } else if (e.edge_type === "function_to_port") {
      // Function (transform) → Port (data)
      const port = findPort(graphNodes, e.target_node_id, e.target_port_id);
      if (port) {
        const dataId = `data-${port.direction}-${port.name}`;
        if (transformNodes.has(e.source_function_id)) {
          if (!dataProducedBy.has(dataId)) dataProducedBy.set(dataId, new Set());
          dataProducedBy.get(dataId)!.add(e.source_function_id);
          pipelineEdges.push({
            sourceId: e.source_function_id,
            targetId: dataId,
            variable_name: e.variable_name,
            data_type: e.data_type,
          });
        }
      }
    } else if (e.edge_type === "import" || e.edge_type === "call") {
      // Cross-file: source output port → target input port
      const srcPort = findPort(graphNodes, e.source_node_id, e.source_port_id);
      const tgtPort = findPort(graphNodes, e.target_node_id, e.target_port_id);
      if (srcPort && tgtPort && srcPort.name === tgtPort.name) {
        // Same variable flowing between files — connect the transforms
        const srcDataId = `data-${srcPort.direction}-${srcPort.name}`;
        const tgtDataId = `data-${tgtPort.direction}-${tgtPort.name}`;
        // Try to merge: if source data is produced by a transform,
        // and target data is consumed by a transform, connect them
        const producers = dataProducedBy.get(srcDataId);
        const consumers = dataConsumedBy.get(tgtDataId);
        if (producers && consumers) {
          for (const srcT of producers) {
            for (const tgtT of consumers) {
              if (srcT !== tgtT) {
                pipelineEdges.push({
                  sourceId: srcT,
                  targetId: tgtT,
                  variable_name: e.variable_name,
                  data_type: e.data_type,
                });
              }
            }
          }
        }
        // Also connect the data nodes themselves (same variable flowing)
        if (srcDataId !== tgtDataId) {
          pipelineEdges.push({
            sourceId: srcDataId,
            targetId: tgtDataId,
            variable_name: e.variable_name,
            data_type: e.data_type,
          });
        }
      }
    } else if (e.edge_type === "export") {
      // Sequential flow within file: function → function
      // Already handled by port_to_function and function_to_port
    }
  }

  // Also add sequential function edges (within same file)
  for (const e of graphEdges) {
    if ((e.edge_type === "call" || e.edge_type === "export") &&
        e.source_node_id === e.target_node_id &&
        e.source_function_id && e.target_function_id &&
        transformNodes.has(e.source_function_id) &&
        transformNodes.has(e.target_function_id)) {
      pipelineEdges.push({
        sourceId: e.source_function_id,
        targetId: e.target_function_id,
        variable_name: e.variable_name,
        data_type: e.data_type,
      });
    }
  }

  // ── Topological sort to assign layers ──
  const allNodeIds = new Set([
    ...Array.from(dataNodes.keys()),
    ...Array.from(transformNodes.keys()),
  ]);

  // Build adjacency for all nodes
  const adj = new Map<string, string[]>();
  const inDeg = new Map<string, number>();
  for (const id of allNodeIds) { adj.set(id, []); inDeg.set(id, 0); }
  for (const pe of pipelineEdges) {
    if (allNodeIds.has(pe.sourceId) && allNodeIds.has(pe.targetId)) {
      adj.get(pe.sourceId)?.push(pe.targetId);
      inDeg.set(pe.targetId, (inDeg.get(pe.targetId) || 0) + 1);
    }
  }

  // Start BFS from nodes with in-degree 0
  const queue: string[] = [];
  for (const [id, deg] of inDeg) {
    if (deg === 0) queue.push(id);
  }
  // If no clear entry points, start with entry data nodes
  if (queue.length === 0) {
    for (const [id, dn] of dataNodes) {
      if (dn.isEntry) queue.push(id);
    }
  }
  // Fallback: all data nodes
  if (queue.length === 0) {
    for (const id of dataNodes.keys()) queue.push(id);
  }

  const layers: string[][] = [];
  const visited = new Set<string>();

  while (queue.length > 0) {
    const layer: string[] = [];
    const layerSize = queue.length;
    for (let i = 0; i < layerSize; i++) {
      const nodeId = queue.shift()!;
      if (visited.has(nodeId)) continue;
      visited.add(nodeId);
      layer.push(nodeId);
      for (const neighbor of adj.get(nodeId) || []) {
        const newDeg = (inDeg.get(neighbor) || 1) - 1;
        inDeg.set(neighbor, newDeg);
        if (newDeg === 0 && !visited.has(neighbor)) {
          queue.push(neighbor);
        }
      }
    }
    if (layer.length > 0) layers.push(layer);
  }

  // Add unvisited nodes
  const remaining: string[] = [];
  for (const id of allNodeIds) {
    if (!visited.has(id)) remaining.push(id);
  }
  if (remaining.length > 0) layers.push(remaining);

  // ── Position nodes within layers ──
  const reactFlowNodes: Node[] = [];
  let currentY = CANVAS_PADDING;

  for (const layer of layers) {
    // Separate data and transform nodes
    const dataInLayer = layer.filter((id) => dataNodes.has(id));
    const transformInLayer = layer.filter((id) => transformNodes.has(id));

    const totalCount = dataInLayer.length + transformInLayer.length;
    if (totalCount === 0) continue;

    // Calculate layer width
    const totalW = dataInLayer.length * DATA_NODE_EST_W +
      transformInLayer.length * TRANSFORM_NODE_EST_W +
      (totalCount - 1) * NODE_GAP_H;

    const startX = CANVAS_PADDING + Math.max(0, (1200 - totalW) / 2);
    let currentX = startX;

    // Place data nodes first, then transform nodes
    for (const dataId of dataInLayer) {
      const dn = dataNodes.get(dataId)!;
      reactFlowNodes.push({
        id: dataId,
        type: "dataVariable",
        position: { x: currentX, y: currentY },
        data: {
          name: dn.name,
          data_type: dn.data_type,
          isEntry: dn.isEntry,
          isExit: dn.isExit,
          isDimmed: false,
          isSelected: false,
          isPathHighlighted: false,
        },
        selectable: true,
        draggable: true,
        style: { width: DATA_NODE_EST_W, height: DATA_NODE_H },
      });
      currentX += DATA_NODE_EST_W + NODE_GAP_H;
    }

    for (const txId of transformInLayer) {
      const tn = transformNodes.get(txId)!;
      reactFlowNodes.push({
        id: txId,
        type: "transform",
        position: { x: currentX, y: currentY },
        data: {
          name: tn.name,
          file_name: tn.file_name,
          architecture_role: tn.architecture_role,
          is_exported: tn.is_exported,
          is_async: tn.is_async,
          isDimmed: false,
          isSelected: false,
          isPathHighlighted: false,
        },
        selectable: true,
        draggable: true,
        style: { width: TRANSFORM_NODE_EST_W, height: TRANSFORM_NODE_H },
      });
      currentX += TRANSFORM_NODE_EST_W + NODE_GAP_H;
    }

    currentY += LAYER_GAP;
  }

  // ── Build edges ──
  const reactFlowEdges: Edge[] = [];
  const existingNodeIds = new Set(reactFlowNodes.map((n) => n.id));

  for (const pe of pipelineEdges) {
    if (existingNodeIds.has(pe.sourceId) && existingNodeIds.has(pe.targetId)) {
      reactFlowEdges.push({
        id: `${pe.sourceId}->${pe.targetId}`,
        source: pe.sourceId,
        target: pe.targetId,
        type: "dataFlow",
        data: {
          variable_name: pe.variable_name,
          data_type: pe.data_type,
          label: `${pe.variable_name}: ${pe.data_type}`,
          edge_type: "import",
          animating: true,
          isDimmed: false,
          isPathHighlighted: false,
        },
      });
    }
  }

  return { nodes: reactFlowNodes, edges: reactFlowEdges };
}

// ── Helper: find a port by node ID and port ID ──
function findPort(
  graphNodes: GNode[],
  nodeId: string,
  portId: string,
): GraphPort | undefined {
  const gNode = graphNodes.find((n) => n.id === nodeId);
  if (!gNode) return undefined;
  return (gNode.ports || []).find((p) => p.id === portId);
}
