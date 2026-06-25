from __future__ import annotations

import json
import importlib.util
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from app.services.resource_paths import child_process_env, worker_command
from app.services.solidworks_com_probe_service import probe_solidworks_connection
from app.services.solidworks_conflict_monitor import write_conflict_report


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
LOCK_GROUP = "SolidWorks 互斥状态"


@dataclass
class HealthRow:
    group: str
    key: str
    status: str
    message: str
    fix_suggestion: str = ""
    details: dict[str, Any] | None = None


BASE_GROUPS = {
    "solidworks": "SolidWorks",
    "sw_revision": "SolidWorks",
    "sw_revision_supported": "SolidWorks",
    "template": "SolidWorks",
    "macro_bas": "SolidWorks",
    "macro_swp": "SolidWorks",
    "v6_generator": "SolidWorks",
    "v5_fallback": "SolidWorks",
    "opencv": "Vision",
    "ultralytics": "Vision",
    "ocr": "Vision",
    "vision_model": "Vision",
    "output_dir": "Data",
    "chinese_path_support": "Data",
    "db_readable": "Data",
    "llm": "Data",
}


SUPPORTED_SW_REVISIONS = ("33.", "32.", "31.")  # SW2025 / SW2024 / SW2023


def _health_probe_timeout_s() -> float:
    try:
        return max(0.5, float(os.environ.get("SWDS_SW_HEALTH_PROBE_TIMEOUT_S", "3")))
    except Exception:
        return 3.0


def collect_system_health(
    *,
    ensure_solidworks: bool = False,
    real_opendoc6_probe: bool = False,
    probe_doc_path: str | Path | None = None,
) -> tuple[list[HealthRow], dict[str, Any]]:
    base = _safe_base_health(ensure_solidworks=ensure_solidworks)
    rows: list[HealthRow] = []

    for item in base.get("items", []):
        key = str(item.get("key", ""))
        rows.append(
            HealthRow(
                group=BASE_GROUPS.get(key, "Data"),
                key=key,
                status=_normalize_status(item.get("status")),
                message=str(item.get("msg") or ""),
                fix_suggestion=str(item.get("fix") or ""),
                details=dict(item),
            )
        )

    rows.extend(
        _solidworks_extra_rows(
            rows,
            allow_dispatch=ensure_solidworks,
            real_opendoc6_probe=real_opendoc6_probe,
            probe_doc_path=probe_doc_path,
        )
    )
    rows.extend(_solidworks_lock_rows())
    rows.extend(_vision_extra_rows())
    rows.extend(_license_rows())
    rows.extend(_ui_worker_rows())

    result = {
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "pass": sum(1 for r in rows if r.status == "pass"),
        "warning": sum(1 for r in rows if r.status == "warning"),
        "fail": sum(1 for r in rows if r.status == "fail"),
        "total": len(rows),
    }
    return rows, result


def _safe_base_health(*, ensure_solidworks: bool = False) -> dict[str, Any]:
    """Collect lightweight health rows without importing fragile native engines.

    The old aggregate health check imported OCR/YOLO/Paddle stacks directly.
    In a frozen worker those imports can terminate the process before Python can
    emit a structured ``job_failed`` event. System Health should report
    availability and next actions, while real model loading belongs to the
    visual-audit worker gates.
    """
    items: list[dict[str, Any]] = []

    solidworks = _solidworks_base_item(allow_dispatch=ensure_solidworks)
    items.append(solidworks)
    items.extend(_solidworks_revision_items(solidworks))
    items.append(_template_item())
    items.append(_file_item("macro_bas", REPO_ROOT / "templates" / "macros" / "auto_section.bas", "auto_section.bas 已就绪", "恢复 templates/macros/auto_section.bas"))
    items.append(_file_item("macro_swp", REPO_ROOT / "templates" / "macros" / "auto_section.swp", "auto_section.swp 已就绪", "在 SolidWorks VBA 中打开 BAS 宏并另存为 SWP", warning_when_missing=True))
    items.append(_output_dir_item())
    items.append(_chinese_path_item())
    items.append(_file_item("v6_generator", REPO_ROOT / ".trae" / "specs" / "build-v6-and-validate-exe-ui" / "drw_generate_v6.py", "v6 生成脚本已就绪", "恢复 .trae/specs/build-v6-and-validate-exe-ui/drw_generate_v6.py"))
    items.append(_file_item("v5_fallback", REPO_ROOT / ".trae" / "specs" / "enforce-drawing-quality" / "drw_generate_v5.py", "v5 兼容脚本已就绪", "恢复 .trae/specs/enforce-drawing-quality/drw_generate_v5.py", warning_when_missing=True))
    items.append(_db_item())
    items.append(_llm_item())
    items.append(_module_presence_item("opencv", "cv2", "pip install opencv-python"))
    items.append(_module_presence_item("ultralytics", "ultralytics", "pip install ultralytics"))
    items.append(_ocr_presence_item())
    items.append(_vision_model_item())

    counts = {
        "pass": sum(1 for item in items if item.get("status") == "pass"),
        "warning": sum(1 for item in items if item.get("status") == "warning"),
        "fail": sum(1 for item in items if item.get("status") == "fail"),
    }
    return {"items": items, **counts, "all_ok": counts["fail"] == 0}


