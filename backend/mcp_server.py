#!/usr/bin/env python3
"""PoltAIshow MCP Server — 为 Claude/Cursor 提供项目结构上下文

Model Context Protocol (MCP) 服务器，暴露以下工具：
1. get_project_structure - 获取项目文件树和架构概览
2. get_file_analysis - 获取文件详细分析
3. get_dependencies - 获取文件依赖关系
4. analyze_impact - 变更影响分析
5. search_files - 搜索文件
6. get_data_flow - 获取两文件间数据流路径

使用方式:
  python mcp_server.py

在 Claude Desktop 配置 (~/.config/claude/config.json):
{
  "mcpServers": {
    "poltaishow": {
      "command": "python",
      "args": ["/path/to/mcp_server.py"]
    }
  }
}
"""

import asyncio
import json
import sys
from typing import Any

# MCP 协议常量
MCP_VERSION = "0.1.0"

# 工具定义
TOOLS = [
    {
        "name": "get_project_structure",
        "description": "获取项目的文件树和架构概览（文件数、语言分布、架构角色统计）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "analysis_id": {
                    "type": "string",
                    "description": "分析 ID（UUID）",
                }
            },
            "required": ["analysis_id"],
        },
    },
    {
        "name": "get_file_analysis",
        "description": "获取指定文件的详细分析（摘要、输入输出、函数、类、架构角色）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "analysis_id": {"type": "string", "description": "分析 ID"},
                "file_path": {"type": "string", "description": "文件路径"},
            },
            "required": ["analysis_id", "file_path"],
        },
    },
    {
        "name": "get_dependencies",
        "description": "获取文件的依赖关系（导入了哪些文件，被哪些文件导入）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "analysis_id": {"type": "string"},
                "file_path": {"type": "string"},
            },
            "required": ["analysis_id", "file_path"],
        },
    },
    {
        "name": "analyze_impact",
        "description": "分析修改某文件会影响哪些其他文件（传递依赖 + 风险评分 1-10）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "analysis_id": {"type": "string"},
                "file_path": {"type": "string"},
            },
            "required": ["analysis_id", "file_path"],
        },
    },
    {
        "name": "search_files",
        "description": "搜索文件（按文件名、语言、架构角色筛选）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "analysis_id": {"type": "string"},
                "query": {"type": "string", "description": "搜索关键词（文件名）"},
                "language": {"type": "string", "description": "语言过滤（可选）"},
                "role": {"type": "string", "description": "架构角色过滤（可选）"},
            },
            "required": ["analysis_id"],
        },
    },
    {
        "name": "get_data_flow",
        "description": "获取两个文件之间的数据流路径（最短路径 + 中间节点）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "analysis_id": {"type": "string"},
                "from_file": {"type": "string"},
                "to_file": {"type": "string"},
            },
            "required": ["analysis_id", "from_file", "to_file"],
        },
    },
]


