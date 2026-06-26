from __future__ import annotations

import csv
import io
import json
import os
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

from app.services.resource_paths import runtime_path
from app.services.solidworks_global_lock import (
    conflict_log_tail,
    default_lock_path,
    explain_conflict,
    is_lock_stale,
    read_lock,
)


@dataclass
class ProcessInfo:
    pid: int
    name: str
    command_line: str = ""
    responding: bool | None = None
    main_window_title: str = ""
    workspace_hint: str = ""


ProcessProvider = Callable[[], list[ProcessInfo]]
_UNSET = object()


def enumerate_relevant_processes() -> list[ProcessInfo]:
    processes = _enumerate_with_powershell()
    if processes:
        return processes
    return _enumerate_with_tasklist()


def build_conflict_report(
    *,
    processes: Iterable[ProcessInfo] | None = None,
    lock: dict[str, Any] | None | object = _UNSET,
) -> dict[str, Any]:
    proc_list = list(processes) if processes is not None else enumerate_relevant_processes()
    lock_data = read_lock() if lock is _UNSET else lock
    lock_data = lock_data if isinstance(lock_data, dict) else None

    sw_processes = [p for p in proc_list if p.name.lower() in {"sldworks.exe", "sldworks"}]
    cad_workers = [p for p in proc_list if "cad_job_worker.py" in p.command_line]
    batch_workers = [p for p in proc_list if "batch_job_worker.py" in p.command_line]
    waiting_jobs = [
        p for p in proc_list
        if "blocked_by_solidworks_lock" in p.command_line or "solidworks_global_lock" in p.command_line
    ]
    smoke_leftovers = [
        p for p in proc_list
        if "sw_drawing_studio.exe" in p.command_line.lower() and "smoke" in p.command_line.lower()
    ]
    dialog_guards = [
        p for p in proc_list
        if "dialogguard" in p.command_line.lower() or "sw_dialog_guard" in p.command_line.lower()
    ]

    findings: list[dict[str, Any]] = []
    level = "OK"

    def add(severity: str, key: str, message: str, fix_suggestion: str = "", details: dict[str, Any] | None = None) -> None:
        nonlocal level
        findings.append({
            "severity": severity,
            "key": key,
            "message": message,
            "fix_suggestion": fix_suggestion,
            "details": details or {},
        })
        if severity == "FAIL":
            level = "FAIL"
        elif severity == "WARNING" and level != "FAIL":
            level = "WARNING"

    active_cad_workers = cad_workers + batch_workers
    if len(active_cad_workers) > 1:
        add(
            "FAIL",
            "multiple_active_cad_workers",
            "检测到多个 CAD worker 正在运行",
            "等待其中一个任务结束；不要并行控制同一个 SolidWorks",
            {"workers": [asdict(p) for p in active_cad_workers]},
        )

    not_responding = [p for p in sw_processes if p.responding is False]
    if not_responding:
        add(
            "FAIL",
            "solidworks_not_responding",
            "SolidWorks 无响应",
            "请先保存未保存文档，关闭阻塞对话框；确认当前 lock owner 后再考虑重启",
            {"processes": [asdict(p) for p in not_responding]},
        )

    unsaved_documents = [p for p in sw_processes if _title_has_unsaved_marker(p.main_window_title)]
    if unsaved_documents:
        add(
            "FAIL",
            "solidworks_unsaved_document_visible",
            "检测到 SolidWorks 标题栏存在未保存标记",
            "请先在 SolidWorks 中手动保存或关闭未保存文档；自动化不得重启或控制该会话",
            {"processes": [asdict(p) for p in unsaved_documents]},
        )

    if sw_processes and not lock_data:
        add(
            "WARNING",
            "solidworks_running_without_lock",
            "SW running 但无 SolidWorks 全局锁",
            "真实 CAD / Add-in / OpenDoc6 操作前必须通过 worker 获取全局锁",
            {"processes": [asdict(p) for p in sw_processes]},
        )

    if lock_data and is_lock_stale(lock_data):
        add(
            "WARNING",
            "stale_lock_detected",
            "检测到锁已过期，可释放",
            "释放前确认 owner 进程不存在且没有未保存文档",
            {"lock": lock_data},
        )

    if smoke_leftovers:
        add(
            "WARNING",
            "smoke_exe_leftovers",
            "检测到 smoke EXE 残留",
            "关闭残留 smoke 进程后再运行真实 CAD 验证",
            {"processes": [asdict(p) for p in smoke_leftovers]},
        )

    if waiting_jobs:
        add(
            "WARNING",
            "waiting_jobs_detected",
            "检测到等待 SolidWorks 锁的任务",
            "保持串行，等待当前任务完成",
            {"processes": [asdict(p) for p in waiting_jobs]},
        )

    if dialog_guards and not lock_data:
        add(
            "FAIL",
            "dialog_guard_without_owner_lock",
            "DialogGuard 在无 owner lock 状态下运行",
            "停止非 owner DialogGuard；真实 COM 操作必须先持锁",
            {"processes": [asdict(p) for p in dialog_guards]},
        )

    if not findings:
        findings.append({
            "severity": "OK",
            "key": "no_conflict_detected",
            "message": "未检测到 SolidWorks 互斥冲突",
            "fix_suggestion": "",
            "details": {},
        })

    conflict = explain_conflict(lock_data) if lock_data else {"reason": "no_active_solidworks_lock", "fix_suggestion": ""}
    fail_count = sum(1 for item in findings if item.get("severity") == "FAIL")
    warning_count = sum(1 for item in findings if item.get("severity") == "WARNING")
    report = {
        "schema": "sw_drawing_studio.solidworks_conflict_report.v1",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "level": level,
        "status": "pass" if level == "OK" else level.lower(),
        "pass": level == "OK",
        "fail_count": fail_count,
        "warning_count": warning_count,
        "lock_path": str(default_lock_path()),
        "lock": lock_data,
        "lock_owner": conflict.get("owner", {}),
        "lock_reason": conflict.get("reason", ""),
        "fix_suggestion": _primary_fix(findings) or conflict.get("fix_suggestion", ""),
        "counts": {
            "solidworks_processes": len(sw_processes),
            "cad_job_workers": len(cad_workers),
            "batch_job_workers": len(batch_workers),
            "waiting_jobs": len(waiting_jobs),
            "smoke_leftovers": len(smoke_leftovers),
            "dialog_guards": len(dialog_guards),
        },
        "solidworks_processes": [asdict(p) for p in sw_processes],
        "cad_workers": [asdict(p) for p in cad_workers],
        "batch_workers": [asdict(p) for p in batch_workers],
        "waiting_jobs": [asdict(p) for p in waiting_jobs],
        "smoke_leftovers": [asdict(p) for p in smoke_leftovers],
        "dialog_guards": [asdict(p) for p in dialog_guards],
        "findings": findings,
        "conflict_log_tail": conflict_log_tail(10),
    }
    return report


