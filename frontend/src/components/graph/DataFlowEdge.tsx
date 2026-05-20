import { memo } from "react";
import { BaseEdge, EdgeLabelRenderer, getSmoothStepPath, Position, type EdgeProps } from "@xyflow/react";
import { getTypeColor } from "./typeColors";

function getSameSidePath(
  sourceX: number,
  sourceY: number,
  targetX: number,
  targetY: number,
  side: Position,
  laneOffset: number,
): [string, number, number] {
  const laneGap = Math.max(18, 36 + laneOffset);
  if (side === Position.Left) {
    const laneX = Math.min(sourceX, targetX) - laneGap;
    return [
      `M ${sourceX},${sourceY} L ${laneX},${sourceY} L ${laneX},${targetY} L ${targetX},${targetY}`,
      laneX,
      (sourceY + targetY) / 2,
    ];
  }
  if (side === Position.Right) {
    const laneX = Math.max(sourceX, targetX) + laneGap;
    return [
      `M ${sourceX},${sourceY} L ${laneX},${sourceY} L ${laneX},${targetY} L ${targetX},${targetY}`,
      laneX,
      (sourceY + targetY) / 2,
    ];
  }
  if (side === Position.Top) {
    const laneY = Math.min(sourceY, targetY) - laneGap;
    return [
      `M ${sourceX},${sourceY} L ${sourceX},${laneY} L ${targetX},${laneY} L ${targetX},${targetY}`,
      (sourceX + targetX) / 2,
      laneY,
    ];
  }
  const laneY = Math.max(sourceY, targetY) + laneGap;
  return [
    `M ${sourceX},${sourceY} L ${sourceX},${laneY} L ${targetX},${laneY} L ${targetX},${targetY}`,
    (sourceX + targetX) / 2,
    laneY,
  ];
}

const DataFlowEdge = memo((props: EdgeProps) => {
  const {
    sourceX, sourceY, targetX, targetY,
    sourcePosition, targetPosition,
    data, selected, id,
  } = props;

  const d = (data || {}) as {
    variable_name?: string;
    data_type?: string;
    label?: string;
    edge_type?: string;
    animating?: boolean;
    isDimmed?: boolean;
    isPathHighlighted?: boolean;
    sourceSide?: Position;
    targetSide?: Position;
    edgeOffsetX?: number;
    edgeOffsetY?: number;
  };

  const dimmed = d.isDimmed && !selected && !d.isPathHighlighted;
  const offsetX = d.edgeOffsetX || 0;
  const offsetY = d.edgeOffsetY || 0;
  const srcSide = d.sourceSide || sourcePosition;
  const tgtSide = d.targetSide || targetPosition;
  const sameSide = srcSide === tgtSide;
  const routed = sameSide
    ? getSameSidePath(
      sourceX,
      sourceY,
      targetX,
      targetY,
      srcSide,
      srcSide === Position.Left || srcSide === Position.Right ? offsetX : offsetY,
    )
    : null;

  if (dimmed) {
    return (
      <BaseEdge
        path={routed ? routed[0] : getSmoothStepPath({
          sourceX: sourceX + offsetX, sourceY: sourceY + offsetY, sourcePosition: srcSide,
          targetX: targetX + offsetX, targetY: targetY + offsetY, targetPosition: tgtSide,
        })[0]}
        style={{ strokeWidth: 1, stroke: "#1a1a2e", opacity: 0.2 }}
        id={id}
      />
    );
  }

  const tc = getTypeColor(d.data_type || "unknown");
  const isCallEdge = d.edge_type === "call";
  const isInternalEdge = d.edge_type === "port_to_function" || d.edge_type === "function_to_port";
  const edgeColor = d.isPathHighlighted
    ? "#a78bfa"
    : isCallEdge
      ? "#f59e0b"
      : isInternalEdge
        ? "#4b5563"
        : tc.dot;
  const flowColor = d.isPathHighlighted
    ? "#c4b5fd"
    : isCallEdge
      ? "#fbbf24"
      : isInternalEdge
        ? "#6b7280"
        : tc.text;
  const strokeWidth = isInternalEdge ? 2 : selected ? 5 : 3.5;

  const [edgePath, labelX, labelY] = routed || getSmoothStepPath({
    sourceX: sourceX + offsetX, sourceY: sourceY + offsetY, sourcePosition: srcSide,
    targetX: targetX + offsetX, targetY: targetY + offsetY, targetPosition: tgtSide,
    borderRadius: 12,
  });

  const animating = d.animating !== false;
  const varName = d.variable_name || "";
  const dataType = d.data_type || "";

  return (
    <>
      {/* Glow */}
      <BaseEdge
        path={edgePath}
        style={{ strokeWidth: strokeWidth + 4, stroke: edgeColor, opacity: 0.08 }}
      />
      {/* Main line */}
      <BaseEdge
        path={edgePath}
        style={{
          strokeWidth,
          stroke: edgeColor,
          opacity: d.isPathHighlighted ? 0.8 : isInternalEdge ? 0.4 : 0.7,
          strokeDasharray: isCallEdge ? "6 4" : undefined,
          transition: "stroke 0.3s",
        }}
        id={id}
      />
      {/* Flow animation */}
      {animating && (
        <path
          d={edgePath}
          fill="none"
          stroke={flowColor}
          strokeWidth={2.5}
          strokeDasharray="8 10"
          className="edge-flow-animated"
          style={{ opacity: d.isPathHighlighted ? 0.9 : 0.6 }}
        />
      )}
      {/* Label — show variable name + type */}
      {(varName || dataType) && (
        <EdgeLabelRenderer>
          <div
            className="absolute pointer-events-none"
            style={{ transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)` }}
          >
            <div
              className="flex items-center gap-1.5 px-2 py-1 rounded-md font-mono whitespace-nowrap shadow-lg"
              style={{
                background: "rgba(10,10,20,0.92)",
                borderColor: tc.border,
                borderWidth: 1,
              }}
            >
              {/* Variable name — the primary thing */}
              {varName && (
                <span className="text-[10px] font-semibold text-[#e2e8f0]">
                  {varName}
                </span>
              )}
              {/* Separator */}
              {varName && dataType && (
                <span className="text-[9px] text-[#4b5563]">:</span>
              )}
              {/* Data type badge */}
              {dataType && (
                <span
                  className="text-[9px] px-1 py-0.5 rounded"
                  style={{ background: tc.bg, color: tc.text, border: `1px solid ${tc.border}` }}
                >
                  {dataType}
                </span>
              )}
            </div>
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
});

DataFlowEdge.displayName = "DataFlowEdge";
export default DataFlowEdge;
