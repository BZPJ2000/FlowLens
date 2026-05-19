import { memo } from "react";
import type { NodeProps } from "@xyflow/react";

interface MethodMeta {
  id: string;
  name: string;
  params: { name: string; type: string }[];
  return_type: string;
  is_exported: boolean;
  is_async: boolean;
}

interface ClassGroupData {
  name: string;
  is_exported: boolean;
  methods: MethodMeta[];
  isDimmed?: boolean;
  parentDimmed?: boolean;
  width: number;
  height: number;
}

const ClassGroupNode = memo(({ data, selected }: NodeProps) => {
  const d = data as unknown as ClassGroupData;
  const dimmed = (d.isDimmed || d.parentDimmed) && !selected;
  const opacity = dimmed ? 0.25 : 1;

  const borderColor = d.is_exported ? "#22c55e50" : "#f59e0b40";

  return (
    <div
      className="relative rounded-lg border-2 border-dashed transition-all duration-300"
      style={{
        width: d.width,
        minHeight: d.height,
        borderColor: selected ? "#f59e0b" : dimmed ? "#1a1a2e" : borderColor,
        background: selected
          ? "rgba(245,158,11,0.04)"
          : "rgba(10,10,16,0.8)",
        opacity,
        boxShadow: selected ? "0 0 12px rgba(245,158,11,0.15)" : "none",
      }}
    >
      {/* Class header */}
      <div
        className="flex items-center gap-1.5 px-2.5 py-1.5 border-b rounded-t-lg"
        style={{
          borderColor: `${borderColor}20`,
          background: selected
            ? "rgba(245,158,11,0.08)"
            : "rgba(15,15,25,0.8)",
        }}
      >
        <span className="text-[9px] font-bold text-[#f59e0b] font-mono">class</span>
        <span className="text-[11px] font-semibold text-[#e2e8f0] truncate font-mono">
          {d.name}
        </span>
        {d.is_exported && (
          <span className="text-[7px] px-1 py-0.5 rounded bg-green-500/20 text-green-400 flex-shrink-0">
            export
          </span>
        )}
      </div>

      {/* Methods are rendered as child ReactFlow nodes (methodSub) inside this container */}
    </div>
  );
});

ClassGroupNode.displayName = "ClassGroupNode";
export default ClassGroupNode;