class MCPServer:
    def __init__(self):
        self.db_path = "poltaishow.db"  # SQLite 数据库路径

    async def handle_request(self, request: dict) -> dict:
        """处理 JSON-RPC 请求"""
        method = request.get("method")
        params = request.get("params", {})
        req_id = request.get("id")

        try:
            if method == "initialize":
                result = await self.handle_initialize(params)
            elif method == "tools/list":
                result = {"tools": TOOLS}
            elif method == "tools/call":
                result = await self.handle_tool_call(params)
            else:
                return self.error_response(req_id, -32601, f"Method not found: {method}")

            return {"jsonrpc": "2.0", "id": req_id, "result": result}

        except Exception as e:
            return self.error_response(req_id, -32603, str(e))

    async def handle_initialize(self, params: dict) -> dict:
        """处理初始化请求"""
        return {
            "protocolVersion": MCP_VERSION,
            "serverInfo": {
                "name": "poltaishow",
                "version": "1.0.0",
            },
            "capabilities": {
                "tools": {},
            },
        }

    async def handle_tool_call(self, params: dict) -> dict:
        """处理工具调用"""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if tool_name == "get_project_structure":
            return await self.get_project_structure(arguments)
        elif tool_name == "get_file_analysis":
            return await self.get_file_analysis(arguments)
        elif tool_name == "get_dependencies":
            return await self.get_dependencies(arguments)
        elif tool_name == "analyze_impact":
            return await self.analyze_impact(arguments)
        elif tool_name == "search_files":
            return await self.search_files(arguments)
        elif tool_name == "get_data_flow":
            return await self.get_data_flow(arguments)
        else:
            raise ValueError(f"Unknown tool: {tool_name}")

    # ── 工具实现 ──────────────────────────────

    async def get_project_structure(self, args: dict) -> dict:
        """获取项目结构"""
        import sqlite3
        analysis_id = args["analysis_id"]

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # 获取分析信息
        cur.execute("SELECT * FROM analyses WHERE id = ?", (analysis_id,))
        analysis = cur.fetchone()
        if not analysis:
            conn.close()
            raise ValueError(f"Analysis not found: {analysis_id}")

        # 获取文件节点
        cur.execute("SELECT file_path, file_name, language, architecture_role FROM file_nodes WHERE analysis_id = ?", (analysis_id,))
        files = [dict(row) for row in cur.fetchall()]

        # 统计
        lang_counts = {}
        role_counts = {}
        for f in files:
            lang_counts[f["language"]] = lang_counts.get(f["language"], 0) + 1
            role = f["architecture_role"] or "other"
            role_counts[role] = role_counts.get(role, 0) + 1

        conn.close()

        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({
                        "total_files": len(files),
                        "languages": lang_counts,
                        "roles": role_counts,
                        "files": files,
                    }, ensure_ascii=False, indent=2),
                }
            ]
        }

    async def get_file_analysis(self, args: dict) -> dict:
        """获取文件详细分析"""
        import sqlite3
        analysis_id = args["analysis_id"]
        file_path = args["file_path"]

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute(
            "SELECT * FROM file_nodes WHERE analysis_id = ? AND file_path = ?",
            (analysis_id, file_path),
        )
        node = cur.fetchone()
        if not node:
            conn.close()
            raise ValueError(f"File not found: {file_path}")

        result = dict(node)
        # 解析 JSON 字段
        result["functions_json"] = json.loads(result.get("functions_json") or "[]")
        result["classes_json"] = json.loads(result.get("classes_json") or "[]")

        conn.close()

        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(result, ensure_ascii=False, indent=2),
                }
            ]
        }

    async def get_dependencies(self, args: dict) -> dict:
        """获取依赖关系"""
        import sqlite3
        analysis_id = args["analysis_id"]
        file_path = args["file_path"]

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # 找到节点 ID
        cur.execute("SELECT id FROM file_nodes WHERE analysis_id = ? AND file_path = ?", (analysis_id, file_path))
        node = cur.fetchone()
        if not node:
            conn.close()
            raise ValueError(f"File not found: {file_path}")
        node_id = node["id"]

        # 导入的文件（该文件依赖谁）
        cur.execute("""
            SELECT fn.file_path, fn.file_name, de.variable_name, de.data_type
            FROM data_edges de
            JOIN file_nodes fn ON de.from_file_id = fn.id
            WHERE de.to_file_id = ? AND de.analysis_id = ?
        """, (node_id, analysis_id))
        imports = [dict(row) for row in cur.fetchall()]

        # 被导入的文件（谁依赖该文件）
        cur.execute("""
            SELECT fn.file_path, fn.file_name, de.variable_name, de.data_type
            FROM data_edges de
            JOIN file_nodes fn ON de.to_file_id = fn.id
            WHERE de.from_file_id = ? AND de.analysis_id = ?
        """, (node_id, analysis_id))
        imported_by = [dict(row) for row in cur.fetchall()]

        conn.close()

        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({
                        "file": file_path,
                        "imports": imports,
                        "imported_by": imported_by,
                    }, ensure_ascii=False, indent=2),
                }
            ]
        }

    async def analyze_impact(self, args: dict) -> dict:
        """变更影响分析"""
        import sqlite3
        from app.core.graph_builder import analyze_impact
        from app.models.schemas import GraphNode, GraphEdge, EdgeType

        analysis_id = args["analysis_id"]
        file_path = args["file_path"]

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # 找到节点 ID
        cur.execute("SELECT id FROM file_nodes WHERE analysis_id = ? AND file_path = ?", (analysis_id, file_path))
        node = cur.fetchone()
        if not node:
            conn.close()
            raise ValueError(f"File not found: {file_path}")
        node_id = str(node["id"])

        # 获取所有节点和边
        cur.execute("SELECT * FROM file_nodes WHERE analysis_id = ?", (analysis_id,))
        nodes_raw = cur.fetchall()
        cur.execute("SELECT * FROM data_edges WHERE analysis_id = ?", (analysis_id,))
        edges_raw = cur.fetchall()
        conn.close()

        nodes = [
            GraphNode(
                id=str(n["id"]),
                file_path=n["file_path"],
                file_name=n["file_name"],
                language=n["language"],
                summary=n["summary"] or "",
                architecture_role=n["architecture_role"] or "",
                functions=[],
                classes=[],
            )
            for n in nodes_raw
        ]
        edges = [
            GraphEdge(
                id=str(e["id"]),
                source_node_id=str(e["from_file_id"]),
                target_node_id=str(e["to_file_id"]),
                variable_name=e["variable_name"] or "",
                data_type=e["data_type"] or "unknown",
                edge_type=EdgeType(e["edge_type"]) if e["edge_type"] else EdgeType.IMPORT,
                label=e["variable_name"] or "",
            )
            for e in edges_raw
        ]

        impact = analyze_impact(node_id, nodes, edges)

        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({
                        "source_file": file_path,
                        "affected_count": len(impact),
                        "affected_files": impact,
                    }, ensure_ascii=False, indent=2),
                }
            ]
        }

    async def search_files(self, args: dict) -> dict:
        """搜索文件"""
        import sqlite3
        analysis_id = args["analysis_id"]
        query = args.get("query", "")
        language = args.get("language")
        role = args.get("role")

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        sql = "SELECT file_path, file_name, language, architecture_role, summary FROM file_nodes WHERE analysis_id = ?"
        params = [analysis_id]

        if query:
            sql += " AND file_name LIKE ?"
            params.append(f"%{query}%")
        if language:
            sql += " AND language = ?"
            params.append(language)
        if role:
            sql += " AND architecture_role = ?"
            params.append(role)

        cur.execute(sql, params)
        results = [dict(row) for row in cur.fetchall()]
        conn.close()

        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({"results": results}, ensure_ascii=False, indent=2),
                }
            ]
        }

    async def get_data_flow(self, args: dict) -> dict:
        """获取数据流路径"""
        import sqlite3
        from collections import deque

        analysis_id = args["analysis_id"]
        from_file = args["from_file"]
        to_file = args["to_file"]

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # 找到节点 ID
        cur.execute("SELECT id, file_path FROM file_nodes WHERE analysis_id = ? AND file_path IN (?, ?)", (analysis_id, from_file, to_file))
        nodes = {row["file_path"]: str(row["id"]) for row in cur.fetchall()}
        if from_file not in nodes or to_file not in nodes:
            conn.close()
            raise ValueError("One or both files not found")

        from_id = nodes[from_file]
        to_id = nodes[to_file]

        # 获取所有边
        cur.execute("SELECT from_file_id, to_file_id FROM data_edges WHERE analysis_id = ?", (analysis_id,))
        edges = [(str(e["from_file_id"]), str(e["to_file_id"])) for e in cur.fetchall()]

        # BFS 找最短路径
        adj = {}
        for src, tgt in edges:
            adj.setdefault(src, []).append(tgt)

        queue = deque([(from_id, [from_id])])
        visited = {from_id}
        path = None

        while queue:
            current, current_path = queue.popleft()
            if current == to_id:
                path = current_path
                break
            for neighbor in adj.get(current, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, current_path + [neighbor]))

        # 转换 ID 为文件路径
        if path:
            cur.execute(f"SELECT id, file_path FROM file_nodes WHERE id IN ({','.join('?' * len(path))})", path)
            id_to_path = {str(row["id"]): row["file_path"] for row in cur.fetchall()}
            path_files = [id_to_path.get(nid, nid) for nid in path]
        else:
            path_files = []

        conn.close()

        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({
                        "from": from_file,
                        "to": to_file,
                        "path": path_files if path_files else "No path found",
                    }, ensure_ascii=False, indent=2),
                }
            ]
        }

    def error_response(self, req_id: Any, code: int, message: str) -> dict:
        """生成错误响应"""
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": code, "message": message},
        }


async def main():
    """MCP 服务器主循环"""
    server = MCPServer()

    # 读取 stdin，处理请求，写入 stdout
    while True:
        try:
            line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
            if not line:
                break

            request = json.loads(line)
            response = await server.handle_request(request)
            print(json.dumps(response), flush=True)

        except json.JSONDecodeError:
            continue
        except Exception as e:
            print(json.dumps({
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32603, "message": str(e)},
            }), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
