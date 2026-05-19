/** Port position calculation and smart edge routing */

import { Position } from "@xyflow/react";

export interface PortPosition {
  /** Vertical position in pixels from the top of the sidebar area */
  topPx: number;
}

/**
 * Compute evenly-spaced vertical port positions within a given sidebar height.
 * Ports are distributed from top to bottom with equal spacing.
 */
export function computePortVerticalPositions(
  count: number,
  totalHeight: number,
  startOffset: number = 8,
): PortPosition[] {
  if (count <= 0) return [];
  const availableH = totalHeight - startOffset * 2;
  if (availableH <= 0) return Array.from({ length: count }, () => ({ topPx: startOffset }));
  const spacing = availableH / Math.max(count, 1);
  return Array.from({ length: count }, (_, i) => ({
    topPx: startOffset + spacing * i + spacing / 2,
  }));
}

/**
 * Given source and target node positions + sizes, determine the best
 * connection sides to minimize edge length and avoid overlaps.
 *
 * Logic: compare dx vs dy between node centers.
 * - |dy| > |dx| → vertical connection (Bottom→Top or Top→Bottom)
 * - |dx| >= |dy| → horizontal connection (Right→Left or Left→Right)
 */
export function getBestConnectionSide(
  srcX: number, srcY: number, srcW: number, srcH: number,
  tgtX: number, tgtY: number, tgtW: number, tgtH: number,
): { sourceSide: Position; targetSide: Position } {
  const srcCenterX = srcX + srcW / 2;
  const srcCenterY = srcY + srcH / 2;
  const tgtCenterX = tgtX + tgtW / 2;
  const tgtCenterY = tgtY + tgtH / 2;

  const dx = tgtCenterX - srcCenterX;
  const dy = tgtCenterY - srcCenterY;

  if (Math.abs(dy) > Math.abs(dx)) {
    // Vertical connection
    if (dy > 0) {
      return { sourceSide: Position.Bottom, targetSide: Position.Top };
    } else {
      return { sourceSide: Position.Top, targetSide: Position.Bottom };
    }
  } else {
    // Horizontal connection
    if (dx > 0) {
      return { sourceSide: Position.Right, targetSide: Position.Left };
    } else {
      return { sourceSide: Position.Left, targetSide: Position.Right };
    }
  }
}

export const PORT_HANDLE_SIZE = 10;
export const PORT_ROW_HEIGHT = 28; // height per port row in sidebar
export const SIDEBAR_MIN_W = 130;   // minimum sidebar width
export const SIDEBAR_PADDING = 10;
