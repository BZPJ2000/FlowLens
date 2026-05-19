"""Phase 1: 纯业务逻辑模型 — Pydantic schemas，不涉及数据库"""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# ═══════════════════════════════════════════
# 枚举
# ═══════════════════════════════════════════

class SourceType(str, Enum):
    GITHUB = "github"
    UPLOAD = "upload"


class AnalysisStatus(str, Enum):
    PENDING = "pending"
    PARSING = "parsing"
    ANALYZING = "analyzing"
    BUILDING = "building"
    COMPLETED = "completed"
    FAILED = "failed"


class EdgeType(str, Enum):
    IMPORT = "import"
    CALL = "call"
    EXPORT = "export"
    PORT_TO_FUNCTION = "port_to_function"
    FUNCTION_TO_PORT = "function_to_port"


# ═══════════════════════════════════════════
# 源码解析结果（Tree-sitter 提取，零 token）
# ═══════════════════════════════════════════

class FunctionSignature(BaseModel):
    name: str
    params: list[dict] = Field(default_factory=list)  # [{name, type, default}]
    return_type: str = "unknown"
    is_exported: bool = False
    is_async: bool = False
    line_start: int = 0
    line_end: int = 0


class FunctionCall(BaseModel):
    caller_name: str
    callee_name: str
    args: list[dict] = Field(default_factory=list)  # [{name, type, position}]
    line: int = 0


class ClassDefinition(BaseModel):
    name: str
    methods: list[FunctionSignature] = Field(default_factory=list)
    is_exported: bool = False
    line_start: int = 0
    line_end: int = 0


class ImportInfo(BaseModel):
    variable_name: str        # 导入的变量名
    source_module: str        # 来源模块路径
    import_type: str = "named"  # named | default | namespace | destructured
    alias: str = ""           # 别名
    data_type: str = "unknown"


class ExportInfo(BaseModel):
    variable_name: str
    export_type: str = "named"  # named | default
    data_type: str = "unknown"
    is_function: bool = False
    is_class: bool = False
    is_type_only: bool = False


class ParseResult(BaseModel):
    """Tree-sitter 解析一个文件的输出"""
    file_path: str
    file_name: str
    language: str = "unknown"
    content_hash: str = ""
    imports: list[ImportInfo] = Field(default_factory=list)
    exports: list[ExportInfo] = Field(default_factory=list)
    functions: list[FunctionSignature] = Field(default_factory=list)
    classes: list[ClassDefinition] = Field(default_factory=list)
    calls: list[FunctionCall] = Field(default_factory=list)
    line_count: int = 0
    byte_size: int = 0


# ═══════════════════════════════════════════
# AI 分析结果（AI 返回，低 token）
# ═══════════════════════════════════════════

class AIInputOutput(BaseModel):
    """一个输入或输出项"""
    name: str
    type: str = "unknown"
    source: str = ""          # 来源模块（仅 import）
    is_function: bool = False
    description: str = ""     # 简短说明这个变量是干什么的


class AIFileAnalysis(BaseModel):
    """AI 分析单个文件的输出（结构化 JSON）"""
    file_path: str
    summary: str = ""                           # 一句话总结
    detail: str = ""                            # 详细解释（一段话）
    inputs: list[AIInputOutput] = Field(default_factory=list)    # 该文件依赖的外部输入
    outputs: list[AIInputOutput] = Field(default_factory=list)   # 该文件提供给外部的输出
    internal_structures: list[dict] = Field(default_factory=list)  # [{name, type, fields, description}]
    architecture_role: str = ""                 # 架构角色：controller/service/model/view/util/config 等
    dependencies_summary: str = ""              # 一句话说明依赖了什么


# ═══════════════════════════════════════════
# 关系图数据
# ═══════════════════════════════════════════

class FunctionNode(BaseModel):
    """函数节点 — 文件内的子节点"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    params: list[dict] = Field(default_factory=list)  # [{name, type}]
    return_type: str = "unknown"
    is_exported: bool = False
    is_async: bool = False
    description: str = ""


class GraphPort(BaseModel):
    """节点上的端口 — 对应函数/变量"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    port_type: str = "function"   # function | variable | class | param
    data_type: str = "unknown"    # string | number | UserDto | Promise<User> 等
    direction: str = "output"     # input | output
    description: str = ""


class GraphNode(BaseModel):
    """数据流图节点 — 对应一个文件"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    file_path: str
    file_name: str
    language: str = "unknown"
    summary: str = ""
    detail: str = ""
    architecture_role: str = ""
    ports: list[GraphPort] = Field(default_factory=list)
    functions: list[FunctionNode] = Field(default_factory=list)
    # 布局坐标（前端计算或 dagre 计算）
    x: float = 0
    y: float = 0


class GraphEdge(BaseModel):
    """数据流图边 — 文件间的数据传递"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    source_node_id: str
    target_node_id: str
    source_port_id: str = ""
    target_port_id: str = ""
    source_function_id: str = ""
    target_function_id: str = ""
    variable_name: str          # 传递的变量名
    data_type: str = "unknown"  # 传递的数据类型
    edge_type: EdgeType = EdgeType.IMPORT
    label: str = ""             # 显示在边上的标签


class DataFlowGraph(BaseModel):
    """完整的数据流图"""
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    entry_points: list[str] = Field(default_factory=list)    # 入口文件 ID
    exit_points: list[str] = Field(default_factory=list)     # 出口文件 ID
    cycles: list[list[str]] = Field(default_factory=list)    # 循环依赖环
    unused_exports: list[dict] = Field(default_factory=list)  # 未使用的导出 [{variable_name, node_ids}]


# ═══════════════════════════════════════════
# 项目 & 分析
# ═══════════════════════════════════════════

class ProjectCreate(BaseModel):
    name: str
    source_type: SourceType
    source_url: str = ""


class Project(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    source_type: SourceType
    source_url: str = ""
    storage_path: str = ""
    file_count: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Analysis(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    status: AnalysisStatus = AnalysisStatus.PENDING
    error_message: str = ""
    progress_pct: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None


class AnalysisProgress(BaseModel):
    """SSE 推送的进度事件"""
    analysis_id: UUID
    status: AnalysisStatus
    progress_pct: int
    message: str = ""
    current_step: str = ""


# ═══════════════════════════════════════════
# 报告
# ═══════════════════════════════════════════

class ArchitectureIssue(BaseModel):
    severity: str = "info"      # info | warning | error
    category: str = ""          # circular_dependency | unused_export | type_mismatch | ...
    description: str = ""
    related_files: list[str] = Field(default_factory=list)
    suggestion: str = ""        # 修复建议


class AnalysisReport(BaseModel):
    project_name: str = ""
    tech_stack: list[str] = Field(default_factory=list)
    file_count: int = 0
    total_lines: int = 0
    architecture_summary: str = ""
    file_details: list[AIFileAnalysis] = Field(default_factory=list)
    core_flows: list[str] = Field(default_factory=list)       # 核心数据流路径描述
    issues: list[ArchitectureIssue] = Field(default_factory=list)
    health_score: int = 100                                  # 架构健康评分 0-100
    generated_at: datetime = Field(default_factory=datetime.utcnow)


# ═══════════════════════════════════════════
# 对话
# ═══════════════════════════════════════════

class ChatMessage(BaseModel):
    role: str  # user | assistant
    content: str
    referenced_nodes: list[str] = Field(default_factory=list)


class ChatRequest(BaseModel):
    session_id: Optional[UUID] = None
    message: str


class ChatResponse(BaseModel):
    session_id: UUID
    reply: str
    referenced: list[str] = Field(default_factory=list)
