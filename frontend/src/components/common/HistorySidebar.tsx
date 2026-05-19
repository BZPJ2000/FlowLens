import { useEffect, useState } from "react";
import { History, Loader2, Clock, Github, Upload, ChevronRight, Circle, CheckCircle2, XCircle, Trash2 } from "lucide-react";
import { api } from "../../api/client";

interface ProjectItem {
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
}

interface HistorySidebarProps {
  onSelect: (analysisId: string) => void;
}

export default function HistorySidebar({ onSelect }: HistorySidebarProps) {
  const [projects, setProjects] = useState<ProjectItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadProjects = () => {
    setLoading(true);
    setError("");
    api
      .listProjects()
      .then(setProjects)
      .catch((e) => setError(e instanceof Error ? e.message : "加载失败"))
      .finally(() => setLoading(false));
  };

  const handleDelete = (projectId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm("确定删除此项目？")) return;
    api.deleteProject(projectId).then(() => {
      setProjects((prev) => prev.filter((p) => p.project_id !== projectId));
    }).catch((err) => {
      setError(err instanceof Error ? err.message : "删除失败");
    });
  };

  useEffect(() => {
    loadProjects();
  }, []);

  const statusIcon = (status: string) => {
    switch (status) {
      case "completed":
        return <CheckCircle2 className="w-3 h-3 text-green-400" />;
      case "failed":
        return <XCircle className="w-3 h-3 text-red-400" />;
      default:
        return <Circle className="w-3 h-3 text-[#6b7280] animate-pulse" />;
    }
  };

  const timeAgo = (iso: string) => {
    if (!iso) return "";
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
  };

  return (
    <div className="w-72 flex-shrink-0 bg-[#08080e] border-r border-[#1e1e3a] overflow-y-auto flex flex-col h-full">
      {/* Header */}
      <div className="flex-shrink-0 flex items-center gap-2 px-4 py-3 border-b border-[#1e1e3a]">
        <History className="w-4 h-4 text-[#6b7280]" />
        <span className="text-xs font-semibold text-[#a1a1aa] uppercase tracking-wider">
          History
        </span>
        <button
          onClick={loadProjects}
          className="ml-auto text-[10px] text-[#6b7280] hover:text-[#a1a1aa] transition-colors"
        >
          Refresh
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {loading && (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-4 h-4 text-[#6b7280] animate-spin" />
          </div>
        )}

        {error && (
          <div className="px-4 py-3 text-[11px] text-red-400">{error}</div>
        )}

        {!loading && projects.length === 0 && (
          <div className="px-4 py-8 text-center text-[11px] text-[#4b5563]">
            <Clock className="w-5 h-5 mx-auto mb-2 opacity-30" />
            No history yet
            <br />
            <span className="text-[10px]">Upload a project to get started</span>
          </div>
        )}

        {!loading &&
          projects.map((p) => {
            const analysis = p.latest_analysis;
            const isCompleted = analysis?.status === "completed";
            const isFailed = analysis?.status === "failed";
            const canOpen = isCompleted && !!analysis;

            return (
              <div
                key={p.project_id}
                onClick={() => {
                  if (canOpen) {
                    onSelect(analysis.analysis_id);
                  }
                }}
                role={canOpen ? "button" : undefined}
                tabIndex={canOpen ? 0 : -1}
                onKeyDown={(e) => {
                  if (canOpen && (e.key === "Enter" || e.key === " ")) {
                    e.preventDefault();
                    onSelect(analysis.analysis_id);
                  }
                }}
                className={`w-full text-left px-4 py-3 border-b border-[#0f0f1a] hover:bg-[#0f0f1a]/50 transition-colors group ${
                  canOpen ? "cursor-pointer" : "opacity-50"
                }`}
              >
                {/* Top row: name + status */}
                <div className="flex items-center gap-2 mb-1">
                  {p.source_type === "github" ? (
                    <Github className="w-3 h-3 text-[#6b7280] flex-shrink-0" />
                  ) : (
                    <Upload className="w-3 h-3 text-[#6b7280] flex-shrink-0" />
                  )}
                  <span className="text-xs text-[#e2e8f0] truncate flex-1 font-medium">
                    {p.name}
                  </span>
                  {analysis && statusIcon(analysis.status)}
                  <button
                    onClick={(ev) => handleDelete(p.project_id, ev)}
                    className="w-4 h-4 flex items-center justify-center text-[#4b5563] hover:text-red-400 opacity-0 group-hover:opacity-100 transition-all flex-shrink-0"
                    title="删除"
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                  {isCompleted && (
                    <ChevronRight className="w-3 h-3 text-[#4b5563] opacity-0 group-hover:opacity-100 transition-opacity" />
                  )}
                </div>

                {/* Bottom row: time + file count */}
                <div className="flex items-center gap-2 text-[10px] text-[#4b5563]">
                  <span>{timeAgo(p.created_at)}</span>
                  <span>·</span>
                  <span>{p.file_count} files</span>
                  {isFailed && analysis?.error_message && (
                    <>
                      <span>·</span>
                      <span className="text-red-400/60 truncate max-w-[120px]">
                        {analysis.error_message.slice(0, 40)}
                      </span>
                    </>
                  )}
                </div>

                {/* Source URL (if github) */}
                {p.source_url && (
                  <div className="text-[9px] text-[#4b5563] truncate mt-0.5 font-mono">
                    {p.source_url}
                  </div>
                )}
              </div>
            );
          })}
      </div>

      {/* Footer */}
      <div className="flex-shrink-0 px-4 py-2 border-t border-[#0f0f1a] text-[9px] text-[#4b5563] text-center">
        {projects.length} project{projects.length !== 1 ? "s" : ""}
      </div>
    </div>
  );
}
