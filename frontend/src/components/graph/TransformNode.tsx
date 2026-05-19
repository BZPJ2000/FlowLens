import { memo } from "react";
import { Handle, Position } from "@xyflow/react";
import type { NodeProps } from "@xyflow/react";

interface TransformData {
  name: string;
  file_name: string;
  architecture_role?: string;
  is_exported?: boolean;
  is_async?: boolean;
  isDimmed?: boolean;
  isSelected?: boolean;
  isPathHighlighted?: boolean;
}

const ROLE_COLORS: Record<string, string> = {
  controller: "#22c55e", service: "#3b82f6", model: "#eab308",
  view: "#a855f7", util: "#6b7280", config: "#f97316",
  middleware: "#ef4444", hook: "#ec4899", store: "#06b6d4",
  route: "#84cc16", type: "#14b8a6",
};

const TransformNode = memo(({ data, selected }: NodeProps) => {
  const d = data as unknown as TransformData;
  const dimmed = d.isDimmed && !selected && !d.isPathHighlighted;
  const opacity = dimmed ? 0.2 : 1;

  const roleColor = ROLE_COLORS[d.architecture_role || ""] || "#475569";

  const borderColor = d.isPathHighlighted
    ? "#a78bfa"
    : selected
      ? roleColor
      : d.is_exported
        ? "#22c55e60"
        : "#3b82f640";

  const bgColor = d.isPathHighlighted
    ? "rgba(124,58,237,0.1)"
    : selected
      ? "rgba(59,130,246,0.08)"
      : "rgba(10,10,16,0.9)";

  return (
    <div
      className="relative rounded-lg border transition-all duration-200"
      style={{
        background: bgColor,
        borderColor,
        opacity,
        minWidth: 160,
        boxShadow: selected
          ? `0 0 12px ${roleColor}30`
          : d.isPathHighlighted
            ? "0 0 8px rgba(124,58,237,0.12)"
            : "0 2px 8px rgba(0,0,0,0.3)",
      }}
    >
      {/* Input handle (top) */}
      <Handle
        type="target"
        position={Position.Top}
        id="in"
        style={{
          background: "#a78bfa",
          width: 8,
          height: 8,
          border: "2px solid #12121c",
          opacity: dimmed ? 0.2 : 1,
        }}
      />

      {/* Content */}
      <div className="px-3 py-2">
        <div className="flex items-center gap-1.5">
          {d.is_async && (
            <span className="text-[7px] px-1 py-0.5 rounded bg-purple-500/15 text-purple-400 font-semibold">async</span>
          )}
          <span className="text-[11px] font-mono font-semibold text-[#e2e8f0]">
            {d.name}()
          </span>
          {d.is_exported && (
            <span className="text-[7px] px-1 py-0.5 rounded bg-green-500/15 text-green-400 font-semibold flex-shrink-0">export</span>
          )}
        </div>
        <div className="flex items-center gap-1.5 mt-1">
          <span
            className="w-1.5 h-1.5 rounded-full flex-shrink-0"
            style={{ background: roleColor }}
          />
          <span className="text-[9px] text-[#6b7280] font-mono truncate">
            {d.file_name}
          </span>
        </div>
      </div>

      {/* Output handle (bottom) */}
      <Handle
        type="source"
        position={Position.Bottom}
        id="out"
        style={{
          background: "#f59e0b",
          width: 8,
          height: 8,
          border: "2px solid #12121c",
          opacity: dimmed ? 0.2 : 1,
        }}
      />
    </div>
  );
});

TransformNode.displayName = "TransformNode";
export default TransformNode;
