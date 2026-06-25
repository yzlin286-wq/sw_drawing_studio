from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from app.services.resource_paths import runtime_path
from app.services.solidworks_conflict_monitor import write_conflict_report
from app.services.solidworks_global_lock import read_lock, require_current_job_lock


def build_restart_preflight(
    *,
    job_id: str = "",
    run_dir: str | Path | None = None,
    user_confirmed: bool = False,
    check_unsaved_documents: bool = False,
) -> dict[str, Any]:
    """Build a conservative restart preflight without restarting SolidWorks."""
    operation = "solidworks_safe_restart.preflight"
    guard = require_current_job_lock(operation)
    lock = read_lock()
    report_path = _restart_report_path(run_dir)
    conflict_report = write_conflict_report(report_path.with_name("conflict_report_before_restart.json"))

    result: dict[str, Any] = {
        "schema": "sw_drawing_studio.solidworks_safe_restart.v1",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "status": "blocked",
        "job_id": job_id or os.environ.get("JOB_ID", ""),
        "lock_held": bool(guard.get("ok")),
        "lock": lock,
        "user_confirmed": bool(user_confirmed),
        "allow_restart_sw": bool(lock.get("allow_restart_sw")) if isinstance(lock, dict) else False,
        "unsaved_documents": [],
        "unsaved_check": {"status": "not_requested"},
        "conflict_report": conflict_report,
        "auto_kill_allowed": False,
        "fix_suggestion": "",
    }

    if not guard.get("ok"):
        result.update({
            "status": "blocked_by_solidworks_lock",
            "reason": guard.get("reason", "blocked_by_solidworks_lock"),
            "owner": guard.get("owner", {}),
            "fix_suggestion": guard.get("fix_suggestion", "等待当前 CAD job 完成，或手动确认后释放 stale lock"),
        })
        _write_restart_report(report_path, result)
        return result

    if not isinstance(lock, dict) or not lock.get("allow_restart_sw"):
        result.update({
            "status": "blocked_restart_not_allowed_by_lock",
            "reason": "current lock does not allow restart",
            "fix_suggestion": "只有当前 lock owner 显式 allow_restart_sw=true 且用户确认后，才允许重启 SolidWorks",
        })
        _write_restart_report(report_path, result)
        return result

    if not user_confirmed:
        result.update({
            "status": "waiting_for_user_confirmation",
            "reason": "user confirmation required",
            "fix_suggestion": "请用户确认已保存未保存文档，并允许当前 job 重启 SolidWorks",
        })
        _write_restart_report(report_path, result)
        return result

    if check_unsaved_documents:
        unsaved = _collect_unsaved_documents()
        result["unsaved_check"] = unsaved
        result["unsaved_documents"] = unsaved.get("documents", [])
        if unsaved.get("status") != "checked":
            result.update({
                "status": "blocked_unsaved_documents_unknown",
                "reason": unsaved.get("reason", "unsaved document status is unknown"),
                "fix_suggestion": "无法确认未保存文档状态；请用户手动保存/关闭文档后再继续",
            })
            _write_restart_report(report_path, result)
            return result
        if unsaved.get("documents"):
            result.update({
                "status": "blocked_unsaved_documents",
                "reason": "unsaved SolidWorks documents detected",
                "fix_suggestion": "请先保存或关闭未保存文档，再重试安全重启",
            })
            _write_restart_report(report_path, result)
            return result

    result.update({
        "status": "ready_for_restart",
        "reason": "",
        "auto_kill_allowed": True,
        "fix_suggestion": "可由当前 lock owner 执行 restart_solidworks_safely(execute=True)",
    })
    _write_restart_report(report_path, result)
    return result


def restart_solidworks_safely(
    *,
    job_id: str = "",
    run_dir: str | Path | None = None,
    user_confirmed: bool = False,
    execute: bool = False,
) -> dict[str, Any]:
    """Restart only the locked SolidWorks PID, and only after preflight passes."""
    preflight = build_restart_preflight(
        job_id=job_id,
        run_dir=run_dir,
        user_confirmed=user_confirmed,
        check_unsaved_documents=True,
    )
    report_path = _restart_report_path(run_dir)
    if preflight.get("status") != "ready_for_restart":
        return preflight
    if not execute:
        preflight.update({
            "status": "dry_run_ready_for_restart",
            "executed": False,
            "fix_suggestion": "preflight 通过；再次调用 execute=True 才会重启当前 lock owner 的 SolidWorks PID",
        })
        _write_restart_report(report_path, preflight)
        return preflight

    lock = preflight.get("lock") if isinstance(preflight.get("lock"), dict) else {}
    sw_pid = _int_or_zero(lock.get("sw_pid"))
    if not sw_pid:
        preflight.update({
            "status": "blocked_missing_sw_pid",
            "executed": False,
            "reason": "lock does not record sw_pid",
            "fix_suggestion": "无法确认应重启的 SolidWorks PID；请用户手动重启",
        })
        _write_restart_report(report_path, preflight)
        return preflight

    restart_result = _terminate_pid_tree(sw_pid)
    preflight.update({
        "status": "restart_executed" if restart_result.get("success") else "restart_failed",
        "executed": bool(restart_result.get("success")),
        "restart_result": restart_result,
        "fix_suggestion": "重启后必须重新运行 Add-in Ping 和 OpenDoc6 probe",
    })
    _write_restart_report(report_path, preflight)
    return preflight


def _collect_unsaved_documents() -> dict[str, Any]:
    guard = require_current_job_lock("solidworks_safe_restart.collect_unsaved_documents")
    if not guard.get("ok"):
        return {"status": "blocked_by_solidworks_lock", "reason": guard.get("reason", ""), "documents": []}
    try:
        import win32com.client as wc

        sw = wc.GetActiveObject("SldWorks.Application")
        docs = getattr(sw, "GetDocuments", None)
        docs = docs() if callable(docs) else docs
        rows: list[dict[str, Any]] = []
        for doc in docs or []:
            title = _call_or_empty(doc, "GetTitle")
            path = _call_or_empty(doc, "GetPathName")
            saved = _call_or_none(doc, "GetSaveFlag")
            is_dirty = bool(saved)
            if is_dirty:
                rows.append({"title": title, "path": path, "save_flag": saved})
        return {"status": "checked", "documents": rows, "reason": ""}
    except Exception as exc:
        return {"status": "unknown", "documents": [], "reason": str(exc)}


def _terminate_pid_tree(pid: int) -> dict[str, Any]:
    if pid <= 0:
        return {"success": False, "reason": "invalid_pid", "pid": pid}
    if os.name != "nt":
        return {"success": False, "reason": "windows_only", "pid": pid}
    try:
        proc = subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
        return {
            "success": proc.returncode == 0,
            "pid": pid,
            "returncode": proc.returncode,
            "stdout": (proc.stdout or "")[-2000:],
            "stderr": (proc.stderr or "")[-2000:],
        }
    except Exception as exc:
        return {"success": False, "pid": pid, "reason": str(exc)}


def _restart_report_path(run_dir: str | Path | None) -> Path:
    if run_dir:
        return Path(run_dir) / "diagnostics" / "restart_report.json"
    return runtime_path("drw_output") / "diagnostics" / "restart_report.json"


def _write_restart_report(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    payload["restart_report"] = str(path)
    return path


def _call_or_none(obj: Any, name: str) -> Any:
    try:
        value = getattr(obj, name)
        return value() if callable(value) else value
    except Exception:
        return None


def _call_or_empty(obj: Any, name: str) -> str:
    value = _call_or_none(obj, name)
    return str(value or "")


def _int_or_zero(value: Any) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0
