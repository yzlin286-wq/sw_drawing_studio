from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from app.services.solidworks_com_probe_service import probe_solidworks_connection


def check_sw_connection_guard(
    *,
    timeout_s: float = 3.0,
    allow_dispatch: bool = False,
    allow_dispatch_ex: bool = False,
) -> dict[str, Any]:
    started = time.monotonic()
    probe = probe_solidworks_connection(
        timeout_s=timeout_s,
        allow_dispatch=allow_dispatch,
        allow_dispatch_ex=allow_dispatch_ex,
    )
    connected = probe.get("status") == "connected"
    reason = "" if connected else str(probe.get("reason") or "solidworks_connection_unavailable")
    bucket = "" if connected else _failure_bucket(probe)
    return {
        "schema": "sw_drawing_studio.sw_connection_guard.v4",
        "status": "pass" if connected else "fail",
        "connected": connected,
        "failure_bucket": bucket,
        "reason": reason,
        "elapsed_ms": int((time.monotonic() - started) * 1000),
        "probe": probe,
        "safe_to_start_cad_job": connected,
        "user_action_required": "" if connected else _user_action(bucket),
        "do_not_continue_batch": not connected,
    }


def write_sw_connection_guard(result: dict[str, Any], path: Path | str) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def _failure_bucket(probe: dict[str, Any]) -> str:
    if probe.get("status") == "timeout":
        return "solidworks_com_active_object_timeout"
    reason = str(probe.get("reason") or "").lower()
    if "timeout" in reason:
        return "solidworks_com_active_object_timeout"
    if "not running" in reason or "unavailable" in reason:
        return "solidworks_not_running_or_unavailable"
    return "solidworks_connection_failed"


def _user_action(bucket: str) -> str:
    if bucket == "solidworks_com_active_object_timeout":
        return "请先在 SolidWorks 中保存/关闭未响应文档，必要时手动安全重启 SolidWorks，然后重新执行连接探测。"
    if bucket == "solidworks_not_running_or_unavailable":
        return "请启动 SolidWorks 并确认 Add-in 可用后重新探测。"
    return "请检查 SolidWorks 状态、弹窗和 Add-in 连接后重新探测。"
