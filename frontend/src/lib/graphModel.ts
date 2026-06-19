import type {
  ClassNode,
  DataFlowGraph,
  FunctionNode,
  GraphEdge,
  GraphNode,
  MethodNode,
  ProjectFile,
} from "../types";

export type CodeNodeKind = "folder" | "file" | "class" | "function" | "method" | "variable";
export type CodeEdgeKind = "contains" | "call" | "arg" | "return" | "unresolved" | "reference";

export interface CodeGraphNode {
  id: string;
  kind: CodeNodeKind;
  label: string;
  subtitle: string;
  folderPath: string;
  fileId?: string;
  filePath?: string;
  fileName?: string;
  language?: string;
  role?: string;
  parentId?: string;
  qualifiedName?: string;
  startLine?: number | null;
  endLine?: number | null;
  params?: { name: string; type: string }[];
  returnType?: string;
  symbolCount?: number;
  edgeCount: number;
  source?: GraphNode | FunctionNode | ClassNode | MethodNode | ProjectFile;
}

export interface CodeGraphEdge {
  id: string;
  source: string;
  target: string;
  kind: CodeEdgeKind;
  label: string;
  dataType?: string;
  lineNumber?: number | null;
  original?: GraphEdge;
}

export interface CodeGraphModel {
  nodes: CodeGraphNode[];
  edges: CodeGraphEdge[];
  folders: CodeGraphNode[];
  files: CodeGraphNode[];
  symbols: CodeGraphNode[];
  variables: CodeGraphNode[];
  projectFiles: ProjectFile[];
  orphanEdgeCount: number;
}

export interface GraphStats {
  folderCount: number;
  fileCount: number;
  classCount: number;
  functionCount: number;
  methodCount: number;
  variableCount: number;
  edgeCount: number;
  callCount: number;
  argCount: number;
  returnCount: number;
}

export interface NodeNeighborhood {
  incoming: CodeGraphEdge[];
  outgoing: CodeGraphEdge[];
  relatedIds: Set<string>;
}

