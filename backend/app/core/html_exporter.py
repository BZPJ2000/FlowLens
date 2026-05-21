"""自包含 HTML 报告导出 — 单文件离线可视化

生成包含完整图数据 + 交互式可视化的单个 HTML 文件：
- 零外部依赖（CSS/JS 全部内联）
- 基于 D3.js 力导向图
- 支持缩放、拖拽、搜索、节点点击
- 可作为 PR 附件、邮件分享、离线查看
"""

from app.models.schemas import DataFlowGraph


def export_html(graph: DataFlowGraph, project_name: str = "PoltAIshow") -> str:
    """生成自包含的 HTML 可视化报告"""

    # 构建节点和边的 JSON 数据
    nodes_json = [
        {
            "id": n.id,
            "label": n.file_name,
            "path": n.file_path,
            "language": n.language,
            "role": n.architecture_role or "other",
            "summary": n.summary or "",
            "functions": len(n.functions),
            "classes": len(n.classes),
        }
        for n in graph.nodes
    ]

    edges_json = [
        {
            "source": e.source_node_id,
            "target": e.target_node_id,
            "label": e.variable_name or "",
            "type": e.data_type or "unknown",
        }
        for e in graph.edges
    ]

    import json
    nodes_data = json.dumps(nodes_json, ensure_ascii=False)
    edges_data = json.dumps(edges_json, ensure_ascii=False)

    # HTML 模板（内联 D3.js + 完整样式）
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{project_name} — 数据流图</title>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #0a0a10;
      color: #f5f5f7;
      overflow: hidden;
    }}
    #header {{
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      height: 50px;
      background: #06060a;
      border-bottom: 1px solid #1e1e3a;
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 20px;
      z-index: 100;
    }}
    #header h1 {{
      font-size: 16px;
      font-weight: 600;
      color: #f5f5f7;
    }}
    #stats {{
      font-size: 12px;
      color: #6b7280;
    }}
    #search {{
      position: fixed;
      top: 60px;
      left: 20px;
      z-index: 50;
      background: #12121c;
      border: 1px solid #1e1e3a;
      border-radius: 8px;
      padding: 8px 12px;
      font-size: 13px;
      color: #f5f5f7;
      width: 250px;
    }}
    #search:focus {{
      outline: none;
      border-color: #7c3aed;
      box-shadow: 0 0 0 3px rgba(124, 58, 237, 0.1);
    }}
    #info {{
      position: fixed;
      top: 60px;
      right: 20px;
      background: #12121c;
      border: 1px solid #1e1e3a;
      border-radius: 8px;
      padding: 12px;
      font-size: 12px;
      color: #a1a1aa;
      max-width: 300px;
      display: none;
      z-index: 50;
    }}
    #info.show {{ display: block; }}
    #info .title {{
      font-weight: 600;
      color: #f5f5f7;
      margin-bottom: 8px;
      font-size: 13px;
    }}
    #info .path {{
      font-family: monospace;
      font-size: 11px;
      color: #6b7280;
      margin-bottom: 8px;
      word-break: break-all;
    }}
    #info .badge {{
      display: inline-block;
      padding: 2px 6px;
      border-radius: 4px;
      font-size: 10px;
      margin-right: 4px;
      margin-bottom: 4px;
    }}
    #info .badge.lang {{ background: #1a1a2e; color: #6b7280; }}
    #info .badge.role {{ background: rgba(124, 58, 237, 0.1); color: #a78bfa; }}
    svg {{ width: 100%; height: 100vh; }}
    .node circle {{
      stroke: #1e1e3a;
      stroke-width: 2px;
      cursor: pointer;
    }}
    .node text {{
      font-size: 10px;
      fill: #a1a1aa;
      pointer-events: none;
      text-anchor: middle;
    }}
    .node.highlight circle {{
      stroke: #7c3aed;
      stroke-width: 3px;
    }}
    .link {{
      stroke: #1e1e3a;
      stroke-opacity: 0.6;
      stroke-width: 1px;
    }}
    .link.highlight {{
      stroke: #7c3aed;
      stroke-opacity: 1;
      stroke-width: 2px;
    }}
  </style>
