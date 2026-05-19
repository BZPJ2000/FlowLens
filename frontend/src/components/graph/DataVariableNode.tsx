import { memo } from "react";
import { Handle, Position } from "@xyflow/react";
import type { NodeProps } from "@xyflow/react";
import { getTypeColor } from "./typeColors";

interface DataVariableData {
  name: string;
  data_type: string;
  isEntry?: boolean;
  isExit?: boolean;
  isDimmed?: boolean;
  isSelected?: boolean;
  isPathHighlighted?: boolean;
}

const DataVariableNode = memo(({ data, selected }: NodeProps) => {
  const d = data as unknown as DataVariableData;
  const tc = getTypeColor(d.data_type);
  const dimmed = d.isDimmed && !selected && !d.isPathHighlighted;
  const opacity = dimmed ? 0.2 : 1;

  const bgColor = d.isPathHighlighted
    ? "rgba(124,58,237,0.15)"
    : selected
      ? tc.bg
      : "rgba(10,10,16,0.9)";

  const borderColor = d.isPathHighlighted
    ? "#a78bfa"
    : selected
      ? tc.dot
      : tc.border;

  return (
    <div
      className="relative rounded-full border transition-all duration-200"
      style={{
        background: bgColor,
        borderColor,
        opacity,
        padding: "6px 14px",
        boxShadow: selected
          ? `0 0 12px ${tc.dot}40`
          : d.isPathHighlighted
            ? "0 0 8px rgba(124,58,237,0.15)"
            : "none",
      }}
    >
      {/* Input handle (top) */}
      <Handle
        type="target"
        position={Position.Top}
        id="in"
        style={{
          background: tc.dot,
          width: 7,
          height: 7,
          border: "2px solid #12121c",
          opacity: dimmed ? 0.2 : 1,
        }}
      />

      {/* Content: dot + name + type tag */}
      <div className="flex items-center gap-2 whitespace-nowrap">
        <span
          className="w-2 h-2 rounded-full flex-shrink-0"
          style={{ background: tc.dot }}
        />
        <span className="text-[11px] font-mono font-semibold text-[#e2e8f0]">
          {d.name}
        </span>
        <span
          className="text-[8px] px-1.5 py-0.5 rounded-full font-mono flex-shrink-0"
          style={{ background: tc.bg, color: tc.text, border: `1px solid ${tc.border}` }}
        >
          {d.data_type}
        </span>
        {d.isEntry && (
          <span className="text-[7px] px-1 rounded bg-green-500/15 text-green-400 font-semibold">IN</span>
        )}
        {d.isExit && (
          <span className="text-[7px] px-1 rounded bg-red-500/15 text-red-400 font-semibold">OUT</span>
        )}
      </div>

      {/* Output handle (bottom) */}
      <Handle
        type="source"
        position={Position.Bottom}
        id="out"
        style={{
          background: tc.dot,
          width: 7,
          height: 7,
          border: "2px solid #12121c",
          opacity: dimmed ? 0.2 : 1,
        }}
      />
    </div>
  );
});

DataVariableNode.displayName = "DataVariableNode";
export default DataVariableNode;
