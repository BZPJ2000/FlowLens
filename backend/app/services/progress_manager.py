"""进度管理器 — WebSocket + 内存状态，供 SSE fallback"""

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class Step(str, Enum):
    INIT = "init"
    CLONING = "cloning"
    EXTRACTING = "extracting"
    PARSING = "parsing"
    ANALYZING = "analyzing"
    BUILDING = "building"
    GENERATING = "generating_report"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ProgressState:
    analysis_id: uuid.UUID
    step: Step = Step.INIT
    pct: int = 0
    message: str = ""
    detail: str = ""  # 当前正在处理的文件名等详细信息
    error: str = ""
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "analysis_id": str(self.analysis_id),
            "step": self.step.value,
            "progress_pct": self.pct,
            "message": self.message,
            "detail": self.detail,
            "status": self.step.value,
            "error": self.error,
        }


class ProgressManager:
    """管理分析任务的进度状态和广播"""

    def __init__(self):
        self._states: dict[uuid.UUID, ProgressState] = {}
        self._subscribers: dict[uuid.UUID, list[asyncio.Queue]] = {}

    def create(self, analysis_id: uuid.UUID) -> ProgressState:
        state = ProgressState(analysis_id=analysis_id)
        self._states[analysis_id] = state
        return state

    def update(
        self,
        analysis_id: uuid.UUID,
        step: Step,
        pct: int,
        message: str = "",
        detail: str = "",
    ):
        state = self._states.get(analysis_id)
        if not state:
            state = self.create(analysis_id)

        state.step = step
        state.pct = pct
        state.message = message
        state.detail = detail

        if step == Step.COMPLETED:
            state.completed_at = datetime.now(timezone.utc)
            state.pct = 100
        elif step == Step.FAILED:
            state.error = message

        self._broadcast(analysis_id, state)

    def fail(self, analysis_id: uuid.UUID, error: str):
        state = self._states.get(analysis_id)
        if not state:
            state = self.create(analysis_id)
        state.step = Step.FAILED
        state.error = error
        self._broadcast(analysis_id, state)

    def get(self, analysis_id: uuid.UUID) -> Optional[ProgressState]:
        return self._states.get(analysis_id)

    async def subscribe(self, analysis_id: uuid.UUID) -> asyncio.Queue:
        """订阅进度更新，返回一个 asyncio.Queue"""
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        if analysis_id not in self._subscribers:
            self._subscribers[analysis_id] = []
        self._subscribers[analysis_id].append(queue)

        # 立即发送当前状态
        state = self._states.get(analysis_id)
        if state:
            queue.put_nowait(state.to_dict())

        return queue

    def unsubscribe(self, analysis_id: uuid.UUID, queue: asyncio.Queue):
        if analysis_id in self._subscribers:
            try:
                self._subscribers[analysis_id].remove(queue)
            except ValueError:
                pass

    def _broadcast(self, analysis_id: uuid.UUID, state: ProgressState):
        data = state.to_dict()
        if analysis_id not in self._subscribers:
            return
        dead = []
        for q in self._subscribers[analysis_id]:
            try:
                q.put_nowait(data)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            self.unsubscribe(analysis_id, q)

    def cleanup(self, analysis_id: uuid.UUID):
        self._states.pop(analysis_id, None)
        self._subscribers.pop(analysis_id, None)


progress_manager = ProgressManager()