def _item(key: str, status: str, msg: str, fix: str = "", **extra: Any) -> dict[str, Any]:
    item: dict[str, Any] = {"key": key, "status": status, "msg": msg, "fix": fix}
    item.update(extra)
    return item


def _probe_details(probe: dict[str, Any]) -> dict[str, Any]:
    details = dict(probe)
    if "status" in details:
        details["probe_status"] = details.pop("status")
    return details


def _connect_solidworks(*, allow_dispatch: bool = False) -> tuple[Any | None, str, str]:
    try:
        import win32com.client
    except Exception as exc:
        return None, "pywin32_unavailable", str(exc)

    try:
        sw = win32com.client.GetActiveObject("SldWorks.Application")
        return sw, "get_active_object", ""
    except Exception as active_exc:
        if not allow_dispatch:
            return None, "get_active_object_failed", str(active_exc)
        try:
            sw = win32com.client.Dispatch("SldWorks.Application")
            return sw, "dispatch", ""
        except Exception as dispatch_exc:
            return None, "dispatch_failed", f"GetActiveObject failed: {active_exc}; Dispatch failed: {dispatch_exc}"


def _solidworks_base_item(*, allow_dispatch: bool = False) -> dict[str, Any]:
    probe = probe_solidworks_connection(
        timeout_s=_health_probe_timeout_s(),
        allow_dispatch=allow_dispatch,
    )
    method = str(probe.get("connection_method") or probe.get("method") or "")
    error = str(probe.get("reason") or "")
    probe_details = _probe_details(probe)
    if probe.get("status") != "connected":
        if "pywin32_unavailable" in error:
            return _item("solidworks", "warning", f"pywin32 不可用: {error}", "真实 CAD 验证前请安装 pywin32", **probe_details)
        if probe.get("status") == "timeout":
            return _item(
                "solidworks",
                "warning",
                f"SolidWorks COM 会话不可响应：{error}",
                "请先保存 SolidWorks 中未保存文档，关闭阻塞对话框；如仍不响应，请重启 SolidWorks 后重跑 System Health",
                failure_bucket="solidworks_com_active_object_timeout",
                **probe_details,
            )
        return _item(
            "solidworks",
            "warning",
            "SolidWorks 未运行或不可连接；历史查看仍可用",
            "真实 CAD 验证前请启动 SolidWorks",
            error=error,
            **probe_details,
        )
    visible = probe.get("visible")
    revision = str(probe.get("sw_revision") or "")
    sw_pid = probe.get("sw_pid")
    for duplicate_key in ("sw_pid", "sw_revision", "visible"):
        probe_details.pop(duplicate_key, None)
    parts = [f"method={method}", f"Visible={visible}"]
    if sw_pid:
        parts.append(f"sw_pid={sw_pid}")
    if revision:
        parts.append(f"revision={revision}")
    return _item(
        "solidworks",
        "pass",
        "SolidWorks 活动对象可用；" + "；".join(parts),
        "",
        sw_pid=sw_pid,
        sw_revision=revision,
        visible=str(visible),
        **probe_details,
    )


def _read_sw_revision(sw: Any) -> str:
    try:
        value = getattr(sw, "RevisionNumber")
        if callable(value):
            value = value()
        return str(value or "")
    except Exception:
        return ""


def _read_sw_pid(sw: Any) -> int | None:
    for method_name in ["GetProcessID", "GetProcessId"]:
        try:
            method = getattr(sw, method_name)
            value = method() if callable(method) else method
            pid = int(value)
            if pid > 0:
                return pid
        except Exception:
            pass
    return None