export function buildCodeGraphModel(graph: DataFlowGraph | null): CodeGraphModel {
  if (!graph) {
    return emptyModel();
  }

  const projectFiles = normalizeProjectFiles(graph);
  const nodes = new Map<string, CodeGraphNode>();
  const edges = new Map<string, CodeGraphEdge>();
  const fileNodeByBackendId = new Map<string, CodeGraphNode>();
  const symbolIds = new Set<string>();
  let orphanEdgeCount = 0;

  for (const file of projectFiles) {
    ensureFolderChain(file.folder_path, nodes, edges);
  }

  for (const backendFile of graph.nodes) {
    const fileNode = toFileNode(backendFile);
    nodes.set(fileNode.id, fileNode);
    fileNodeByBackendId.set(backendFile.id, fileNode);
    linkFolderToFile(fileNode, nodes, edges);

    for (const fn of backendFile.functions ?? []) {
      const symbolNode = toFunctionNode(backendFile, fn);
      nodes.set(symbolNode.id, symbolNode);
      symbolIds.add(symbolNode.id);
      addEdge(edges, {
        id: `contains:${backendFile.id}:${fn.id}`,
        source: fileNode.id,
        target: symbolNode.id,
        kind: "contains",
        label: "defines",
      });
    }

    for (const cls of backendFile.classes ?? []) {
      const classNode = toClassNode(backendFile, cls);
      nodes.set(classNode.id, classNode);
      symbolIds.add(classNode.id);
      addEdge(edges, {
        id: `contains:${backendFile.id}:${cls.id}`,
        source: fileNode.id,
        target: classNode.id,
        kind: "contains",
        label: "class",
      });

      for (const method of cls.methods ?? []) {
        const methodNode = toMethodNode(backendFile, cls, method);
        nodes.set(methodNode.id, methodNode);
        symbolIds.add(methodNode.id);
        addEdge(edges, {
          id: `contains:${cls.id}:${method.id}`,
          source: classNode.id,
          target: methodNode.id,
          kind: "contains",
          label: "method",
        });
      }
    }
  }

  for (const projectFile of projectFiles) {
    if (nodes.has(projectFile.id)) continue;
    const fileNode = toProjectFileNode(projectFile);
    nodes.set(fileNode.id, fileNode);
    linkFolderToFile(fileNode, nodes, edges);
  }

  for (const edge of graph.edges) {
    const sourceId = edge.source_function_id || edge.source_node_id;
    const targetId = edge.target_function_id || edge.target_node_id;
    const hasSource = nodes.has(sourceId) || symbolIds.has(sourceId);
    const hasTarget = nodes.has(targetId) || symbolIds.has(targetId);
    if (!hasSource || !hasTarget) {
      orphanEdgeCount += 1;
      continue;
    }

    const relationshipKind = edgeKind(edge);
    if (relationshipKind === "arg" || relationshipKind === "return") {
      const sourceNode = nodes.get(sourceId);
      const targetNode = nodes.get(targetId);
      const variableNode = toVariableNode(edge, relationshipKind, sourceNode, targetNode);
      nodes.set(variableNode.id, variableNode);
      addEdge(edges, {
        id: `${edge.id}:source`,
        source: sourceId,
        target: variableNode.id,
        kind: relationshipKind,
        label: edge.source_slot || edge.variable_name || relationshipKind,
        dataType: edge.data_type,
        lineNumber: edge.line_number ?? null,
        original: edge,
      });
      addEdge(edges, {
        id: `${edge.id}:target`,
        source: variableNode.id,
        target: targetId,
        kind: relationshipKind,
        label: edge.target_slot || edge.variable_name || relationshipKind,
        dataType: edge.data_type,
        lineNumber: edge.line_number ?? null,
        original: edge,
      });
      continue;
    }

    addEdge(edges, {
      id: edge.id,
      source: sourceId,
      target: targetId,
      kind: relationshipKind,
      label: readableEdgeLabel(edge),
      dataType: edge.data_type,
      lineNumber: edge.line_number ?? null,
      original: edge,
    });
  }

  const nodeList = addEdgeCounts(Array.from(nodes.values()), Array.from(edges.values()));
  const edgeList = Array.from(edges.values());
  return {
    nodes: nodeList,
    edges: edgeList,
    folders: nodeList.filter((node) => node.kind === "folder"),
    files: nodeList.filter((node) => node.kind === "file"),
    symbols: nodeList.filter((node) =>
      node.kind === "class" || node.kind === "function" || node.kind === "method",
    ),
    variables: nodeList.filter((node) => node.kind === "variable"),
    projectFiles,
    orphanEdgeCount,
  };
}

export function getGraphStats(model: CodeGraphModel): GraphStats {
  return {
    folderCount: model.folders.length,
    fileCount: model.files.length,
    classCount: model.nodes.filter((node) => node.kind === "class").length,
    functionCount: model.nodes.filter((node) => node.kind === "function").length,
    methodCount: model.nodes.filter((node) => node.kind === "method").length,
    variableCount: model.variables.length,
    edgeCount: model.edges.length,
    callCount: model.edges.filter((edge) => edge.kind === "call").length,
    argCount: model.edges.filter((edge) => edge.kind === "arg").length,
    returnCount: model.edges.filter((edge) => edge.kind === "return").length,
  };
}

export function getNodeNeighborhood(
  model: CodeGraphModel,
  nodeId: string | null,
): NodeNeighborhood {
  if (!nodeId) {
    return { incoming: [], outgoing: [], relatedIds: new Set() };
  }

  const incoming = model.edges.filter((edge) => edge.target === nodeId);
  const outgoing = model.edges.filter((edge) => edge.source === nodeId);
  const relatedIds = new Set<string>([nodeId]);
  for (const edge of incoming) relatedIds.add(edge.source);
  for (const edge of outgoing) relatedIds.add(edge.target);
  return { incoming, outgoing, relatedIds };
}

