"""Phase 1: 报告生成引擎 — 基于分析结果生成架构文档

产出:
1. 架构概要（角色分布、数据流摘要）
2. 架构健康评分（0-100）
3. 问题诊断（循环依赖、未使用导出、大型文件、孤儿文件、重型依赖）
4. 核心数据流路径
5. 按角色分组的文件详情
"""

from collections import defaultdict
from datetime import datetime, timezone

from app.models.schemas import (
    AIFileAnalysis,
    AnalysisReport,
    ArchitectureIssue,
    DataFlowGraph,
    GraphNode,
    ParseResult,
)


class ReportGenerator:

    def generate(
        self,
        project_name: str,
        parse_results: list[ParseResult],
        ai_results: list[AIFileAnalysis],
        graph: DataFlowGraph,
    ) -> AnalysisReport:
        ai_map = {a.file_path: a for a in ai_results}

        total_lines = sum(p.line_count for p in parse_results)
        languages = list({p.language for p in parse_results if p.language != "unknown"})

        arch_summary = self._build_architecture_summary(ai_results, graph)
        issues = self._diagnose_issues(parse_results, ai_results, graph, ai_map)
        core_flows = self._identify_core_flows(graph, ai_map)
        health_score = self._calculate_health_score(graph, issues)

        return AnalysisReport(
            project_name=project_name,
            tech_stack=languages,
            file_count=len(parse_results),
            total_lines=total_lines,
            architecture_summary=arch_summary,
            file_details=ai_results,
            core_flows=core_flows,
            issues=issues,
            health_score=health_score,
            generated_at=datetime.now(timezone.utc),
        )

    # ── Markdown 渲染 ─────────────────────────

    def generate_markdown(self, report: AnalysisReport) -> str:
        L = []
        L.append(f"# {report.project_name} — 架构分析报告\n")
        L.append(f"> 生成时间: {report.generated_at.strftime('%Y-%m-%d %H:%M UTC')}\n")

        # 健康评分
        score = getattr(report, "health_score", None)
        if score is not None:
            emoji = "🟢" if score >= 80 else ("🟡" if score >= 50 else "🔴")
            bar = "█" * int(score / 5) + "░" * (20 - int(score / 5))
            L.append(f"## 架构健康评分: {emoji} {score}/100\n")
            L.append(f"```\n{bar}\n```\n")

        # 项目概况
        L.append("## 项目概况\n")
        L.append(f"| 指标 | 值 |")
        L.append(f"|------|----|")
        L.append(f"| 文件总数 | {report.file_count} |")
        L.append(f"| 代码总行数 | {report.total_lines:,} |")
        L.append(f"| 技术栈 | {', '.join(report.tech_stack) or '未知'} |")
        L.append(f"| 图节点数 | {len(report.file_details)} |")
        L.append(f"| 发现问题 | {len(report.issues)} 个 |\n")

        # 架构概要
        L.append("## 架构概要\n")
        L.append(report.architecture_summary)
        L.append("")

        # 核心数据流
        if report.core_flows:
            L.append("## 核心数据流\n")
            for i, flow in enumerate(report.core_flows, 1):
                L.append(f"{i}. {flow}")
            L.append("")

        # 问题诊断（按严重度排序）
        if report.issues:
            L.append("## 架构问题\n")
            severity_order = {"error": 0, "warning": 1, "info": 2}
            sorted_issues = sorted(
                report.issues,
                key=lambda x: severity_order.get(x.severity, 99),
            )
            for issue in sorted_issues:
                emoji = {"error": "🔴", "warning": "🟡", "info": "🔵"}.get(
                    issue.severity, "⚪"
                )
                L.append(
                    f"- {emoji} **[{issue.severity.upper()}]** "
                    f"{issue.category}: {issue.description}"
                )
                if issue.related_files:
                    L.append(f"  - 相关文件: `{'`, `'.join(issue.related_files[:10])}`")
                if issue.suggestion:
                    L.append(f"  - 建议: {issue.suggestion}")
            L.append("")

        # 文件详情（按角色分组）
        L.append("## 文件详情\n")
        by_role: dict[str, list[AIFileAnalysis]] = {}
        for f in report.file_details:
            by_role.setdefault(f.architecture_role or "other", []).append(f)

        role_labels = {
            "controller": "控制器 / 路由",
            "service": "业务逻辑 / Service",
            "model": "数据模型",
            "view": "视图 / 组件",
            "util": "工具函数",
            "config": "配置文件",
            "middleware": "中间件",
            "hook": "钩子 / Hooks",
            "store": "状态管理",
            "route": "路由定义",
            "type": "类型定义",
            "test": "测试",
            "other": "其他",
        }

        for role, files in sorted(by_role.items()):
            label = role_labels.get(role, role)
            L.append(f"### {label} ({len(files)} 个文件)\n")
            for f in files[:50]:  # 每种角色最多展示 50 个
                L.append(f"#### `{f.file_path}`\n")
                L.append(f"**{f.summary}**\n")
                if f.detail:
                    L.append(f"{f.detail}\n")

                if f.inputs:
                    L.append("*输入/依赖:*\n")
                    for inp in f.inputs:
                        src = f" — 来自 `{inp.source}`" if inp.source else ""
                        L.append(f"- `{inp.name}: {inp.type}`{src}")
                    L.append("")

                if f.outputs:
                    L.append("*输出/提供:*\n")
                    for out in f.outputs:
                        L.append(f"- `{out.name}: {out.type}`")
                    L.append("")

                if f.internal_structures:
                    L.append("*内部数据结构:*\n")
                    for s in f.internal_structures:
                        fields_str = ", ".join(
                            f"`{fd.get('name', '?')}: {fd.get('type', '?')}`"
                            for fd in s.get("fields", [])
                        )
                        L.append(
                            f"- `{s.get('name', '?')}` "
                            f"({s.get('type', '?')}): {fields_str}"
                        )
                    L.append("")

        L.append("---\n")
        L.append("*本报告由 PoltAIshow 自动生成*\n")
        return "\n".join(L)

    # ── 架构概要 ──────────────────────────────

    def _build_architecture_summary(
        self,
        ai_results: list[AIFileAnalysis],
        graph: DataFlowGraph,
    ) -> str:
        role_counts: dict[str, int] = {}
        for r in ai_results:
            role_counts[r.architecture_role or "other"] = (
                role_counts.get(r.architecture_role or "other", 0) + 1
            )

        role_str = ", ".join(
            f"{k}: {v}个" for k, v in sorted(
                role_counts.items(), key=lambda x: -x[1]
            )
        )

        parts = [
            f"该项目共有 {len(ai_results)} 个文件，"
            f"{len(graph.nodes)} 个图节点，"
            f"{len(graph.edges)} 条数据流连接。",
            f"架构角色分布: {role_str}。",
        ]

        if graph.entry_points:
            entry_names = [
                self._node_name(graph, nid) for nid in graph.entry_points[:3]
            ]
            parts.append(f"数据入口: {', '.join(entry_names)}。")

        if graph.exit_points:
            exit_names = [
                self._node_name(graph, nid) for nid in graph.exit_points[:3]
            ]
            parts.append(f"数据出口: {', '.join(exit_names)}。")

        # 循环依赖
        cycles = getattr(graph, "cycles", [])
        if cycles:
            parts.append(f"⚠️ 检测到 {len(cycles)} 个循环依赖。")
        else:
            parts.append("✅ 未检测到循环依赖。")

        return " ".join(parts)

    # ── 问题诊断 ──────────────────────────────

    def _diagnose_issues(
        self,
        parse_results: list[ParseResult],
        ai_results: list[AIFileAnalysis],
        graph: DataFlowGraph,
        ai_map: dict[str, AIFileAnalysis],
    ) -> list[ArchitectureIssue]:
        issues: list[ArchitectureIssue] = []

        # 1. 循环依赖
        cycles = getattr(graph, "cycles", [])
        if cycles:
            cycle_descs = []
            cycle_files = []
            for cycle in cycles[:5]:
                names = [self._node_name(graph, nid) for nid in cycle]
                cycle_descs.append(" → ".join(names))
                cycle_files.extend(names)
            issues.append(ArchitectureIssue(
                severity="error",
                category="circular_dependency",
                description=f"检测到 {len(cycles)} 个循环依赖: {'; '.join(cycle_descs)}",
                related_files=list(set(cycle_files)),
                suggestion="重构相互引用的模块，提取公共接口到独立文件。",
            ))

        # 2. 未使用导出
        unused = getattr(graph, "unused_exports", [])
        if unused:
            examples = [
                f"`{u['variable_name']}`" for u in unused[:10]
            ]
            issues.append(ArchitectureIssue(
                severity="warning",
                category="unused_export",
                description=(
                    f"发现 {len(unused)} 个未使用的导出: {', '.join(examples)}"
                    f"{'...' if len(unused) > 10 else ''}"
                ),
                related_files=list({
                    fid for u in unused for fid in u.get("node_ids", [])
                }),
                suggestion="删除未使用的导出以减小 API 面积，或确认它们是为外部消费者准备的。",
            ))

        # 3. 大型文件（行数过多）
        large_files = [
            (p.file_path, p.line_count)
            for p in parse_results if p.line_count > 500
        ]
        if large_files:
            large_files.sort(key=lambda x: -x[1])
            examples = [
                f"`{fp}` ({lc} 行)" for fp, lc in large_files[:5]
            ]
            issues.append(ArchitectureIssue(
                severity="warning",
                category="large_file",
                description=(
                    f"发现 {len(large_files)} 个超过 500 行的大文件: "
                    f"{'; '.join(examples)}"
                ),
                related_files=[fp for fp, _ in large_files],
                suggestion="将大文件拆分为更小的模块，遵循单一职责原则。",
            ))

        # 4. 孤儿文件（既没导入也没导出，或完全没有连接）
        node_ids_with_edges: set[str] = set()
        for e in graph.edges:
            node_ids_with_edges.add(e.source_node_id)
            node_ids_with_edges.add(e.target_node_id)
        orphans = [
            n for n in graph.nodes
            if n.id not in node_ids_with_edges
        ]
        if orphans:
            issues.append(ArchitectureIssue(
                severity="info",
                category="orphan_file",
                description=(
                    f"发现 {len(orphans)} 个孤立文件（无数据流连接）: "
                    f"{', '.join(f'`{o.file_name}`' for o in orphans[:8])}"
                ),
                related_files=[o.file_path for o in orphans],
                suggestion="检查这些文件是否为死代码，或是否需要被其他模块引用。",
            ))

        # 5. 重依赖文件（导入过多）
        heavy_importers = []
        for ai in ai_results:
            if len(ai.inputs) > 15:
                heavy_importers.append((ai.file_path, len(ai.inputs)))
        if heavy_importers:
            heavy_importers.sort(key=lambda x: -x[1])
            examples = [
                f"`{fp}` ({n} 个依赖)" for fp, n in heavy_importers[:5]
            ]
            issues.append(ArchitectureIssue(
                severity="warning",
                category="heavy_dependency",
                description=(
                    f"发现 {len(heavy_importers)} 个重度依赖文件（>15 个导入）: "
                    f"{'; '.join(examples)}"
                ),
                related_files=[fp for fp, _ in heavy_importers],
                suggestion="考虑将这些文件的职责拆分，减少单一文件的依赖数量。",
            ))

        # 6. 缺少类型定义（如果项目语言支持类型但未用）
        type_files = [
            ai.file_path for ai in ai_results
            if ai.architecture_role == "type"
        ]
        if not type_files and len(ai_results) > 10:
            # 检查是否有 TS 项目但无类型文件
            has_ts = any(
                p.language in ("typescript", "typescriptreact")
                for p in parse_results
            )
            if has_ts:
                issues.append(ArchitectureIssue(
                    severity="info",
                    category="no_type_definitions",
                    description="TypeScript 项目中未检测到独立的类型定义文件。",
                    suggestion="建议将共享类型提取到 `types.ts` 或 `interfaces.ts` 中。",
                ))

        # 无问题时
        if not issues:
            issues.append(ArchitectureIssue(
                severity="info",
                category="clean",
                description="未检测到明显的架构问题，项目结构良好。",
            ))

        return issues

    # ── 核心数据流 ────────────────────────────

    def _identify_core_flows(
        self, graph: DataFlowGraph, ai_map: dict[str, AIFileAnalysis]
    ) -> list[str]:
        flows: list[str] = []

        # 从入口到出口的宏观流
        if graph.entry_points and graph.exit_points:
            entry_names = [
                self._node_name(graph, nid) for nid in graph.entry_points[:5]
            ]
            exit_names = [
                self._node_name(graph, nid) for nid in graph.exit_points[:5]
            ]
            flows.append(
                f"数据从入口文件 **{', '.join(entry_names)}** 流入，"
                f"经过 {len(graph.nodes)} 个文件的处理，"
                f"最终到达出口 **{', '.join(exit_names)}**。"
                f"数据流共包含 {len(graph.edges)} 条连接。"
            )

        # 按架构角色的经典流
        role_groups: dict[str, list[str]] = defaultdict(list)
        for n in graph.nodes:
            role_groups[n.architecture_role or "other"].append(n.file_name)

        if role_groups.get("controller"):
            c_count = len(role_groups["controller"])
            s_count = len(role_groups.get("service", []))
            m_count = len(role_groups.get("model", []))
            flows.append(
                f"请求通过 {c_count} 个控制器进入系统"
                + (
                    f"，调用 {s_count} 个服务层处理后"
                    if s_count else ""
                )
                + (
                    f"，操作 {m_count} 个数据模型后返回响应"
                    if m_count else ""
                )
                + "。"
            )

        if not flows:
            flows.append(
                "该项目的数据流结构较为扁平，"
                "各文件通过导入导出形成了松散耦合的关系网。"
            )

        return flows

    # ── 健康评分 ──────────────────────────────

    def _calculate_health_score(
        self, graph: DataFlowGraph, issues: list[ArchitectureIssue]
    ) -> int:
        score = 100

        # 循环依赖: -15/个
        cycles = getattr(graph, "cycles", [])
        score -= min(len(cycles) * 15, 40)

        # 未使用导出: -2/个
        unused = getattr(graph, "unused_exports", [])
        score -= min(len(unused) * 2, 15)

        # 问题严重度
        for issue in issues:
            if issue.severity == "error":
                score -= 10
            elif issue.severity == "warning":
                score -= 5
            elif issue.severity == "info" and issue.category != "clean":
                score -= 1

        # 图密度（太少连接 vs 太多连接）
        node_count = len(graph.nodes)
        edge_count = len(graph.edges)
        if node_count > 0:
            density = edge_count / max(node_count, 1)
            if density < 0.3:
                score -= 5  # 连接太少，可能是松散耦合或分析不全
            elif density > 5:
                score -= 5  # 连接过多，可能是乱 import

        return max(0, min(100, score))

    # ── 辅助 ─────────────────────────────────

    def _node_name(self, graph: DataFlowGraph, node_id: str) -> str:
        for n in graph.nodes:
            if n.id == node_id:
                return n.file_name
        return node_id[:8]


# 单例
report_generator = ReportGenerator()
