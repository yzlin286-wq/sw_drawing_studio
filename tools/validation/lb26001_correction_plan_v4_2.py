"""Build the UI-first LB26001 v4.2 correction plan.

This is a file-only planning report. It combines the learned same-name
reference drawing standard with the current application Drawing Review UI
screenshot judgement. It must not be treated as CAD execution or acceptance
evidence.
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
REQUIRED_VISUAL_CHECKS = (
    "reference_match",
    "view_layout",
    "display_dimensions",
    "dimension_readability",
    "title_block",
    "manufacturing_notes",
)
FINDING_CHECK_KEYWORDS = {
    "reference_match": ("reference", "same-name", "not match", "does not match", "differs"),
    "view_layout": ("view layout", "layout", "view", "sheet framing", "scale"),
    "display_dimensions": ("dimension", "displaydim", "callout", "hole", "offset", "small projection"),
    "dimension_readability": ("dense", "cluster", "readability", "placement", "readable"),
    "title_block": ("title", "title-block", "titleblock", "border", "frame"),
    "manufacturing_notes": ("manufacturing", "notes", "roughness", "bottom text"),
}

DEFAULT_STANDARD = REPO_ROOT / "drw_output" / "reference_style_profile" / "lb26001_drawing_standard_v3_0.json"
DEFAULT_REQUESTED_STATUS = REPO_ROOT / "drw_output" / "diagnostics" / "lb26001_requested_drawings_status_v4_2.json"
DEFAULT_READINESS = REPO_ROOT / "drw_output" / "diagnostics" / "lb26001_006_regression_readiness_v4_2.json"
DEFAULT_REFERENCE_DIR = REPO_ROOT / "3D转2D测试图纸"
DEFAULT_REFERENCE_INTENT_PLAN_006 = REPO_ROOT / "drw_output" / "reference_intent_dimension_plan_006.json"
DEFAULT_OUT_JSON = REPO_ROOT / "drw_output" / "reference_style_profile" / "lb26001_correction_plan_v4_2.json"
DEFAULT_OUT_MD = REPO_ROOT / "drw_output" / "reference_style_profile" / "lb26001_correction_plan_v4_2.md"


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


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


def _rule_map(standard: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in standard.get("sample_rules") or []:
        if not isinstance(item, dict):
            continue
        base = str(item.get("base") or "").strip()
        if base:
            result[base] = item
    return result


def _status_map(requested_status: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in requested_status.get("base_results") or []:
        if not isinstance(item, dict):
            continue
        base = str(item.get("base") or "").strip()
        if base:
            result[base] = item
    return result


def _failed_checklist_items(status_entry: dict[str, Any]) -> list[str]:
    value = status_entry.get("manual_visual_checklist_failed_items")
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    checklist = status_entry.get("latest_manual_visual_checklist")
    if isinstance(checklist, dict):
        return [key for key in REQUIRED_VISUAL_CHECKS if checklist.get(key) is False]
    return []


def _missing_checklist_items(status_entry: dict[str, Any]) -> list[str]:
    value = status_entry.get("manual_visual_checklist_missing_items")
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    checklist = status_entry.get("latest_manual_visual_checklist")
    if not isinstance(checklist, dict):
        return list(REQUIRED_VISUAL_CHECKS)
    missing: list[str] = []
    for key in REQUIRED_VISUAL_CHECKS:
        if key not in checklist or checklist.get(key) is None:
            missing.append(key)
    return missing


def _notes(status_entry: dict[str, Any]) -> dict[str, str]:
    value = status_entry.get("latest_manual_visual_checklist_notes")
    if not isinstance(value, dict):
        return {}
    return {str(key): str(item) for key, item in value.items() if str(item).strip()}


def _findings(status_entry: dict[str, Any]) -> list[str]:
    value = status_entry.get("latest_manual_findings")
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _latest_manual_failed(status_entry: dict[str, Any]) -> bool:
    status = str(status_entry.get("latest_manual_status") or status_entry.get("status") or "").strip().lower()
    return status in {"fail", "failed", "visual_fail", "generated_png_source_invalid", "manual_visual_checklist_failed"}


def _inferred_check_notes_from_findings(status_entry: dict[str, Any]) -> dict[str, str]:
    findings = _findings(status_entry)
    if not findings or not _latest_manual_failed(status_entry):
        return {}
    result: dict[str, list[str]] = {key: [] for key in REQUIRED_VISUAL_CHECKS}
    for finding in findings:
        lowered = finding.lower()
        for key, keywords in FINDING_CHECK_KEYWORDS.items():
            if any(keyword in lowered for keyword in keywords):
                result[key].append(finding)
    populated = {key: " ".join(values) for key, values in result.items() if values}
    if populated:
        return populated
    return {key: "Direct UI screenshot review failed without a structured checklist; this item must be rechecked." for key in REQUIRED_VISUAL_CHECKS}


def _effective_visual_checks(status_entry: dict[str, Any]) -> tuple[list[str], list[str], dict[str, str]]:
    failed = _failed_checklist_items(status_entry)
    missing = _missing_checklist_items(status_entry)
    if failed or missing:
        return failed, missing, {}
    inferred_notes = _inferred_check_notes_from_findings(status_entry)
    inferred_failed = [key for key in REQUIRED_VISUAL_CHECKS if key in inferred_notes]
    return inferred_failed, [], inferred_notes


def _reference_standard(rule: dict[str, Any]) -> dict[str, Any]:
    return {
        "reference_drawing": str(rule.get("reference_drawing") or ""),
        "sheet_size_mm": rule.get("sheet_size_mm") or {},
        "required_view_count": _int(rule.get("required_view_count")),
        "required_view_types": {
            str(key): _int(value)
            for key, value in (rule.get("required_view_types") or {}).items()
        },
        "required_projected_view_count": _int(rule.get("required_projected_view_count")),
        "display_dim_floor": _int(rule.get("display_dim_floor")),
        "layout_slots_center_norm": rule.get("layout_slots_center_norm") or {},
        "layout_tolerance_norm": rule.get("layout_tolerance_norm"),
        "section_policy": rule.get("section_policy") or {},
        "sheet_template_policy": {
            "policy": "strip_default_template_artifacts",
            "default_template_artifacts_allowed": False,
            "skip_builtin_gb_frame_titleblock": True,
            "visible_titlebar_mode": "compact_reference_fields",
            "reason": "same-name reference controls visible sheet/titleblock style",
        },
        "must_not_count_as_display_dim": rule.get("must_not_count_as_display_dim") or [
            "Note",
            "OCR text",
            "QC sidecar",
            "visual-only text",
        ],
        "correction_checks": rule.get("correction_checks") or [],
    }


def _visual_correction_actions(status_entry: dict[str, Any]) -> list[dict[str, str]]:
    actions_by_key = {
        "reference_match": "Match the same-name SLDDRW reference composition before considering API metrics sufficient.",
        "view_layout": "Use the learned normalized layout slots and avoid default title-block-driven sheet placement.",
        "display_dimensions": "Create explicit reference-intent SolidWorks DisplayDim objects for visible manufacturing callouts.",
        "dimension_readability": "Arrange dimensions into readable lanes and reject overlap or sparse generic AutoDimension output.",
        "title_block": "Remove or suppress the oversized default title block/frame when it conflicts with the reference layout.",
        "manufacturing_notes": "Preserve reference-style notes, roughness, warning text, and compact callout regions.",
    }
    notes = _notes(status_entry)
    inferred_failed, inferred_missing, inferred_notes = _effective_visual_checks(status_entry)
    result: list[dict[str, str]] = []
    for key in inferred_failed or inferred_missing:
        result.append(
            {
                "check": key,
                "source_note": notes.get(key) or inferred_notes.get(key, ""),
                "source_type": "manual_visual_checklist" if notes.get(key) else ("direct_ui_screenshot_finding" if inferred_notes.get(key) else "missing_manual_checklist"),
                "correction_action": actions_by_key.get(key, "Review and correct this visual checklist item from the application UI screenshot."),
            }
        )
    return result


def _validation_commands(base: str) -> dict[str, str]:
    short = base.rsplit("-", 1)[-1]
    return {
        "readiness_check": (
            "python tools\\validation\\lb26001_006_regression_readiness_v4_2.py "
            "--out drw_output\\diagnostics\\lb26001_006_regression_readiness_v4_2.json"
        ),
        "locked_real_cad_regression": (
            f'Run one JobRuntimeFacade/QProcess CAD job for "{base}" only after readiness is clear; '
            "do not call SolidWorks from the UI thread."
        ),
        "dimension_validation": f"python tools\\validation\\dimension_validation_smoke_v3.py --run-dir <fresh_run_dir> --out drw_output\\dimension_validation_{short}_v4_2.json",
        "strict_reference_compare": f"python tools\\validation\\reference_compare_v4.py --run-dir <fresh_run_dir> --base {base} --out drw_output\\reference_compare_v4_{short}_v4_2.json",
        "drawing_review_ui_screenshot": (
            "python tools\\ui_robot\\drawing_visual_review_suite.py "
            f"--base {base} --out-dir drw_output\\ui_acceptance\\<fresh_{short}_ui_review>"
        ),
        "ui_closure": (
            "python tools\\validation\\apply_ui_visual_review_v4.py "
            "--summary <fresh_staged_summary.json> --ui-report <fresh_drawing_visual_review_report.json> "
            "--manual-review <fresh_manual_visual_judgement.json> --out-dir <fresh_closed_loop_dir> "
            f"--base {base}"
        ),
    }


def _reference_intent_trace_policy(base: str) -> dict[str, Any]:
    if base != PRIMARY_BASE:
        return {
            "required": False,
            "reason": "gated until 006 reference-intent DisplayDim persistence and UI screenshot acceptance pass",
        }
    return {
        "required": True,
        "source_plan": str(DEFAULT_REFERENCE_INTENT_PLAN_006),
        "required_fields": [
            "target_key",
            "view_slot",
            "selected_entity",
            "add_method",
            "display_dim_count_before",
            "display_dim_count_after",
            "target_covered_after_attempt",
            "persisted_after_reopen",
        ],
        "required_stages": [
            "pre_saveas",
            "post_saveas_reopen_prune",
            "pre_export_final",
            "post_layout_final",
        ],
        "final_stage_required": "post_layout_final",
        "generic_autodimension_acceptance_allowed": False,
        "expected_add_methods_by_type": {
            "diameter": "AddDiameterDimension2",
            "linear_horizontal": "AddHorizontalDimension2",
            "linear_vertical": "AddVerticalDimension2",
        },
    }


def _visual_validation_policy(bases: list[str]) -> dict[str, Any]:
    return {
        "per_drawing_application_ui_screenshot_required": True,
        "required_bases": list(bases),
        "required_review_mode": "application_drawing_review_ui_screenshot",
        "final_judgement_source": "application_drawing_review_ui_screenshot_manual_visual_judgement",
        "manual_visual_judgement_required": True,
        "manual_visual_checklist_required": True,
        "same_name_reference_screenshot_comparison_required": True,
        "api_metrics_role": "supporting_evidence_only",
        "api_only_acceptance_allowed": False,
        "supporting_api_metrics_do_not_override_visual_fail": True,
    }


def _entry(
    *,
    sequence: int,
    base: str,
    rule: dict[str, Any],
    status_entry: dict[str, Any],
    reference_dir: Path,
    readiness_blockers: list[str],
) -> dict[str, Any]:
    part_path = reference_dir / f"{base}.SLDPRT"
    reference_drawing = reference_dir / f"{base}.SLDDRW"
    is_primary = base == PRIMARY_BASE
    current_pass = bool(status_entry.get("pass"))
    primary_ready = not readiness_blockers
    failed_checks, missing_checks, inferred_notes = _effective_visual_checks(status_entry)
    return {
        "sequence": sequence,
        "base": base,
        "correction_stage": "pilot_006_first" if is_primary else "gated_after_006_pass",
        "real_cad_regression_allowed_now": bool(is_primary and primary_ready),
        "blocked_by_readiness": bool(is_primary and readiness_blockers),
        "blocked_until_006_passes": not is_primary,
        "part_path": str(part_path),
        "part_exists": part_path.exists(),
        "reference_drawing": str(rule.get("reference_drawing") or reference_drawing),
        "reference_drawing_exists": reference_drawing.exists(),
        "must_not_modify_original_part": True,
        "reference_standard": _reference_standard(rule),
        "current_ui_status": {
            "status": str(status_entry.get("status") or "missing_status"),
            "pass": current_pass,
            "application_ui_screenshot_review_required": True,
            "application_ui_screenshot_review_present": bool(
                status_entry.get("application_ui_screenshot_review_present")
            ),
            "application_ui_screenshot_review_method_ok": bool(
                status_entry.get("application_ui_screenshot_review_method_ok")
            ),
            "application_ui_screenshot_gate_pass": bool(status_entry.get("application_ui_screenshot_gate_pass")),
            "application_ui_screenshot_content_check_pass": bool(
                status_entry.get("application_ui_screenshot_content_check_pass")
            ),
            "ui_screenshot_file_count": _int(status_entry.get("ui_screenshot_file_count")),
            "application_ui_screenshot_paths_existing_application_ui": list(
                status_entry.get("application_ui_screenshot_paths_existing_application_ui") or []
            ),
            "ui_visual_review_status": str(status_entry.get("ui_visual_review_status") or ""),
            "ui_screenshot_review_is_final_gate": True,
            "api_is_not_final_judgement": True,
            "api_only_acceptance_allowed": False,
            "missing_ui_acceptance_requirements": list(status_entry.get("missing_ui_acceptance_requirements") or []),
            "generated_png_source_pass": bool(status_entry.get("generated_png_source_pass")),
            "source_ui_report": str(status_entry.get("source_ui_report") or ""),
            "latest_manual_review": str(status_entry.get("latest_manual_review") or ""),
            "latest_manual_status": str(status_entry.get("latest_manual_status") or ""),
            "latest_manual_required_correction": str(status_entry.get("latest_manual_required_correction") or ""),
        },
        "visual_validation_required": {
            "application_drawing_review_ui_screenshot_required": True,
            "manual_visual_judgement_required": True,
            "manual_visual_checklist_required": True,
            "same_name_reference_screenshot_comparison_required": True,
            "current_ui_screenshot_file_count": _int(status_entry.get("ui_screenshot_file_count")),
            "current_missing_ui_acceptance_requirements": list(
                status_entry.get("missing_ui_acceptance_requirements") or []
            ),
            "final_judgement_source": "application_drawing_review_ui_screenshot_manual_visual_judgement",
            "api_is_not_final_judgement": True,
            "api_only_acceptance_allowed": False,
        },
        "reference_intent_trace_policy": _reference_intent_trace_policy(base),
        "ui_visual_failures": {
            "failed_checklist_items": _failed_checklist_items(status_entry),
            "missing_checklist_items": _missing_checklist_items(status_entry),
            "inferred_failed_checklist_items": failed_checks if inferred_notes else [],
            "effective_failed_visual_checks": failed_checks,
            "direct_ui_findings_used_for_correction": bool(inferred_notes),
            "checklist_notes": _notes(status_entry),
            "inferred_check_notes": inferred_notes,
            "findings": _findings(status_entry),
        },
        "correction_actions": _visual_correction_actions(status_entry),
        "acceptance_requirements": [
            "Fresh run artifacts must be under drw_output/runs/<run_id>/ and must include SLDDRW/PDF/DXF/PNG plus manifest and event log.",
            "Worker stdout/event logs must include job_started, progress, heartbeat, and job_finished or job_failed with reason.",
            "Generated view count and view type counts must match the same-name reference standard.",
            "Projected views must be true projected views, not independent named-view substitutes.",
            "Final persisted/exported real SolidWorks DisplayDim count must meet or exceed the same-name reference floor.",
            "006 reference-intent dimensions must record target key, view slot, selected entity, add method, before/after count, target coverage, and persisted-after-reopen evidence.",
            "Note/OCR/QC sidecar/visual-only text must not be counted as DisplayDim.",
            "Application Drawing Review UI screenshot review must pass with every required manual visual checklist item true.",
        ],
        "validation_commands": _validation_commands(base),
    }


def build_correction_plan(
    *,
    standard: dict[str, Any],
    requested_status: dict[str, Any],
    readiness: dict[str, Any],
    reference_dir: Path = DEFAULT_REFERENCE_DIR,
    requested_bases: list[str] | None = None,
) -> dict[str, Any]:
    bases = requested_bases or REQUESTED_BASES
    rules = _rule_map(standard)
    statuses = _status_map(requested_status)
    readiness_blockers = [str(item) for item in readiness.get("blocking_issue_keys") or [] if str(item).strip()]
    primary_status = statuses.get(PRIMARY_BASE, {})
    expansion_allowed = bool(primary_status.get("pass")) and not readiness_blockers
    entries = [
        _entry(
            sequence=index,
            base=base,
            rule=rules.get(base, {}),
            status_entry=statuses.get(base, {}),
            reference_dir=reference_dir,
            readiness_blockers=readiness_blockers,
        )
        for index, base in enumerate(bases, start=1)
    ]
    missing_reference_rules = [base for base in bases if base not in rules]
    missing_status_entries = [base for base in bases if base not in statuses]

    if readiness_blockers:
        status = "blocked_by_solidworks_readiness"
    elif not bool(primary_status.get("pass")):
        status = "blocked_by_006"
    elif not all(bool(statuses.get(base, {}).get("pass")) for base in bases):
        status = "needs_remaining_reference_corrections"
    else:
        status = "all_requested_drawings_ui_passed"

    return {
        "schema": "sw_drawing_studio.lb26001_correction_plan.v4_2",
        "generated_at": _now(),
        "status": status,
        "pass": False,
        "report_is_acceptance_evidence": False,
        "correction_plan_ready": bool(entries) and not missing_reference_rules,
        "requested_status": str(requested_status.get("status") or ""),
        "readiness_status": str(readiness.get("status") or requested_status.get("readiness_status") or ""),
        "readiness_blocking_issue_keys": readiness_blockers,
        "requested_bases": bases,
        "primary_base": PRIMARY_BASE,
        "pilot_first_policy": "Do not expand acceptance to 007/008/009/015/022 until 006 passes real CAD, strict v4/v6, and application UI screenshot manual judgement.",
        "expansion_allowed_after_006": expansion_allowed,
        "api_is_not_final_judgement": True,
        "api_only_acceptance_allowed": False,
        "ui_screenshot_review_is_final_gate": True,
        "visual_validation_policy": _visual_validation_policy(bases),
        "source_standard": str(DEFAULT_STANDARD),
        "source_requested_status": str(DEFAULT_REQUESTED_STATUS),
        "source_readiness": str(DEFAULT_READINESS),
        "missing_reference_rules": missing_reference_rules,
        "missing_status_entries": missing_status_entries,
        "preconditions": [
            "SolidWorks must be responsive and unsaved-document risk must be cleared before real CAD rerun.",
            "Only the 006 pilot may run first, and it must run through JobRuntimeFacade/QProcess with the global SolidWorks lock.",
            "Original SLDPRT/SLDASM files must not be modified; use run_dir/input_work copies.",
            "Do not lower QC thresholds and do not count Note/OCR/QC sidecar text as DisplayDim.",
            "Every accepted drawing needs application Drawing Review UI screenshot evidence and a complete manual visual checklist.",
        ],
        "entries": entries,
    }


def render_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# LB26001 v4.2 UI-first correction plan",
        "",
        f"- Generated at: `{plan.get('generated_at')}`",
        f"- Status: `{plan.get('status')}`",
        f"- Primary base: `{plan.get('primary_base')}`",
        f"- Readiness blockers: `{', '.join(plan.get('readiness_blocking_issue_keys') or []) or 'none'}`",
        "- This is not acceptance evidence; application UI screenshot review remains the final gate.",
        "",
        "## Preconditions",
        "",
    ]
    lines.extend(f"- {item}" for item in plan.get("preconditions") or [])
    lines.extend(
        [
            "",
            "## Correction order",
            "",
            "| # | Base | Stage | Views | DisplayDim floor | UI status | Failed visual checks | Allowed now |",
            "| ---: | --- | --- | --- | ---: | --- | --- | --- |",
        ]
    )
    for item in plan.get("entries") or []:
        standard = item.get("reference_standard") or {}
        view_types = ", ".join(
            f"{key}x{value}" for key, value in sorted((standard.get("required_view_types") or {}).items())
        )
        views = f"{standard.get('required_view_count')} views; {view_types}"
        failures = ", ".join(
            (item.get("ui_visual_failures") or {}).get("failed_checklist_items")
            or (item.get("ui_visual_failures") or {}).get("effective_failed_visual_checks")
            or []
        )
        allowed = "yes" if item.get("real_cad_regression_allowed_now") else "no"
        lines.append(
            "| {sequence} | {base} | {stage} | {views} | {floor} | {status} | {failures} | {allowed} |".format(
                sequence=item.get("sequence"),
                base=item.get("base"),
                stage=item.get("correction_stage"),
                views=views,
                floor=standard.get("display_dim_floor"),
                status=(item.get("current_ui_status") or {}).get("status"),
                failures=failures or "none",
                allowed=allowed,
            )
        )
    lines.extend(["", "## 006 next action", ""])
    primary = next((item for item in plan.get("entries") or [] if item.get("base") == PRIMARY_BASE), {})
    for action in primary.get("correction_actions") or []:
        lines.append(f"- `{action.get('check')}`: {action.get('correction_action')}")
    lines.extend(
        [
            "",
            "> Run no real CAD correction until readiness is clear. After that, rerun only LB26001-A-04-006 first and close it through strict v4/v6 plus Drawing Review UI screenshot manual judgement.",
            "",
        ]
    )
    return "\n".join(lines)


def write_correction_plan(
    *,
    standard_path: Path = DEFAULT_STANDARD,
    requested_status_path: Path = DEFAULT_REQUESTED_STATUS,
    readiness_path: Path = DEFAULT_READINESS,
    reference_dir: Path = DEFAULT_REFERENCE_DIR,
    out_json: Path = DEFAULT_OUT_JSON,
    out_md: Path = DEFAULT_OUT_MD,
    requested_bases: list[str] | None = None,
) -> dict[str, Any]:
    plan = build_correction_plan(
        standard=_read_json(standard_path),
        requested_status=_read_json(requested_status_path),
        readiness=_read_json(readiness_path),
        reference_dir=reference_dir,
        requested_bases=requested_bases,
    )
    _write_json(out_json, plan)
    _write_text(out_md, render_markdown(plan))
    return plan


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the LB26001 v4.2 UI-first correction plan.")
    parser.add_argument("--standard", default=str(DEFAULT_STANDARD))
    parser.add_argument("--requested-status", default=str(DEFAULT_REQUESTED_STATUS))
    parser.add_argument("--readiness", default=str(DEFAULT_READINESS))
    parser.add_argument("--reference-dir", default=str(DEFAULT_REFERENCE_DIR))
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    parser.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    parser.add_argument("--base", action="append", default=[])
    args = parser.parse_args()

    plan = write_correction_plan(
        standard_path=Path(args.standard),
        requested_status_path=Path(args.requested_status),
        readiness_path=Path(args.readiness),
        reference_dir=Path(args.reference_dir),
        out_json=Path(args.out_json),
        out_md=Path(args.out_md),
        requested_bases=args.base or None,
    )
    print(
        json.dumps(
            {
                "pass": plan.get("pass"),
                "status": plan.get("status"),
                "correction_plan_ready": plan.get("correction_plan_ready"),
                "entry_count": len(plan.get("entries") or []),
                "out_json": str(Path(args.out_json)),
                "out_md": str(Path(args.out_md)),
            },
            ensure_ascii=False,
        )
    )
    return 0 if plan.get("correction_plan_ready") else 1


if __name__ == "__main__":
    raise SystemExit(main())