def _solidworks_revision_items(solidworks_item: dict[str, Any]) -> list[dict[str, Any]]:
    if solidworks_item.get("status") != "pass":
        return [
            _item("sw_revision", "warning", "无法读取：SolidWorks 尚未连接", "真实 CAD 验证前请先启动 SolidWorks"),
            _item("sw_revision_supported", "warning", "无法判断：SolidWorks 尚未连接", "真实 CAD 验证前请先启动 SolidWorks"),
        ]
    revision = str(solidworks_item.get("sw_revision") or "")
    if not revision:
        return [
            _item("sw_revision", "warning", "SolidWorks 已连接，但 RevisionNumber 读取为空", "检查 SolidWorks COM RevisionNumber API"),
            _item("sw_revision_supported", "warning", "无法判断支持状态：RevisionNumber 为空", "确认 SolidWorks 版本为 2023/2024/2025"),
        ]
    supported = any(revision.startswith(prefix) for prefix in SUPPORTED_SW_REVISIONS)
    return [
        _item("sw_revision", "pass", f"RevisionNumber = {revision}", "", sw_revision=revision),
        _item(
            "sw_revision_supported",
            "pass" if supported else "warning",
            f"版本 {revision} 在支持列表内" if supported else f"版本 {revision} 不在已知支持列表 {SUPPORTED_SW_REVISIONS}",
            "" if supported else "建议使用 SolidWorks 2023/2024/2025 后重跑 Reality Gate",
            sw_revision=revision,
            supported_revisions=list(SUPPORTED_SW_REVISIONS),
        ),
    ]


def _template_item() -> dict[str, str]:
    candidates = [
        REPO_ROOT / "templates" / "gb_a4_landscape.DRWDOT",
        REPO_ROOT / "templates" / "gb_a4_landscape.drwdot",
    ]
    for candidate in candidates:
        if candidate.exists() and candidate.stat().st_size > 10 * 1024:
            return _item("template", "pass", f"{candidate.name} 已就绪", "")
    return _item("template", "fail", "GB A4 横向模板缺失或文件过小", "运行 templates/build_drwdot.py")


def _file_item(key: str, path: Path, pass_msg: str, fix: str, warning_when_missing: bool = False) -> dict[str, str]:
    if path.exists():
        return _item(key, "pass", pass_msg, "")
    return _item(key, "warning" if warning_when_missing else "fail", f"{path.name} 缺失", fix)


def _output_dir_item() -> dict[str, str]:
    out = REPO_ROOT / "drw_output"
    try:
        out.mkdir(parents=True, exist_ok=True)
        probe = out / ".health_probe.tmp"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return _item("output_dir", "pass", f"{out} 可写", "")
    except Exception as exc:
        return _item("output_dir", "fail", f"输出目录不可写: {exc}", "检查目录权限")


def _chinese_path_item() -> dict[str, str]:
    out = REPO_ROOT / "drw_output"
    try:
        out.mkdir(parents=True, exist_ok=True)
        probe = out / ".unicode_path_probe.tmp"
        probe.write_text("unicode ok", encoding="utf-8")
        content = probe.read_text(encoding="utf-8")
        probe.unlink(missing_ok=True)
        if "unicode ok" in content:
            return _item("chinese_path_support", "pass", "Unicode 路径读写探测通过", "")
        return _item("chinese_path_support", "warning", "Unicode 路径探测内容不一致", "检查 Windows 区域设置和 UTF-8 设置")
    except Exception as exc:
        return _item("chinese_path_support", "warning", f"Unicode 路径探测失败: {exc}", "检查 Windows 区域设置和 UTF-8 设置")


def _db_item() -> dict[str, str]:
    needs = [
        REPO_ROOT / "libs" / "standard_parts.db",
        REPO_ROOT / "libs" / "process" / "process.db",
        REPO_ROOT / "libs" / "pricing" / "rules.yaml",
    ]
    missing = [p.name for p in needs if not p.exists()]
    if missing:
        return _item("db_readable", "fail", f"数据文件缺失: {', '.join(missing)}", "恢复 libs 数据文件")
    try:
        import sqlite3

        for db in needs[:2]:
            con = sqlite3.connect(str(db))
            con.execute("SELECT 1").fetchone()
            con.close()
        return _item("db_readable", "pass", "标准件、工艺和报价数据可读取", "")
    except Exception as exc:
        return _item("db_readable", "fail", f"SQLite 读取失败: {exc}", "重建数据文件")


def _llm_item() -> dict[str, str]:
    try:
        from app.services.llm_client import build_default_client

        client = build_default_client()
        model = getattr(client, "model", "")
        if model:
            return _item("llm", "pass", f"LLM 模型已配置: {model}", "")
        return _item("llm", "warning", "LLM 模型未配置", "执行 AI 操作前请配置供应商和模型")
    except Exception as exc:
        return _item("llm", "warning", f"LLM 配置探测失败: {exc}", "检查 config/llm.yaml")


