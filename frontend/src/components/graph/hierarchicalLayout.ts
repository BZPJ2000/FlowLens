/**
 * 层次化布局算法（Sugiyama-style Layered Layout）
 *
 * 目标：
 * 1. 将节点分配到不同的层（layer），使数据流从左到右或从上到下
 * 2. 减少边的交叉
 * 3. 优化节点间距，使连接更清晰
 * 4. 考虑节点大小，避免重叠
 */

import type { GraphNode as GNode, GraphEdge as GEdge } from "../../types";

interface LayeredNode {
  id: string;
  gNode: GNode;
  layer: number;        // 所在层
  posInLayer: number;   // 层内位置
  width: number;
  height: number;
  x: number;
  y: number;
}

interface AdjacencyList {
  outgoing: Map<string, Set<string>>;  // node -> [targets]
  incoming: Map<string, Set<string>>;  // node -> [sources]
}

/**
 * Step 1: 构建邻接表
 */
function buildAdjacencyList(nodes: GNode[], edges: GEdge[]): AdjacencyList {
  const outgoing = new Map<string, Set<string>>();
  const incoming = new Map<string, Set<string>>();

  for (const n of nodes) {
    outgoing.set(n.id, new Set());
    incoming.set(n.id, new Set());
  }

  for (const e of edges) {
    if (e.source_node_id !== e.target_node_id) {
      outgoing.get(e.source_node_id)?.add(e.target_node_id);
      incoming.get(e.target_node_id)?.add(e.source_node_id);
    }
  }

  return { outgoing, incoming };
}

/**
 * Step 2: 层分配（Layer Assignment）
 * 使用最长路径算法，确保所有边都从左到右
 */
function assignLayers(
  nodes: GNode[],
  adj: AdjacencyList,
  entryPoints: string[]
): Map<string, number> {
  const layers = new Map<string, number>();
  const visited = new Set<string>();
  const { incoming, outgoing } = adj;

  // 找到所有入度为 0 的节点作为起点
  const roots: string[] = [];
  for (const n of nodes) {
    if (incoming.get(n.id)?.size === 0) {
      roots.push(n.id);
    }
  }

  // 如果有指定的入口点，优先使用
  const startNodes = entryPoints.length > 0 ? entryPoints : roots;
  if (startNodes.length === 0) {
    // 如果没有入口点，选择第一个节点
    startNodes.push(nodes[0].id);
  }

  // BFS 分层
  const queue: Array<{ id: string; layer: number }> = [];
  for (const id of startNodes) {
    queue.push({ id, layer: 0 });
    layers.set(id, 0);
  }

  while (queue.length > 0) {
    const { id, layer } = queue.shift()!;
    if (visited.has(id)) continue;
    visited.add(id);

    const targets = outgoing.get(id) || new Set();
    for (const targetId of targets) {
      const currentLayer = layers.get(targetId) ?? -1;
      const newLayer = layer + 1;

      if (newLayer > currentLayer) {
        layers.set(targetId, newLayer);
        queue.push({ id: targetId, layer: newLayer });
      }
    }
  }

  // 处理未访问的节点（孤立节点或循环依赖）
  let maxLayer = Math.max(...Array.from(layers.values()), 0);
  for (const n of nodes) {
    if (!layers.has(n.id)) {
      maxLayer++;
      layers.set(n.id, maxLayer);
    }
  }

  return layers;
}

/**
 * Step 3: 减少边交叉（Crossing Reduction）
 * 使用重心法（Barycenter Method）
 */
function reduceCrossings(
  layeredNodes: LayeredNode[][],
  adj: AdjacencyList,
  iterations: number = 4
): void {
  for (let iter = 0; iter < iterations; iter++) {
    // 从上到下
    for (let i = 1; i < layeredNodes.length; i++) {
      const layer = layeredNodes[i];
      const prevLayer = layeredNodes[i - 1];

      // 计算每个节点的重心位置
      const barycenters = layer.map((node) => {
        const sources = adj.incoming.get(node.id) || new Set();
        let sum = 0;
        let count = 0;

        for (const srcId of sources) {
          const srcNode = prevLayer.find((n) => n.id === srcId);
          if (srcNode) {
            sum += srcNode.posInLayer;
            count++;
          }
        }

        return count > 0 ? sum / count : node.posInLayer;
      });

      // 按重心排序
      const sorted = layer
        .map((node, idx) => ({ node, barycenter: barycenters[idx] }))
        .sort((a, b) => a.barycenter - b.barycenter);

      // 更新位置
      sorted.forEach((item, idx) => {
        item.node.posInLayer = idx;
      });
    }

    // 从下到上
    for (let i = layeredNodes.length - 2; i >= 0; i--) {
      const layer = layeredNodes[i];
      const nextLayer = layeredNodes[i + 1];

      const barycenters = layer.map((node) => {
        const targets = adj.outgoing.get(node.id) || new Set();
        let sum = 0;
        let count = 0;

        for (const tgtId of targets) {
          const tgtNode = nextLayer.find((n) => n.id === tgtId);
          if (tgtNode) {
            sum += tgtNode.posInLayer;
            count++;
          }
        }

        return count > 0 ? sum / count : node.posInLayer;
      });

      const sorted = layer
        .map((node, idx) => ({ node, barycenter: barycenters[idx] }))
        .sort((a, b) => a.barycenter - b.barycenter);

      sorted.forEach((item, idx) => {
        item.node.posInLayer = idx;
      });
    }
  }
}

