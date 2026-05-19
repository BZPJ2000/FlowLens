import { memo } from "react";
import type { NodeProps } from "@xyflow/react";

interface FolderGroupData {
  folder_path: string;
  folder_name: string;
  file_count: number;
  width: number;
  height: number;
  isDimmed?: boolean;
  isSelected?: boolean;
}

const FolderGroupNode = memo(({ data, selected }: NodeProps) => {
  const d = data as unknown as FolderGroupData;
  const dimmed = d.isDimmed && !selected;
  const opacity = dimmed ? 0.3 : 1;

  return (
    <div
      className="relative rounded-2xl border transition-all duration-300"
      style={{
        width: d.width,
        minHeight: d.height,
        borderColor: selected
          ? "#7c3aed60"
          : dimmed
            ? "#1a1a2e"
            : "#2a2a4a",
        background: selected
          ? "rgba(124,58,237,0.04)"
          : dimmed
            ? "rgba(6,6,10,0.3)"
            : "rgba(10,10,20,0.7)",
        backdropFilter: "blur(12px)",
        opacity,
        boxShadow: selected
          ? "0 0 30px rgba(124,58,237,0.1), inset 0 0 30px rgba(124,58,237,0.02)"
          : dimmed
            ? "none"
            : "0 4px 24px rgba(0,0,0,0.3)",
      }}
    >
      {/* Title bar */}
      <div
        className="flex items-center gap-2 px-4 py-3 border-b rounded-t-2xl"
        style={{
          borderColor: dimmed ? "#1a1a2e" : "#2a2a4a",
          background: selected
            ? "rgba(124,58,237,0.08)"
            : "rgba(15,15,30,0.8)",
        }}
      >
        {/* Folder icon */}
        <svg
          className="w-4 h-4 flex-shrink-0"
          viewBox="0 0 24 24"
          fill="none"
          stroke={selected ? "#a78bfa" : "#6b7280"}
          strokeWidth="1.5"
        >
          <path d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6.465a1 1 0 01-.832-.445L10.465 4.555A1 1 0 009.633 4H5a2 2 0 00-2 2v1z" />
        </svg>

        <span
          className="text-xs font-semibold text-[#a1a1aa] truncate flex-1 font-mono"
          title={d.folder_path}
        >
          {d.folder_name}
        </span>

        <span className="text-[10px] px-2 py-0.5 rounded-full bg-[#1a1a2e] text-[#6b7280] flex-shrink-0">
          {d.file_count} file{d.file_count !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Child files are rendered by ReactFlow compound node mechanism */}
    </div>
  );
});

FolderGroupNode.displayName = "FolderGroupNode";
export default FolderGroupNode;
