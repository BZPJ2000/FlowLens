import type {
  ClassNode,
  DataFlowGraph,
  FunctionNode,
  GraphEdge,
  GraphNode,
  MethodNode,
  ProjectFile,
} from "../types";

export type SymbolKind = "function" | "method" | "class";
export type TraceEdgeKind = "call" | "arg" | "return" | "unknown";

export interface SymbolNode {
  id: string;
  name: string;
  qualifiedName: string;
  kind: SymbolKind;
  fileId: string;
  filePath: string;
  fileName: string;
  folderPath: string;
  language: string;
  role: string;
  params: { name: string; type: string }[];
  returnType: string;
  description: string;
  startLine: number | null;
  endLine: number | null;
  parentClassId?: string;
  parentClassName?: string;
}

export interface TraceEdge {
  id: string;
  sourceId: string;
  targetId: string;
  sourceFileId: string;
  targetFileId: string;
  kind: TraceEdgeKind;
  variableName: string;
  sourceSlot: string | null;
  targetSlot: string | null;
  dataType: string;
  label: string;
  lineNumber: number | null;
  isCrossFile: boolean;
}

export interface ProjectGraphModel {
  symbols: SymbolNode[];
  edges: TraceEdge[];
  files: GraphNode[];
  projectFiles: ProjectFile[];
  modules: string[];
  entrySymbols: string[];
  exitSymbols: string[];
  orphanEdgeCount: number;
}

export interface GraphStats {
  fileCount: number;
  symbolCount: number;
  classCount: number;
  functionCount: number;
  methodCount: number;
  edgeCount: number;
  callCount: number;
  argCount: number;
  returnCount: number;
  crossFileCount: number;
}

export interface SymbolNeighborhood {
  incoming: TraceEdge[];
  outgoing: TraceEdge[];
  relatedIds: Set<string>;
}

export function buildProjectGraphModel(graph: DataFlowGraph | null): ProjectGraphModel {
  if (!graph) {
    return {
      symbols: [],
      edges: [],
      files: [],
      projectFiles: [],
      modules: [],
      entrySymbols: [],
      exitSymbols: [],
      orphanEdgeCount: 0,
    };
  }

  const symbols: SymbolNode[] = [];
  const symbolIds = new Set<string>();

  for (const file of graph.nodes) {
    for (const fn of file.functions) {
      const symbol = functionToSymbol(file, fn);
      symbols.push(symbol);
      symbolIds.add(symbol.id);
    }

    for (const cls of file.classes) {
      const classSymbol = classToSymbol(file, cls);
      symbols.push(classSymbol);
      symbolIds.add(classSymbol.id);

      for (const method of cls.methods) {
        const methodSymbol = methodToSymbol(file, cls, method);
        symbols.push(methodSymbol);
        symbolIds.add(methodSymbol.id);
      }
    }
  }

  const traceEdges: TraceEdge[] = [];
  let orphanEdgeCount = 0;
  for (const edge of graph.edges) {
    if (!edge.source_function_id || !edge.target_function_id) {
      orphanEdgeCount += 1;
      continue;
    }
    if (!symbolIds.has(edge.source_function_id) || !symbolIds.has(edge.target_function_id)) {
      orphanEdgeCount += 1;
      continue;
    }
    traceEdges.push(toTraceEdge(edge));
  }

  const incoming = new Map<string, number>();
  const outgoing = new Map<string, number>();
  for (const edge of traceEdges) {
    outgoing.set(edge.sourceId, (outgoing.get(edge.sourceId) ?? 0) + 1);
    incoming.set(edge.targetId, (incoming.get(edge.targetId) ?? 0) + 1);
  }

  return {
    symbols,
    edges: traceEdges,
    files: graph.nodes,
    projectFiles: graph.project_files?.length
      ? graph.project_files
      : graph.nodes.map((node) => ({
          id: node.id,
          file_path: node.file_path,
          file_name: node.file_name,
          folder_path: node.folder_path,
          language: node.language,
          has_symbols: node.functions.length + node.classes.length > 0,
          symbol_count:
            node.functions.length +
            node.classes.length +
            node.classes.reduce((sum, item) => sum + item.methods.length, 0),
        })),
    modules: Array.from(
      new Set(graph.nodes.map((node) => node.folder_path || "(root)")),
    ).sort((a, b) => a.localeCompare(b)),
    entrySymbols: symbols
      .filter((symbol) => !incoming.has(symbol.id) && (outgoing.get(symbol.id) ?? 0) > 0)
      .map((symbol) => symbol.id),
    exitSymbols: symbols
      .filter((symbol) => !outgoing.has(symbol.id) && (incoming.get(symbol.id) ?? 0) > 0)
      .map((symbol) => symbol.id),
    orphanEdgeCount,
  };
}

export function getGraphStats(model: ProjectGraphModel): GraphStats {
  return {
    fileCount: model.files.length,
    symbolCount: model.symbols.length,
    classCount: model.symbols.filter((symbol) => symbol.kind === "class").length,
    functionCount: model.symbols.filter((symbol) => symbol.kind === "function").length,
    methodCount: model.symbols.filter((symbol) => symbol.kind === "method").length,
    edgeCount: model.edges.length,
    callCount: model.edges.filter((edge) => edge.kind === "call").length,
    argCount: model.edges.filter((edge) => edge.kind === "arg").length,
    returnCount: model.edges.filter((edge) => edge.kind === "return").length,
    crossFileCount: model.edges.filter((edge) => edge.isCrossFile).length,
  };
}

