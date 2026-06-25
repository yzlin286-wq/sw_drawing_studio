"""v2.3 Task 1: 作业队列

线程安全的作业队列管理，支持优先级、重试、暂停/恢复、持久化。
"""
from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class JobStatus(str, Enum):
    """作业状态枚举"""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    RECOVERING = "recovering"


class JobPriority(int, Enum):
    """作业优先级枚举（数值越大优先级越高）"""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    URGENT = 3


@dataclass
class JobRecord:
    """作业记录数据类"""
    job_id: str                          # 作业 ID（UUID）
    part_name: str                       # 零件名称
    part_path: str                       # 零件文件路径
    job_type: str                        # 作业类型: cad / vision_audit / batch
    status: JobStatus = JobStatus.PENDING    # 当前状态
    priority: JobPriority = JobPriority.NORMAL   # 优先级
    created_at: str = ""                 # 创建时间
    started_at: Optional[str] = None     # 开始时间
    finished_at: Optional[str] = None    # 结束时间
    duration_s: float = 0               # 耗时（秒）
    retry_count: int = 0                # 已重试次数
    max_retries: int = 3                # 最大重试次数
    timeout_s: float = 600              # 超时时间（秒）
    sw_pid: Optional[int] = None        # SolidWorks 进程 PID
    run_dir: str = ""                   # 运行目录
    run_id: str = ""                    # 运行 ID
    error: str = ""                     # 错误信息
    progress: float = 0                 # 进度 0.0 ~ 1.0
    stage: str = ""                     # 当前阶段描述
    result: dict = field(default_factory=dict)   # 结果数据
    last_event: str = ""                # 最后一条事件摘要

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典（枚举转为值）"""
        d = asdict(self)
        d["status"] = self.status.value if isinstance(self.status, JobStatus) else str(self.status)
        d["priority"] = self.priority.value if isinstance(self.priority, JobPriority) else int(self.priority)
        return d

    @staticmethod
    def from_dict(d: dict[str, Any]) -> JobRecord:
        """从字典反序列化"""
        d = dict(d)  # 浅拷贝避免修改原字典
        # 枚举字段还原
        status_val = d.get("status", "pending")
        if isinstance(status_val, str):
            d["status"] = JobStatus(status_val)
        prio_val = d.get("priority", 1)
        if isinstance(prio_val, int):
            d["priority"] = JobPriority(prio_val)
        return JobRecord(**{k: v for k, v in d.items() if k in JobRecord.__dataclass_fields__})


def _new_job_id() -> str:
    return uuid.uuid4().hex[:12]


def _now_str() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


class JobQueue:
    """线程安全的作业队列

    支持优先级排序、重试、暂停/恢复、持久化。
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._jobs: dict[str, JobRecord] = {}  # job_id -> JobRecord

    # ── 增删查 ─────────────────────────────────────────────

    def add_job(self, record: JobRecord) -> str:
        """添加作业到队列，返回 job_id"""
        with self._lock:
            if not record.job_id:
                record.job_id = _new_job_id()
            if not record.created_at:
                record.created_at = _now_str()
            self._jobs[record.job_id] = record
        return record.job_id

    def remove_job(self, job_id: str) -> None:
        """从队列中移除作业"""
        with self._lock:
            self._jobs.pop(job_id, None)

    def get_job(self, job_id: str) -> Optional[JobRecord]:
        """获取指定作业记录"""
        with self._lock:
            return self._jobs.get(job_id)

    # ── 优先级调度 ─────────────────────────────────────────

    def get_next_pending(self) -> Optional[JobRecord]:
        """获取下一个待执行作业（按优先级降序、创建时间升序）"""
        with self._lock:
            candidates = [
                j for j in self._jobs.values()
                if j.status in (JobStatus.PENDING, JobStatus.QUEUED)
            ]
            if not candidates:
                return None
            # 优先级降序，创建时间升序
            candidates.sort(key=lambda j: (-j.priority.value, j.created_at))
            return candidates[0]

    # ── 状态更新 ───────────────────────────────────────────

    def update_status(self, job_id: str, status: JobStatus, **kwargs: Any) -> None:
        """更新作业状态及附加字段"""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job.status = status
            for k, v in kwargs.items():
                if hasattr(job, k):
                    setattr(job, k, v)
            # 自动设置时间戳
            if status == JobStatus.RUNNING and not job.started_at:
                job.started_at = _now_str()
            if status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.TIMEOUT):
                job.finished_at = _now_str()
                if job.started_at:
                    try:
                        t0 = time.mktime(time.strptime(job.started_at, "%Y-%m-%dT%H:%M:%S"))
                        t1 = time.mktime(time.strptime(job.finished_at, "%Y-%m-%dT%H:%M:%S"))
                        job.duration_s = round(t1 - t0, 2)
                    except (ValueError, OverflowError):
                        pass

    def pause_job(self, job_id: str) -> None:
        """暂停作业"""
        self.update_status(job_id, JobStatus.PAUSED)

    def resume_job(self, job_id: str) -> None:
        """恢复作业（回到 pending 等待调度）"""
        self.update_status(job_id, JobStatus.PENDING)

    def cancel_job(self, job_id: str) -> bool:
        """取消作业"""
        if self.get_job(job_id) is None:
            return False
        self.update_status(job_id, JobStatus.CANCELLED)
        return True

    def skip_job(self, job_id: str) -> bool:
        """跳过作业（标记为完成但不执行）"""
        if self.get_job(job_id) is None:
            return False
        self.update_status(job_id, JobStatus.COMPLETED, error="skipped by user")
        return True

    def retry_job(self, job_id: str) -> Optional[JobRecord]:
        """重试作业（递增 retry_count，回到 pending）

        超过 max_retries 则标记为 failed。
        """
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            job.retry_count += 1
            if job.retry_count > job.max_retries:
                job.status = JobStatus.FAILED
                job.error = f"超过最大重试次数 ({job.max_retries})"
                job.finished_at = _now_str()
                return job
            # 重置状态准备重试
            job.status = JobStatus.PENDING
            job.started_at = None
            job.finished_at = None
            job.duration_s = 0
            job.progress = 0
            job.stage = ""
            job.error = ""
            job.sw_pid = None
            return job

    # ── 列表/统计 ──────────────────────────────────────────

    def list_jobs(self, status_filter: Optional[JobStatus | str | list[JobStatus | str]] = None) -> list[JobRecord]:
        """列出作业（可按状态过滤）"""
        with self._lock:
            jobs = list(self._jobs.values())
        if status_filter is not None:
            if isinstance(status_filter, (JobStatus, str)):
                status_filter = [status_filter]
            filter_set: set[JobStatus] = set()
            for item in status_filter:
                if isinstance(item, JobStatus):
                    filter_set.add(item)
                else:
                    try:
                        filter_set.add(JobStatus(str(item)))
                    except ValueError:
                        continue
            jobs = [j for j in jobs if j.status in filter_set]
        # 按创建时间倒序
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        return jobs

    def active_count(self) -> int:
        """当前运行中的作业数"""
        with self._lock:
            return sum(1 for j in self._jobs.values() if j.status == JobStatus.RUNNING)

    def pending_count(self) -> int:
        """等待中的作业数"""
        with self._lock:
            return sum(1 for j in self._jobs.values()
                       if j.status in (JobStatus.PENDING, JobStatus.QUEUED))

    # ── 序列化/持久化 ──────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典（用于 JSON）"""
        with self._lock:
            return {
                jid: j.to_dict() for jid, j in self._jobs.items()
            }

    def save(self, path: Path) -> None:
        """持久化到 JSON 文件"""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = self.to_dict()
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def load(self, path: Path) -> None:
        """从 JSON 文件恢复队列"""
        path = Path(path)
        if not path.exists():
            return
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        with self._lock:
            self._jobs.clear()
            for jid, d in raw.items():
                try:
                    self._jobs[jid] = JobRecord.from_dict(d)
                except (KeyError, TypeError, ValueError):
                    continue
