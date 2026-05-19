import { memo } from "react";
import { X, Info } from "lucide-react";

const ROLE_COLORS: Record<string, { border: string; label: string }> = {
  controller: { border: "#22c55e", label: "控制器/路由" },
  service:    { border: "#3b82f6", label: "业务逻辑" },
  model:      { border: "#eab308", label: "数据模型" },
  view:       { border: "#a855f7", label: "视图/组件" },
  util:       { border: "#6b7280", label: "工具函数" },
  config:     { border: "#f97316", label: "配置文件" },
  middleware: { border: "#ef4444", label: "中间件" },
  hook:       { border: "#ec4899", label: "钩子/Hook" },
  store:      { border: "#06b6d4", label: "状态管理" },
  route:      { border: "#84cc16", label: "路由定义" },
  type:       { border: "#14b8a6", label: "类型定义" },
  test:       { border: "#8b5cf6", label: "测试" },
  other:      { border: "#475569", label: "其他" },
};

const TYPE_COLORS: Record<string, { hex: string; label: string }> = {
  string:   { hex: "#4ade80", label: "String" },
  number:   { hex: "#60a5fa", label: "Number" },
  boolean:  { hex: "#f59e0b", label: "Boolean" },
  function: { hex: "#c084fc", label: "Function" },
  object:   { hex: "#fb923c", label: "Object" },
  array:    { hex: "#f472b6", label: "Array" },
  Promise:  { hex: "#38bdf8", label: "Promise" },
  unknown:  { hex: "#9ca3af", label: "Unknown" },
};

interface LegendPanelProps {
  visible: boolean;
  onClose: () => void;
}

const LegendPanel = memo(({ visible, onClose }: LegendPanelProps) => {
  if (!visible) return null;

  return (
    <div className="absolute bottom-4 left-4 z-10 animate-fade-in">
      <div className="bg-[#0a0a10]/95 backdrop-blur-md border border-[#1e1e3a] rounded-xl p-4 shadow-2xl min-w-[260px]">
        {/* Header */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Info className="w-3.5 h-3.5 text-[#a1a1aa]" />
            <span className="text-[11px] font-semibold text-[#f5f5f7] uppercase tracking-wider">
              Legend
            </span>
          </div>
          <button
            onClick={onClose}
            className="text-[#6b7280] hover:text-[#f5f5f7] transition-colors"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Node Roles */}
        <div className="mb-3">
          <div className="text-[9px] uppercase tracking-wider text-[#6b7280] mb-2">
            Node Roles
          </div>
          <div className="grid grid-cols-2 gap-x-3 gap-y-1.5">
            {Object.entries(ROLE_COLORS).map(([role, { border, label }]) => (
              <div key={role} className="flex items-center gap-2">
                <span
                  className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                  style={{ background: border }}
                />
                <span className="text-[10px] text-[#a1a1aa]">{label}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Divider */}
        <div className="h-px bg-[#1e1e3a] my-3" />

        {/* Port Types */}
        <div>
          <div className="text-[9px] uppercase tracking-wider text-[#6b7280] mb-2">
            Data Types
          </div>
          <div className="flex flex-wrap gap-2">
            {Object.entries(TYPE_COLORS).map(([type, { hex, label }]) => (
              <div key={type} className="flex items-center gap-1.5">
                <span
                  className="w-2 h-2 rounded-full flex-shrink-0 ring-1 ring-[#12121c]"
                  style={{ background: hex }}
                />
                <span className="text-[10px] text-[#a1a1aa]">{label}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Shortcuts */}
        <div className="h-px bg-[#1e1e3a] my-3" />
        <div className="text-[9px] uppercase tracking-wider text-[#6b7280] mb-2">
          Shortcuts
        </div>
        <div className="space-y-1 text-[10px] text-[#6b7280]">
          <div><kbd className="px-1 py-0.5 rounded bg-[#12121c] border border-[#2a2a4a] text-[#a1a1aa] text-[9px]">Click</kbd> Select node</div>
          <div><kbd className="px-1 py-0.5 rounded bg-[#12121c] border border-[#2a2a4a] text-[#a1a1aa] text-[9px]">Esc</kbd> Deselect all</div>
          <div><kbd className="px-1 py-0.5 rounded bg-[#12121c] border border-[#2a2a4a] text-[#a1a1aa] text-[9px]">Scroll</kbd> Zoom</div>
          <div><kbd className="px-1 py-0.5 rounded bg-[#12121c] border border-[#2a2a4a] text-[#a1a1aa] text-[9px]">Drag</kbd> Pan canvas</div>
        </div>
      </div>
    </div>
  );
});

LegendPanel.displayName = "LegendPanel";
export default LegendPanel;
