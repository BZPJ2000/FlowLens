import { useEffect, useState } from "react";
import { X, FileCode, ArrowDownToLine, ArrowUpFromLine, Hash, ExternalLink, ChevronDown } from "lucide-react";
import { useGraphStore } from "../../stores/graphStore";
import { api } from "../../api/client";
import { openInEditor, getPreferredEditor, setPreferredEditor, EDITORS, type EditorType } from "../../utils/editorLink";

const TYPE_COLORS: Record<string, string> = {
  string: "#4ade80", number: "#60a5fa", boolean: "#f59e0b",
  function: "#c084fc", object: "#fb923c", array: "#f472b6",
  unknown: "#9ca3af", void: "#6b7280", Promise: "#38bdf8",
};

function getTypeColor(type: string): string {
  const base = type.replace(/[<>\[\]|&]/g, " ").trim().split(/\s+/)[0];
  return TYPE_COLORS[base] || "#9ca3af";
}

export default function DetailPanel() {
  const selectedNodeId = useGraphStore((s) => s.selectedNodeId);
  const selectedFileDetail = useGraphStore((s) => s.selectedFileDetail);
  const setFileDetail = useGraphStore((s) => s.setFileDetail);
  const showDetailPanel = useGraphStore((s) => s.showDetailPanel);
  const toggleDetailPanel = useGraphStore((s) => s.toggleDetailPanel);
  const analysisId = useGraphStore((s) => s.analysisId);
  const graph = useGraphStore((s) => s.graph);
  const selectNode = useGraphStore((s) => s.selectNode);

  const [preferredEditor, setPreferredEditorState] = useState<EditorType>(getPreferredEditor());
  const [showEditorMenu, setShowEditorMenu] = useState(false);

  const selectedNode = graph?.nodes.find((n) => n.id === selectedNodeId);

  useEffect(() => {
    if (selectedNodeId && analysisId) {
      api.getFile(analysisId, selectedNodeId).then(setFileDetail).catch(console.error);
    } else {
      setFileDetail(null);
    }
  }, [selectedNodeId, analysisId]);

  if (!showDetailPanel) return null;

  return (
    <div className="w-80 flex-shrink-0 bg-[#0a0a10] border-l border-[#1e1e3a] overflow-y-auto animate-fade-in">
      {/* Header */}
      <div className="sticky top-0 bg-[#0a0a10]/95 backdrop-blur-sm flex items-center justify-between p-3 border-b border-[#1e1e3a] z-10">
        <div className="flex items-center gap-2">
          <FileCode className="w-4 h-4 text-[#a1a1aa]" />
          <h3 className="text-xs font-semibold text-[#f5f5f7] uppercase tracking-wider">
            文件详情
          </h3>
        </div>
        <button
          onClick={() => { toggleDetailPanel(); selectNode(null); }}
          className="text-[#6b7280] hover:text-[#f5f5f7] transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {!selectedNode && !selectedFileDetail ? (
        <div className="p-6 text-center text-sm text-[#6b7280]">
          点击图中节点查看详情
        </div>
      ) : (
        <div className="p-4 space-y-4 text-sm">
          {/* File path */}
          <div>
            <div className="text-[10px] uppercase tracking-wider text-[#6b7280] mb-1">
              File
            </div>
            <div className="text-[#f5f5f7] font-mono text-xs break-all bg-[#12121c] rounded px-2 py-1.5 border border-[#1e1e3a]">
              {selectedNode?.file_path || selectedFileDetail?.file_path}
            </div>

            {/* Open in Editor button */}
            <div className="mt-2 relative">
              <button
                onClick={() => {
                  const filePath = selectedNode?.file_path || selectedFileDetail?.file_path;
                  if (filePath) openInEditor(preferredEditor, filePath);
                }}
                className="w-full flex items-center justify-center gap-2 px-3 py-1.5 text-xs bg-[#7c3aed]/10 hover:bg-[#7c3aed]/20 text-[#a78bfa] rounded border border-[#7c3aed]/20 hover:border-[#7c3aed]/40 transition-all"
              >
                <ExternalLink className="w-3.5 h-3.5" />
                <span>Open in {EDITORS[preferredEditor].name}</span>
              </button>

              {/* Editor selector dropdown */}
              <button
                onClick={() => setShowEditorMenu(!showEditorMenu)}
                className="absolute right-0 top-0 h-full px-2 hover:bg-[#7c3aed]/10 rounded-r border-l border-[#7c3aed]/20 transition-colors"
              >
                <ChevronDown className="w-3 h-3 text-[#a78bfa]" />
              </button>

              {showEditorMenu && (
                <div className="absolute top-full left-0 right-0 mt-1 bg-[#12121c] border border-[#1e1e3a] rounded shadow-lg z-20 overflow-hidden">
                  {(Object.keys(EDITORS) as EditorType[]).map((editor) => (
                    <button
                      key={editor}
                      onClick={() => {
                        setPreferredEditorState(editor);
                        setPreferredEditor(editor);
                        setShowEditorMenu(false);
                      }}
                      className={`w-full flex items-center gap-2 px-3 py-2 text-xs hover:bg-[#1a1a2e] transition-colors ${
                        editor === preferredEditor ? "bg-[#7c3aed]/10 text-[#a78bfa]" : "text-[#a1a1aa]"
                      }`}
                    >
                      <span>{EDITORS[editor].icon}</span>
                      <span>{EDITORS[editor].name}</span>
                      {editor === preferredEditor && (
                        <span className="ml-auto text-[10px] text-[#7c3aed]">✓</span>
                      )}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Badges */}
          <div className="flex gap-1.5 flex-wrap">
            {selectedNode?.language && (
              <span className="text-[10px] px-2 py-0.5 rounded bg-[#1a1a2e] text-[#6b7280] border border-[#1e1e3a]">
                {selectedNode.language}
              </span>
            )}
            {selectedFileDetail?.architecture_role && (
              <span className="text-[10px] px-2 py-0.5 rounded bg-purple-500/10 text-purple-400 border border-purple-500/20">
                {selectedFileDetail.architecture_role}
              </span>
            )}
          </div>

          {/* Summary */}
          <div>
            <div className="text-[10px] uppercase tracking-wider text-[#6b7280] mb-1">
              Summary
            </div>
            <div className="text-[#f5f5f7] text-xs leading-relaxed">
              {selectedFileDetail?.summary || selectedNode?.summary || "—"}
            </div>
          </div>

          {/* Detail */}
          <div>
            <div className="text-[10px] uppercase tracking-wider text-[#6b7280] mb-1">
              Detail
            </div>
            <div className="text-[#a1a1aa] text-xs leading-relaxed">
              {selectedFileDetail?.detail || selectedNode?.detail || "—"}
            </div>
          </div>

          {/* Inputs */}
          {selectedFileDetail?.inputs && selectedFileDetail.inputs.length > 0 && (
            <div>
              <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-[#6b7280] mb-2">
                <ArrowDownToLine className="w-3 h-3" />
                Inputs / Dependencies
              </div>
              <div className="space-y-1">
                {selectedFileDetail.inputs.map((inp, i) => (
                  <div
                    key={i}
                    className="flex items-center gap-2 text-[11px] bg-[#12121c] rounded-lg px-2.5 py-1.5 border border-[#1e1e3a]"
                  >
                    <span
                      className="w-2 h-2 rounded-full flex-shrink-0"
                      style={{ background: getTypeColor(inp.type) }}
                    />
                    <span className="text-[#f5f5f7] font-mono text-[11px]">{inp.name}</span>
                    <span className="text-[#6b7280] flex-1 text-right">: {inp.type}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Outputs */}
          {selectedFileDetail?.outputs && selectedFileDetail.outputs.length > 0 && (
            <div>
              <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-[#6b7280] mb-2">
                <ArrowUpFromLine className="w-3 h-3" />
                Outputs / Exports
              </div>
              <div className="space-y-1">
                {selectedFileDetail.outputs.map((out, i) => (
                  <div
                    key={i}
                    className="flex items-center gap-2 text-[11px] bg-[#12121c] rounded-lg px-2.5 py-1.5 border border-[#1e1e3a]"
                  >
                    <span
                      className="w-2 h-2 rounded-full flex-shrink-0"
                      style={{ background: getTypeColor(out.type) }}
                    />
                    <span className="text-[#f5f5f7] font-mono text-[11px]">{out.name}</span>
                    <span className="text-[#6b7280] flex-1 text-right">: {out.type}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Internal Structures */}
          {selectedFileDetail?.internal_structures &&
            selectedFileDetail.internal_structures.length > 0 && (
              <div>
                <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-[#6b7280] mb-2">
                  <Hash className="w-3 h-3" />
                  Structures
                </div>
                <div className="space-y-1.5">
                  {selectedFileDetail.internal_structures.map((s, i) => (
                    <div
                      key={i}
                      className="bg-[#12121c] rounded-lg px-2.5 py-1.5 border border-[#1e1e3a]"
                    >
                      <div className="text-[11px] font-mono text-[#f5f5f7]">
                        {(s as Record<string, string>).name || "?"}
                        <span className="text-[#6b7280] ml-1">
                          ({(s as Record<string, string>).type || "?"})
                        </span>
                      </div>
                      {Array.isArray((s as Record<string, unknown>).fields) && (
                        <div className="flex flex-wrap gap-1 mt-1">
                          {((s as Record<string, unknown>).fields as Array<Record<string, string>>).map(
                            (f, j) => (
                              <span
                                key={j}
                                className="text-[9px] px-1 py-0.5 rounded bg-[#1a1a2e] text-[#a1a1aa] font-mono"
                              >
                                {f.name}: {f.type}
                              </span>
                            )
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
        </div>
      )}
    </div>
  );
}