/**
 * Step 4: 坐标分配（Coordinate Assignment）
 * 考虑节点大小，避免重叠
 */
function assignCoordinates(
  layeredNodes: LayeredNode[][],
  direction: 'horizontal' | 'vertical' = 'horizontal'
): void {
  const LAYER_GAP = 500;  // 大幅增加层间距离，为连线留出空间
  const NODE_GAP = 120;   // 增加节点间距离
  const PADDING = 100;    // 画布边距

  if (direction === 'horizontal') {
    // 水平布局：从左到右
    let currentX = PADDING;

    for (let i = 0; i < layeredNodes.length; i++) {
      const layer = layeredNodes[i];

      // 计算这一层的最大宽度
      const maxWidth = Math.max(...layer.map((n) => n.width), 200);

      // 计算这一层的总高度
      const totalHeight = layer.reduce((sum, n) => sum + n.height, 0) + (layer.length - 1) * NODE_GAP;

      // 从中心开始垂直排列
      let currentY = PADDING + Math.max(0, (1000 - totalHeight) / 2);

      for (const node of layer) {
        node.x = currentX;
        node.y = currentY;
        currentY += node.height + NODE_GAP;
      }

      currentX += maxWidth + LAYER_GAP;
    }
  } else {
    // 垂直布局：从上到下
    let currentY = PADDING;

    for (let i = 0; i < layeredNodes.length; i++) {
      const layer = layeredNodes[i];

      // 计算这一层的最大高度
      const maxHeight = Math.max(...layer.map((n) => n.height), 150);

      // 计算这一层的总宽度
      const totalWidth = layer.reduce((sum, n) => sum + n.width, 0) + (layer.length - 1) * NODE_GAP;

      // 从中心开始水平排列
      let currentX = PADDING + Math.max(0, (1600 - totalWidth) / 2);

      for (const node of layer) {
        node.x = currentX;
        node.y = currentY;
        currentX += node.width + NODE_GAP;
      }

      currentY += maxHeight + LAYER_GAP;
    }
  }
}

/**
 * 主函数：层次化布局
 */
export function hierarchicalLayout(
  nodes: GNode[],
  edges: GEdge[],
  entryPoints: string[],
  direction: 'horizontal' | 'vertical' = 'horizontal'
): Map<string, { x: number; y: number }> {
  if (nodes.length === 0) {
    return new Map();
  }

  // Step 1: 构建邻接表
  const adj = buildAdjacencyList(nodes, edges);

  // Step 2: 层分配
  const layerMap = assignLayers(nodes, adj, entryPoints);

  // 按层分组
  const maxLayer = Math.max(...Array.from(layerMap.values()));
  const layeredNodes: LayeredNode[][] = Array.from({ length: maxLayer + 1 }, () => []);

  for (const gNode of nodes) {
    const layer = layerMap.get(gNode.id) ?? 0;

    // 估算节点大小
    const fnCount = (gNode.functions || []).length;
    const clsCount = (gNode.classes || []).length;
    const itemCount = fnCount + clsCount;

    const width = Math.min(400, Math.max(280, 280 + itemCount * 20));
    const height = Math.max(150, 100 + itemCount * 40);

    layeredNodes[layer].push({
      id: gNode.id,
      gNode,
      layer,
      posInLayer: layeredNodes[layer].length,
      width,
      height,
      x: 0,
      y: 0,
    });
  }

  // Step 3: 减少边交叉
  reduceCrossings(layeredNodes, adj, 4);

  // Step 4: 坐标分配
  assignCoordinates(layeredNodes, direction);

  // 返回位置映射
  const positions = new Map<string, { x: number; y: number }>();
  for (const layer of layeredNodes) {
    for (const node of layer) {
      positions.set(node.id, { x: node.x, y: node.y });
    }
  }

  return positions;
}
