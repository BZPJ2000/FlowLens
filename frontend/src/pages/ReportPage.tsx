import { useEffect, useState } from "react";
import { ArrowLeft, FileText, AlertTriangle, Info } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { useGraphStore } from "../stores/graphStore";
import { api } from "../api/client";

interface ReportPageProps {
  onBack: () => void;
}

export default function ReportPage({ onBack }: ReportPageProps) {
  const analysisId = useGraphStore((s) => s.analysisId);
  const [contentMd, setContentMd] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!analysisId) return;
    api
      .getReport(analysisId)
      .then((r) => setContentMd(r.content_md))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [analysisId]);

  return (
    <div className="w-full h-full flex flex-col bg-[#0a0a10]">
      {/* Header */}
      <div className="flex-shrink-0 flex items-center gap-3 px-4 py-3 border-b border-[#1e1e3a] bg-[#06060a]">
        <button
          onClick={onBack}
          className="flex items-center gap-1.5 text-xs text-[#a1a1aa] hover:text-[#f5f5f7] transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          返回可视化
        </button>
        <div className="flex items-center gap-2 text-sm text-[#f5f5f7] font-semibold">
          <FileText className="w-4 h-4 text-[#7c3aed]" />
          架构分析报告
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="flex items-center justify-center h-full text-[#6b7280] text-sm">
            正在加载报告...
          </div>
        ) : (
          <div className="max-w-3xl mx-auto p-8">
            <div className="prose prose-invert prose-sm max-w-none
              prose-headings:text-[#f5f5f7]
              prose-h1:text-xl prose-h1:font-bold prose-h1:border-b prose-h1:border-[#1e1e3a] prose-h1:pb-3
              prose-h2:text-lg prose-h2:font-semibold prose-h2:mt-8
              prose-h3:text-base prose-h3:font-medium prose-h3:text-[#a1a1aa]
              prose-p:text-[#a1a1aa] prose-p:leading-relaxed
              prose-code:text-[#c084fc] prose-code:bg-[#1a1a2e] prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:text-xs
              prose-pre:bg-[#12121c] prose-pre:border prose-pre:border-[#1e1e3a] prose-pre:rounded-lg
              prose-li:text-[#a1a1aa] prose-li:text-xs
              prose-strong:text-[#f5f5f7]
              prose-a:text-[#60a5fa]
              prose-hr:border-[#1e1e3a]
              [&_table]:text-xs
              [&_th]:text-[#6b7280] [&_th]:font-medium
              [&_td]:text-[#a1a1aa] [&_td]:border-[#1e1e3a]
            ">
              <ReactMarkdown>{contentMd}</ReactMarkdown>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
