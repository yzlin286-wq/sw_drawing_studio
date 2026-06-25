"""v2.3 Task B: Job Runtime Facade - UI 统一调用入口

UI 只能通过该 facade 启动作业，禁止直接调用：
- win32com / SolidWorks COM
- PaddleOCR / YOLO / OpenCV
- batch_validator / vision_qc_v4 / vision_qc_v5

所有重操作必须通过 QProcess 在 worker 子进程中执行。
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Optional

from PySide6.QtCore import QObject, Signal

from app.services.resource_paths import bundle_root, runtime_path

# Runtime artifacts must be written next to the source tree or frozen EXE, not
# under PyInstaller's temporary extraction directory.
REPO_ROOT = runtime_path(".")


def _validation_trace(stage: str, **data: Any) -> None:
    trace_path = os.environ.get("SWDS_VALIDATION_TRACE", "").strip()
    if not trace_path:
        return
    try:
        payload = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "epoch": time.time(),
            "stage": stage,
            **data,
        }
        path = Path(trace_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass

# Worker 脚本路径
WORKERS_DIR = bundle_root() / "app" / "workers"
CAD_WORKER = WORKERS_DIR / "cad_job_worker.py"
VISION_AUDIT_WORKER = WORKERS_DIR / "vision_audit_worker.py"
BATCH_WORKER = WORKERS_DIR / "batch_job_worker.py"
DRAWING_REVIEW_WORKER = WORKERS_DIR / "drawing_review_worker.py"
QC_ACTION_WORKER = WORKERS_DIR / "qc_action_worker.py"
DIAGNOSTICS_ACTION_WORKER = WORKERS_DIR / "diagnostics_action_worker.py"
LLM_ACTION_WORKER = WORKERS_DIR / "llm_action_worker.py"
SYSTEM_HEALTH_WORKER = WORKERS_DIR / "health_check_worker.py"
MOCK_WORKER = WORKERS_DIR / "mock_long_job_worker.py"


class JobRuntimeFacade(QObject):
    """UI 统一调用入口

    所有 UI 页面必须通过本类启动作业，不得直接调用 COM/OCR/YOLO/batch_validator。
    """

    # 信号
    job_started = Signal(str, dict)  # job_id, job_info
    job_progress = Signal(str, dict)  # job_id, progress_data
    job_finished = Signal(str, dict)  # job_id, result
    job_failed = Signal(str, dict)  # job_id, error_info
    job_heartbeat = Signal(str, dict)  # job_id, heartbeat_data
    event_logged = Signal(str, str, dict)  # job_id, event_type, data

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._job_runner = None
        self._job_queue = None
        self._event_bus = None
        self._event_wrappers: dict[Callable, Callable] = {}
        self._initialized = False

    def initialize(self):
        """初始化 JobRunner/JobQueue/EventBus（延迟初始化，避免 UI 启动时阻塞）"""
        if self._initialized:
            return

        try:
            from app.services.job_event_bus import JobEventBus
            from app.services.job_queue import JobQueue
            from app.services.job_runner import JobRunner

            self._event_bus = JobEventBus()
            self._job_queue = JobQueue()
            self._job_runner = JobRunner(
                event_bus=self._event_bus,
                job_queue=self._job_queue,
                max_concurrent=1,
            )

            # 连接 JobRunner 信号到 Facade 信号
            self._job_runner.job_started.connect(self._on_job_started)
            self._job_runner.job_progress.connect(self._on_job_progress)
            self._job_runner.job_finished.connect(self._on_job_finished)
            self._job_runner.job_failed.connect(self._on_job_failed)
            self._job_runner.job_heartbeat.connect(self._on_job_heartbeat)
            self._job_runner.event_logged.connect(self._on_event_logged)

            self._initialized = True
        except Exception as e:
            raise RuntimeError(f"JobRuntimeFacade 初始化失败: {e}")

    def _ensure_initialized(self):
        if not self._initialized:
            self.initialize()

    # ========== CAD 作业 ==========

    def start_cad_job(
        self,
        part_path: str,
        output_dir: str = "",
        max_rounds: int = 3,
        timeout_s: float = 600,
        priority: str = "normal",
        titlebar_overrides: dict | None = None,
        strategy: str = "v6_recommended",
    ) -> str:
        """启动 CAD 出图作业

        Args:
            part_path: SLDPRT 文件路径
            output_dir: 输出目录（默认 drw_output）
            max_rounds: 最大 QC 迭代轮数
            timeout_s: 超时时间（秒）
            priority: 优先级 (low/normal/high/urgent)

        Returns:
            job_id: 作业 ID
        """
        _validation_trace("facade_start_cad_job_enter", part_path=part_path, timeout_s=timeout_s, max_rounds=max_rounds)
        _validation_trace("facade_ensure_initialized_start")
        self._ensure_initialized()
        _validation_trace("facade_ensure_initialized_done")

        job_id = str(uuid.uuid4())[:8]
        part_name = Path(part_path).stem

        run_id = ""
        run_dir = ""
        if not output_dir:
            try:
                _validation_trace("facade_new_run_import_start", job_id=job_id)
                from app.services.run_manager import new_run

                _validation_trace("facade_new_run_call_start", job_id=job_id)
                ctx = new_run(strategy=strategy, input_part_path=part_path)
                _validation_trace("facade_new_run_call_done", job_id=job_id, run_id=ctx.run_id, run_dir=str(ctx.run_dir))
                run_id = ctx.run_id
                run_dir = str(ctx.run_dir)
                output_dir = run_dir
                if titlebar_overrides:
                    ctx.write_log("run.log", f"titlebar_overrides={json.dumps(titlebar_overrides, ensure_ascii=False)}")
                ctx.write_manifest()
                _validation_trace("facade_manifest_written", job_id=job_id, run_dir=run_dir)
            except Exception:
                _validation_trace("facade_new_run_exception", job_id=job_id)
                run_id = ""
                run_dir = ""

        # 添加到队列
        _validation_trace("facade_job_record_import_start", job_id=job_id)
        from app.services.job_queue import JobRecord, JobPriority
        priority_map = {
            "low": JobPriority.LOW,
            "normal": JobPriority.NORMAL,
            "high": JobPriority.HIGH,
            "urgent": JobPriority.URGENT,
        }
        record = JobRecord(
            job_id=job_id,
            part_name=part_name,
            part_path=part_path,
            job_type="cad",
            priority=priority_map.get(priority, JobPriority.NORMAL),
            timeout_s=timeout_s,
            run_dir=run_dir,
            run_id=run_id,
        )
        record.result["max_rounds"] = max_rounds
        record.result["output_dir"] = output_dir
        record.result["titlebar_overrides"] = titlebar_overrides or {}
        record.result["strategy"] = strategy

        _validation_trace("facade_queue_add_start", job_id=job_id, run_dir=run_dir)
        self._job_queue.add_job(record)
        _validation_trace("facade_queue_add_done", job_id=job_id)

        # 启动作业
        _validation_trace("facade_runner_start_job_start", job_id=job_id)
        self._job_runner.start_job(record)
        _validation_trace("facade_runner_start_job_done", job_id=job_id)

        _validation_trace("facade_start_cad_job_return", job_id=job_id)
        return job_id

    # ========== 批量作业 ==========

    def start_batch_job(
        self,
        part_paths: list[str],
        output_dir: str = "",
        max_rounds: int = 3,
        timeout_s: float = 600,
        priority: str = "normal",
    ) -> str:
        """启动批量出图作业

        Args:
            part_paths: SLDPRT 文件路径列表
            output_dir: 输出目录
            max_rounds: 最大 QC 迭代轮数
            timeout_s: 单件超时时间（秒）
            priority: 优先级

        Returns:
            job_id: 作业 ID
        """
        self._ensure_initialized()

        job_id = str(uuid.uuid4())[:8]

        # 添加到队列
        from app.services.job_queue import JobRecord, JobPriority
        priority_map = {
            "low": JobPriority.LOW,
            "normal": JobPriority.NORMAL,
            "high": JobPriority.HIGH,
            "urgent": JobPriority.URGENT,
        }
        record = JobRecord(
            job_id=job_id,
            part_name=f"batch_{len(part_paths)}_parts",
            part_path=json.dumps(part_paths, ensure_ascii=False),
            job_type="batch",
            priority=priority_map.get(priority, JobPriority.NORMAL),
            timeout_s=timeout_s * len(part_paths),  # 批量作业超时 = 单件超时 × 数量
        )
        record.result["part_paths"] = part_paths
        record.result["parts_json"] = record.part_path
        record.result["max_rounds"] = max_rounds
        record.result["output_dir"] = output_dir

        self._job_queue.add_job(record)

        # 启动作业
        self._job_runner.start_job(record)

        return job_id

    # ========== 视觉审计作业 ==========

    def start_visual_audit(
        self,
        pdf_path: str,
        png_path: str = "",
        run_dir: str = "",
        priority: str = "normal",
    ) -> str:
        """启动视觉审计作业

        Args:
            pdf_path: PDF 文件路径
            png_path: PNG 预览图路径（可选）
            run_dir: 运行目录
            priority: 优先级

        Returns:
            job_id: 作业 ID
        """
        self._ensure_initialized()

        job_id = str(uuid.uuid4())[:8]
        part_name = Path(pdf_path).stem

        # 添加到队列
        from app.services.job_queue import JobRecord, JobPriority
        priority_map = {
            "low": JobPriority.LOW,
            "normal": JobPriority.NORMAL,
            "high": JobPriority.HIGH,
            "urgent": JobPriority.URGENT,
        }
        record = JobRecord(
            job_id=job_id,
            part_name=part_name,
            part_path=pdf_path,
            job_type="vision_audit",
            priority=priority_map.get(priority, JobPriority.NORMAL),
            timeout_s=120,  # 视觉审计超时 2 分钟
        )
        record.result["png_path"] = png_path
        record.result["run_dir"] = run_dir

        self._job_queue.add_job(record)

        # 启动作业
        self._job_runner.start_job(record)

        return job_id

    # ========== Drawing Review 操作 ==========

    def start_drawing_review_action(
        self,
        action: str,
        slddrw_path: str = "",
        sldprt_path: str = "",
        pdf_path: str = "",
        png_path: str = "",
        run_dir: str = "",
        run_id: str = "",
        timeout_s: float = 300,
        priority: str = "normal",
    ) -> str:
        """启动 Drawing Review 修复/复核操作。

        Heavy actions such as Add-in dimension generation, Document Manager
        relinking, and Vision QC must run in a worker process instead of the UI.
        """
        self._ensure_initialized()

        allowed = {"addin_dimension", "docmgr_relink", "vision_qc_v3"}
        if action not in allowed:
            raise ValueError(f"未知 Drawing Review action: {action}")

        job_id = str(uuid.uuid4())[:8]
        part_name = Path(slddrw_path or pdf_path or run_dir or action).stem or action

        from app.services.job_queue import JobRecord, JobPriority
        priority_map = {
            "low": JobPriority.LOW,
            "normal": JobPriority.NORMAL,
            "high": JobPriority.HIGH,
            "urgent": JobPriority.URGENT,
        }
        record = JobRecord(
            job_id=job_id,
            part_name=f"review_{action}_{part_name}",
            part_path=slddrw_path or pdf_path,
            job_type="drawing_review",
            priority=priority_map.get(priority, JobPriority.NORMAL),
            timeout_s=timeout_s,
            run_dir=run_dir,
            run_id=run_id,
        )
        record.result.update({
            "action": action,
            "slddrw_path": slddrw_path,
            "sldprt_path": sldprt_path,
            "pdf_path": pdf_path,
            "png_path": png_path,
            "run_dir": run_dir,
            "run_id": run_id,
        })

        self._job_queue.add_job(record)
        self._job_runner.start_job(record)
        return job_id

    # ========== Legacy QC 操作 ==========

    def start_qc_action(
        self,
        action: str,
        slddrw_path: str = "",
        qc_json_path: str = "",
        png_path: str = "",
        run_dir: str = "",
        timeout_s: float = 180,
        priority: str = "normal",
    ) -> str:
        """启动 legacy QC 页面操作。

        PNG rendering, Vision QC v2, and old LLM vision scoring can be slow or
        touch image/model code, so UI pages submit them through this facade.
        """
        self._ensure_initialized()

        allowed = {"render_png", "vision_qc_v2", "legacy_vision_score"}
        if action not in allowed:
            raise ValueError(f"未知 QC action: {action}")

        job_id = str(uuid.uuid4())[:8]
        part_name = Path(slddrw_path or qc_json_path or png_path or action).stem or action

        from app.services.job_queue import JobRecord, JobPriority
        priority_map = {
            "low": JobPriority.LOW,
            "normal": JobPriority.NORMAL,
            "high": JobPriority.HIGH,
            "urgent": JobPriority.URGENT,
        }
        record = JobRecord(
            job_id=job_id,
            part_name=f"qc_{action}_{part_name}",
            part_path=slddrw_path or qc_json_path or png_path,
            job_type="qc_action",
            priority=priority_map.get(priority, JobPriority.NORMAL),
            timeout_s=timeout_s,
            run_dir=run_dir,
            run_id=f"qc_{job_id}",
        )
        record.result.update({
            "action": action,
            "slddrw_path": slddrw_path,
            "qc_json_path": qc_json_path,
            "png_path": png_path,
            "run_dir": run_dir,
        })

        self._job_queue.add_job(record)
        self._job_runner.start_job(record)
        return job_id

    # ========== Diagnostics Actions ==========

    def start_diagnostics_action(
        self,
        action: str,
        run_id: str,
        screenshots_dir: str = "",
        timeout_s: float = 180,
        priority: str = "normal",
    ) -> str:
        """Start diagnostics package work in a QProcess worker."""
        self._ensure_initialized()

        allowed = {"build_zip"}
        if action not in allowed:
            raise ValueError(f"Unknown diagnostics action: {action}")

        normalized_run_id = str(run_id or "").strip()
        if not normalized_run_id:
            raise ValueError("run_id is required")

        job_id = str(uuid.uuid4())[:8]
        run_dir = str(REPO_ROOT / "drw_output" / "runs" / normalized_run_id)

        from app.services.job_queue import JobRecord, JobPriority
        priority_map = {
            "low": JobPriority.LOW,
            "normal": JobPriority.NORMAL,
            "high": JobPriority.HIGH,
            "urgent": JobPriority.URGENT,
        }
        record = JobRecord(
            job_id=job_id,
            part_name=f"diagnostics_{normalized_run_id}",
            part_path=normalized_run_id,
            job_type="diagnostics_action",
            priority=priority_map.get(priority, JobPriority.NORMAL),
            timeout_s=timeout_s,
            run_dir=run_dir,
            run_id=normalized_run_id,
        )
        record.result.update({
            "action": action,
            "run_id": normalized_run_id,
            "screenshots_dir": screenshots_dir,
        })

        self._job_queue.add_job(record)
        self._job_runner.start_job(record)
        return job_id

    # ========== LLM Actions ==========

    def start_llm_action(
        self,
        action: str,
        part_path: str = "",
        context: str = "",
        timeout_s: float = 120,
        priority: str = "normal",
    ) -> str:
        """Start an LLM-backed UI action in a QProcess worker.

        AI pre-analysis, technical-text generation, and model connection tests
        may block on network/model calls, so UI pages submit them through this
        facade.
        """
        self._ensure_initialized()

        allowed = {"pre_analyze", "tech_text", "test_connection"}
        if action not in allowed:
            raise ValueError(f"Unknown LLM action: {action}")

        job_id = str(uuid.uuid4())[:8]
        part_name = Path(part_path or action).stem or action
        run_dir = str(REPO_ROOT / "drw_output" / "runs" / f"llm_{time.strftime('%Y%m%d_%H%M%S')}_{job_id}")
        try:
            Path(run_dir).mkdir(parents=True, exist_ok=True)
        except Exception:
            run_dir = ""

        from app.services.job_queue import JobRecord, JobPriority
        priority_map = {
            "low": JobPriority.LOW,
            "normal": JobPriority.NORMAL,
            "high": JobPriority.HIGH,
            "urgent": JobPriority.URGENT,
        }
        record = JobRecord(
            job_id=job_id,
            part_name=f"llm_{action}_{part_name}",
            part_path=part_path,
            job_type="llm_action",
            priority=priority_map.get(priority, JobPriority.NORMAL),
            timeout_s=timeout_s,
            run_dir=run_dir,
            run_id=f"llm_{job_id}",
        )
        record.result.update({
            "action": action,
            "part_path": part_path,
            "context": context,
            "run_dir": run_dir,
        })

        self._job_queue.add_job(record)
        self._job_runner.start_job(record)
        return job_id
    # ========== System Health ==========

    def start_system_health_check(
        self,
        timeout_s: float = 30,
        priority: str = "normal",
    ) -> str:
        """Start a System Health check in a QProcess worker."""
        self._ensure_initialized()

        job_id = str(uuid.uuid4())[:8]

        from app.services.job_queue import JobRecord, JobPriority
        priority_map = {
            "low": JobPriority.LOW,
            "normal": JobPriority.NORMAL,
            "high": JobPriority.HIGH,
            "urgent": JobPriority.URGENT,
        }
        record = JobRecord(
            job_id=job_id,
            part_name="system_health_check",
            part_path="",
            job_type="system_health",
            priority=priority_map.get(priority, JobPriority.NORMAL),
            timeout_s=timeout_s,
            run_id=f"system_health_{job_id}",
        )
        record.result["scope"] = "system_health"

        self._job_queue.add_job(record)
        self._job_runner.start_job(record)
        return job_id

    # ========== Mock 作业（测试用）==========

    def start_mock_job(
        self,
        scenario: str = "normal_pass",
        duration_s: float = 10.0,
        priority: str = "normal",
    ) -> str:
        """启动 Mock 作业（用于 UI 测试）

        Args:
            scenario: 场景 (pass/normal_pass/pass_with_warning/timeout/failed/recovered/stuck_then_recovered)
            duration_s: 模拟时长（秒）
            priority: 优先级

        Returns:
            job_id: 作业 ID
        """
        self._ensure_initialized()

        job_id = str(uuid.uuid4())[:8]
        run_dir = str(REPO_ROOT / "drw_output" / "runs" / f"mock_{time.strftime('%Y%m%d_%H%M%S')}_{job_id}")

        # 添加到队列
        from app.services.job_queue import JobRecord, JobPriority
        priority_map = {
            "low": JobPriority.LOW,
            "normal": JobPriority.NORMAL,
            "high": JobPriority.HIGH,
            "urgent": JobPriority.URGENT,
        }
        record = JobRecord(
            job_id=job_id,
            part_name=f"mock_{scenario}",
            part_path="",
            job_type="mock",
            priority=priority_map.get(priority, JobPriority.NORMAL),
            timeout_s=duration_s + 30,
            run_dir=run_dir,
            run_id=f"mock_{job_id}",
        )
        record.result["scenario"] = scenario
        record.result["duration_s"] = duration_s

        self._job_queue.add_job(record)

        # 启动作业
        self._job_runner.start_job(record)

        return job_id

    # ========== 作业控制 ==========

    def cancel_job(self, job_id: str) -> bool:
        """取消作业

        Args:
            job_id: 作业 ID

        Returns:
            True 如果成功取消
        """
        self._ensure_initialized()
        return self._job_runner.cancel_job(job_id)

    def retry_job(self, job_id: str) -> Optional[str]:
        """重试作业

        Args:
            job_id: 作业 ID

        Returns:
            新 job_id 如果成功，None 如果失败
        """
        self._ensure_initialized()
        record = self._job_queue.retry_job(job_id)
        if record:
            self._job_runner.start_job(record)
            return record.job_id
        return None

    def skip_job(self, job_id: str) -> bool:
        """跳过作业

        Args:
            job_id: 作业 ID

        Returns:
            True 如果成功跳过
        """
        self._ensure_initialized()
        return self._job_runner.skip_job(job_id)

    def pause_queue(self):
        """暂停作业队列"""
        self._ensure_initialized()
        self._job_runner.pause_queue()

    def resume_queue(self):
        """恢复作业队列"""
        self._ensure_initialized()
        self._job_runner.resume_queue()

    # ========== 查询 ==========

    def get_job_status(self, job_id: str) -> Optional[dict]:
        """获取作业状态

        Args:
            job_id: 作业 ID

        Returns:
            作业状态字典
        """
        self._ensure_initialized()
        record = self._job_queue.get_job(job_id)
        if record:
            return record.to_dict()
        return None

    def list_jobs(self, status_filter: Optional[str] = None) -> list[dict]:
        """列出作业

        Args:
            status_filter: 状态过滤 (pending/running/completed/failed/cancelled)

        Returns:
            作业列表
        """
        self._ensure_initialized()
        records = self._job_queue.list_jobs(status_filter=status_filter)
        return [r.to_dict() for r in records]

    def get_active_job(self) -> Optional[dict]:
        """获取当前活跃作业

        Returns:
            活跃作业字典
        """
        self._ensure_initialized()
        record = self._job_runner.get_active_job()
        if record:
            return record.to_dict()
        return None

    def subscribe_events(self, callback: Callable[[str, str, dict], None]):
        """订阅事件

        Args:
            callback: 回调函数 (job_id, event_type, data)
        """
        self._ensure_initialized()
        if callback in self._event_wrappers:
            return

        def _wrapper(event):
            callback(event.job_id, event.event_type, event.data or {})

        self._event_wrappers[callback] = _wrapper
        self._event_bus.subscribe(_wrapper)

    def unsubscribe_events(self, callback: Callable[[str, str, dict], None]):
        """取消订阅事件

        Args:
            callback: 回调函数
        """
        self._ensure_initialized()
        wrapper = self._event_wrappers.pop(callback, None)
        if wrapper is not None:
            self._event_bus.unsubscribe(wrapper)

    # ========== 内部信号处理 ==========

    def _on_job_started(self, job_id: str, job_info: dict):
        self.job_started.emit(job_id, job_info)

    def _on_job_progress(self, job_id: str, progress_data: dict):
        self.job_progress.emit(job_id, progress_data)

    def _on_job_finished(self, job_id: str, result: dict):
        self.job_finished.emit(job_id, result)

    def _on_job_failed(self, job_id: str, error_info: dict):
        self.job_failed.emit(job_id, error_info)

    def _on_job_heartbeat(self, job_id: str, heartbeat_data: dict):
        self.job_heartbeat.emit(job_id, heartbeat_data)

    def _on_event_logged(self, job_id: str, event_type: str, data: dict):
        self.event_logged.emit(job_id, event_type, data)


# ========== 全局单例 ==========

_facade_instance: Optional[JobRuntimeFacade] = None


def get_job_runtime_facade() -> JobRuntimeFacade:
    """获取全局 JobRuntimeFacade 单例"""
    global _facade_instance
    if _facade_instance is None:
        _facade_instance = JobRuntimeFacade()
    return _facade_instance
