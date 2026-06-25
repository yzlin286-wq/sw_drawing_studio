"""v3.0 Real CAD Smoke validator.

This deliberately starts a real CAD job through JobRuntimeFacade so the evidence
matches the UI architecture: Facade -> JobRunner -> QProcess worker. It does not
modify source CAD files and it does not lower QC thresholds.
"""
from __future__ import annotations

import argparse
import json
import multiprocessing
import os
import sys
import time
from pathlib import Path
from typing import Any

from PySide6.QtCore import QCoreApplication, QTimer

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PART = REPO_ROOT / "3D转2D测试图纸" / "LB26001-A-04-040.SLDPRT"
DEFAULT_REPORT = REPO_ROOT / "drw_output" / "cad_smoke_v3_0.json"
PRIMARY_LB26001_006_BASE = "LB26001-A-04-006"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _trace_path_for(report_path: Path) -> Path:
    return report_path.with_name(f"{report_path.stem}_trace.jsonl")


def _append_trace(trace_path: Path | None, stage: str, **data: Any) -> None:
    if trace_path is None:
        return
    try:
        trace_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "epoch": time.time(),
            "stage": stage,
            **data,
        }
        with trace_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _tail_trace(trace_path: Path, limit: int = 20) -> list[dict[str, Any]]:
    try:
        lines = trace_path.read_text(encoding="utf-8-sig").splitlines()
    except Exception:
        return []
    out: list[dict[str, Any]] = []
    for line in lines[-limit:]:
        try:
            out.append(json.loads(line))
        except Exception:
            pass
    return out


def _path_info(path: Path, started_epoch: float | None = None) -> dict[str, Any]:
    exists = path.exists()
    info: dict[str, Any] = {
        "path": str(path),
        "exists": exists,
        "size_bytes": 0,
        "mtime": "",
        "mtime_epoch": None,
        "fresh": False,
    }
    if not exists:
        return info
    stat = path.stat()
    info.update({
        "size_bytes": stat.st_size,
        "mtime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)),
        "mtime_epoch": stat.st_mtime,
        "fresh": bool(started_epoch is None or stat.st_mtime >= started_epoch - 1.0),
    })
    return info


def _event_type(event: dict[str, Any]) -> str:
    return str(event.get("event_type") or event.get("type") or "")


def _load_event_log(run_dir: Path) -> list[dict[str, Any]]:
    log = run_dir / "job_event_log.jsonl"
    events: list[dict[str, Any]] = []
    if not log.exists():
        return events
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            events.append(obj)
    return events


def _empty_path_info() -> dict[str, Any]:
    return {
        "path": "",
        "exists": False,
        "size_bytes": 0,
        "mtime": "",
        "mtime_epoch": None,
        "fresh": False,
    }


def _find_first(run_dir: Path, patterns: list[str]) -> Path | None:
    for pattern in patterns:
        matches = sorted(run_dir.glob(pattern))
        for match in matches:
            if match.is_file():
                return match
    return None


def _collect_artifacts(run_dir: Path, base: str, started_epoch: float | None) -> dict[str, Any]:
    paths = {
        "manifest": run_dir / "manifest.json",
        "sw_session": run_dir / "sw_session.json",
        "job_event_log": run_dir / "job_event_log.jsonl",
        "input_copy": _find_first(run_dir, [f"input/{base}.*", "input/*.SLDPRT", "input/*.SLDASM"]),
        "slddrw": _find_first(run_dir, [f"drawing/{base}_v5.SLDDRW", "drawing/*.SLDDRW"]),
        "pdf": _find_first(run_dir, [f"drawing/{base}_v5.PDF", "drawing/*.PDF"]),
        "dxf": _find_first(run_dir, [f"drawing/{base}_v5.DXF", "drawing/*.DXF"]),
        "png": _find_first(run_dir, [f"drawing/{base}_v5.PNG", "drawing/*.PNG"]),
        "qc_json": _find_first(run_dir, [f"qc/{base}_v5_qc.json", "qc/*_qc.json"]),
        "warnings_json": _find_first(run_dir, [f"qc/{base}_v5_warnings.json", "qc/*_warnings.json"]),
        "drawing_blueprint": _find_first(run_dir, ["qc/drawing_blueprint.json", "qc/*drawing_blueprint*.json", "drawing/*drawing_blueprint*.json"]),
        "vision_qc": _find_first(run_dir, ["qc/vision_qc_v6.json", "qc/vision_qc_v2.json", "qc/vision_qc_v5.json", "qc/*_v5_vision.json"]),
        "vision_qc_v6": _find_first(run_dir, ["qc/vision_qc_v6.json"]),
        "final_quality": run_dir / "qc" / "final_quality.json",
    }
    return {key: _path_info(path, started_epoch) if path else _empty_path_info() for key, path in paths.items()}


