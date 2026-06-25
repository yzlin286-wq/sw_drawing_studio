"""v2.3 Task 1: Job 事件总线

线程安全的事件发布/订阅系统，用于 Job Runner 进程间通信。
Worker 子进程通过 stdout 输出 JSONL 事件，主进程解析后发布到事件总线。
"""
from __future__ import annotations

import json
import threading
import time
from collections import deque
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Callable


class JobEventType(str, Enum):
    """作业事件类型枚举"""
    JOB_STARTED = "job_started"
    PROGRESS = "progress"
    HEARTBEAT = "heartbeat"
    WARNING = "warning"
    RECOVERED = "recovered"
    JOB_FINISHED = "job_finished"
    JOB_FAILED = "job_failed"


@dataclass
class JobEvent:
    """作业事件数据类"""
    event_type: str          # 事件类型（对应 JobEventType 值）
    job_id: str              # 作业 ID
    timestamp: str           # ISO 格式时间戳
    data: dict = field(default_factory=dict)   # 事件附带数据
    message: str = ""        # 人类可读消息

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典"""
        d = asdict(self)
        d["type"] = self.event_type
        return d

    def to_json(self) -> str:
        """序列化为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @staticmethod
    def from_dict(d: dict[str, Any]) -> JobEvent:
        """从字典反序列化"""
        return JobEvent(
            event_type=d.get("event_type") or d.get("type", ""),
            job_id=d.get("job_id", ""),
            timestamp=d.get("timestamp", ""),
            data=d.get("data", {}),
            message=d.get("message", ""),
        )

    @staticmethod
    def now_iso() -> str:
        """返回当前 ISO 格式时间戳"""
        return time.strftime("%Y-%m-%dT%H:%M:%S")


class JobEventBus:
    """线程安全的作业事件总线

    - 发布/订阅模式
    - 保留最近事件用于查询
    - 支持 JSONL 序列化/反序列化（用于日志持久化）
    """

    def __init__(self, max_recent: int = 5000) -> None:
        self._lock = threading.RLock()
        self._events: deque[JobEvent] = deque(maxlen=max_recent)
        self._subscribers: list[Callable[[JobEvent], None]] = []

    # ── 发布/订阅 ──────────────────────────────────────────

    def publish(self, event: JobEvent) -> None:
        """发布事件到总线，通知所有订阅者"""
        with self._lock:
            self._events.append(event)
            subs = list(self._subscribers)
        # 在锁外回调，避免死锁
        for cb in subs:
            try:
                cb(event)
            except Exception:
                pass

    def subscribe(self, callback: Callable[[JobEvent], None]) -> None:
        """注册事件回调"""
        with self._lock:
            if callback not in self._subscribers:
                self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[JobEvent], None]) -> None:
        """注销事件回调"""
        with self._lock:
            try:
                self._subscribers.remove(callback)
            except ValueError:
                pass

    # ── 查询 ───────────────────────────────────────────────

    def get_recent_events(self, n: int = 50) -> list[JobEvent]:
        """获取最近 n 条事件"""
        with self._lock:
            events = list(self._events)
        return events[-n:] if len(events) > n else events

    def get_events_for_job(self, job_id: str) -> list[JobEvent]:
        """获取指定作业的全部事件"""
        with self._lock:
            return [e for e in self._events if e.job_id == job_id]

    def clear_old_events(self, max_age_s: float = 3600) -> None:
        """清除超过 max_age_s 秒的旧事件"""
        cutoff = time.time() - max_age_s
        with self._lock:
            kept: deque[JobEvent] = deque(maxlen=self._events.maxlen)
            for e in self._events:
                try:
                    # 解析 ISO 时间戳
                    ts = time.mktime(time.strptime(e.timestamp, "%Y-%m-%dT%H:%M:%S"))
                    if ts >= cutoff:
                        kept.append(e)
                except (ValueError, OverflowError):
                    kept.append(e)  # 无法解析的事件保留
            self._events = kept

    # ── JSONL 序列化 ───────────────────────────────────────

    def to_jsonl(self) -> str:
        """将所有事件序列化为 JSONL 格式字符串"""
        with self._lock:
            lines = [e.to_json() for e in self._events]
        return "\n".join(lines)

    @staticmethod
    def from_jsonl(text: str) -> list[JobEvent]:
        """从 JSONL 文本反序列化事件列表"""
        events: list[JobEvent] = []
        for line in text.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                events.append(JobEvent.from_dict(d))
            except (json.JSONDecodeError, KeyError):
                continue
        return events
