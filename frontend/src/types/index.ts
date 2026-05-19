// ═══════════════════════════════════════════
// 前端类型定义 — 与后端 Pydantic models 对应
// ═══════════════════════════════════════════

export type AnalysisStatus =
  | "pending"
  | "parsing"
  | "analyzing"
  | "building"
  | "completed"
  | "failed";

export interface FunctionNode {
  id: string;
  name: string;
  params: { name: string; type: string }[];
  return_type: string;
  is_exported: boolean;
  is_async: boolean;
  description: string;
}

export interface MethodNode {
  id: string;
  name: string;
  params: { name: string; type: string }[];
  return_type: string;
  is_exported: boolean;
  is_async: boolean;
  description: string;
}

export interface ClassNode {
  id: string;
  name: string;
  is_exported: boolean;
  methods: MethodNode[];
}

export interface GraphPort {
  id: string;
  name: string;
  port_type: "function" | "variable" | "class" | "param";
  data_type: string;
  direction: "input" | "output";
  description: string;
}

export interface GraphNode {
  id: string;
  file_path: string;
  file_name: string;
  folder_path: string;
  language: string;
  summary: string;
  detail: string;
  architecture_role: string;
  ports: GraphPort[];
  functions: FunctionNode[];
  classes: ClassNode[];
  x: number;
  y: number;
}

export interface GraphEdge {
  id: string;
  source_node_id: string;
  target_node_id: string;
  source_port_id: string;
  target_port_id: string;
  source_function_id: string;
  target_function_id: string;
  variable_name: string;
  data_type: string;
  edge_type: "import" | "call" | "export" | "port_to_function" | "function_to_port";
  label: string;
}

export interface DataFlowGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
  entry_points: string[];
  exit_points: string[];
}

export interface AnalysisProgress {
  analysis_id: string;
  status: AnalysisStatus;
  progress_pct: number;
  message: string;
  current_step: string;
}

export interface AIInputOutput {
  name: string;
  type: string;
  source: string;
  is_function: boolean;
  description: string;
}

export interface AIFileAnalysis {
  file_path: string;
  summary: string;
  detail: string;
  inputs: AIInputOutput[];
  outputs: AIInputOutput[];
  internal_structures: Record<string, unknown>[];
  architecture_role: string;
  dependencies_summary: string;
}

export interface ArchitectureIssue {
  severity: "info" | "warning" | "error";
  category: string;
  description: string;
  related_files: string[];
  suggestion: string;
}

export interface AnalysisReport {
  project_name: string;
  tech_stack: string[];
  file_count: number;
  total_lines: number;
  architecture_summary: string;
  file_details: AIFileAnalysis[];
  core_flows: string[];
  issues: ArchitectureIssue[];
  health_score: number;
  generated_at: string;
}
