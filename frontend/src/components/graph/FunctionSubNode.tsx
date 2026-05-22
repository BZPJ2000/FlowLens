import { memo } from "react";
import { Handle, Position } from "@xyflow/react";

interface FunctionSubNodeData {
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
const HEADER_H = 28;

const FunctionSubNode = memo(({ data, selected }: { data: FunctionSubNodeData; selected?: boolean }) => {
  const d = data;
  const dimmed = (d.isDimmed || d.parentDimmed) && !selected && !d.isPathHighlighted;
  const opacity = dimmed ? 0.2 : 1;

  const bgColor = d.isPathHighlighted
    ? "rgba(124,58,237,0.10)"
    : d.is_exported
      ? "rgba(34,197,94,0.12)"
      : d.is_async
        ? "rgba(168,85,247,0.10)"
        : "rgba(59,130,246,0.08)";

  const borderColor = d.isPathHighlighted
    ? "#a78bfa"
    : d.is_exported
      ? "#22c55e60"
      : d.is_async
        ? "#a855f760"
        : "#3b82f640";

  const dotColor = d.isPathHighlighted
    ? "#a78bfa"
    : d.is_exported
      ? "#22c55e"
      : d.is_async
        ? "#a855f7"
        : "#60a5fa";

  const paramCount = d.params.length;

  // 计算上下边的多个连接点位置
  const topHandleCount = Math.max(1, Math.ceil(paramCount / 2)); // 上边至少1个点
  const bottomHandleCount = Math.max(1, Math.ceil(paramCount / 2)); // 下边至少1个点

  return (
    <div
      className="relative rounded-md border transition-all duration-300"
      style={{
        background: bgColor,
        borderColor,
        opacity,
        minWidth: 200,
        maxWidth: 320,
        boxShadow: selected
          ? `0 0 10px ${borderColor}`
          : d.isPathHighlighted
            ? "0 0 8px rgba(124,58,237,0.15)"
            : undefined,
      }}
    >
      {/* ── Top handles (multiple connection points) ── */}
      {Array.from({ length: topHandleCount }).map((_, idx) => {
        const totalWidth = 200; // 假设节点宽度
        const spacing = totalWidth / (topHandleCount + 1);
        const leftPos = spacing * (idx + 1);
        return (
          <Handle
            key={`top-${idx}`}
            type="target"
            position={Position.Top}
            id={`top-${idx}`}
            style={{
              background: "#a78bfa",
              width: 7,
              height: 7,
              border: "2px solid #12121c",
              opacity: dimmed ? 0.2 : 1,
              left: `${(leftPos / totalWidth) * 100}%`,
            }}
          />
        );
      })}

      {/* ── Bottom handles (multiple connection points) ── */}
      {Array.from({ length: bottomHandleCount }).map((_, idx) => {
        const totalWidth = 200;
        const spacing = totalWidth / (bottomHandleCount + 1);
        const leftPos = spacing * (idx + 1);
        return (
          <Handle
            key={`bottom-${idx}`}
            type="source"
            position={Position.Bottom}
            id={`bottom-${idx}`}
            style={{
              background: d.return_type && d.return_type !== "unknown" ? "#f59e0b" : "#60a5fa",
              width: 7,
              height: 7,
              border: "2px solid #12121c",
              opacity: dimmed ? 0.2 : 1,
              left: `${(leftPos / totalWidth) * 100}%`,
            }}
          />
        );
      })}

      {/* ── Global call handle (fallback, left top) ── */}
      <Handle
        type="target"
        position={Position.Left}
        id="call"
        title={`call ${d.name}`}
        style={{
          background: "#a78bfa",
          width: 7,
          height: 7,
          border: "2px solid #12121c",
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
            width: 6,
            height: 6,
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
        title={d.return_type !== "unknown" ? `→ ${d.return_type}` : "→"}
        style={{
          background: d.return_type && d.return_type !== "unknown" ? "#f59e0b" : "#60a5fa",
          width: 7,
          height: 7,
          border: "2px solid #12121c",
          opacity: dimmed ? 0.2 : 1,
          top: HEADER_H / 2,
        }}
      />

      {/* ── Header: function name ── */}
      <div
        className="flex items-center gap-1.5 px-2.5 py-1.5 border-b"
        style={{ borderColor: `${borderColor}40` }}
      >
        <span
          className="w-1.5 h-1.5 rounded-full flex-shrink-0"
          style={{ background: dotColor }}
        />
        <span
          className="text-[11px] font-mono font-bold text-[#e2e8f0] truncate"
          title={d.name}
        >
          {d.name}()
        </span>
        {d.is_async && (
          <span className="text-[8px] px-1 py-0.5 rounded bg-purple-500/20 text-purple-400 flex-shrink-0">
            async
          </span>
        )}
        {d.is_exported && (
          <span className="text-[8px] px-1 py-0.5 rounded bg-green-500/20 text-green-400 flex-shrink-0">
            export
          </span>
        )}
      </div>

      {/* ── Body: param rows ── */}
      {paramCount > 0 && (
        <div className="px-2.5 py-1">
          {d.params.map((param) => (
            <div
              key={param.name}
              className="flex items-center gap-1.5 text-[9px]"
              style={{ height: PARAM_ROW_H }}
            >
              <span className="w-1.5 h-1.5 rounded-full flex-shrink-0 bg-blue-500/40" />
              <span className="text-[#e2e8f0] font-mono font-medium">{param.name}</span>
              <span className="text-[#64748b]">:</span>
              <span className="text-[#60a5fa] font-mono">{param.type}</span>
            </div>
          ))}
        </div>
      )}
      {paramCount === 0 && (
        <div className="px-2.5 py-1">
          <div className="text-[8px] text-[#334155] italic">无参数</div>
        </div>
      )}

      {/* ── Return type footer ── */}
      <div
        className="px-2.5 py-1 border-t flex items-center gap-1.5"
        style={{ borderColor: `${borderColor}40` }}
      >
        <span className="text-[7px] text-[#64748b] font-semibold">OUT</span>
        <span className="text-[9px] text-[#f59e0b] font-mono font-semibold">
          {d.return_type || "unknown"}
        </span>
      </div>
    </div>
  );
});

FunctionSubNode.displayName = "FunctionSubNode";
export default FunctionSubNode;
