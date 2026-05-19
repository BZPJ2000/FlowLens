import { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";

interface PortDef {
  id: string;
  name: string;
  data_type: string;
  direction: "input" | "output";
  description: string;
}

const ROLE_COLORS: Record<string, { border: string; bg: string; dot: string }> = {
  controller: { border: "#22c55e", bg: "rgba(34,197,94,0.08)", dot: "#22c55e" },
  service:    { border: "#3b82f6", bg: "rgba(59,130,246,0.08)", dot: "#3b82f6" },
  model:      { border: "#eab308", bg: "rgba(234,179,8,0.08)",  dot: "#eab308" },
  view:       { border: "#a855f7", bg: "rgba(168,85,247,0.08)",  dot: "#a855f7" },
  util:       { border: "#6b7280", bg: "rgba(107,114,128,0.08)", dot: "#6b7280" },
  config:     { border: "#f97316", bg: "rgba(249,115,22,0.08)",  dot: "#f97316" },
  middleware: { border: "#ef4444", bg: "rgba(239,68,68,0.08)",   dot: "#ef4444" },
  hook:       { border: "#ec4899", bg: "rgba(236,72,153,0.08)",  dot: "#ec4899" },
  store:      { border: "#06b6d4", bg: "rgba(6,182,212,0.08)",   dot: "#06b6d4" },
  route:      { border: "#84cc16", bg: "rgba(132,204,22,0.08)",  dot: "#84cc16" },
  type:       { border: "#14b8a6", bg: "rgba(20,184,166,0.08)",  dot: "#14b8a6" },
  other:      { border: "#475569", bg: "rgba(71,85,105,0.08)",   dot: "#475569" },
};

const TYPE_COLORS: Record<string, string> = {
  string: "#4ade80", number: "#60a5fa", boolean: "#f59e0b",
  function: "#c084fc", object: "#fb923c", array: "#f472b6",
  unknown: "#9ca3af", void: "#6b7280", Promise: "#38bdf8",
};

function getTypeColor(type: string): string {
  const base = type.replace(/[<>\[\]|&]/g, " ").trim().split(/\s+/)[0];
  return TYPE_COLORS[base] || TYPE_COLORS.unknown;
}

const FileNode = memo(({ data, selected }: NodeProps) => {
  const d = data as unknown as {
    file_name: string;
    language: string;
    summary: string;
    architecture_role: string;
    ports: PortDef[];
    isSelected: boolean;
    isDimmed: boolean;
    isEntry: boolean;
    isExit: boolean;
  };
  const role = ROLE_COLORS[d.architecture_role] || ROLE_COLORS.other;
  const inputPorts = d.ports.filter((p: PortDef) => p.direction === "input");
  const outputPorts = d.ports.filter((p: PortDef) => p.direction === "output");
  const dimmed = d.isDimmed && !selected;
  const opacity = dimmed ? 0.3 : 1;

  return (
    <div
      className={`relative rounded-lg border-2 backdrop-blur-sm px-3 py-2 transition-all duration-300 ${selected ? "node-selected" : ""}`}
      style={{
        minWidth: 180,
        borderColor: role.border,
        background: role.bg,
        opacity,
        boxShadow: selected ? `0 0 16px ${role.border}40, 0 0 32px ${role.border}20` : dimmed ? "none" : `0 2px 8px rgba(0,0,0,0.3)`,
      }}
    >
      {inputPorts.map((port: PortDef, i: number) => (
        <Handle
          key={port.id}
          type="target"
          position={Position.Left}
          id={port.id}
          style={{
            top: inputPorts.length === 1 ? "50%" : `${((i + 1) / (inputPorts.length + 1)) * 100}%`,
            background: getTypeColor(port.data_type),
            width: 8, height: 8, border: "2px solid #12121c",
            opacity: dimmed ? 0.3 : 1,
          }}
          title={`${port.name}: ${port.data_type}`}
        />
      ))}

      <div className="flex items-center gap-1.5 mb-1">
        <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: role.dot }} />
        <span className="text-xs font-semibold text-[#f5f5f7] truncate" title={d.file_name}>
          {d.file_name}
        </span>
      </div>

      {d.summary && (
        <div className="text-[10px] text-[#a1a1aa] leading-tight line-clamp-2" style={{ opacity: dimmed ? 0.5 : 0.8 }}>
          {d.summary}
        </div>
      )}

      <div className="flex gap-1 mt-1.5">
        <span className="text-[9px] px-1.5 py-0.5 rounded bg-[#1a1a2e] text-[#6b7280]">{d.language}</span>
        {d.architecture_role && (
          <span className="text-[9px] px-1.5 py-0.5 rounded" style={{ background: `${role.border}20`, color: role.border }}>
            {d.architecture_role}
          </span>
        )}
      </div>

      {(d.isEntry || d.isExit) && (
        <div className="flex gap-1 mt-1">
          {d.isEntry && <span className="text-[8px] px-1 py-0.5 rounded bg-green-500/20 text-green-400">ENTRY</span>}
          {d.isExit && <span className="text-[8px] px-1 py-0.5 rounded bg-red-500/20 text-red-400">EXIT</span>}
        </div>
      )}

      {outputPorts.map((port: PortDef, i: number) => (
        <Handle
          key={port.id}
          type="source"
          position={Position.Right}
          id={port.id}
          style={{
            top: outputPorts.length === 1 ? "50%" : `${((i + 1) / (outputPorts.length + 1)) * 100}%`,
            background: getTypeColor(port.data_type),
            width: 8, height: 8, border: "2px solid #12121c",
            opacity: dimmed ? 0.3 : 1,
          }}
          title={`${port.name}: ${port.data_type}`}
        />
      ))}
    </div>
  );
});

FileNode.displayName = "FileNode";
export default FileNode;