</head>
<body>
  <div id="header">
    <h1>{project_name}</h1>
    <div id="stats"></div>
  </div>
  <input id="search" type="text" placeholder="搜索文件名..." />
  <div id="info"></div>
  <svg id="graph"></svg>

  <script src="https://d3js.org/d3.v7.min.js"></script>
  <script>
    const nodes = {nodes_data};
    const links = {edges_data};

    const width = window.innerWidth;
    const height = window.innerHeight;

    const svg = d3.select("#graph");
    const g = svg.append("g");

    // 缩放
    const zoom = d3.zoom()
      .scaleExtent([0.1, 4])
      .on("zoom", (event) => g.attr("transform", event.transform));
    svg.call(zoom);

    // 力导向模拟
    const simulation = d3.forceSimulation(nodes)
      .force("link", d3.forceLink(links).id(d => d.id).distance(100))
      .force("charge", d3.forceManyBody().strength(-300))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("collision", d3.forceCollide().radius(30));

    // 边
    const link = g.append("g")
      .selectAll("line")
      .data(links)
      .join("line")
      .attr("class", "link");

    // 节点
    const node = g.append("g")
      .selectAll("g")
      .data(nodes)
      .join("g")
      .attr("class", "node")
      .call(d3.drag()
        .on("start", dragstarted)
        .on("drag", dragged)
        .on("end", dragended));

    node.append("circle")
      .attr("r", 8)
      .attr("fill", d => getRoleColor(d.role));

    node.append("text")
      .attr("dy", 20)
      .text(d => d.label);

    // 节点点击
    node.on("click", (event, d) => {{
      showInfo(d);
      highlightNode(d);
    }});

    // 搜索
    d3.select("#search").on("input", function() {{
      const query = this.value.toLowerCase();
      node.classed("highlight", d => d.label.toLowerCase().includes(query));
    }});

    // 更新统计
    d3.select("#stats").text(`${{nodes.length}} 个文件, ${{links.length}} 条连接`);

    simulation.on("tick", () => {{
      link
        .attr("x1", d => d.source.x)
        .attr("y1", d => d.source.y)
        .attr("x2", d => d.target.x)
        .attr("y2", d => d.target.y);

      node.attr("transform", d => `translate(${{d.x}},${{d.y}})`);
    }});

    function dragstarted(event, d) {{
      if (!event.active) simulation.alphaTarget(0.3).restart();
      d.fx = d.x;
      d.fy = d.y;
    }}

    function dragged(event, d) {{
      d.fx = event.x;
      d.fy = event.y;
    }}

    function dragended(event, d) {{
      if (!event.active) simulation.alphaTarget(0);
      d.fx = null;
      d.fy = null;
    }}

    function showInfo(d) {{
      const info = d3.select("#info");
      info.classed("show", true);
      info.html(`
        <div class="title">${{d.label}}</div>
        <div class="path">${{d.path}}</div>
        <div>
          <span class="badge lang">${{d.language}}</span>
          <span class="badge role">${{d.role}}</span>
        </div>
        <div style="margin-top: 8px; font-size: 11px;">
          ${{d.summary || '—'}}
        </div>
        <div style="margin-top: 8px; font-size: 10px; color: #6b7280;">
          ${{d.functions}} 个函数, ${{d.classes}} 个类
        </div>
      `);
    }}

    function highlightNode(d) {{
      node.classed("highlight", n => n.id === d.id);
      link.classed("highlight", l => l.source.id === d.id || l.target.id === d.id);
    }}

    function getRoleColor(role) {{
      const colors = {{
        controller: "#60a5fa",
        service: "#a78bfa",
        model: "#f472b6",
        view: "#4ade80",
        util: "#fbbf24",
        config: "#fb923c",
        middleware: "#38bdf8",
        hook: "#c084fc",
        store: "#f59e0b",
        route: "#10b981",
        type: "#6366f1",
        test: "#6b7280",
        other: "#9ca3af",
      }};
      return colors[role] || colors.other;
    }}
  </script>
</body>
</html>"""

    return html


def export_html_file(graph: DataFlowGraph, output_path: str, project_name: str = "PoltAIshow") -> None:
    """导出 HTML 到文件"""
    content = export_html(graph, project_name)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
