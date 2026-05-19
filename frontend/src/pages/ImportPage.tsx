import { useState, useRef, type DragEvent } from "react";
import { Github, Upload, Loader2, Zap, FileCode } from "lucide-react";
import { useGraphStore } from "../stores/graphStore";
import { api } from "../api/client";

interface ImportPageProps {
  onStart: (analysisId: string) => void;
}

export default function ImportPage({ onStart }: ImportPageProps) {
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [progressPct, setProgressPct] = useState(0);
  const [progressMsg, setProgressMsg] = useState("");
  const [progressDetail, setProgressDetail] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const setProgress = useGraphStore((s) => s.setProgress);
  const setAnalysisId = useGraphStore((s) => s.setAnalysisId);
  const [scanProgressDetail, currentFileDetail] = progressDetail.split("；当前文件: ");

  const startAnalysis = (analysisId: string) => {
    setAnalysisId(analysisId);
    setAnalyzing(true);

    // 主进度来源: SSE (实时)
    const es = api.streamProgress(analysisId, (p) => {
      setProgress(p.progress_pct, p.message, p.status as never);
      setProgressPct(p.progress_pct || 0);
      setProgressMsg(p.message || "");
      setProgressDetail(p.detail || "");

      if (p.status === "completed") {
        es.close();
        setTimeout(() => onStart(analysisId), 600);
      } else if (p.status === "failed") {
        es.close();
        setError(p.message || "分析失败");
        setAnalyzing(false);
        setLoading(false);
      }
    });

    // 后备轮询: 每 3 秒查一次 DB 状态，防止 SSE 断开
    let pollFailures = 0;
    const poll = setInterval(async () => {
      try {
        pollFailures = 0;
        const a = await api.getAnalysis(analysisId);
        if (a.status === "completed") {
          clearInterval(poll);
          es.close();
          setProgressPct(100);
          setProgressMsg("分析完成");
          setTimeout(() => onStart(analysisId), 300);
        } else if (a.status === "failed") {
          clearInterval(poll);
          es.close();
          setError(a.error_message || "分析失败");
          setAnalyzing(false);
          setLoading(false);
        }
        // 用 DB 进度更新（SSE 正常时会覆盖）
        if (a.progress_pct > progressPct) {
          setProgressPct(a.progress_pct);
        }
      } catch {
        pollFailures++;
        // 连续 5 次轮询失败（15s），停止并报错
        if (pollFailures >= 5) {
          clearInterval(poll);
          es.close();
          setError("无法连接服务器，请刷新页面后重试");
          setAnalyzing(false);
          setLoading(false);
        }
      }
    }, 3000);
  };

  const handleUrlSubmit = async () => {
    if (!url.trim()) return;
    setLoading(true);
    setError("");
    try {
      const res = await api.importFromUrl(url.trim());
      startAnalysis(res.analysis_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "导入失败");
      setLoading(false);
    }
  };

  const handleFileUpload = async (file: File) => {
    setLoading(true);
    setError("");
    try {
      const res = await api.importFromFile(file);
      startAnalysis(res.analysis_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "上传失败");
      setLoading(false);
    }
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file && (file.name.endsWith(".zip") || file.name.endsWith(".tar.gz") || file.name.endsWith(".tgz"))) {
      handleFileUpload(file);
    } else {
      setError("请上传 .zip / .tar.gz 文件");
    }
  };

  return (
    <div className="w-full h-full flex items-center justify-center bg-[#06060a]"
      style={{ background: "radial-gradient(circle at 50% 50%, rgba(124,58,237,0.04) 0%, transparent 70%), linear-gradient(to bottom, #06060a, #0a0a10)" }}
    >
      <div className="w-full max-w-lg px-6">
        {/* Logo */}
        <div className="text-center mb-10">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-[#7c3aed]/10 border border-[#7c3aed]/20 mb-4">
            <Zap className="w-7 h-7 text-[#a78bfa]" />
          </div>
          <h1 className="text-3xl font-bold text-[#f5f5f7] mb-2 tracking-tight">
            PoltAIshow
          </h1>
          <p className="text-sm text-[#6b7280] leading-relaxed max-w-sm mx-auto">
            导入项目源码，AI 自动解析数据流向，
            <br />
            可视化每个文件的输入输出关系
          </p>
        </div>

        {/* GitHub URL */}
        <div className="mb-4">
          <label className="text-[10px] uppercase tracking-wider text-[#6b7280] mb-2 block">
            GitHub 仓库地址
          </label>
          <div className="flex gap-2">
            <div className="flex-1 relative">
              <Github className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#6b7280]" />
              <input
                type="text"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleUrlSubmit()}
                placeholder="https://github.com/user/repo"
                className="w-full bg-[#12121c] border border-[#1e1e3a] rounded-lg pl-9 pr-3 py-2.5 text-sm text-[#f5f5f7] placeholder-[#4b5563] focus:outline-none focus:border-[#7c3aed] focus:ring-1 focus:ring-[#7c3aed]/30 disabled:opacity-50"
                disabled={loading}
              />
            </div>
            <button
              onClick={handleUrlSubmit}
              disabled={loading || !url.trim()}
              className="px-5 py-2.5 bg-[#7c3aed] hover:bg-[#6d28d9] disabled:bg-[#1a1a2e] disabled:text-[#4b5563] text-white text-sm rounded-lg font-medium transition-all active:scale-95"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : "分析"}
            </button>
          </div>
        </div>

        {/* Divider — GitNexus style */}
        <div className="flex items-center gap-3 my-6">
          <div className="flex-1 h-px bg-[#1e1e3a]" />
          <span className="text-[10px] text-[#4b5563] uppercase tracking-wider">或</span>
          <div className="flex-1 h-px bg-[#1e1e3a]" />
        </div>

        {/* File Upload */}
        <div
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
          onClick={() => fileRef.current?.click()}
          className={`
            border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-all
            ${dragOver
              ? "border-[#7c3aed] bg-[#7c3aed]/5"
              : "border-[#1e1e3a] hover:border-[#2a2a4a] bg-[#0a0a10]"
            }
            ${loading ? "pointer-events-none opacity-50" : ""}
          `}
        >
          <Upload className="w-8 h-8 text-[#4b5563] mx-auto mb-3" />
          <div className="text-sm text-[#a1a1aa]">
            拖拽项目压缩包到此处，或点击选择文件
          </div>
          <div className="text-xs text-[#4b5563] mt-1.5">支持 .zip / .tar.gz</div>
        </div>
        <input
          ref={fileRef}
          type="file"
          accept=".zip,.tar.gz,.tgz"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) handleFileUpload(file);
          }}
        />

        {/* Error */}
        {error && (
          <div className="mt-4 p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-sm text-red-400 animate-fade-in">
            {error}
          </div>
        )}

        {/* Analyzing progress */}
        {analyzing && (
          <div className="mt-6 p-4 bg-[#0a0a10] border border-[#1e1e3a] rounded-xl animate-fade-in">
            <div className="flex items-center gap-3 mb-3">
              <FileCode className="w-4 h-4 text-[#a78bfa] animate-pulse" />
              <span className="text-sm font-medium text-[#f5f5f7]">分析中...</span>
              <span className="text-xs text-[#6b7280] ml-auto">{Math.round(progressPct)}%</span>
            </div>

            {/* Progress bar */}
            <div className="w-full h-2 bg-[#1a1a2e] rounded-full overflow-hidden mb-2">
              <div
                className="h-full rounded-full transition-all duration-500 ease-out"
                style={{
                  width: `${Math.max(2, progressPct)}%`,
                  background: "linear-gradient(90deg, #7c3aed, #a78bfa)",
                }}
              />
            </div>

            {/* Step message */}
            <div className="text-xs text-[#a1a1aa]">{progressMsg || "正在准备..."}</div>
            {progressDetail && (
              <div className="text-[10px] text-[#4b5563] mt-1 leading-relaxed">
                <div className="break-words">{scanProgressDetail}</div>
                {currentFileDetail && (
                  <div className="mt-0.5 truncate font-mono">
                    当前文件: {currentFileDetail}
                  </div>
                )}
              </div>
            )}

            {/* Steps indicator */}
            <div className="flex gap-1.5 mt-3">
              {["解析", "AI分析", "构建图", "报告"].map((label, i) => {
                const stepPct = [20, 55, 85, 100][i];
                const done = progressPct >= stepPct;
                return (
                  <div key={i} className="flex items-center gap-1">
                    <span className={`w-1.5 h-1.5 rounded-full ${done ? "bg-[#a78bfa]" : "bg-[#2a2a4a]"}`} />
                    <span className={`text-[9px] ${done ? "text-[#a1a1aa]" : "text-[#4b5563]"}`}>{label}</span>
                    {i < 3 && <span className="w-3 h-px bg-[#1e1e3a]" />}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Loading (initial upload) */}
        {loading && !analyzing && (
          <div className="mt-4 flex items-center justify-center gap-2 text-sm text-[#6b7280]">
            <Loader2 className="w-4 h-4 animate-spin" />
            正在上传项目...
          </div>
        )}
      </div>
    </div>
  );
}
