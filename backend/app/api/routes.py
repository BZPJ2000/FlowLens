"""API 路由 — 导入、分析、查询、对话"""

import asyncio
import hashlib
import json
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel


def make_fn_id(file_path: str, fn_name: str) -> str:
    h = hashlib.md5(f"{file_path}::fn::{fn_name}".encode()).hexdigest()[:24]
    return f"fn_{h}"

def make_class_id(file_path: str, class_name: str) -> str:
    h = hashlib.md5(f"{file_path}::cls::{class_name}".encode()).hexdigest()[:24]
    return f"cls_{h}"

def make_method_id(file_path: str, class_name: str, method_name: str) -> str:
    h = hashlib.md5(f"{file_path}::cls::{class_name}::m::{method_name}".encode()).hexdigest()[:24]
    return f"m_{h}"

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.database import get_db
from app.db.repository import (
    AnalysisRepo,
    ChatRepo,
    DataEdgeRepo,
    FileNodeRepo,
    ProjectRepo,
    ReportRepo,
)
from app.db.models import FileNode
from app.services.import_service import import_service
from app.services.progress_manager import progress_manager, Step
from app.services.analyzer import run_analysis
from app.core.graph_builder import graph_builder, analyze_impact
from app.core.graphml_exporter import export_graphml
from app.core.html_exporter import export_html
from app.core.cfg_generator import generate_cfg

router = APIRouter(prefix="/api/v1")


# ═══════════════════════════════════════════
# Projects (list)
# ═══════════════════════════════════════════

@router.get("/projects")
async def list_projects(db: AsyncSession = Depends(get_db)):
    """列出所有项目及其最新分析状态"""
    projects = await ProjectRepo.list_all(db)
    result = []
    for p in projects:
        # Get latest analysis for this project
        analyses = p.analyses  # relationship already loaded
        latest_analysis = None
        if analyses:
            latest = sorted(analyses, key=lambda a: a.created_at, reverse=True)[0]
            latest_analysis = {
                "analysis_id": latest.id,
                "status": latest.status,
                "progress_pct": latest.progress_pct,
                "error_message": latest.error_message or "",
            }
        result.append({
            "project_id": p.id,
            "name": p.name,
            "source_type": p.source_type,
            "source_url": p.source_url or "",
            "file_count": p.file_count,
            "created_at": p.created_at.isoformat() if p.created_at else "",
            "latest_analysis": latest_analysis,
        })
    return result


# ═══════════════════════════════════════════
# Delete Project
# ═══════════════════════════════════════════

