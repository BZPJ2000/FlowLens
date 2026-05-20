import { useState, useMemo, useCallback } from "react";
import {
  ArrowLeft, FolderOpen, FileCode, Search, X,
  ChevronRight, ChevronDown, RefreshCw, Loader2,
  Filter, SortAsc, SortDesc,
} from "lucide-react";
import { useGraphStore } from "../stores/graphStore";
import { api } from "../api/client";
import type { GraphNode } from "../types";

interface ParsingEnginePageProps {
  onBack: () => void;
}

type SortField = "name" | "language" | "functions" | "classes" | "ports";
type SortDir = "asc" | "desc";

/** Language badge color map */
const LANG_COLORS: Record<string, string> = {
  typescript: "#3178c6",
  javascript: "#f7df1e",
  python: "#3776ab",
  java: "#ed8b00",
  go: "#00add8",
  rust: "#dea584",
  cpp: "#00599c",
  c: "#a8b9cc",
  csharp: "#239120",
  ruby: "#cc342d",
  php: "#777bb4",
  swift: "#fa7343",
  kotlin: "#7f52ff",
  vue: "#42b883",
  svelte: "#ff3e00",
};

interface FolderTree {
  name: string;
  path: string;
  files: GraphNode[];
  children: FolderTree[];
}

function buildTree(nodes: GraphNode[]): FolderTree {
  const root: FolderTree = { name: "(root)", path: "", files: [], children: [] };
  const map = new Map<string, FolderTree>();
  map.set("", root);

  for (const node of nodes) {
    const folder = node.folder_path || "";
    if (!map.has(folder)) {
      // Create intermediate folders
      const parts = folder.replace(/\\/g, "/").split("/").filter(Boolean);
      let current = "";
      for (const part of parts) {
        const parent = current;
        current = current ? `${current}/${part}` : part;
        if (!map.has(current)) {
          const entry: FolderTree = { name: part, path: current, files: [], children: [] };
          map.set(current, entry);
          const parentNode = map.get(parent) || root;
          parentNode.children.push(entry);
        }
      }
    }
    map.get(folder)!.files.push(node);
  }
  return root;
}