def _append_check(checks: list[dict[str, Any]], key: str, ok: bool, reason: str, fix: str = "") -> None:
    checks.append({
        "key": key,
        "pass": bool(ok),
        "reason": "" if ok else reason,
        "fix_suggestion": "" if ok else fix,
    })


def _lb26001_006_direct_cad_guard(
    part_path: Path,
    *,
    sw_state: dict[str, Any] | None = None,
    packet_report_path: Path | None = None,
) -> dict[str, Any]:
    if part_path.stem != PRIMARY_LB26001_006_BASE:
        return {
            "required": False,
            "allowed": True,
            "status": "not_applicable",
            "reason": "not_lb26001_006",
        }

    from tools.validation.lb26001_006_regression_readiness_v4_2 import (
        DEFAULT_EXPANSION_GATE,
        DEFAULT_LOCK_FILE,
        DEFAULT_UI_GATE,
        build_readiness_report,
        collect_solidworks_process_state,
    )
    from tools.validation.lb26001_006_rerun_packet_v4_2 import (
        DEFAULT_CORRECTION_PLAN,
        DEFAULT_REFERENCE_INTENT_CONTRACT,
        DEFAULT_REFERENCE_INTENT_PLAN,
        DEFAULT_REQUESTED_STATUS,
        build_rerun_packet,
    )

    readiness = build_readiness_report(
        sw_state=sw_state or collect_solidworks_process_state(),
        ui_gate_path=DEFAULT_UI_GATE,
        expansion_gate_path=DEFAULT_EXPANSION_GATE,
        lock_file=DEFAULT_LOCK_FILE,
    )
    packet = build_rerun_packet(
        readiness=readiness,
        requested_status=_read_json(DEFAULT_REQUESTED_STATUS),
        correction_plan=_read_json(DEFAULT_CORRECTION_PLAN),
        reference_intent_plan_path=DEFAULT_REFERENCE_INTENT_PLAN,
        reference_intent_contract_path=DEFAULT_REFERENCE_INTENT_CONTRACT,
    )
    if packet_report_path is not None:
        _write_json(packet_report_path, packet)
    readiness_blockers = [str(item) for item in readiness.get("blocking_issue_keys") or [] if str(item).strip()]
    offline_missing = [str(item) for item in packet.get("offline_prerequisite_missing_keys") or [] if str(item).strip()]
    allowed = bool(
        readiness.get("ready_to_start_locked_006_cad")
        and packet.get("real_cad_allowed_now")
        and not readiness_blockers
        and not offline_missing
    )
    issue_fixes = [
        str(item.get("fix_suggestion") or "")
        for item in readiness.get("issues") or []
        if isinstance(item, dict) and item.get("severity") in {"critical", "major"}
    ]
    prerequisite_fixes = [
        str(item.get("fix_suggestion") or "")
        for item in packet.get("offline_prerequisites") or []
        if isinstance(item, dict) and not item.get("pass")
    ]
    fixes: list[str] = []
    for item in issue_fixes + prerequisite_fixes:
        if item and item not in fixes:
            fixes.append(item)
    return {
        "required": True,
        "allowed": allowed,
        "status": "ready" if allowed else "blocked_by_lb26001_006_direct_guard",
        "readiness_status": readiness.get("status", ""),
        "ready_to_start_locked_006_cad": bool(readiness.get("ready_to_start_locked_006_cad")),
        "readiness_blocking_issue_keys": readiness_blockers,
        "rerun_packet_status": packet.get("status", ""),
        "rerun_packet_report": str(packet_report_path or ""),
        "rerun_packet_build_ready": bool(packet.get("packet_build_ready")),
        "real_cad_allowed_now": bool(packet.get("real_cad_allowed_now")),
        "offline_prerequisite_missing_keys": offline_missing,
        "current_006_ui_verdict": packet.get("current_006_ui_verdict") or {},
        "manual_recovery_required": bool((readiness.get("safe_recovery_guidance") or {}).get("manual_recovery_required")),
        "automatic_restart_allowed": bool((readiness.get("safe_recovery_guidance") or {}).get("automatic_restart_allowed")),
        "fix_suggestions": fixes,
        "api_is_not_final_judgement": True,
        "ui_screenshot_review_is_final_gate": True,
    }


