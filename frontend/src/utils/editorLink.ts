/**
 * 编辑器 Deep Link 工具 — 一键在 VS Code/Cursor/WebStorm/Zed 中打开文件
 *
 * 支持的编辑器 URL schemes:
 * - VS Code: vscode://file/{path}:{line}:{column}
 * - Cursor: cursor://file/{path}:{line}:{column}
 * - WebStorm: webstorm://open?file={path}&line={line}
 * - Zed: zed://file/{path}:{line}:{column}
 * - Sublime: subl://open?url=file://{path}&line={line}&column={column}
 */

export type EditorType = "vscode" | "cursor" | "webstorm" | "zed" | "sublime";

export interface EditorConfig {
  name: string;
  scheme: string;
  icon: string;
}

export const EDITORS: Record<EditorType, EditorConfig> = {
  vscode: { name: "VS Code", scheme: "vscode", icon: "📝" },
  cursor: { name: "Cursor", scheme: "cursor", icon: "✨" },
  webstorm: { name: "WebStorm", scheme: "webstorm", icon: "🌊" },
  zed: { name: "Zed", scheme: "zed", icon: "⚡" },
  sublime: { name: "Sublime", scheme: "subl", icon: "🎨" },
};

/**
 * 生成编辑器 deep link URL
 * @param editor 编辑器类型
 * @param filePath 文件路径（相对或绝对）
 * @param line 行号（可选，从 1 开始）
 * @param column 列号（可选，从 1 开始）
 */
export function generateEditorUrl(
  editor: EditorType,
  filePath: string,
  line: number = 1,
  column: number = 1,
): string {
  // 移除前导 ./ 或 /
  const cleanPath = filePath.replace(/^\.?\//, "");

  switch (editor) {
    case "vscode":
    case "cursor":
    case "zed":
      return `${EDITORS[editor].scheme}://file/${cleanPath}:${line}:${column}`;

    case "webstorm":
      return `${EDITORS[editor].scheme}://open?file=${encodeURIComponent(cleanPath)}&line=${line}`;

    case "sublime":
      return `${EDITORS[editor].scheme}://open?url=file://${encodeURIComponent(cleanPath)}&line=${line}&column=${column}`;

    default:
      return `vscode://file/${cleanPath}:${line}:${column}`;
  }
}

/**
 * 打开文件在编辑器中
 */
export function openInEditor(
  editor: EditorType,
  filePath: string,
  line?: number,
  column?: number,
): void {
  const url = generateEditorUrl(editor, filePath, line, column);
  window.location.href = url;
}

/**
 * 从 localStorage 获取用户偏好的编辑器
 */
export function getPreferredEditor(): EditorType {
  const stored = localStorage.getItem("preferredEditor");
  if (stored && stored in EDITORS) {
    return stored as EditorType;
  }
  return "vscode"; // 默认 VS Code
}

/**
 * 保存用户偏好的编辑器
 */
export function setPreferredEditor(editor: EditorType): void {
  localStorage.setItem("preferredEditor", editor);
}