export function searchNodes(model: CodeGraphModel, query: string): CodeGraphNode[] {
  const normalized = query.trim().toLowerCase();
  if (!normalized) return [];
  return model.nodes
    .filter((node) =>
      [
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
        .includes(normalized),
    )
    .slice(0, 40);
}

export function edgeKindFromLabel(edge: GraphEdge): "call" | "arg" | "return" | "unknown" {
  const kind = edgeKind(edge);
  return kind === "call" || kind === "arg" || kind === "return" ? kind : "unknown";
}

function emptyModel(): CodeGraphModel {
  return {
    nodes: [],
    edges: [],
    folders: [],
    files: [],
    symbols: [],
    variables: [],
    projectFiles: [],
    orphanEdgeCount: 0,
  };
}

function normalizeProjectFiles(graph: DataFlowGraph): ProjectFile[] {
  if (graph.project_files?.length) return graph.project_files;
  return graph.nodes.map((node) => ({
    id: node.id,
    file_path: node.file_path,
    file_name: node.file_name,
    folder_path: node.folder_path,
    language: node.language,
    has_symbols: node.functions.length + node.classes.length > 0,
    symbol_count:
      node.functions.length +
      node.classes.length +
      node.classes.reduce((sum, cls) => sum + cls.methods.length, 0),
  }));
}

function ensureFolderChain(
  folderPath: string,
  nodes: Map<string, CodeGraphNode>,
  edges: Map<string, CodeGraphEdge>,
): void {
  const normalized = normalizeFolder(folderPath);
  const parts = normalized ? normalized.split("/") : [];
  if (!nodes.has("folder:root")) {
    nodes.set("folder:root", {
      id: "folder:root",
      kind: "folder",
      label: "root",
      subtitle: "project root",
      folderPath: "",
      symbolCount: 0,
      edgeCount: 0,
    });
  }

  let parentId = "folder:root";
  let current = "";
  for (const part of parts) {
    current = current ? `${current}/${part}` : part;
    const id = folderId(current);
    if (!nodes.has(id)) {
      nodes.set(id, {
        id,
        kind: "folder",
        label: part,
        subtitle: current,
        folderPath: current,
        parentId,
        symbolCount: 0,
        edgeCount: 0,
      });
    }
    addEdge(edges, {
      id: `contains:${parentId}:${id}`,
      source: parentId,
      target: id,
      kind: "contains",
      label: "contains",
    });
    parentId = id;
  }
}

function linkFolderToFile(
  fileNode: CodeGraphNode,
  nodes: Map<string, CodeGraphNode>,
  edges: Map<string, CodeGraphEdge>,
): void {
  ensureFolderChain(fileNode.folderPath, nodes, edges);
  const parentId = fileNode.folderPath ? folderId(fileNode.folderPath) : "folder:root";
  addEdge(edges, {
    id: `contains:${parentId}:${fileNode.id}`,
    source: parentId,
    target: fileNode.id,
    kind: "contains",
    label: "file",
  });
}

function toFileNode(file: GraphNode): CodeGraphNode {
  const symbolCount =
    file.functions.length +
    file.classes.length +
    file.classes.reduce((sum, cls) => sum + cls.methods.length, 0);
  return {
    id: file.id,
    kind: "file",
    label: file.file_name,
    subtitle: file.folder_path || "root",
    folderPath: normalizeFolder(file.folder_path),
    fileId: file.id,
    filePath: file.file_path,
    fileName: file.file_name,
    language: file.language,
    role: file.architecture_role,
    symbolCount,
    edgeCount: 0,
    source: file,
  };
}

function toProjectFileNode(file: ProjectFile): CodeGraphNode {
  return {
    id: file.id,
    kind: "file",
    label: file.file_name,
    subtitle: file.folder_path || "root",
    folderPath: normalizeFolder(file.folder_path),
    fileId: file.id,
    filePath: file.file_path,
    fileName: file.file_name,
    language: file.language,
    role: file.has_symbols ? "module" : "source",
    symbolCount: file.symbol_count,
    edgeCount: 0,
    source: file,
  };
}

function toFunctionNode(file: GraphNode, fn: FunctionNode): CodeGraphNode {
  return {
    id: fn.id,
    kind: "function",
    label: fn.name,
    subtitle: file.file_name,
    folderPath: normalizeFolder(file.folder_path),
    fileId: file.id,
    filePath: file.file_path,
    fileName: file.file_name,
    language: file.language,
    role: file.architecture_role,
    parentId: file.id,
    qualifiedName: fn.qualified_name ?? fn.id,
    startLine: fn.start_line ?? null,
    endLine: fn.end_line ?? null,
    params: fn.params,
    returnType: fn.return_type,
    edgeCount: 0,
    source: fn,
  };
}

function toClassNode(file: GraphNode, cls: ClassNode): CodeGraphNode {
  return {
    id: cls.id,
    kind: "class",
    label: cls.name,
    subtitle: file.file_name,
    folderPath: normalizeFolder(file.folder_path),
    fileId: file.id,
    filePath: file.file_path,
    fileName: file.file_name,
    language: file.language,
    role: file.architecture_role,
    parentId: file.id,
    qualifiedName: cls.qualified_name ?? cls.id,
    startLine: cls.start_line ?? null,
    endLine: cls.end_line ?? null,
    returnType: "class",
    symbolCount: cls.methods.length,
    edgeCount: 0,
    source: cls,
  };
}

function toMethodNode(file: GraphNode, cls: ClassNode, method: MethodNode): CodeGraphNode {
  return {
    id: method.id,
    kind: "method",
    label: method.name,
    subtitle: cls.name,
    folderPath: normalizeFolder(file.folder_path),
    fileId: file.id,
    filePath: file.file_path,
    fileName: file.file_name,
    language: file.language,
    role: file.architecture_role,
    parentId: cls.id,
    qualifiedName: method.qualified_name ?? method.id,
    startLine: method.start_line ?? null,
    endLine: method.end_line ?? null,
    params: method.params,
    returnType: method.return_type,
    edgeCount: 0,
    source: method,
  };
}

function toVariableNode(
  edge: GraphEdge,
  kind: "arg" | "return",
  sourceNode?: CodeGraphNode,
  targetNode?: CodeGraphNode,
): CodeGraphNode {
  const slot = kind === "arg" ? edge.source_slot || edge.variable_name : edge.target_slot || edge.variable_name;
  const label = slot || (kind === "arg" ? "argument" : "return");
  const owner = sourceNode?.filePath ? sourceNode : targetNode;
  return {
    id: `var:${edge.id}`,
    kind: "variable",
    label,
    subtitle: edge.data_type || kind,
    folderPath: owner?.folderPath ?? "",
    fileId: owner?.fileId,
    filePath: owner?.filePath,
    fileName: owner?.fileName,
    language: owner?.language,
    role: "data-flow",
    qualifiedName: edge.label,
    returnType: edge.data_type,
    edgeCount: 0,
  };
}

function addEdge(edges: Map<string, CodeGraphEdge>, edge: CodeGraphEdge): void {
  if (edge.source === edge.target) return;
  edges.set(edge.id, edge);
}

function addEdgeCounts(nodes: CodeGraphNode[], edges: CodeGraphEdge[]): CodeGraphNode[] {
  const counts = new Map<string, number>();
  for (const edge of edges) {
    counts.set(edge.source, (counts.get(edge.source) ?? 0) + 1);
    counts.set(edge.target, (counts.get(edge.target) ?? 0) + 1);
  }
  return nodes.map((node) => ({ ...node, edgeCount: counts.get(node.id) ?? 0 }));
}

function edgeKind(edge: GraphEdge): CodeEdgeKind {
  if (edge.edge_type === "call") return "call";
  if (edge.edge_type === "arg") return "arg";
  if (edge.edge_type === "return") return "return";
  if (edge.edge_type === "contains") return "contains";
  if (edge.edge_type === "unresolved_call" || edge.resolution === "unresolved") return "unresolved";
  return "reference";
}

function readableEdgeLabel(edge: GraphEdge): string {
  if (edge.edge_type === "call") return edge.label || "calls";
  if (edge.edge_type === "arg") return `${edge.source_slot || edge.variable_name || "arg"} -> ${edge.target_slot || "param"}`;
  if (edge.edge_type === "return") return `${edge.source_slot || "return"} -> ${edge.target_slot || edge.variable_name || "result"}`;
  return edge.label || edge.edge_type;
}

function folderId(folderPath: string): string {
  return `folder:${normalizeFolder(folderPath) || "root"}`;
}

function normalizeFolder(folderPath: string): string {
  return folderPath.replace(/\\/g, "/").replace(/^\.\/?/, "").replace(/\/$/, "");
}
