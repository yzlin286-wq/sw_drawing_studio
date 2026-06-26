"""v2.3 Task 1: CAD 作业 Worker

在独立子进程中执行 CAD 出图 + QC 闭环（调用 drw_qc_loop_v6.py）。
通过 stdout 输出 JSONL 事件，供主进程 JobRunner 解析。

CLI:
    python cad_job_worker.py --job-id <id> --part-path <path> --output-dir <dir>
                             --max-rounds <n> --timeout-s <sec>
"""
from __future__ import annotations

import argparse
import atexit
import faulthandler
import importlib.util
import json
import os
import queue
import shutil
import signal
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path
from types import SimpleNamespace

from app.services.resource_paths import (
    bundle_root,
    child_process_env,
    pipeline_command,
    pipeline_script_path,
    runtime_path,
)
from app.services.solidworks_global_lock import acquire_lock, heartbeat as lock_heartbeat, release_lock
from app.services.solidworks_resource_audit import (
    DOC_REGISTRY_ENV,
    RESOURCE_AUDIT_ENV,
    SolidWorksResourceAudit,
    cleanup_job_owned_documents,
    document_registry_path,
    load_document_registry_events,
    summarize_document_registry,
)

# 确保 stdout 行缓冲（事件实时传递）
sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

BUNDLE_ROOT = bundle_root()
RUNTIME_ROOT = runtime_path(".")
_SUBPROCESS_CREATIONFLAGS = (
    getattr(subprocess, "CREATE_NO_WINDOW", 0)
    if sys.platform.startswith("win")
    else 0
)
_ACTIVE_CONTEXT: dict[str, str] = {"job_id": "", "run_dir": ""}


def _worker_trace(run_dir: str | Path | None, stage: str, **data) -> None:
    if not run_dir:
        return
    try:
        logs_dir = Path(run_dir) / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "epoch": time.time(),
            "pid": os.getpid(),
            "stage": stage,
            **data,
        }
        with (logs_dir / "cad_worker_lifecycle.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _install_process_diagnostics() -> None:
    try:
        faulthandler.enable(all_threads=True)
    except Exception:
        pass

    def _trace_unhandled(exc_type, exc, tb) -> None:
        _worker_trace(
            _ACTIVE_CONTEXT.get("run_dir"),
            "unhandled_exception",
            job_id=_ACTIVE_CONTEXT.get("job_id"),
            exception_type=getattr(exc_type, "__name__", str(exc_type)),
            error=str(exc),
            traceback="".join(traceback.format_exception(exc_type, exc, tb))[-8000:],
        )
        sys.__excepthook__(exc_type, exc, tb)

    def _trace_thread_unhandled(args) -> None:
        _worker_trace(
            _ACTIVE_CONTEXT.get("run_dir"),
            "unhandled_thread_exception",
            job_id=_ACTIVE_CONTEXT.get("job_id"),
            thread=getattr(args.thread, "name", ""),
            exception_type=getattr(args.exc_type, "__name__", str(args.exc_type)),
            error=str(args.exc_value),
            traceback="".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback))[-8000:],
        )
        try:
            threading.__excepthook__(args)
        except Exception:
            pass

    def _trace_atexit() -> None:
        _worker_trace(
            _ACTIVE_CONTEXT.get("run_dir"),
            "process_atexit",
            job_id=_ACTIVE_CONTEXT.get("job_id"),
        )

    def _trace_signal(signum, frame) -> None:
        _worker_trace(
            _ACTIVE_CONTEXT.get("run_dir"),
            "process_signal",
            job_id=_ACTIVE_CONTEXT.get("job_id"),
            signum=signum,
        )
        raise SystemExit(f"signal_{signum}")

    sys.excepthook = _trace_unhandled
    threading.excepthook = _trace_thread_unhandled
    atexit.register(_trace_atexit)
    for sig_name in ("SIGTERM", "SIGINT"):
        sig = getattr(signal, sig_name, None)
        if sig is None:
            continue
        try:
            signal.signal(sig, _trace_signal)
        except Exception:
            pass


_install_process_diagnostics()


def _emit(event_type: str, job_id: str, data: dict | None = None, message: str = "") -> None:
    """向 stdout 输出一条 JSONL 事件"""
    event = {
        "event_type": event_type,
        "job_id": job_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "data": data or {},
        "message": message,
    }
    print(json.dumps(event, ensure_ascii=False), flush=True)


def _heartbeat_loop(
    job_id: str,
    stop_event: threading.Event,
    interval: float = 10.0,
    *,
    solidworks_lock: bool = False,
) -> None:
    """后台心跳线程：每 interval 秒发送一次心跳事件"""
    while not stop_event.is_set():
        if solidworks_lock:
            try:
                lock_heartbeat(job_id)
            except Exception:
                pass
        _emit("heartbeat", job_id, data={"ts": time.time()}, message="worker alive")
        stop_event.wait(interval)


def _emit_document_registry_events(job_id: str, run_dir: str | Path | None, start_index: int = 0) -> int:
    if not run_dir:
        return start_index
    events = load_document_registry_events(document_registry_path(run_dir))
    for event in events[max(0, int(start_index)) :]:
        event_type = str(event.get("event_type") or "")
        if event_type not in {"solidworks_doc_opened", "solidworks_doc_closed", "solidworks_doc_close_failed"}:
            continue
        _emit(
            event_type,
            job_id,
            data=event,
            message=f"{event_type}: {event.get('role') or ''} {event.get('title') or event.get('path') or ''}".strip(),
        )
    return len(events)


def _resource_block_payload(snapshot: dict | None, cleanup: dict | None = None) -> dict:
    snapshot = snapshot or {}
    cleanup = cleanup or {}
    blockers = list(snapshot.get("resource_blockers") or [])
    if cleanup and not cleanup.get("pass", True):
        blockers.append({
            "key": "solidworks_cleanup_not_clean",
            "status": cleanup.get("status", "blocked_by_solidworks_resource_pressure"),
            "reason": cleanup.get("reason", "job-owned SolidWorks document cleanup did not pass"),
        })
    return {
        "status": "blocked_by_solidworks_resource_pressure",
        "failure_bucket": "solidworks_resource_pressure",
        "resource_blockers": blockers,
        "audit_path": snapshot.get("audit_path", ""),
        "cleanup_status": cleanup.get("status", ""),
        "recoverable": True,
        "fix_suggestion": "Inspect solidworks_resource_audit.json and solidworks_document_registry.json before another CAD rerun.",
    }


def _finalize_solidworks_resources(
    *,
    job_id: str,
    output_dir: str,
    resource_audit: SolidWorksResourceAudit,
    solidworks_lock: dict,
    registry_event_cursor: int,
    release_reason: str,
) -> dict:
    registry_event_cursor = _emit_document_registry_events(job_id, output_dir, registry_event_cursor)
    cleanup = cleanup_job_owned_documents(output_dir, job_id)
    registry_event_cursor = _emit_document_registry_events(job_id, output_dir, registry_event_cursor)
    registry_summary = cleanup.get("registry_summary") or summarize_document_registry(output_dir)
    _emit(
        "solidworks_cleanup_finished",
        job_id,
        data={
            "status": cleanup.get("status"),
            "pass": bool(cleanup.get("pass")),
            "cleanup_records": cleanup.get("cleanup_records") or [],
            "document_registry": registry_summary,
        },
        message="SolidWorks job-owned document cleanup finished",
    )
    after_snapshot = resource_audit.capture(
        "after_cad_cleanup",
        lock_result=solidworks_lock,
        registry_summary=registry_summary,
    )
    if after_snapshot.get("resource_blockers"):
        _emit(
            "solidworks_resource_blocked",
            job_id,
            data=_resource_block_payload(after_snapshot, cleanup),
            message="SolidWorks resource audit found blockers after CAD cleanup",
        )
    release = release_lock(job_id, release_reason)
    return {
        "cleanup": cleanup,
        "after_resource_audit": after_snapshot,
        "release": release,
        "registry_event_cursor": registry_event_cursor,
    }


def _copy_if_exists(
    src: Path,
    dst_dir: Path,
    *,
    min_mtime: float | None = None,
    stale_artifacts: list[dict] | None = None,
) -> str:
    if not src.exists():
        return ""
    try:
        src_mtime = src.stat().st_mtime
    except OSError:
        src_mtime = 0.0
    if min_mtime is not None and src_mtime < (float(min_mtime) - 1.0):
        if stale_artifacts is not None:
            stale_artifacts.append({
                "path": str(src),
                "mtime": src_mtime,
                "min_mtime": float(min_mtime),
                "reason": "legacy_output_older_than_job_start",
            })
        return ""
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / src.name
    shutil.copy2(src, dst)
    return str(dst)


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


