"""Phase 2: SQLAlchemy ORM 模型 — SQLite / MySQL 通用"""

import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
)
from sqlalchemy.orm import relationship

from app.db.database import Base


def utcnow():
    return datetime.now(timezone.utc)


def new_uuid():
    return str(uuid.uuid4())


# ═══════════════════════════════════════════
# Project
# ═══════════════════════════════════════════

class Project(Base):
    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, default=new_uuid)
    name = Column(String(255), nullable=False)
    source_type = Column(String(20), nullable=False)  # 'github' | 'upload'
    source_url = Column(Text, default="")
    storage_path = Column(Text, default="")
    file_count = Column(Integer, default=0)
    total_size_kb = Column(Integer, default=0)
    created_at = Column(DateTime, default=utcnow)

    analyses = relationship("Analysis", back_populates="project", cascade="all, delete-orphan")


# ═══════════════════════════════════════════
# Analysis
# ═══════════════════════════════════════════

class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(String(36), primary_key=True, default=new_uuid)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(20), default="pending")
    error_message = Column(Text, default="")
    progress_pct = Column(Integer, default=0)
    created_at = Column(DateTime, default=utcnow)
    completed_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, default=lambda: utcnow() + timedelta(hours=24))

    project = relationship("Project", back_populates="analyses")
    file_nodes = relationship("FileNode", back_populates="analysis", cascade="all, delete-orphan")
    data_edges = relationship("DataEdge", back_populates="analysis", cascade="all, delete-orphan")
    chat_sessions = relationship("ChatSession", back_populates="analysis", cascade="all, delete-orphan")
    report = relationship("AnalysisReport", back_populates="analysis", uselist=False, cascade="all, delete-orphan")


# ═══════════════════════════════════════════
# FileNode
# ═══════════════════════════════════════════

class FileNode(Base):
    __tablename__ = "file_nodes"

    id = Column(String(36), primary_key=True, default=new_uuid)
    analysis_id = Column(String(36), ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False)
    file_path = Column(String(1000), nullable=False)
    file_name = Column(String(255), nullable=False)
    language = Column(String(50), default="unknown")
    content_hash = Column(String(64), default="")
    summary = Column(String(500), default="")
    detail_explain = Column(Text, default="")
    imports_json = Column(JSON, default=list)
    exports_json = Column(JSON, default=list)
    functions_json = Column(JSON, default=list)
    classes_json = Column(JSON, default=list)
    raw_content = Column(Text, default="")
    created_at = Column(DateTime, default=utcnow)

    analysis = relationship("Analysis", back_populates="file_nodes")
    function_ports = relationship("FunctionPort", back_populates="file_node", cascade="all, delete-orphan")


# ═══════════════════════════════════════════
# DataEdge
# ═══════════════════════════════════════════

class DataEdge(Base):
    __tablename__ = "data_edges"

    id = Column(String(36), primary_key=True, default=new_uuid)
    analysis_id = Column(String(36), ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False)
    from_file_id = Column(String(36), ForeignKey("file_nodes.id", ondelete="CASCADE"), nullable=True)
    to_file_id = Column(String(36), ForeignKey("file_nodes.id", ondelete="CASCADE"), nullable=True)
    from_port_name = Column(String(255), default="")
    to_port_name = Column(String(255), default="")
    variable_name = Column(String(255), nullable=False)
    data_type = Column(String(255), default="unknown")
    edge_type = Column(String(20), default="import")
    metadata_json = Column(JSON, default=dict)

    analysis = relationship("Analysis", back_populates="data_edges")


# ═══════════════════════════════════════════
# FunctionPort
# ═══════════════════════════════════════════

class FunctionPort(Base):
    __tablename__ = "function_ports"

    id = Column(String(36), primary_key=True, default=new_uuid)
    file_node_id = Column(String(36), ForeignKey("file_nodes.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    params_json = Column(JSON, default=list)
    return_type = Column(String(255), default="unknown")
    is_exported = Column(Boolean, default=False)
    is_imported = Column(Boolean, default=False)
    position = Column(Integer, default=0)

    file_node = relationship("FileNode", back_populates="function_ports")


# ═══════════════════════════════════════════
# ChatSession
# ═══════════════════════════════════════════

class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(String(36), primary_key=True, default=new_uuid)
    analysis_id = Column(String(36), ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), default="新对话")
    created_at = Column(DateTime, default=utcnow)

    analysis = relationship("Analysis", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")


# ═══════════════════════════════════════════
# ChatMessage
# ═══════════════════════════════════════════

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(String(36), primary_key=True, default=new_uuid)
    session_id = Column(String(36), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False)  # 'user' | 'assistant'
    content = Column(Text, nullable=False)
    referenced_nodes = Column(JSON, default=list)
    created_at = Column(DateTime, default=utcnow)

    session = relationship("ChatSession", back_populates="messages")


# ═══════════════════════════════════════════
# AnalysisReport
# ═══════════════════════════════════════════

class AnalysisReport(Base):
    __tablename__ = "analysis_reports"

    id = Column(String(36), primary_key=True, default=new_uuid)
    analysis_id = Column(String(36), ForeignKey("analyses.id", ondelete="CASCADE"), unique=True, nullable=False)
    content_md = Column(Text, default="")
    architecture_summary = Column(Text, default="")
    issue_count = Column(Integer, default=0)
    generated_at = Column(DateTime, default=utcnow)

    analysis = relationship("Analysis", back_populates="report")
