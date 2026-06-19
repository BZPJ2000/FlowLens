import type {
  AnalysisProgress,
  DataFlowGraph,
  ImportResult,
  ProjectSummary,
  SourceFile,
} from "../types";

const BASE = "/api/v1";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const body = await response.text().catch(() => "");
    throw new Error(body || `HTTP ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export const api = {
  listProjects: () => request<ProjectSummary[]>("/projects"),

  deleteProject: (projectId: string) =>
    request<{ status: string; project_id: string }>(`/projects/${projectId}`, {
      method: "DELETE",
    }),

  importLocalPath: (sourcePath: string) =>
    request<ImportResult>("/projects/import", {
      method: "POST",
      body: JSON.stringify({ source_type: "local", source_url: sourcePath }),
    }),

  importArchive: async (file: File) => {
    const form = new FormData();
    form.append("file", file);
    const response = await fetch(`${BASE}/projects/import/upload`, {
      method: "POST",
      body: form,
    });
    if (!response.ok) {
      const body = await response.text().catch(() => "");
      throw new Error(body || `HTTP ${response.status}`);
    }
    return response.json() as Promise<ImportResult>;
  },

  getAnalysis: (analysisId: string) =>
    request<AnalysisProgress>(`/analyses/${analysisId}`),

  streamProgress: (
    analysisId: string,
    onProgress: (progress: AnalysisProgress) => void,
    onError?: () => void,
  ) => {
    const events = new EventSource(`${BASE}/analyses/${analysisId}/stream`);
    events.onmessage = (event) => {
      onProgress(JSON.parse(event.data) as AnalysisProgress);
    };
    events.onerror = () => {
      events.close();
      onError?.();
    };
    return events;
  },

  getGraph: (analysisId: string) =>
    request<DataFlowGraph>(`/analyses/${analysisId}/graph`),

  getSource: (
    analysisId: string,
    filePath: string,
    startLine?: number | null,
    endLine?: number | null,
  ) => {
    const params = new URLSearchParams({ file_path: filePath });
    if (startLine != null) params.set("start_line", String(startLine));
    if (endLine != null) params.set("end_line", String(endLine));
    return request<SourceFile>(`/analyses/${analysisId}/source?${params.toString()}`);
  },
};
