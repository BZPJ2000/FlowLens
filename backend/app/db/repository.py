"""Phase 2: Repository 层 — 数据访问封装，与业务逻辑解耦"""

from uuid import UUID
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import (
    Analysis,
    AnalysisReport,
    ChatMessage,
    ChatSession,
    DataEdge,
    FileNode,
    FunctionPort,
    Project,
)


class ProjectRepo:
    @staticmethod
    async def create(db: AsyncSession, name: str, source_type: str, source_url: str = "") -> Project:
        p = Project(name=name, source_type=source_type, source_url=source_url)
        db.add(p)
        await db.flush()
        return p

    @staticmethod
    async def get(db: AsyncSession, project_id: str) -> Optional[Project]:
        return await db.get(Project, project_id)

    @staticmethod
    async def list_all(db: AsyncSession) -> list[Project]:
        result = await db.execute(
            select(Project)
            .options(selectinload(Project.analyses))
            .order_by(Project.created_at.desc())
            .limit(50)
        )
        return list(result.scalars().all())


class AnalysisRepo:
    @staticmethod
    async def create(db: AsyncSession, project_id: str) -> Analysis:
        a = Analysis(project_id=project_id)
        db.add(a)
        await db.flush()
        return a

    @staticmethod
    async def get(db: AsyncSession, analysis_id: str) -> Optional[Analysis]:
        return await db.get(Analysis, analysis_id)

    @staticmethod
    async def update_status(
        db: AsyncSession, analysis_id: str,
        status: str, progress_pct: int = 0, error: str = "",
    ) -> None:
        a = await db.get(Analysis, analysis_id)
        if a:
            a.status = status
            a.progress_pct = progress_pct
            if error:
                a.error_message = error
            if status in ("completed", "failed"):
                a.completed_at = datetime.now(timezone.utc)
            await db.flush()

    @staticmethod
    async def cleanup_expired(db: AsyncSession) -> int:
        """清理过期分析，返回清理数量"""
        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(Analysis).where(Analysis.expires_at < now)
        )
        expired = result.scalars().all()
        for a in expired:
            await db.delete(a)
        await db.flush()
        return len(expired)


class FileNodeRepo:
    @staticmethod
    async def bulk_create(db: AsyncSession, analysis_id: str, files: list[dict]) -> list[FileNode]:
        nodes = []
        for f in files:
            node = FileNode(analysis_id=analysis_id, **f)
            db.add(node)
            nodes.append(node)
        await db.flush()
        return nodes

    @staticmethod
    async def get_by_analysis(db: AsyncSession, analysis_id: str) -> list[FileNode]:
        result = await db.execute(
            select(FileNode).where(FileNode.analysis_id == analysis_id)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get(db: AsyncSession, file_id: str) -> Optional[FileNode]:
        return await db.get(FileNode, file_id)


class DataEdgeRepo:
    @staticmethod
    async def bulk_create(db: AsyncSession, analysis_id: str, edges: list[dict]) -> list[DataEdge]:
        nodes = []
        for e in edges:
            edge = DataEdge(analysis_id=analysis_id, **e)
            db.add(edge)
            nodes.append(edge)
        await db.flush()
        return nodes

    @staticmethod
    async def get_by_analysis(db: AsyncSession, analysis_id: str) -> list[DataEdge]:
        result = await db.execute(
            select(DataEdge).where(DataEdge.analysis_id == analysis_id)
        )
        return list(result.scalars().all())


class ChatRepo:
    @staticmethod
    async def create_session(db: AsyncSession, analysis_id: str | UUID, title: str = "新对话") -> ChatSession:
        s = ChatSession(analysis_id=str(analysis_id), title=title)
        db.add(s)
        await db.flush()
        return s

    @staticmethod
    async def get_or_create_session(db: AsyncSession, analysis_id: str, session_id: Optional[str] = None) -> ChatSession:
        if session_id:
            session = await db.get(ChatSession, session_id)
            if session:
                return session
        return await ChatRepo.create_session(db, analysis_id)

    @staticmethod
    async def add_message(
        db: AsyncSession, session_id: str, role: str, content: str,
        referenced_nodes: list[str] | None = None,
    ) -> ChatMessage:
        msg = ChatMessage(
            session_id=session_id, role=role, content=content,
            referenced_nodes=referenced_nodes or [],
        )
        db.add(msg)
        await db.flush()
        return msg

    @staticmethod
    async def list_sessions(db: AsyncSession, analysis_id: str) -> list[ChatSession]:
        result = await db.execute(
            select(ChatSession)
            .where(ChatSession.analysis_id == analysis_id)
            .order_by(ChatSession.created_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_messages(db: AsyncSession, session_id: str) -> list[ChatMessage]:
        result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at)
        )
        return list(result.scalars().all())


class ReportRepo:
    @staticmethod
    async def save(db: AsyncSession, analysis_id: str, content_md: str, arch_summary: str, issue_count: int) -> AnalysisReport:
        analysis_id = str(analysis_id)
        # Try query by analysis_id
        result = await db.execute(
            select(AnalysisReport).where(AnalysisReport.analysis_id == analysis_id)
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.content_md = content_md
            existing.architecture_summary = arch_summary
            existing.issue_count = issue_count
            existing.generated_at = datetime.now(timezone.utc)
        else:
            existing = AnalysisReport(
                analysis_id=analysis_id,
                content_md=content_md,
                architecture_summary=arch_summary,
                issue_count=issue_count,
            )
            db.add(existing)
        await db.flush()
        return existing

    @staticmethod
    async def get(db: AsyncSession, analysis_id: str) -> Optional[AnalysisReport]:
        result = await db.execute(
            select(AnalysisReport).where(AnalysisReport.analysis_id == analysis_id)
        )
        return result.scalar_one_or_none()