def _module_presence_item(key: str, module_name: str, fix: str) -> dict[str, str]:
    try:
        spec = importlib.util.find_spec(module_name)
    except Exception as exc:
        return _item(key, "warning", f"{module_name} 存在性探测失败: {exc}", fix)
    if spec is None:
        return _item(key, "warning", f"{module_name} 未安装", fix)
    return _item(key, "pass", f"{module_name} 已安装；导入延迟到 worker 门槛", "")


def _ocr_presence_item() -> dict[str, str]:
    engines = []
    for name in ["paddleocr", "easyocr", "pytesseract"]:
        try:
            if importlib.util.find_spec(name) is not None:
                engines.append(name)
        except Exception:
            pass
    try:
        if importlib.util.find_spec("fitz") is not None:
            engines.append("fitz")
    except Exception:
        pass
    if engines:
        return _item("ocr", "pass", f"OCR 相关模块存在: {', '.join(engines)}；导入延迟执行", "")
    return _item("ocr", "warning", "未检测到 OCR 相关模块", "安装 paddleocr、easyocr、pytesseract 或 PyMuPDF")


def _vision_model_item() -> dict[str, str]:
    candidates = [
        REPO_ROOT / "models" / "yolo_drawing_obb.pt",
        REPO_ROOT / "models" / "yolov8n-obb.pt",
        REPO_ROOT / "models" / "yolov8n.pt",
        REPO_ROOT / "app" / "models" / "yolo_drawing_obb.pt",
    ]
    found = [p for p in candidates if p.exists()]
    if found:
        return _item("vision_model", "pass", f"已找到视觉模型: {found[0]}", "")
    return _item("vision_model", "warning", "未找到专用 YOLO/OBB 权重", "将训练后的权重放到 models/yolo_drawing_obb.pt")


def health_rows_to_dicts(rows: list[HealthRow]) -> list[dict[str, Any]]:
    return [asdict(row) for row in rows]


def health_rows_from_dicts(items: list[dict[str, Any]]) -> list[HealthRow]:
    rows: list[HealthRow] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        rows.append(
            HealthRow(
                group=str(item.get("group") or ""),
                key=str(item.get("key") or ""),
                status=_normalize_status(item.get("status")),
                message=str(item.get("message") or ""),
                fix_suggestion=str(item.get("fix_suggestion") or ""),
                details=item.get("details") if isinstance(item.get("details"), dict) else None,
            )
        )
    return rows


def _solidworks_extra_rows(
    existing_rows: list[HealthRow],
    *,
    allow_dispatch: bool = False,
    real_opendoc6_probe: bool = False,
    probe_doc_path: str | Path | None = None,
) -> list[HealthRow]:
    rows: list[HealthRow] = []
    solidworks = find_row(existing_rows, "solidworks")
    sw_running = bool(solidworks and solidworks.status == "pass")
    rows.append(
        HealthRow(
            "SolidWorks",
            "sw_running",
            "pass" if sw_running else "warning",
            "SolidWorks 已连接"
            if sw_running
            else "SolidWorks 未运行；制图功能不可用，历史查看仍可用",
            ""
            if sw_running
            else "真实 CAD 验证前请启动 SolidWorks；历史、日志和视觉审计仍可使用",
        )
    )

    if sw_running:
        addin = _probe_addin_ping()
    else:
        addin = HealthRow(
            "SolidWorks",
            "addin_ping",
            "warning",
            "已跳过 Add-in Ping：SolidWorks COM 会话不可用",
            "先恢复 SolidWorks COM 连接，再验证 Add-in Ping",
            solidworks.details if solidworks and isinstance(solidworks.details, dict) else None,
        )
    rows.append(addin)

    if sw_running and real_opendoc6_probe:
        rows.append(_probe_opendoc6(probe_doc_path, allow_dispatch=allow_dispatch))
    elif sw_running and addin.status == "pass":
        rows.append(
            HealthRow(
                "SolidWorks",
                "opendoc6_test",
                "warning",
                "已跳过 OpenDoc6 真实打开探测，避免改变当前 SolidWorks 会话",
                "运行 024/040 或 core_12 验证门槛以执行真实 OpenDoc6 探测",
            )
        )
    else:
        rows.append(
            HealthRow(
                "SolidWorks",
                "opendoc6_test",
                "warning",
                "SolidWorks 或 Add-in 不可用；已跳过 OpenDoc6 测试",
                "启动 SolidWorks 并确认 Add-in Ping 后再运行真实打开验证",
            )
        )

    rows.append(_probe_dialog_guard())
    return rows


