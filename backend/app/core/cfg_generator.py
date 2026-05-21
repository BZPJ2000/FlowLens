"""函数内部控制流图生成器 — 可视化 if/while/for/switch 分支逻辑

借鉴 Cxx2Flow，为单个函数生成控制流图（CFG）：
- 支持 Python (基于 ast 模块)
- 支持 TypeScript/JavaScript (基于正则匹配)
- 输出 DOT 格式（可用 Graphviz 渲染为 SVG/PNG）

控制流节点类型:
- entry: 函数入口
- exit: 函数出口
- statement: 普通语句
- condition: 条件判断 (if/while/for)
- branch: 分支 (then/else)
"""

import ast
import re
from typing import List, Tuple
from dataclasses import dataclass


@dataclass
class CFGNode:
    """控制流图节点"""
    id: int
    type: str  # entry, exit, statement, condition, branch
    label: str
    line: int = 0


@dataclass
class CFGEdge:
    """控制流图边"""
    from_id: int
    to_id: int
    label: str = ""  # true/false/empty


class ControlFlowGraph:
    """控制流图"""
    def __init__(self):
        self.nodes: List[CFGNode] = []
        self.edges: List[CFGEdge] = []
        self.node_counter = 0

    def add_node(self, node_type: str, label: str, line: int = 0) -> int:
        """添加节点，返回节点 ID"""
        node_id = self.node_counter
        self.node_counter += 1
        self.nodes.append(CFGNode(node_id, node_type, label, line))
        return node_id

    def add_edge(self, from_id: int, to_id: int, label: str = ""):
        """添加边"""
        self.edges.append(CFGEdge(from_id, to_id, label))

    def to_dot(self, function_name: str = "function") -> str:
        """生成 DOT 格式"""
        lines = [
            f"digraph {function_name} {{",
            "  node [shape=box, style=rounded];",
            "  rankdir=TB;",
            "",
        ]

        # 节点
        for node in self.nodes:
            shape = "ellipse" if node.type in ("entry", "exit") else "box"
            if node.type == "condition":
                shape = "diamond"
            label = node.label.replace('"', '\\"').replace('\n', '\\n')
            lines.append(f'  n{node.id} [label="{label}", shape={shape}];')

        lines.append("")

        # 边
        for edge in self.edges:
            label_attr = f' [label="{edge.label}"]' if edge.label else ""
            lines.append(f"  n{edge.from_id} -> n{edge.to_id}{label_attr};")

        lines.append("}")
        return "\n".join(lines)


# ═══════════════════════════════════════════
# Python CFG 生成（基于 ast）
# ═══════════════════════════════════════════

class PythonCFGBuilder(ast.NodeVisitor):
    """Python 函数控制流图构建器"""

    def __init__(self):
        self.cfg = ControlFlowGraph()
        self.entry_id = self.cfg.add_node("entry", "Entry")
        self.exit_id = self.cfg.add_node("exit", "Exit")
        self.current_id = self.entry_id

    def build(self, func_node: ast.FunctionDef) -> ControlFlowGraph:
        """构建函数的 CFG"""
        # 遍历函数体
        for stmt in func_node.body:
            self.current_id = self.visit_stmt(stmt, self.current_id)

        # 连接到出口
        if self.current_id != self.exit_id:
            self.cfg.add_edge(self.current_id, self.exit_id)

        return self.cfg

    def visit_stmt(self, node: ast.AST, prev_id: int) -> int:
        """访问语句，返回下一个节点 ID"""
        if isinstance(node, ast.If):
            return self.visit_if(node, prev_id)
        elif isinstance(node, ast.While):
            return self.visit_while(node, prev_id)
        elif isinstance(node, ast.For):
            return self.visit_for(node, prev_id)
        elif isinstance(node, ast.Return):
            return self.visit_return(node, prev_id)
        elif isinstance(node, ast.Try):
            return self.visit_try(node, prev_id)
        else:
            # 普通语句
            stmt_id = self.cfg.add_node("statement", ast.unparse(node)[:50], getattr(node, "lineno", 0))
            self.cfg.add_edge(prev_id, stmt_id)
            return stmt_id

    def visit_if(self, node: ast.If, prev_id: int) -> int:
        """处理 if 语句"""
        cond_id = self.cfg.add_node("condition", f"if {ast.unparse(node.test)[:30]}", node.lineno)
        self.cfg.add_edge(prev_id, cond_id)

        # then 分支
        then_id = cond_id
        for stmt in node.body:
            then_id = self.visit_stmt(stmt, then_id)

        # else 分支
        if node.orelse:
            else_id = cond_id
            for stmt in node.orelse:
                else_id = self.visit_stmt(stmt, else_id)
        else:
            else_id = cond_id

        # 合并节点
        merge_id = self.cfg.add_node("statement", "merge", 0)
        self.cfg.add_edge(then_id, merge_id, "true")
        self.cfg.add_edge(else_id, merge_id, "false")

        return merge_id

    def visit_while(self, node: ast.While, prev_id: int) -> int:
        """处理 while 循环"""
        cond_id = self.cfg.add_node("condition", f"while {ast.unparse(node.test)[:30]}", node.lineno)
        self.cfg.add_edge(prev_id, cond_id)

        # 循环体
        body_id = cond_id
        for stmt in node.body:
            body_id = self.visit_stmt(stmt, body_id)

        # 回边
        self.cfg.add_edge(body_id, cond_id, "loop")

        # 退出
        exit_id = self.cfg.add_node("statement", "exit loop", 0)
        self.cfg.add_edge(cond_id, exit_id, "false")

        return exit_id

    def visit_for(self, node: ast.For, prev_id: int) -> int:
        """处理 for 循环"""
        cond_id = self.cfg.add_node("condition", f"for {ast.unparse(node.target)} in {ast.unparse(node.iter)[:20]}", node.lineno)
        self.cfg.add_edge(prev_id, cond_id)

        # 循环体
        body_id = cond_id
        for stmt in node.body:
            body_id = self.visit_stmt(stmt, body_id)

        # 回边
        self.cfg.add_edge(body_id, cond_id, "loop")

        # 退出
        exit_id = self.cfg.add_node("statement", "exit loop", 0)
        self.cfg.add_edge(cond_id, exit_id, "done")

        return exit_id

    def visit_return(self, node: ast.Return, prev_id: int) -> int:
        """处理 return 语句"""
        ret_id = self.cfg.add_node("statement", f"return {ast.unparse(node.value) if node.value else ''}", node.lineno)
        self.cfg.add_edge(prev_id, ret_id)
        self.cfg.add_edge(ret_id, self.exit_id)
        return ret_id

    def visit_try(self, node: ast.Try, prev_id: int) -> int:
        """处理 try-except"""
        try_id = self.cfg.add_node("statement", "try", node.lineno)
        self.cfg.add_edge(prev_id, try_id)

        # try 块
        body_id = try_id
        for stmt in node.body:
            body_id = self.visit_stmt(stmt, body_id)

        # except 块
        for handler in node.handlers:
            except_id = self.cfg.add_node("statement", f"except {ast.unparse(handler.type) if handler.type else 'Exception'}", handler.lineno)
            self.cfg.add_edge(try_id, except_id, "exception")
            for stmt in handler.body:
                except_id = self.visit_stmt(stmt, except_id)

        merge_id = self.cfg.add_node("statement", "merge", 0)
        self.cfg.add_edge(body_id, merge_id)
        return merge_id