def write_conflict_report(
    out_path: str | Path | None = None,
    *,
    processes: Iterable[ProcessInfo] | None = None,
    lock: dict[str, Any] | None | object = _UNSET,
) -> dict[str, Any]:
    report = build_conflict_report(processes=processes, lock=lock)
    path = Path(out_path) if out_path else runtime_path("drw_output") / "diagnostics" / "conflict_report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report["report_path"] = str(path)
    return report


def _primary_fix(findings: list[dict[str, Any]]) -> str:
    for severity in ("FAIL", "WARNING"):
        for item in findings:
            if item.get("severity") == severity and item.get("fix_suggestion"):
                return str(item.get("fix_suggestion"))
    return ""


def _title_has_unsaved_marker(title: str) -> bool:
    title = str(title or "").strip()
    return title.endswith("*]") or title.endswith("*")


def _enumerate_with_powershell() -> list[ProcessInfo]:
    if os.name != "nt":
        return []
    script = (
        "$gp = @{}; "
        "Get-Process | ForEach-Object { $gp[$_.Id] = $_ }; "
        "Get-CimInstance Win32_Process | "
        "Where-Object { $_.Name -match 'SLDWORKS|python|sw_drawing|DialogGuard' -or $_.CommandLine -match 'cad_job_worker|batch_job_worker|sw_dialog_guard|DialogGuard|smoke|solidworks_global_lock' } | "
        "ForEach-Object { "
        "$p=$gp[$_.ProcessId]; "
        "[PSCustomObject]@{Pid=$_.ProcessId;Name=$_.Name;CommandLine=$_.CommandLine;Responding=if($p){$p.Responding}else{$null};MainWindowTitle=if($p){$p.MainWindowTitle}else{''}} "
        "} | ConvertTo-Json -Depth 3"
    )
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            text=True,
            capture_output=True,
            timeout=8,
            encoding="utf-8",
            errors="replace",
        )
        raw = (proc.stdout or "").strip()
        if not raw:
            return []
        data = json.loads(raw)
        if isinstance(data, dict):
            data = [data]
        rows = []
        for item in data if isinstance(data, list) else []:
            command_line = str(item.get("CommandLine") or "")
            if _is_monitor_query_process(command_line):
                continue
            rows.append(
                ProcessInfo(
                    pid=int(item.get("Pid") or 0),
                    name=str(item.get("Name") or ""),
                    command_line=command_line,
                    responding=_bool_or_none(item.get("Responding")),
                    main_window_title=str(item.get("MainWindowTitle") or ""),
                    workspace_hint=_workspace_hint(str(item.get("CommandLine") or "")),
                )
            )
        return _apply_solidworks_window_state(
            [p for p in rows if p.pid > 0 and p.name],
            _solidworks_window_state_by_pid(),
        )
    except Exception:
        return []


