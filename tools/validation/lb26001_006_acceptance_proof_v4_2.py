"""Build the LB26001-A-04-006 UI-backed acceptance proof.

This tool is file-only. It combines staged CAD evidence, application Drawing
Review UI closure evidence, and the LB26001 acceptance gate into a single
human-readable proof packet. It never calls SolidWorks or COM.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


BASE = "LB26001-A-04-006"
DEFAULT_STAGED_SUMMARY = (
    REPO_ROOT
    / "drw_output"
    / "staged_validation"
    / "LB26001_006_explicit_displaydim_visible_entities_20260623"
    / "summary.json"
)
DEFAULT_UI_GATE = (
    REPO_ROOT
    / "drw_output"
    / "ui_acceptance"
    / "LB26001_006_explicit_displaydim_visible_entities_visual_review_20260623"
    / "closed_loop_strict_final_20260624"
    / "ui_visual_review_gate_summary.json"
)
DEFAULT_SCREENSHOT_BINDING_GATE = (
    REPO_ROOT
    / "drw_output"
    / "ui_acceptance"
    / "LB26001_006_explicit_displaydim_visible_entities_visual_review_20260623"
    / "closed_loop_manual_screenshot_bind_20260624"
    / "ui_visual_review_gate_summary.json"
)
DEFAULT_ACCEPTANCE_GATE = (
    REPO_ROOT
    / "drw_output"
    / "ui_acceptance"
    / "LB26001_006_explicit_displaydim_visible_entities_visual_review_20260623"
    / "closed_loop_strict_final_20260624"
    / "lb26001_acceptance_gate_v4_2.json"
)
DEFAULT_SUPPLEMENTAL_CHECKLIST_GATE = (
    REPO_ROOT
    / "drw_output"
    / "ui_acceptance"
    / "LB26001_006_explicit_displaydim_visible_entities_visual_review_20260623"
    / "closed_loop_codex_v4_2_checklist_20260624"
    / "lb26001_acceptance_gate_v4_2.json"
)
DEFAULT_DIRECT_UI_SCREENSHOT_RECHECK = (
    REPO_ROOT
    / "drw_output"
    / "ui_acceptance"
    / "LB26001_ref6_visual_review_manual_20260623"
    / "codex_direct_ui_screenshot_recheck_20260624.json"
)
DEFAULT_OUT_JSON = REPO_ROOT / "drw_output" / "diagnostics" / "lb26001_006_acceptance_proof_v4_2.json"
DEFAULT_OUT_MD = REPO_ROOT / "drw_output" / "diagnostics" / "lb26001_006_acceptance_proof_v4_2.md"


def _same_path(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except Exception:
        return str(left).lower() == str(right).lower()


def _latest_locked_real_rerun_artifacts() -> dict[str, Path]:
    staged_root = REPO_ROOT / "drw_output" / "staged_validation"
    ui_root = REPO_ROOT / "drw_output" / "ui_acceptance"
    candidates: list[tuple[float, dict[str, Path]]] = []
    for summary_path in staged_root.glob("LB26001_006_locked_real_rerun_*/summary.json"):
        summary = _read_json(summary_path)
        if str(summary.get("stage") or "") != "LB26001_006":
            continue
        if int(summary.get("processed") or 0) < 1:
            continue
        review_dir = ui_root / f"{summary_path.parent.name}_visual_review"
        closed_loop = review_dir / "closed_loop"
        ui_gate = closed_loop / "ui_visual_review_gate_summary.json"
        acceptance_gate = closed_loop / "lb26001_acceptance_gate_v4_2.json"
        manual_review = review_dir / "manual_visual_judgement.json"
        if not (ui_gate.exists() and acceptance_gate.exists() and manual_review.exists()):
            continue
        try:
            mtime = max(
                summary_path.stat().st_mtime,
                ui_gate.stat().st_mtime,
                acceptance_gate.stat().st_mtime,
                manual_review.stat().st_mtime,
            )
        except Exception:
            mtime = 0.0
        candidates.append(
            (
                mtime,
                {
                    "staged_summary": summary_path,
                    "ui_gate": ui_gate,
                    "screenshot_binding_gate": ui_gate,
                    "acceptance_gate": acceptance_gate,
                    "supplemental_checklist_gate": acceptance_gate,
                    "direct_ui_screenshot_recheck": manual_review,
                },
            )
        )
    if not candidates:
        return {}
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


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


def _existing_json_candidates(paths: list[Path]) -> list[Path]:
    result: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        if not path.exists() or not path.is_file() or path.suffix.lower() != ".json":
            continue
        try:
            key = str(path.resolve()).casefold()
        except Exception:
            key = str(path).casefold()
        if key not in seen:
            seen.add(key)
            result.append(path)
    return result


def _canonical_path(value: Any, *, base_dir: Path | None = None) -> str:
    path = _resolve_artifact_path(value, base_dir=base_dir)
    if not path:
        return ""
    try:
        return str(path.resolve()).casefold()
    except Exception:
        return str(path).casefold()


def _find_staged_case(summary: dict[str, Any], base: str) -> dict[str, Any]:
    for item in summary.get("cases") or []:
        if not isinstance(item, dict):
            continue
        item_base = str(item.get("part_name") or Path(str(item.get("part") or "")).stem or "").strip()
        if item_base == base:
            return item
    return {}


def _find_gate_entry(gate: dict[str, Any], base: str) -> dict[str, Any]:
    for item in gate.get("entries") or []:
        if isinstance(item, dict) and str(item.get("base") or "").strip() == base:
            return item
    return {}


def _find_acceptance_base_result(gate: dict[str, Any], base: str) -> dict[str, Any]:
    for item in gate.get("base_results") or []:
        if isinstance(item, dict) and str(item.get("base") or "").strip() == base:
            return item
    return {}


def _find_direct_recheck_case(payload: dict[str, Any], base: str) -> dict[str, Any]:
    for container in ["cases", "entries"]:
        for item in payload.get(container) or []:
            if isinstance(item, dict) and str(item.get("base") or "").strip() == base:
                return item
    return {}


def _direct_recheck_candidate_paths(
    default_path: Path,
    acceptance_base: dict[str, Any],
    supplemental_base: dict[str, Any],
) -> list[Path]:
    candidates: list[Path] = [default_path]
    screenshot_values = _merged_text_list(
        acceptance_base.get("ui_screenshot_files"),
        supplemental_base.get("ui_screenshot_files"),
    )
    for value in screenshot_values:
        screenshot = _resolve_artifact_path(value)
        if not screenshot:
            continue
        ui_dir = screenshot.parent.parent
        candidates.extend(sorted(ui_dir.glob("manual_visual_judgement*.json")))
        candidates.extend(sorted(ui_dir.glob("codex_direct_ui_screenshot_recheck*.json")))
    return _existing_json_candidates(candidates)


def _direct_recheck_gate_base(
    acceptance_base: dict[str, Any],
    supplemental_base: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(acceptance_base)
    merged["ui_screenshot_files"] = _merged_text_list(
        acceptance_base.get("ui_screenshot_files"),
        supplemental_base.get("ui_screenshot_files"),
    )
    return merged


def _select_direct_recheck_path(
    requested_path: Path | None,
    acceptance_base: dict[str, Any],
    supplemental_base: dict[str, Any],
) -> Path:
    default_path = requested_path or DEFAULT_DIRECT_UI_SCREENSHOT_RECHECK
    gate_base = _direct_recheck_gate_base(acceptance_base, supplemental_base)
    best_path: Path | None = None
    best_mtime = -1.0
    for candidate in _direct_recheck_candidate_paths(default_path, acceptance_base, supplemental_base):
        payload = _read_json(candidate)
        entry = _find_direct_recheck_case(payload, BASE)
        evidence = _direct_ui_screenshot_recheck_evidence(candidate, payload, entry, gate_base)
        if evidence.get("direct_ui_screenshot_recheck_current"):
            try:
                mtime = candidate.stat().st_mtime
            except Exception:
                mtime = 0.0
            if mtime >= best_mtime:
                best_path = candidate
                best_mtime = mtime
    return best_path or default_path


def _tri_bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _first_bool(*values: Any) -> bool | None:
    for value in values:
        parsed = _tri_bool(value)
        if parsed is not None:
            return parsed
    return None


def _bool_or_false(value: Any) -> bool:
    return bool(value) if value is not None else False


def _any_true(*values: Any) -> bool:
    return any(_tri_bool(value) is True for value in values)


def _first_text(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _merged_text_list(*values: Any) -> list[str]:
    merged: list[str] = []
    for value in values:
        items = value if isinstance(value, list) else []
        for item in items:
            text = str(item or "").strip()
            if text and text not in merged:
                merged.append(text)
    return merged


def _first_non_empty_dict(*values: Any) -> dict[str, Any]:
    for value in values:
        if isinstance(value, dict) and value:
            return value
    return {}


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def _status_pass(value: Any) -> bool:
    return str(value or "").strip().lower() in {"pass", "passed", "ok", "accepted"}


def _direct_ui_screenshot_recheck_evidence(
    path: Path,
    payload: dict[str, Any],
    entry: dict[str, Any],
    acceptance_base: dict[str, Any],
) -> dict[str, Any]:
    base_dir = path.parent
    method = str(payload.get("review_method") or payload.get("review_mode") or payload.get("method") or "").lower()
    method_ok = "ui" in method and "screenshot" in method
    screenshot_value = entry.get("screenshot") or entry.get("ui_screenshot") or entry.get("application_ui_screenshot")
    screenshot_path = _resolve_artifact_path(screenshot_value, base_dir=base_dir)
    screenshot_exists = bool(screenshot_path and screenshot_path.exists() and screenshot_path.is_file() and screenshot_path.stat().st_size > 0)
    gate_screenshots = [
        _canonical_path(item)
        for item in acceptance_base.get("ui_screenshot_files") or []
        if str(item or "").strip()
    ]
    screenshot_canonical = _canonical_path(screenshot_value, base_dir=base_dir)
    screenshot_matches_gate = bool(screenshot_canonical and screenshot_canonical in gate_screenshots)
    current = bool(path.exists() and entry and screenshot_exists and screenshot_matches_gate)
    entry_status = str(entry.get("status") or entry.get("manual_status") or entry.get("verdict") or payload.get("overall_status") or payload.get("status") or "")
    overall_status = str(payload.get("overall_status") or payload.get("status") or "")
    direct_pass = bool(
        current
        and method_ok
        and _status_pass(entry_status)
        and (_status_pass(overall_status) or not overall_status)
    )
    findings = entry.get("visual_findings") or entry.get("findings") or []
    return {
        "direct_ui_screenshot_recheck": str(path),
        "direct_ui_screenshot_recheck_exists": path.exists(),
        "direct_ui_screenshot_recheck_entry_present": bool(entry),
        "direct_ui_screenshot_recheck_current": current,
        "direct_ui_screenshot_recheck_method": method,
        "direct_ui_screenshot_recheck_method_ok": method_ok,
        "direct_ui_screenshot_recheck_status": entry_status.lower(),
        "direct_ui_screenshot_recheck_overall_status": overall_status.lower(),
        "direct_ui_screenshot_recheck_pass": direct_pass if current else None,
        "direct_ui_screenshot_recheck_screenshot": str(screenshot_path or ""),
        "direct_ui_screenshot_recheck_screenshot_exists": screenshot_exists,
        "direct_ui_screenshot_recheck_screenshot_matches_gate": screenshot_matches_gate,
        "direct_ui_screenshot_recheck_findings": [str(item) for item in findings if str(item).strip()],
    }


def _staged_evidence(summary_path: Path, summary: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    case_present = bool(case)
    case_dir_path = _resolve_artifact_path(case.get("case_dir"), base_dir=summary_path.parent)
    lifecycle_report_value = case.get("displaydim_lifecycle_report")
    if not lifecycle_report_value and case_dir_path:
        lifecycle_report_value = str(case_dir_path / "displaydim_lifecycle_audit.json")
    lifecycle_report_path = _resolve_artifact_path(
        lifecycle_report_value,
        base_dir=case_dir_path or summary_path.parent,
    )
    lifecycle_report = _read_json(lifecycle_report_path) if lifecycle_report_path else {}
    lifecycle_required = _first_bool(case.get("displaydim_lifecycle_required"))
    if lifecycle_required is None:
        lifecycle_required = case_present and str(case.get("part_name") or "") == BASE
    lifecycle_report_exists = bool(
        lifecycle_report_path
        and lifecycle_report_path.exists()
        and lifecycle_report_path.is_file()
        and lifecycle_report_path.stat().st_size > 0
    )
    lifecycle_case_pass = _first_bool(case.get("displaydim_lifecycle_pass"))
    lifecycle_report_pass = _first_bool(lifecycle_report.get("pass"))
    lifecycle_pass = True
    if lifecycle_required:
        lifecycle_pass = bool(lifecycle_case_pass is True and lifecycle_report_exists and lifecycle_report_pass is True)
    lifecycle_blockers = _unique(
        [str(item) for item in case.get("displaydim_lifecycle_blocking_issue_keys") or []]
        + [str(item) for item in lifecycle_report.get("blocking_issue_keys") or []]
    )
    fields = {
        "cad_pass": bool(case.get("cad_pass")),
        "dimension_pass": bool(case.get("dimension_pass")),
        "reference_pass": bool(case.get("reference_pass")),
        "reference_style_pass": bool(case.get("reference_style_pass")),
        "displaydim_lifecycle_pass": bool(lifecycle_pass),
        "vision_qc_v6_pass": bool(case.get("vision_qc_v6_pass")),
        "reference_compare_v4_pass": bool(case.get("reference_compare_v4_pass")),
        "deliverable": bool(case.get("deliverable")),
    }
    return {
        "staged_summary": str(summary_path),
        "staged_summary_exists": summary_path.exists(),
        "staged_status": str(summary.get("status") or "missing"),
        "staged_pass": bool(summary.get("pass")),
        "staged_stage": str(summary.get("stage") or ""),
        "staged_processed": int(summary.get("processed") or 0),
        "staged_total": int(summary.get("total") or 0),
        "case_present": case_present,
        "case_status": str(case.get("status") or ""),
        "case_dir": str(case.get("case_dir") or ""),
        "run_dir": str(case.get("run_dir") or ""),
        "displaydim_lifecycle_required": bool(lifecycle_required),
        "displaydim_lifecycle_report": str(lifecycle_report_path or ""),
        "displaydim_lifecycle_report_exists": lifecycle_report_exists,
        "displaydim_lifecycle_report_status": str(lifecycle_report.get("status") or case.get("displaydim_lifecycle_status") or ""),
        "displaydim_lifecycle_case_pass": _bool_or_false(lifecycle_case_pass),
        "displaydim_lifecycle_report_pass": _bool_or_false(lifecycle_report_pass),
        "displaydim_lifecycle_blocking_issue_keys": lifecycle_blockers,
        **fields,
        "case_quality_pass": bool(case_present and all(fields.values())),
    }


def _ui_evidence(
    *,
    ui_gate_path: Path,
    ui_gate: dict[str, Any],
    ui_entry: dict[str, Any],
    screenshot_gate_path: Path,
    screenshot_gate: dict[str, Any],
    screenshot_entry: dict[str, Any],
    acceptance_base: dict[str, Any],
    supplemental_checklist_gate_path: Path,
    supplemental_checklist_gate: dict[str, Any],
    supplemental_checklist_base: dict[str, Any],
    direct_recheck_path: Path,
    direct_recheck: dict[str, Any],
    direct_recheck_entry: dict[str, Any],
) -> dict[str, Any]:
    ui_report_entry_pass = _first_bool(
        screenshot_entry.get("ui_report_entry_pass"),
        ui_entry.get("ui_report_entry_pass"),
    )
    if ui_report_entry_pass is None:
        ui_report_entry_pass = bool(
            acceptance_base.get("source_ui_report_application_ui_ok")
            and int(acceptance_base.get("ui_screenshot_file_count") or 0) > 0
        )

    manual_binding_pass = _first_bool(
        screenshot_entry.get("manual_review_entry_screenshot_pass"),
        ui_entry.get("manual_review_entry_screenshot_pass"),
    )
    manual_screenshot_match = _first_bool(
        screenshot_entry.get("manual_review_screenshot_matches_ui_report_entry"),
        ui_entry.get("manual_review_screenshot_matches_ui_report_entry"),
    )
    ui_entries_all_pass = _first_bool(
        screenshot_gate.get("ui_report_entries_all_pass"),
        ui_gate.get("ui_report_entries_all_pass"),
        ui_report_entry_pass,
    )
    manual_entries_all_pass = _first_bool(
        screenshot_gate.get("manual_review_entries_all_pass"),
        ui_gate.get("manual_review_entries_all_pass"),
        manual_binding_pass,
    )
    v6_pass = _first_bool(
        ui_entry.get("vision_qc_v6_visual_acceptance_pass"),
        ui_gate.get("vision_qc_v6_all_pass"),
        acceptance_base.get("vision_qc_v6_visual_acceptance_pass"),
    )
    v4_pass = _first_bool(
        ui_entry.get("reference_compare_v4_pass"),
        ui_gate.get("reference_compare_v4_all_pass"),
        acceptance_base.get("reference_compare_v4_pass"),
    )
    generated_png_required = bool(
        ui_entry.get("generated_png_source_required")
        or screenshot_entry.get("generated_png_source_required")
        or supplemental_checklist_base.get("generated_png_source_required")
        or acceptance_base.get("generated_png_source_required")
    )
    generated_png_pass = _first_bool(
        supplemental_checklist_base.get("generated_png_source_pass"),
        screenshot_entry.get("generated_png_source_pass"),
        ui_entry.get("generated_png_source_pass"),
        acceptance_base.get("generated_png_source_pass"),
    )
    reasons = _merged_text_list(
        ui_entry.get("reasons"),
        screenshot_entry.get("reasons"),
        supplemental_checklist_base.get("reasons"),
        acceptance_base.get("reasons"),
    )
    direct_evidence = _direct_ui_screenshot_recheck_evidence(
        direct_recheck_path,
        direct_recheck,
        direct_recheck_entry,
        _direct_recheck_gate_base(acceptance_base, supplemental_checklist_base),
    )
    manual_case_status_pass = _first_bool(
        supplemental_checklist_base.get("manual_case_status_pass"),
        acceptance_base.get("manual_case_status_pass"),
    )
    manual_checklist_required = _first_bool(
        supplemental_checklist_base.get("manual_visual_checklist_required"),
        acceptance_base.get("manual_visual_checklist_required"),
    )
    manual_checklist_pass = _first_bool(
        supplemental_checklist_base.get("manual_visual_checklist_pass"),
        acceptance_base.get("manual_visual_checklist_pass"),
    )
    ui_screenshot_files = _merged_text_list(
        acceptance_base.get("ui_screenshot_files"),
        supplemental_checklist_base.get("ui_screenshot_files"),
    )
    return {
        "ui_gate": str(ui_gate_path),
        "ui_gate_exists": ui_gate_path.exists(),
        "ui_gate_status": str(ui_gate.get("status") or "missing"),
        "ui_gate_pass": bool(ui_gate.get("pass")),
        "ui_gate_entry_present": bool(ui_entry),
        "ui_report_entries_all_pass": _bool_or_false(ui_entries_all_pass),
        "manual_review_entries_all_pass": _bool_or_false(manual_entries_all_pass),
        "vision_qc_v6_all_pass": bool(ui_gate.get("vision_qc_v6_all_pass")),
        "reference_compare_v4_all_pass": bool(ui_gate.get("reference_compare_v4_all_pass")),
        "screenshot_binding_gate": str(screenshot_gate_path),
        "screenshot_binding_gate_exists": screenshot_gate_path.exists(),
        "screenshot_binding_entry_present": bool(screenshot_entry),
        "supplemental_checklist_gate": str(supplemental_checklist_gate_path),
        "supplemental_checklist_gate_exists": supplemental_checklist_gate_path.exists(),
        "supplemental_checklist_gate_status": str(supplemental_checklist_gate.get("status") or "missing"),
        "supplemental_checklist_base_result_present": bool(supplemental_checklist_base),
        "ui_report_entry_pass": bool(ui_report_entry_pass),
        "manual_review_entry_screenshot_pass": bool(manual_binding_pass),
        "manual_review_screenshot_matches_ui_report_entry": bool(manual_screenshot_match),
        "vision_qc_v6_visual_acceptance_pass": _bool_or_false(v6_pass),
        "reference_compare_v4_pass": _bool_or_false(v4_pass),
        "generated_png_source_required": generated_png_required,
        "generated_png_source_pass": (not generated_png_required) or _bool_or_false(generated_png_pass),
        "generated_png_source_evidence": _first_non_empty_dict(
            supplemental_checklist_base.get("generated_png_source_evidence"),
            screenshot_entry.get("generated_png_source_evidence"),
            acceptance_base.get("generated_png_source_evidence"),
            ui_entry.get("generated_png_source_evidence"),
        ),
        "ui_screenshot_file_count": max(
            int(acceptance_base.get("ui_screenshot_file_count") or 0),
            int(supplemental_checklist_base.get("ui_screenshot_file_count") or 0),
            len(ui_screenshot_files),
        ),
        "ui_screenshot_files": ui_screenshot_files,
        "source_ui_report": _first_text(
            supplemental_checklist_base.get("source_ui_report"),
            acceptance_base.get("source_ui_report"),
        ),
        "source_ui_report_application_ui_ok": _any_true(
            supplemental_checklist_base.get("source_ui_report_application_ui_ok"),
            acceptance_base.get("source_ui_report_application_ui_ok"),
            screenshot_entry.get("ui_report_application_ui_ok"),
            ui_entry.get("ui_report_application_ui_ok"),
        ),
        "manual_case_status_pass": _bool_or_false(manual_case_status_pass),
        "manual_visual_checklist_required": _bool_or_false(manual_checklist_required),
        "manual_visual_checklist_pass": _bool_or_false(manual_checklist_pass),
        "manual_visual_checklist_missing_items": _merged_text_list(
            supplemental_checklist_base.get("manual_visual_checklist_missing_items"),
            acceptance_base.get("manual_visual_checklist_missing_items"),
        ),
        "manual_visual_checklist_failed_items": _merged_text_list(
            supplemental_checklist_base.get("manual_visual_checklist_failed_items"),
            acceptance_base.get("manual_visual_checklist_failed_items"),
        ),
        "manual_visual_checklist_not_passed_items": _merged_text_list(
            supplemental_checklist_base.get("manual_visual_checklist_not_passed_items"),
            acceptance_base.get("manual_visual_checklist_not_passed_items"),
        ),
        "reasons": reasons,
        **direct_evidence,
    }


def _acceptance_evidence(path: Path, gate: dict[str, Any], base_result: dict[str, Any]) -> dict[str, Any]:
    primary_pass = bool(gate.get("primary_pass") or base_result.get("pass"))
    return {
        "acceptance_gate": str(path),
        "acceptance_gate_exists": path.exists(),
        "acceptance_gate_status": str(gate.get("status") or "missing"),
        "acceptance_gate_pass": bool(gate.get("pass")),
        "acceptance_primary_pass": primary_pass,
        "acceptance_base_result_present": bool(base_result),
        "acceptance_base_result_pass": bool(base_result.get("pass")),
        "acceptance_reasons": list(gate.get("reasons") or []),
        "acceptance_issue_count": len(gate.get("issues") or []),
    }


def _blocking_issue_keys(
    *,
    staged: dict[str, Any],
    ui: dict[str, Any],
    acceptance: dict[str, Any],
) -> list[str]:
    keys: list[str] = []
    if not staged["staged_summary_exists"]:
        keys.append("staged_summary_missing")
    if not staged["case_present"]:
        keys.append("staged_case_missing")
    if staged["case_present"] and not staged["deliverable"]:
        keys.append("staged_case_not_deliverable")
    if staged["case_present"] and not staged["reference_style_pass"]:
        keys.append("staged_reference_style_not_pass")
    if staged["case_present"] and staged.get("displaydim_lifecycle_required") and not staged.get("displaydim_lifecycle_report_exists"):
        keys.append("displaydim_lifecycle_report_missing")
    if staged["case_present"] and staged.get("displaydim_lifecycle_required") and not staged.get("displaydim_lifecycle_pass"):
        keys.append("displaydim_lifecycle_not_pass")
    if staged["case_present"] and not staged["vision_qc_v6_pass"]:
        keys.append("staged_vision_qc_v6_not_pass")
    if staged["case_present"] and not staged["reference_compare_v4_pass"]:
        keys.append("staged_reference_compare_v4_not_pass")
    if not ui["ui_gate_exists"]:
        keys.append("ui_gate_missing")
    if not ui["ui_gate_pass"]:
        keys.append("ui_gate_not_pass")
    if not ui["ui_gate_entry_present"]:
        keys.append("ui_gate_entry_missing")
    if not ui["ui_report_entry_pass"]:
        keys.append("ui_report_entry_not_pass")
    if int(ui.get("ui_screenshot_file_count") or 0) <= 0:
        keys.append("ui_screenshot_file_missing")
    if not ui["source_ui_report_application_ui_ok"]:
        keys.append("application_ui_source_report_invalid")
    if not ui["screenshot_binding_entry_present"]:
        keys.append("manual_review_screenshot_binding_entry_missing")
    if not ui["manual_review_entry_screenshot_pass"]:
        keys.append("manual_review_screenshot_not_bound")
    if ui.get("direct_ui_screenshot_recheck_current") and not ui.get("direct_ui_screenshot_recheck_method_ok"):
        keys.append("direct_ui_screenshot_recheck_method_invalid")
    elif ui.get("direct_ui_screenshot_recheck_current") and ui.get("direct_ui_screenshot_recheck_pass") is not True:
        keys.append("direct_ui_screenshot_recheck_not_pass")
    if not ui["manual_case_status_pass"]:
        keys.append("manual_visual_case_not_pass")
    if not ui["manual_visual_checklist_required"]:
        keys.append("manual_visual_checklist_missing")
    elif (
        not ui["manual_visual_checklist_pass"]
        or ui.get("manual_visual_checklist_missing_items")
        or ui.get("manual_visual_checklist_failed_items")
        or ui.get("manual_visual_checklist_not_passed_items")
    ):
        keys.append("manual_visual_checklist_not_pass")
    if not ui["vision_qc_v6_visual_acceptance_pass"]:
        keys.append("v6_with_ui_not_pass")
    if not ui["reference_compare_v4_pass"]:
        keys.append("reference_compare_v4_with_ui_not_pass")
    if ui["generated_png_source_required"] and not ui["generated_png_source_pass"]:
        keys.append("generated_png_source_not_current_run")
    if not acceptance["acceptance_gate_exists"]:
        keys.append("acceptance_gate_missing")
    if not acceptance["acceptance_base_result_present"]:
        keys.append("acceptance_base_result_missing")
    if not acceptance["acceptance_primary_pass"]:
        keys.append("acceptance_gate_not_pass")
    return _unique(keys)


def _next_actions(keys: list[str]) -> list[str]:
    actions: list[str] = []
    if any(key.startswith("staged_") for key in keys):
        actions.append(
            "After SolidWorks readiness clears, run exactly one locked LB26001-A-04-006 CAD rerun and require final DisplayDim >= 12 with proven post_layout_final target coverage."
        )
    if "displaydim_lifecycle_report_missing" in keys or "displaydim_lifecycle_not_pass" in keys:
        actions.append(
            "Refresh the 006 DisplayDim lifecycle audit from the fresh staged case and require the report itself to pass, not only staged summary fields."
        )
    if "v6_with_ui_not_pass" in keys or "reference_compare_v4_with_ui_not_pass" in keys:
        actions.append(
            "Fix the generated drawing against the reference drafting standard, then rerun strict v4 reference compare and v6 visual QC with Drawing Review UI screenshots."
        )
    if "manual_review_screenshot_not_bound" in keys or "ui_report_entry_not_pass" in keys:
        actions.append(
            "Capture the generated-vs-reference comparison from the application Drawing Review UI and bind the manual visual judgement to that exact screenshot file."
        )
    if "direct_ui_screenshot_recheck_not_pass" in keys or "direct_ui_screenshot_recheck_method_invalid" in keys:
        actions.append(
            "Rerun the application Drawing Review UI screenshot review for the corrected 006 output and record a PASS direct visual recheck before using API metrics as supporting evidence."
        )
    if "generated_png_source_not_current_run" in keys:
        actions.append(
            "Use the PNG exported from the current run_dir, not a legacy drw_output/v5 image, for application UI screenshot review."
        )
    actions.append("Do not expand acceptance to LB26001-A-04-007/008/009/015/022 until this 006 proof is PASS.")
    return _unique(actions)


def build_acceptance_proof(
    *,
    staged_summary_path: Path = DEFAULT_STAGED_SUMMARY,
    ui_gate_path: Path = DEFAULT_UI_GATE,
    screenshot_binding_gate_path: Path = DEFAULT_SCREENSHOT_BINDING_GATE,
    acceptance_gate_path: Path = DEFAULT_ACCEPTANCE_GATE,
    supplemental_checklist_gate_path: Path = DEFAULT_SUPPLEMENTAL_CHECKLIST_GATE,
    direct_ui_screenshot_recheck_path: Path | None = None,
    out_json: Path | None = None,
    out_md: Path | None = None,
) -> dict[str, Any]:
    latest_artifacts = _latest_locked_real_rerun_artifacts()
    if latest_artifacts:
        if _same_path(staged_summary_path, DEFAULT_STAGED_SUMMARY):
            staged_summary_path = latest_artifacts["staged_summary"]
        if _same_path(ui_gate_path, DEFAULT_UI_GATE):
            ui_gate_path = latest_artifacts["ui_gate"]
        if _same_path(screenshot_binding_gate_path, DEFAULT_SCREENSHOT_BINDING_GATE):
            screenshot_binding_gate_path = latest_artifacts["screenshot_binding_gate"]
        if _same_path(acceptance_gate_path, DEFAULT_ACCEPTANCE_GATE):
            acceptance_gate_path = latest_artifacts["acceptance_gate"]
        if _same_path(supplemental_checklist_gate_path, DEFAULT_SUPPLEMENTAL_CHECKLIST_GATE):
            supplemental_checklist_gate_path = latest_artifacts["supplemental_checklist_gate"]
        if direct_ui_screenshot_recheck_path is None:
            direct_ui_screenshot_recheck_path = latest_artifacts["direct_ui_screenshot_recheck"]

    staged_summary = _read_json(staged_summary_path)
    staged_case = _find_staged_case(staged_summary, BASE)
    ui_gate = _read_json(ui_gate_path)
    ui_entry = _find_gate_entry(ui_gate, BASE)
    screenshot_gate = _read_json(screenshot_binding_gate_path)
    screenshot_entry = _find_gate_entry(screenshot_gate, BASE)
    acceptance_gate = _read_json(acceptance_gate_path)
    acceptance_base = _find_acceptance_base_result(acceptance_gate, BASE)
    supplemental_checklist_gate = _read_json(supplemental_checklist_gate_path)
    supplemental_checklist_base = _find_acceptance_base_result(supplemental_checklist_gate, BASE)
    direct_ui_screenshot_recheck_path = _select_direct_recheck_path(
        direct_ui_screenshot_recheck_path,
        acceptance_base,
        supplemental_checklist_base,
    )
    direct_recheck = _read_json(direct_ui_screenshot_recheck_path)
    direct_recheck_entry = _find_direct_recheck_case(direct_recheck, BASE)

    staged = _staged_evidence(staged_summary_path, staged_summary, staged_case)
    ui = _ui_evidence(
        ui_gate_path=ui_gate_path,
        ui_gate=ui_gate,
        ui_entry=ui_entry,
        screenshot_gate_path=screenshot_binding_gate_path,
        screenshot_gate=screenshot_gate,
        screenshot_entry=screenshot_entry,
        acceptance_base=acceptance_base,
        supplemental_checklist_gate_path=supplemental_checklist_gate_path,
        supplemental_checklist_gate=supplemental_checklist_gate,
        supplemental_checklist_base=supplemental_checklist_base,
        direct_recheck_path=direct_ui_screenshot_recheck_path,
        direct_recheck=direct_recheck,
        direct_recheck_entry=direct_recheck_entry,
    )
    acceptance = _acceptance_evidence(acceptance_gate_path, acceptance_gate, acceptance_base)
    blocking_keys = _blocking_issue_keys(staged=staged, ui=ui, acceptance=acceptance)
    passed = not blocking_keys
    status = "pass" if passed else ("blocked_by_006" if "acceptance_gate_not_pass" in blocking_keys else "need_review")
    payload = {
        "schema": "sw_drawing_studio.lb26001_006_acceptance_proof.v4_2",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "base": BASE,
        "status": status,
        "pass": passed,
        "report_is_acceptance_evidence": passed,
        "api_only_acceptance_allowed": False,
        "api_is_not_final_judgement": True,
        "application_ui_screenshot_is_final_gate": True,
        "staged_evidence": staged,
        "ui_closure_evidence": ui,
        "acceptance_gate_evidence": acceptance,
        "blocking_issue_keys": blocking_keys,
        "blocking_reasons": _unique(
            list(ui.get("reasons") or [])
            + list(acceptance.get("acceptance_reasons") or [])
            + blocking_keys
        ),
        "next_required_actions": _next_actions(blocking_keys),
    }
    if out_json is not None:
        _write_json(out_json, payload)
    if out_md is not None:
        _write_text(out_md, render_markdown(payload))
    return payload


def render_markdown(payload: dict[str, Any]) -> str:
    staged = payload.get("staged_evidence") or {}
    ui = payload.get("ui_closure_evidence") or {}
    acceptance = payload.get("acceptance_gate_evidence") or {}
    lines = [
        f"# {payload.get('base')} v4.2 Acceptance Proof",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- PASS: `{str(payload.get('pass')).lower()}`",
        "- API-only acceptance allowed: `false`",
        "- Application UI screenshot is final gate: `true`",
        "",
        "## Gates",
        "",
        "| Gate | Result | Evidence |",
        "| --- | --- | --- |",
        f"| Staged CAD deliverable | `{str(staged.get('case_quality_pass')).lower()}` | `{staged.get('staged_summary')}` |",
        f"| DisplayDim lifecycle audit | `{str(staged.get('displaydim_lifecycle_pass')).lower()}` | `{staged.get('displaydim_lifecycle_report')}` |",
        f"| UI report screenshot entry | `{str(ui.get('ui_report_entry_pass')).lower()}` | `{ui.get('screenshot_binding_gate')}` |",
        f"| Manual judgement screenshot binding | `{str(ui.get('manual_review_entry_screenshot_pass')).lower()}` | `{ui.get('screenshot_binding_gate')}` |",
        f"| Direct UI screenshot recheck | `{str(ui.get('direct_ui_screenshot_recheck_pass')).lower()}` | `{ui.get('direct_ui_screenshot_recheck')}` |",
        f"| v6 visual QC with UI | `{str(ui.get('vision_qc_v6_visual_acceptance_pass')).lower()}` | `{ui.get('ui_gate')}` |",
        f"| Reference compare v4 with UI | `{str(ui.get('reference_compare_v4_pass')).lower()}` | `{ui.get('ui_gate')}` |",
        f"| Fresh generated PNG source | `{str(ui.get('generated_png_source_pass')).lower()}` | `{ui.get('ui_screenshot_file_count')} UI screenshot file(s)` |",
        f"| Acceptance primary gate | `{str(acceptance.get('acceptance_primary_pass')).lower()}` | `{acceptance.get('acceptance_gate')}` |",
        "",
        "## Blocking Issues",
        "",
    ]
    keys = list(payload.get("blocking_issue_keys") or [])
    if keys:
        lines.extend([f"- `{key}`" for key in keys])
    else:
        lines.append("- None")
    lines.extend(["", "## Next Required Actions", ""])
    lines.extend([f"- {item}" for item in payload.get("next_required_actions") or []])
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build LB26001-A-04-006 UI-backed acceptance proof.")
    parser.add_argument("--staged-summary", default=str(DEFAULT_STAGED_SUMMARY))
    parser.add_argument("--ui-gate", default=str(DEFAULT_UI_GATE))
    parser.add_argument("--screenshot-binding-gate", default=str(DEFAULT_SCREENSHOT_BINDING_GATE))
    parser.add_argument("--acceptance-gate", default=str(DEFAULT_ACCEPTANCE_GATE))
    parser.add_argument("--supplemental-checklist-gate", default=str(DEFAULT_SUPPLEMENTAL_CHECKLIST_GATE))
    parser.add_argument("--direct-ui-screenshot-recheck", default="")
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    parser.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    args = parser.parse_args()

    payload = build_acceptance_proof(
        staged_summary_path=_repo_path(args.staged_summary),
        ui_gate_path=_repo_path(args.ui_gate),
        screenshot_binding_gate_path=_repo_path(args.screenshot_binding_gate),
        acceptance_gate_path=_repo_path(args.acceptance_gate),
        supplemental_checklist_gate_path=_repo_path(args.supplemental_checklist_gate),
        direct_ui_screenshot_recheck_path=(
            _repo_path(args.direct_ui_screenshot_recheck)
            if args.direct_ui_screenshot_recheck
            else None
        ),
        out_json=_repo_path(args.out_json),
        out_md=_repo_path(args.out_md),
    )
    print(json.dumps({
        "pass": payload.get("pass"),
        "status": payload.get("status"),
        "blocking_issue_keys": payload.get("blocking_issue_keys", []),
        "report": str(_repo_path(args.out_json)),
    }, ensure_ascii=False))
    return 0 if payload.get("pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
