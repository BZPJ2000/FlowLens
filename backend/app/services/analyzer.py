"""分析编排服务 — 串联解析、规则分析、图构建、报告生成、持久化"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.parser import SourceScanStats, parser as code_parser
from app.core.graph_builder import graph_builder
from app.core.report_generator import report_generator
from app.db.repository import (
    AnalysisRepo,
    DataEdgeRepo,
    FileNodeRepo,
    ReportRepo,
)
from app.models.schemas import AnalysisStatus


async def run_analysis(
    db: AsyncSession,
    analysis_id: uuid.UUID,
    project_name: str,
    source_dir: str,
    progress_callback=None,
):
    """执行完整的分析流程

    Pipeline:
    1. 解析源码 → 2. AI 分析 → 3. 构建关系图 → 4. 生成报告
    每步都有进度回调，失败时更新 status 为 failed
    """

    async def update(status: AnalysisStatus, pct: int, msg: str = "", detail: str = ""):
        await AnalysisRepo.update_status(db, str(analysis_id), status.value, pct, msg)
        await db.commit()  # commit status immediately so UI polls see progress
        if progress_callback:
            await progress_callback(analysis_id, status, pct, msg, detail)

    scan_detail = ""
    parse_results = []
    ai_results = []
    graph = None
    partial_failure = False
    error_messages = []

    # ── Step 1: 解析源码 (0–20%) ────────────
    try:
        await update(AnalysisStatus.PARSING, 5, "正在扫描项目文件结构...")

        parse_results, scan_stats = code_parser.scan_project(source_dir)

        if not parse_results:
            await update(AnalysisStatus.FAILED, 0, "未找到可解析的源码文件")
            return  # 没有源码文件，直接退出，不抛异常

        total_parsed = len(parse_results)
        truncated_count = max(0, total_parsed - settings.max_files)
        parse_results = parse_results[:settings.max_files]
        analyzed_count = len(parse_results)
        scan_detail = _format_scan_progress_detail(
            scan_stats,
            total_source_files=total_parsed,
            analyzed_files=analyzed_count,
            truncated_files=truncated_count,
        )

        await update(
            AnalysisStatus.PARSING, 20,
            f"解析完成，将分析 {analyzed_count} 个业务源码文件",
            f"{scan_detail}；语言分布: {_count_languages(parse_results)}",
        )
    except Exception as e:
        error_messages.append(f"解析阶段失败: {e}")
        partial_failure = True
        # 解析失败但已有部分结果，继续后续流程
        if not parse_results:
            await update(AnalysisStatus.FAILED, 0, f"解析失败: {e}")
            return

    # ── Step 2: 规则分析 (20–65%) ────────────
    if parse_results:
        await update(AnalysisStatus.ANALYZING, 22, "开始规则分析...", scan_detail)

        from app.core.rule_analyzer import rule_analyzer

        total = len(parse_results)
        ai_results = []
        for i, pr in enumerate(parse_results):
            ai_results.append(rule_analyzer.analyze(pr))
            if (i + 1) % 10 == 0 or i == total - 1:
                pct = 20 + int(((i + 1) / total) * 45)
                await update(
                    AnalysisStatus.ANALYZING, pct,
                    f"规则分析: {i + 1}/{total}",
                    f"{scan_detail}；当前文件: {pr.file_path}",
                )

        await update(
            AnalysisStatus.ANALYZING, 65,
            f"规则分析完成，共 {len(ai_results)} 个文件",
        )

    # ── Step 2.5: 持久化文件分析结果 (65–75%) ──
    path_to_db_id: dict[str, str] = {}
    if parse_results and ai_results:
        try:
            await update(AnalysisStatus.ANALYZING, 68, "持久化规则分析结果...")
            # 确保两个列表长度一致
            min_len = min(len(parse_results), len(ai_results))
            path_to_db_id = await _persist_file_nodes(
                db, analysis_id,
                parse_results[:min_len], ai_results[:min_len],
            )
            await db.commit()
        except Exception as e:
            error_messages.append(f"持久化文件分析结果失败: {e}")
            partial_failure = True
            await db.rollback()

    # ── Step 3: 构建关系图 (75–85%) ──────────
    if parse_results and ai_results:
        try:
            await update(AnalysisStatus.BUILDING, 75, "构建数据流关系图...")
            min_len = min(len(parse_results), len(ai_results))
            graph = graph_builder.build(
                parse_results[:min_len], ai_results[:min_len],
            )

            await update(
                AnalysisStatus.BUILDING, 82,
                f"关系图构建完成: {len(graph.nodes)} 节点, {len(graph.edges)} 边",
            )

            # 持久化边
            await update(AnalysisStatus.BUILDING, 84, "持久化数据流关系...")
            await _persist_edges(db, analysis_id, graph, path_to_db_id)
            await db.commit()
        except Exception as e:
            error_messages.append(f"关系图构建失败: {e}")
            partial_failure = True
            await db.rollback()
            try:
                # 尝试用空图继续
                from app.models.schemas import DataFlowGraph
                graph = DataFlowGraph()
            except Exception:
                pass

    # ── Step 4: 生成报告 (85–100%) ───────────
    if graph and parse_results and ai_results:
        try:
            await update(AnalysisStatus.BUILDING, 86, "生成架构报告...")
            min_len = min(len(parse_results), len(ai_results))
            report = report_generator.generate(
                project_name,
                parse_results[:min_len], ai_results[:min_len], graph,
            )
            markdown = report_generator.generate_markdown(report)

            await ReportRepo.save(
                db, str(analysis_id), markdown,
                report.architecture_summary,
                len(report.issues),
            )
            await db.commit()

            status_msg = "分析完成"
            if partial_failure:
                status_msg = f"分析部分完成（{len(error_messages)} 个步骤失败）"
            await update(
                AnalysisStatus.COMPLETED, 100,
                f"{status_msg} — {len(graph.nodes)} 节点, {len(graph.edges)} 数据流, "
                f"{len(report.issues)} 个问题, 健康评分 {report.health_score}/100",
            )
        except Exception as e:
            error_messages.append(f"报告生成失败: {e}")
            await db.rollback()
            await update(
                AnalysisStatus.COMPLETED, 95,
                f"分析完成（报告生成失败）— {len(graph.nodes)} 节点, {len(graph.edges)} 数据流",
            )
    elif parse_results:
        # 即使没有图也能完成（至少解析完成了）
        final_msg = "分析完成（仅解析，无关系图）"
        if error_messages:
            final_msg += f"；错误: {'; '.join(error_messages[-2:])}"
        await update(AnalysisStatus.COMPLETED, 50, final_msg)


# ── 持久化辅助 ──────────────────────────────────

async def _persist_file_nodes(
    db: AsyncSession,
    analysis_id: uuid.UUID,
    parse_results,
    ai_results,
) -> dict[str, str]:
    """持久化 AI 分析结果到 FileNode，返回 {file_path: db_id} 映射"""
    aid = str(analysis_id)  # MySQL String(36) 列需要字符串，不能传 UUID 对象
    file_records = []
    for pr, ai_result in zip(parse_results, ai_results):
        file_records.append({
            "file_path": pr.file_path,
            "file_name": pr.file_name,
            "language": pr.language,
            "content_hash": pr.content_hash,
            "summary": ai_result.summary,
            "detail_explain": ai_result.detail,
            "imports_json": [
                inp.model_dump() for inp in ai_result.inputs
            ],
            "exports_json": [
                out.model_dump() for out in ai_result.outputs
            ],
            "functions_json": [
                f.model_dump() for f in pr.functions
            ],
            "classes_json": [
                c.model_dump() for c in pr.classes
            ],
        })

    nodes = await FileNodeRepo.bulk_create(db, aid, file_records)
    return {n.file_path: str(n.id) for n in nodes}


async def _persist_edges(
    db: AsyncSession,
    analysis_id: uuid.UUID,
    graph,
    path_to_db_id: dict[str, str],
):
    """持久化数据流边到 DataEdge"""
    aid = str(analysis_id)
    node_id_to_path = {n.id: n.file_path for n in graph.nodes}
    edge_records = []
    for edge in graph.edges:
        from_path = node_id_to_path.get(edge.source_node_id, "")
        to_path = node_id_to_path.get(edge.target_node_id, "")
        from_db_id = path_to_db_id.get(from_path)
        to_db_id = path_to_db_id.get(to_path)

        if from_db_id and to_db_id:
            edge_records.append({
                "from_file_id": from_db_id,
                "to_file_id": to_db_id,
                "from_port_name": edge.source_port_id,
                "to_port_name": edge.target_port_id,
                "variable_name": edge.variable_name,
                "data_type": edge.data_type,
                "edge_type": edge.edge_type.value,
                "metadata_json": {
                    "source_function_id": edge.source_function_id or "",
                    "target_function_id": edge.target_function_id or "",
                },
            })

    if edge_records:
        await DataEdgeRepo.bulk_create(db, aid, edge_records)


# ── 辅助 ─────────────────────────────────────

def _format_scan_progress_detail(
    scan_stats: SourceScanStats,
    total_source_files: int,
    analyzed_files: int,
    truncated_files: int,
) -> str:
    limit_text = (
        f"分析队列上限 {settings.max_files}，已截断 {truncated_files} 个"
        if truncated_files
        else f"未触发 {settings.max_files} 上限"
    )
    return (
        f"发现 {scan_stats.discovered_files} 个文件；"
        f"非源码/不支持后缀 {scan_stats.unsupported_extension_files} 个；"
        f"候选代码 {scan_stats.supported_extension_files} 个；"
        f"过滤配置/测试/构建/生成文件 {scan_stats.ignored_files} 个；"
        f"业务源码 {total_source_files} 个；"
        f"本次分析 {analyzed_files} 个；"
        f"{limit_text}"
    )


def _count_languages(parse_results) -> str:
    from collections import Counter
    counts = Counter(p.language for p in parse_results)
    return ", ".join(f"{lang}: {n}" for lang, n in counts.most_common(5))
