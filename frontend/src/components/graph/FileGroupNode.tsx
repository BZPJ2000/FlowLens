import { memo, useMemo } from "react";
import { Handle, Position } from "@xyflow/react";
import type { NodeProps } from "@xyflow/react";
import { computePortVerticalPositions, PORT_HANDLE_SIZE } from "./portLayout";
import { getTypeColor } from "./typeColors";

interface PortDef {
  id: string;
  name: string;
  data_type: string;
  direction: "input" | "output";
  port_type: string;
  description: string;
}

const ROLE_COLORS: Record<string, { border: string; bg: string; dot: string; text: string }> = {
  controller: { border: "#22c55e", bg: "rgba(34,197,94,0.04)", dot: "#22c55e", text: "#4ade80" },
  service:    { border: "#3b82f6", bg: "rgba(59,130,246,0.04)", dot: "#3b82f6", text: "#60a5fa" },
  model:      { border: "#eab308", bg: "rgba(234,179,8,0.04)",  dot: "#eab308", text: "#facc15" },
  view:       { border: "#a855f7", bg: "rgba(168,85,247,0.04)",  dot: "#a855f7", text: "#c084fc" },
  util:       { border: "#6b7280", bg: "rgba(107,114,128,0.04)", dot: "#6b7280", text: "#9ca3af" },
  config:     { border: "#f97316", bg: "rgba(249,115,22,0.04)",  dot: "#f97316", text: "#fb923c" },
  middleware: { border: "#ef4444", bg: "rgba(239,68,68,0.04)",   dot: "#ef4444", text: "#f87171" },
  hook:       { border: "#ec4899", bg: "rgba(236,72,153,0.04)",  dot: "#ec4899", text: "#f472b6" },
  store:      { border: "#06b6d4", bg: "rgba(6,182,212,0.04)",   dot: "#06b6d4", text: "#22d3ee" },
  route:      { border: "#84cc16", bg: "rgba(132,204,22,0.04)",  dot: "#84cc16", text: "#a3e635" },
  type:       { border: "#14b8a6", bg: "rgba(20,184,166,0.04)",  dot: "#14b8a6", text: "#2dd4bf" },
  other:      { border: "#475569", bg: "rgba(71,85,105,0.04)",   dot: "#475569", text: "#94a3b8" },
};

interface FileGroupData {
  file_name: string;
  folder_path: string;
  language: string;
  summary: string;
  architecture_role: string;
  ports: PortDef[];
  functions: { id: string; name: string; is_exported: boolean; is_async: boolean; params: { name: string; type: string }[]; return_type: string }[];
  isSelected: boolean;
  isDimmed: boolean;
  isEntry: boolean;
  isExit: boolean;
  isPathHighlighted: boolean;
  width: number;
  height: number;
  leftSidebarW: number;
  rightSidebarW: number;
  contentH: number;
  functionCount: number;
  exportedCount: number;
}

const HEADER_H = 36;
const FOOTER_H = 26;