@router.delete("/projects/{project_id}")
async def delete_project(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """删除项目及其所有关联数据"""
    pid = str(project_id)
    project = await ProjectRepo.get(db, pid)
    if not project:
        raise HTTPException(404, "项目不存在")
    await db.delete(project)
    await db.commit()
    return {"status": "deleted", "project_id": pid}


# ═══════════════════════════════════════════
# Import
# ═══════════════════════════════════════════

class ImportRequest(BaseModel):
    source_type: str = "github"
    source_url: str = ""


@router.post("/projects/import")
async def import_project_json(
    background_tasks: BackgroundTasks,
    req: ImportRequest,
    db: AsyncSession = Depends(get_db),
):
    """导入项目 — JSON body（GitHub URL）"""
    if not req.source_url:
        raise HTTPException(400, "请提供 GitHub URL")
    source = req.source_type
    url = req.source_url
    project_name = url.rstrip("/").split("/")[-1].replace(".git", "")

    return await _create_and_launch(background_tasks, db, project_name, source, url)


@router.post("/projects/import/upload")
async def import_project_upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """导入项目 — multipart form（文件上传）"""
    file_bytes = await file.read()
    file_name = file.filename or "project"
    project_name = file_name
    for ext in (".zip", ".tar.gz", ".tgz", ".tar"):
        project_name = project_name.replace(ext, "")

    return await _create_and_launch(
        background_tasks, db, project_name, "upload", "",
        file_bytes=file_bytes, file_name=file_name,
    )


async def _create_and_launch(
    background_tasks: BackgroundTasks,
    db: AsyncSession,
    project_name: str,
    source_type: str,
    source_url: str,
    file_bytes: bytes | None = None,
    file_name: str | None = None,
):

    # 创建 project 和 analysis
    project = await ProjectRepo.create(db, project_name, source_type, source_url)
    analysis = await AnalysisRepo.create(db, project.id)
    aid = str(analysis.id)

    # 先提交 project + analysis 到 DB，否则后台任务的独立 session 会因为
    # 外键约束等待主 session 释放锁，导致 MySQL lock timeout
    await db.commit()

    # 后台启动分析 — 使用 asyncio.create_task 而非 BackgroundTasks，
    # 因为 BackgroundTasks 在 reload 模式下可能被中断
    import asyncio
    asyncio.create_task(
        _run_import_and_analyze(aid, project_name, source_type, source_url, file_bytes, file_name)
    )

    return {
        "project_id": str(project.id),
        "analysis_id": aid,
        "status": "pending",
    }


async def _run_import_and_analyze(
    analysis_id_str: str,
    project_name: str,
    source_type: str,
    source_url: str,
    file_bytes: bytes | None,
    file_name: str | None,
    reuse_storage_path: str = "",  # 重新分析时复用已有路径
):
    """导入 + 分析完整流程（独立 DB session）"""
    from app.db.database import async_session
    import traceback, logging
    logger = logging.getLogger("poltai")

    analysis_id = uuid.UUID(analysis_id_str)
    tmpdir = ""
    is_reuse = bool(reuse_storage_path)
    try:
        if is_reuse:
            # 重新分析：跳过导入，直接使用已有源码
            tmpdir = reuse_storage_path
            progress_manager.update(
                analysis_id, Step.EXTRACTING, 5,
                f"项目已就绪（复用已有源码）: {project_name}",
                tmpdir,
            )
        else:
            # Step 1: 导入
            progress_manager.update(
                analysis_id, Step.CLONING, 2,
                "正在获取项目源码...",
            )

            if source_type == "github" and source_url:
                tmpdir = await import_service.import_from_github(source_url)
            elif file_bytes and file_name:
                upload_dir = Path(settings.upload_dir)
                upload_dir.mkdir(exist_ok=True)
                tmp_path = upload_dir / f"{analysis_id}.zip"
                tmp_path.write_bytes(file_bytes)
                tmpdir = await import_service.import_from_upload(str(tmp_path))

            if not tmpdir:
                raise RuntimeError("无法获取项目源码")

            progress_manager.update(
                analysis_id, Step.EXTRACTING, 5,
                f"项目已导入: {project_name}",
                tmpdir,
            )

        # Step 2: 分析（带进度回调 + 独立 DB session）
        async def on_progress(aid, status, pct, msg, detail=""):
            step_map = {
                "pending": Step.INIT,
                "parsing": Step.PARSING,
                "analyzing": Step.ANALYZING,
                "building": Step.BUILDING,
                "completed": Step.COMPLETED,
                "failed": Step.FAILED,
            }
            sv = status.value if hasattr(status, "value") else status
            step = step_map.get(sv, Step.ANALYZING)
            progress_manager.update(analysis_id, step, pct, msg, detail)

        async with async_session() as db:
            await run_analysis(db, analysis_id, project_name, tmpdir, on_progress)
            await db.commit()

        progress_manager.update(
            analysis_id, Step.COMPLETED, 100,
            "分析完成",
        )

    except Exception as e:
        logger.error(f"Analysis {analysis_id_str} failed: {e}\n{traceback.format_exc()}")
        progress_manager.fail(analysis_id, str(e))
        # 同步更新 DB 状态为 failed，避免前端轮询永远看不到结果
        try:
            async with async_session() as fail_db:
                await AnalysisRepo.update_status(
                    fail_db, str(analysis_id), "failed", 0, str(e),
                )
                await fail_db.commit()
        except Exception:
            pass  # DB 更新失败不掩盖原始错误
    finally:
        # 仅清理临时导入的目录，复用目录不删除
        if tmpdir and not is_reuse:
            import_service.cleanup(tmpdir)


# ═══════════════════════════════════════════
# Analysis / Progress
# ═══════════════════════════════════════════

@router.get("/analyses/{analysis_id}")
async def get_analysis(analysis_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select, func
    aid = str(analysis_id)
    a = await AnalysisRepo.get(db, aid)
    if not a:
        raise HTTPException(404, "分析不存在")
    # 单独查询文件数量，避免 relationship lazy-load 在 async 下触发 MissingGreenlet
    result = await db.execute(
        select(func.count(FileNode.id)).where(FileNode.analysis_id == aid)
    )
    file_count = result.scalar() or 0
    return {
        "id": str(a.id),
        "status": a.status,
        "progress_pct": a.progress_pct,
        "file_count": file_count,
        "error_message": a.error_message,
    }


@router.get("/analyses/{analysis_id}/stream")
async def stream_progress(analysis_id: uuid.UUID):
    """SSE 进度流 — 使用 ProgressManager 的订阅机制"""
    q = await progress_manager.subscribe(analysis_id)

    async def generate():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=30)
                    yield f"data: {json.dumps(event)}\n\n"
                    if event.get("status") in ("completed", "failed"):
                        break
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            progress_manager.unsubscribe(analysis_id, q)

    return StreamingResponse(generate(), media_type="text/event-stream")


# ═══════════════════════════════════════════
# Re-Analysis
# ═══════════════════════════════════════════

@router.post("/analyses/{analysis_id}/reanalyze")
async def reanalyze_project(analysis_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """触发重新分析 — 基于已有项目创建新分析，支持增量重新识别"""
    aid = str(analysis_id)
    a = await AnalysisRepo.get(db, aid)
    if not a:
        raise HTTPException(404, "分析不存在")

    # 获取关联的 project
    project = await ProjectRepo.get(db, a.project_id)
    if not project:
        raise HTTPException(404, "项目不存在")

    # 检查项目存储路径是否存在
    from pathlib import Path
    storage_path = project.storage_path
    if not storage_path or not Path(storage_path).exists():
        raise HTTPException(400, "项目源码已过期，请重新导入")

    # 创建新的 analysis 记录
    new_analysis = await AnalysisRepo.create(db, project.id)
    new_aid = str(new_analysis.id)
    await db.commit()

    # 后台启动重新分析（复用已有源码路径）
    import asyncio
    asyncio.create_task(
        _run_import_and_analyze(
            new_aid, project.name,
            project.source_type, project.source_url or "",
            None, None,
            reuse_storage_path=storage_path,
        )
    )

    return {
        "analysis_id": new_aid,
        "project_id": str(project.id),
        "status": "pending",
        "message": "已创建重新分析任务",
    }


# ═══════════════════════════════════════════
# Graph
# ═══════════════════════════════════════════

@router.get("/analyses/{analysis_id}/graph")
async def get_graph(analysis_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    aid = str(analysis_id)
    a = await AnalysisRepo.get(db, aid)
    if not a:
        raise HTTPException(404, "分析不存在")

    nodes_raw = await FileNodeRepo.get_by_analysis(db, aid)
    edges_raw = await DataEdgeRepo.get_by_analysis(db, aid)

    nodes = []
    for n in nodes_raw:
        # Build function nodes from functions_json (deterministic IDs)
        functions = []
        for fn in (n.functions_json or []):
            fn_name = fn.get("name", "?")
            functions.append({
                "id": make_fn_id(n.file_path, fn_name),
                "name": fn_name,
                "params": fn.get("params", []),
                "return_type": fn.get("return_type", "unknown"),
                "is_exported": fn.get("is_exported", False),
                "is_async": fn.get("is_async", False),
                "description": fn.get("description", ""),
            })

        # Build class nodes from classes_json
        classes = []
        for cls in (n.classes_json or []):
            cls_name = cls.get("name", "?")
            methods = []
            for m in (cls.get("methods") or []):
                m_name = m.get("name", "?")
                methods.append({
                    "id": make_method_id(n.file_path, cls_name, m_name),
                    "name": m_name,
                    "params": m.get("params", []),
                    "return_type": m.get("return_type", "unknown"),
                    "is_exported": m.get("is_exported", False),
                    "is_async": m.get("is_async", False),
                    "description": m.get("description", ""),
                })
            classes.append({
                "id": make_class_id(n.file_path, cls_name),
                "name": cls_name,
                "is_exported": cls.get("is_exported", False),
                "methods": methods,
            })

        # Extract folder path from file_path (parent directory)
        folder_path = str(Path(n.file_path).parent) if n.file_path else ""

        nodes.append({
            "id": str(n.id),
            "file_path": n.file_path,
            "file_name": n.file_name,
            "folder_path": folder_path,
            "language": n.language,
            "summary": n.summary or "",
            "detail": n.detail_explain or "",
            "architecture_role": "",
            "ports": _build_ports(n.imports_json, n.exports_json, n.functions_json, n.classes_json),
            "functions": functions,
            "classes": classes,
        })

    edges = []
    for e in edges_raw:
        meta = e.metadata_json or {}
        var_name = e.variable_name or ""
        edge_type = e.edge_type or "import"
        # 优先使用 GraphBuilder 持久化的真实端口 ID；别名导入时源/目标端口名可能不同。
        if e.from_port_name or e.to_port_name:
            source_port_id = e.from_port_name
            target_port_id = e.to_port_name or ""
        elif edge_type == "import" and var_name:
            source_port_id = f"port-output-{var_name}"
            target_port_id = f"port-input-{var_name}"
        else:
            source_port_id = ""
            target_port_id = ""
        edges.append({
            "id": str(e.id),
            "source_node_id": str(e.from_file_id),
            "target_node_id": str(e.to_file_id),
            "source_port_id": source_port_id,
            "target_port_id": target_port_id,
            "source_function_id": meta.get("source_function_id", ""),
            "target_function_id": meta.get("target_function_id", ""),
            "variable_name": var_name,
            "data_type": e.data_type or "unknown",
            "edge_type": edge_type,
            "label": f"{var_name}: {e.data_type}" if var_name else "",
        })

    # 计算入口/出口
    in_deg: dict[str, int] = {}
    out_deg: dict[str, int] = {}
    for e in edges:
        out_deg[e["source_node_id"]] = out_deg.get(e["source_node_id"], 0) + 1
        in_deg[e["target_node_id"]] = in_deg.get(e["target_node_id"], 0) + 1

    entry_points = [
        n["id"] for n in nodes
        if in_deg.get(n["id"], 0) == 0 and out_deg.get(n["id"], 0) > 0
    ]
    exit_points = [
        n["id"] for n in nodes
        if out_deg.get(n["id"], 0) == 0 and in_deg.get(n["id"], 0) > 0
    ]

    # 构建文件夹列表
    folder_map: dict[str, dict] = {}
    for n in nodes:
        fp = n.get("folder_path", "")
        if fp not in folder_map:
            folder_map[fp] = {"path": fp, "name": Path(fp).name or fp or "(root)", "file_count": 0}
        folder_map[fp]["file_count"] += 1
    folders = sorted(folder_map.values(), key=lambda f: f["path"])

    return {
        "nodes": nodes,
        "edges": edges,
        "folders": folders,
        "entry_points": entry_points,
        "exit_points": exit_points,
    }


def _build_ports(imports_json, exports_json, functions_json, classes_json=None):
    """从 DB JSON 字段构建端口列表 — 使用确定性 ID 以便边能精确匹配"""
    ports = []
    port_keys = set()

    def add_port(name, port_type, data_type, direction, description=""):
        if not name:
            return
        key = (direction, name)
        if key in port_keys:
            return
        port_keys.add(key)
        ports.append({
            "id": f"port-{direction}-{name}",
            "name": name,
            "port_type": port_type,
            "data_type": data_type or "unknown",
            "direction": direction,
            "description": description,
        })

    for imp in (imports_json or []):
        name = imp.get("name", "?")
        add_port(
            name,
            "function" if imp.get("is_function") else "variable",
            imp.get("type", "unknown"),
            "input",
            imp.get("description", imp.get("source", "")),
        )
    for exp in (exports_json or []):
        name = exp.get("name", "?")
        add_port(
            name,
            "function" if exp.get("is_function") else "variable",
            exp.get("type", "unknown"),
            "output",
            exp.get("description", ""),
        )
    for fn in (functions_json or []):
        for param in (fn.get("params") or []):
            add_port(
                param.get("name", ""),
                "param",
                param.get("type", "unknown"),
                "input",
                f"{fn.get('name', '?')}() 参数",
            )
    for cls in (classes_json or []):
        cls_name = cls.get("name", "?")
        for method in (cls.get("methods") or []):
            for param in (method.get("params") or []):
                add_port(
                    param.get("name", ""),
                    "param",
                    param.get("type", "unknown"),
                    "input",
                    f"{cls_name}.{method.get('name', '?')}() 参数",
                )
    return ports


# ═══════════════════════════════════════════
# File Detail
# ═══════════════════════════════════════════

@router.get("/analyses/{analysis_id}/files/{file_id}")
async def get_file_detail(
    analysis_id: uuid.UUID, file_id: uuid.UUID, db: AsyncSession = Depends(get_db),
):
    aid = str(analysis_id)
    fid = str(file_id)
    node = await FileNodeRepo.get(db, fid)
    if not node or node.analysis_id != aid:
        raise HTTPException(404, "文件不存在")

    return {
        "file_path": node.file_path,
        "file_name": node.file_name,
        "language": node.language,
        "summary": node.summary or "",
        "detail": node.detail_explain or "",
        "inputs": node.imports_json or [],
        "outputs": node.exports_json or [],
        "internal_structures": [],
        "architecture_role": "",
        "dependencies_summary": "",
    }


# ═══════════════════════════════════════════
# Chat Sessions
# ═══════════════════════════════════════════

@router.get("/analyses/{analysis_id}/chat/sessions")
async def list_chat_sessions(analysis_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """列出某个分析下的所有对话会话"""
    aid = str(analysis_id)
    a = await AnalysisRepo.get(db, aid)
    if not a:
        raise HTTPException(404, "分析不存在")
    sessions = await ChatRepo.list_sessions(db, aid)
    return [
        {
            "session_id": str(s.id),
            "title": s.title or "新对话",
            "created_at": s.created_at.isoformat() if s.created_at else "",
        }
        for s in sessions
    ]


@router.get("/analyses/{analysis_id}/chat/{session_id}")
async def get_chat_history(
    analysis_id: uuid.UUID, session_id: uuid.UUID, db: AsyncSession = Depends(get_db),
):
    """获取某个对话会话的完整消息历史"""
    sid = str(session_id)
    messages = await ChatRepo.get_messages(db, sid)
    return [
        {
            "id": str(m.id),
            "role": m.role,
            "content": m.content,
            "referenced_nodes": m.referenced_nodes or [],
            "created_at": m.created_at.isoformat() if m.created_at else "",
        }
        for m in messages
    ]


# ═══════════════════════════════════════════
# Report
# ═══════════════════════════════════════════

@router.get("/analyses/{analysis_id}/report")
async def get_report(analysis_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    report = await ReportRepo.get(db, str(analysis_id))
    if not report:
        raise HTTPException(404, "报告尚未生成")
    return {
        "content_md": report.content_md,
        "architecture_summary": report.architecture_summary,
        "issue_count": report.issue_count,
    }


# ═══════════════════════════════════════════
# Chat
# ═══════════════════════════════════════════

class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str


@router.post("/analyses/{analysis_id}/chat")
async def chat(
    analysis_id: uuid.UUID,
    req: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """智能问答 — 基于 RAG 检索增强"""
    # 获取或创建会话
    session_id = uuid.UUID(req.session_id) if req.session_id else None
    session = await ChatRepo.get_or_create_session(db, analysis_id, session_id)

    # 保存用户消息
    await ChatRepo.add_message(db, session.id, "user", req.message)

    # 获取所有分析数据
    aid = str(analysis_id)
    nodes_raw = await FileNodeRepo.get_by_analysis(db, aid)
    edges_raw = await DataEdgeRepo.get_by_analysis(db, aid)

    # 转为 dict 列表
    nodes_data = []
    for n in nodes_raw:
        nodes_data.append({
            "id": str(n.id),
            "file_path": n.file_path,
            "file_name": n.file_name,
            "summary": n.summary or "",
            "detail": n.detail_explain or "",
            "architecture_role": "",
            "imports_json": n.imports_json or [],
            "exports_json": n.exports_json or [],
        })

    edges_data = []
    for e in edges_raw:
        edges_data.append({
            "source_node_id": str(e.from_file_id),
            "target_node_id": str(e.to_file_id),
            "variable_name": e.variable_name,
            "data_type": e.data_type,
        })

    # RAG 上下文构建
    context = rag_service.build_context(req.message, nodes_data, edges_data)

    # 获取历史消息
    history = await ChatRepo.get_messages(db, session.id)
    chat_history = [
        {"role": h.role, "content": h.content}
        for h in history[-10:]
    ]

    # 调用 AI
    from app.core.ai_engine import ai_engine
    try:
        reply = await ai_engine.chat(req.message, context, chat_history)
    except Exception:
        reply = "AI 服务暂时不可用，请检查 API Key 配置。"

    # 保存回复
    await ChatRepo.add_message(db, session.id, "assistant", reply)

    return {
        "session_id": str(session.id),
        "reply": reply,
        "referenced": [],
    }


@router.post("/analyses/{analysis_id}/chat/stream")
async def chat_stream(
    analysis_id: uuid.UUID,
    req: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """流式智能问答 — SSE streaming 响应"""
    session_id = uuid.UUID(req.session_id) if req.session_id else None
    session = await ChatRepo.get_or_create_session(db, analysis_id, session_id)

    # 保存用户消息
    await ChatRepo.add_message(db, session.id, "user", req.message)

    # 获取分析数据 + RAG 上下文
    aid = str(analysis_id)
    nodes_raw = await FileNodeRepo.get_by_analysis(db, aid)
    edges_raw = await DataEdgeRepo.get_by_analysis(db, aid)

    nodes_data = [
        {
            "id": str(n.id), "file_path": n.file_path,
            "file_name": n.file_name, "summary": n.summary or "",
            "detail": n.detail_explain or "", "architecture_role": "",
            "imports_json": n.imports_json or [], "exports_json": n.exports_json or [],
        }
        for n in nodes_raw
    ]
    edges_data = [
        {
            "source_node_id": str(e.from_file_id),
            "target_node_id": str(e.to_file_id),
            "variable_name": e.variable_name, "data_type": e.data_type,
        }
        for e in edges_raw
    ]

    context = rag_service.build_context(req.message, nodes_data, edges_data)
    history = await ChatRepo.get_messages(db, session.id)
    chat_history = [{"role": h.role, "content": h.content} for h in history[-10:]]
    await db.commit()

    from app.core.ai_engine import ai_engine

    async def generate():
        full_reply = ""
        try:
            async for sse_data in ai_engine.stream_chat(req.message, context, chat_history):
                # Accumulate full reply for saving
                for line in sse_data.strip().split("\n"):
                    if line.startswith("data: "):
                        try:
                            evt = json.loads(line[6:])
                            if evt.get("type") == "chunk":
                                full_reply += evt.get("delta", "")
                        except (json.JSONDecodeError, KeyError):
                            pass
                yield sse_data
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

        # 保存助手回复
        if full_reply:
            try:
                from app.db.database import async_session
                async with async_session() as save_db:
                    await ChatRepo.add_message(save_db, session.id, "assistant", full_reply)
                    await save_db.commit()
            except Exception:
                pass

    return StreamingResponse(generate(), media_type="text/event-stream")


# ═══════════════════════════════════════════
# Graph Export (GraphML)
# ═══════════════════════════════════════════

@router.get("/analyses/{analysis_id}/graph/export/graphml")
async def export_graph_graphml(analysis_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """导出 GraphML 格式（兼容 Gephi/yEd/NetworkX）"""
    aid = str(analysis_id)
    a = await AnalysisRepo.get(db, aid)
    if not a:
        raise HTTPException(404, "分析不存在")

    nodes_raw = await FileNodeRepo.get_by_analysis(db, aid)
    edges_raw = await DataEdgeRepo.get_by_analysis(db, aid)

    # 构建 DataFlowGraph
    from app.models.schemas import DataFlowGraph, GraphNode, GraphEdge, EdgeType
    nodes = []
    for n in nodes_raw:
        functions = []
        for fn in (n.functions_json or []):
            functions.append({
                "id": make_fn_id(n.file_path, fn.get("name", "?")),
                "name": fn.get("name", "?"),
                "params": fn.get("params", []),
                "return_type": fn.get("return_type", "unknown"),
                "is_exported": fn.get("is_exported", False),
                "is_async": fn.get("is_async", False),
                "description": fn.get("description", ""),
            })
        classes = []
        for cls in (n.classes_json or []):
            cls_name = cls.get("name", "?")
            methods = []
            for m in (cls.get("methods") or []):
                methods.append({
                    "id": make_method_id(n.file_path, cls_name, m.get("name", "?")),
                    "name": m.get("name", "?"),
                    "params": m.get("params", []),
                    "return_type": m.get("return_type", "unknown"),
                    "is_exported": m.get("is_exported", False),
                    "is_async": m.get("is_async", False),
                    "description": m.get("description", ""),
                })
            classes.append({
                "id": make_class_id(n.file_path, cls_name),
                "name": cls_name,
                "is_exported": cls.get("is_exported", False),
                "methods": methods,
            })
        nodes.append(GraphNode(
            id=str(n.id),
            file_path=n.file_path,
            file_name=n.file_name,
            language=n.language,
            summary=n.summary or "",
            architecture_role=n.architecture_role or "",
            functions=functions,
            classes=classes,
        ))

    edges = []
    for e in edges_raw:
        edge_type_str = e.edge_type or "import"
        try:
            edge_type = EdgeType(edge_type_str)
        except ValueError:
            edge_type = EdgeType.IMPORT
        edges.append(GraphEdge(
            id=str(e.id),
            source_node_id=str(e.from_file_id),
            target_node_id=str(e.to_file_id),
            variable_name=e.variable_name or "",
            data_type=e.data_type or "unknown",
            edge_type=edge_type,
            label=e.variable_name or "",
        ))

    graph = DataFlowGraph(nodes=nodes, edges=edges, entry_points=[], exit_points=[])
    project = await ProjectRepo.get(db, a.project_id)
    project_name = project.name if project else "PoltAIshow"

    graphml_content = export_graphml(graph, project_name)

    from fastapi.responses import Response
    return Response(
        content=graphml_content,
        media_type="application/xml",
        headers={"Content-Disposition": f"attachment; filename={project_name}_graph.graphml"},
    )


@router.get("/analyses/{analysis_id}/graph/export/html")
async def export_graph_html(analysis_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """导出自包含 HTML 可视化（零依赖，可离线查看）"""
    aid = str(analysis_id)
    a = await AnalysisRepo.get(db, aid)
    if not a:
        raise HTTPException(404, "分析不存在")

    nodes_raw = await FileNodeRepo.get_by_analysis(db, aid)
    edges_raw = await DataEdgeRepo.get_by_analysis(db, aid)

    # 构建 DataFlowGraph（简化版，只需基本信息）
    from app.models.schemas import DataFlowGraph, GraphNode, GraphEdge, EdgeType
    nodes = [
        GraphNode(
            id=str(n.id),
            file_path=n.file_path,
            file_name=n.file_name,
            language=n.language,
            summary=n.summary or "",
            architecture_role=n.architecture_role or "",
            functions=[{"id": f"fn_{i}", "name": fn.get("name", "?"), "params": [], "return_type": "", "is_exported": False, "is_async": False, "description": ""} for i, fn in enumerate(n.functions_json or [])],
            classes=[{"id": f"cls_{i}", "name": cls.get("name", "?"), "is_exported": False, "methods": []} for i, cls in enumerate(n.classes_json or [])],
        )
        for n in nodes_raw
    ]
    edges = [
        GraphEdge(
            id=str(e.id),
            source_node_id=str(e.from_file_id),
            target_node_id=str(e.to_file_id),
            variable_name=e.variable_name or "",
            data_type=e.data_type or "unknown",
            edge_type=EdgeType(e.edge_type) if e.edge_type else EdgeType.IMPORT,
            label=e.variable_name or "",
        )
        for e in edges_raw
    ]

    graph = DataFlowGraph(nodes=nodes, edges=edges, entry_points=[], exit_points=[])
    project = await ProjectRepo.get(db, a.project_id)
    project_name = project.name if project else "PoltAIshow"

    html_content = export_html(graph, project_name)

    from fastapi.responses import Response
    return Response(
        content=html_content,
        media_type="text/html",
        headers={"Content-Disposition": f"attachment; filename={project_name}_graph.html"},
    )


# ═══════════════════════════════════════════
# Change Impact Analysis
# ═══════════════════════════════════════════

@router.get("/analyses/{analysis_id}/impact/{node_id}")
async def get_change_impact(
    analysis_id: uuid.UUID, node_id: str, db: AsyncSession = Depends(get_db)
):
    """变更影响分析: 返回修改该文件会影响的所有文件 + 风险评分"""
    aid = str(analysis_id)
    a = await AnalysisRepo.get(db, aid)
    if not a:
        raise HTTPException(404, "分析不存在")

    nodes_raw = await FileNodeRepo.get_by_analysis(db, aid)
    edges_raw = await DataEdgeRepo.get_by_analysis(db, aid)

    # 构建简化的 GraphNode/GraphEdge
    from app.models.schemas import GraphNode, GraphEdge, EdgeType
    nodes = [
        GraphNode(
            id=str(n.id),
            file_path=n.file_path,
            file_name=n.file_name,
            language=n.language,
            summary=n.summary or "",
            architecture_role=n.architecture_role or "",
            functions=[],
            classes=[],
        )
        for n in nodes_raw
    ]
    edges = [
        GraphEdge(
            id=str(e.id),
            source_node_id=str(e.from_file_id),
            target_node_id=str(e.to_file_id),
            variable_name=e.variable_name or "",
            data_type=e.data_type or "unknown",
            edge_type=EdgeType(e.edge_type) if e.edge_type else EdgeType.IMPORT,
            label=e.variable_name or "",
        )
        for e in edges_raw
    ]

    impact = analyze_impact(node_id, nodes, edges)

    return {
        "source_node_id": node_id,
        "affected_count": len(impact),
        "affected_files": impact,
    }


# ═══════════════════════════════════════════
# Control Flow Graph (CFG) Generation
# ═══════════════════════════════════════════

@router.post("/cfg/generate")
async def generate_control_flow_graph(
    source_code: str,
    function_name: str,
    language: str,
):
    """生成函数内部控制流图（DOT 格式）

    支持 Python 和 TypeScript/JavaScript。
    返回 DOT 格式，可用 Graphviz 渲染为 SVG/PNG。
    """
    dot_content = generate_cfg(source_code, function_name, language)

    from fastapi.responses import Response
    return Response(
        content=dot_content,
        media_type="text/plain",
        headers={"Content-Disposition": f"attachment; filename={function_name}_cfg.dot"},
    )