export default function ParsingEnginePage({ onBack }: ParsingEnginePageProps) {
  const graph = useGraphStore((s) => s.graph);
  const analysisId = useGraphStore((s) => s.analysisId);
  const nodes = graph?.nodes || [];

  const [search, setSearch] = useState("");
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set([""]));
  const [sortField, setSortField] = useState<SortField>("name");
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const [langFilter, setLangFilter] = useState<string>("");
  const [reanalyzing, setReanalyzing] = useState(false);
  const [selectedFile, setSelectedFile] = useState<GraphNode | null>(null);

  // Stats
  const stats = useMemo(() => {
    const langs = new Map<string, number>();
    let totalFns = 0, totalClasses = 0, totalPorts = 0;
    for (const n of nodes) {
      langs.set(n.language, (langs.get(n.language) || 0) + 1);
      totalFns += n.functions?.length || 0;
      totalClasses += n.classes?.length || 0;
      totalPorts += n.ports?.length || 0;
    }
    return { langs, totalFns, totalClasses, totalPorts, totalFiles: nodes.length };
  }, [nodes]);

  // Filtered + sorted nodes
  const filteredNodes = useMemo(() => {
    let result = [...nodes];
    if (search) {
      const q = search.toLowerCase();
      result = result.filter(
        (n) =>
          n.file_name.toLowerCase().includes(q) ||
          n.file_path.toLowerCase().includes(q) ||
          n.summary.toLowerCase().includes(q)
      );
    }
    if (langFilter) {
      result = result.filter((n) => n.language === langFilter);
    }
    result.sort((a, b) => {
      let cmp = 0;
      switch (sortField) {
        case "name": cmp = a.file_name.localeCompare(b.file_name); break;
        case "language": cmp = a.language.localeCompare(b.language); break;
        case "functions": cmp = (a.functions?.length || 0) - (b.functions?.length || 0); break;
        case "classes": cmp = (a.classes?.length || 0) - (b.classes?.length || 0); break;
        case "ports": cmp = (a.ports?.length || 0) - (b.ports?.length || 0); break;
      }
      return sortDir === "asc" ? cmp : -cmp;
    });
    return result;
  }, [nodes, search, langFilter, sortField, sortDir]);

  const tree = useMemo(() => buildTree(filteredNodes), [filteredNodes]);

  const toggleFolder = useCallback((path: string) => {
    setExpandedFolders((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  }, []);

  const handleReanalyze = useCallback(async () => {
    if (!analysisId || reanalyzing) return;
    setReanalyzing(true);
    try {
      await fetch(`/api/v1/analyses/${analysisId}/reanalyze`, { method: "POST" });
    } catch { /* ignore */ }
    finally { setReanalyzing(false); }
  }, [analysisId, reanalyzing]);

  const toggleSort = (field: SortField) => {
    if (sortField === field) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else { setSortField(field); setSortDir("asc"); }
  };

  return (
    <div className="w-full h-full flex flex-col bg-[#06060a] text-[#f5f5f7]">
      {/* Header */}
      <div className="flex-shrink-0 h-10 bg-[#0a0a10] border-b border-[#1e1e3a] flex items-center justify-between px-4">
        <div className="flex items-center gap-3">
          <button onClick={onBack} className="flex items-center gap-1 text-xs text-[#a1a1aa] hover:text-[#f5f5f7] transition-colors">
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Back</span>
          </button>
          <span className="text-xs font-bold tracking-tight">Parsing Engine</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleReanalyze}
            disabled={reanalyzing}
            className="flex items-center gap-1 text-[10px] px-2 py-1 rounded border border-[#1e1e3a] bg-[#12121c] text-[#a1a1aa] hover:text-[#f5f5f7] hover:border-[#7c3aed]/40 disabled:opacity-40 transition-all"
          >
            {reanalyzing ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
            Re-analyze
          </button>
        </div>
      </div>

      {/* Stats bar */}
      <div className="flex-shrink-0 px-4 py-2 border-b border-[#1e1e3a] flex items-center gap-4 text-[10px] text-[#6b7280] bg-[#0a0a10]">
        <span>Files: <span className="text-[#a1a1aa] font-mono">{stats.totalFiles}</span></span>
        <span>Functions: <span className="text-[#a1a1aa] font-mono">{stats.totalFns}</span></span>
        <span>Classes: <span className="text-[#a1a1aa] font-mono">{stats.totalClasses}</span></span>
        <span>Ports: <span className="text-[#a1a1aa] font-mono">{stats.totalPorts}</span></span>
        <span className="ml-auto flex items-center gap-2">
          {Array.from(stats.langs.entries()).slice(0, 5).map(([lang, count]) => (
            <span key={lang} className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full" style={{ backgroundColor: LANG_COLORS[lang] || "#6b7280" }} />
              <span className="text-[#a1a1aa]">{lang}</span>
              <span className="font-mono">{count}</span>
            </span>
          ))}
        </span>
      </div>

      {/* Toolbar */}
      <div className="flex-shrink-0 px-4 py-2 border-b border-[#1e1e3a] flex items-center gap-2 bg-[#0a0a10]">
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3 h-3 text-[#4b5563]" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Filter files..."
            className="w-full bg-[#12121c] border border-[#1e1e3a] rounded pl-7 pr-7 py-1 text-[11px] text-[#f5f5f7] placeholder-[#4b5563] focus:outline-none focus:border-[#7c3aed]/50"
          />
          {search && (
            <button onClick={() => setSearch("")} className="absolute right-2 top-1/2 -translate-y-1/2 text-[#4b5563] hover:text-[#a1a1aa]">
              <X className="w-3 h-3" />
            </button>
          )}
        </div>
        <div className="flex items-center gap-1">
          <Filter className="w-3 h-3 text-[#4b5563]" />
          <select
            value={langFilter}
            onChange={(e) => setLangFilter(e.target.value)}
            className="bg-[#12121c] border border-[#1e1e3a] rounded px-2 py-1 text-[10px] text-[#a1a1aa] focus:outline-none"
          >
            <option value="">All languages</option>
            {Array.from(stats.langs.keys()).sort().map((l) => (
              <option key={l} value={l}>{l}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 flex overflow-hidden">
        {/* File tree */}
        <div className="w-72 flex-shrink-0 border-r border-[#1e1e3a] overflow-y-auto p-2">
          <FolderNode folder={tree} depth={0} expanded={expandedFolders} onToggle={toggleFolder} onSelect={setSelectedFile} selected={selectedFile} />
        </div>

        {/* File detail / table */}
        <div className="flex-1 overflow-y-auto">
          {selectedFile ? (
            <FileDetail node={selectedFile} onClose={() => setSelectedFile(null)} />
          ) : (
            <FileTable nodes={filteredNodes} sortField={sortField} sortDir={sortDir} onSort={toggleSort} onSelect={setSelectedFile} />
          )}
        </div>
      </div>
    </div>
  );
}

// ── Sub-components ──────────────────────────────

interface FolderNodeProps {
  folder: FolderTree;
  depth: number;
  expanded: Set<string>;
  onToggle: (path: string) => void;
  onSelect: (node: GraphNode) => void;
  selected: GraphNode | null;
}

function FolderNode({ folder, depth, expanded, onToggle, onSelect, selected }: FolderNodeProps) {
  const isOpen = expanded.has(folder.path);
  const hasContent = folder.files.length > 0 || folder.children.length > 0;

  return (
    <div>
      {folder.name !== "(root)" && (
        <button
          onClick={() => onToggle(folder.path)}
          className="w-full flex items-center gap-1 py-0.5 px-1 rounded text-[11px] text-[#a1a1aa] hover:bg-[#1e1e3a]/50 transition-colors"
          style={{ paddingLeft: `${depth * 12 + 4}px` }}
        >
          {hasContent ? (
            isOpen ? <ChevronDown className="w-3 h-3 flex-shrink-0" /> : <ChevronRight className="w-3 h-3 flex-shrink-0" />
          ) : <span className="w-3" />}
          <FolderOpen className="w-3 h-3 text-[#7c3aed]/60 flex-shrink-0" />
          <span className="truncate">{folder.name}</span>
          <span className="ml-auto text-[9px] text-[#4b5563] font-mono">{folder.files.length}</span>
        </button>
      )}
      {(isOpen || folder.name === "(root)") && (
        <>
          {folder.children.map((child) => (
            <FolderNode key={child.path} folder={child} depth={depth + 1} expanded={expanded} onToggle={onToggle} onSelect={onSelect} selected={selected} />
          ))}
          {folder.files.map((file) => (
            <button
              key={file.id}
              onClick={() => onSelect(file)}
              className={`w-full flex items-center gap-1 py-0.5 px-1 rounded text-[11px] transition-colors ${
                selected?.id === file.id ? "bg-[#7c3aed]/15 text-[#f5f5f7]" : "text-[#6b7280] hover:bg-[#1e1e3a]/50 hover:text-[#a1a1aa]"
              }`}
              style={{ paddingLeft: `${(depth + 1) * 12 + 4}px` }}
            >
              <FileCode className="w-3 h-3 flex-shrink-0" />
              <span className="truncate">{file.file_name}</span>
            </button>
          ))}
        </>
      )}
    </div>
  );
}

interface FileTableProps {
  nodes: GraphNode[];
  sortField: SortField;
  sortDir: SortDir;
  onSort: (field: SortField) => void;
  onSelect: (node: GraphNode) => void;
}

function FileTable({ nodes, sortField, sortDir, onSort, onSelect }: FileTableProps) {
  const SortIcon = sortDir === "asc" ? SortAsc : SortDesc;

  const header = (label: string, field: SortField) => (
    <button
      onClick={() => onSort(field)}
      className={`flex items-center gap-0.5 text-[10px] uppercase tracking-wider ${
        sortField === field ? "text-[#a78bfa]" : "text-[#4b5563]"
      } hover:text-[#a1a1aa]`}
    >
      {label}
      {sortField === field && <SortIcon className="w-2.5 h-2.5" />}
    </button>
  );

  return (
    <div className="p-3">
      <table className="w-full text-[11px]">
        <thead>
          <tr className="border-b border-[#1e1e3a]">
            <th className="text-left py-1.5 px-2">{header("File", "name")}</th>
            <th className="text-left py-1.5 px-2">{header("Language", "language")}</th>
            <th className="text-center py-1.5 px-2">{header("Fns", "functions")}</th>
            <th className="text-center py-1.5 px-2">{header("Classes", "classes")}</th>
            <th className="text-center py-1.5 px-2">{header("Ports", "ports")}</th>
            <th className="text-left py-1.5 px-2 text-[10px] uppercase tracking-wider text-[#4b5563]">Summary</th>
          </tr>
        </thead>
        <tbody>
          {nodes.map((n) => (
            <tr
              key={n.id}
              onClick={() => onSelect(n)}
              className="border-b border-[#1e1e3a]/50 hover:bg-[#1e1e3a]/30 cursor-pointer transition-colors"
            >
              <td className="py-1.5 px-2 text-[#f5f5f7] font-mono truncate max-w-[200px]">{n.file_name}</td>
              <td className="py-1.5 px-2">
                <span className="inline-flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full" style={{ backgroundColor: LANG_COLORS[n.language] || "#6b7280" }} />
                  <span className="text-[#a1a1aa]">{n.language}</span>
                </span>
              </td>
              <td className="py-1.5 px-2 text-center font-mono text-[#a1a1aa]">{n.functions?.length || 0}</td>
              <td className="py-1.5 px-2 text-center font-mono text-[#a1a1aa]">{n.classes?.length || 0}</td>
              <td className="py-1.5 px-2 text-center font-mono text-[#a1a1aa]">{n.ports?.length || 0}</td>
              <td className="py-1.5 px-2 text-[#6b7280] truncate max-w-[250px]">{n.summary}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {nodes.length === 0 && (
        <div className="text-center text-[#4b5563] text-xs py-8">No files match the current filter</div>
      )}
    </div>
  );
}

interface FileDetailProps {
  node: GraphNode;
  onClose: () => void;
}

function FileDetail({ node, onClose }: FileDetailProps) {
  const inputs = node.ports?.filter((p) => p.direction === "input") || [];
  const outputs = node.ports?.filter((p) => p.direction === "output") || [];

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-bold text-[#f5f5f7]">{node.file_name}</h2>
          <p className="text-[10px] text-[#6b7280] font-mono">{node.file_path}</p>
        </div>
        <button onClick={onClose} className="text-[#6b7280] hover:text-[#f5f5f7]">
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Summary */}
      <div className="bg-[#12121c] border border-[#1e1e3a] rounded-lg p-3">
        <p className="text-[11px] text-[#a1a1aa]">{node.summary || "No summary"}</p>
        {node.detail && <p className="text-[10px] text-[#6b7280] mt-1">{node.detail}</p>}
      </div>

      {/* Functions */}
      {node.functions && node.functions.length > 0 && (
        <div>
          <h3 className="text-[10px] uppercase tracking-wider text-[#4b5563] mb-1">Functions ({node.functions.length})</h3>
          <div className="space-y-1">
            {node.functions.map((fn) => (
              <div key={fn.id} className="bg-[#12121c] border border-[#1e1e3a] rounded px-2 py-1 flex items-center gap-2">
                <span className="text-[11px] text-[#a78bfa] font-mono">{fn.name}</span>
                <span className="text-[9px] text-[#4b5563]">
                  ({fn.params.map((p) => `${p.name}: ${p.type}`).join(", ")})
                </span>
                <span className="text-[9px] text-[#6b7280]">→ {fn.return_type}</span>
                {fn.is_async && <span className="text-[8px] bg-[#7c3aed]/20 text-[#a78bfa] px-1 rounded">async</span>}
                {fn.is_exported && <span className="text-[8px] bg-green-500/20 text-green-400 px-1 rounded">export</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Classes */}
      {node.classes && node.classes.length > 0 && (
        <div>
          <h3 className="text-[10px] uppercase tracking-wider text-[#4b5563] mb-1">Classes ({node.classes.length})</h3>
          <div className="space-y-2">
            {node.classes.map((cls) => (
              <div key={cls.id} className="bg-[#12121c] border border-[#1e1e3a] rounded p-2">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-[11px] text-[#f59e0b] font-mono">{cls.name}</span>
                  {cls.is_exported && <span className="text-[8px] bg-green-500/20 text-green-400 px-1 rounded">export</span>}
                </div>
                {cls.methods.length > 0 && (
                  <div className="pl-3 space-y-0.5">
                    {cls.methods.map((m) => (
                      <div key={m.id} className="text-[10px] text-[#6b7280]">
                        <span className="text-[#a1a1aa] font-mono">{m.name}</span>
                        <span className="text-[#4b5563]">({m.params.map((p) => p.name).join(", ")})</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Ports */}
      {(inputs.length > 0 || outputs.length > 0) && (
        <div className="grid grid-cols-2 gap-3">
          <div>
            <h3 className="text-[10px] uppercase tracking-wider text-[#4b5563] mb-1">Inputs ({inputs.length})</h3>
            <div className="space-y-0.5">
              {inputs.slice(0, 15).map((p) => (
                <div key={p.id} className="text-[10px] text-[#6b7280] flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-blue-400/60" />
                  <span className="font-mono text-[#a1a1aa]">{p.name}</span>
                  <span className="text-[#4b5563]">: {p.data_type}</span>
                </div>
              ))}
              {inputs.length > 15 && <span className="text-[9px] text-[#4b5563]">+{inputs.length - 15} more</span>}
            </div>
          </div>
          <div>
            <h3 className="text-[10px] uppercase tracking-wider text-[#4b5563] mb-1">Outputs ({outputs.length})</h3>
            <div className="space-y-0.5">
              {outputs.slice(0, 15).map((p) => (
                <div key={p.id} className="text-[10px] text-[#6b7280] flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-green-400/60" />
                  <span className="font-mono text-[#a1a1aa]">{p.name}</span>
                  <span className="text-[#4b5563]">: {p.data_type}</span>
                </div>
              ))}
              {outputs.length > 15 && <span className="text-[9px] text-[#4b5563]">+{outputs.length - 15} more</span>}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