def _solidworks_window_state_by_pid() -> dict[int, dict[str, Any]]:
    if os.name != "nt":
        return {}
    command = (
        "Get-Process SLDWORKS -ErrorAction SilentlyContinue | "
        "Select-Object Id,Responding,MainWindowTitle | ConvertTo-Json -Compress"
    )
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            text=True,
            capture_output=True,
            timeout=8,
            encoding="utf-8",
            errors="replace",
        )
        raw = (proc.stdout or "").strip()
        if not raw:
            return {}
        data = json.loads(raw)
        if isinstance(data, dict):
            data = [data]
        state: dict[int, dict[str, Any]] = {}
        for item in data if isinstance(data, list) else []:
            try:
                pid = int(item.get("Id") or 0)
            except (TypeError, ValueError):
                continue
            if pid <= 0:
                continue
            state[pid] = {
                "responding": item.get("Responding"),
                "main_window_title": str(item.get("MainWindowTitle") or ""),
            }
        return state
    except Exception:
        return {}


def _apply_solidworks_window_state(
    processes: list[ProcessInfo],
    state_by_pid: dict[int, dict[str, Any]],
) -> list[ProcessInfo]:
    for process in processes:
        if process.name.lower() not in {"sldworks.exe", "sldworks"}:
            continue
        state = state_by_pid.get(process.pid) or {}
        responding = _bool_or_none(state.get("responding"))
        title = str(state.get("main_window_title") or "")
        if responding is not None:
            process.responding = responding
        if title:
            process.main_window_title = title
    return processes


def _enumerate_with_tasklist() -> list[ProcessInfo]:
    if os.name != "nt":
        return []
    try:
        proc = subprocess.run(
            ["tasklist", "/fo", "csv", "/nh"],
            text=True,
            capture_output=True,
            timeout=5,
            encoding="utf-8",
            errors="replace",
        )
        rows: list[ProcessInfo] = []
        for row in csv.reader(io.StringIO(proc.stdout or "")):
            if len(row) < 2:
                continue
            name = row[0]
            if not any(token in name.lower() for token in ("sldworks", "python", "sw_drawing")):
                continue
            try:
                pid = int(row[1])
            except Exception:
                pid = 0
            if pid:
                rows.append(ProcessInfo(pid=pid, name=name))
        return rows
    except Exception:
        return []


def _workspace_hint(command_line: str) -> str:
    marker = "Desktop\\SW 相关"
    if marker in command_line:
        return marker
    return ""


def _is_monitor_query_process(command_line: str) -> bool:
    text = command_line.lower()
    return "get-ciminstance win32_process" in text and "convertto-json" in text


def _bool_or_none(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    return None
