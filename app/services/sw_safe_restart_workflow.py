from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


def build_safe_restart_workflow(
    *,
    connection_guard: dict[str, Any],
    user_confirmed: bool = False,
) -> dict[str, Any]:
    bucket = connection_guard.get("failure_bucket") or ""
    connected = bool(connection_guard.get("connected"))
    steps = [
        {
            "key": "save_or_close_unsaved_documents",
            "status": "required" if not connected else "not_needed",
            "message": "请先在 SolidWorks 中保存或关闭所有未保存文档。",
        },
        {
            "key": "manual_close_solidworks_if_unresponsive",
            "status": "required" if bucket == "solidworks_com_active_object_timeout" else "optional",
            "message": "若 SolidWorks 无响应，请由用户手动关闭或重启，软件不得自动杀死用户未确认的进程。",
        },
        {
            "key": "restart_solidworks",
            "status": "allowed_after_user_confirmation" if user_confirmed else "waiting_for_user_confirmation",
            "message": "用户确认后可执行安全重启流程，然后重新 Add-in Ping。",
        },
        {
            "key": "rerun_addin_ping",
            "status": "pending",
            "message": "重启后必须重新运行 Add-in Ping 和 OpenDoc6 probe。",
        },
    ]
    return {
        "schema": "sw_drawing_studio.sw_safe_restart_workflow.v4",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "connection_status": connection_guard.get("status") or "",
        "failure_bucket": bucket,
        "auto_kill_allowed": False,
        "user_confirmed": user_confirmed,
        "steps": steps,
    }


def write_safe_restart_workflow(workflow: dict[str, Any], path: Path | str) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(workflow, ensure_ascii=False, indent=2), encoding="utf-8")
    return out