def generate_python_cfg(source_code: str, function_name: str) -> str:
    """为 Python 函数生成控制流图（DOT 格式）"""
    try:
        tree = ast.parse(source_code)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == function_name:
                builder = PythonCFGBuilder()
                cfg = builder.build(node)
                return cfg.to_dot(function_name)
        return f"// Function '{function_name}' not found"
    except Exception as e:
        return f"// Error: {e}"


# ═══════════════════════════════════════════
# TypeScript/JavaScript CFG 生成（简化版）
# ═══════════════════════════════════════════

def generate_typescript_cfg(source_code: str, function_name: str) -> str:
    """为 TypeScript/JavaScript 函数生成控制流图（简化版）

    注意：这是基于正则的简化实现，不如 AST 精确。
    """
    # 提取函数体（支持多种函数声明方式）
    patterns = [
        rf"function\s+{function_name}\s*\([^)]*\)[^{{]*\{{([^}}]+)\}}",  # function name() { }
        rf"const\s+{function_name}\s*=\s*\([^)]*\)\s*=>\s*\{{([^}}]+)\}}",  # const name = () => { }
        rf"{function_name}\s*\([^)]*\)[^{{]*\{{([^}}]+)\}}",  # name() { } (method)
    ]

    body = None
    for pattern in patterns:
        match = re.search(pattern, source_code, re.DOTALL)
        if match:
            body = match.group(1)
            break

    if not body:
        return f"// Function '{function_name}' not found"

    cfg = ControlFlowGraph()
    entry_id = cfg.add_node("entry", "Entry")
    exit_id = cfg.add_node("exit", "Exit")

    # 简化：按行处理
    lines = body.strip().split('\n')
    current_id = entry_id

    for line in lines:
        line = line.strip()
        if not line or line.startswith('//'):
            continue

        if line.startswith('if'):
            cond_id = cfg.add_node("condition", line[:40])
            cfg.add_edge(current_id, cond_id)
            current_id = cond_id
        elif line.startswith('return'):
            ret_id = cfg.add_node("statement", line[:40])
            cfg.add_edge(current_id, ret_id)
            cfg.add_edge(ret_id, exit_id)
            current_id = ret_id
        else:
            stmt_id = cfg.add_node("statement", line[:40])
            cfg.add_edge(current_id, stmt_id)
            current_id = stmt_id

    if current_id != exit_id:
        cfg.add_edge(current_id, exit_id)

    return cfg.to_dot(function_name)


# ═══════════════════════════════════════════
# 统一接口
# ═══════════════════════════════════════════

def generate_cfg(source_code: str, function_name: str, language: str) -> str:
    """生成函数控制流图（DOT 格式）

    Args:
        source_code: 源代码
        function_name: 函数名
        language: 语言 (python, typescript, javascript)

    Returns:
        DOT 格式的控制流图
    """
    if language == "python":
        return generate_python_cfg(source_code, function_name)
    elif language in ("typescript", "javascript", "typescriptreact", "javascriptreact"):
        return generate_typescript_cfg(source_code, function_name)
    else:
        return f"// Language '{language}' not supported for CFG generation"
