"""Summarize the requested LB26001 drawings against UI-first acceptance.

This report is file-only. It deliberately treats API, geometry, and style
metrics as supporting evidence and uses application Drawing Review UI evidence
as the acceptance source of truth.
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.application_ui_screenshot_validator import validate_application_ui_screenshots

PRIMARY_BASE = "LB26001-A-04-006"
REQUESTED_BASES = [
    PRIMARY_BASE,
    "LB26001-A-04-007",
    "LB26001-A-04-008",
    "LB26001-A-04-009",
    "LB26001-A-04-015",
    "LB26001-A-04-022",
]
DEFAULT_ACCEPTANCE_GATE = (
    REPO_ROOT
    / "drw_output"
    / "ui_acceptance"
    / "LB26001_006_explicit_displaydim_visible_entities_visual_review_20260623"
    / "closed_loop_strict_final_20260624"
    / "lb26001_acceptance_gate_v4_2.json"
)
DEFAULT_ACCEPTANCE_PROOF = REPO_ROOT / "drw_output" / "diagnostics" / "lb26001_006_acceptance_proof_v4_2.json"
DEFAULT_READINESS = REPO_ROOT / "drw_output" / "diagnostics" / "lb26001_006_regression_readiness_v4_2.json"
DEFAULT_DIRECT_UI_SCREENSHOT_RECHECK = (
    REPO_ROOT
    / "drw_output"
    / "ui_acceptance"
    / "LB26001_ref6_visual_review_manual_20260623"
    / "codex_direct_ui_screenshot_recheck_20260624.json"
)
DEFAULT_MANUAL_REVIEWS = [
    DEFAULT_DIRECT_UI_SCREENSHOT_RECHECK,
    REPO_ROOT / "drw_output" / "ui_acceptance" / "LB26001_ref6_visual_review_manual_20260623" / "manual_visual_judgement_codex_20260624.json",
    REPO_ROOT / "drw_output" / "ui_acceptance" / "LB26001_006_explicit_displaydim_visible_entities_visual_review_20260623" / "manual_visual_judgement_codex_v4_2_20260624.json",
    REPO_ROOT / "drw_output" / "ui_acceptance" / "LB26001_ref6_visual_review_manual_20260623" / "manual_visual_judgement.json",
    REPO_ROOT / "drw_output" / "ui_acceptance" / "LB26001_006_explicit_displaydim_visible_entities_visual_review_20260623" / "manual_visual_judgement.json",
    REPO_ROOT / "drw_output" / "ui_acceptance" / "LB26001_ref5_fresh_png_visual_review_bases_20260622" / "manual_visual_judgement.json",
]
DEFAULT_MANUAL_REVIEW_GLOBS = [
    REPO_ROOT
    / "drw_output"
    / "ui_acceptance"
    / "LB26001_006_locked_real_rerun_*_visual_review"
    / "manual_visual_judgement*.json",
    REPO_ROOT
    / "drw_output"
    / "ui_acceptance"
    / "LB26001_ref6_application_ui_screenshot_recheck*"
    / "manual_visual_judgement_codex_*.json",
    REPO_ROOT
    / "drw_output"
    / "ui_acceptance"
    / "LB26001_ref6_application_ui_screenshot_recheck*"
    / "manual_visual_judgement.json",
]
DEFAULT_OUT = REPO_ROOT / "drw_output" / "diagnostics" / "lb26001_requested_drawings_status_v4_2.json"


def _read_json(path: Path | None) -> dict[str, Any]:
    if not path:
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def _same_path(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except Exception:
        return str(left).lower() == str(right).lower()


def _latest_locked_real_rerun_acceptance_gate() -> Path | None:
    staged_root = REPO_ROOT / "drw_output" / "staged_validation"
    ui_root = REPO_ROOT / "drw_output" / "ui_acceptance"
    candidates: list[tuple[float, Path]] = []
    for summary_path in staged_root.glob("LB26001_006_locked_real_rerun_*/summary.json"):
        summary = _read_json(summary_path)
        if str(summary.get("stage") or "") != "LB26001_006":
            continue
        if int(summary.get("processed") or 0) < 1:
            continue
        gate_path = (
            ui_root
            / f"{summary_path.parent.name}_visual_review"
            / "closed_loop"
            / "lb26001_acceptance_gate_v4_2.json"
        )
        if not gate_path.exists():
            continue
        try:
            mtime = max(summary_path.stat().st_mtime, gate_path.stat().st_mtime)
        except Exception:
            mtime = 0.0
        candidates.append((mtime, gate_path))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _default_manual_review_paths() -> list[Path]:
    paths: list[Path] = [path for path in DEFAULT_MANUAL_REVIEWS if path.exists()]
    for pattern in DEFAULT_MANUAL_REVIEW_GLOBS:
        for raw_path in glob.glob(str(pattern)):
            path = Path(raw_path)
            if path.exists():
                paths.append(path)
    result: list[Path] = []
    seen: set[str] = set()
    for path in sorted(paths, key=lambda item: item.stat().st_mtime if item.exists() else 0, reverse=True):
        key = str(path.resolve()).lower()
        if key not in seen:
            seen.add(key)
            result.append(path)
    return result


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _repo_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


def _resolve_artifact_path(value: Any, *, base_dir: Path | None = None) -> Path | None:
    text = str(value or "").strip()
    if not text:
        return None
    path = Path(text)
    if path.is_absolute():
        return path
    if base_dir is not None:
        local = (base_dir / path).resolve()
        if local.exists():
            return local
    return (REPO_ROOT / path).resolve()


def _acceptance_entry_map(acceptance_gate: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in acceptance_gate.get("base_results") or []:
        if not isinstance(item, dict):
            continue
        base = str(item.get("base") or "").strip()
        if base:
            result[base] = item
    return result


def _issue_map(acceptance_gate: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for item in acceptance_gate.get("issues") or []:
        if not isinstance(item, dict):
            continue
        base = str(item.get("base") or "").strip()
        if base:
            result.setdefault(base, []).append(item)
    return result


def _manual_review_entries(paths: list[Path]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for path in paths:
        payload = _read_json(path)
        if not payload:
            continue
        for container in ["cases", "entries"]:
            for item in payload.get(container) or []:
                if not isinstance(item, dict):
                    continue
                base = str(item.get("base") or "").strip()
                if not base:
                    continue
                normalized = dict(item)
                normalized["manual_review"] = str(path)
                normalized["manual_review_mtime"] = path.stat().st_mtime if path.exists() else 0
                normalized["overall_status"] = str(payload.get("overall_status") or payload.get("status") or "")
                normalized["review_mode"] = str(
                    payload.get("review_mode")
                    or payload.get("review_method")
                    or payload.get("method")
                    or payload.get("review_scope")
                    or ""
                )
                result.setdefault(base, []).append(normalized)
    for entries in result.values():
        entries.sort(key=lambda item: float(item.get("manual_review_mtime") or 0), reverse=True)
    return result


def _latest_manual(entries: list[dict[str, Any]]) -> dict[str, Any]:
    return entries[0] if entries else {}


def _manual_status(entry: dict[str, Any]) -> str:
    return str(
        entry.get("manual_status")
        or entry.get("verdict")
        or entry.get("status")
        or entry.get("overall_status")
        or ""
    ).lower()


def _manual_screenshot_files(entry: dict[str, Any]) -> list[str]:
    base_dir = Path(str(entry.get("manual_review") or "")).parent
    paths: list[str] = []
    for key in ["ui_screenshot", "application_ui_screenshot", "screenshot"]:
        path = _resolve_artifact_path(entry.get(key), base_dir=base_dir)
        if path and path.exists() and path.is_file() and path.stat().st_size > 0:
            text = str(path)
            if text not in paths:
                paths.append(text)
    return paths


def _existing_screenshot_files(values: list[Any]) -> tuple[list[str], list[str]]:
    existing: list[str] = []
    missing_or_invalid: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        path = _resolve_artifact_path(text)
        if path and path.exists() and path.is_file() and path.stat().st_size > 0:
            resolved = str(path)
            if resolved not in existing:
                existing.append(resolved)
        elif text not in missing_or_invalid:
            missing_or_invalid.append(text)
    return existing, missing_or_invalid


def _manual_review_method_ok(entry: dict[str, Any]) -> bool:
    method = str(entry.get("review_mode") or entry.get("method") or "").lower()
    return "ui" in method and "screenshot" in method


def _manual_findings(entry: dict[str, Any]) -> list[str]:
    for key in ["findings", "visual_findings"]:
        value = entry.get(key)
        if isinstance(value, list):
            return [str(item) for item in value if str(item).strip()]
    return []


def _manual_visual_checklist(entry: dict[str, Any]) -> dict[str, Any]:
    value = entry.get("visual_checklist") or entry.get("ui_visual_checklist") or entry.get("checklist") or {}
    return dict(value) if isinstance(value, dict) else {}


def _manual_visual_checklist_notes(entry: dict[str, Any]) -> dict[str, str]:
    value = entry.get("visual_checklist_notes") or entry.get("ui_visual_checklist_notes") or {}
    if not isinstance(value, dict):
        return {}
    return {str(key): str(item) for key, item in value.items() if str(item).strip()}


def _ui_visual_review_status(
    *,
    latest_manual: dict[str, Any],
    manual_status: str,
    manual_pass: bool,
    screenshot_files: list[str],
    issues: list[dict[str, Any]],
) -> str:
    issue_keys = {str(item.get("key") or "") for item in issues}
    if "generated_png_source_evidence_not_current_run" in issue_keys:
        return "generated_png_source_invalid"
    if "application_ui_screenshot_source_report_invalid" in issue_keys:
        return "ui_screenshot_source_invalid"
    if "manual_visual_checklist_failed" in issue_keys:
        return "manual_visual_checklist_failed"
    if "manual_visual_checklist_missing_or_incomplete" in issue_keys:
        return "manual_visual_checklist_missing"
    if manual_pass and screenshot_files and _manual_review_method_ok(latest_manual):
        return "pass"
    if manual_status == "fail" or "application_ui_screenshot_review_not_passed" in issue_keys:
        return "visual_fail"
    if manual_status and not screenshot_files:
        return "ui_screenshot_missing"
    if "ui_visual_review_gate_missing" in issue_keys:
        return "ui_review_gate_missing"
    return "need_review"


def _missing_ui_acceptance_requirements(
    *,
    gate_entry: dict[str, Any],
    latest_manual: dict[str, Any],
    screenshot_files: list[str],
    screenshot_content_pass: bool,
    issues: list[dict[str, Any]],
) -> list[str]:
    missing: list[str] = []
    issue_keys = {str(item.get("key") or "") for item in issues}
    if not gate_entry:
        missing.append("acceptance_gate_entry")
    if "ui_visual_review_gate_missing" in issue_keys:
        missing.append("ui_visual_review_gate")
    if not screenshot_files:
        missing.append("application_ui_screenshot_file")
    if screenshot_files and not screenshot_content_pass:
        missing.append("application_ui_screenshot_content")
    if not _manual_review_method_ok(latest_manual):
        missing.append("application_ui_screenshot_review_method")
    if not bool(gate_entry.get("source_ui_report_application_ui_ok")):
        missing.append("application_ui_source_report")
    if not bool(gate_entry.get("manual_case_status_pass")):
        missing.append("manual_case_pass")
    if not bool(gate_entry.get("manual_visual_checklist_required")) or bool(gate_entry.get("manual_visual_checklist_missing_items")):
        missing.append("manual_visual_checklist")
    generated_png_required = bool(gate_entry.get("generated_png_source_required")) or bool(
        "generated_png_source_evidence_not_current_run" in issue_keys
    )
    if not gate_entry or (generated_png_required and not bool(gate_entry.get("generated_png_source_pass"))):
        missing.append("fresh_generated_png_source")
    return missing


def _strict_application_ui_gate_pass(
    *,
    gate_pass: bool,
    ui_visual_status: str,
    primary_proof_blocks: bool,
    missing_ui_requirements: list[str],
    gate_entry: dict[str, Any],
    screenshot_content_pass: bool,
) -> bool:
    if primary_proof_blocks:
        return False
    if not gate_pass or ui_visual_status != "pass" or missing_ui_requirements:
        return False
    if not bool(gate_entry.get("source_ui_report_application_ui_ok")):
        return False
    if not bool(gate_entry.get("manual_case_status_pass")):
        return False
    if not bool(gate_entry.get("manual_visual_checklist_required")):
        return False
    if not bool(gate_entry.get("manual_visual_checklist_pass")):
        return False
    if gate_entry.get("manual_visual_checklist_missing_items"):
        return False
    if gate_entry.get("manual_visual_checklist_failed_items"):
        return False
    if gate_entry.get("manual_visual_checklist_not_passed_items"):
        return False
    if not screenshot_content_pass:
        return False
    generated_png_required = bool(gate_entry.get("generated_png_source_required"))
    if generated_png_required and not bool(gate_entry.get("generated_png_source_pass")):
        return False
    return True


def _per_drawing_ui_review_matrix(base_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    matrix: list[dict[str, Any]] = []
    for item in base_results:
        latest_checklist = item.get("latest_manual_visual_checklist")
        if not isinstance(latest_checklist, dict):
            latest_checklist = {}
        failed_items = list(item.get("manual_visual_checklist_failed_items") or [])
        missing_items = list(item.get("manual_visual_checklist_missing_items") or [])
        not_passed_items = list(item.get("manual_visual_checklist_not_passed_items") or [])
        if not failed_items and latest_checklist:
            failed_items = [str(key) for key, value in latest_checklist.items() if value is False]
        if not not_passed_items and latest_checklist:
            not_passed_items = [str(key) for key, value in latest_checklist.items() if value is not True]
        manual_visual_judgement_pass = (
            bool(item.get("manual_case_status_pass"))
            and bool(item.get("manual_visual_checklist_required"))
            and bool(item.get("manual_visual_checklist_pass"))
            and not failed_items
            and not missing_items
            and not not_passed_items
        )
        matrix.append(
            {
                "base": str(item.get("base") or ""),
                "application_ui_screenshot_required": True,
                "application_ui_screenshot_present": bool(item.get("application_ui_screenshot_review_present")),
                "application_ui_screenshot_file_count": int(item.get("ui_screenshot_file_count") or 0),
                "application_ui_screenshot_content_check_pass": bool(
                    item.get("application_ui_screenshot_content_check_pass")
                ),
                "manual_visual_judgement_required": True,
                "manual_visual_judgement_present": bool(item.get("latest_manual_review")),
                "manual_visual_judgement_pass": manual_visual_judgement_pass,
                "manual_visual_checklist_required": True,
                "manual_visual_checklist_pass": bool(item.get("manual_visual_checklist_pass")),
                "manual_visual_checklist_failed_items": failed_items,
                "manual_visual_checklist_missing_items": missing_items,
                "manual_visual_checklist_not_passed_items": not_passed_items,
                "latest_manual_visual_checklist": latest_checklist,
                "latest_manual_visual_checklist_notes": item.get("latest_manual_visual_checklist_notes") or {},
                "latest_manual_findings": list(item.get("latest_manual_findings") or []),
                "latest_manual_required_correction": str(item.get("latest_manual_required_correction") or ""),
                "source_ui_report_application_ui_ok": bool(item.get("source_ui_report_application_ui_ok")),
                "ui_visual_review_status": str(item.get("ui_visual_review_status") or ""),
                "acceptance_status": str(item.get("acceptance_status") or ""),
                "acceptance_blocked_by_006": bool(item.get("acceptance_blocked_by_006")),
                "missing_ui_acceptance_requirements": list(item.get("missing_ui_acceptance_requirements") or []),
                "ui_screenshot_files": list(item.get("ui_screenshot_files") or []),
                "application_ui_screenshot_paths_existing_application_ui": list(
                    item.get("application_ui_screenshot_paths_existing_application_ui") or []
                ),
                "comparison_image": str(item.get("comparison_image") or ""),
                "generated_png": str(item.get("generated_png") or ""),
                "reference_png": str(item.get("reference_png") or ""),
                "final_judgement_source": "application_drawing_review_ui_screenshot_manual_visual_judgement",
                "api_is_not_final_judgement": True,
                "api_only_acceptance_allowed": False,
                "pass": bool(item.get("pass")),
            }
        )
    return matrix


def _base_status(
    *,
    base: str,
    acceptance_gate: dict[str, Any],
    primary_acceptance_proof: dict[str, Any],
    gate_entry: dict[str, Any],
    issues: list[dict[str, Any]],
    manual_entries: list[dict[str, Any]],
) -> dict[str, Any]:
    latest_manual = _latest_manual(manual_entries)
    manual_status = _manual_status(latest_manual)
    screenshot_files, invalid_gate_screenshot_files = _existing_screenshot_files(list(gate_entry.get("ui_screenshot_files") or []))
    for path in _manual_screenshot_files(latest_manual):
        if path not in screenshot_files:
            screenshot_files.append(path)
    screenshot_content = validate_application_ui_screenshots([Path(path) for path in screenshot_files])
    screenshot_content_pass = bool(screenshot_content.get("pass"))

    gate_pass = bool(gate_entry.get("pass"))
    manual_pass = bool(latest_manual.get("visual_acceptance_pass")) or manual_status in {"pass", "passed", "ok", "accepted"}
    ui_visual_status = _ui_visual_review_status(
        latest_manual=latest_manual,
        manual_status=manual_status,
        manual_pass=manual_pass,
        screenshot_files=screenshot_files,
        issues=issues,
    )
    missing_ui_requirements = _missing_ui_acceptance_requirements(
        gate_entry=gate_entry,
        latest_manual=latest_manual,
        screenshot_files=screenshot_files,
        screenshot_content_pass=screenshot_content_pass,
        issues=issues,
    )
    proof_present = bool(primary_acceptance_proof)
    proof_pass = bool(primary_acceptance_proof.get("pass")) if proof_present else False
    proof_blocking_keys = list(primary_acceptance_proof.get("blocking_issue_keys") or [])
    primary_proof_blocks = not proof_present or not proof_pass
    accepted = _strict_application_ui_gate_pass(
        gate_pass=gate_pass,
        ui_visual_status=ui_visual_status,
        primary_proof_blocks=primary_proof_blocks,
        missing_ui_requirements=missing_ui_requirements,
        gate_entry=gate_entry,
        screenshot_content_pass=screenshot_content_pass,
    )
    expansion_blocked = (
        (acceptance_gate.get("status") == "blocked_by_006" or primary_proof_blocks)
        and base != PRIMARY_BASE
    )
    if accepted:
        status = "pass"
    elif ui_visual_status == "visual_fail":
        status = "visual_fail"
    elif ui_visual_status in {
        "ui_screenshot_missing",
        "ui_review_gate_missing",
        "generated_png_source_invalid",
        "ui_screenshot_source_invalid",
        "manual_visual_checklist_missing",
        "manual_visual_checklist_failed",
    }:
        status = ui_visual_status
    elif expansion_blocked:
        status = "blocked_by_006"
    else:
        status = "need_review"
    acceptance_status = "pass" if accepted else ("blocked_by_006" if expansion_blocked else status)

    return {
        "base": base,
        "status": status,
        "acceptance_status": acceptance_status,
        "pass": accepted,
        "acceptance_blocked_by_006": expansion_blocked,
        "api_is_not_final_judgement": True,
        "api_only_acceptance_allowed": False,
        "ui_screenshot_review_is_final_gate": True,
        "ui_visual_review_status": ui_visual_status,
        "application_ui_screenshot_review_required": True,
        "application_ui_screenshot_review_present": bool(latest_manual and screenshot_files),
        "application_ui_screenshot_content_check_pass": screenshot_content_pass,
        "application_ui_screenshot_paths_existing_application_ui": list(screenshot_content.get("passing_paths") or []),
        "application_ui_screenshot_content_checks": list(screenshot_content.get("checks") or []),
        "application_ui_screenshot_review_method_ok": _manual_review_method_ok(latest_manual),
        "application_ui_screenshot_gate_pass": bool(accepted and not missing_ui_requirements),
        "missing_ui_acceptance_requirements": missing_ui_requirements,
        "source_ui_report": str(gate_entry.get("source_ui_report") or ""),
        "source_ui_report_schema": str(gate_entry.get("source_ui_report_schema") or ""),
        "source_ui_report_mode": str(gate_entry.get("source_ui_report_mode") or ""),
        "source_ui_report_application_ui_ok": bool(gate_entry.get("source_ui_report_application_ui_ok")),
        "manual_case_status_pass": bool(gate_entry.get("manual_case_status_pass")),
        "manual_visual_checklist_required": bool(gate_entry.get("manual_visual_checklist_required")),
        "manual_visual_checklist_pass": bool(gate_entry.get("manual_visual_checklist_pass")),
        "manual_visual_checklist_missing_items": list(gate_entry.get("manual_visual_checklist_missing_items") or []),
        "manual_visual_checklist_failed_items": list(gate_entry.get("manual_visual_checklist_failed_items") or []),
        "manual_visual_checklist_not_passed_items": list(gate_entry.get("manual_visual_checklist_not_passed_items") or []),
        "generated_png_source_required": bool(gate_entry.get("generated_png_source_required")),
        "generated_png_source_pass": bool(gate_entry.get("generated_png_source_pass")),
        "generated_png_source_evidence": gate_entry.get("generated_png_source_evidence") or {},
        "acceptance_gate_entry_present": bool(gate_entry),
        "acceptance_gate_pass": gate_pass,
        "primary_acceptance_proof_present": proof_present,
        "primary_acceptance_proof_status": str(primary_acceptance_proof.get("status") or ""),
        "primary_acceptance_proof_pass": proof_pass,
        "primary_acceptance_proof_blocking_issue_keys": proof_blocking_keys,
        "vision_qc_v6_visual_acceptance_pass": bool(gate_entry.get("vision_qc_v6_visual_acceptance_pass")),
        "reference_compare_v4_pass": bool(gate_entry.get("reference_compare_v4_pass")),
        "manual_review_count": len(manual_entries),
        "latest_manual_review": str(latest_manual.get("manual_review") or ""),
        "latest_manual_status": manual_status,
        "latest_manual_visual_acceptance_pass": manual_pass,
        "latest_manual_findings": _manual_findings(latest_manual),
        "latest_manual_visual_checklist": _manual_visual_checklist(latest_manual),
        "latest_manual_visual_checklist_notes": _manual_visual_checklist_notes(latest_manual),
        "latest_manual_required_correction": str(latest_manual.get("required_correction") or latest_manual.get("required_next_action") or ""),
        "comparison_image": str(latest_manual.get("comparison_image") or latest_manual.get("comparison_png") or ""),
        "generated_png": str(latest_manual.get("generated_png") or ""),
        "reference_png": str(latest_manual.get("reference_png") or ""),
        "ui_screenshot_file_count": len(screenshot_files),
        "ui_screenshot_files": screenshot_files,
        "invalid_or_missing_gate_ui_screenshot_files": invalid_gate_screenshot_files,
        "issue_keys": sorted({str(item.get("key")) for item in issues if item.get("key")}),
        "reasons": list(gate_entry.get("reasons") or []),
        "next_action": _next_action(base, status),
    }


def _next_action(base: str, status: str) -> str:
    if base == PRIMARY_BASE:
        return (
            "Repair 006 first: preserve at least 12 real DisplayDim annotations through SaveAs/Reopen/post-layout, "
            "then rerun locked CAD and application Drawing Review UI judgement."
        )
    if status == "blocked_by_006":
        return "Do not accept this drawing yet; wait until LB26001-A-04-006 passes the UI-backed gate."
    return "After 006 passes, regenerate this drawing and capture application Drawing Review UI screenshots."


def build_requested_drawings_status(
    *,
    acceptance_gate_path: Path = DEFAULT_ACCEPTANCE_GATE,
    acceptance_proof_path: Path = DEFAULT_ACCEPTANCE_PROOF,
    readiness_path: Path = DEFAULT_READINESS,
    manual_review_paths: list[Path] | None = None,
    out_path: Path | None = None,
) -> dict[str, Any]:
    latest_gate = _latest_locked_real_rerun_acceptance_gate()
    if latest_gate is not None and _same_path(acceptance_gate_path, DEFAULT_ACCEPTANCE_GATE):
        acceptance_gate_path = latest_gate

    manual_paths = manual_review_paths if manual_review_paths is not None else _default_manual_review_paths()
    acceptance_gate = _read_json(acceptance_gate_path)
    acceptance_proof = _read_json(acceptance_proof_path)
    readiness = _read_json(readiness_path)
    gate_entries = _acceptance_entry_map(acceptance_gate)
    issues_by_base = _issue_map(acceptance_gate)
    manuals = _manual_review_entries(manual_paths)

    bases = list(REQUESTED_BASES)
    base_results = [
        _base_status(
            base=base,
            acceptance_gate=acceptance_gate,
            primary_acceptance_proof=acceptance_proof,
            gate_entry=gate_entries.get(base) or {},
            issues=issues_by_base.get(base) or [],
            manual_entries=manuals.get(base) or [],
        )
        for base in bases
    ]
    per_drawing_ui_review_matrix = _per_drawing_ui_review_matrix(base_results)
    pass_count = sum(1 for item in base_results if item.get("pass"))
    per_drawing_ui_acceptance_pass_count = sum(1 for item in per_drawing_ui_review_matrix if item.get("pass"))
    drawings_missing_application_ui_screenshot = [
        str(item.get("base"))
        for item in per_drawing_ui_review_matrix
        if not item.get("application_ui_screenshot_present")
    ]
    drawings_missing_manual_visual_judgement = [
        str(item.get("base"))
        for item in per_drawing_ui_review_matrix
        if not item.get("manual_visual_judgement_present")
    ]
    drawings_with_visual_failure = [
        str(item.get("base"))
        for item in per_drawing_ui_review_matrix
        if str(item.get("ui_visual_review_status") or "") in {"visual_fail", "manual_visual_checklist_failed"}
    ]
    drawings_with_incomplete_ui_review = [
        str(item.get("base")) for item in per_drawing_ui_review_matrix if not item.get("pass")
    ]
    primary_proof_present = bool(acceptance_proof)
    primary_proof_blocks = not primary_proof_present or not acceptance_proof.get("pass")
    if pass_count == len(bases) and not primary_proof_blocks:
        status = "pass"
    elif acceptance_gate.get("status") == "blocked_by_006" or primary_proof_blocks:
        status = "blocked_by_006"
    else:
        status = "need_review"
    payload = {
        "schema": "sw_drawing_studio.lb26001_requested_drawings_status.v4_2",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "requested_bases": bases,
        "acceptance_gate": str(acceptance_gate_path),
        "acceptance_gate_status": acceptance_gate.get("status", "missing"),
        "primary_acceptance_proof": str(acceptance_proof_path),
        "primary_acceptance_proof_present": primary_proof_present,
        "primary_acceptance_proof_status": acceptance_proof.get("status", "missing"),
        "primary_acceptance_proof_pass": bool(acceptance_proof.get("pass")) if acceptance_proof else False,
        "primary_acceptance_proof_blocking_issue_keys": list(acceptance_proof.get("blocking_issue_keys") or []),
        "readiness_report": str(readiness_path),
        "readiness_status": readiness.get("status", "missing"),
        "readiness_blocking_issue_keys": list(readiness.get("blocking_issue_keys") or []),
        "manual_reviews": [str(path) for path in manual_paths],
        "status": status,
        "pass": status == "pass",
        "pass_count": pass_count,
        "not_pass_count": len(bases) - pass_count,
        "all_generated_drawings_currently_unqualified": pass_count == 0,
        "api_is_not_final_judgement": True,
        "ui_screenshot_review_is_final_gate": True,
        "per_drawing_application_ui_screenshot_required": True,
        "final_judgement_requires_application_ui_per_drawing": True,
        "final_judgement_source": "application_drawing_review_ui_screenshot_manual_visual_judgement",
        "per_drawing_ui_review_matrix": per_drawing_ui_review_matrix,
        "per_drawing_ui_acceptance_pass_count": per_drawing_ui_acceptance_pass_count,
        "per_drawing_ui_review_incomplete_count": len(drawings_with_incomplete_ui_review),
        "drawings_missing_application_ui_screenshot": drawings_missing_application_ui_screenshot,
        "drawings_missing_manual_visual_judgement": drawings_missing_manual_visual_judgement,
        "drawings_with_visual_failure": drawings_with_visual_failure,
        "drawings_with_incomplete_ui_review": drawings_with_incomplete_ui_review,
        "base_results": base_results,
        "next_actions": [
            "Recover SolidWorks safely before any real CAD rerun; current readiness must be ready.",
            "Run only LB26001-A-04-006 first and require a passing UI-backed 006 acceptance proof.",
            "For each requested drawing, clear missing_ui_acceptance_requirements with fresh application UI screenshots and a complete manual checklist.",
            "Treat 007/008/009/015/022 as blocked from acceptance until 006 passes.",
        ],
    }
    if out_path is not None:
        _write_json(out_path, payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize requested LB26001 drawing acceptance status.")
    parser.add_argument("--acceptance-gate", default=str(DEFAULT_ACCEPTANCE_GATE))
    parser.add_argument("--acceptance-proof", default=str(DEFAULT_ACCEPTANCE_PROOF))
    parser.add_argument("--readiness", default=str(DEFAULT_READINESS))
    parser.add_argument("--manual-review", action="append", default=[])
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    manual_paths = [_repo_path(path) for path in args.manual_review] if args.manual_review else None
    out = _repo_path(args.out)
    payload = build_requested_drawings_status(
        acceptance_gate_path=_repo_path(args.acceptance_gate),
        acceptance_proof_path=_repo_path(args.acceptance_proof),
        readiness_path=_repo_path(args.readiness),
        manual_review_paths=manual_paths,
        out_path=out,
    )
    print(json.dumps({
        "pass": payload.get("pass"),
        "status": payload.get("status"),
        "pass_count": payload.get("pass_count"),
        "not_pass_count": payload.get("not_pass_count"),
        "report": str(out),
    }, ensure_ascii=False))
    return 0 if payload.get("pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
