"""Final EXE Reality Gate for v3.0 SolidWorks readiness.

This validator intentionally launches the frozen EXE worker instead of importing
application services from the current source tree. It records the exact worker
JSONL events and writes the release-gate artifact required by v3.0.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EXE = REPO_ROOT / "dist" / "sw_drawing_studio.exe"
DEFAULT_OUT_DIR = REPO_ROOT / "drw_output" / "ui_acceptance" / "exe_reality_gate_v3_0"
REPORT_NAME = "exe_reality_gate_v3_0.json"
REPORT_MD_NAME = "exe_reality_gate_v3_0.md"

REQUIRED_EVENTS = {"job_started", "progress", "heartbeat", "job_finished"}

HARD_PASS_ROWS = {
    "solidworks",
    "sw_running",
    "sw_revision",
    "sw_revision_supported",
    "addin_ping",
    "opendoc6_test",
    "dialog_guard",
    "template",
    "macro_bas",
    "output_dir",
    "chinese_path_support",
}

RECORDED_ROWS = {
    "document_manager_key",
    "macro_swp",
    "vision_model",
    "opencv",
    "ultralytics",
    "ocr",
    "fitz",
    "cv2",
    "ultralytics_import",
    "paddleocr",
    "mock_worker_smoke",
    "cad_job_worker.py",
    "batch_job_worker.py",
    "drawing_review_worker.py",
    "qc_action_worker.py",
    "llm_action_worker.py",
    "vision_audit_worker.py",
    "mock_long_job_worker.py",
    "health_check_worker.py",
}


def _decode(data: bytes) -> str:
    for encoding in ("utf-8", "gb18030", "mbcs"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
        except LookupError:
            continue
    return data.decode("utf-8", errors="replace")


def _jsonl_events(stdout: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in stdout.splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            event = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def _event_type(event: dict[str, Any]) -> str:
    return str(event.get("event_type") or event.get("type") or "")


def _event_types(events: list[dict[str, Any]]) -> set[str]:
    return {_event_type(event) for event in events if _event_type(event)}


def _latest_event(events: list[dict[str, Any]], event_type: str) -> dict[str, Any] | None:
    for event in reversed(events):
        if _event_type(event) == event_type:
            return event
    return None


def _select_probe_source(explicit: str | None = None) -> Path | None:
    if explicit:
        path = Path(explicit)
        return path.resolve() if path.exists() else None

    sample_dir = REPO_ROOT / "3D转2D测试图纸"
    if not sample_dir.exists():
        return None
    candidates = [
        p for p in sample_dir.iterdir()
        if (
            p.is_file()
            and not p.name.startswith("~$")
            and p.stat().st_size > 10_000
            and p.suffix.lower() in {".sldprt", ".sldasm", ".slddrw"}
        )
    ]
    preferred = [
        p for p in candidates
        if "LB26001-A-04-040" in p.name or "LB26001" in p.name or p.suffix.lower() == ".sldprt"
    ]
    pool = preferred or candidates
    if not pool:
        return None
    return sorted(pool, key=lambda p: (p.suffix.lower() != ".sldprt", p.stat().st_size, p.name))[0].resolve()


def _copy_probe_doc(source: Path | None, out_dir: Path) -> Path | None:
    if source is None:
        return None
    input_work = out_dir / "input_work"
    input_work.mkdir(parents=True, exist_ok=True)
    target = input_work / source.name
    shutil.copy2(source, target)
    return target.resolve()


def _run_health_worker(exe: Path, probe_doc: Path | None, timeout_s: int) -> dict[str, Any]:
    cmd = [
        str(exe),
        "--worker",
        "system_health",
        "--job-id",
        "exe_reality_gate_v3_0",
        "--ensure-solidworks",
    ]
    if probe_doc is not None:
        cmd.extend(["--real-opendoc6-probe", "--probe-doc-path", str(probe_doc)])

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    started = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_s,
            env=env,
        )
        stdout = _decode(proc.stdout)
        stderr = _decode(proc.stderr)
        return {
            "cmd": cmd,
            "returncode": proc.returncode,
            "timeout": False,
            "duration_s": round(time.monotonic() - started, 2),
            "stdout": stdout,
            "stderr": stderr,
            "events": _jsonl_events(stdout),
        }
    except subprocess.TimeoutExpired as exc:
        stdout = _decode(exc.stdout or b"")
        stderr = _decode(exc.stderr or b"")
        return {
            "cmd": cmd,
            "returncode": None,
            "timeout": True,
            "duration_s": round(time.monotonic() - started, 2),
            "stdout": stdout,
            "stderr": stderr,
            "events": _jsonl_events(stdout),
            "timeout_s": timeout_s,
        }


def _payload_from_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    finished = _latest_event(events, "job_finished")
    if not finished:
        return {}
    data = finished.get("data")
    if not isinstance(data, dict):
        return {}
    result = data.get("result")
    return result if isinstance(result, dict) else {}


def _row_by_key(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = payload.get("rows")
    if not isinstance(rows, list):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if isinstance(row, dict) and row.get("key"):
            result[str(row["key"])] = row
    return result


def _row_status(row: dict[str, Any] | None) -> str:
    if not row:
        return "missing"
    return str(row.get("status") or "warning").lower()


def _row_detail_value(row: dict[str, Any] | None, key: str) -> Any:
    if not row:
        return None
    if key in row:
        return row.get(key)
    details = row.get("details")
    if isinstance(details, dict):
        if key in details:
            return details.get(key)
        nested = details.get("details")
        if isinstance(nested, dict):
            return nested.get(key)
    return None


def _check_rows(rows: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    checks: list[dict[str, Any]] = []
    reasons: list[str] = []
    fixes: list[str] = []

    for key in sorted(HARD_PASS_ROWS):
        row = rows.get(key)
        status = _row_status(row)
        passed = status == "pass"
        reason = "" if passed else (str(row.get("message") or "") if row else f"缺少必需健康项: {key}")
        fix = "" if passed else (str(row.get("fix_suggestion") or "") if row else "确认 System Health worker 输出完整 rows")
        checks.append(
            {
                "key": key,
                "required": "pass",
                "present": row is not None,
                "status": status,
                "pass": passed,
                "reason": reason,
                "evidence": row,
                "fix_suggestion": fix,
            }
        )
        if not passed:
            reasons.append(f"{key}: {reason}")
            if fix:
                fixes.append(f"{key}: {fix}")

    for key in sorted(RECORDED_ROWS):
        row = rows.get(key)
        status = _row_status(row)
        passed = row is not None and status in {"pass", "warning"}
        reason = "" if passed else f"缺少需记录健康项: {key}"
        fix = "" if passed else "确认 System Health worker 输出完整 rows"
        checks.append(
            {
                "key": key,
                "required": "recorded_pass_or_warning",
                "present": row is not None,
                "status": status,
                "pass": passed,
                "reason": reason,
                "evidence": row,
                "fix_suggestion": fix,
            }
        )
        if not passed:
            reasons.append(f"{key}: {reason}")
            fixes.append(f"{key}: {fix}")

    solidworks = rows.get("solidworks")
    sw_pid = _row_detail_value(solidworks, "sw_pid")
    pid_ok = isinstance(sw_pid, int) and sw_pid > 0
    checks.append(
        {
            "key": "sw_pid",
            "required": "positive_integer",
            "present": sw_pid is not None,
            "status": "pass" if pid_ok else "fail",
            "pass": pid_ok,
            "reason": "" if pid_ok else "Reality Gate 未记录有效 sw_pid",
            "evidence": {"sw_pid": sw_pid, "solidworks_row": solidworks},
            "fix_suggestion": "" if pid_ok else "确认 SolidWorks 作为活动 COM 对象运行，GetProcessID 可用，并重跑 Reality Gate",
        }
    )
    if not pid_ok:
        reasons.append("sw_pid: Reality Gate 未记录有效 sw_pid")
        fixes.append("sw_pid: 确认 SolidWorks 作为活动 COM 对象运行，GetProcessID 可用，并重跑 Reality Gate")

    return checks, reasons, sorted(set(fixes))


def _failure_bucket(run: dict[str, Any], missing_events: list[str], payload: dict[str, Any], checks: list[dict[str, Any]]) -> str:
    if run.get("timeout"):
        return "system_health_worker_timeout"
    if run.get("returncode") not in (0, None):
        return "system_health_worker_failed"
    if missing_events:
        return "system_health_worker_missing_events"
    if not payload:
        return "system_health_payload_missing"

    failed = [check for check in checks if not check.get("pass")]
    failed_keys = {str(check.get("key")) for check in failed}
    if "solidworks" in failed_keys or "sw_running" in failed_keys:
        return "solidworks_not_running"
    if "sw_pid" in failed_keys:
        return "solidworks_pid_missing"
    if "sw_revision" in failed_keys or "sw_revision_supported" in failed_keys:
        return "solidworks_revision_unverified"
    if "addin_ping" in failed_keys:
        return "addin_ping_failed"
    if "opendoc6_test" in failed_keys:
        return "opendoc6_probe_failed"
    if "dialog_guard" in failed_keys:
        return "dialog_guard_unavailable"
    if failed_keys & {"template", "macro_bas", "output_dir", "chinese_path_support"}:
        return "required_resource_unavailable"
    if failed:
        return "reality_gate_checks_failed"
    return ""


def _write_markdown(report: dict[str, Any], path: Path) -> None:
    status = "PASS" if report.get("pass") else "WARNING"
    lines = [
        "# v3.0 EXE Reality Gate",
        "",
        f"Generated: {report.get('generated_at', '')}",
        f"EXE: `{report.get('exe', '')}`",
        f"Status: **{status}**",
        f"Failure bucket: `{report.get('failure_bucket') or ''}`",
        "",
        "## Command",
        "",
        "```powershell",
        " ".join(str(part) for part in report.get("command", [])),
        "```",
        "",
        "## Required Checks",
        "",
        "| Key | Required | Status | Result |",
        "| --- | --- | --- | --- |",
    ]
    for check in report.get("checks", []):
        result = "PASS" if check.get("pass") else "WARNING"
        lines.append(f"| {check.get('key')} | {check.get('required')} | {check.get('status')} | {result} |")

    lines.extend(["", "## Reasons", ""])
    for reason in report.get("reasons", []) or ["No blocking reasons."]:
        lines.append(f"- {reason}")
    lines.extend(["", "## Fix Suggestions", ""])
    for fix in report.get("fix_suggestions", []) or ["No fix suggestions."]:
        lines.append(f"- {fix}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_gate(exe: Path, out_dir: Path, timeout_s: int, probe_source: str | None) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    selected_source = _select_probe_source(probe_source)
    probe_doc = _copy_probe_doc(selected_source, out_dir)

    if not exe.exists():
        report = {
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "mode": "exe_reality_gate_v3",
            "exe": str(exe),
            "out_dir": str(out_dir),
            "pass": False,
            "status": "fail",
            "failure_bucket": "exe_missing",
            "reasons": [f"EXE 不存在: {exe}"],
            "fix_suggestions": ["先运行 PyInstaller 构建 dist/sw_drawing_studio.exe"],
            "artifacts": {},
        }
        (out_dir / REPORT_NAME).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        _write_markdown(report, out_dir / REPORT_MD_NAME)
        return report

    run = _run_health_worker(exe, probe_doc, timeout_s)
    events = run["events"]
    types = sorted(_event_types(events))
    missing_events = sorted(REQUIRED_EVENTS - set(types))
    payload = _payload_from_events(events)
    rows = _row_by_key(payload)
    checks, row_reasons, row_fixes = _check_rows(rows)

    event_ok = run.get("returncode") == 0 and not run.get("timeout") and not missing_events and bool(payload)
    pass_gate = event_ok and all(bool(check.get("pass")) for check in checks)

    reasons: list[str] = []
    fixes: list[str] = []
    if run.get("timeout"):
        reasons.append(f"System Health worker 超时: {timeout_s}s")
        fixes.append("检查 SolidWorks 弹窗、OpenDoc6 卡死或 worker 启动问题")
    if run.get("returncode") not in (0, None):
        reasons.append(f"System Health worker 返回码为 {run.get('returncode')}")
        fixes.append("查看 stdout_tail/stderr_tail 并修复 worker 参数或 EXE 构建")
    if missing_events:
        reasons.append(f"缺少 worker JSONL 事件: {', '.join(missing_events)}")
        fixes.append("确认 health_check_worker.py 按 JSONL 契约输出 job_started/progress/heartbeat/job_finished")
    if not payload:
        reasons.append("未从 job_finished 事件中解析到 System Health payload")
        fixes.append("检查 System Health worker 是否在 data.result 中返回 rows/summary")
    reasons.extend(row_reasons)
    fixes.extend(row_fixes)

    failure_bucket = _failure_bucket(run, missing_events, payload, checks)
    report = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "exe_reality_gate_v3",
        "exe": str(exe),
        "out_dir": str(out_dir),
        "command": run["cmd"],
        "returncode": run.get("returncode"),
        "timeout": run.get("timeout"),
        "duration_s": run.get("duration_s"),
        "timeout_s": timeout_s,
        "probe_source": str(selected_source) if selected_source else "",
        "probe_doc_path": str(probe_doc) if probe_doc else "",
        "pass": pass_gate,
        "status": "pass" if pass_gate else "warning",
        "failure_bucket": failure_bucket,
        "event_count": len(events),
        "event_types": types,
        "required_events": sorted(REQUIRED_EVENTS),
        "missing_events": missing_events,
        "health_summary": payload.get("summary", {}) if payload else {},
        "checks": checks,
        "rows": list(rows.values()),
        "reasons": sorted(set(reasons)),
        "fix_suggestions": sorted(set(fixes)),
        "stdout_tail": str(run.get("stdout") or "")[-3000:],
        "stderr_tail": str(run.get("stderr") or "")[-3000:],
        "artifacts": {
            "report_json": str(out_dir / REPORT_NAME),
            "report_md": str(out_dir / REPORT_MD_NAME),
            "copied_probe_doc": str(probe_doc) if probe_doc else "",
        },
        "remaining_gates": [
            "Real CAD Smoke remains pending.",
            "2D annotation validation smoke remains pending.",
            "Reference drawing comparison smoke remains pending.",
            "Staged CAD validation remains pending.",
            "Historical Visual Audit 100 percent coverage remains pending.",
        ],
    }
    (out_dir / REPORT_NAME).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_markdown(report, out_dir / REPORT_MD_NAME)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run final EXE Reality Gate for sw_drawing_studio v3.0.")
    parser.add_argument("--exe", default=str(DEFAULT_EXE))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--timeout-s", type=int, default=180)
    parser.add_argument("--probe-source", default="", help="Optional SLDPRT/SLDASM/SLDDRW copied before OpenDoc6 probe.")
    args = parser.parse_args(argv)

    report = run_gate(
        exe=Path(args.exe).resolve(),
        out_dir=Path(args.out_dir).resolve(),
        timeout_s=args.timeout_s,
        probe_source=args.probe_source or None,
    )
    print(
        json.dumps(
            {
                "pass": report["pass"],
                "status": report["status"],
                "failure_bucket": report.get("failure_bucket", ""),
                "report": report.get("artifacts", {}).get("report_json", ""),
            },
            ensure_ascii=False,
        )
    )
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
