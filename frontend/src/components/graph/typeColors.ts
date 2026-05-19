/** Data type → color mapping for port dots and edge styling (ComfyUI/DEBUG style) */

export interface TypeColors {
  dot: string;
  text: string;
  bg: string;
  border: string;
}

const TYPE_COLOR_MAP: Record<string, TypeColors> = {
  string:   { dot: "#60a5fa", text: "#93c5fd", bg: "rgba(96,165,250,0.12)",  border: "rgba(96,165,250,0.25)" },
  number:   { dot: "#34d399", text: "#6ee7b7", bg: "rgba(52,211,153,0.12)",  border: "rgba(52,211,153,0.25)" },
  boolean:  { dot: "#f59e0b", text: "#fcd34d", bg: "rgba(245,158,11,0.12)",  border: "rgba(245,158,11,0.25)" },
  bool:     { dot: "#f59e0b", text: "#fcd34d", bg: "rgba(245,158,11,0.12)",  border: "rgba(245,158,11,0.25)" },
  object:   { dot: "#a78bfa", text: "#c4b5fd", bg: "rgba(167,139,250,0.12)", border: "rgba(167,139,250,0.25)" },
  function: { dot: "#f472b6", text: "#f9a8d4", bg: "rgba(244,114,182,0.12)", border: "rgba(244,114,182,0.25)" },
  Promise:  { dot: "#38bdf8", text: "#7dd3fc", bg: "rgba(56,189,248,0.12)",  border: "rgba(56,189,248,0.25)" },
  array:    { dot: "#fb923c", text: "#fdba74", bg: "rgba(251,146,60,0.12)",  border: "rgba(251,146,60,0.25)" },
  void:     { dot: "#6b7280", text: "#9ca3af", bg: "rgba(107,114,128,0.12)", border: "rgba(107,114,128,0.20)" },
  null:     { dot: "#6b7280", text: "#9ca3af", bg: "rgba(107,114,128,0.12)", border: "rgba(107,114,128,0.20)" },
  undefined:{ dot: "#6b7280", text: "#9ca3af", bg: "rgba(107,114,128,0.12)", border: "rgba(107,114,128,0.20)" },
  any:      { dot: "#6b7280", text: "#9ca3af", bg: "rgba(107,114,128,0.12)", border: "rgba(107,114,128,0.20)" },
  unknown:  { dot: "#6b7280", text: "#9ca3af", bg: "rgba(107,114,128,0.12)", border: "rgba(107,114,128,0.20)" },
};

const DEFAULT_COLORS: TypeColors = TYPE_COLOR_MAP.unknown;

/** Extract the base type from a complex type string like "Promise<User>" → "Promise" */
export function extractBaseType(dataType: string): string {
  if (!dataType) return "unknown";
  // Strip generics: Promise<User> → Promise
  const base = dataType.replace(/<.*/, "").trim();
  return base || dataType;
}

/** Get color scheme for a data type */
export function getTypeColor(dataType: string): TypeColors {
  if (!dataType || dataType === "unknown") return DEFAULT_COLORS;
  const base = extractBaseType(dataType);
  // Direct match
  if (TYPE_COLOR_MAP[base]) return TYPE_COLOR_MAP[base];
  // Case-insensitive
  const lower = base.toLowerCase();
  for (const [key, val] of Object.entries(TYPE_COLOR_MAP)) {
    if (key.toLowerCase() === lower) return val;
  }
  return DEFAULT_COLORS;
}

/** Get edge stroke color based on data type */
export function getEdgeColor(dataType: string, isDimmed: boolean, isHighlighted: boolean): string {
  if (isHighlighted) return "#a78bfa";
  if (isDimmed) return "#1a1a2e";
  return getTypeColor(dataType).dot;
}