def _descendant_process_rows(root_pid: int) -> list[dict]:
    if not root_pid or not sys.platform.startswith("win"):
        return []
    by_parent: dict[int, list[dict]] = {}
    for row in _windows_process_rows():
        by_parent.setdefault(int(row.get("parent_pid") or 0), []).append(row)
    descendants: list[dict] = []
    pending = [int(root_pid)]
    while pending:
        parent = pending.pop(0)
        for child in by_parent.get(parent, []):
            descendants.append(child)
            pending.append(int(child.get("pid") or 0))
    return descendants


def _kill_descendant_processes(root_pid: int) -> list[dict]:
    stopped: list[dict] = []
    for child in reversed(_descendant_process_rows(root_pid)):
        pid = int(child.get("pid") or 0)
        name = str(child.get("name") or "")
        record = {"pid": pid, "parent_pid": child.get("parent_pid"), "name": name}
        if not pid:
            continue
        if name.lower() == "sldworks.exe":
            record["skipped"] = "solidworks_process_not_auto_killed"
            stopped.append(record)
            continue
        try:
            if sys.platform.startswith("win"):
                subprocess.run(
                    ["taskkill", "/PID", str(pid), "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=5,
                    check=False,
                )
            else:
                os.kill(pid, 15)
            record["stopped"] = True
        except Exception as exc:
            record["stopped"] = False
            record["error"] = str(exc)
        stopped.append(record)
    return stopped


def _kill_popen_tree(proc: subprocess.Popen | None) -> list[dict]:
    if proc is None:
        return []
    pid = int(getattr(proc, "pid", 0) or 0)
    stopped: list[dict] = []
    if sys.platform.startswith("win"):
        try:
            if pid:
                subprocess.run(
                    ["taskkill", "/PID", str(pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=10,
                    check=False,
                )
                stopped.append({"pid": pid, "name": "root_process", "stopped": True})
        except Exception:
            pass
        stopped.extend(_kill_descendant_processes(pid))
        return stopped
    if proc.poll() is not None:
        return _kill_descendant_processes(pid)
    try:
        proc.kill()
        stopped.append({"pid": pid, "name": "root_process", "stopped": True})
    except Exception:
        pass
    stopped.extend(_kill_descendant_processes(pid))
    return stopped


def _run_subprocess_streamed(
    cmd: list[str],
    *,
    cwd: str,
    env: dict[str, str],
    timeout_s: float,
    job_id: str,
    run_dir: str | Path | None = None,
) -> dict:
    """Run a subprocess while keeping stdout streaming and lifecycle truthful."""
    _worker_trace(run_dir, "subprocess_popen_start", cmd=cmd, cwd=cwd, timeout_s=timeout_s)
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        env=env,
        creationflags=_SUBPROCESS_CREATIONFLAGS,
    )
    _worker_trace(run_dir, "subprocess_popen_started", child_pid=proc.pid)
    line_queue: queue.Queue[str] = queue.Queue()
    stdout_closed = threading.Event()
    subprocess_tail: list[str] = []
    line_count = 0
    start = time.time()
    stdout_eof_reported = False

    def _reader() -> None:
        try:
            assert proc.stdout is not None
            for raw in proc.stdout:
                line_queue.put(raw)
        except Exception as exc:
            line_queue.put(f"[cad_worker_stdout_reader_error] {exc}")
        finally:
            stdout_closed.set()

    reader = threading.Thread(target=_reader, name=f"cad-worker-stdout-{job_id}", daemon=True)
    reader.start()
    _worker_trace(run_dir, "subprocess_stdout_reader_started", child_pid=proc.pid)

    def _drain() -> int:
        nonlocal line_count
        drained = 0
        while True:
            try:
                raw = line_queue.get_nowait()
            except queue.Empty:
                break
            line = str(raw).rstrip("\r\n")
            if not line:
                continue
            drained += 1
            line_count += 1
            _tail_append(subprocess_tail, line)
            _emit("warning", job_id, data={"source": "subprocess", "line": line}, message=line)
            progress = min(0.05 + line_count * 0.005, 0.90)
            if line_count % 10 == 0:
                _emit(
                    "progress",
                    job_id,
                    data={"progress": round(progress, 3), "stage": f"出图中 (lines={line_count})"},
                    message=f"出图进行中... ({line_count} 行)",
                )
        return drained

    next_wait_trace = time.time() + 0.5
    while True:
        _drain()
        rc = proc.poll()
        if rc is not None:
            _worker_trace(run_dir, "subprocess_poll_returned", child_pid=proc.pid, returncode=rc)
            break
        elapsed = time.time() - start
        if elapsed > timeout_s:
            cleanup = _kill_popen_tree(proc)
            reader.join(timeout=3)
            _drain()
            _worker_trace(
                run_dir,
                "subprocess_timeout",
                child_pid=proc.pid,
                elapsed_s=round(elapsed, 3),
                cleanup=cleanup,
            )
            return {
                "proc_pid": proc.pid,
                "returncode": None,
                "timeout": True,
                "duration_s": round(elapsed, 3),
                "lines": line_count,
                "subprocess_tail": subprocess_tail,
                "cleanup": cleanup,
            }
        if stdout_closed.is_set() and not stdout_eof_reported:
            stdout_eof_reported = True
            _worker_trace(run_dir, "subprocess_stdout_closed_before_exit", child_pid=proc.pid)
            _emit(
                "warning",
                job_id,
                data={"source": "cad_worker", "child_pid": proc.pid, "line": "subprocess_stdout_closed_before_exit"},
                message="subprocess stdout closed before process exit; waiting for process termination",
            )
        if time.time() >= next_wait_trace:
            _worker_trace(
                run_dir,
                "subprocess_waiting",
                child_pid=proc.pid,
                elapsed_s=round(elapsed, 3),
                stdout_closed=stdout_closed.is_set(),
                queued_lines=line_queue.qsize(),
            )
            next_wait_trace = time.time() + 1.0
        time.sleep(0.2)

    reader.join(timeout=3)
    _drain()
    time.sleep(0.2)
    descendants = _descendant_process_rows(int(proc.pid or 0))
    cleanup: list[dict] = []
    if descendants:
        cleanup = _kill_descendant_processes(int(proc.pid or 0))
    _worker_trace(
        run_dir,
        "subprocess_result_ready",
        child_pid=proc.pid,
        returncode=proc.returncode,
        lines=line_count,
        orphan_descendants=descendants,
        orphan_cleanup=cleanup,
    )
    return {
        "proc_pid": proc.pid,
        "returncode": int(proc.returncode or 0),
        "timeout": False,
        "duration_s": round(time.time() - start, 3),
        "lines": line_count,
        "subprocess_tail": subprocess_tail,
        "stdout_eof_before_exit": stdout_eof_reported,
        "orphan_descendants": descendants,
        "orphan_descendant_cleanup": cleanup,
    }


def _run_qc_loop_inprocess(
    qc_script_key: str,
    part_path: str,
    *,
    max_rounds: int,
    timeout_s: float,
    job_id: str,
    env: dict[str, str],
    run_dir: str | Path | None = None,
) -> dict:
    if qc_script_key != "drw_qc_loop_v6":
        return {"used": False, "reason": "unsupported_qc_script"}

    script_path = pipeline_script_path(qc_script_key)
    _worker_trace(
        run_dir,
        "qc_loop_inprocess_import_start",
        script=str(script_path),
        max_rounds=max_rounds,
        timeout_s=timeout_s,
    )
    old_env: dict[str, str | None] = {}
    for key, value in env.items():
        old_env[key] = os.environ.get(key)
        os.environ[key] = str(value)
    os.environ["V6_SUBPROC_TIMEOUT"] = str(int(timeout_s))
    os.environ["QC_LOOP_MAX_ROUNDS"] = str(int(max_rounds))
    try:
        module_name = f"_swds_drw_qc_loop_v6_{job_id}"
        spec = importlib.util.spec_from_file_location(module_name, script_path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot import qc loop script: {script_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        run_qc_loop = getattr(module, "run_qc_loop", None)
        if not callable(run_qc_loop):
            raise RuntimeError(f"run_qc_loop missing in {script_path}")
        _worker_trace(run_dir, "qc_loop_inprocess_run_start", script=str(script_path))
        result = run_qc_loop(part_path, max_rounds=max_rounds)
        final_pass = bool(result.get("final_pass")) if isinstance(result, dict) else False
        payload = {
            "used": True,
            "returncode": 0 if final_pass else 1,
            "timeout": False,
            "lines": 0,
            "subprocess_tail": [],
            "qc_loop_result": result,
        }
        _worker_trace(run_dir, "qc_loop_inprocess_run_done", result=payload)
        return payload
    except BaseException as exc:
        payload = {
            "used": True,
            "returncode": None,
            "timeout": False,
            "lines": 0,
            "subprocess_tail": [str(exc)],
            "error": str(exc),
            "exception_type": type(exc).__name__,
        }
        _worker_trace(run_dir, "qc_loop_inprocess_exception", result=payload)
        return payload
    finally:
        for key, old_value in old_env.items():
            if old_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old_value


def _child_result_has_generated_artifacts(child_result: dict) -> bool:
    try:
        qc_loop_result = child_result.get("qc_loop_result") if isinstance(child_result, dict) else {}
        for round_rec in (qc_loop_result or {}).get("rounds") or []:
            if round_rec.get("generated_path"):
                return True
            sub_result = (round_rec.get("subprocess") or {}).get("result") or {}
            if any(sub_result.get(key) for key in ("slddrw", "pdf", "dxf", "png")):
                return True
    except Exception:
        return False
    return False


def _tail_append(lines: list[str], line: str, limit: int = 80) -> None:
    lines.append(line)
    if len(lines) > limit:
        del lines[: len(lines) - limit]


def _classify_failure(reason: str, result_data: dict | None = None) -> dict:
    result_data = result_data or {}
    evidence_lines = [str(line) for line in (result_data.get("subprocess_tail") or [])]
    evidence_text = "\n".join(evidence_lines + [str(reason)])

    if "blocked_by_solidworks_lock" in evidence_text or result_data.get("status") == "blocked_by_solidworks_lock":
        lock_result = result_data.get("solidworks_lock") if isinstance(result_data.get("solidworks_lock"), dict) else {}
        return {
            "failure_bucket": "solidworks_lock_conflict",
            "failure_reason": "status=blocked_by_solidworks_lock",
            "fix_suggestion": str(lock_result.get("fix_suggestion") or "等待当前 CAD job 完成，或手动确认后释放 stale lock"),
            "recoverable": True,
            "evidence": [json.dumps(lock_result.get("owner", {}), ensure_ascii=False)],
        }

    if "solidworks_active_object_timeout" in evidence_text or "GetActiveObject probe timed out" in evidence_text:
        return {
            "failure_bucket": "solidworks_com_active_object_timeout",
            "failure_reason": "SolidWorks COM active object did not respond within the bounded probe.",
            "fix_suggestion": (
                "请先保存 SolidWorks 中的未保存文档，关闭可能阻塞的对话框；"
                "如仍不响应，请重启 SolidWorks 后重新运行 006 样张修正测试。"
            ),
            "recoverable": True,
            "evidence": [
                line for line in evidence_lines
                if "sw_connect" in line or "solidworks_active_object_timeout" in line or "GetActiveObject" in line
            ][-8:],
        }

    if "subprocess_exit_code" in str(reason):
        return {
            "failure_bucket": "cad_subprocess_failed",
            "failure_reason": str(reason),
            "fix_suggestion": "查看 job_event_log.jsonl 中的子进程尾部日志，修复 CAD/QC 子流程失败原因后重试。",
            "recoverable": True,
            "evidence": evidence_lines[-8:],
        }

    return {
        "failure_bucket": "cad_worker_failure",
        "failure_reason": str(reason),
        "fix_suggestion": "查看 manifest.json、sw_session.json 和 job_event_log.jsonl 后重试。",
        "recoverable": True,
        "evidence": evidence_lines[-8:],
    }


def _read_com_value(obj, name: str):
    try:
        value = getattr(obj, name)
        return value() if callable(value) else value
    except Exception:
        return None


def _write_sw_session_snapshot(run_dir: Path, result_data: dict) -> str:
    """Write a truthful SolidWorks session snapshot for release evidence."""
    path = run_dir / "sw_session.json"
    snapshot = {
        "schema": "sw_drawing_studio.sw_session.v1",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source": "cad_job_worker",
        "status": "unknown",
        "connection_method": "",
        "sw_pid": None,
        "sw_revision": "",
        "visible": None,
        "active_doc_title": "",
        "active_doc_path": "",
        "reason": "",
    }
    try:
        import win32com.client

        method = "get_active_object"
        try:
            sw = win32com.client.GetActiveObject("SldWorks.Application")
        except Exception as active_exc:
            method = "dispatch"
            try:
                sw = win32com.client.Dispatch("SldWorks.Application")
                snapshot["reason"] = f"GetActiveObject failed; Dispatch succeeded: {active_exc}"
            except Exception as dispatch_exc:
                snapshot["status"] = "failed"
                snapshot["connection_method"] = "failed"
                snapshot["reason"] = f"GetActiveObject failed: {active_exc}; Dispatch failed: {dispatch_exc}"
                path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
                result_data["sw_session"] = str(path)
                return str(path)

        snapshot["status"] = "connected"
        snapshot["connection_method"] = method
        revision = _read_com_value(sw, "RevisionNumber")
        if revision is not None:
            snapshot["sw_revision"] = str(revision)
        visible = _read_com_value(sw, "Visible")
        if visible is not None:
            snapshot["visible"] = bool(visible)
        pid_value = _read_com_value(sw, "GetProcessID")
        try:
            pid = int(pid_value) if pid_value is not None else None
            snapshot["sw_pid"] = pid if pid and pid > 0 else None
        except Exception:
            snapshot["reason"] = f"GetProcessID unreadable: {pid_value!r}"
        active_doc = _read_com_value(sw, "ActiveDoc")
        if active_doc is not None:
            title = _read_com_value(active_doc, "GetTitle")
            doc_path = _read_com_value(active_doc, "GetPathName")
            snapshot["active_doc_title"] = str(title or "")
            snapshot["active_doc_path"] = str(doc_path or "")
    except Exception as exc:
        snapshot["status"] = "failed"
        snapshot["reason"] = str(exc)

    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    result_data["sw_session"] = str(path)
    return str(path)


def _ensure_vision_and_final_quality(
    run_dir: Path,
    drawing_dir: Path,
    qc_dir: Path,
    base: str,
    qc_data: dict,
    artifacts: dict[str, list[str]],
    result_data: dict,
) -> None:
    """Generate vision_qc_v2.json and final_quality.json in the worker run_dir."""
    qc_json = qc_dir / f"{base}_v5_qc.json"
    if not qc_json.exists():
        candidates = sorted(qc_dir.glob("*_qc.json"))
        qc_json = candidates[0] if candidates else Path()
    if not qc_json or not qc_json.exists():
        result_data["vision_final_quality_error"] = "qc_json_missing"
        return

    png_path = drawing_dir / f"{base}_v5.PNG"
    if not png_path.exists():
        candidates = sorted(drawing_dir.glob("*.PNG")) + sorted(drawing_dir.glob("*.png"))
        png_path = candidates[0] if candidates else Path()

    try:
        from app.services.final_quality import compute_final_quality
        from app.services.vision_qc_v2 import run_vision_qc_v2
        from app.services.vision_qc_v6 import run_vision_qc_v6

        vqc2 = run_vision_qc_v2(qc_json, png_path if png_path.exists() else Path(""), run_dir)
        vision_path = run_dir / "qc" / "vision_qc_v2.json"
        if vision_path.exists():
            os.utime(vision_path, None)
            sp = str(vision_path)
            if sp not in artifacts["qc"]:
                artifacts["qc"].append(sp)

        ctx = SimpleNamespace(
            hard_fail=list(qc_data.get("hard_fail") or result_data.get("hard_fail") or []),
            warnings=list(qc_data.get("warnings") or result_data.get("warnings") or []),
            drawing_usable=qc_data.get("drawing_usable") or result_data.get("drawing_usable") or {},
            dimension_grade=qc_data.get("dimension_grade", ""),
            usable_for=qc_data.get("usable_for", []),
            drawing_accuracy_score=qc_data.get("drawing_accuracy_score", {}),
        )
        final_quality = compute_final_quality(ctx, vqc2, run_dir=run_dir)
        fq_path = run_dir / "qc" / "final_quality.json"
        fq_path.write_text(json.dumps(final_quality, ensure_ascii=False, indent=2), encoding="utf-8")
        sp = str(fq_path)
        if sp not in artifacts["qc"]:
            artifacts["qc"].append(sp)
        result_data["final_quality"] = final_quality
        result_data["vision_qc_v2"] = str(vision_path)
        result_data["final_quality_path"] = str(fq_path)

        blueprint_path = qc_dir / "drawing_blueprint.json"
        try:
            vqc6 = run_vision_qc_v6(
                png_path=png_path if png_path.exists() else drawing_dir / f"{base}_v5.PNG",
                run_dir=run_dir,
                blueprint_path=blueprint_path if blueprint_path.exists() else None,
                qc_json_path=qc_json if qc_json.exists() else None,
            )
            vision6_path = run_dir / "qc" / "vision_qc_v6.json"
            if vision6_path.exists():
                os.utime(vision6_path, None)
                sp = str(vision6_path)
                if sp not in artifacts["qc"]:
                    artifacts["qc"].append(sp)
            result_data["vision_qc_v6"] = str(vision6_path)
            result_data["vision_qc_v6_status"] = vqc6.get("status", "")
            result_data["vision_qc_v6_visual_acceptance_pass"] = vqc6.get("visual_acceptance_pass")
        except Exception as exc:
            result_data["vision_qc_v6_error"] = str(exc)
    except Exception as exc:
        result_data["vision_final_quality_error"] = str(exc)


def _collect_worker_artifacts(part_path: str, output_dir: str, result_data: dict) -> dict:
    """Copy v5 pipeline artifacts into the worker run_dir and write manifest.

    The legacy v5/v6 scripts still write canonical outputs to drw_output/v5.
    For v2.3 process-isolated jobs, the UI needs a self-contained run_dir for
    diagnostics, audit, retry, and EXE validation evidence.
    """
    base = Path(part_path).stem
    run_dir = Path(output_dir)
    drawing_dir = run_dir / "drawing"
    qc_dir = run_dir / "qc"
    logs_dir = run_dir / "logs"
    manifest_path = run_dir / "manifest.json"
    v5_dir = runtime_path("drw_output") / "v5"
    min_artifact_mtime = result_data.get("job_started_at")
    stale_artifacts: list[dict] = []

    artifacts: dict[str, list[str]] = {"drawing": [], "qc": [], "logs": []}
    for ext in ("SLDDRW", "PDF", "DXF", "PNG"):
        copied = _copy_if_exists(
            v5_dir / f"{base}_v5.{ext}",
            drawing_dir,
            min_mtime=min_artifact_mtime,
            stale_artifacts=stale_artifacts,
        )
        if copied:
            artifacts["drawing"].append(copied)

    for suffix in ("_v5_qc.json", "_v5_warnings.json", "_v5_vision.json"):
        copied = _copy_if_exists(
            v5_dir / f"{base}{suffix}",
            qc_dir,
            min_mtime=min_artifact_mtime,
            stale_artifacts=stale_artifacts,
        )
        if copied:
            artifacts["qc"].append(copied)

    # Keep QC artifacts emitted directly into RUN_DIR/qc by classification and
    # sidecar services in the manifest.
    if qc_dir.exists():
        for p in sorted(qc_dir.glob("*.json")):
            sp = str(p)
            if sp not in artifacts["qc"]:
                artifacts["qc"].append(sp)

    sw_session = _write_sw_session_snapshot(run_dir, result_data)

    qc_data = {}
    qc_local = qc_dir / f"{base}_v5_qc.json"
    if qc_local.exists():
        try:
            qc_data = json.loads(qc_local.read_text(encoding="utf-8"))
        except Exception as exc:
            result_data["local_qc_error"] = str(exc)

    _ensure_vision_and_final_quality(
        run_dir=run_dir,
        drawing_dir=drawing_dir,
        qc_dir=qc_dir,
        base=base,
        qc_data=qc_data,
        artifacts=artifacts,
        result_data=result_data,
    )
    if qc_dir.exists():
        for p in sorted(qc_dir.glob("*.json")):
            sp = str(p)
            if sp not in artifacts["qc"]:
                artifacts["qc"].append(sp)

    core_files_ok = all(
        (drawing_dir / f"{base}_v5.{ext}").exists()
        for ext in ("SLDDRW", "PDF", "DXF", "PNG")
    )
    drawing_usable = qc_data.get("drawing_usable") or result_data.get("drawing_usable") or {}
    hard_fail = qc_data.get("hard_fail", result_data.get("hard_fail", []))
    warnings = qc_data.get("warnings", result_data.get("warnings", []))
    run_id = result_data.get("run_id") or run_dir.name

    manifest = {
        "schema": "sw_drawing_studio.worker_manifest.v1",
        "job_type": "cad",
        "part_path": part_path,
        "part_base": base,
        "run_id": run_id,
        "run_dir": str(run_dir),
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "returncode": result_data.get("returncode"),
        "line_count": result_data.get("lines"),
        "core_files_ok": core_files_ok,
        "drawing_usable": drawing_usable,
        "hard_fail": hard_fail,
        "warnings": warnings,
        "qc_pass": qc_data.get("pass", result_data.get("qc_pass")),
        "qc_score_pass_count": qc_data.get("score_pass_count", result_data.get("qc_pass_count")),
        "dimension_grade": qc_data.get("dimension_grade", ""),
        "dimension_sources": qc_data.get("dimension_sources", {}),
        "display_dim_count": qc_data.get("display_dim_count", 0),
        "note_dim_count": qc_data.get("note_dim_count", 0),
        "model_associative_dim_count": qc_data.get("model_associative_dim_count", 0),
        "addin_dimension_count": qc_data.get("addin_dimension_count", 0),
        "docmgr_reference_count": qc_data.get("docmgr_reference_count", 0),
        "drawing_accuracy_score": qc_data.get("drawing_accuracy_score", {}),
        "final_quality": result_data.get("final_quality", {}),
        "vision_final_quality_error": result_data.get("vision_final_quality_error", ""),
        "vision_qc_v6": result_data.get("vision_qc_v6", ""),
        "vision_qc_v6_status": result_data.get("vision_qc_v6_status", ""),
        "vision_qc_v6_visual_acceptance_pass": result_data.get("vision_qc_v6_visual_acceptance_pass"),
        "vision_qc_v6_error": result_data.get("vision_qc_v6_error", ""),
        "artifact_freshness": {
            "min_mtime": min_artifact_mtime,
            "stale_artifacts": stale_artifacts,
        },
        "output_files": artifacts,
        "sw_session": sw_session,
    }
    run_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    artifacts["logs"].append(str(manifest_path))
    artifacts["logs"].append(sw_session)

    result_data["manifest"] = str(manifest_path)
    result_data["run_dir"] = str(run_dir)
    result_data["output_files"] = artifacts
    result_data["core_files_ok"] = core_files_ok
    result_data["drawing_usable"] = drawing_usable
    result_data["hard_fail"] = hard_fail
    result_data["warnings"] = warnings
    result_data["stale_artifacts"] = stale_artifacts
    result_data["qc_pass"] = manifest["qc_pass"]
    result_data["qc_pass_count"] = manifest["qc_score_pass_count"]
    return manifest


def _write_failure_manifest(part_path: str, output_dir: str, result_data: dict, reason: str) -> dict:
    """Write non-blocking failure evidence without copying stale v5 outputs."""
    base = Path(part_path).stem
    run_dir = Path(output_dir)
    logs_dir = run_dir / "logs"
    run_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    failure = _classify_failure(reason, result_data)
    failure_bucket = failure.get("failure_bucket") or "cad_worker_failure"
    effective_reason = failure.get("failure_reason") or reason
    run_id = result_data.get("run_id") or run_dir.name

    sw_session_path = run_dir / "sw_session.json"
    sw_snapshot = {
        "schema": "sw_drawing_studio.sw_session.v1",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source": "cad_job_worker",
        "status": "not_collected",
        "connection_method": "skipped_on_worker_failure",
        "sw_pid": None,
        "sw_revision": "",
        "visible": None,
        "active_doc_title": "",
        "active_doc_path": "",
        "reason": effective_reason,
        "failure_bucket": failure_bucket,
        "fix_suggestion": failure.get("fix_suggestion", ""),
        "recoverable": bool(failure.get("recoverable", True)),
        "evidence": failure.get("evidence", []),
    }
    sw_session_path.write_text(json.dumps(sw_snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    manifest_path = run_dir / "manifest.json"
    hard_fail = list(result_data.get("hard_fail") or ["subprocess_failed"])
    if failure_bucket and failure_bucket not in hard_fail:
        hard_fail.insert(0, failure_bucket)
    manifest = {
        "schema": "sw_drawing_studio.worker_manifest.v1",
        "job_type": "cad",
        "part_path": part_path,
        "part_base": base,
        "run_id": run_id,
        "run_dir": str(run_dir),
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "returncode": result_data.get("returncode"),
        "line_count": result_data.get("lines"),
        "core_files_ok": False,
        "drawing_usable": {"pass": False, "reason": effective_reason},
        "hard_fail": hard_fail,
        "warnings": list(result_data.get("warnings") or []),
        "qc_pass": False,
        "qc_score_pass_count": 0,
        "dimension_grade": "",
        "dimension_sources": {},
        "display_dim_count": 0,
        "note_dim_count": 0,
        "model_associative_dim_count": 0,
        "addin_dimension_count": 0,
        "docmgr_reference_count": 0,
        "drawing_accuracy_score": {},
        "final_quality": {},
        "vision_final_quality_error": "skipped_on_worker_failure",
        "output_files": {
            "drawing": [],
            "qc": [],
            "logs": [str(manifest_path), str(sw_session_path)],
        },
        "sw_session": str(sw_session_path),
        "failure_reason": effective_reason,
        "failure_bucket": failure_bucket,
        "fix_suggestion": failure.get("fix_suggestion", ""),
        "recoverable": bool(failure.get("recoverable", True)),
        "failure_evidence": failure.get("evidence", []),
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    result_data["manifest"] = str(manifest_path)
    result_data["sw_session"] = str(sw_session_path)
    result_data["worker_manifest"] = manifest
    return manifest


def _prepare_reference_intent_dimension_contract(part_path: str, output_dir: str) -> dict:
    """Prepare the v4.2 006 reference-intent plan/contract inside run_dir/qc.

    This function is offline-only. It must be called by the lock-owning CAD
    worker before launching the real SolidWorks subprocess so the generator and
    downstream QC consume the same explicit dimension intent.
    """
    base = Path(part_path).stem
    if base != "LB26001-A-04-006":
        return {"enabled": False, "status": "not_required", "base": base}
    try:
        from app.services.reference_intent_dimension_executor import (
            build_execution_contract,
            write_execution_contract,
        )
        from app.services.reference_intent_dimension_planner import (
            build_reference_intent_dimension_plan,
            load_reference_profile,
            write_reference_intent_dimension_plan,
        )

        run_dir = Path(output_dir)
        qc_dir = run_dir / "qc"
        qc_dir.mkdir(parents=True, exist_ok=True)
        profile = load_reference_profile(base)
        plan = build_reference_intent_dimension_plan(base, reference_profile=profile)
        plan_path = write_reference_intent_dimension_plan(
            plan,
            qc_dir / "reference_intent_dimension_plan_006.json",
        )
        expected_drawing = run_dir / "drawing" / f"{base}_v5.SLDDRW"
        contract = build_execution_contract(
            plan,
            drawing_path=expected_drawing,
            run_dir=run_dir,
        )
        contract_path = write_execution_contract(
            contract,
            qc_dir / "reference_intent_dimension_contract_006.json",
        )
        ui_correction_evidence = _prepare_lb26001_006_ui_correction_evidence(base, qc_dir)
        return {
            "enabled": True,
            "status": "ready",
            "base": base,
            "plan_path": str(plan_path),
            "contract_path": str(contract_path),
            "ui_correction_evidence": ui_correction_evidence,
            "required_display_dim_count": plan.get("required_display_dim_count"),
            "dimension_target_count": len(plan.get("dimensions") or []),
            "operation_count": contract.get("operation_count"),
            "requires_solidworks_lock": True,
            "ui_thread_may_execute": False,
            "allowed_entrypoint": "cad_job_worker",
        }
    except Exception as exc:
        return {
            "enabled": True,
            "status": "failed",
            "base": base,
            "error": str(exc),
            "failure_bucket": "reference_intent_contract_prepare_failed",
            "fix_suggestion": "检查 reference_profiles_v4.json 与 reference_intent_dimension_planner.py，修复后再运行 006 CAD worker。",
        }


def _prepare_lb26001_006_ui_correction_evidence(base: str, qc_dir: Path) -> dict:
    if base != "LB26001-A-04-006":
        return {"enabled": False, "status": "not_required", "base": base}
    packet_path = Path(
        os.environ.get(
            "SWDS_LB26001_006_RERUN_PACKET_PATH",
            str(runtime_path("drw_output") / "diagnostics" / "lb26001_006_rerun_packet_v4_2.json"),
        )
    )
    try:
        packet = json.loads(packet_path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {
            "enabled": True,
            "status": "missing_or_unreadable",
            "base": base,
            "source_packet": str(packet_path),
            "error": str(exc),
            "required_for_acceptance": False,
        }
    verdict = packet.get("current_006_ui_verdict") if isinstance(packet, dict) else {}
    if not isinstance(verdict, dict):
        verdict = {}
    bucket_path = Path(
        os.environ.get(
            "SWDS_LB26001_006_UI_DEFECT_BUCKETS_PATH",
            str(runtime_path("drw_output") / "diagnostics" / "lb26001_006_ui_defect_buckets_v4_4.json"),
        )
    )
    try:
        bucket_report = json.loads(bucket_path.read_text(encoding="utf-8-sig"))
    except Exception:
        bucket_report = {}
    active_buckets = list(bucket_report.get("active_buckets") or []) if isinstance(bucket_report, dict) else []
    evidence = {
        "schema": "sw_drawing_studio.lb26001_006_ui_correction_evidence.v4_2",
        "base": base,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source_packet": str(packet_path),
        "ui_defect_buckets_report": str(bucket_path),
        "ui_defect_buckets_status": str(bucket_report.get("status") or "") if isinstance(bucket_report, dict) else "",
        "active_defect_buckets": active_buckets,
        "packet_status": str(packet.get("status") or ""),
        "packet_build_ready": bool(packet.get("packet_build_ready")),
        "real_cad_allowed_at_packet_time": bool(packet.get("real_cad_allowed_now")),
        "api_is_not_final_judgement": True,
        "application_ui_screenshot_is_final_gate": True,
        "current_006_ui_verdict": verdict,
        "comparison_image": str(verdict.get("comparison_image") or ""),
        "failed_visual_checklist_items": list(verdict.get("failed_visual_checklist_items") or []),
        "latest_manual_findings": list(verdict.get("latest_manual_findings") or []),
        "latest_manual_required_correction": str(verdict.get("latest_manual_required_correction") or ""),
        "ui_screenshot_files": list(verdict.get("ui_screenshot_files") or []),
        "generated_png": str(verdict.get("generated_png") or ""),
        "reference_png": str(verdict.get("reference_png") or ""),
    }
    out_path = qc_dir / "lb26001_006_ui_correction_evidence.json"
    out_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "enabled": True,
        "status": "ready",
        "base": base,
        "path": str(out_path),
        "source_packet": str(packet_path),
        "ui_defect_buckets_report": str(bucket_path),
        "active_defect_buckets": active_buckets,
        "failed_visual_check_count": len(evidence["failed_visual_checklist_items"]),
        "latest_manual_finding_count": len(evidence["latest_manual_findings"]),
        "comparison_image": evidence["comparison_image"],
        "ui_thread_may_execute": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="CAD Job Worker")
    parser.add_argument("--job-id", required=True, help="作业 ID")
    parser.add_argument("--part-path", required=True, help="零件文件路径 (.SLDPRT)")
    parser.add_argument("--output-dir", default="", help="输出目录")
    parser.add_argument("--max-rounds", type=int, default=3, help="最大 QC 迭代轮数")
    parser.add_argument("--timeout-s", type=float, default=600, help="超时时间（秒）")
    args = parser.parse_args()

    job_id: str = args.job_id
    part_path: str = args.part_path
    output_dir: str = args.output_dir or str(runtime_path("drw_output"))
    max_rounds: int = args.max_rounds
    timeout_s: float = args.timeout_s
    run_id = os.environ.get("RUN_ID", "")
    _ACTIVE_CONTEXT["job_id"] = job_id
    _ACTIVE_CONTEXT["run_dir"] = output_dir
    _worker_trace(
        output_dir,
        "main_enter",
        job_id=job_id,
        part_path=part_path,
        max_rounds=max_rounds,
        timeout_s=timeout_s,
        run_id=run_id,
    )

    # ── 校验输入 ───────────────────────────────────────────
    if not Path(part_path).exists():
        _emit("job_failed", job_id,
              data={"error": f"零件文件不存在: {part_path}"},
              message=f"零件文件不存在: {part_path}")
        return 1

    # ── 定位 QC 循环脚本 ──────────────────────────────────
    v6_script = pipeline_script_path("drw_qc_loop_v6")
    v5_script = pipeline_script_path("drw_qc_loop_v5")
    use_v5 = os.environ.get("USE_V5", "") == "1"
    if v6_script.exists() and not use_v5:
        qc_script_key = "drw_qc_loop_v6"
        qc_script = str(v6_script)
    elif v5_script.exists():
        qc_script_key = "drw_qc_loop_v5"
        qc_script = str(v5_script)
    else:
        _emit("job_failed", job_id,
              data={"error": "QC 循环脚本不存在（v6/v5 均未找到）"},
              message="QC 循环脚本不存在")
        return 1

    # ── 发布 job_started ──────────────────────────────────
    job_started_at = time.time()
    _emit("job_started", job_id,
          data={
              "job_type": "cad",
              "part_path": part_path,
              "output_dir": output_dir,
              "max_rounds": max_rounds,
              "run_id": run_id,
              "worker_script": str(__file__),
              "qc_script": qc_script,
          },
          message=f"CAD 作业启动: {Path(part_path).stem}")

    resource_audit = SolidWorksResourceAudit(output_dir, job_id, run_id)
    registry_event_cursor = 0

    lock_timeout_s = float(os.environ.get("SW_GLOBAL_LOCK_TIMEOUT_S", "30") or "30")
    solidworks_lock = acquire_lock(
        owner_project=os.environ.get("SW_DRAWING_STUDIO_OWNER_PROJECT", "sw_drawing_studio"),
        owner_workspace=str(runtime_path(".")),
        job_id=job_id,
        operation="cad_job_worker.generate_drawing",
        part_path=part_path,
        timeout_sec=lock_timeout_s,
        run_id=run_id,
        allow_restart_sw=os.environ.get("SWDS_ALLOW_RESTART_SW", "0") == "1",
    )
    _worker_trace(
        output_dir,
        "lock_acquire_result",
        acquired=bool(solidworks_lock.get("acquired")),
        status=solidworks_lock.get("status"),
        reason=solidworks_lock.get("reason"),
    )
    if not solidworks_lock.get("acquired"):
        lock_block_snapshot = resource_audit.capture(
            "lock_blocked",
            lock_result=solidworks_lock,
            include_com_documents=False,
        )
        _emit(
            "solidworks_resource_blocked",
            job_id,
            data={
                "status": "blocked_by_solidworks_lock",
                "solidworks_lock": solidworks_lock,
                "resource_audit": lock_block_snapshot,
            },
            message="SolidWorks global lock blocked CAD resource audit",
        )
        result_data = {
            "returncode": 4,
            "lines": 0,
            "run_id": run_id,
            "run_dir": output_dir,
            "job_started_at": time.time(),
            "status": "blocked_by_solidworks_lock",
            "error": "blocked_by_solidworks_lock",
            "hard_fail": ["solidworks_lock_conflict"],
            "warnings": [],
            "solidworks_lock": solidworks_lock,
        }
        if output_dir:
            try:
                result_data["worker_manifest"] = _write_failure_manifest(
                    part_path,
                    output_dir,
                    result_data,
                    "blocked_by_solidworks_lock",
                )
            except Exception as exc:
                result_data["artifact_collect_error"] = str(exc)
        _emit(
            "job_failed",
            job_id,
            data={
                "error": "blocked_by_solidworks_lock",
                "status": "blocked_by_solidworks_lock",
                "failure_bucket": "solidworks_lock_conflict",
                "owner": solidworks_lock.get("owner", {}),
                "reason": solidworks_lock.get("reason", ""),
                "fix_suggestion": solidworks_lock.get("fix_suggestion", ""),
                "recoverable": True,
            },
            message="SolidWorks 正被另一个任务使用",
        )
        return 4

    _emit(
        "solidworks_resource_audit_started",
        job_id,
        data={
            "audit_path": str(resource_audit.path),
            "registry_path": str(document_registry_path(output_dir)),
            "lock_status": solidworks_lock.get("status"),
        },
        message="SolidWorks resource audit started",
    )
    before_resource_snapshot = resource_audit.capture("before_cad", lock_result=solidworks_lock)
    if before_resource_snapshot.get("resource_blockers"):
        result_data = {
            "returncode": 7,
            "lines": 0,
            "run_id": run_id,
            "run_dir": output_dir,
            "job_started_at": job_started_at,
            "status": "blocked_by_solidworks_resource_pressure",
            "error": "blocked_by_solidworks_resource_pressure",
            "hard_fail": ["solidworks_resource_pressure"],
            "warnings": [],
            "solidworks_lock": solidworks_lock,
            "solidworks_resource_audit": str(resource_audit.path),
            "solidworks_resource_snapshot": before_resource_snapshot,
        }
        if output_dir:
            try:
                result_data["worker_manifest"] = _write_failure_manifest(
                    part_path,
                    output_dir,
                    result_data,
                    "blocked_by_solidworks_resource_pressure",
                )
            except Exception as exc:
                result_data["artifact_collect_error"] = str(exc)
        _resource_final = _finalize_solidworks_resources(
            job_id=job_id,
            output_dir=output_dir,
            resource_audit=resource_audit,
            solidworks_lock=solidworks_lock,
            registry_event_cursor=registry_event_cursor,
            release_reason="cad_job_worker_resource_pressure_before",
        )
        result_data["solidworks_cleanup"] = _resource_final["cleanup"]
        result_data["solidworks_resource_audit_after"] = _resource_final["after_resource_audit"]
        result_data["solidworks_lock_release"] = _resource_final["release"]
        _emit(
            "solidworks_resource_blocked",
            job_id,
            data=_resource_block_payload(before_resource_snapshot),
            message="SolidWorks resource audit blocked CAD before COM work",
        )
        _emit(
            "job_failed",
            job_id,
            data={
                "error": "blocked_by_solidworks_resource_pressure",
                "status": "blocked_by_solidworks_resource_pressure",
                "failure_bucket": "solidworks_resource_pressure",
                "resource_blockers": before_resource_snapshot.get("resource_blockers") or [],
                "fix_suggestion": "Inspect solidworks_resource_audit.json before retrying real CAD.",
                "recoverable": True,
            },
            message="SolidWorks resource pressure blocked CAD before COM work",
        )
        return 7

    reference_intent_contract = _prepare_reference_intent_dimension_contract(part_path, output_dir)
    if reference_intent_contract.get("enabled") and reference_intent_contract.get("status") != "ready":
        result_data = {
            "returncode": 5,
            "lines": 0,
            "run_id": run_id,
            "run_dir": output_dir,
            "job_started_at": job_started_at,
            "status": "reference_intent_contract_prepare_failed",
            "error": reference_intent_contract.get("error", "reference_intent_contract_prepare_failed"),
            "hard_fail": ["reference_intent_contract_prepare_failed"],
            "warnings": [],
            "reference_intent_dimension": reference_intent_contract,
        }
        if output_dir:
            try:
                result_data["worker_manifest"] = _write_failure_manifest(
                    part_path,
                    output_dir,
                    result_data,
                    str(result_data["error"]),
                )
            except Exception as exc:
                result_data["artifact_collect_error"] = str(exc)
        _resource_final = _finalize_solidworks_resources(
            job_id=job_id,
            output_dir=output_dir,
            resource_audit=resource_audit,
            solidworks_lock=solidworks_lock,
            registry_event_cursor=registry_event_cursor,
            release_reason="reference_intent_contract_prepare_failed",
        )
        result_data["solidworks_cleanup"] = _resource_final["cleanup"]
        result_data["solidworks_resource_audit_after"] = _resource_final["after_resource_audit"]
        result_data["solidworks_lock_release"] = _resource_final["release"]
        _emit(
            "job_failed",
            job_id,
            data={
                "error": result_data["error"],
                "status": "reference_intent_contract_prepare_failed",
                "failure_bucket": "reference_intent_contract_prepare_failed",
                "fix_suggestion": reference_intent_contract.get("fix_suggestion", ""),
                "recoverable": True,
            },
            message="006 reference-intent dimension contract could not be prepared",
        )
        return 5
    if reference_intent_contract.get("enabled"):
        _worker_trace(
            output_dir,
            "reference_intent_contract_ready",
            status=reference_intent_contract.get("status"),
            dimension_target_count=reference_intent_contract.get("dimension_target_count"),
            operation_count=reference_intent_contract.get("operation_count"),
        )
        _emit(
            "progress",
            job_id,
            data={
                "progress": 0.03,
                "stage": "reference_intent_contract_ready",
                "reference_intent_dimension": reference_intent_contract,
            },
            message="006 reference-intent dimension contract ready",
        )

    # ── 启动心跳线程 ──────────────────────────────────────
    stop_hb = threading.Event()
    hb_thread = threading.Thread(
        target=_heartbeat_loop,
        args=(job_id, stop_hb, 10.0),
        kwargs={"solidworks_lock": True},
        daemon=True,
    )
    hb_thread.start()

    # ── 构造子进程环境 ─────────────────────────────────────
    env = child_process_env()
    env["V6_SUBPROC_TIMEOUT"] = str(int(timeout_s))
    env["QC_LOOP_MAX_ROUNDS"] = str(max_rounds)
    env["JOB_ID"] = job_id
    env["SW_DRAWING_STUDIO_LOCK_JOB_ID"] = job_id
    env[DOC_REGISTRY_ENV] = str(document_registry_path(output_dir))
    env[RESOURCE_AUDIT_ENV] = str(resource_audit.path)
    if os.environ.get("CAD_WORKER_SUBPROCESS_GENERATOR", "") != "1":
        env["QC_LOOP_INPROCESS_GENERATOR"] = "1"
    if output_dir:
        env["RUN_DIR"] = output_dir
    if run_id:
        env["RUN_ID"] = run_id
    titlebar_overrides = os.environ.get("TITLEBAR_OVERRIDES_JSON", "")
    if titlebar_overrides:
        env["TITLEBAR_OVERRIDES_JSON"] = titlebar_overrides
    if reference_intent_contract.get("plan_path"):
        env["REFERENCE_INTENT_DIMENSION_PLAN_PATH"] = str(reference_intent_contract["plan_path"])
    if reference_intent_contract.get("contract_path"):
        env["REFERENCE_INTENT_DIMENSION_CONTRACT_PATH"] = str(reference_intent_contract["contract_path"])
    ui_correction_evidence = reference_intent_contract.get("ui_correction_evidence")
    if isinstance(ui_correction_evidence, dict) and ui_correction_evidence.get("path"):
        env["LB26001_006_UI_CORRECTION_EVIDENCE_PATH"] = str(ui_correction_evidence["path"])
    if isinstance(ui_correction_evidence, dict) and ui_correction_evidence.get("ui_defect_buckets_report"):
        env["LB26001_006_UI_DEFECT_BUCKETS_PATH"] = str(ui_correction_evidence["ui_defect_buckets_report"])

    cmd = pipeline_command(qc_script_key, [part_path])
    _worker_trace(output_dir, "pipeline_command_ready", cmd=cmd)

    # ── 执行 QC 循环子进程 ────────────────────────────────
    rc = -1
    line_count = 0
    subprocess_tail: list[str] = []
    child_result: dict = {}
    try:
        _emit("progress", job_id,
              data={"progress": 0.05, "stage": "启动出图流程"},
              message="正在启动出图流程...")

        use_subprocess_qc_loop = os.environ.get("CAD_WORKER_SUBPROCESS_QC_LOOP", "") == "1"
        if qc_script_key == "drw_qc_loop_v6" and not use_subprocess_qc_loop:
            child_result = _run_qc_loop_inprocess(
                qc_script_key,
                part_path,
                max_rounds=max_rounds,
                timeout_s=timeout_s,
                job_id=job_id,
                env=env,
                run_dir=output_dir,
            )
        else:
            child_result = _run_subprocess_streamed(
                cmd,
                cwd=str(RUNTIME_ROOT),
                env=env,
                timeout_s=timeout_s,
                job_id=job_id,
                run_dir=output_dir,
            )
        _worker_trace(output_dir, "subprocess_helper_returned", child_result=child_result)
        line_count = int(child_result.get("lines") or 0)
        subprocess_tail = list(child_result.get("subprocess_tail") or [])
        if child_result.get("error"):
            raise RuntimeError(str(child_result.get("error")))
        if child_result.get("timeout"):
            raise subprocess.TimeoutExpired(cmd, timeout_s)
        rc = int(child_result.get("returncode") if child_result.get("returncode") is not None else -1)

    except subprocess.TimeoutExpired:
        stop_hb.set()
        result_data = {
            "returncode": None,
            "lines": line_count,
            "run_id": run_id,
            "run_dir": output_dir,
            "job_started_at": job_started_at,
            "error": f"subprocess_timeout_{timeout_s}s",
            "hard_fail": ["subprocess_timeout"],
            "warnings": [],
            "subprocess_tail": subprocess_tail,
            "subprocess_result": child_result,
        }
        if reference_intent_contract.get("enabled"):
            result_data["reference_intent_dimension"] = reference_intent_contract
        failure = _classify_failure(result_data["error"], result_data)
        failure["failure_bucket"] = "cad_subprocess_timeout"
        failure["failure_reason"] = result_data["error"]
        failure["fix_suggestion"] = "检查 SolidWorks 对话框、COM 卡死和 drw_generate_v6 输出尾部后重试。"
        result_data.update(failure)
        if output_dir:
            try:
                result_data["worker_manifest"] = _write_failure_manifest(
                    part_path,
                    output_dir,
                    result_data,
                    result_data["failure_reason"],
                )
            except Exception as exc:
                result_data["artifact_collect_error"] = str(exc)
        _resource_final = _finalize_solidworks_resources(
            job_id=job_id,
            output_dir=output_dir,
            resource_audit=resource_audit,
            solidworks_lock=solidworks_lock,
            registry_event_cursor=registry_event_cursor,
            release_reason="cad_job_worker_timeout",
        )
        result_data["solidworks_cleanup"] = _resource_final["cleanup"]
        result_data["solidworks_resource_audit_after"] = _resource_final["after_resource_audit"]
        result_data["solidworks_lock_release"] = _resource_final["release"]
        _emit("job_failed", job_id,
              data={
                  "error": f"子进程超时 ({timeout_s}s)",
                  "failure_bucket": result_data.get("failure_bucket", ""),
                  "reason": result_data.get("failure_reason", ""),
                  "fix_suggestion": result_data.get("fix_suggestion", ""),
                  "recoverable": True,
              },
              message=f"出图超时: {timeout_s}s")
        return 2
    except Exception as exc:
        stop_hb.set()
        result_data = {
            "returncode": None,
            "lines": line_count,
            "run_id": run_id,
            "run_dir": output_dir,
            "job_started_at": job_started_at,
            "error": str(exc),
            "hard_fail": ["cad_worker_exception"],
            "warnings": [],
            "subprocess_tail": subprocess_tail,
            "subprocess_result": child_result,
        }
        if reference_intent_contract.get("enabled"):
            result_data["reference_intent_dimension"] = reference_intent_contract
        failure = _classify_failure(str(exc), result_data)
        failure["failure_bucket"] = failure.get("failure_bucket") or "cad_worker_exception"
        result_data.update(failure)
        if output_dir:
            try:
                result_data["worker_manifest"] = _write_failure_manifest(
                    part_path,
                    output_dir,
                    result_data,
                    result_data.get("failure_reason") or str(exc),
                )
            except Exception as manifest_exc:
                result_data["artifact_collect_error"] = str(manifest_exc)
        _resource_final = _finalize_solidworks_resources(
            job_id=job_id,
            output_dir=output_dir,
            resource_audit=resource_audit,
            solidworks_lock=solidworks_lock,
            registry_event_cursor=registry_event_cursor,
            release_reason="cad_job_worker_exception",
        )
        result_data["solidworks_cleanup"] = _resource_final["cleanup"]
        result_data["solidworks_resource_audit_after"] = _resource_final["after_resource_audit"]
        result_data["solidworks_lock_release"] = _resource_final["release"]
        _emit("job_failed", job_id,
              data={
                  "error": str(exc),
                  "failure_bucket": result_data.get("failure_bucket", ""),
                  "reason": result_data.get("failure_reason", ""),
                  "fix_suggestion": result_data.get("fix_suggestion", ""),
                  "recoverable": True,
              },
              message=f"执行异常: {exc}")
        return 3
    finally:
        stop_hb.set()

    orphan_cleanup = list(child_result.get("orphan_descendant_cleanup") or [])
    if orphan_cleanup:
        result_data = {
            "returncode": rc,
            "lines": line_count,
            "run_id": run_id,
            "run_dir": output_dir,
            "job_started_at": job_started_at,
            "error": "subprocess_left_orphan_descendants",
            "hard_fail": ["cad_subprocess_orphan_descendants"],
            "warnings": [],
            "subprocess_tail": subprocess_tail,
            "subprocess_result": child_result,
            "orphan_descendant_cleanup": orphan_cleanup,
        }
        if reference_intent_contract.get("enabled"):
            result_data["reference_intent_dimension"] = reference_intent_contract
        result_data.update({
            "failure_bucket": "cad_subprocess_orphan_descendants",
            "failure_reason": "subprocess exited while descendant worker processes were still alive",
            "fix_suggestion": "修复 drw_qc_loop_v6/drw_generate_v6，使生成链在退出前等待并关闭所有子进程。",
            "recoverable": True,
        })
        if output_dir:
            try:
                result_data["worker_manifest"] = _write_failure_manifest(
                    part_path,
                    output_dir,
                    result_data,
                    result_data["failure_reason"],
                )
            except Exception as exc:
                result_data["artifact_collect_error"] = str(exc)
        _resource_final = _finalize_solidworks_resources(
            job_id=job_id,
            output_dir=output_dir,
            resource_audit=resource_audit,
            solidworks_lock=solidworks_lock,
            registry_event_cursor=registry_event_cursor,
            release_reason="cad_job_worker_orphan_descendants",
        )
        result_data["solidworks_cleanup"] = _resource_final["cleanup"]
        result_data["solidworks_resource_audit_after"] = _resource_final["after_resource_audit"]
        result_data["solidworks_lock_release"] = _resource_final["release"]
        _emit("job_failed", job_id,
              data={
                  "error": result_data["error"],
                  "returncode": rc,
                  "failure_bucket": result_data["failure_bucket"],
                  "reason": result_data["failure_reason"],
                  "fix_suggestion": result_data["fix_suggestion"],
                  "recoverable": True,
                  "orphan_descendant_cleanup": orphan_cleanup,
              },
              message="出图子进程遗留后代进程")
        return 6

    # ── 结果判定 ───────────────────────────────────────────
    if rc == 0:
        _worker_trace(output_dir, "result_branch_success", returncode=rc, lines=line_count)
        _emit("progress", job_id,
              data={"progress": 0.95, "stage": "收集结果"},
              message="出图完成，收集结果...")
        # 尝试读取 QC JSON
        result_data: dict = {
            "returncode": rc,
            "lines": line_count,
            "run_id": run_id,
            "run_dir": output_dir,
            "job_started_at": job_started_at,
        }
        if reference_intent_contract.get("enabled"):
            result_data["reference_intent_dimension"] = reference_intent_contract
        base = Path(part_path).stem
        manifest_path = Path(output_dir) / "manifest.json" if output_dir else Path()
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                result_data["manifest"] = str(manifest_path)
                result_data["run_id"] = manifest.get("run_id") or run_id
                result_data["run_dir"] = str(manifest_path.parent)
                result_data["drawing_usable"] = manifest.get("drawing_usable", {})
                result_data["hard_fail"] = manifest.get("hard_fail", [])
                result_data["warnings"] = manifest.get("warnings", [])
                result_data["qc_pass_count"] = manifest.get("qc_pass_count", 0)
                result_data["vision_score"] = manifest.get("vision_score")
                result_data["output_files"] = manifest.get("output_files", {})
                result_data["exception_summary"] = manifest.get("exception_summary", [])
                result_data["bom_status"] = manifest.get("bom_status", "")
                result_data["process_status"] = manifest.get("process_status", "")
                result_data["quote_status"] = manifest.get("quote_status", "")
                result_data["fallback_used"] = manifest.get("fallback_used", False)
            except Exception as exc:
                result_data["manifest_error"] = str(exc)

        qc_json_path = Path(output_dir) / "qc" / f"{base}_v5_qc.json" if output_dir else Path()
        if not qc_json_path.exists():
            qc_json_path = runtime_path("drw_output") / "v5" / f"{base}_v5_qc.json"
        if qc_json_path.exists():
            try:
                qc_data = json.loads(qc_json_path.read_text(encoding="utf-8"))
                result_data["qc"] = qc_data
                result_data["qc_pass"] = bool(qc_data.get("pass"))
                result_data["qc_pass_count"] = result_data.get("qc_pass_count") or qc_data.get("score_pass_count", 0)
            except Exception:
                pass
        if output_dir:
            try:
                manifest = _collect_worker_artifacts(part_path, output_dir, result_data)
                result_data["worker_manifest"] = manifest
            except Exception as exc:
                result_data["artifact_collect_error"] = str(exc)
        _resource_final = _finalize_solidworks_resources(
            job_id=job_id,
            output_dir=output_dir,
            resource_audit=resource_audit,
            solidworks_lock=solidworks_lock,
            registry_event_cursor=registry_event_cursor,
            release_reason="cad_job_worker_finished",
        )
        result_data["solidworks_cleanup"] = _resource_final["cleanup"]
        result_data["solidworks_resource_audit_after"] = _resource_final["after_resource_audit"]
        result_data["solidworks_lock_release"] = _resource_final["release"]
        _worker_trace(output_dir, "emit_job_finished", result_data=result_data)
        _emit("job_finished", job_id,
              data={"result": result_data},
              message=f"CAD 作业完成 (rc={rc})")
        return 0
    else:
        _worker_trace(output_dir, "result_branch_failure", returncode=rc, lines=line_count)
        result_data: dict = {
            "returncode": rc,
            "lines": line_count,
            "run_id": run_id,
            "run_dir": output_dir,
            "job_started_at": job_started_at,
            "error": f"subprocess_exit_code_{rc}",
            "hard_fail": ["subprocess_failed"],
            "warnings": [],
            "subprocess_tail": subprocess_tail,
        }
        if reference_intent_contract.get("enabled"):
            result_data["reference_intent_dimension"] = reference_intent_contract
        failure = _classify_failure(result_data["error"], result_data)
        if _child_result_has_generated_artifacts(child_result):
            failure.update({
                "failure_bucket": "cad_qc_failed_after_generation",
                "failure_reason": "CAD generation wrote fresh artifacts, but the QC loop did not reach final_pass.",
                "fix_suggestion": "Use the copied run_dir drawing artifacts for UI screenshot review, then fix the reported QC/visual issues.",
                "recoverable": True,
            })
        result_data.update(failure)
        if output_dir:
            try:
                if _child_result_has_generated_artifacts(child_result):
                    manifest = _collect_worker_artifacts(part_path, output_dir, result_data)
                else:
                    manifest = _write_failure_manifest(
                        part_path,
                        output_dir,
                        result_data,
                        result_data.get("failure_reason") or result_data["error"],
                    )
                result_data["worker_manifest"] = manifest
            except Exception as exc:
                result_data["artifact_collect_error"] = str(exc)
        _resource_final = _finalize_solidworks_resources(
            job_id=job_id,
            output_dir=output_dir,
            resource_audit=resource_audit,
            solidworks_lock=solidworks_lock,
            registry_event_cursor=registry_event_cursor,
            release_reason="cad_job_worker_failed",
        )
        result_data["solidworks_cleanup"] = _resource_final["cleanup"]
        result_data["solidworks_resource_audit_after"] = _resource_final["after_resource_audit"]
        result_data["solidworks_lock_release"] = _resource_final["release"]
        _worker_trace(output_dir, "emit_job_failed", result_data=result_data)
        _emit("job_failed", job_id,
              data={
                  "error": f"子进程退出码: {rc}",
                  "returncode": rc,
                  "failure_bucket": result_data.get("failure_bucket", ""),
                  "reason": result_data.get("failure_reason", ""),
                  "fix_suggestion": result_data.get("fix_suggestion", ""),
                  "recoverable": bool(result_data.get("recoverable", True)),
              },
              message=f"出图失败 (rc={rc})")
        return rc if rc > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