def _write_lb26001_006_direct_guard_report(part_path: Path, report_path: Path, guard: dict[str, Any]) -> dict[str, Any]:
    reasons = list(guard.get("readiness_blocking_issue_keys") or []) + list(
        guard.get("offline_prerequisite_missing_keys") or []
    )
    if not reasons:
        reasons = [str(guard.get("status") or "lb26001_006_direct_guard_blocked")]
    payload = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "real_cad_smoke_v3",
        "part_path": str(part_path),
        "job_id": "",
        "status": {
            "status": "blocked_by_lb26001_006_direct_guard",
            "error": "lb26001_006_direct_cad_guard_not_ready",
        },
        "terminal": {
            "failed": True,
            "reason": "LB26001-A-04-006 direct real CAD smoke requires no-COM readiness and rerun packet approval first.",
        },
        "run_dir": "",
        "event_types": [],
        "event_count": 0,
        "observed_event_count": 0,
        "artifacts": {},
        "lb26001_006_direct_guard": guard,
        "lb26001_006_rerun_packet_report": str(guard.get("rerun_packet_report") or ""),
        "lb26001_006_current_ui_verdict": guard.get("current_006_ui_verdict") or {},
        "checks": [
            {
                "name": "lb26001_006_no_com_readiness_and_rerun_packet_guard",
                "pass": False,
                "reason": "; ".join(reasons),
                "fix_suggestion": (guard.get("fix_suggestions") or ["Run no-COM readiness audit and rerun packet before CAD."])[0],
            }
        ],
        "pass": False,
        "reasons": reasons,
        "fix_suggestions": list(guard.get("fix_suggestions") or []),
    }
    _write_json(report_path, payload)
    return payload


def _optional_path(value: Any) -> Path | None:
    text = str(value or "").strip()
    if not text:
        return None
    return Path(text)


def _resolve_report_path(value: Any, *, default: Path) -> Path:
    text = str(value or "").strip()
    path = Path(text) if text else default
    if not path.is_absolute():
        path = (REPO_ROOT / path).resolve()
    return path


def _set_006_rerun_packet_env(
    part_path: Path,
    packet_path: Path | None,
    trace_path: Path | None = None,
) -> str:
    if part_path.stem != PRIMARY_LB26001_006_BASE:
        return ""
    env_key = "SWDS_LB26001_006_RERUN_PACKET_PATH"
    if packet_path is not None:
        packet_text = str(packet_path)
        os.environ[env_key] = packet_text
    else:
        packet_text = os.environ.get(env_key, "").strip()
    _append_trace(trace_path, "lb26001_006_rerun_packet_env_set", packet_path=packet_text)
    return packet_text


