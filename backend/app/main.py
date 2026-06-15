from __future__ import annotations

import asyncio
import json
import shutil
import tarfile
import tempfile
import zipfile
from pathlib import Path
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .analyzer import resolve_source_path, run_analysis
from .llm import LlmCallError, LlmConfigError, chat_text
from .state import app_state


app = FastAPI(title="PoltAIshow API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ImportRequest(BaseModel):
    source_type: str = "local"
    source_url: str


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str
    selected_symbol_ids: list[str] = Field(default_factory=list)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/v1/projects")
def list_projects() -> list[dict]:
    payload = []
    for project in app_state.list_projects():
        latest = None
        if project.analysis_ids:
            analysis = app_state.get_analysis(project.analysis_ids[-1])
            if analysis is not None:
                latest = {
                    "analysis_id": analysis.analysis_id,
                    "status": analysis.status,
                    "progress_pct": analysis.progress_pct,
                    "error_message": analysis.error_message,
                }
        payload.append(
            {
                "project_id": project.project_id,
                "name": project.name,
                "source_type": project.source_type,
                "source_url": project.source_url,
                "file_count": app_state.get_analysis(project.analysis_ids[-1]).file_count
                if project.analysis_ids and app_state.get_analysis(project.analysis_ids[-1])
                else 0,
                "created_at": project.created_at.isoformat(),
                "latest_analysis": latest,
            }
        )
    return payload


@app.delete("/api/v1/projects/{project_id}")
def delete_project(project_id: str) -> dict:
    if not app_state.delete_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    return {"status": "deleted", "project_id": project_id}


@app.post("/api/v1/projects/import")
def import_project(request: ImportRequest, background_tasks: BackgroundTasks) -> dict:
    try:
        source_path = resolve_source_path(request.source_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    record = app_state.create_analysis(
        source_path=source_path,
        source_type=request.source_type,
        source_url=request.source_url,
        project_name=source_path.name,
    )
    background_tasks.add_task(run_analysis, record)
    return {
        "project_id": record.project_id,
        "analysis_id": record.analysis_id,
        "status": record.status,
    }


@app.post("/api/v1/projects/import/upload")
async def upload_project(file: UploadFile = File(...), background_tasks: BackgroundTasks = None) -> dict:
    if background_tasks is None:
        background_tasks = BackgroundTasks()
    temp_root = Path(tempfile.mkdtemp(prefix="poltaishow-upload-"))
    archive_path = temp_root / (file.filename or f"upload-{uuid4().hex}.zip")
    with archive_path.open("wb") as handle:
        shutil.copyfileobj(file.file, handle)
    source_path = _extract_archive(archive_path, temp_root)
    record = app_state.create_analysis(
        source_path=source_path,
        source_type="upload",
        source_url=file.filename or str(archive_path),
        project_name=source_path.name,
    )
    background_tasks.add_task(run_analysis, record)
    return {"project_id": record.project_id, "analysis_id": record.analysis_id, "status": record.status}


@app.get("/api/v1/analyses/{analysis_id}")
def get_analysis(analysis_id: str) -> dict:
    analysis = _get_analysis_or_404(analysis_id)
    return {
        "id": analysis.analysis_id,
        "status": analysis.status,
        "progress_pct": analysis.progress_pct,
        "file_count": analysis.file_count,
        "error_message": analysis.error_message,
    }


@app.get("/api/v1/analyses/{analysis_id}/stream")
async def stream_analysis(analysis_id: str) -> StreamingResponse:
    _get_analysis_or_404(analysis_id)

    async def events():
        last_payload = None
        while True:
            analysis = app_state.get_analysis(analysis_id)
            if analysis is None:
                break
            payload = analysis.progress_event()
            encoded = json.dumps(payload, ensure_ascii=False)
            if encoded != last_payload:
                yield f"data: {encoded}\n\n"
                last_payload = encoded
            if analysis.status in {"completed", "failed"}:
                break
            await asyncio.sleep(0.2)

    return StreamingResponse(events(), media_type="text/event-stream")


@app.get("/api/v1/analyses/{analysis_id}/graph")
def get_graph(analysis_id: str) -> dict:
    analysis = _get_analysis_or_404(analysis_id)
    if analysis.frontend_graph is None:
        raise HTTPException(status_code=409, detail="Analysis graph is not ready")
    return analysis.frontend_graph


@app.get("/api/v1/analyses/{analysis_id}/files/{file_id}")
def get_file_detail(analysis_id: str, file_id: str) -> dict:
    analysis = _get_analysis_or_404(analysis_id)
    detail = analysis.file_details.get(file_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="File node not found")
    return detail


@app.get("/api/v1/analyses/{analysis_id}/source")
def get_source(
    analysis_id: str,
    file_path: str = Query(..., min_length=1),
    start_line: int | None = Query(None, ge=1),
    end_line: int | None = Query(None, ge=1),
) -> dict:
    analysis = _get_analysis_or_404(analysis_id)
    if analysis.graph is None:
        raise HTTPException(status_code=409, detail="Analysis graph is not ready")

    resolved_path = _resolve_analyzed_file(analysis, file_path)
    try:
        content = resolved_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise HTTPException(status_code=404, detail=f"Could not read source file: {exc}") from exc

    lines = content.splitlines()
    total_lines = len(lines)
    normalized_start = max(1, start_line or 1)
    normalized_end = min(total_lines, end_line or total_lines)
    if normalized_end < normalized_start:
        normalized_end = normalized_start

    return {
        "file_path": str(resolved_path),
        "language": _language_from_path(resolved_path),
        "start_line": normalized_start,
        "end_line": normalized_end,
        "total_lines": total_lines,
        "content": content,
    }


@app.get("/api/v1/analyses/{analysis_id}/report")
def get_report(analysis_id: str) -> dict:
    analysis = _get_analysis_or_404(analysis_id)
    return {
        "content_md": analysis.report_md or "# Project Analysis Report\n\nAnalysis is not ready.",
        "architecture_summary": "Static project graph summary",
        "issue_count": len(analysis.graph.warnings) if analysis.graph else 0,
    }


@app.post("/api/v1/analyses/{analysis_id}/reanalyze")
def reanalyze(analysis_id: str, background_tasks: BackgroundTasks) -> dict:
    analysis = _get_analysis_or_404(analysis_id)
    analysis.graph = None
    analysis.frontend_graph = None
    analysis.file_details = {}
    analysis.report_md = ""
    analysis.error_message = ""
    app_state.update_progress(
        analysis_id,
        status="pending",
        progress_pct=0,
        message="Queued for re-analysis",
    )
    background_tasks.add_task(run_analysis, analysis)
    return {"status": "queued", "analysis_id": analysis_id}


@app.post("/api/v1/analyses/{analysis_id}/chat")
def chat(analysis_id: str, request: ChatRequest) -> dict:
    analysis = _get_analysis_or_404(analysis_id)
    reply = answer_question(analysis, request.message, request.selected_symbol_ids)
    return {
        "session_id": request.session_id or uuid4().hex,
        "reply": reply,
        "referenced": request.selected_symbol_ids,
    }


@app.post("/api/v1/analyses/{analysis_id}/chat/stream")
async def chat_stream(analysis_id: str, request: ChatRequest) -> StreamingResponse:
    analysis = _get_analysis_or_404(analysis_id)
    reply = answer_question(analysis, request.message, request.selected_symbol_ids)

    async def events():
        for chunk in _chunk_text(reply, 80):
            yield f"data: {json.dumps({'type': 'chunk', 'delta': chunk}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.01)
        yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")


def answer_question(analysis, message: str, selected_symbol_ids: list[str] | None = None) -> str:
    graph = analysis.graph
    frontend_graph = analysis.frontend_graph
    if graph is None or frontend_graph is None:
        return "Analysis is not ready yet."

    selected_context = _selected_symbol_context(graph, selected_symbol_ids or [])
    local_answer = _local_answer(analysis, message, selected_context)
    llm_answer = _try_llm_answer(message, local_answer, selected_context)
    if llm_answer:
        return llm_answer
    return local_answer


def _local_answer(analysis, message: str, selected_context: str = "") -> str:
    graph = analysis.graph
    frontend_graph = analysis.frontend_graph
    if graph is None or frontend_graph is None:
        return "Analysis is not ready yet."

    if selected_context:
        return selected_context

    lower = message.lower()
    if any(word in lower for word in ["function", "函数", "方法", "method"]):
        top = "\n".join(
            f"- `{symbol.qualified_name}` in `{Path(symbol.file_path).name}`"
            for symbol in graph.symbols[:30]
        )
        return f"这个项目目前识别到 {len(graph.symbols)} 个函数/类/方法符号。前 30 个是：\n\n{top}"
    if any(word in lower for word in ["edge", "调用", "传值", "flow", "关系"]):
        resolved = [edge for edge in graph.edges if edge.target_symbol_id]
        return (
            f"这个项目目前有 {len(graph.edges)} 条静态关系边，其中 {len(resolved)} 条能解析到目标符号。"
            "边类型包括 contains、call、arg、return 和 unresolved_call。"
        )
    if any(word in lower for word in ["file", "文件", "模块"]):
        files = "\n".join(f"- `{node['file_path']}`: {node['summary']}" for node in frontend_graph["nodes"][:30])
        return f"这次分析覆盖 {len(frontend_graph['nodes'])} 个文件：\n\n{files}"

    stats = graph.scan_stats
    return (
        "DeepSeek 未配置或本次调用失败，我现在先基于静态分析图回答。"
        f"\n\n项目根目录：`{graph.project_root}`"
        f"\n解析文件：{stats.files_parsed if stats else len(frontend_graph['nodes'])}"
        f"\n符号数量：{len(graph.symbols)}"
        f"\n关系边数量：{len(graph.edges)}"
        "\n\n你可以问：有哪些函数、哪些文件、调用关系/传值关系是什么。"
    )


def _try_llm_answer(message: str, local_context: str, selected_context: str = "") -> str | None:
    prompt = _llm_prompt(message, local_context, selected_context)
    try:
        return chat_text(
            [
                {
                    "role": "system",
                    "content": (
                        "你是 PoltAIshow 的项目代码分析助手。"
                        "只能基于提供的静态分析上下文回答；不要编造不存在的代码。"
                        "如果上下文不足，要直接说明缺口和下一步需要查看的符号。"
                        "回答要中文、具体、偏工程判断。"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=1800,
        )
    except (LlmConfigError, LlmCallError):
        return None


def _llm_prompt(message: str, local_context: str, selected_context: str = "") -> str:
    context_title = "选区上下文" if selected_context else "项目静态分析上下文"
    return (
        f"用户问题：\n{message.strip()}\n\n"
        f"{context_title}：\n{local_context[:12000]}\n\n"
        "请基于上面的函数/类/方法、调用、传参、返回关系回答。"
    )


def _selected_symbol_context(graph, selected_symbol_ids: list[str]) -> str:
    selected_ids = list(dict.fromkeys(selected_symbol_ids))
    if not selected_ids:
        return ""

    symbol_by_id = {symbol.symbol_id: symbol for symbol in graph.symbols}
    selected_symbols = [symbol_by_id[symbol_id] for symbol_id in selected_ids if symbol_id in symbol_by_id]
    if not selected_symbols:
        return "当前选区没有匹配到后端分析图里的符号，可能是前端图已经刷新过。"

    selected_set = {symbol.symbol_id for symbol in selected_symbols}
    internal_edges = [
        edge
        for edge in graph.edges
        if edge.target_symbol_id
        and edge.source_symbol_id in selected_set
        and edge.target_symbol_id in selected_set
    ]
    neighbor_edges = [
        edge
        for edge in graph.edges
        if edge.target_symbol_id
        and (
            edge.source_symbol_id in selected_set
            or edge.target_symbol_id in selected_set
        )
    ]

    lines = [
        f"当前选中了 {len(selected_symbols)} 个符号。我先基于静态分析图给出选区上下文：",
        "",
        "## 符号",
    ]
    for symbol in selected_symbols[:30]:
        lines.append(
            f"- `{symbol.qualified_name}` ({symbol.kind.value}, {symbol.language.value}) "
            f"in `{Path(symbol.file_path).name}:{symbol.start_line}-{symbol.end_line}`"
        )

    lines.extend(["", "## 选区内部关系"])
    if internal_edges:
        lines.extend(_edge_context_lines(internal_edges, symbol_by_id, limit=40))
    else:
        lines.append("- 这些符号之间没有解析到直接边；下面给出它们和外部符号的相邻关系。")

    lines.extend(["", "## 相邻关系"])
    if neighbor_edges:
        lines.extend(_edge_context_lines(neighbor_edges, symbol_by_id, limit=60))
    else:
        lines.append("- 没有解析到相邻调用/传参/返回关系。")

    lines.extend(
        [
            "",
            "说明：现在展示的是静态表达式级传值，比如 `实参 -> 形参`、`return -> 接收变量`；真实运行时数值变化需要后续接入执行 tracing 或测试采样。",
        ]
    )
    return "\n".join(lines)


def _edge_context_lines(edges, symbol_by_id: dict, *, limit: int) -> list[str]:
    lines = []
    for edge in edges[:limit]:
        source = symbol_by_id.get(edge.source_symbol_id)
        target = symbol_by_id.get(edge.target_symbol_id) if edge.target_symbol_id else None
        source_name = source.qualified_name if source else edge.source_symbol_id
        target_name = target.qualified_name if target else edge.target_symbol_id or "<unresolved>"
        slot = ""
        if edge.source_slot or edge.target_slot:
            slot = f" | `{edge.source_slot or ''} -> {edge.target_slot or ''}`"
        detail = f" | {edge.detail}" if edge.detail else ""
        lines.append(
            f"- {edge.kind.value}: `{source_name}` -> `{target_name}`{slot}{detail}"
        )
    if len(edges) > limit:
        lines.append(f"- ...还有 {len(edges) - limit} 条关系未展开。")
    return lines


def _get_analysis_or_404(analysis_id: str):
    analysis = app_state.get_analysis(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return analysis


def _resolve_analyzed_file(analysis, requested_file_path: str) -> Path:
    root = Path(analysis.graph.project_root if analysis.graph else analysis.source_path).resolve()
    requested = Path(requested_file_path)
    candidate = requested.resolve() if requested.is_absolute() else (root / requested).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="Source path is outside analyzed project") from exc
    if not candidate.is_file():
        raise HTTPException(status_code=404, detail="Source file not found")
    return candidate


def _language_from_path(path: Path) -> str:
    suffix = path.suffix.lower()
    return {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".java": "java",
        ".go": "go",
        ".rs": "rust",
    }.get(suffix, "text")


def _extract_archive(archive_path: Path, temp_root: Path) -> Path:
    output_dir = temp_root / "source"
    output_dir.mkdir(parents=True, exist_ok=True)
    suffixes = "".join(archive_path.suffixes).lower()
    if suffixes.endswith(".zip"):
        with zipfile.ZipFile(archive_path) as archive:
            archive.extractall(output_dir)
    elif suffixes.endswith(".tar.gz") or suffixes.endswith(".tgz"):
        with tarfile.open(archive_path) as archive:
            archive.extractall(output_dir)
    else:
        raise HTTPException(status_code=400, detail="Only .zip, .tar.gz, and .tgz uploads are supported")
    children = [child for child in output_dir.iterdir() if child.is_dir()]
    return children[0] if len(children) == 1 else output_dir


def _chunk_text(text: str, size: int):
    for index in range(0, len(text), size):
        yield text[index : index + size]