def _solidworks_lock_rows() -> list[HealthRow]:
    try:
        report = write_conflict_report()
    except Exception as exc:
        return [
            HealthRow(
                LOCK_GROUP,
                "solidworks_conflict_monitor",
                "warning",
                f"SolidWorks 互斥状态读取失败: {exc}",
                "检查 app/services/solidworks_conflict_monitor.py 和 diagnostics 输出目录权限",
            )
        ]

    level = str(report.get("level") or "WARNING").upper()
    status = "pass" if level == "OK" else "fail" if level == "FAIL" else "warning"
    lock = report.get("lock") if isinstance(report.get("lock"), dict) else {}
    owner = report.get("lock_owner") if isinstance(report.get("lock_owner"), dict) else {}
    sw_processes = report.get("solidworks_processes") if isinstance(report.get("solidworks_processes"), list) else []
    first_sw = sw_processes[0] if sw_processes and isinstance(sw_processes[0], dict) else {}
    fix = str(report.get("fix_suggestion") or "")
    if status == "warning" and not fix:
        fix = "真实 CAD / Add-in / OpenDoc6 操作前必须通过 worker 获取全局锁"

    lock_state = "active" if lock else "none"
    if lock and owner.get("stale_lock"):
        lock_state = "stale"

    rows = [
        HealthRow(
            LOCK_GROUP,
            "solidworks_mutex_status",
            status,
            f"互斥状态={level}, lock={lock_state}",
            fix,
            report,
        ),
        HealthRow(
            LOCK_GROUP,
            "solidworks_lock_owner",
            "warning" if lock and owner.get("owner_job_id") else "pass" if not lock else status,
            (
                f"owner_project={owner.get('owner_project','')} | "
                f"owner_job_id={owner.get('owner_job_id','')} | "
                f"operation={owner.get('operation','')}"
            )
            if lock
            else "当前无 SolidWorks 全局锁",
            "等待当前任务完成" if lock and not owner.get("stale_lock") else "检测到锁已过期，可释放" if owner.get("stale_lock") else "",
            owner,
        ),
        HealthRow(
            LOCK_GROUP,
            "solidworks_heartbeat_age",
            "warning" if owner.get("stale_lock") else "pass",
            f"heartbeat_age={owner.get('heartbeat_age_s')}s",
            "检测到锁已过期，可释放" if owner.get("stale_lock") else "",
            owner,
        ),
        HealthRow(
            LOCK_GROUP,
            "solidworks_process_state",
            "fail" if first_sw.get("responding") is False else "pass" if first_sw else "warning",
            (
                f"SW PID={first_sw.get('pid')} Responding={first_sw.get('responding')} "
                f"Title={first_sw.get('main_window_title','')}"
            )
            if first_sw
            else "未枚举到 SLDWORKS.exe；历史查看和离线视觉审计仍可用",
            "SolidWorks 无响应，请先保存未保存文档，再重启" if first_sw.get("responding") is False else "",
            first_sw,
        ),
        HealthRow(
            LOCK_GROUP,
            "solidworks_waiting_jobs",
            "warning" if int(report.get("counts", {}).get("waiting_jobs", 0)) else "pass",
            f"waiting_jobs={report.get('counts', {}).get('waiting_jobs', 0)}",
            "SolidWorks 正被另一个任务使用；等待当前任务完成" if int(report.get("counts", {}).get("waiting_jobs", 0)) else "",
            report.get("counts", {}),
        ),
        HealthRow(
            LOCK_GROUP,
            "solidworks_com_without_lock_forbidden",
            "pass",
            "禁止在未取得锁时调用 COM",
            "通过 JobRuntimeFacade / CAD worker / batch worker 进入真实 SolidWorks 操作",
            {"lock_path": report.get("lock_path")},
        ),
    ]
    return rows


