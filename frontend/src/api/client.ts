const BASE = "/api/v1";

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || `HTTP ${res.status}`);
  }
  return res.json();
}

export const api = {
  listProjects: () =>
    request<
      {
        project_id: string;
        name: string;
        source_type: string;
        source_url: string;
        file_count: number;
        created_at: string;
        latest_analysis: {
          analysis_id: string;
          status: string;
          progress_pct: number;
          error_message: string;
        } | null;
      }[]
    >("/projects"),

  deleteProject: (projectId: string) =>
    request<{ status: string; project_id: string }>(
      `/projects/${projectId}`,
      { method: "DELETE" }
    ),

  importFromUrl: (url: string) =>
    request<{ project_id: string; analysis_id: string; status: string }>(
      "/projects/import",
      { method: "POST", body: JSON.stringify({ source_type: "github", source_url: url }) }
    ),

  importFromFile: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return fetch(`${BASE}/projects/import/upload`, { method: "POST", body: fd }).then(
      (r) => r.json()
    ) as Promise<{ project_id: string; analysis_id: string; status: string }>;
  },

  getAnalysis: (id: string) =>
    request<{ id: string; status: string; progress_pct: number; file_count: number; error_message: string }>(
      `/analyses/${id}`
    ),

  streamProgress: (
    id: string,
    onProgress: (p: { progress_pct: number; message: string; status: string; detail?: string }) => void
  ) => {
    const es = new EventSource(`${BASE}/analyses/${id}/stream`);
    es.onmessage = (e) => {
      const data = JSON.parse(e.data);
      onProgress(data);
      if (data.status === "completed" || data.status === "failed") es.close();
    };
    es.onerror = () => es.close();
    return es;
  },

  getGraph: (id: string) =>
    request<{
      nodes: import("../types").GraphNode[];
      edges: import("../types").GraphEdge[];
      entry_points: string[];
      exit_points: string[];
    }>(`/analyses/${id}/graph`),

  getFile: (analysisId: string, fileId: string) =>
    request<import("../types").AIFileAnalysis>(
      `/analyses/${analysisId}/files/${fileId}`
    ),

  getReport: (id: string) =>
    request<{ content_md: string; architecture_summary: string; issue_count: number }>(
      `/analyses/${id}/report`
    ),

  sendMessage: (analysisId: string, message: string, sessionId?: string) =>
    request<{ session_id: string; reply: string; referenced: string[] }>(
      `/analyses/${analysisId}/chat`,
      { method: "POST", body: JSON.stringify({ session_id: sessionId || null, message }) }
    ),

  /** 流式聊天 — 使用 fetch + ReadableStream 消费后端 SSE 端点 */
  async sendMessageStream(
    analysisId: string,
    message: string,
    sessionId: string | null,
    onChunk: (delta: string) => void,
    onDone: () => void,
    onError: (error: string) => void,
    signal?: AbortSignal,
  ): Promise<void> {
    try {
      const response = await fetch(`${BASE}/analyses/${analysisId}/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, message }),
        signal,
      });

      if (!response.ok) {
        const text = await response.text().catch(() => "");
        throw new Error(text || `HTTP ${response.status}`);
      }

      if (!response.body) throw new Error("响应体为空");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            const data = line.slice(6).trim();
            if (!data) continue;

            try {
              const evt = JSON.parse(data);
              if (evt.type === "chunk") {
                onChunk(evt.delta || "");
              } else if (evt.type === "done") {
                onDone();
                return;
              } else if (evt.type === "error") {
                onError(evt.error || "流式错误");
                return;
              }
            } catch {
              // 忽略无法解析的行
            }
          }
        }
      } finally {
        reader.releaseLock();
      }

      // 流结束但没收到 done 事件
      onDone();
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : "未知错误";
      if (errMsg.includes("aborted") || errMsg.includes("AbortError")) {
        onDone();
      } else {
        onError(errMsg);
      }
    }
  },
};
