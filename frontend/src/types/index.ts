export type AnalysisStatus =
  | "pending"
  | "parsing"
  | "analyzing"
  | "building"
  | "completed"
  | "failed";

export interface ParamNode {
  name: string;
  type: string;
}

export interface FunctionNode {
  id: string;
  name: string;
  qualified_name?: string;
  start_line?: number;
  end_line?: number;
  params: ParamNode[];
  return_type: string;
  is_exported: boolean;
  is_async: boolean;
  description: string;
}

export interface MethodNode extends FunctionNode {}

export interface ClassNode {
  id: string;
  name: string;
  qualified_name?: string;
  start_line?: number;
  end_line?: number;
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
  edge_type:
    | "call"
    | "arg"
    | "return"
    | "unresolved_call"
    | "contains"
    | "import"
    | "export"
    | "port_to_function"
    | "function_to_port";
  source_slot?: string | null;
  target_slot?: string | null;
  line_number?: number | null;
  resolution?: "resolved" | "partial" | "unresolved";
  label: string;
}

export interface ProjectFile {
  id: string;
  file_path: string;
  file_name: string;
  folder_path: string;
  language: string;
  has_symbols: boolean;
  symbol_count: number;
}

export interface DataFlowGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
  entry_points: string[];
  exit_points: string[];
  project_files?: ProjectFile[];
}

export interface ProjectSummary {
  project_id: string;
  name: string;
  source_type: string;
  source_url: string;
  file_count: number;
  created_at: string;
  latest_analysis: {
    analysis_id: string;
    status: AnalysisStatus;
    progress_pct: number;
    error_message: string;
  } | null;
}

export interface AnalysisProgress {
  analysis_id?: string;
  id?: string;
  status: AnalysisStatus;
  progress_pct: number;
  message?: string;
  detail?: string;
  file_count?: number;
  error_message?: string;
}

export interface ImportResult {
  project_id: string;
  analysis_id: string;
  status: AnalysisStatus;
}

export interface SourceFile {
  file_path: string;
  language: string;
  start_line: number;
  end_line: number;
  total_lines: number;
  content: string;
}