def _probe_opendoc6(probe_doc_path: str | Path | None, *, allow_dispatch: bool = False) -> HealthRow:
    if not probe_doc_path:
        return HealthRow(
            "SolidWorks",
            "opendoc6_test",
            "fail",
            "已请求真实 OpenDoc6 探测，但未提供探测文件",
            "传入 copied SLDPRT/SLDASM/SLDDRW 路径后重跑 Reality Gate",
        )

    path = Path(probe_doc_path).resolve()
    if not path.exists():
        return HealthRow(
            "SolidWorks",
            "opendoc6_test",
            "fail",
            f"OpenDoc6 探测文件不存在: {path}",
            "复制真实 CAD 样本到 run_dir/input_work 后重跑 Reality Gate",
            {"probe_doc_path": str(path)},
        )

    doc_type = {".sldprt": 1, ".sldasm": 2, ".slddrw": 3}.get(path.suffix.lower())
    if not doc_type:
        return HealthRow(
            "SolidWorks",
            "opendoc6_test",
            "fail",
            f"OpenDoc6 探测文件类型不支持: {path.suffix}",
            "使用 SLDPRT、SLDASM 或 SLDDRW 作为探测文件",
            {"probe_doc_path": str(path)},
        )

    lock_result = _acquire_probe_lock("system_health.opendoc6_probe", str(path))
    if not lock_result.get("acquired"):
        return HealthRow(
            "SolidWorks",
            "opendoc6_test",
            "warning",
            "OpenDoc6 探测已被 SolidWorks 全局锁阻止",
            str(lock_result.get("fix_suggestion") or "等待当前 CAD job 完成后再运行真实打开验证"),
            lock_result,
        )

    try:
        import pythoncom
        from win32com.client import VARIANT

        sw, method, error = _connect_solidworks(allow_dispatch=allow_dispatch)
        if sw is None:
            return HealthRow(
                "SolidWorks",
                "opendoc6_test",
                "fail",
                f"OpenDoc6 前无法连接 SolidWorks: {error}",
                "启动 SolidWorks 或允许 release gate 使用 Dispatch 后重跑",
                {"probe_doc_path": str(path), "connection_method": method, "error": error},
            )
        err = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        warn = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        started = time.monotonic()
        doc = sw.OpenDoc6(str(path), doc_type, 257, "", err, warn)
        duration_ms = int((time.monotonic() - started) * 1000)
        err_value = int(getattr(err, "value", 0) or 0)
        warn_value = int(getattr(warn, "value", 0) or 0)
        if doc is None:
            return HealthRow(
                "SolidWorks",
                "opendoc6_test",
                "fail",
                f"OpenDoc6 返回 None，errors={err_value} warnings={warn_value}",
                "检查样本文件、SolidWorks 弹窗、引用缺失和 OpenDoc6 silent 选项",
                {
                    "probe_doc_path": str(path),
                    "doc_type": doc_type,
                    "errors": err_value,
                    "warnings": warn_value,
                    "duration_ms": duration_ms,
                    "connection_method": method,
                },
            )

        title = ""
        try:
            title = str(doc.GetTitle())
        except Exception:
            title = path.name
        try:
            sw.CloseDoc(title)
        except Exception:
            pass
        return HealthRow(
            "SolidWorks",
            "opendoc6_test",
            "pass",
            f"OpenDoc6 真实打开探测通过: {path.name}",
            "",
            {
                "probe_doc_path": str(path),
                "doc_type": doc_type,
                "errors": err_value,
                "warnings": warn_value,
                "duration_ms": duration_ms,
                "title": title,
                "connection_method": method,
            },
        )
    except Exception as exc:
        return HealthRow(
            "SolidWorks",
            "opendoc6_test",
            "fail",
            f"OpenDoc6 探测异常: {exc}",
            "确认 SolidWorks 无阻塞弹窗，使用 copied input_work 文件后重跑 Reality Gate",
            {"probe_doc_path": str(path), "exception": type(exc).__name__},
        )
    finally:
        _release_probe_lock(str(lock_result.get("job_id") or os.environ.get("JOB_ID") or ""))


def _probe_addin_ping() -> HealthRow:
    lock_result = _acquire_probe_lock("system_health.addin_ping", "")
    if not lock_result.get("acquired"):
        return HealthRow(
            "SolidWorks",
            "addin_ping",
            "warning",
            "Add-in Ping 已被 SolidWorks 全局锁阻止",
            str(lock_result.get("fix_suggestion") or "等待当前 CAD job 完成后再验证 Add-in Ping"),
            lock_result,
        )
    try:
        from app.services.sw_addin_client import ping

        result = ping()
        if result.get("available"):
            return HealthRow(
                "SolidWorks",
                "addin_ping",
                "pass",
                f"Add-in Ping succeeded ({result.get('method', '')})",
                "",
                result,
            )
        sw_running = bool(result.get("sw_running"))
        return HealthRow(
            "SolidWorks",
            "addin_ping",
            "warning" if not sw_running else "fail",
            str(result.get("reason") or "Add-in Ping unavailable"),
            "Register and load SwDrawingStudioAddin; skip drawing generation when SolidWorks is not running",
            result,
        )
    except Exception as exc:
        return HealthRow(
            "SolidWorks",
            "addin_ping",
            "warning",
            f"Add-in Ping probe failed: {exc}",
            "Check pywin32, COM registration, and tools/SwDrawingStudioAddin/bin",
        )
    finally:
        _release_probe_lock(str(lock_result.get("job_id") or os.environ.get("JOB_ID") or ""))


