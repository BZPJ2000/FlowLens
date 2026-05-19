import { memo } from "react";
import { Handle, Position } from "@xyflow/react";
import type { NodeProps } from "@xyflow/react";

interface MethodSubNodeData {
  name: string;
  params: { name: string; type: string }[];
  return_type: string;
  is_exported: boolean;
  is_async: boolean;
  description: string;
  isDimmed?: boolean;
  isSelected?: boolean;
  isPathHighlighted?: boolean;
  parentDimmed?: boolean;
}

const PARAM_ROW_H = 22;
const HEADER_H = 26;

const MethodSubNode = memo(({ data, selected }: NodeProps) => {
  const d = data as unknown as MethodSubNodeData;
  const dimmed = (d.isDimmed || d.parentDimmed) && !selected && !d.isPathHighlighted;
  const opacity = dimmed ? 0.2 : 1;

  const bgColor = d.isPathHighlighted
    ? "rgba(124,58,237,0.08)"
    : d.is_exported
      ? "rgba(34,197,94,0.10)"
      : d.is_async
        ? "rgba(168,85,247,0.08)"
        : "rgba(245,158,11,0.06)";

  const borderColor = d.isPathHighlighted
    ? "#a78bfa50"
    : d.is_exported
      ? "#22c55e50"
      : d.is_async
        ? "#a855f750"
        : "#f59e0b30";

  const dotColor = d.isPathHighlighted
    ? "#a78bfa"
    : d.is_exported
      ? "#22c55e"
      : d.is_async
        ? "#a855f7"
        : "#f59e0b";

  return (
    <div
      className="relative rounded border transition-all duration-300"
      style={{
        background: bgColor,
        borderColor,
        opacity,
        minWidth: 160,
        boxShadow: selected
          ? `0 0 6px ${borderColor}`
          : d.isPathHighlighted
            ? "0 0 6px rgba(124,58,237,0.12)"
            : undefined,
      }}
    >
      {/* ── Global call handle (left top) ── */}
      <Handle
        type="target"
        position={Position.Left}
        id="call"
        title={`call ${d.name}`}
        style={{
          background: "#f59e0b",
          width: 6,
          height: 6,
          border: "1.5px solid #12121c",
          opacity: dimmed ? 0.2 : 1,
          top: HEADER_H / 2,
        }}
      />

      {/* ── Per-parameter input handles (left side) ── */}
      {d.params.map((param, idx) => (
        <Handle
          key={`in-${param.name}`}
          type="target"
          position={Position.Left}
          id={`in-${param.name}`}
          title={`${param.name}: ${param.type}`}
          style={{
            background: "#60a5fa",
            width: 5,
            height: 5,
            border: "1.5px solid #12121c",
            opacity: dimmed ? 0.2 : 1,
            top: HEADER_H + PARAM_ROW_H / 2 + idx * PARAM_ROW_H,
          }}
        />
      ))}

      {/* ── Output handle (right) ── */}
      <Handle
        type="source"
        position={Position.Right}
        id="out"
        title={d.return_type !== "unknown" ? `→ ${d.return_type}` : ""}
        style={{
          background: d.return_type && d.return_type !== "unknown" ? "#f59e0b" : "#60a5fa",
          width: 6,
          height: 6,
          border: "2px solid #12121c",
          opacity: dimmed ? 0.2 : 1,
          top: HEADER_H / 2,
        }}
      />

      {/* ── Header ── */}
      <div
        className="flex items-center gap-1.5 px-2.5 py-1 border-b"
        style={{ borderColor: `${borderColor}30` }}
      >
        <span className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ background: dotColor }} />
        <span className="text-[10px] font-mono font-semibold text-[#e2e8f0] truncate">
          {d.name}()
        </span>
        {d.is_async && (
          <span className="text-[7px] px-1 py-0.5 rounded bg-purple-500/20 text-purple-400">
            async
          </span>
        )}
      </div>

      {/* ── Params body ── */}
      {d.params.length > 0 && (
        <div className="px-2.5 py-1">
          {d.params.map((param) => (
            <div key={param.name} className="flex items-center gap-1 text-[8px]" style={{ height: PARAM_ROW_H }}>
              <span className="w-1 h-1 rounded-full flex-shrink-0 bg-blue-500/40" />
              <span className="text-[#e2e8f0] font-mono">{param.name}</span>
              <span className="text-[#64748b]">:</span>
              <span className="text-[#60a5fa] font-mono">{param.type}</span>
            </div>
          ))}
        </div>
      )}
      {d.params.length === 0 && (
        <div className="px-2.5 py-1">
          <div className="text-[7px] text-[#334155] italic">无参数</div>
        </div>
      )}

      {/* ── Return type ── */}
      <div
        className="px-2.5 py-0.5 border-t flex items-center gap-1"
        style={{ borderColor: `${borderColor}20` }}
      >
        <span className="text-[7px] text-[#64748b] font-semibold">OUT</span>
        <span className="text-[8px] text-[#f59e0b] font-mono font-semibold">{d.return_type || "unknown"}</span>
      </div>
    </div>
  );
});

MethodSubNode.displayName = "MethodSubNode";
export default MethodSubNode;
