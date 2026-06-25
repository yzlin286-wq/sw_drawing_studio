"""File-only gap audit for the LB26001-A-04-006 real landing loop.

The audit intentionally does not call SolidWorks, COM, OCR, or worker
subprocesses. It explains whether the next locked 006 CAD run may start and
whether the six requested drawings have UI screenshot-backed acceptance.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
PRIMARY_BASE = "LB26001-A-04-006"
REQUESTED_BASES = [
    PRIMARY_BASE,
    "LB26001-A-04-007",
    "LB26001-A-04-008",
    "LB26001-A-04-009",
    "LB26001-A-04-015",
    "LB26001-A-04-022",
]

DEFAULT_READINESS = REPO_ROOT / "drw_output" / "diagnostics" / "lb26001_006_regression_readiness_v4_2.json"
DEFAULT_RERUN_PACKET = REPO_ROOT / "drw_output" / "diagnostics" / "lb26001_006_rerun_packet_v4_2.json"
DEFAULT_REQUESTED_STATUS = REPO_ROOT / "drw_output" / "diagnostics" / "lb26001_requested_drawings_status_v4_2.json"
DEFAULT_DIRECT_GUARD = REPO_ROOT / "drw_output" / "diagnostics" / "lb26001_006_direct_smoke_guard_v4_2.json"
DEFAULT_ACCEPTANCE_PROOF = REPO_ROOT / "drw_output" / "diagnostics" / "lb26001_006_acceptance_proof_v4_2.json"
DEFAULT_LIFECYCLE_AUDIT = REPO_ROOT / "drw_output" / "diagnostics" / "lb26001_006_displaydim_lifecycle_audit_v4_2.json"
DEFAULT_OUT_JSON = REPO_ROOT / "drw_output" / "diagnostics" / "lb26001_006_real_landing_gap_audit_v4_2.json"
DEFAULT_OUT_MD = REPO_ROOT / "drw_output" / "diagnostics" / "lb26001_006_real_landing_gap_audit_v4_2.md"

DEFAULT_STAGED_VALIDATION_SOURCE = REPO_ROOT / "tools" / "validation" / "staged_cad_validation_v3.py"
DEFAULT_REAL_CAD_SMOKE_SOURCE = REPO_ROOT / "tools" / "validation" / "real_cad_smoke_v3.py"
DEFAULT_JOB_RUNNER_SOURCE = REPO_ROOT / "app" / "services" / "job_runner.py"
DEFAULT_FACADE_SOURCE = REPO_ROOT / "app" / "services" / "job_runtime_facade.py"
DEFAULT_CAD_WORKER_SOURCE = REPO_ROOT / "app" / "workers" / "cad_job_worker.py"
DEFAULT_GLOBAL_LOCK_SOURCE = REPO_ROOT / "app" / "services" / "solidworks_global_lock.py"
DEFAULT_LOCK_CONFLICT_TEST_SOURCE = REPO_ROOT / "test_v4_2_cad_worker_lock_conflict.py"
STAGED_PREFLIGHT_SUMMARY_GLOBS = [
    "LB26001_006_*preflight*/summary.json",
    "LB26001_006_*readiness*/summary.json",
    "LB26001_006_packet_ready_readiness_bucket_*/summary.json",
]


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _read_json(path: Path | None) -> dict[str, Any]:
    if not path:
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _repo_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


def _path_exists(path: Path | None) -> bool:
    return bool(path and path.exists() and path.is_file() and path.stat().st_size > 0)


def _text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except Exception:
        return ""


def _json_status(path: Path | None, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": str(path or ""),
        "exists": _path_exists(path),
        "loaded": bool(payload),
    }


def _requirement(
    key: str,
    passed: bool,
    status: str,
    evidence: dict[str, Any],
    fix_suggestion: str,
    *,
    severity: str = "major",
) -> dict[str, Any]:
    return {
        "key": key,
        "pass": bool(passed),
        "status": status,
        "severity": severity,
        "evidence": evidence,
        "fix_suggestion": "" if passed else fix_suggestion,
        "api_is_not_final_judgement": True,
    }


def _bool_nested(payload: dict[str, Any], key: str, nested: str) -> bool | None:
    value = payload.get(key)
    if isinstance(value, bool):
        return value
    nested_payload = payload.get(nested)
    if isinstance(nested_payload, dict) and isinstance(nested_payload.get(key), bool):
        return nested_payload.get(key)
    return None


def _staged_preflight_no_cad_started(path: Path | None, payload: dict[str, Any]) -> bool:
    if not path or not payload:
        return False
    run_root = path.parent
    return bool(
        payload.get("processed") == 0
        and payload.get("deliverable_count") == 0
        and not (run_root / "sw_connection_guard.json").exists()
        and not (run_root / f"01_{PRIMARY_BASE}").exists()
    )


def _staged_preflight_summary_candidate(path: Path) -> bool:
    payload = _read_json(path)
    if not payload:
        return False
    preflight_markers = (
        "readiness_preflight_pass",
        "rerun_packet_preflight_pass",
        "lb26001_006_real_cad_allowed_now",
        "sw_connection_guard_skipped_due_to_readiness",
        "lb26001_006_rerun_packet_blocked_only_by_readiness",
    )
    return any(key in payload for key in preflight_markers) and _staged_preflight_no_cad_started(path, payload)


def _latest_staged_preflight_summary() -> Path | None:
    root = REPO_ROOT / "drw_output" / "staged_validation"
    by_path: dict[str, Path] = {}
    for pattern in STAGED_PREFLIGHT_SUMMARY_GLOBS:
        for path in root.glob(pattern):
            if _staged_preflight_summary_candidate(path):
                by_path[str(path)] = path
    matches = sorted(by_path.values(), key=lambda path: path.stat().st_mtime if path.exists() else 0, reverse=True)
    return matches[0] if matches else None


def _staged_preflight_report(path: Path | None, payload: dict[str, Any]) -> dict[str, Any]:
    failure_bucket = payload.get("failure_bucket") or []
    if not isinstance(failure_bucket, list):
        failure_bucket = [str(failure_bucket)]
    ui_evidence = payload.get("lb26001_006_ui_evidence")
    if not isinstance(ui_evidence, dict):
        ui_evidence = {}
    latest_findings = ui_evidence.get("latest_manual_findings") or payload.get("lb26001_006_latest_manual_findings") or []
    if not isinstance(latest_findings, list):
        latest_findings = [str(latest_findings)]
    return {
        "path": str(path or ""),
        "exists": _path_exists(path),
        "loaded": bool(payload),
        "status": payload.get("status"),
        "processed": payload.get("processed"),
        "deliverable_count": payload.get("deliverable_count"),
        "readiness_preflight_pass": payload.get("readiness_preflight_pass"),
        "rerun_packet_preflight_pass": payload.get("rerun_packet_preflight_pass"),
        "lb26001_006_real_cad_allowed_now": payload.get("lb26001_006_real_cad_allowed_now"),
        "lb26001_006_rerun_packet_build_ready": payload.get("lb26001_006_rerun_packet_build_ready"),
        "lb26001_006_rerun_packet_blocked_only_by_readiness": payload.get(
            "lb26001_006_rerun_packet_blocked_only_by_readiness"
        ),
        "sw_connection_guard_skipped_due_to_readiness": payload.get("sw_connection_guard_skipped_due_to_readiness"),
        "failure_bucket": [str(item) for item in failure_bucket],
        "no_cad_started": _staged_preflight_no_cad_started(path, payload),
        "ui_evidence": ui_evidence,
        "comparison_image": str(
            payload.get("lb26001_006_comparison_image") or ui_evidence.get("comparison_image") or ""
        ),
        "latest_manual_findings": [str(item) for item in latest_findings if str(item).strip()],
        "latest_manual_required_correction": str(
            payload.get("lb26001_006_latest_manual_required_correction")
            or ui_evidence.get("latest_manual_required_correction")
            or ""
        ),
    }


def _per_drawing_ui_matrix(requested_status: dict[str, Any]) -> list[dict[str, Any]]:
    raw = requested_status.get("per_drawing_ui_review_matrix") or []
    if not isinstance(raw, list):
        return []
    matrix: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, dict):
            matrix.append(dict(item))
    return matrix


def _per_drawing_ui_summary(requested_status: dict[str, Any]) -> dict[str, Any]:
    matrix = _per_drawing_ui_matrix(requested_status)
    by_base = {str(item.get("base") or ""): item for item in matrix}
    missing_bases = [base for base in REQUESTED_BASES if base not in by_base]
    incomplete = [base for base in REQUESTED_BASES if not bool(by_base.get(base, {}).get("pass"))]
    api_only_claim = bool(requested_status.get("pass_count") == len(REQUESTED_BASES) and incomplete)
    accepted = bool(matrix and not missing_bases and not incomplete)
    entries: list[dict[str, Any]] = []
    for base in REQUESTED_BASES:
        item = by_base.get(base) or {}
        entries.append(
            {
                "base": base,
                "pass": bool(item.get("pass")),
                "application_ui_screenshot_required": item.get("application_ui_screenshot_required") is not False,
                "application_ui_screenshot_present": bool(item.get("application_ui_screenshot_present")),
                "application_ui_screenshot_file_count": int(item.get("application_ui_screenshot_file_count") or 0),
                "application_ui_screenshot_content_check_pass": bool(
                    item.get("application_ui_screenshot_content_check_pass")
                ),
                "manual_visual_judgement_present": bool(item.get("manual_visual_judgement_present")),
                "manual_visual_judgement_pass": bool(item.get("manual_visual_judgement_pass")),
                "manual_visual_checklist_pass": bool(item.get("manual_visual_checklist_pass")),
                "manual_visual_checklist_failed_items": list(item.get("manual_visual_checklist_failed_items") or []),
                "manual_visual_checklist_missing_items": list(item.get("manual_visual_checklist_missing_items") or []),
                "manual_visual_checklist_not_passed_items": list(
                    item.get("manual_visual_checklist_not_passed_items") or []
                ),
                "latest_manual_visual_checklist": item.get("latest_manual_visual_checklist") or {},
                "latest_manual_visual_checklist_notes": item.get("latest_manual_visual_checklist_notes") or {},
                "latest_manual_findings": list(item.get("latest_manual_findings") or []),
                "latest_manual_required_correction": str(item.get("latest_manual_required_correction") or ""),
                "source_ui_report_application_ui_ok": bool(item.get("source_ui_report_application_ui_ok")),
                "ui_visual_review_status": str(item.get("ui_visual_review_status") or ""),
                "missing_ui_acceptance_requirements": list(item.get("missing_ui_acceptance_requirements") or []),
                "ui_screenshot_files": list(item.get("ui_screenshot_files") or []),
                "application_ui_screenshot_paths_existing_application_ui": list(
                    item.get("application_ui_screenshot_paths_existing_application_ui") or []
                ),
                "comparison_image": str(item.get("comparison_image") or ""),
                "generated_png": str(item.get("generated_png") or ""),
                "reference_png": str(item.get("reference_png") or ""),
                "final_judgement_source": str(
                    item.get("final_judgement_source")
                    or "application_drawing_review_ui_screenshot_manual_visual_judgement"
                ),
            }
        )
    return {
        "matrix_present": bool(matrix),
        "matrix_count": len(matrix),
        "accepted": accepted,
        "missing_bases": missing_bases,
        "incomplete_bases": incomplete,
        "api_only_pass_claim_detected": api_only_claim,
        "entries": entries,
    }


def _source_signature_report(
    *,
    staged_validation_source_path: Path,
    real_cad_smoke_source_path: Path,
    job_runner_source_path: Path,
    facade_source_path: Path,
    cad_worker_source_path: Path,
    global_lock_source_path: Path,
    lock_conflict_test_source_path: Path,
) -> dict[str, Any]:
    staged = _text(staged_validation_source_path)
    smoke = _text(real_cad_smoke_source_path)
    runner = _text(job_runner_source_path)
    facade = _text(facade_source_path)
    cad_worker = _text(cad_worker_source_path)
    lock_source = _text(global_lock_source_path)
    lock_test = _text(lock_conflict_test_source_path)
    architecture_checks = [
        {
            "key": "staged_validation_invokes_real_cad_smoke",
            "pass": "real_cad_smoke_v3.py" in staged,
        },
        {
            "key": "staged_validation_does_not_directly_spawn_cad_worker",
            "pass": "cad_job_worker.py" not in staged,
        },
        {
            "key": "real_cad_smoke_uses_facade",
            "pass": "JobRuntimeFacade" in smoke and ".start_cad_job(" in smoke,
        },
        {
            "key": "job_runner_uses_qprocess",
            "pass": "QProcess" in runner and ".start(" in runner,
        },
        {
            "key": "facade_cad_worker_registered",
            "pass": "CAD_WORKER" in facade and "cad_job_worker.py" in facade,
        },
    ]
    lock_checks = [
        {
            "key": "cad_worker_reports_lock_block",
            "pass": "blocked_by_solidworks_lock" in cad_worker,
        },
        {
            "key": "cad_worker_reports_lock_bucket",
            "pass": "solidworks_lock_conflict" in cad_worker and "failure_bucket" in cad_worker,
        },
        {
            "key": "cad_worker_reports_fix_suggestion",
            "pass": "fix_suggestion" in cad_worker,
        },
        {
            "key": "global_lock_reports_owner",
            "pass": "owner" in lock_source and "blocked_by_solidworks_lock" in lock_source,
        },
        {
            "key": "lock_conflict_contract_test_exists",
            "pass": "blocked_by_solidworks_lock" in lock_test
            and "solidworks_lock_conflict" in lock_test
            and "fix_suggestion" in lock_test,
        },
    ]
    return {
        "architecture_checks": architecture_checks,
        "architecture_pass": all(item["pass"] for item in architecture_checks),
        "lock_contract_checks": lock_checks,
        "lock_contract_pass": all(item["pass"] for item in lock_checks),
        "sources": {
            "staged_validation": str(staged_validation_source_path),
            "real_cad_smoke": str(real_cad_smoke_source_path),
            "job_runner": str(job_runner_source_path),
            "facade": str(facade_source_path),
            "cad_worker": str(cad_worker_source_path),
            "global_lock": str(global_lock_source_path),
            "lock_conflict_test": str(lock_conflict_test_source_path),
        },
    }


def build_gap_audit(
    *,
    readiness_path: Path = DEFAULT_READINESS,
    rerun_packet_path: Path = DEFAULT_RERUN_PACKET,
    requested_status_path: Path = DEFAULT_REQUESTED_STATUS,
    direct_guard_path: Path = DEFAULT_DIRECT_GUARD,
    acceptance_proof_path: Path = DEFAULT_ACCEPTANCE_PROOF,
    lifecycle_audit_path: Path = DEFAULT_LIFECYCLE_AUDIT,
    staged_preflight_summary_path: Path | None = None,
    staged_validation_source_path: Path = DEFAULT_STAGED_VALIDATION_SOURCE,
    real_cad_smoke_source_path: Path = DEFAULT_REAL_CAD_SMOKE_SOURCE,
    job_runner_source_path: Path = DEFAULT_JOB_RUNNER_SOURCE,
    facade_source_path: Path = DEFAULT_FACADE_SOURCE,
    cad_worker_source_path: Path = DEFAULT_CAD_WORKER_SOURCE,
    global_lock_source_path: Path = DEFAULT_GLOBAL_LOCK_SOURCE,
    lock_conflict_test_source_path: Path = DEFAULT_LOCK_CONFLICT_TEST_SOURCE,
    out_json: Path | None = None,
    out_md: Path | None = None,
) -> dict[str, Any]:
    readiness = _read_json(readiness_path)
    packet = _read_json(rerun_packet_path)
    requested_status = _read_json(requested_status_path)
    direct_guard_report = _read_json(direct_guard_path)
    direct_guard = direct_guard_report.get("lb26001_006_direct_guard") or {}
    acceptance_proof = _read_json(acceptance_proof_path)
    lifecycle_audit = _read_json(lifecycle_audit_path)
    preflight_path = staged_preflight_summary_path or _latest_staged_preflight_summary()
    staged_preflight = _read_json(preflight_path)

    readiness_ready = readiness.get("ready_to_start_locked_006_cad") is True
    readiness_blockers = [str(item) for item in readiness.get("blocking_issue_keys") or [] if str(item).strip()]
    manual_recovery = _bool_nested(readiness, "manual_recovery_required", "safe_recovery_guidance")
    automatic_restart = _bool_nested(readiness, "automatic_restart_allowed", "safe_recovery_guidance")
    real_cad_allowed = packet.get("real_cad_allowed_now") is True
    direct_guard_allowed = direct_guard.get("allowed") is True
    direct_guard_required = direct_guard.get("required") is True
    direct_guard_blocked = direct_guard_required and direct_guard_allowed is False and not direct_guard_report.get("run_dir")
    packet_missing = [str(item) for item in packet.get("offline_prerequisite_missing_keys") or []]

    ui_summary = _per_drawing_ui_summary(requested_status)
    staged_preflight_report = _staged_preflight_report(preflight_path, staged_preflight)
    source_report = _source_signature_report(
        staged_validation_source_path=staged_validation_source_path,
        real_cad_smoke_source_path=real_cad_smoke_source_path,
        job_runner_source_path=job_runner_source_path,
        facade_source_path=facade_source_path,
        cad_worker_source_path=cad_worker_source_path,
        global_lock_source_path=global_lock_source_path,
        lock_conflict_test_source_path=lock_conflict_test_source_path,
    )

    staged_preflight_pass = bool(
        staged_preflight
        and staged_preflight_report["no_cad_started"] is True
        and staged_preflight_report["lb26001_006_real_cad_allowed_now"] is False
        and staged_preflight_report["sw_connection_guard_skipped_due_to_readiness"] is True
    )

    requirements = [
        _requirement(
            "readiness_report_loaded",
            bool(readiness),
            "pass" if readiness else "missing",
            _json_status(readiness_path, readiness) | {
                "status": readiness.get("status"),
                "ready_to_start_locked_006_cad": readiness.get("ready_to_start_locked_006_cad"),
                "blocking_issue_keys": readiness_blockers,
            },
            "Regenerate the no-COM readiness report before deciding whether CAD may run.",
            severity="critical",
        ),
        _requirement(
            "manual_recovery_and_no_automatic_restart_policy",
            (not readiness_blockers) or (manual_recovery is True and automatic_restart is False),
            "pass" if (not readiness_blockers or (manual_recovery is True and automatic_restart is False)) else "not_proven",
            {
                "readiness_blocking_issue_keys": readiness_blockers,
                "manual_recovery_required": manual_recovery,
                "automatic_restart_allowed": automatic_restart,
            },
            "When SolidWorks is not ready, require manual recovery and keep automatic restart forbidden.",
            severity="critical",
        ),
        _requirement(
            "locked_006_cad_not_allowed_until_readiness_passes",
            (readiness_ready and real_cad_allowed) or (not readiness_ready and not real_cad_allowed),
            "pass" if (readiness_ready and real_cad_allowed) or (not readiness_ready and not real_cad_allowed) else "not_proven",
            {
                "ready_to_start_locked_006_cad": readiness_ready,
                "real_cad_allowed_now": real_cad_allowed,
                "readiness_blocking_issue_keys": readiness_blockers,
                "offline_prerequisite_missing_keys": packet_missing,
            },
            "Do not start real 006 CAD until readiness and rerun packet both allow it.",
            severity="critical",
        ),
        _requirement(
            "direct_006_real_cad_smoke_guard_blocks_when_not_ready",
            bool(direct_guard_report) and ((readiness_ready and direct_guard_allowed) or (not readiness_ready and direct_guard_blocked)),
            "pass" if direct_guard_report else "missing",
            _json_status(direct_guard_path, direct_guard_report) | {
                "direct_guard_required": direct_guard_required,
                "direct_guard_allowed": direct_guard_allowed,
                "direct_guard_status": direct_guard.get("status"),
                "run_dir": direct_guard_report.get("run_dir", ""),
                "reasons": direct_guard_report.get("reasons", []),
            },
            "Run the direct 006 smoke guard evidence and ensure it exits before CAD when readiness is blocked.",
            severity="critical",
        ),
        _requirement(
            "staged_preflight_skips_sw_connection_when_readiness_blocked",
            staged_preflight_pass,
            "pass" if staged_preflight_pass else ("missing" if not staged_preflight else "not_proven"),
            staged_preflight_report,
            "Rerun the staged 006 preflight and keep it from touching SolidWorks while readiness is blocked.",
            severity="major",
        ),
        _requirement(
            "real_cad_entrypoint_uses_facade_qprocess_worker",
            source_report["architecture_pass"],
            "pass" if source_report["architecture_pass"] else "not_proven",
            {
                "checks": source_report["architecture_checks"],
                "sources": source_report["sources"],
            },
            "Keep staged real CAD routed through real_cad_smoke_v3, JobRuntimeFacade, JobRunner, and QProcess.",
            severity="critical",
        ),
        _requirement(
            "solidworks_global_lock_conflict_contract_present",
            source_report["lock_contract_pass"],
            "pass" if source_report["lock_contract_pass"] else "not_proven",
            {
                "checks": source_report["lock_contract_checks"],
                "sources": source_report["sources"],
            },
            "Maintain blocked_by_solidworks_lock, owner, failure_bucket, and fix_suggestion diagnostics.",
            severity="critical",
        ),
        _requirement(
            "six_requested_drawings_status_loaded",
            bool(requested_status) and all(base in requested_status.get("requested_bases", []) for base in REQUESTED_BASES),
            "pass" if requested_status else "missing",
            _json_status(requested_status_path, requested_status) | {
                "status": requested_status.get("status"),
                "pass_count": requested_status.get("pass_count"),
                "not_pass_count": requested_status.get("not_pass_count"),
                "requested_bases": requested_status.get("requested_bases", []),
            },
            "Regenerate the requested drawings status report with all six requested bases.",
            severity="major",
        ),
        _requirement(
            "api_only_success_cannot_accept_requested_drawings",
            bool(requested_status)
            and requested_status.get("final_judgement_requires_application_ui_per_drawing") is True
            and requested_status.get("api_is_not_final_judgement") is True
            and not ui_summary["api_only_pass_claim_detected"],
            "pass" if requested_status else "missing",
            {
                "final_judgement_requires_application_ui_per_drawing": requested_status.get(
                    "final_judgement_requires_application_ui_per_drawing"
                ),
                "api_is_not_final_judgement": requested_status.get("api_is_not_final_judgement"),
                "pass_count": requested_status.get("pass_count"),
                "per_drawing_ui_review_incomplete_count": requested_status.get("per_drawing_ui_review_incomplete_count"),
                "api_only_pass_claim_detected": ui_summary["api_only_pass_claim_detected"],
            },
            "Do not accept any requested drawing unless its application UI screenshot review entry passes.",
            severity="critical",
        ),
        _requirement(
            "six_drawing_application_ui_review_complete",
            ui_summary["accepted"],
            "pass" if ui_summary["accepted"] else "blocked",
            {
                "matrix_present": ui_summary["matrix_present"],
                "matrix_count": ui_summary["matrix_count"],
                "missing_bases": ui_summary["missing_bases"],
                "incomplete_bases": ui_summary["incomplete_bases"],
                "entries": ui_summary["entries"],
            },
            "Capture application Drawing Review UI screenshots and complete manual visual checklists for every requested drawing.",
            severity="critical",
        ),
        _requirement(
            "primary_006_acceptance_proof_passes",
            acceptance_proof.get("pass") is True,
            "pass" if acceptance_proof.get("pass") is True else ("missing" if not acceptance_proof else "blocked"),
            _json_status(acceptance_proof_path, acceptance_proof) | {
                "status": acceptance_proof.get("status"),
                "pass": acceptance_proof.get("pass"),
                "blocking_issue_keys": acceptance_proof.get("blocking_issue_keys", []),
                "run_dir": acceptance_proof.get("run_dir"),
            },
            "Finish a fresh 006 CAD/UI closure and obtain a passing 006 acceptance proof before expanding.",
            severity="critical",
        ),
        _requirement(
            "displaydim_lifecycle_passes_for_006",
            lifecycle_audit.get("pass") is True,
            "pass" if lifecycle_audit.get("pass") is True else ("missing" if not lifecycle_audit else "blocked"),
            _json_status(lifecycle_audit_path, lifecycle_audit) | {
                "status": lifecycle_audit.get("status"),
                "pass": lifecycle_audit.get("pass"),
                "blocking_issue_keys": lifecycle_audit.get("blocking_issue_keys", []),
            },
            "Preserve at least 12 real SolidWorks DisplayDim annotations through the 006 lifecycle and rerun the lifecycle audit.",
            severity="critical",
        ),
        _requirement(
            "dependent_drawings_remain_blocked_until_006_passes",
            requested_status.get("status") == "blocked_by_006" and acceptance_proof.get("pass") is not True,
            "pass" if requested_status.get("status") == "blocked_by_006" and acceptance_proof.get("pass") is not True else "not_proven",
            {
                "requested_status": requested_status.get("status"),
                "primary_acceptance_proof_pass": acceptance_proof.get("pass"),
                "blocked_bases": [base for base in REQUESTED_BASES if base != PRIMARY_BASE],
            },
            "Keep 007/008/009/015/022 acceptance blocked until 006 passes the full UI-backed gate.",
            severity="major",
        ),
    ]

    critical_failures = [item["key"] for item in requirements if item["severity"] == "critical" and not item["pass"]]
    missing_requirements = [item["key"] for item in requirements if not item["pass"] and item["status"] == "missing"]
    blocked_requirements = [item["key"] for item in requirements if not item["pass"] and item["status"] == "blocked"]

    if readiness_blockers or not readiness_ready:
        overall_status = "blocked_by_solidworks_readiness"
    elif not acceptance_proof.get("pass"):
        overall_status = "blocked_by_006_acceptance_proof"
    elif not ui_summary["accepted"]:
        overall_status = "blocked_by_application_ui_screenshot_review"
    elif critical_failures:
        overall_status = "not_proven"
    else:
        overall_status = "ready_for_next_locked_006_step"

    payload = {
        "schema": "sw_drawing_studio.lb26001_006_real_landing_gap_audit.v4_2",
        "generated_at": _now(),
        "base": PRIMARY_BASE,
        "requested_bases": REQUESTED_BASES,
        "status": overall_status,
        "pass": False,
        "release_ready": False,
        "ready_to_start_locked_006_cad": readiness_ready,
        "real_cad_allowed_now": real_cad_allowed,
        "must_not_run_real_cad_when_blocked": True,
        "manual_solidworks_recovery_required": bool(manual_recovery),
        "automatic_restart_allowed": bool(automatic_restart) if automatic_restart is not None else False,
        "api_is_not_final_judgement": True,
        "api_only_acceptance_allowed": False,
        "application_ui_screenshot_is_final_gate": True,
        "per_drawing_application_ui_screenshot_required": True,
        "six_requested_drawings_accepted": ui_summary["accepted"],
        "six_requested_drawings_all_currently_unqualified": requested_status.get("pass_count") == 0,
        "critical_failure_keys": critical_failures,
        "missing_requirement_keys": missing_requirements,
        "blocked_requirement_keys": blocked_requirements,
        "readiness_blocking_issue_keys": readiness_blockers,
        "staged_preflight_summary_path": staged_preflight_report["path"],
        "staged_preflight_status": staged_preflight_report["status"],
        "staged_preflight_no_cad_started": staged_preflight_report["no_cad_started"],
        "staged_preflight_failure_bucket": staged_preflight_report["failure_bucket"],
        "staged_preflight_packet_build_ready": staged_preflight_report[
            "lb26001_006_rerun_packet_build_ready"
        ],
        "staged_preflight_packet_blocked_only_by_readiness": staged_preflight_report[
            "lb26001_006_rerun_packet_blocked_only_by_readiness"
        ],
        "staged_preflight_ui_evidence": staged_preflight_report["ui_evidence"],
        "staged_preflight_comparison_image": staged_preflight_report["comparison_image"],
        "staged_preflight_latest_manual_findings": staged_preflight_report["latest_manual_findings"],
        "staged_preflight_latest_manual_required_correction": staged_preflight_report[
            "latest_manual_required_correction"
        ],
        "requirements": requirements,
        "per_drawing_ui_review_matrix": ui_summary["entries"],
        "source_signature_report": source_report,
        "next_actions": [
            "Manually start or recover SolidWorks, then rerun the no-COM readiness audit.",
            "Rerun the no-COM 006 rerun packet; real CAD may start only if readiness and packet both allow it.",
            "Run exactly one locked LB26001-A-04-006 CAD regression through staged_cad_validation_v3.",
            "Run DisplayDim lifecycle, reference compare/style, v6 visual QC, then Drawing Review UI screenshot review for 006.",
            "Only after 006 passes the UI-backed acceptance proof, repeat the same UI screenshot workflow for 007/008/009/015/022.",
        ],
    }

    if out_json is not None:
        _write_json(out_json, payload)
    if out_md is not None:
        _write_text(out_md, render_markdown(payload))
    return payload


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# LB26001-A-04-006 Real Landing Gap Audit v4.2",
        "",
        f"- Generated at: `{payload.get('generated_at')}`",
        f"- Status: `{payload.get('status')}`",
        f"- Release ready: `{payload.get('release_ready')}`",
        f"- Ready to start locked 006 CAD: `{payload.get('ready_to_start_locked_006_cad')}`",
        f"- Real CAD allowed now: `{payload.get('real_cad_allowed_now')}`",
        f"- Staged preflight no CAD started: `{payload.get('staged_preflight_no_cad_started')}`",
        f"- Staged preflight packet build ready: `{payload.get('staged_preflight_packet_build_ready')}`",
        f"- Staged preflight blocked only by readiness: `{payload.get('staged_preflight_packet_blocked_only_by_readiness')}`",
        f"- Six requested drawings accepted: `{payload.get('six_requested_drawings_accepted')}`",
        f"- API-only acceptance allowed: `{payload.get('api_only_acceptance_allowed')}`",
        f"- Application UI screenshot final gate: `{payload.get('application_ui_screenshot_is_final_gate')}`",
        "",
        "## Latest Staged Preflight",
        "",
        f"- Summary: `{payload.get('staged_preflight_summary_path')}`",
        f"- Status: `{payload.get('staged_preflight_status')}`",
        f"- Failure bucket: `{','.join(payload.get('staged_preflight_failure_bucket') or [])}`",
        f"- Comparison image: `{payload.get('staged_preflight_comparison_image') or ''}`",
        "",
    ]
    staged_findings = [
        str(item)
        for item in payload.get("staged_preflight_latest_manual_findings") or []
        if str(item).strip()
    ]
    if staged_findings:
        lines.extend(["## Staged UI Findings", ""])
        for finding in staged_findings:
            lines.append(f"- {finding}")
        lines.append("")
    lines.extend(["## Blocking Keys", ""])
    for key in payload.get("critical_failure_keys") or []:
        lines.append(f"- `{key}`")
    if not payload.get("critical_failure_keys"):
        lines.append("- None")
    lines.extend(["", "## Requirements", ""])
    for item in payload.get("requirements") or []:
        mark = "PASS" if item.get("pass") else str(item.get("status") or "FAIL").upper()
        lines.append(f"- `{item.get('key')}`: **{mark}**")
        fix = str(item.get("fix_suggestion") or "")
        if fix:
            lines.append(f"  Fix: {fix}")
    lines.extend(["", "## Per-Drawing UI Review", ""])
    for item in payload.get("per_drawing_ui_review_matrix") or []:
        lines.append(
            "- `{base}` pass=`{passed}` screenshot_count=`{count}` status=`{status}` missing=`{missing}`".format(
                base=item.get("base"),
                passed=item.get("pass"),
                count=item.get("application_ui_screenshot_file_count"),
                status=item.get("ui_visual_review_status"),
                missing=",".join(item.get("missing_ui_acceptance_requirements") or []),
            )
        )
    lines.extend(["", "## Next Actions", ""])
    for action in payload.get("next_actions") or []:
        lines.append(f"- {action}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a no-COM 006 real landing gap audit.")
    parser.add_argument("--readiness", default=str(DEFAULT_READINESS))
    parser.add_argument("--rerun-packet", default=str(DEFAULT_RERUN_PACKET))
    parser.add_argument("--requested-status", default=str(DEFAULT_REQUESTED_STATUS))
    parser.add_argument("--direct-guard", default=str(DEFAULT_DIRECT_GUARD))
    parser.add_argument("--acceptance-proof", default=str(DEFAULT_ACCEPTANCE_PROOF))
    parser.add_argument("--lifecycle-audit", default=str(DEFAULT_LIFECYCLE_AUDIT))
    parser.add_argument("--staged-preflight-summary", default="")
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    parser.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    args = parser.parse_args()

    staged_preflight = _repo_path(args.staged_preflight_summary) if args.staged_preflight_summary else None
    payload = build_gap_audit(
        readiness_path=_repo_path(args.readiness),
        rerun_packet_path=_repo_path(args.rerun_packet),
        requested_status_path=_repo_path(args.requested_status),
        direct_guard_path=_repo_path(args.direct_guard),
        acceptance_proof_path=_repo_path(args.acceptance_proof),
        lifecycle_audit_path=_repo_path(args.lifecycle_audit),
        staged_preflight_summary_path=staged_preflight,
        out_json=_repo_path(args.out_json),
        out_md=_repo_path(args.out_md),
    )
    print(json.dumps({
        "status": payload.get("status"),
        "pass": payload.get("pass"),
        "ready_to_start_locked_006_cad": payload.get("ready_to_start_locked_006_cad"),
        "real_cad_allowed_now": payload.get("real_cad_allowed_now"),
        "staged_preflight_no_cad_started": payload.get("staged_preflight_no_cad_started"),
        "staged_preflight_packet_build_ready": payload.get("staged_preflight_packet_build_ready"),
        "staged_preflight_packet_blocked_only_by_readiness": payload.get(
            "staged_preflight_packet_blocked_only_by_readiness"
        ),
        "six_requested_drawings_accepted": payload.get("six_requested_drawings_accepted"),
        "out_json": str(_repo_path(args.out_json)),
        "out_md": str(_repo_path(args.out_md)),
    }, ensure_ascii=False, indent=2))
    return 0 if payload.get("status") == "ready_for_next_locked_006_step" else 1


if __name__ == "__main__":
    raise SystemExit(main())
