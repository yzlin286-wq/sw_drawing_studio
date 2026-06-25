"""v2.3 Task 1: Job Runner 进程隔离

使用 QProcess 在独立子进程中执行作业，避免阻塞主进程和 SolidWorks COM 会话。
通过 stdout JSONL 协议接收子进程事件，发布到 JobEventBus。
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QProcess, QObject, Signal

from app.services.job_event_bus import JobEventBus, JobEvent, JobEventType
from app.services.job_queue import JobQueue, JobRecord, JobStatus
from app.services.resource_paths import bundle_root, runtime_path, worker_command

# 项目根目录
REPO_ROOT = bundle_root()
# Worker 脚本目录
WORKERS_DIR = REPO_ROOT / "app" / "workers"

# 作业类型 → Worker 脚本映射
_WORKER_SCRIPTS: dict[str, str] = {
    "cad": "cad_job_worker.py",
    "vision_audit": "vision_audit_worker.py",
    "drawing_review": "drawing_review_worker.py",
    "qc_action": "qc_action_worker.py",
    "diagnostics_action": "diagnostics_action_worker.py",
    "llm_action": "llm_action_worker.py",
    "system_health": "health_check_worker.py",
    "batch": "batch_job_worker.py",
    "mock": "mock_long_job_worker.py",
}


def _validation_trace(stage: str, **data) -> None:
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


def _kill_process_tree(proc: QProcess | None) -> bool:
    """Terminate a worker and its child processes.

    QProcess.kill() only targets the direct worker on Windows. CAD workers spawn
    qc/generation subprocesses, so cancellation must clean the full process tree
    to avoid orphaned SolidWorks automation helpers.
    """
    if proc is None:
        return False
    process_id = getattr(proc, "processId", None)
    pid = int(process_id() or 0) if callable(process_id) else 0
    if pid and sys.platform.startswith("win"):
        try:
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
                check=False,
            )
            wait_for_finished = getattr(proc, "waitForFinished", None)
            if callable(wait_for_finished):
                wait_for_finished(3000)
            return True
        except Exception:
            pass
    proc.kill()
    wait_for_finished = getattr(proc, "waitForFinished", None)
    if callable(wait_for_finished):
        wait_for_finished(3000)
    return True


def _windows_process_rows() -> list[dict]:
    if not sys.platform.startswith("win"):
        return []
    try:
        import ctypes
        from ctypes import wintypes

        class PROCESSENTRY32W(ctypes.Structure):
            _fields_ = [
                ("dwSize", wintypes.DWORD),
                ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.POINTER(wintypes.ULONG)),
                ("th32ModuleID", wintypes.DWORD),
                ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase", wintypes.LONG),
                ("dwFlags", wintypes.DWORD),
                ("szExeFile", wintypes.WCHAR * 260),
            ]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        snapshot = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)
        invalid_handle = ctypes.c_void_p(-1).value
        if snapshot == invalid_handle:
            return []
        try:
            entry = PROCESSENTRY32W()
            entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
            rows: list[dict] = []
            ok = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
            while ok:
                rows.append({
                    "pid": int(entry.th32ProcessID),
                    "parent_pid": int(entry.th32ParentProcessID),
                    "name": str(entry.szExeFile),
                })
                ok = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
            return rows
        finally:
            kernel32.CloseHandle(snapshot)
    except Exception:
        return []


def _kill_descendant_processes(root_pid: int) -> list[dict]:
    """Kill non-SolidWorks descendants left behind by a finished worker."""
    if not root_pid or not sys.platform.startswith("win"):
        return []
    rows = _windows_process_rows()
    by_parent: dict[int, list[dict]] = {}
    for row in rows:
        by_parent.setdefault(int(row.get("parent_pid") or 0), []).append(row)

    descendants: list[dict] = []
    queue = [int(root_pid)]
    while queue:
        parent = queue.pop(0)
        for child in by_parent.get(parent, []):
            descendants.append(child)
            queue.append(int(child.get("pid") or 0))

    stopped: list[dict] = []
    for child in reversed(descendants):
        pid = int(child.get("pid") or 0)
        name = str(child.get("name") or "")
        record = {"pid": pid, "name": name, "parent_pid": child.get("parent_pid")}
        if not pid:
            continue
        if name.lower() == "sldworks.exe":
            record["skipped"] = "solidworks_process_not_auto_killed"
            stopped.append(record)
            continue
        try:
            os.kill(pid, signal.SIGTERM)
            record["stopped"] = True
        except Exception as exc:
            record["stopped"] = False
            record["error"] = str(exc)
        stopped.append(record)
    return stopped


class JobRunner(QObject):
    """作业运行器：使用 QProcess 在子进程中执行作业

    - 单作业串行执行（max_concurrent=1，SolidWorks COM 限制）
    - 通过 stdout JSONL 协议接收进度/事件
    - 自动调度队列中的下一个待执行作业
    """

    job_started = Signal(str, dict)
    job_progress = Signal(str, dict)
    job_finished = Signal(str, dict)
    job_failed = Signal(str, dict)
    job_heartbeat = Signal(str, dict)
    event_logged = Signal(str, str, dict)

    def __init__(
        self,
        event_bus: JobEventBus,
        job_queue: JobQueue,
        max_concurrent: int = 1,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._event_bus = event_bus
        self._job_queue = job_queue
        self._max_concurrent = max_concurrent

        # 当前活跃的 QProcess 及其对应的 job_id
        self._processes: dict[str, QProcess] = {}
        self._process_pids: dict[str, int] = {}
        self._queue_paused = False
        self._event_bus.subscribe(self._relay_event)

    def _relay_event(self, event: JobEvent) -> None:
        """Relay JobEventBus events into Qt signals consumed by the UI facade."""
        data = event.data or {}
        if event.event_type == JobEventType.JOB_STARTED.value:
            self.job_started.emit(event.job_id, data)
        elif event.event_type == JobEventType.PROGRESS.value:
            self.job_progress.emit(event.job_id, data)
        elif event.event_type == JobEventType.JOB_FINISHED.value:
            self.job_finished.emit(event.job_id, data)
        elif event.event_type == JobEventType.JOB_FAILED.value:
            self.job_failed.emit(event.job_id, data)
        elif event.event_type == JobEventType.HEARTBEAT.value:
            self.job_heartbeat.emit(event.job_id, data)
        elif event.event_type == JobEventType.RECOVERED.value:
            self.job_progress.emit(event.job_id, data)
        self.event_logged.emit(event.job_id, event.event_type, data)

    # ── 启动作业 ───────────────────────────────────────────

    def start_job(self, record: JobRecord) -> bool:
        """启动指定作业的子进程

        Returns:
            True 表示成功启动，False 表示失败。
        """
        job_id = record.job_id
        _validation_trace("runner_start_job_enter", job_id=job_id, job_type=record.job_type, run_dir=record.run_dir)
        worker_name = _WORKER_SCRIPTS.get(record.job_type)
        if not worker_name:
            _validation_trace("runner_unknown_job_type", job_id=job_id, job_type=record.job_type)
            self._event_bus.publish(JobEvent(
                event_type=JobEventType.JOB_FAILED.value,
                job_id=job_id,
                timestamp=JobEvent.now_iso(),
                data={"error": f"未知作业类型: {record.job_type}"},
                message=f"未知作业类型: {record.job_type}",
            ))
            self._job_queue.update_status(job_id, JobStatus.FAILED,
                                          error=f"未知作业类型: {record.job_type}")
            return False

        worker_script = WORKERS_DIR / worker_name
        _validation_trace("runner_worker_script_resolved", job_id=job_id, worker_script=str(worker_script))
        if not worker_script.exists():
            _validation_trace("runner_worker_script_missing", job_id=job_id, worker_script=str(worker_script))
            self._event_bus.publish(JobEvent(
                event_type=JobEventType.JOB_FAILED.value,
                job_id=job_id,
                timestamp=JobEvent.now_iso(),
                data={"error": f"Worker 脚本不存在: {worker_script}"},
                message=f"Worker 脚本不存在: {worker_script}",
            ))
            self._job_queue.update_status(job_id, JobStatus.FAILED,
                                          error=f"Worker 脚本不存在: {worker_script}")
            return False

        # 构造子进程参数
        proc = QProcess(self)
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        _validation_trace("runner_qprocess_created", job_id=job_id)

        # 设置环境变量
        env = QProcess.systemEnvironment()
        env.append("PYTHONIOENCODING=utf-8")
        env.append("PYTHONUTF8=1")
        env.append(f"SW_DRAWING_STUDIO_BUNDLE_ROOT={bundle_root()}")
        env.append(f"SW_DRAWING_STUDIO_RUNTIME_ROOT={runtime_path('.')}")
        env.append(f"PYTHONPATH={bundle_root()}{os.pathsep}{os.environ.get('PYTHONPATH', '')}")
        env.append(f"JOB_ID={job_id}")
        env.append(f"RUN_DIR={record.run_dir}")
        env.append(f"RUN_ID={record.run_id}")
        titlebar_overrides = record.result.get("titlebar_overrides")
        if isinstance(titlebar_overrides, dict) and titlebar_overrides:
            env.append(f"TITLEBAR_OVERRIDES_JSON={json.dumps(titlebar_overrides, ensure_ascii=False)}")
        proc.setEnvironment(env)
        _validation_trace("runner_environment_set", job_id=job_id)

        # 连接信号
        proc.readyReadStandardOutput.connect(lambda proc=proc: self._on_stdout(job_id, proc))
        proc.finished.connect(lambda code, status: self._on_finished(job_id, code, status))
        proc.errorOccurred.connect(lambda error: self._on_error(job_id, error))

        # 根据作业类型构造命令行参数
        args = self._build_worker_args(record)
        _validation_trace("runner_worker_args_built", job_id=job_id, args=args)

        # 启动子进程
        program, worker_args = worker_command(record.job_type, worker_script, args)
        _validation_trace("runner_worker_command_built", job_id=job_id, program=str(program), worker_args=worker_args)
        _validation_trace("runner_qprocess_start_call", job_id=job_id)
        proc.start(program, worker_args)
        _validation_trace("runner_qprocess_wait_for_started_enter", job_id=job_id)
        started_ok = proc.waitForStarted(5000)
        _validation_trace("runner_qprocess_wait_for_started_exit", job_id=job_id, started=bool(started_ok), state=str(proc.state()))
        if not started_ok:
            self._event_bus.publish(JobEvent(
                event_type=JobEventType.JOB_FAILED.value,
                job_id=job_id,
                timestamp=JobEvent.now_iso(),
                data={"error": "QProcess 启动超时"},
                message="QProcess 启动超时",
            ))
            self._job_queue.update_status(job_id, JobStatus.FAILED, error="QProcess 启动超时")
            proc.deleteLater()
            return False

        process_id = int(proc.processId())
        self._processes[job_id] = proc
        self._process_pids[job_id] = process_id
        _validation_trace("runner_process_stored", job_id=job_id, pid=process_id)
        self._job_queue.update_status(job_id, JobStatus.RUNNING,
                                      started_at=JobEvent.now_iso(),
                                      sw_pid=process_id)
        _validation_trace("runner_status_running", job_id=job_id, pid=process_id)

        # 发布 job_started 事件
        self._event_bus.publish(JobEvent(
            event_type=JobEventType.JOB_STARTED.value,
            job_id=job_id,
            timestamp=JobEvent.now_iso(),
            data={
                "job_type": record.job_type,
                "part_name": record.part_name,
                "part_path": record.part_path,
                "worker_script": str(worker_script),
            },
            message=f"作业启动: {record.part_name} ({record.job_type})",
        ))
        _validation_trace("runner_job_started_event_published", job_id=job_id)
        return True

    def _build_worker_args(self, record: JobRecord) -> list[str]:
        """根据作业类型构造 Worker 命令行参数"""
        if record.job_type == "cad":
            output_dir = str(record.result.get("output_dir") or record.run_dir or (REPO_ROOT / "drw_output"))
            max_rounds = int(record.result.get("max_rounds", 3))
            return [
                "--job-id", record.job_id,
                "--part-path", record.part_path,
                "--output-dir", output_dir,
                "--max-rounds", str(max_rounds),
                "--timeout-s", str(int(record.timeout_s)),
            ]
        elif record.job_type == "vision_audit":
            # vision_audit 需要 PDF/PNG 路径
            png_path = str(record.result.get("png_path") or "")
            run_dir = str(record.result.get("run_dir") or record.run_dir or "")
            return [
                "--job-id", record.job_id,
                "--pdf-path", record.part_path,  # 复用 part_path 字段传入 PDF 路径
                "--png-path", png_path,
                "--run-dir", run_dir,
            ]
        elif record.job_type == "batch":
            # batch 需要零件列表 JSON
            parts_json = str(record.result.get("parts_json") or record.part_path or "")
            if not parts_json and record.result.get("part_paths"):
                parts_json = json.dumps(record.result.get("part_paths"), ensure_ascii=False)
            output_dir = str(record.result.get("output_dir") or record.run_dir or (REPO_ROOT / "drw_output"))
            max_rounds = int(record.result.get("max_rounds", 3))
            return [
                "--job-id", record.job_id,
                "--parts-json", parts_json,
                "--output-dir", output_dir,
                "--max-rounds", str(max_rounds),
                "--timeout-s", str(int(record.timeout_s)),
            ]
        elif record.job_type == "drawing_review":
            return [
                "--job-id", record.job_id,
                "--action", str(record.result.get("action") or ""),
                "--slddrw-path", str(record.result.get("slddrw_path") or ""),
                "--sldprt-path", str(record.result.get("sldprt_path") or ""),
                "--pdf-path", str(record.result.get("pdf_path") or ""),
                "--png-path", str(record.result.get("png_path") or ""),
                "--run-dir", str(record.run_dir or record.result.get("run_dir") or ""),
                "--run-id", str(record.run_id or record.result.get("run_id") or ""),
            ]
        elif record.job_type == "qc_action":
            return [
                "--job-id", record.job_id,
                "--action", str(record.result.get("action") or ""),
                "--slddrw-path", str(record.result.get("slddrw_path") or ""),
                "--qc-json-path", str(record.result.get("qc_json_path") or ""),
                "--png-path", str(record.result.get("png_path") or ""),
                "--run-dir", str(record.run_dir or record.result.get("run_dir") or ""),
            ]
        elif record.job_type == "diagnostics_action":
            return [
                "--job-id", record.job_id,
                "--action", str(record.result.get("action") or ""),
                "--run-id", str(record.result.get("run_id") or record.run_id or ""),
                "--screenshots-dir", str(record.result.get("screenshots_dir") or ""),
            ]
        elif record.job_type == "llm_action":
            return [
                "--job-id", record.job_id,
                "--action", str(record.result.get("action") or ""),
                "--part-path", str(record.result.get("part_path") or record.part_path or ""),
                "--context", str(record.result.get("context") or ""),
                "--run-dir", str(record.run_dir or record.result.get("run_dir") or ""),
            ]
        elif record.job_type == "system_health":
            return [
                "--job-id", record.job_id,
            ]
        elif record.job_type == "mock":
            return [
                "--job-id", record.job_id,
                "--scenario", str(record.result.get("scenario") or "normal_pass"),
                "--duration-s", str(float(record.result.get("duration_s") or 10.0)),
            ]
        return []

    # ── stdout 事件解析 ────────────────────────────────────

    @staticmethod
    def _is_process_valid(proc: QProcess | None) -> bool:
        if proc is None:
            return False
        try:
            import shiboken6

            return bool(shiboken6.isValid(proc))
        except Exception:
            try:
                proc.state()
                return True
            except RuntimeError:
                return False
            except Exception:
                return False

    def _on_stdout(self, job_id: str, proc: QProcess | None = None) -> None:
        """读取子进程 stdout，解析 JSONL 事件"""
        current = self._processes.get(job_id)
        if proc is None:
            proc = current
        if proc is None or current is not proc or not self._is_process_valid(proc):
            return
        while True:
            try:
                if not proc.canReadLine():
                    break
                raw = proc.readLine()
            except RuntimeError:
                break
            if not raw:
                break
            line = bytes(raw).decode("utf-8", errors="replace").strip()
            if not line:
                continue
            # 尝试解析为 JSON 事件
            try:
                d = json.loads(line)
                event_type = d.get("event_type") or d.get("type", "")
                if not event_type:
                    raise KeyError("event_type")
                d["event_type"] = event_type
                d.setdefault("type", event_type)
                data = d.get("data", {})
                message = d.get("message", "")
                self._append_job_event_log(job_id, d)
                # 发布到事件总线
                self._event_bus.publish(JobEvent(
                    event_type=event_type,
                    job_id=d.get("job_id", job_id),
                    timestamp=d.get("timestamp", JobEvent.now_iso()),
                    data=data,
                    message=message,
                ))
                # 同步更新队列中的作业状态
                self._sync_job_from_event(job_id, event_type, data)
            except (json.JSONDecodeError, KeyError):
                # 非 JSON 行作为普通日志（warning 事件）
                warning_event = {
                    "event_type": JobEventType.WARNING.value,
                    "type": JobEventType.WARNING.value,
                    "job_id": job_id,
                    "timestamp": JobEvent.now_iso(),
                    "data": {"raw_line": line},
                    "message": line,
                }
                self._append_job_event_log(job_id, warning_event)
                self._event_bus.publish(JobEvent(
                    event_type=JobEventType.WARNING.value,
                    job_id=job_id,
                    timestamp=JobEvent.now_iso(),
                    data={"raw_line": line},
                    message=line,
                ))

    def _sync_job_from_event(self, job_id: str, event_type: str, data: dict) -> None:
        """根据事件类型同步更新作业队列状态"""
        if event_type == JobEventType.PROGRESS.value:
            self._job_queue.update_status(
                job_id, JobStatus.RUNNING,
                progress=data.get("progress", 0),
                stage=data.get("stage", ""),
                last_event=event_type,
            )
        elif event_type == JobEventType.HEARTBEAT.value:
            self._job_queue.update_status(job_id, JobStatus.RUNNING, last_event=event_type)
        elif event_type == JobEventType.WARNING.value:
            self._job_queue.update_status(job_id, JobStatus.RUNNING, last_event=event_type)
        elif event_type == JobEventType.RECOVERED.value:
            self._job_queue.update_status(
                job_id, JobStatus.RUNNING,
                stage=data.get("stage", "recovered"),
                last_event=event_type,
            )
        elif event_type == JobEventType.JOB_FINISHED.value:
            result = data.get("result", {})
            self._job_queue.update_status(
                job_id, JobStatus.COMPLETED,
                progress=1.0, stage="done",
                result=result, last_event=event_type,
            )
        elif event_type == JobEventType.JOB_FAILED.value:
            self._job_queue.update_status(
                job_id, JobStatus.FAILED,
                error=data.get("error", ""), last_event=event_type,
            )

    def _append_job_event_log(self, job_id: str, event: dict) -> None:
        """Persist worker JSONL events into the job run directory when available."""
        job = self._job_queue.get_job(job_id)
        if job is None or not job.run_dir:
            return
        try:
            run_dir = Path(job.run_dir)
            run_dir.mkdir(parents=True, exist_ok=True)
            log_path = run_dir / "job_event_log.jsonl"
            with log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
        except Exception:
            # Event persistence must never break UI/event delivery.
            return

    def _publish_runner_failure(
        self,
        job_id: str,
        *,
        error: str,
        message: str,
        exit_code: int | None = None,
        exit_status: object | None = None,
        failure_bucket: str = "qprocess_worker_failed",
        reason: str = "",
        fix_suggestion: str = "",
        recoverable: bool = True,
        extra_data: dict | None = None,
    ) -> None:
        """Publish and persist a runner-generated terminal failure event."""
        job = self._job_queue.get_job(job_id)
        last_event = job.last_event if job else ""
        data = {
            "error": error,
            "failure_bucket": failure_bucket,
            "reason": reason or error,
            "fix_suggestion": fix_suggestion,
            "recoverable": recoverable,
            "exit_code": exit_code,
            "exit_status": str(exit_status) if exit_status is not None else "",
            "last_event": last_event,
            "source": "job_runner",
        }
        if extra_data:
            data.update(extra_data)
        if job and job.job_type in {"cad", "batch"}:
            try:
                from app.services.solidworks_global_lock import release_lock

                data["solidworks_lock_release"] = release_lock(job_id, failure_bucket)
            except Exception as exc:
                data["solidworks_lock_release"] = {
                    "released": False,
                    "status": "release_error",
                    "error": str(exc),
                }
        event = {
            "event_type": JobEventType.JOB_FAILED.value,
            "type": JobEventType.JOB_FAILED.value,
            "job_id": job_id,
            "timestamp": JobEvent.now_iso(),
            "data": data,
            "message": message,
        }
        self._append_job_event_log(job_id, event)
        self._event_bus.publish(JobEvent(
            event_type=JobEventType.JOB_FAILED.value,
            job_id=job_id,
            timestamp=event["timestamp"],
            data=data,
            message=message,
        ))
        self._job_queue.update_status(
            job_id,
            JobStatus.FAILED,
            error=error,
            last_event=JobEventType.JOB_FAILED.value,
        )

    # ── 进程结束/错误 ──────────────────────────────────────

    def _on_finished(self, job_id: str, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        """子进程结束回调"""
        proc = self._processes.get(job_id)
        process_id = int(self._process_pids.pop(job_id, 0) or 0)
        if proc is not None and self._is_process_valid(proc):
            try:
                process_id = process_id or int(proc.processId() or 0)
            except RuntimeError:
                pass
        if proc is not None:
            try:
                self._on_stdout(job_id, proc)
            except RuntimeError:
                pass
        proc = self._processes.pop(job_id, None)
        if proc is not None and self._is_process_valid(proc):
            try:
                proc.readyReadStandardOutput.disconnect()
            except Exception:
                pass
            try:
                proc.deleteLater()
            except RuntimeError:
                pass
        orphan_cleanup = _kill_descendant_processes(process_id)

        job = self._job_queue.get_job(job_id)
        current_status = job.status if job else None

        # 如果已被标记为 completed/failed（通过 stdout 事件），不再重复处理
        if current_status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
            self._process_queue()
            return

        if exit_status == QProcess.ExitStatus.CrashExit:
            self._publish_runner_failure(
                job_id,
                error=f"子进程崩溃 (exit_code={exit_code})",
                message=f"子进程崩溃 (exit_code={exit_code})",
                exit_code=exit_code,
                exit_status=exit_status,
                failure_bucket="qprocess_crash_exit",
                fix_suggestion="检查 worker stderr/stdout、崩溃转储和 job_event_log.jsonl。",
                recoverable=True,
                extra_data={"orphan_descendant_cleanup": orphan_cleanup},
            )
        elif exit_code != 0:
            self._publish_runner_failure(
                job_id,
                error=f"子进程退出码: {exit_code}",
                message=f"子进程退出码: {exit_code}",
                exit_code=exit_code,
                exit_status=exit_status,
                failure_bucket="qprocess_nonzero_exit",
                fix_suggestion="检查 worker stdout JSONL 和 run_dir/manifest.json 中的失败原因。",
                recoverable=True,
                extra_data={"orphan_descendant_cleanup": orphan_cleanup},
            )
        else:
            self._publish_runner_failure(
                job_id,
                error="worker exited without terminal event",
                message="worker exited without job_finished/job_failed",
                exit_code=exit_code,
                exit_status=exit_status,
                failure_bucket="missing_terminal_worker_event",
                reason=(
                    "QProcess exited with code 0, but the worker did not emit "
                    "job_finished or job_failed on stdout JSONL."
                ),
                fix_suggestion=(
                    "Fix the worker to emit a terminal JSONL event and preserve "
                    "failure evidence before exiting."
                ),
                recoverable=True,
                extra_data={"orphan_descendant_cleanup": orphan_cleanup},
            )

        # 自动调度下一个作业
        self._process_queue()

    def _on_error(self, job_id: str, error: QProcess.ProcessError) -> None:
        """子进程错误回调"""
        job = self._job_queue.get_job(job_id)
        if job and job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
            return
        timed_out = getattr(
            QProcess.ProcessError,
            "TimedOut",
            getattr(QProcess.ProcessError, "Timedout", None),
        )
        error_msgs = {
            QProcess.ProcessError.FailedToStart: "子进程启动失败",
            QProcess.ProcessError.Crashed: "子进程崩溃",
            QProcess.ProcessError.WriteError: "子进程写入错误",
            QProcess.ProcessError.ReadError: "子进程读取错误",
            QProcess.ProcessError.UnknownError: "子进程未知错误",
        }
        if timed_out is not None:
            error_msgs[timed_out] = "子进程超时"
        msg = error_msgs.get(error, f"QProcess error: {error}")
        process_error = getattr(error, "value", str(error))
        self._event_bus.publish(JobEvent(
            event_type=JobEventType.WARNING.value,
            job_id=job_id,
            timestamp=JobEvent.now_iso(),
            data={"error": msg, "process_error": process_error},
            message=msg,
        ))
        # 严重错误标记为 failed
        if error in (QProcess.ProcessError.FailedToStart, QProcess.ProcessError.Crashed):
            self._job_queue.update_status(job_id, JobStatus.FAILED, error=msg)

    # ── 取消/暂停/恢复 ─────────────────────────────────────

    def cancel_job(self, job_id: str) -> bool:
        """取消指定作业（终止子进程）"""
        proc = self._processes.get(job_id)
        process_killed = _kill_process_tree(proc)
        process_id = int(self._process_pids.pop(job_id, 0) or 0)
        descendant_cleanup = _kill_descendant_processes(process_id)
        cancelled = self._job_queue.cancel_job(job_id)
        event = JobEvent(
            event_type=JobEventType.WARNING.value,
            job_id=job_id,
            timestamp=JobEvent.now_iso(),
            data={
                "action": "cancelled",
                "reason": "cancelled by user",
                "process_killed": process_killed,
                "orphan_descendant_cleanup": descendant_cleanup,
            },
            message="作业已取消",
        )
        self._append_job_event_log(job_id, event.to_dict())
        self._event_bus.publish(event)
        return cancelled

    def skip_job(self, job_id: str) -> bool:
        """跳过指定作业。

        Pending jobs are marked completed without execution. Running jobs are
        first terminated so the table state cannot claim completion while an old
        worker process keeps running in the background.
        """
        proc = self._processes.get(job_id)
        process_killed = _kill_process_tree(proc)
        process_id = int(self._process_pids.pop(job_id, 0) or 0)
        descendant_cleanup = _kill_descendant_processes(process_id)
        skipped = self._job_queue.skip_job(job_id)
        event = JobEvent(
            event_type=JobEventType.WARNING.value,
            job_id=job_id,
            timestamp=JobEvent.now_iso(),
            data={
                "action": "skipped",
                "reason": "skipped by user",
                "process_killed": process_killed,
                "orphan_descendant_cleanup": descendant_cleanup,
            },
            message="作业已跳过",
        )
        self._append_job_event_log(job_id, event.to_dict())
        self._event_bus.publish(event)
        if proc is None:
            self._process_queue()
        return skipped

    def pause_queue(self) -> None:
        """暂停队列调度（不终止当前运行的作业）"""
        self._queue_paused = True

    def resume_queue(self) -> None:
        """恢复队列调度"""
        self._queue_paused = False
        self._process_queue()

    # ── 状态查询 ───────────────────────────────────────────

    def is_running(self) -> bool:
        """是否有作业正在运行"""
        return len(self._processes) > 0

    def get_active_job(self) -> Optional[JobRecord]:
        """获取当前正在运行的作业记录"""
        with self._job_queue._lock:
            for jid in list(self._processes.keys()):
                job = self._job_queue.get_job(jid)
                if job and job.status == JobStatus.RUNNING:
                    return job
        return None

    # ── 队列调度 ───────────────────────────────────────────

    def _process_queue(self) -> None:
        """检查当前作业是否完成，启动下一个待执行作业"""
        if self._queue_paused:
            return
        if self._job_queue.active_count() >= self._max_concurrent:
            return
        next_job = self._job_queue.get_next_pending()
        if next_job is None:
            return
        # 标记为 queued 再启动
        self._job_queue.update_status(next_job.job_id, JobStatus.QUEUED)
        self.start_job(next_job)
