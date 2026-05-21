"""GraphML 标准格式导出 — 兼容 Gephi, yEd, NetworkX 等图分析工具

输出符合 GraphML 1.0 规范的 XML 文件，节点和边携带完整属性：
- 节点: file_name, language, architecture_role, summary, function_count, class_count
- 边: variable_name, data_type, edge_type, label
"""

import xml.etree.ElementTree as ET

from app.models.schemas import DataFlowGraph


def export_graphml(graph: DataFlowGraph, project_name: str = "PoltAIshow") -> str:
    """将 DataFlowGraph 导出为 GraphML 格式的 XML 字符串。

    兼容 Gephi 0.10+, yEd 3.x, NetworkX 等工具。
    """
    NS = "http://graphml.graphdrawing.org/xmlns"
    ET.register_namespace("", NS)
    root = ET.Element("graphml", xmlns=NS)

    # ── 节点属性 key 定义 ──
    _add_key(root, "label", "node", "标签 / 文件名", "string")
    _add_key(root, "language", "node", "编程语言", "string")
    _add_key(root, "role", "node", "架构角色", "string")
    _add_key(root, "summary", "node", "一句话总结", "string")
    _add_key(root, "file_path", "node", "文件路径", "string")
    _add_key(root, "function_count", "node", "函数数量", "int")
    _add_key(root, "class_count", "node", "类数量", "int")

    # ── 边属性 key 定义 ──
    _add_key(root, "label", "edge", "边标签", "string")
    _add_key(root, "variable_name", "edge", "变量名", "string")
    _add_key(root, "data_type", "edge", "数据类型", "string")
    _add_key(root, "edge_type", "edge", "边类型", "string")

    # ── 图主体 ──
    graph_el = ET.SubElement(root, "graph", id="G", edgedefault="directed")

    # 项目元信息
    _add_data(graph_el, "project_name", project_name)

    # 节点
    for node in graph.nodes:
        node_el = ET.SubElement(graph_el, "node", id=_safe_id(node.id))
        _add_data(node_el, "label", node.file_name)
        _add_data(node_el, "language", node.language)
        _add_data(node_el, "role", node.architecture_role or "")
        _add_data(node_el, "summary", node.summary or "")
        _add_data(node_el, "file_path", node.file_path)
        _add_data(node_el, "function_count", str(len(node.functions)))
        _add_data(node_el, "class_count", str(len(node.classes)))

    # 边
    for edge in graph.edges:
        edge_el = ET.SubElement(
            graph_el, "edge",
            source=_safe_id(edge.source_node_id),
            target=_safe_id(edge.target_node_id),
        )
        edge_type = getattr(edge.edge_type, "value", None) or str(edge.edge_type)
        _add_data(edge_el, "label", edge.label or edge.variable_name)
        _add_data(edge_el, "variable_name", edge.variable_name)
        _add_data(edge_el, "data_type", edge.data_type or "unknown")
        _add_data(edge_el, "edge_type", edge_type)

    return ET.tostring(root, encoding="unicode", xml_declaration=True)


def export_graphml_file(graph: DataFlowGraph, output_path: str, project_name: str = "PoltAIshow") -> None:
    """导出 GraphML 到文件。"""
    content = export_graphml(graph, project_name)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)


# ── 辅助 ─────────────────────────────────────

def _add_key(parent: ET.Element, name: str, for_type: str, display_name: str, attr_type: str) -> ET.Element:
    """添加 <key> 定义"""
    return ET.SubElement(parent, "key", {
        "id": f"{for_type}_{name}" if name == "label" else name,
        "for": for_type,
        "attr.name": display_name,
        "attr.type": attr_type,
    })


def _add_data(parent: ET.Element, key: str, value: str) -> ET.Element:
    """添加 <data> 元素"""
    data_el = ET.SubElement(parent, "data", key=key)
    data_el.text = value
    return data_el


def _safe_id(node_id: str) -> str:
    """GraphML 要求 ID 以字母开头，不能含特殊字符。"""
    # 简单地将 UUID/数字 ID 包装为 n_ 前缀
    sanitized = node_id.replace("-", "_").replace(".", "_")
    if sanitized[0].isdigit():
        sanitized = f"n_{sanitized}"
    return sanitized