const FileGroupNode = memo(({ data, selected }: NodeProps) => {
  const d = data as unknown as FileGroupData;
  const role = ROLE_COLORS[d.architecture_role] || ROLE_COLORS.other;
  const dimmed = d.isDimmed && !selected && !d.isPathHighlighted;
  const opacity = dimmed ? 0.25 : 1;

  const ports = d.ports || [];
  const inputPorts = useMemo(() => ports.filter((p) => p.direction === "input"), [ports]);
  const outputPorts = useMemo(() => ports.filter((p) => p.direction === "output"), [ports]);

  const nodeWidth = d.width || 520;
  const nodeHeight = d.height || 200;
  const leftW = d.leftSidebarW || 0;
  const rightW = d.rightSidebarW || 0;
  const contentH = d.contentH || 120;
  const hasInputs = inputPorts.length > 0;
  const hasOutputs = outputPorts.length > 0;

  const sidebarAreaH = contentH - 8;
  const inputPositions = useMemo(
    () => computePortVerticalPositions(inputPorts.length, sidebarAreaH, 4),
    [inputPorts.length, sidebarAreaH],
  );
  const outputPositions = useMemo(
    () => computePortVerticalPositions(outputPorts.length, sidebarAreaH, 4),
    [outputPorts.length, sidebarAreaH],
  );

  const handleBase = {
    width: PORT_HANDLE_SIZE,
    height: PORT_HANDLE_SIZE,
    border: "2px solid #12121c",
    opacity: dimmed ? 0.2 : 1,
  };

  return (
    <div
      className="relative rounded-xl border-2 backdrop-blur-sm transition-all duration-300 overflow-hidden"
      style={{
        width: nodeWidth,
        height: nodeHeight,
        borderColor: d.isPathHighlighted
          ? "#a78bfa"
          : selected
            ? role.border
            : d.isDimmed
              ? "#1a1a2e"
              : role.border,
        background: d.isPathHighlighted
          ? "rgba(124,58,237,0.06)"
          : selected
            ? role.bg
            : "rgba(10,10,16,0.95)",
        opacity,
        boxShadow: selected
          ? `0 0 20px ${role.border}30, 0 0 40px ${role.border}10`
          : d.isPathHighlighted
            ? "0 0 16px rgba(124,58,237,0.2)"
            : d.isDimmed
              ? "none"
              : "0 4px 16px rgba(0,0,0,0.4)",
      }}
    >
      {/* ── Header bar ── */}
      <div
        className="flex items-center gap-2 px-3 border-b"
        style={{
          height: HEADER_H,
          borderColor: dimmed ? "#1a1a2e" : `${role.border}30`,
          background: `linear-gradient(to bottom, ${role.bg}, transparent)`,
        }}
      >
        <span
          className="w-2.5 h-2.5 rounded-full flex-shrink-0"
          style={{ background: role.dot, opacity: dimmed ? 0.5 : 1 }}
        />
        <span className="text-xs font-bold text-[#f5f5f7] truncate flex-1 font-mono" title={d.file_name}>
          {d.file_name}
        </span>
        <span className="text-[9px] px-1.5 py-0.5 rounded bg-[#1a1a2e] text-[#6b7280] flex-shrink-0 font-mono">
          {d.language}
        </span>
        {d.architecture_role && d.architecture_role !== "other" && (
          <span className="text-[9px] px-1.5 py-0.5 rounded flex-shrink-0"
            style={{ background: `${role.border}20`, color: role.text }}>
            {d.architecture_role}
          </span>
        )}
        {d.isEntry && (
          <span className="text-[8px] px-1.5 py-0.5 rounded bg-green-500/20 text-green-400 flex-shrink-0 font-semibold">ENTRY</span>
        )}
        {d.isExit && (
          <span className="text-[8px] px-1.5 py-0.5 rounded bg-red-500/20 text-red-400 flex-shrink-0 font-semibold">EXIT</span>
        )}
      </div>

      {/* ── Body: 3-column layout ── */}
      <div className="flex" style={{ height: contentH }}>
        {/* ── Left sidebar: INPUT ports ── */}
        {hasInputs && (
          <div
            className="relative border-r flex-shrink-0"
            style={{
              width: leftW,
              borderColor: dimmed ? "#1a1a2e" : `${role.border}15`,
            }}
          >
            <div className="absolute top-1 left-0 right-0 text-center text-[7px] text-[#4b5563] uppercase tracking-wider font-semibold">
              ▼ IN
            </div>
            {inputPorts.map((port, idx) => {
              const pos = inputPositions[idx];
              const tc = getTypeColor(port.data_type);
              return (
                <div key={port.id}>
                  <Handle
                    type="target"
                    position={Position.Left}
                    id={port.id}
                    style={{
                      ...handleBase,
                      background: tc.dot,
                      top: HEADER_H + pos.topPx,
                    }}
                  />
                  <Handle
                    type="source"
                    position={Position.Left}
                    id={port.id}
                    style={{
                      ...handleBase,
                      background: tc.dot,
                      opacity: 0.001,
                      top: HEADER_H + pos.topPx,
                    }}
                  />
                  <div
                    className="absolute left-2 right-1 flex items-center gap-1.5 pointer-events-none"
                    style={{ top: pos.topPx - 10 }} // 标签垂直居中对齐 Handle
                  >
                    <span
                      className="w-2 h-2 rounded-full flex-shrink-0"
                      style={{ background: tc.dot }}
                    />
                    <span
                      className="text-[10px] font-semibold text-[#f1f5f9] truncate leading-[20px] font-mono"
                      title={`${port.name}: ${port.data_type}`}
                    >
                      {port.name}
                    </span>
                    <span
                      className="text-[8px] px-1 py-0.5 rounded flex-shrink-0 ml-auto font-mono"
                      style={{ background: tc.bg, color: tc.text, border: `1px solid ${tc.border}` }}
                    >
                      {port.data_type}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* ── Center: function/class child nodes rendered by ReactFlow ── */}
        <div className="flex-1 relative" />

        {/* ── Right sidebar: OUTPUT ports ── */}
        {hasOutputs && (
          <div
            className="relative border-l flex-shrink-0"
            style={{
              width: rightW,
              borderColor: dimmed ? "#1a1a2e" : `${role.border}15`,
            }}
          >
            <div className="absolute top-1 left-0 right-0 text-center text-[7px] text-[#4b5563] uppercase tracking-wider font-semibold">
              ▼ OUT
            </div>
            {outputPorts.map((port, idx) => {
              const pos = outputPositions[idx];
              const tc = getTypeColor(port.data_type);
              return (
                <div key={port.id}>
                  <Handle
                    type="source"
                    position={Position.Right}
                    id={port.id}
                    style={{
                      ...handleBase,
                      background: tc.dot,
                      top: HEADER_H + pos.topPx,
                    }}
                  />
                  <Handle
                    type="target"
                    position={Position.Right}
                    id={port.id}
                    style={{
                      ...handleBase,
                      background: tc.dot,
                      opacity: 0.001,
                      top: HEADER_H + pos.topPx,
                    }}
                  />
                  <div
                    className="absolute left-1 right-2 flex items-center gap-1.5 pointer-events-none"
                    style={{ top: pos.topPx - 10 }}
                  >
                    <span
                      className="text-[8px] px-1 py-0.5 rounded flex-shrink-0 font-mono"
                      style={{ background: tc.bg, color: tc.text, border: `1px solid ${tc.border}` }}
                    >
                      {port.data_type}
                    </span>
                    <span
                      className="text-[10px] font-semibold text-[#f1f5f9] truncate leading-[20px] flex-1 text-right font-mono"
                      title={`${port.name}: ${port.data_type}`}
                    >
                      {port.name}
                    </span>
                    <span
                      className="w-2 h-2 rounded-full flex-shrink-0"
                      style={{ background: tc.dot }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Fallback handles (left/right) */}
      <Handle type="target" position={Position.Left} id="in"
        style={{ ...handleBase, background: "#60a5fa", visibility: "hidden" }} />
      <Handle type="source" position={Position.Right} id="out"
        style={{ ...handleBase, background: "#f59e0b", visibility: "hidden" }} />

      {/* Top/Bottom handles for vertical connections */}
      <Handle type="target" position={Position.Top} id="top"
        style={{ ...handleBase, background: "#a78bfa" }} />
      <Handle type="source" position={Position.Bottom} id="bottom"
        style={{ ...handleBase, background: "#a78bfa" }} />

      {/* ── Footer ── */}
      <div
        className="px-3 flex items-center justify-between border-t"
        style={{
          height: FOOTER_H,
          borderColor: dimmed ? "#1a1a2e" : `${role.border}20`,
        }}
      >
        <span className="text-[9px] text-[#4b5563] font-mono">
          {d.functionCount} items ({d.exportedCount} exported)
        </span>
        {d.summary && (
          <span className="text-[8px] text-[#6b7280] truncate max-w-[220px]" title={d.summary}>
            {d.summary}
          </span>
        )}
      </div>
    </div>
  );
});

FileGroupNode.displayName = "FileGroupNode";
export default FileGroupNode;