def _acquire_probe_lock(operation: str, part_path: str) -> dict[str, Any]:
    try:
        from app.services.solidworks_global_lock import acquire_lock

        job_id = os.environ.get("JOB_ID") or f"system_health_{os.getpid()}"
        result = acquire_lock(
            owner_project=os.environ.get("SW_DRAWING_STUDIO_OWNER_PROJECT", "sw_drawing_studio"),
            owner_workspace=str(REPO_ROOT),
            job_id=job_id,
            operation=operation,
            part_path=part_path,
            timeout_sec=float(os.environ.get("SW_HEALTH_LOCK_TIMEOUT_S", "0.5") or "0.5"),
            run_id=os.environ.get("RUN_ID", ""),
            ttl_sec=30,
        )
        result["job_id"] = job_id
        return result
    except Exception as exc:
        return {"acquired": False, "status": "lock_error", "reason": str(exc), "fix_suggestion": "检查 SolidWorks 全局锁文件权限"}


def _release_probe_lock(job_id: str) -> None:
    if not job_id:
        return
    try:
        from app.services.solidworks_global_lock import release_lock

        release_lock(job_id, "system_health_probe_finished")
    except Exception:
        pass


def _probe_dialog_guard() -> HealthRow:
    try:
        from app.services.sw_dialog_guard import DialogGuardV2

        return HealthRow(
            "SolidWorks",
            "dialog_guard",
            "pass",
            f"DialogGuard import ok: {DialogGuardV2.__name__}",
            "",
        )
    except Exception as exc:
        return HealthRow(
            "SolidWorks",
            "dialog_guard",
            "fail",
            f"DialogGuard unavailable: {exc}",
            "Check app/services/sw_dialog_guard.py and pywin32/win32gui dependencies",
        )


def _vision_extra_rows() -> list[HealthRow]:
    rows: list[HealthRow] = []
    for module_name, key, package_hint in [
        ("fitz", "fitz", "pip install PyMuPDF"),
        ("cv2", "cv2", "pip install opencv-python"),
        ("ultralytics", "ultralytics_import", "pip install ultralytics"),
        ("paddleocr", "paddleocr", "pip install paddleocr"),
    ]:
        try:
            spec = importlib.util.find_spec(module_name)
            if spec is None:
                rows.append(HealthRow("Vision", key, "warning", f"{module_name} is not installed", package_hint))
            else:
                rows.append(
                    HealthRow(
                        "Vision",
                        key,
                        "pass",
                        f"{module_name} is installed; import deferred to visual worker gate",
                        "",
                    )
                )
        except Exception as exc:
            rows.append(HealthRow("Vision", key, "warning", f"{module_name} presence probe failed: {exc}", package_hint))

    weights = [
        REPO_ROOT / "models" / "yolo_drawing_obb.pt",
        REPO_ROOT / "models" / "yolov8n-obb.pt",
        REPO_ROOT / "models" / "yolov8n.pt",
        REPO_ROOT / "app" / "models" / "yolo_drawing_obb.pt",
    ]
    found = [p for p in weights if p.exists()]
    if found:
        rows.append(HealthRow("Vision", "yolo_weights", "pass", f"YOLO 权重: {found[0]}", ""))
    else:
        rows.append(
            HealthRow(
                "Vision",
                "yolo_weights",
                "warning",
                "未找到专用 YOLO/OBB 权重；视觉检查将依赖规则或通用模型",
                "将训练后的权重放到 models/yolo_drawing_obb.pt",
            )
        )
    return rows


def _license_rows() -> list[HealthRow]:
    try:
        from app.services.docmgr_service import probe_docmgr

        result = probe_docmgr()
        if result.get("available"):
            return [HealthRow("License", "document_manager_key", "pass", "Document Manager 可用", "", result)]
        license_present = bool(result.get("license_key_present"))
        status = "warning" if not license_present else "fail"
        return [
            HealthRow(
                "License",
                "document_manager_key",
                status,
                str(result.get("reason") or "Document Manager 不可用"),
                "配置 SW_DM_LICENSE_KEY 或 config/docmgr.yaml；当前流程可降级但必须解释原因",
                result,
            )
        ]
    except Exception as exc:
        return [
            HealthRow(
                "License",
                "document_manager_key",
                "warning",
                f"Document Manager 探测失败: {exc}",
                "检查 app/services/docmgr_service.py 和 SolidWorks Document Manager 安装",
            )
        ]