export function getSymbolNeighborhood(
  model: ProjectGraphModel,
  symbolId: string | null,
): SymbolNeighborhood {
  if (!symbolId) {
    return { incoming: [], outgoing: [], relatedIds: new Set() };
  }
  const incoming = model.edges.filter((edge) => edge.targetId === symbolId);
  const outgoing = model.edges.filter((edge) => edge.sourceId === symbolId);
  const relatedIds = new Set<string>([symbolId]);
  for (const edge of incoming) {
    relatedIds.add(edge.sourceId);
  }
  for (const edge of outgoing) {
    relatedIds.add(edge.targetId);
  }
  return { incoming, outgoing, relatedIds };
}

export function getReachableSubgraph(
  model: ProjectGraphModel,
  startId: string,
  maxDepth = 3,
): Set<string> {
  const reached = new Set<string>([startId]);
  let frontier = new Set<string>([startId]);
  for (let depth = 0; depth < maxDepth; depth += 1) {
    const next = new Set<string>();
    for (const edge of model.edges) {
      if (frontier.has(edge.sourceId) && !reached.has(edge.targetId)) {
        reached.add(edge.targetId);
        next.add(edge.targetId);
      }
    }
    frontier = next;
    if (frontier.size === 0) break;
  }
  return reached;
}

export function edgeKindFromLabel(edge: GraphEdge): TraceEdgeKind {
  if (edge.edge_type === "call" || edge.edge_type === "arg" || edge.edge_type === "return") {
    return edge.edge_type;
  }
  const label = `${edge.edge_type} ${edge.label}`.toLowerCase();
  if (label.includes("return")) return "return";
  if (label.includes("arg") || label.includes(" -> ")) return "arg";
  if (label.includes("call")) return "call";
  return "unknown";
}

function functionToSymbol(file: GraphNode, fn: FunctionNode): SymbolNode {
  return {
    id: fn.id,
    name: fn.name,
    qualifiedName: fn.qualified_name ?? fn.id,
    kind: "function",
    fileId: file.id,
    filePath: file.file_path,
    fileName: file.file_name,
    folderPath: file.folder_path || "(root)",
    language: file.language,
    role: file.architecture_role,
    params: fn.params,
    returnType: fn.return_type,
    description: fn.description,
    startLine: fn.start_line ?? null,
    endLine: fn.end_line ?? null,
  };
}

function classToSymbol(file: GraphNode, cls: ClassNode): SymbolNode {
  return {
    id: cls.id,
    name: cls.name,
    qualifiedName: cls.qualified_name ?? cls.id,
    kind: "class",
    fileId: file.id,
    filePath: file.file_path,
    fileName: file.file_name,
    folderPath: file.folder_path || "(root)",
    language: file.language,
    role: file.architecture_role,
    params: [],
    returnType: "class",
    description: `${cls.name} in ${file.file_name}`,
    startLine: cls.start_line ?? null,
    endLine: cls.end_line ?? null,
  };
}

function methodToSymbol(file: GraphNode, cls: ClassNode, method: MethodNode): SymbolNode {
  return {
    id: method.id,
    name: method.name,
    qualifiedName: method.qualified_name ?? method.id,
    kind: "method",
    fileId: file.id,
    filePath: file.file_path,
    fileName: file.file_name,
    folderPath: file.folder_path || "(root)",
    language: file.language,
    role: file.architecture_role,
    params: method.params,
    returnType: method.return_type,
    description: method.description,
    startLine: method.start_line ?? null,
    endLine: method.end_line ?? null,
    parentClassId: cls.id,
    parentClassName: cls.name,
  };
}

function toTraceEdge(edge: GraphEdge): TraceEdge {
  const kind = edgeKindFromLabel(edge);
  const sourceSlot = edge.source_slot ?? null;
  const targetSlot = edge.target_slot ?? null;
  const label = traceEdgeLabel(kind, edge.label, sourceSlot, targetSlot);
  return {
    id: edge.id,
    sourceId: edge.source_function_id,
    targetId: edge.target_function_id,
    sourceFileId: edge.source_node_id,
    targetFileId: edge.target_node_id,
    kind,
    variableName: edge.variable_name || label || kind,
    sourceSlot,
    targetSlot,
    dataType: edge.data_type || "Unknown",
    label,
    lineNumber: edge.line_number ?? null,
    isCrossFile: edge.source_node_id !== edge.target_node_id,
  };
}

function traceEdgeLabel(
  kind: TraceEdgeKind,
  rawLabel: string,
  sourceSlot: string | null,
  targetSlot: string | null,
): string {
  if (kind === "arg") {
    return `${sourceSlot || "arg"} -> ${targetSlot || "param"}`;
  }
  if (kind === "return") {
    return `${sourceSlot || "return"} -> ${targetSlot || "result"}`;
  }
  return rawLabel || kind;
}