def run_smoke(
    part_path: Path,
    timeout_s: int,
    max_rounds: int,
    report_path: Path,
    *,
    validator_grace_s: int = 30,
    trace_path: Path | None = None,
    lb26001_006_rerun_packet_path: Path | None = None,
) -> dict[str, Any]:
    from app.services.job_runtime_facade import JobRuntimeFacade

    _append_trace(trace_path, "run_smoke_enter", part_path=str(part_path), timeout_s=timeout_s, max_rounds=max_rounds)
    if trace_path is not None:
        os.environ["SWDS_VALIDATION_TRACE"] = str(trace_path)
    packet_env_path = _set_006_rerun_packet_env(part_path, lb26001_006_rerun_packet_path, trace_path)
    app = QCoreApplication.instance() or QCoreApplication(sys.argv)
    _append_trace(trace_path, "qcore_ready")
    _append_trace(trace_path, "facade_construct_start")
    facade = JobRuntimeFacade()
    _append_trace(trace_path, "facade_construct_done")
    observed_events: list[dict[str, Any]] = []
    terminal: dict[str, Any] = {"finished": False, "failed": False}
    started_epoch = time.time()
    original_stat = part_path.stat()

    def on_event(job_id: str, event_type: str, data: dict) -> None:
        observed_events.append({
            "job_id": job_id,
            "event_type": event_type,
            "data": data,
            "seen_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        })

    def on_finished(job_id: str, data: dict) -> None:
        terminal.update({"finished": True, "job_id": job_id, "result": data})
        app.quit()

    def on_failed(job_id: str, data: dict) -> None:
        terminal.update({"failed": True, "job_id": job_id, "error": data})
        app.quit()

    facade.event_logged.connect(on_event)
    facade.job_finished.connect(on_finished)
    facade.job_failed.connect(on_failed)
    _append_trace(trace_path, "signals_connected")

    try:
        _append_trace(trace_path, "start_cad_job_call_start")
        job_id = facade.start_cad_job(
            part_path=str(part_path),
            max_rounds=max_rounds,
            timeout_s=timeout_s,
            priority="normal",
            strategy="v6_recommended",
        )
        _append_trace(trace_path, "start_cad_job_call_done", job_id=job_id)
    except Exception as exc:
        _append_trace(trace_path, "start_cad_job_exception", error=str(exc))
        finished_epoch = time.time()
        payload = {
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "mode": "real_cad_smoke_v3",
            "part_path": str(part_path),
            "job_id": "",
            "started_at_epoch": started_epoch,
            "finished_at_epoch": finished_epoch,
            "duration_s": round(finished_epoch - started_epoch, 1),
            "status": {"status": "failed", "error": str(exc)},
            "terminal": {"failed": True, "error": str(exc)},
            "run_dir": "",
            "lb26001_006_rerun_packet_report": packet_env_path,
            "event_types": [],
            "event_count": 0,
            "observed_event_count": len(observed_events),
            "artifacts": {},
            "checks": [{
                "name": "facade_start_cad_job",
                "pass": False,
                "reason": f"JobRuntimeFacade.start_cad_job raised: {exc}",
                "fix_suggestion": "Fix facade/job-runner startup before running real CAD smoke.",
            }],
            "pass": False,
            "reasons": [f"JobRuntimeFacade.start_cad_job raised: {exc}"],
            "fix_suggestions": ["Fix facade/job-runner startup before running real CAD smoke."],
        }
        _write_json(report_path, payload)
        return payload

    hard_timeout = {"hit": False}

    def timeout() -> None:
        hard_timeout["hit"] = True
        terminal.update({
            "timeout": True,
            "reason": f"validator timeout after {timeout_s + validator_grace_s}s",
        })
        facade.cancel_job(job_id)
        app.quit()

    QTimer.singleShot(int((timeout_s + max(0, validator_grace_s)) * 1000), timeout)
    _append_trace(trace_path, "app_exec_enter", job_id=job_id)
    app.exec()
    _append_trace(trace_path, "app_exec_exit", job_id=job_id, terminal=terminal)

    finished_epoch = time.time()
    _append_trace(trace_path, "collect_status_start", job_id=job_id)
    status = facade.get_job_status(job_id) or {}
    _append_trace(trace_path, "collect_status_done", status=status)
    run_dir = _optional_path(status.get("run_dir"))
    result = terminal.get("result") if isinstance(terminal.get("result"), dict) else {}
    if run_dir is None and isinstance(result, dict):
        run_dir = _optional_path(result.get("run_dir"))

    manifest = _read_json(run_dir / "manifest.json") if run_dir is not None else {}
    if run_dir is None and manifest.get("run_dir"):
        run_dir = _optional_path(manifest.get("run_dir"))

    event_log_events = _load_event_log(run_dir) if run_dir is not None else []
    event_types = sorted({_event_type(e) for e in event_log_events if _event_type(e)})
    artifacts = _collect_artifacts(run_dir, part_path.stem, started_epoch) if run_dir is not None else {}
    qc = _read_json(Path(artifacts.get("qc_json", {}).get("path", ""))) if artifacts else {}
    final_quality = _read_json(Path(artifacts.get("final_quality", {}).get("path", ""))) if artifacts else {}
    sw_session = _read_json(Path(artifacts.get("sw_session", {}).get("path", ""))) if artifacts else {}

    after_stat = part_path.stat()
    checks: list[dict[str, Any]] = []
    _append_check(checks, "facade_submitted", bool(job_id), "JobRuntimeFacade did not return a job id.")
    _append_check(checks, "job_completed", status.get("status") == "completed" and terminal.get("finished") is True,
                  f"Job status is {status.get('status')}; terminal={terminal}",
                  "Inspect job_event_log.jsonl and worker stdout for the CAD worker failure.")
    _append_check(checks, "hard_timeout", not hard_timeout["hit"], "Validator hard timeout fired.",
                  "Check SolidWorks dialogs, worker timeout, and cancel/retry behavior.")
    required_events = {"job_started", "progress", "heartbeat"}
    if terminal.get("finished") is True:
        required_events.add("job_finished")
    elif terminal.get("failed") is True or status.get("status") == "failed":
        required_events.add("job_failed")
    elif not hard_timeout["hit"]:
        required_events.add("job_finished")
    missing_events = sorted(required_events - set(event_types))
    _append_check(checks, "worker_jsonl_events", not missing_events,
                  f"Missing worker events: {missing_events}",
                  "Ensure cad_job_worker emits job_started/progress/heartbeat plus job_finished or job_failed.")
    _append_check(checks, "run_dir_under_runs", run_dir is not None and run_dir.exists() and (REPO_ROOT / "drw_output" / "runs") in run_dir.resolve().parents,
                  f"run_dir is invalid: {run_dir}",
                  "Use JobRuntimeFacade.start_cad_job without overriding output_dir.")
    for key in ["manifest", "sw_session", "job_event_log", "input_copy", "slddrw", "pdf", "dxf", "png", "qc_json", "warnings_json", "drawing_blueprint", "vision_qc", "vision_qc_v6", "final_quality"]:
        info = artifacts.get(key, {})
        _append_check(checks, f"artifact_{key}", bool(info.get("exists") and info.get("size_bytes", 0) > 0),
                      f"Missing or empty artifact: {key}",
                      f"Make the CAD worker write {key} into run_dir.")
    for key in ["slddrw", "pdf", "dxf", "png", "qc_json", "warnings_json", "drawing_blueprint", "vision_qc", "vision_qc_v6", "final_quality", "manifest", "sw_session"]:
        info = artifacts.get(key, {})
        _append_check(checks, f"fresh_{key}", bool(info.get("exists") and info.get("fresh")),
                      f"Artifact is not fresh relative to job start: {key}",
                      "Regenerate the CAD job and verify mtime >= job_started_at.")
    _append_check(checks, "original_cad_unchanged",
                  original_stat.st_size == after_stat.st_size and original_stat.st_mtime == after_stat.st_mtime,
                  "Original CAD file size or mtime changed.",
                  "Only operate on copied files under run_dir/input or worker scratch directories.")
    drawing_usable = manifest.get("drawing_usable") or {}
    _append_check(checks, "manifest_drawing_usable", drawing_usable.get("pass") is True,
                  f"manifest.drawing_usable.pass is not true: {drawing_usable}",
                  "Fix generated drawing quality; do not lower QC thresholds.")
    hard_fail = manifest.get("hard_fail") or []
    _append_check(checks, "manifest_no_hard_fail", not hard_fail,
                  f"manifest hard_fail is not empty: {hard_fail}",
                  "Fix the CAD/QC cause and rerun smoke.")
    _append_check(checks, "qc_json_readable", bool(qc), "QC JSON could not be read.",
                  "Ensure *_v5_qc.json is written into run_dir/qc.")
    fq_status = str(final_quality.get("status") or "")
    _append_check(checks, "final_quality_status", fq_status in {"pass", "pass_with_warning"},
                  f"final_quality.status is {fq_status!r}",
                  "Run visual QC/final quality fusion and fix blocking issues.")
    _append_check(checks, "sw_session_connected", sw_session.get("status") == "connected" and bool(sw_session.get("sw_pid")),
                  f"sw_session does not prove connection: {sw_session}",
                  "Record SolidWorks sw_pid/revision from inside the CAD worker.")

    terminal_error = terminal.get("error") if isinstance(terminal.get("error"), dict) else {}
    failure_bucket = (
        manifest.get("failure_bucket")
        or sw_session.get("failure_bucket")
        or terminal_error.get("failure_bucket")
        or (hard_fail[0] if hard_fail else "")
    )
    failure_reason = (
        manifest.get("failure_reason")
        or sw_session.get("reason")
        or terminal_error.get("reason")
        or ""
    )
    failure_fix_suggestion = (
        manifest.get("fix_suggestion")
        or sw_session.get("fix_suggestion")
        or terminal_error.get("fix_suggestion")
        or ""
    )

    payload = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "real_cad_smoke_v3",
        "part_path": str(part_path),
        "job_id": job_id,
        "started_at_epoch": started_epoch,
        "finished_at_epoch": finished_epoch,
        "duration_s": round(finished_epoch - started_epoch, 1),
        "status": status,
        "terminal": terminal,
        "run_dir": str(run_dir or ""),
        "lb26001_006_rerun_packet_report": packet_env_path,
        "failure_bucket": failure_bucket,
        "failure_reason": failure_reason,
        "failure_fix_suggestion": failure_fix_suggestion,
        "event_types": event_types,
        "event_count": len(event_log_events),
        "observed_event_count": len(observed_events),
        "artifacts": artifacts,
        "manifest_summary": {
            "drawing_usable": drawing_usable,
            "hard_fail": hard_fail,
            "warnings": manifest.get("warnings") or [],
            "dimension_grade": manifest.get("dimension_grade", ""),
            "dimension_sources": manifest.get("dimension_sources", {}),
        },
        "qc_summary": {
            "pass": qc.get("pass"),
            "score_pass_count": qc.get("score_pass_count"),
            "hard_fail": qc.get("hard_fail") or [],
            "warnings": qc.get("warnings") or [],
            "drawing_usable": qc.get("drawing_usable") or {},
        },
        "final_quality": final_quality,
        "sw_session": sw_session,
        "checks": checks,
        "pass": all(c["pass"] for c in checks),
    }
    payload["reasons"] = [c["reason"] for c in checks if not c["pass"] and c["reason"]]
    payload["fix_suggestions"] = [c["fix_suggestion"] for c in checks if not c["pass"] and c["fix_suggestion"]]
    if failure_fix_suggestion and failure_fix_suggestion not in payload["fix_suggestions"]:
        payload["fix_suggestions"].insert(0, failure_fix_suggestion)
    _write_json(report_path, payload)
    _append_trace(trace_path, "report_written", report=str(report_path), passed=payload["pass"])
    return payload


def _run_smoke_child(
    part_path_text: str,
    timeout_s: int,
    max_rounds: int,
    report_path_text: str,
    validator_grace_s: int,
    trace_path_text: str,
    lb26001_006_rerun_packet_path_text: str,
) -> None:
    report_path = Path(report_path_text)
    trace_path = Path(trace_path_text)
    _append_trace(trace_path, "child_started", part_path=part_path_text, report_path=report_path_text)
    try:
        _append_trace(trace_path, "child_run_smoke_call")
        run_smoke(
            Path(part_path_text),
            timeout_s=timeout_s,
            max_rounds=max_rounds,
            report_path=report_path,
            validator_grace_s=validator_grace_s,
            trace_path=trace_path,
            lb26001_006_rerun_packet_path=Path(lb26001_006_rerun_packet_path_text) if lb26001_006_rerun_packet_path_text else None,
        )
        _append_trace(trace_path, "child_run_smoke_return")
    except Exception as exc:
        _append_trace(trace_path, "child_exception", error=str(exc))
        payload = {
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "mode": "real_cad_smoke_v3",
            "part_path": part_path_text,
            "job_id": "",
            "status": {"status": "failed", "error": str(exc)},
            "terminal": {"failed": True, "error": str(exc)},
            "run_dir": "",
            "lb26001_006_rerun_packet_report": lb26001_006_rerun_packet_path_text,
            "event_types": [],
            "event_count": 0,
            "observed_event_count": 0,
            "artifacts": {},
            "trace_path": str(trace_path),
            "trace_tail": _tail_trace(trace_path),
            "checks": [{
                "name": "validator_child_exception",
                "pass": False,
                "reason": f"real_cad_smoke child raised: {exc}",
                "fix_suggestion": "Inspect the validator traceback and JobRuntimeFacade startup path.",
            }],
            "pass": False,
            "reasons": [f"real_cad_smoke child raised: {exc}"],
            "fix_suggestions": ["Inspect the validator traceback and JobRuntimeFacade startup path."],
        }
        _write_json(report_path, payload)


def run_smoke_with_process_guard(
    part_path: Path,
    timeout_s: int,
    max_rounds: int,
    report_path: Path,
    *,
    validator_grace_s: int = 30,
    startup_grace_s: int = 30,
    lb26001_006_rerun_packet_path: Path | None = None,
) -> dict[str, Any]:
    guard_timeout_s = max(1, int(timeout_s) + max(0, int(validator_grace_s)) + max(0, int(startup_grace_s)))
    started_epoch = time.time()
    trace_path = _trace_path_for(report_path)
    try:
        if trace_path.exists():
            trace_path.unlink()
    except Exception:
        pass
    packet_path_text = str(lb26001_006_rerun_packet_path or "")
    _append_trace(
        trace_path,
        "parent_start",
        guard_timeout_s=guard_timeout_s,
        report_path=str(report_path),
        lb26001_006_rerun_packet_path=packet_path_text,
    )
    ctx = multiprocessing.get_context("spawn")
    proc = ctx.Process(
        target=_run_smoke_child,
        args=(
            str(part_path),
            int(timeout_s),
            int(max_rounds),
            str(report_path),
            int(validator_grace_s),
            str(trace_path),
            packet_path_text,
        ),
        name="real_cad_smoke_v3_child",
    )
    proc.start()
    _append_trace(trace_path, "parent_child_started", child_pid=proc.pid)
    proc.join(guard_timeout_s)
    if proc.is_alive():
        _append_trace(trace_path, "parent_guard_timeout", child_pid=proc.pid)
        proc.terminate()
        proc.join(5)
        finished_epoch = time.time()
        payload = {
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "mode": "real_cad_smoke_v3",
            "part_path": str(part_path),
            "job_id": "",
            "started_at_epoch": started_epoch,
            "finished_at_epoch": finished_epoch,
            "duration_s": round(finished_epoch - started_epoch, 1),
            "status": {"status": "failed", "error": "process_guard_timeout"},
            "terminal": {
                "timeout": True,
                "reason": f"process guard timeout after {guard_timeout_s}s",
                "child_pid": proc.pid,
                "child_exitcode": proc.exitcode,
            },
            "run_dir": "",
            "lb26001_006_rerun_packet_report": packet_path_text,
            "event_types": [],
            "event_count": 0,
            "observed_event_count": 0,
            "artifacts": {},
            "trace_path": str(trace_path),
            "trace_tail": _tail_trace(trace_path),
            "checks": [{
                "name": "process_guard_timeout",
                "pass": False,
                "reason": f"Validator child process did not exit within {guard_timeout_s}s.",
                "fix_suggestion": "Bound JobRuntimeFacade/QProcess startup and inspect SolidWorks dialogs or stuck worker startup.",
            }],
            "pass": False,
            "reasons": [f"Validator child process did not exit within {guard_timeout_s}s."],
            "fix_suggestions": ["Bound JobRuntimeFacade/QProcess startup and inspect SolidWorks dialogs or stuck worker startup."],
        }
        _write_json(report_path, payload)
        return payload

    payload = _read_json(report_path)
    if payload:
        _append_trace(trace_path, "parent_child_report_found", child_exitcode=proc.exitcode)
        payload.setdefault("process_guard", {
            "enabled": True,
            "timeout_s": guard_timeout_s,
            "child_exitcode": proc.exitcode,
        })
        payload.setdefault("trace_path", str(trace_path))
        payload.setdefault("trace_tail", _tail_trace(trace_path))
        _write_json(report_path, payload)
        return payload

    finished_epoch = time.time()
    _append_trace(trace_path, "parent_child_report_missing", child_exitcode=proc.exitcode)
    payload = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "real_cad_smoke_v3",
        "part_path": str(part_path),
        "job_id": "",
        "started_at_epoch": started_epoch,
        "finished_at_epoch": finished_epoch,
        "duration_s": round(finished_epoch - started_epoch, 1),
        "status": {"status": "failed", "error": f"child_exitcode={proc.exitcode}; report_missing"},
        "terminal": {"failed": True, "child_exitcode": proc.exitcode},
        "run_dir": "",
        "lb26001_006_rerun_packet_report": packet_path_text,
        "event_types": [],
        "event_count": 0,
        "observed_event_count": 0,
        "artifacts": {},
        "trace_path": str(trace_path),
        "trace_tail": _tail_trace(trace_path),
        "checks": [{
            "name": "validator_report_written",
            "pass": False,
            "reason": f"Validator child exited with code {proc.exitcode} but did not write {report_path}.",
            "fix_suggestion": "Ensure every validator failure path writes a report JSON before exiting.",
        }],
        "pass": False,
        "reasons": [f"Validator child exited with code {proc.exitcode} but did not write {report_path}."],
        "fix_suggestions": ["Ensure every validator failure path writes a report JSON before exiting."],
    }
    _write_json(report_path, payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run v3.0 Real CAD Smoke through JobRuntimeFacade.")
    parser.add_argument("--part", default=str(DEFAULT_PART), help="Absolute or repo-relative SLDPRT/SLDASM path.")
    parser.add_argument("--timeout-s", type=int, default=900)
    parser.add_argument("--validator-grace-s", type=int, default=30,
                        help="Extra seconds after the worker timeout before this validator cancels and writes a failure report.")
    parser.add_argument("--startup-grace-s", type=int, default=30,
                        help="Extra seconds for facade/QProcess startup before the process guard writes a failure report.")
    parser.add_argument("--no-process-guard", action="store_true",
                        help="Run the validator in-process. Intended only for debugging.")
    parser.add_argument("--max-rounds", type=int, default=1)
    parser.add_argument("--out", default=str(DEFAULT_REPORT), help="Report JSON path.")
    parser.add_argument(
        "--lb26001-006-rerun-packet",
        default="",
        help="Optional LB26001-A-04-006 rerun packet JSON path to pass into the CAD worker environment.",
    )
    args = parser.parse_args()

    part = Path(args.part)
    if not part.is_absolute():
        part = (REPO_ROOT / part).resolve()
    out = Path(args.out)
    if not out.is_absolute():
        out = (REPO_ROOT / out).resolve()
    if not part.exists():
        payload = {
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "mode": "real_cad_smoke_v3",
            "part_path": str(part),
            "pass": False,
            "reasons": [f"Part file does not exist: {part}"],
            "fix_suggestions": ["Provide a real SLDPRT/SLDASM from 3D转2D测试图纸."],
        }
        _write_json(out, payload)
        print(json.dumps({"pass": False, "report": str(out), "reason": payload["reasons"][0]}, ensure_ascii=False))
        return 1

    lb26001_006_rerun_packet_path = _resolve_report_path(
        args.lb26001_006_rerun_packet,
        default=out.with_name("lb26001_006_rerun_packet_v4_2.json"),
    )
    direct_guard = _lb26001_006_direct_cad_guard(
        part,
        packet_report_path=lb26001_006_rerun_packet_path if part.stem == PRIMARY_LB26001_006_BASE else None,
    )
    if direct_guard.get("required") and not direct_guard.get("allowed"):
        payload = _write_lb26001_006_direct_guard_report(part, out, direct_guard)
        print(json.dumps({
            "pass": False,
            "report": str(out),
            "run_dir": "",
            "reasons": payload.get("reasons", []),
        }, ensure_ascii=False))
        return 1

    if args.no_process_guard:
        payload = run_smoke(
            part,
            timeout_s=args.timeout_s,
            max_rounds=args.max_rounds,
            report_path=out,
            validator_grace_s=args.validator_grace_s,
            lb26001_006_rerun_packet_path=lb26001_006_rerun_packet_path if direct_guard.get("required") else None,
        )
    else:
        payload = run_smoke_with_process_guard(
            part,
            timeout_s=args.timeout_s,
            max_rounds=args.max_rounds,
            report_path=out,
            validator_grace_s=args.validator_grace_s,
            startup_grace_s=args.startup_grace_s,
            lb26001_006_rerun_packet_path=lb26001_006_rerun_packet_path if direct_guard.get("required") else None,
        )
    print(json.dumps({
        "pass": payload["pass"],
        "report": str(out),
        "run_dir": payload.get("run_dir", ""),
        "reasons": payload.get("reasons", []),
    }, ensure_ascii=False))
    return 0 if payload["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