def _ui_worker_rows() -> list[HealthRow]:
    rows: list[HealthRow] = []
    worker_dir = REPO_ROOT / "app" / "workers"
    for name in [
        "cad_job_worker.py",
        "batch_job_worker.py",
        "drawing_review_worker.py",
        "qc_action_worker.py",
        "llm_action_worker.py",
        "solidworks_com_probe_worker.py",
        "vision_audit_worker.py",
        "mock_long_job_worker.py",
        "health_check_worker.py",
    ]:
        path = worker_dir / name
        rows.append(
            HealthRow(
                "UI-Worker",
                name,
                "pass" if path.exists() else "fail",
                f"{name} 存在" if path.exists() else f"{name} 缺失",
                "" if path.exists() else f"恢复 app/workers/{name}",
            )
        )

    mock_path = worker_dir / "mock_long_job_worker.py"
    if mock_path.exists():
        try:
            program, args = worker_command(
                "mock",
                mock_path,
                [
                    "--job-id",
                    "health",
                    "--duration-s",
                    "0.1",
                    "--scenario",
                    "normal_pass",
                ],
            )
            proc = subprocess.run(
                [program, *args],
                cwd=str(REPO_ROOT),
                text=True,
                capture_output=True,
                timeout=5,
                env=child_process_env(),
                encoding="utf-8",
                errors="replace",
            )
            ok = proc.returncode == 0 and "job_finished" in (proc.stdout or "")
            rows.append(
                HealthRow(
                    "UI-Worker",
                    "mock_worker_smoke",
                    "pass" if ok else "fail",
                    "mock worker 可启动并完成" if ok else f"mock worker 失败 rc={proc.returncode}",
                    "" if ok else (proc.stderr or proc.stdout or "检查 mock_long_job_worker.py"),
                    {"stdout": (proc.stdout or "")[-2000:], "stderr": (proc.stderr or "")[-2000:]},
                )
            )
        except Exception as exc:
            rows.append(
                HealthRow(
                    "UI-Worker",
                    "mock_worker_smoke",
                    "fail",
                    f"mock worker 启动失败: {exc}",
                    "检查 Python/EXE worker 调度和 app/workers/mock_long_job_worker.py",
                )
            )
    return rows


def _normalize_status(status: Any) -> str:
    text = str(status or "warning").lower()
    if text in {"pass", "warning", "fail"}:
        return text
    if text in {"ok", "success", "true"}:
        return "pass"
    if text in {"error", "false"}:
        return "fail"
    return "warning"


def find_row(rows: list[HealthRow], key: str) -> HealthRow | None:
    for row in rows:
        if row.key == key:
            return row
    return None


def count_status(rows: list[HealthRow]) -> dict[str, int]:
    return {
        "pass": sum(1 for r in rows if r.status == "pass"),
        "warning": sum(1 for r in rows if r.status == "warning"),
        "fail": sum(1 for r in rows if r.status == "fail"),
    }


def build_summary_text(rows: list[HealthRow], result: dict[str, Any]) -> str:
    counts = count_status(rows)
    lines = [
        "系统健康摘要",
        f"时间戳: {result.get('ts', '')}",
        f"pass={counts['pass']} warning={counts['warning']} fail={counts['fail']}",
        "",
    ]
    ordered_groups = ["SolidWorks", LOCK_GROUP, "Vision", "Data", "License", "UI-Worker"]
    ordered_groups.extend(sorted({r.group for r in rows if r.group not in set(ordered_groups)}))
    for group in ordered_groups:
        group_rows = [r for r in rows if r.group == group]
        if not group_rows:
            continue
        lines.append(f"[{group}]")
        for row in group_rows:
            line = f"- {row.status.upper()} {row.key}: {row.message}"
            if row.fix_suggestion:
                line += f" | fix: {row.fix_suggestion}"
            lines.append(line)
        lines.append("")
    return "\n".join(lines).strip()


def system_health_payload(rows: list[HealthRow], result: dict[str, Any]) -> dict[str, Any]:
    return {
        "rows": health_rows_to_dicts(rows),
        "summary": result,
        "summary_text": build_summary_text(rows, result),
    }


def payload_to_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)
