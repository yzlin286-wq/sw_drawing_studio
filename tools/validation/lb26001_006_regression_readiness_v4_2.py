"""Readiness audit for the next LB26001-A-04-006 real CAD regression.

This audit is intentionally file/process-state only. It does not call
SolidWorks COM, open documents, or mutate the SolidWorks session.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.solidworks_global_lock import explain_conflict, is_lock_stale

PRIMARY_BASE = "LB26001-A-04-006"
DEFAULT_UI_GATE = (
    REPO_ROOT
    / "drw_output"
    / "ui_acceptance"
    / "LB26001_006_explicit_displaydim_visible_entities_visual_review_20260623"
    / "closed_loop_strict_final_20260624"
    / "ui_visual_review_gate_summary.json"
)
DEFAULT_EXPANSION_GATE = DEFAULT_UI_GATE.parent / "lb26001_acceptance_gate_v4_2.json"
DEFAULT_LOCK_FILE = Path(os.environ.get("LOCALAPPDATA", "")) / "sw_drawing_studio" / "solidworks_global_lock.json"
DEFAULT_OUT = REPO_ROOT / "drw_output" / "diagnostics" / "lb26001_006_regression_readiness_v4_2.json"
DEFAULT_OUT_MD = REPO_ROOT / "drw_output" / "diagnostics" / "lb26001_006_regression_readiness_v4_2.md"


def _read_json(path: Path | None) -> dict[str, Any]:
    if not path:
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _repo_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


def collect_solidworks_process_state() -> dict[str, Any]:
    if os.name != "nt":
        return {
            "source": "process_probe",
            "platform": os.name,
            "process_present": False,
            "responding": None,
            "main_window_title": "",
            "reason": "non_windows_process_probe_skipped",
        }
    command = (
        "Get-Process SLDWORKS -ErrorAction SilentlyContinue | "
        "Select-Object Id,ProcessName,Responding,MainWindowTitle | ConvertTo-Json -Compress"
    )
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=8,
            check=False,
        )
    except Exception as exc:
        return {
            "source": "process_probe",
            "process_present": False,
            "responding": None,
            "main_window_title": "",
            "reason": f"process_probe_exception:{exc}",
        }
    stdout = completed.stdout.strip()
    if not stdout:
        return {
            "source": "process_probe",
            "process_present": False,
            "responding": None,
            "main_window_title": "",
            "returncode": completed.returncode,
        }
    try:
        raw = json.loads(stdout)
    except Exception as exc:
        return {
            "source": "process_probe",
            "process_present": False,
            "responding": None,
            "main_window_title": "",
            "reason": f"process_probe_json_error:{exc}",
            "stdout": stdout,
            "returncode": completed.returncode,
        }
    items = raw if isinstance(raw, list) else [raw]
    selected = items[0] if items else {}
    return {
        "source": "process_probe",
        "process_present": bool(items),
        "process_count": len(items),
        "pid": selected.get("Id"),
        "responding": selected.get("Responding"),
        "main_window_title": str(selected.get("MainWindowTitle") or ""),
        "returncode": completed.returncode,
    }


def _solidworks_issues(sw_state: dict[str, Any], lock_file: Path) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    title = str(sw_state.get("main_window_title") or "")
    responding = sw_state.get("responding")
    if not sw_state.get("process_present"):
        issues.append(_issue(
            "solidworks_not_running",
            "critical",
            {"solidworks_process": sw_state},
            "Start SolidWorks, open no unsaved work, and rerun this readiness audit before launching locked 006 CAD.",
        ))
    elif responding is not True:
        issues.append(_issue(
            "solidworks_not_responding",
            "critical",
            {"solidworks_process": sw_state},
            "Save any unsaved SolidWorks work manually, close/restart SolidWorks safely, then rerun this readiness audit.",
        ))
    if title.strip().endswith("*]") or title.strip().endswith("*"):
        issues.append(_issue(
            "solidworks_unsaved_document_visible",
            "critical",
            {"main_window_title": title},
            "Manually save or close the unsaved SolidWorks document before any CAD worker attempts the 006 rerun.",
        ))
    if lock_file.exists():
        lock_payload = _read_json(lock_file)
        stale = is_lock_stale(lock_payload)
        conflict = explain_conflict(lock_payload)
        if stale:
            issues.append(_issue(
                "solidworks_global_lock_stale",
                "info",
                {
                    "lock_file": str(lock_file),
                    "lock": lock_payload,
                    "conflict": conflict,
                },
                "The SolidWorks lock appears stale; the next lock acquisition should release it, but do not start CAD until SolidWorks itself is responsive and no unsaved document is visible.",
            ))
        else:
            issues.append(_issue(
                "solidworks_global_lock_present",
                "major",
                {
                    "lock_file": str(lock_file),
                    "lock": lock_payload,
                    "conflict": conflict,
                },
                "Wait for the current SolidWorks lock owner to finish or resolve stale lock diagnostics before starting 006.",
            ))
    return issues


def _ui_gate_issues(ui_gate: dict[str, Any], path: Path) -> list[dict[str, Any]]:
    if not ui_gate:
        return [_issue(
            "ui_visual_review_gate_missing",
            "major",
            {"ui_gate": str(path)},
            "Run apply_ui_visual_review_v4.py after the next 006 Drawing Review UI screenshot judgement.",
        )]
    entries = {str(item.get("base") or ""): item for item in ui_gate.get("entries") or [] if isinstance(item, dict)}
    entry = entries.get(PRIMARY_BASE) or {}
    issues: list[dict[str, Any]] = []
    if entry and not entry.get("vision_qc_v6_visual_acceptance_pass"):
        issues.append(_issue(
            "previous_006_v6_ui_gate_not_pass",
            "info",
            {"ui_gate": str(path), "entry": entry},
            "This is expected for the previous failed run; rerun closure after the next fresh 006 CAD/UI screenshot attempt.",
        ))
    if entry and not entry.get("reference_compare_v4_pass"):
        issues.append(_issue(
            "previous_006_v4_ui_gate_not_pass",
            "info",
            {"ui_gate": str(path), "entry": entry},
            "This is expected for the previous failed run; next run must resolve strict v4 blockers.",
        ))
    return issues


def _expansion_gate_issues(expansion_gate: dict[str, Any], path: Path) -> list[dict[str, Any]]:
    if not expansion_gate:
        return [_issue(
            "lb26001_expansion_gate_missing",
            "major",
            {"expansion_gate": str(path)},
            "Run lb26001_acceptance_gate_v4_2.py after UI closure so expansion remains explicitly blocked until 006 passes.",
        )]
    if expansion_gate.get("status") != "pass":
        return [_issue(
            "lb26001_expansion_currently_blocked",
            "info",
            {"expansion_gate": str(path), "status": expansion_gate.get("status"), "reasons": expansion_gate.get("reasons", [])},
            "This is expected until 006 passes; do not run acceptance on 007/008/009/015/022.",
        )]
    return []


def _issue(key: str, severity: str, evidence: dict[str, Any], fix_suggestion: str) -> dict[str, Any]:
    return {
        "key": key,
        "severity": severity,
        "source": "lb26001_006_regression_readiness_v4_2",
        "confidence": 1.0,
        "evidence": evidence,
        "fix_suggestion": fix_suggestion,
    }


def _safe_recovery_guidance(sw_state: dict[str, Any], blocking_keys: list[str]) -> dict[str, Any]:
    title = str(sw_state.get("main_window_title") or "")
    needs_manual_recovery = any(
        key in set(blocking_keys)
        for key in {
            "solidworks_not_running",
            "solidworks_not_responding",
            "solidworks_unsaved_document_visible",
        }
    )
    steps: list[str] = []
    if "solidworks_unsaved_document_visible" in blocking_keys:
        steps.append("In SolidWorks, manually save or close the visible unsaved document before any automated CAD job starts.")
    if "solidworks_not_responding" in blocking_keys:
        steps.append("If SolidWorks is not responding, use the Windows UI to recover, close, or restart it only after protecting unsaved work.")
    if "solidworks_not_running" in blocking_keys:
        steps.append("Start SolidWorks manually and leave it responsive with no unsaved document marker in the title bar.")
    steps.extend(
        [
            "Rerun this no-COM readiness audit after SolidWorks is responsive.",
            "Only when readiness is ready, rerun the no-COM 006 rerun packet.",
            "Then run exactly one locked LB26001-A-04-006 CAD regression through staged_cad_validation_v3.",
        ]
    )
    return {
        "manual_recovery_required": needs_manual_recovery,
        "automatic_restart_allowed": False,
        "reason": (
            "Automatic restart is forbidden while SolidWorks is unresponsive or an unsaved document marker is visible."
            if needs_manual_recovery
            else "No manual SolidWorks recovery blocker is present in the readiness report."
        ),
        "observed_main_window_title": title,
        "steps": steps,
        "do_not": [
            "Do not kill or restart SLDWORKS.exe from automation while unsaved work may exist.",
            "Do not start 007/008/009/015/022 acceptance before 006 passes.",
            "Do not use API or file creation as a substitute for the Drawing Review UI screenshot judgement.",
        ],
    }


def build_readiness_report(
    *,
    sw_state: dict[str, Any],
    ui_gate_path: Path = DEFAULT_UI_GATE,
    expansion_gate_path: Path = DEFAULT_EXPANSION_GATE,
    lock_file: Path = DEFAULT_LOCK_FILE,
) -> dict[str, Any]:
    ui_gate = _read_json(ui_gate_path)
    expansion_gate = _read_json(expansion_gate_path)
    lock_payload = _read_json(lock_file) if lock_file.exists() else {}
    lock_conflict = explain_conflict(lock_payload) if lock_payload else {}
    issues = (
        _solidworks_issues(sw_state, lock_file)
        + _ui_gate_issues(ui_gate, ui_gate_path)
        + _expansion_gate_issues(expansion_gate, expansion_gate_path)
    )
    blocking = [item for item in issues if item.get("severity") in {"critical", "major"}]
    ready = not blocking
    blocking_keys = [str(item.get("key")) for item in blocking]
    return {
        "schema": "sw_drawing_studio.lb26001_006_regression_readiness.v4_2",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "base": PRIMARY_BASE,
        "ready_to_start_locked_006_cad": ready,
        "status": "ready" if ready else "blocked",
        "solidworks_process": sw_state,
        "solidworks_lock_file": str(lock_file),
        "solidworks_lock_present": lock_file.exists(),
        "solidworks_lock_stale": is_lock_stale(lock_payload) if lock_payload else False,
        "solidworks_lock_conflict": lock_conflict,
        "solidworks_lock_owner": lock_conflict.get("owner", {}) if isinstance(lock_conflict, dict) else {},
        "solidworks_lock_fix_suggestion": str(lock_conflict.get("fix_suggestion") or "") if isinstance(lock_conflict, dict) else "",
        "ui_visual_review_gate": str(ui_gate_path),
        "ui_visual_review_gate_status": ui_gate.get("status", "missing"),
        "lb26001_expansion_gate": str(expansion_gate_path),
        "lb26001_expansion_gate_status": expansion_gate.get("status", "missing"),
        "issues": issues,
        "blocking_issue_keys": blocking_keys,
        "safe_recovery_guidance": _safe_recovery_guidance(sw_state, blocking_keys),
        "next_commands_after_solidworks_safe": [
            "python tools\\validation\\staged_cad_validation_v3.py --stage LB26001_006 --timeout-s 900 --max-rounds 1 --out-dir drw_output\\staged_validation\\LB26001_006_<timestamp>",
            "python tools\\ui_robot\\drawing_visual_review_suite.py --summary drw_output\\staged_validation\\LB26001_006_<timestamp>\\summary.json --base LB26001-A-04-006 --out-dir drw_output\\ui_acceptance\\LB26001_006_<timestamp>_visual_review",
            "write manual_visual_judgement.json from the Drawing Review UI screenshot verdict",
            "python tools\\validation\\apply_ui_visual_review_v4.py --summary <summary.json> --ui-report <drawing_visual_review_report.json> --manual-review <manual_visual_judgement.json> --base LB26001-A-04-006",
            "python tools\\validation\\lb26001_acceptance_gate_v4_2.py --gate-summary <ui_visual_review_gate_summary.json>",
        ],
    }


def render_markdown(report: dict[str, Any]) -> str:
    sw_state = report.get("solidworks_process") or {}
    guidance = report.get("safe_recovery_guidance") or {}
    lock_conflict = report.get("solidworks_lock_conflict") or {}
    lock_owner = report.get("solidworks_lock_owner") or {}
    lines = [
        "# LB26001-A-04-006 Readiness Recovery Checklist v4.2",
        "",
        f"- Generated at: `{report.get('generated_at', '')}`",
        f"- Status: `{report.get('status', '')}`",
        f"- ready_to_start_locked_006_cad: `{bool(report.get('ready_to_start_locked_006_cad'))}`",
        f"- Manual recovery required: `{bool(guidance.get('manual_recovery_required'))}`",
        f"- Automatic restart allowed: `{bool(guidance.get('automatic_restart_allowed'))}`",
        f"- Blocking issue keys: `{', '.join(str(item) for item in report.get('blocking_issue_keys') or [])}`",
        "",
        "## Observed SolidWorks State",
        "",
        f"- process_present: `{sw_state.get('process_present')}`",
        f"- responding: `{sw_state.get('responding')}`",
        f"- pid: `{sw_state.get('pid', '')}`",
        f"- main_window_title: `{sw_state.get('main_window_title', '')}`",
        f"- global_lock_present: `{bool(report.get('solidworks_lock_present'))}`",
        f"- global_lock_stale: `{bool(report.get('solidworks_lock_stale'))}`",
        "",
        "## SolidWorks Lock Details",
        "",
        f"- lock_file: `{report.get('solidworks_lock_file', '')}`",
        f"- conflict_reason: `{lock_conflict.get('reason', '')}`",
        f"- fix_suggestion: `{lock_conflict.get('fix_suggestion', '')}`",
        f"- owner_project: `{lock_owner.get('owner_project', '')}`",
        f"- owner_job_id: `{lock_owner.get('owner_job_id', '')}`",
        f"- owner_run_id: `{lock_owner.get('owner_run_id', '')}`",
        f"- owner_pid: `{lock_owner.get('owner_pid', '')}`",
        f"- owner_worker_pid: `{lock_owner.get('owner_worker_pid', '')}`",
        f"- operation: `{lock_owner.get('operation', '')}`",
        f"- heartbeat_age_s: `{lock_owner.get('heartbeat_age_s', '')}`",
        "",
        "## Manual Recovery Steps",
        "",
    ]
    for index, step in enumerate(guidance.get("steps") or [], start=1):
        lines.append(f"{index}. {step}")
    if not guidance.get("steps"):
        lines.append("1. No manual SolidWorks recovery step is required by this report.")
    lines.extend(["", "## Do Not", ""])
    for item in guidance.get("do_not") or []:
        lines.append(f"- {item}")
    lines.extend(["", "## Recovery Verification Command", ""])
    lines.append(
        "- `python tools\\validation\\lb26001_006_regression_readiness_v4_2.py --out "
        "drw_output\\diagnostics\\lb26001_006_regression_readiness_v4_2.json --out-md "
        "drw_output\\diagnostics\\lb26001_006_regression_readiness_v4_2.md`"
    )
    lines.extend(["", "## Next Commands After Readiness Is Safe", ""])
    for command in report.get("next_commands_after_solidworks_safe") or []:
        lines.append(f"- `{command}`")
    lines.extend(["", "## Issues", ""])
    for item in report.get("issues") or []:
        lines.append(
            "- `{key}` severity=`{severity}` fix=`{fix}`".format(
                key=item.get("key", ""),
                severity=item.get("severity", ""),
                fix=item.get("fix_suggestion", ""),
            )
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit readiness for the next locked LB26001-A-04-006 CAD rerun.")
    parser.add_argument("--ui-gate", default=str(DEFAULT_UI_GATE))
    parser.add_argument("--expansion-gate", default=str(DEFAULT_EXPANSION_GATE))
    parser.add_argument("--lock-file", default=str(DEFAULT_LOCK_FILE))
    parser.add_argument("--sw-state-json", default="", help="Optional fixture JSON for tests/offline audits.")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    args = parser.parse_args()

    sw_state = _read_json(_repo_path(args.sw_state_json)) if args.sw_state_json else collect_solidworks_process_state()
    report = build_readiness_report(
        sw_state=sw_state,
        ui_gate_path=_repo_path(args.ui_gate),
        expansion_gate_path=_repo_path(args.expansion_gate),
        lock_file=_repo_path(args.lock_file),
    )
    out = _repo_path(args.out)
    _write_json(out, report)
    out_md = _repo_path(args.out_md) if args.out_md else None
    if out_md is not None:
        _write_text(out_md, render_markdown(report))
    print(json.dumps({
        "ready": report["ready_to_start_locked_006_cad"],
        "status": report["status"],
        "blocking_issue_keys": report["blocking_issue_keys"],
        "report": str(out),
        "report_md": str(out_md or ""),
    }, ensure_ascii=False))
    return 0 if report["ready_to_start_locked_006_cad"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
