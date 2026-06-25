"""Audit the LB26001 v4.2 UI-first acceptance gate.

The gate is deliberately file-only. It consumes UI closure summaries produced
by apply_ui_visual_review_v4.py and does not call SolidWorks or any COM API.
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

from app.services.application_ui_screenshot_validator import validate_application_ui_screenshots
from app.services.generated_png_source_evidence import generated_png_source_evidence

PRIMARY_BASE = "LB26001-A-04-006"
DEPENDENT_BASES = [
    "LB26001-A-04-007",
    "LB26001-A-04-008",
    "LB26001-A-04-009",
    "LB26001-A-04-015",
    "LB26001-A-04-022",
]
DEFAULT_BASES = [PRIMARY_BASE, *DEPENDENT_BASES]
DEFAULT_STAGED_SUMMARY = (
    REPO_ROOT
    / "drw_output"
    / "staged_validation"
    / "LB26001_006_explicit_displaydim_visible_entities_20260623"
    / "summary.json"
)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _repo_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


def _artifact_path(value: Any, *, base_dir: Path | None = None) -> Path | None:
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


def _entry_pass(entry: dict[str, Any], evidence: dict[str, Any] | None = None) -> bool:
    if not entry:
        return False
    evidence = evidence if evidence is not None else _entry_evidence(entry, "")
    generated_png_source_ok = (
        not bool(evidence.get("generated_png_source_required"))
        or bool(evidence.get("generated_png_source_pass"))
    )
    manual_visual_checklist_ok = (
        bool(evidence.get("manual_case_status_pass"))
        and bool(evidence.get("manual_visual_checklist_required"))
        and bool(evidence.get("manual_visual_checklist_pass"))
        and not list(evidence.get("manual_visual_checklist_missing_items") or [])
        and not list(evidence.get("manual_visual_checklist_failed_items") or [])
        and not list(evidence.get("manual_visual_checklist_not_passed_items") or [])
    )
    return (
        bool(entry.get("vision_qc_v6_visual_acceptance_pass"))
        and bool(entry.get("reference_compare_v4_pass"))
        and bool(evidence.get("vision_qc_v6_visual_acceptance_pass"))
        and bool(evidence.get("reference_compare_v4_pass"))
        and bool(evidence.get("ui_screenshot_review_pass"))
        and bool(evidence.get("ui_screenshot_review_method_ok"))
        and bool(evidence.get("ui_screenshot_review_case_match"))
        and bool(evidence.get("source_ui_report_application_ui_ok"))
        and int(evidence.get("ui_screenshot_file_count") or 0) > 0
        and bool(evidence.get("ui_screenshot_content_check_pass"))
        and manual_visual_checklist_ok
        and generated_png_source_ok
    )


def _find_staged_case(summary: dict[str, Any], base: str) -> dict[str, Any]:
    for item in summary.get("cases") or []:
        if not isinstance(item, dict):
            continue
        item_base = str(item.get("part_name") or Path(str(item.get("part") or "")).stem or "").strip()
        if item_base == base:
            return item
    return {}


def _staged_lifecycle_evidence(staged_summary_path: Path | None, base: str) -> dict[str, Any]:
    if base != PRIMARY_BASE:
        return {
            "displaydim_lifecycle_required": False,
            "displaydim_lifecycle_pass": True,
        }
    summary_path = staged_summary_path or DEFAULT_STAGED_SUMMARY
    summary = _read_json(summary_path)
    case = _find_staged_case(summary, base)
    case_dir = _artifact_path(case.get("case_dir"), base_dir=summary_path.parent) if case else None
    lifecycle_report_value = case.get("displaydim_lifecycle_report") if case else ""
    if not lifecycle_report_value and case_dir:
        lifecycle_report_value = str(case_dir / "displaydim_lifecycle_audit.json")
    lifecycle_report_path = _artifact_path(lifecycle_report_value, base_dir=case_dir or summary_path.parent)
    lifecycle_report = _read_json(lifecycle_report_path) if lifecycle_report_path else {}
    lifecycle_report_exists = bool(
        lifecycle_report_path
        and lifecycle_report_path.exists()
        and lifecycle_report_path.is_file()
        and lifecycle_report_path.stat().st_size > 0
    )
    lifecycle_case_pass = case.get("displaydim_lifecycle_pass") is True
    lifecycle_report_pass = lifecycle_report.get("pass") is True
    lifecycle_pass = bool(case and lifecycle_case_pass and lifecycle_report_exists and lifecycle_report_pass)
    return {
        "staged_summary": str(summary_path),
        "staged_summary_exists": summary_path.exists(),
        "staged_case_present": bool(case),
        "displaydim_lifecycle_required": True,
        "displaydim_lifecycle_report": str(lifecycle_report_path or ""),
        "displaydim_lifecycle_report_exists": lifecycle_report_exists,
        "displaydim_lifecycle_status": str(lifecycle_report.get("status") or case.get("displaydim_lifecycle_status") or ""),
        "displaydim_lifecycle_case_pass": lifecycle_case_pass,
        "displaydim_lifecycle_report_pass": lifecycle_report_pass,
        "displaydim_lifecycle_pass": lifecycle_pass,
        "displaydim_lifecycle_blocking_issue_keys": list(case.get("displaydim_lifecycle_blocking_issue_keys") or [])
        + list(lifecycle_report.get("blocking_issue_keys") or []),
    }


def _merge_gate_entries(gate_paths: list[Path]) -> dict[str, dict[str, Any]]:
    entries: dict[str, dict[str, Any]] = {}
    for gate_path in gate_paths:
        payload = _read_json(gate_path)
        for entry in payload.get("entries") or []:
            if not isinstance(entry, dict):
                continue
            base = str(entry.get("base") or "").strip()
            if not base:
                continue
            merged = dict(entry)
            merged["gate_summary"] = str(gate_path)
            merged["_gate_summary_dir"] = str(gate_path.parent)
            entries[base] = merged
    return entries


def _entry_evidence(entry: dict[str, Any], base: str) -> dict[str, Any]:
    gate_dir = _artifact_path(entry.get("_gate_summary_dir")) if entry.get("_gate_summary_dir") else None
    v6_path = _artifact_path(entry.get("vision_qc_v6_with_ui_review"), base_dir=gate_dir)
    v4_path = _artifact_path(entry.get("reference_compare_v4_with_ui_review"), base_dir=gate_dir)
    v6 = _read_json(v6_path) if v6_path else {}
    v4 = _read_json(v4_path) if v4_path else {}
    ui_review = (v6.get("checks") or {}).get("ui_screenshot_review") or {}
    case_match = ui_review.get("case_match") or {}
    screenshot_files = _existing_ui_screenshot_files(v6, v6_path, base)
    screenshot_content = validate_application_ui_screenshots([Path(path) for path in screenshot_files])
    generated_png_source_evidence = (
        ui_review.get("generated_png_source_evidence")
        or _generated_png_source_evidence_from_report(ui_review, v6_path, base)
    )
    generated_png_source_required = bool(ui_review.get("generated_png_source_required")) or base in DEFAULT_BASES
    generated_png_source_pass = bool(ui_review.get("generated_png_source_pass")) or bool(
        generated_png_source_evidence.get("strict_source_pass")
    )
    return {
        "vision_qc_v6_with_ui_review": str(v6_path or ""),
        "vision_qc_v6_artifact_exists": bool(v6_path and v6_path.exists() and v6_path.is_file()),
        "vision_qc_v6_visual_acceptance_pass": bool(v6.get("visual_acceptance_pass")),
        "vision_qc_v6_status": str(v6.get("status") or ""),
        "ui_screenshot_review_pass": bool(ui_review.get("pass")),
        "ui_screenshot_review_method_ok": bool(ui_review.get("manual_review_method_ok")),
        "ui_screenshot_review_case_match": bool(case_match.get("pass", True)),
        "ui_screenshot_review_case_match_details": case_match,
        "manual_case_status_pass": bool(case_match.get("manual_case_status_pass")),
        "manual_visual_checklist_required": bool(case_match.get("visual_checklist_required")),
        "manual_visual_checklist_pass": bool(case_match.get("visual_checklist_pass")),
        "manual_visual_checklist_missing_items": list(case_match.get("missing_visual_checklist_items") or []),
        "manual_visual_checklist_failed_items": list(case_match.get("failed_visual_checklist_items") or []),
        "manual_visual_checklist_not_passed_items": list(case_match.get("not_passed_visual_checklist_items") or []),
        "source_ui_report": str(ui_review.get("source_ui_report") or ""),
        "source_ui_report_schema": str(ui_review.get("source_ui_report_schema") or ""),
        "source_ui_report_mode": str(ui_review.get("source_ui_report_mode") or ""),
        "source_ui_report_application_ui_ok": bool(ui_review.get("source_ui_report_application_ui_ok")),
        "ui_screenshot_files": screenshot_files,
        "ui_screenshot_file_count": len(screenshot_files),
        "ui_screenshot_content_check_pass": bool(screenshot_content.get("pass")),
        "ui_screenshot_paths_existing_application_ui": list(screenshot_content.get("passing_paths") or []),
        "ui_screenshot_content_checks": list(screenshot_content.get("checks") or []),
        "generated_png_source_required": generated_png_source_required,
        "generated_png_source_pass": generated_png_source_pass,
        "generated_png_source_evidence": generated_png_source_evidence,
        "reference_compare_v4_with_ui_review": str(v4_path or ""),
        "reference_compare_v4_artifact_exists": bool(v4_path and v4_path.exists() and v4_path.is_file()),
        "reference_compare_v4_pass": bool(v4.get("pass")),
        "reference_compare_v4_status": str(v4.get("status") or ""),
    }


def _existing_ui_screenshot_files(v6: dict[str, Any], v6_path: Path | None, base: str) -> list[str]:
    ui_review = (v6.get("checks") or {}).get("ui_screenshot_review") or {}
    manual_review_path = _artifact_path(v6.get("manual_review"), base_dir=v6_path.parent if v6_path else None)
    base_dir = manual_review_path.parent if manual_review_path else (v6_path.parent if v6_path else REPO_ROOT)
    candidates: list[Path] = []
    for item in ui_review.get("ui_screenshot_paths_existing") or ui_review.get("ui_screenshot_paths") or []:
        path = _artifact_path(item, base_dir=base_dir)
        if path is not None:
            candidates.append(path)

    source_report = _artifact_path(ui_review.get("source_ui_report"), base_dir=base_dir)
    if source_report and source_report.exists():
        report = _read_json(source_report)
        for item in report.get("entries") or []:
            if not isinstance(item, dict):
                continue
            item_base = str(item.get("base") or "").strip()
            if base and item_base and item_base != base:
                continue
            screenshot = item.get("ui_screenshot") or {}
            path_text = ""
            if isinstance(screenshot, dict):
                path_text = str(screenshot.get("path") or "")
            elif isinstance(screenshot, str):
                path_text = screenshot
            path = _artifact_path(path_text, base_dir=source_report.parent)
            if path is not None:
                candidates.append(path)

    existing: list[str] = []
    for path in candidates:
        if path.exists() and path.is_file() and path.stat().st_size > 0:
            text = str(path)
            if text not in existing:
                existing.append(text)
    return existing


def _generated_png_source_evidence_from_report(
    ui_review: dict[str, Any],
    v6_path: Path | None,
    base: str,
) -> dict[str, Any]:
    manual_review_path = _artifact_path(v6_path and _read_json(v6_path).get("manual_review"), base_dir=v6_path.parent if v6_path else None)
    base_dir = manual_review_path.parent if manual_review_path else (v6_path.parent if v6_path else REPO_ROOT)
    source_report = _artifact_path(ui_review.get("source_ui_report"), base_dir=base_dir)
    if not source_report or not source_report.exists():
        return {}
    report = _read_json(source_report)
    for item in report.get("entries") or []:
        if not isinstance(item, dict):
            continue
        item_base = str(item.get("base") or "").strip()
        if base and item_base and item_base != base:
            continue
        evidence = item.get("generated_png_evidence") or {}
        if isinstance(evidence, dict) and evidence:
            return evidence
        inferred = generated_png_source_evidence(
            base=item_base or base,
            run_dir=item.get("run_dir"),
            generated_png=item.get("generated_png"),
            source="drawing_visual_review_report_path_inference",
            base_dir=source_report.parent,
        )
        if inferred.get("path") or inferred.get("reasons"):
            return inferred
    return {}


def _issue(
    key: str,
    severity: str,
    base: str,
    evidence: dict[str, Any],
    fix_suggestion: str,
) -> dict[str, Any]:
    return {
        "key": key,
        "severity": severity,
        "base": base,
        "source": "lb26001_acceptance_gate_v4_2",
        "confidence": 1.0,
        "evidence": evidence,
        "fix_suggestion": fix_suggestion,
        "api_is_not_final_judgement": True,
    }


def audit_lb26001_acceptance_gate(
    *,
    gate_summaries: list[Path],
    staged_summary_path: Path | None = DEFAULT_STAGED_SUMMARY,
    requested_bases: list[str] | None = None,
    out_path: Path | None = None,
) -> dict[str, Any]:
    bases = requested_bases or list(DEFAULT_BASES)
    entries = _merge_gate_entries(gate_summaries)
    issues: list[dict[str, Any]] = []

    primary_entry = entries.get(PRIMARY_BASE) or {}
    primary_evidence = _entry_evidence(primary_entry, PRIMARY_BASE) if primary_entry else {}
    primary_lifecycle_evidence = _staged_lifecycle_evidence(staged_summary_path, PRIMARY_BASE)
    primary_pass = _entry_pass(primary_entry, primary_evidence) and bool(primary_lifecycle_evidence.get("displaydim_lifecycle_pass"))
    expansion_requested = any(base in DEPENDENT_BASES for base in bases)
    if expansion_requested and not primary_pass:
        issues.append(_issue(
            "lb26001_006_required_before_expansion",
            "critical",
            PRIMARY_BASE,
            {
                "requested_bases": bases,
                "primary_entry_present": bool(primary_entry),
                "primary_vision_qc_v6_visual_acceptance_pass": primary_entry.get("vision_qc_v6_visual_acceptance_pass"),
                "primary_reference_compare_v4_pass": primary_entry.get("reference_compare_v4_pass"),
                "primary_ui_screenshot_file_count": primary_evidence.get("ui_screenshot_file_count", 0),
                "primary_reasons": primary_entry.get("reasons", []),
            },
            "Pass LB26001-A-04-006 through real CAD, strict v4 compare, v6 visual QC, and application Drawing Review UI judgement before expanding to 007/008/009/015/022.",
        ))

    base_results: list[dict[str, Any]] = []
    for base in bases:
        entry = entries.get(base) or {}
        evidence = _entry_evidence(entry, base) if entry else {}
        lifecycle_evidence = _staged_lifecycle_evidence(staged_summary_path, base)
        passed = _entry_pass(entry, evidence) and bool(lifecycle_evidence.get("displaydim_lifecycle_pass"))
        if not entry:
            issues.append(_issue(
                "ui_visual_review_gate_missing",
                "major",
                base,
                {"gate_summaries": [str(path) for path in gate_summaries]},
                "Run apply_ui_visual_review_v4.py after capturing Drawing Review UI screenshots and manual judgement for this base.",
            ))
        else:
            if not evidence.get("vision_qc_v6_artifact_exists"):
                issues.append(_issue(
                    "vision_qc_v6_with_ui_review_artifact_missing",
                    "major",
                    base,
                    {
                        "vision_qc_v6_with_ui_review": entry.get("vision_qc_v6_with_ui_review"),
                        "resolved_path": evidence.get("vision_qc_v6_with_ui_review"),
                    },
                    "Run apply_ui_visual_review_v4.py so this drawing has a readable v6-with-UI report.",
                ))
            if not entry.get("vision_qc_v6_visual_acceptance_pass") or not evidence.get("vision_qc_v6_visual_acceptance_pass"):
                issues.append(_issue(
                    "vision_qc_v6_with_ui_review_not_pass",
                    "major",
                    base,
                    {
                        "vision_qc_v6_with_ui_review": entry.get("vision_qc_v6_with_ui_review"),
                        "vision_qc_v6_status": entry.get("vision_qc_v6_status"),
                        "reasons": entry.get("reasons", []),
                    },
                    "Fix the drawing and obtain a passing v6 visual QC result backed by application UI screenshot judgement.",
                ))
            if int(evidence.get("ui_screenshot_file_count") or 0) <= 0:
                issues.append(_issue(
                    "application_ui_screenshot_evidence_missing",
                    "critical" if base == PRIMARY_BASE else "major",
                    base,
                    {
                        "vision_qc_v6_with_ui_review": evidence.get("vision_qc_v6_with_ui_review"),
                        "ui_screenshot_review_pass": evidence.get("ui_screenshot_review_pass"),
                        "ui_screenshot_review_method_ok": evidence.get("ui_screenshot_review_method_ok"),
                        "ui_screenshot_review_case_match": evidence.get("ui_screenshot_review_case_match"),
                        "ui_screenshot_file_count": evidence.get("ui_screenshot_file_count"),
                        "ui_screenshot_files": evidence.get("ui_screenshot_files", []),
                    },
                    "Use the application Drawing Review UI to capture readable generated-vs-reference screenshots for this exact drawing and attach the evidence before acceptance.",
                ))
            elif not evidence.get("ui_screenshot_content_check_pass"):
                issues.append(_issue(
                    "application_ui_screenshot_content_invalid",
                    "critical" if base == PRIMARY_BASE else "major",
                    base,
                    {
                        "vision_qc_v6_with_ui_review": evidence.get("vision_qc_v6_with_ui_review"),
                        "ui_screenshot_file_count": evidence.get("ui_screenshot_file_count"),
                        "ui_screenshot_files": evidence.get("ui_screenshot_files", []),
                        "ui_screenshot_content_checks": evidence.get("ui_screenshot_content_checks", []),
                    },
                    "Capture the screenshot from the actual Drawing Review application window with the side-by-side generated/reference review visible.",
                ))
            elif not evidence.get("ui_screenshot_review_pass"):
                issues.append(_issue(
                    "application_ui_screenshot_review_not_passed",
                    "critical" if base == PRIMARY_BASE else "major",
                    base,
                    {
                        "vision_qc_v6_with_ui_review": evidence.get("vision_qc_v6_with_ui_review"),
                        "ui_screenshot_review_pass": evidence.get("ui_screenshot_review_pass"),
                        "ui_screenshot_review_method_ok": evidence.get("ui_screenshot_review_method_ok"),
                        "ui_screenshot_review_case_match": evidence.get("ui_screenshot_review_case_match"),
                        "ui_screenshot_file_count": evidence.get("ui_screenshot_file_count"),
                        "ui_screenshot_files": evidence.get("ui_screenshot_files", []),
                    },
                    "Fix the drawing defects found in the application Drawing Review UI screenshot workflow and rerun the visual judgement.",
                ))
            if not evidence.get("source_ui_report_application_ui_ok"):
                issues.append(_issue(
                    "application_ui_screenshot_source_report_invalid",
                    "critical" if base == PRIMARY_BASE else "major",
                    base,
                    {
                        "vision_qc_v6_with_ui_review": evidence.get("vision_qc_v6_with_ui_review"),
                        "source_ui_report": evidence.get("source_ui_report"),
                        "source_ui_report_schema": evidence.get("source_ui_report_schema"),
                        "source_ui_report_mode": evidence.get("source_ui_report_mode"),
                        "source_ui_report_application_ui_ok": evidence.get("source_ui_report_application_ui_ok"),
                    },
                    "Capture and attach the evidence through the application Drawing Review UI report; API/exported image reports cannot be the final judgement source.",
                ))
            if not evidence.get("manual_case_status_pass"):
                issues.append(_issue(
                    "manual_visual_case_not_pass",
                    "critical" if base == PRIMARY_BASE else "major",
                    base,
                    {
                        "vision_qc_v6_with_ui_review": evidence.get("vision_qc_v6_with_ui_review"),
                        "manual_case_status_pass": evidence.get("manual_case_status_pass"),
                        "ui_screenshot_review_case_match": evidence.get("ui_screenshot_review_case_match"),
                        "ui_screenshot_review_case_match_details": evidence.get("ui_screenshot_review_case_match_details"),
                    },
                    "Record a PASS manual visual judgement for this exact drawing from the application Drawing Review UI screenshot workflow.",
                ))
            if not evidence.get("manual_visual_checklist_required"):
                issues.append(_issue(
                    "manual_visual_checklist_missing_or_incomplete",
                    "critical" if base == PRIMARY_BASE else "major",
                    base,
                    {
                        "vision_qc_v6_with_ui_review": evidence.get("vision_qc_v6_with_ui_review"),
                        "manual_visual_checklist_required": evidence.get("manual_visual_checklist_required"),
                        "manual_visual_checklist_pass": evidence.get("manual_visual_checklist_pass"),
                        "manual_visual_checklist_missing_items": evidence.get("manual_visual_checklist_missing_items"),
                    },
                    "Record the required per-drawing visual checklist from the application Drawing Review UI before accepting this drawing.",
                ))
            if (
                evidence.get("manual_visual_checklist_required")
                and not evidence.get("manual_visual_checklist_pass")
                and evidence.get("manual_visual_checklist_missing_items")
            ):
                issues.append(_issue(
                    "manual_visual_checklist_missing_or_incomplete",
                    "critical" if base == PRIMARY_BASE else "major",
                    base,
                    {
                        "vision_qc_v6_with_ui_review": evidence.get("vision_qc_v6_with_ui_review"),
                        "manual_case_status_pass": evidence.get("manual_case_status_pass"),
                        "manual_visual_checklist_required": evidence.get("manual_visual_checklist_required"),
                        "manual_visual_checklist_pass": evidence.get("manual_visual_checklist_pass"),
                        "manual_visual_checklist_missing_items": evidence.get("manual_visual_checklist_missing_items"),
                        "manual_visual_checklist_failed_items": evidence.get("manual_visual_checklist_failed_items"),
                        "manual_visual_checklist_not_passed_items": evidence.get("manual_visual_checklist_not_passed_items"),
                    },
                    "Record a per-drawing manual visual checklist from the application Drawing Review UI before accepting this drawing.",
                ))
            if (
                evidence.get("manual_visual_checklist_required")
                and not evidence.get("manual_visual_checklist_pass")
                and evidence.get("manual_visual_checklist_failed_items")
            ):
                issues.append(_issue(
                    "manual_visual_checklist_failed",
                    "critical" if base == PRIMARY_BASE else "major",
                    base,
                    {
                        "vision_qc_v6_with_ui_review": evidence.get("vision_qc_v6_with_ui_review"),
                        "manual_case_status_pass": evidence.get("manual_case_status_pass"),
                        "manual_visual_checklist_required": evidence.get("manual_visual_checklist_required"),
                        "manual_visual_checklist_pass": evidence.get("manual_visual_checklist_pass"),
                        "manual_visual_checklist_failed_items": evidence.get("manual_visual_checklist_failed_items"),
                        "manual_visual_checklist_not_passed_items": evidence.get("manual_visual_checklist_not_passed_items"),
                    },
                    "Fix the drawing defects marked false in the application Drawing Review UI visual checklist before accepting this drawing.",
                ))
            if evidence.get("generated_png_source_required") and not evidence.get("generated_png_source_pass"):
                issues.append(_issue(
                    "generated_png_source_evidence_not_current_run",
                    "critical" if base == PRIMARY_BASE else "major",
                    base,
                    {
                        "vision_qc_v6_with_ui_review": evidence.get("vision_qc_v6_with_ui_review"),
                        "generated_png_source_required": evidence.get("generated_png_source_required"),
                        "generated_png_source_pass": evidence.get("generated_png_source_pass"),
                        "generated_png_source_evidence": evidence.get("generated_png_source_evidence"),
                    },
                    "Capture the application Drawing Review UI with the generated PNG resolved from the current run_dir/drawing output, not a legacy drw_output/v5 artifact.",
                ))
            if lifecycle_evidence.get("displaydim_lifecycle_required") and not lifecycle_evidence.get("staged_summary_exists"):
                issues.append(_issue(
                    "staged_summary_missing_for_displaydim_lifecycle",
                    "critical",
                    base,
                    lifecycle_evidence,
                    "Run the fresh LB26001-A-04-006 staged CAD validation and pass its summary.json into this acceptance gate.",
                ))
            if lifecycle_evidence.get("displaydim_lifecycle_required") and not lifecycle_evidence.get("staged_case_present"):
                issues.append(_issue(
                    "staged_case_missing_for_displaydim_lifecycle",
                    "critical",
                    base,
                    lifecycle_evidence,
                    "Use a staged summary that contains the LB26001-A-04-006 case before accepting or expanding.",
                ))
            if lifecycle_evidence.get("displaydim_lifecycle_required") and not lifecycle_evidence.get("displaydim_lifecycle_report_exists"):
                issues.append(_issue(
                    "displaydim_lifecycle_report_missing",
                    "critical",
                    base,
                    lifecycle_evidence,
                    "Run the 006 DisplayDim lifecycle audit from the fresh staged case and require the report file to exist.",
                ))
            if lifecycle_evidence.get("displaydim_lifecycle_required") and not lifecycle_evidence.get("displaydim_lifecycle_pass"):
                issues.append(_issue(
                    "displaydim_lifecycle_not_pass",
                    "critical",
                    base,
                    lifecycle_evidence,
                    "Fix real SolidWorks DisplayDim persistence and target coverage, then rerun the lifecycle audit until it passes.",
                ))
            if not evidence.get("reference_compare_v4_artifact_exists"):
                issues.append(_issue(
                    "reference_compare_v4_with_ui_review_artifact_missing",
                    "major",
                    base,
                    {
                        "reference_compare_v4_with_ui_review": entry.get("reference_compare_v4_with_ui_review"),
                        "resolved_path": evidence.get("reference_compare_v4_with_ui_review"),
                    },
                    "Run apply_ui_visual_review_v4.py so this drawing has a readable strict v4-with-UI report.",
                ))
            if not entry.get("reference_compare_v4_pass") or not evidence.get("reference_compare_v4_pass"):
                issues.append(_issue(
                    "reference_compare_v4_with_ui_review_not_pass",
                    "critical" if base == PRIMARY_BASE else "major",
                    base,
                    {
                        "reference_compare_v4_with_ui_review": entry.get("reference_compare_v4_with_ui_review"),
                        "reference_compare_v4_status": entry.get("reference_compare_v4_status"),
                        "reasons": entry.get("reasons", []),
                    },
                    "Resolve strict v4 reference comparison blockers before accepting this drawing.",
                ))
        base_results.append({
            "base": base,
            "entry_present": bool(entry),
            "pass": passed,
            "vision_qc_v6_visual_acceptance_pass": bool(entry.get("vision_qc_v6_visual_acceptance_pass")),
            "reference_compare_v4_pass": bool(entry.get("reference_compare_v4_pass")),
            "ui_screenshot_file_count": int(evidence.get("ui_screenshot_file_count") or 0),
            "ui_screenshot_files": list(evidence.get("ui_screenshot_files") or []),
            "ui_screenshot_content_check_pass": bool(evidence.get("ui_screenshot_content_check_pass")),
            "ui_screenshot_paths_existing_application_ui": list(evidence.get("ui_screenshot_paths_existing_application_ui") or []),
            "ui_screenshot_content_checks": list(evidence.get("ui_screenshot_content_checks") or []),
            "ui_screenshot_review_case_match": bool(evidence.get("ui_screenshot_review_case_match")),
            "ui_screenshot_review_case_match_details": evidence.get("ui_screenshot_review_case_match_details", {}),
            "manual_case_status_pass": bool(evidence.get("manual_case_status_pass")),
            "manual_visual_checklist_required": bool(evidence.get("manual_visual_checklist_required")),
            "manual_visual_checklist_pass": bool(evidence.get("manual_visual_checklist_pass")),
            "manual_visual_checklist_missing_items": list(evidence.get("manual_visual_checklist_missing_items") or []),
            "manual_visual_checklist_failed_items": list(evidence.get("manual_visual_checklist_failed_items") or []),
            "manual_visual_checklist_not_passed_items": list(evidence.get("manual_visual_checklist_not_passed_items") or []),
            "source_ui_report": evidence.get("source_ui_report", ""),
            "source_ui_report_schema": evidence.get("source_ui_report_schema", ""),
            "source_ui_report_mode": evidence.get("source_ui_report_mode", ""),
            "source_ui_report_application_ui_ok": bool(evidence.get("source_ui_report_application_ui_ok")),
            "generated_png_source_required": bool(evidence.get("generated_png_source_required")),
            "generated_png_source_pass": bool(evidence.get("generated_png_source_pass")),
            "generated_png_source_evidence": evidence.get("generated_png_source_evidence", {}),
            "displaydim_lifecycle_required": bool(lifecycle_evidence.get("displaydim_lifecycle_required")),
            "displaydim_lifecycle_pass": bool(lifecycle_evidence.get("displaydim_lifecycle_pass")),
            "displaydim_lifecycle_report": lifecycle_evidence.get("displaydim_lifecycle_report", ""),
            "displaydim_lifecycle_report_exists": bool(lifecycle_evidence.get("displaydim_lifecycle_report_exists")),
            "displaydim_lifecycle_report_pass": bool(lifecycle_evidence.get("displaydim_lifecycle_report_pass")),
            "displaydim_lifecycle_blocking_issue_keys": list(lifecycle_evidence.get("displaydim_lifecycle_blocking_issue_keys") or []),
            "vision_qc_v6_with_ui_review": evidence.get("vision_qc_v6_with_ui_review", ""),
            "reference_compare_v4_with_ui_review": evidence.get("reference_compare_v4_with_ui_review", ""),
            "gate_summary": entry.get("gate_summary", ""),
            "reasons": list(entry.get("reasons") or []),
        })

    status = "pass" if not issues else ("blocked_by_006" if any(item["key"] == "lb26001_006_required_before_expansion" for item in issues) else "need_review")
    payload = {
        "schema": "sw_drawing_studio.lb26001_acceptance_gate.v4_2",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "gate_summaries": [str(path) for path in gate_summaries],
        "staged_summary": str(staged_summary_path or ""),
        "requested_bases": bases,
        "primary_base": PRIMARY_BASE,
        "dependent_bases": DEPENDENT_BASES,
        "primary_pass": primary_pass,
        "expansion_requested": expansion_requested,
        "status": status,
        "pass": status == "pass",
        "api_is_not_final_judgement": True,
        "per_drawing_application_ui_screenshot_required": True,
        "base_results": base_results,
        "issues": issues,
        "reasons": sorted({str(item.get("key")) for item in issues}),
        "fix_suggestions": _unique([str(item.get("fix_suggestion") or "") for item in issues]),
    }
    if out_path is not None:
        _write_json(out_path, payload)
    return payload


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit LB26001 v4.2 UI-first acceptance gate.")
    parser.add_argument("--gate-summary", action="append", required=True, help="ui_visual_review_gate_summary.json. Repeat to merge bases.")
    parser.add_argument("--staged-summary", default=str(DEFAULT_STAGED_SUMMARY), help="Fresh staged_cad_validation_v3 summary.json for LB26001-A-04-006 lifecycle evidence.")
    parser.add_argument("--base", action="append", default=[], help="Requested base. Defaults to all six requested LB26001 drawings.")
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    out = _repo_path(args.out) if args.out else None
    payload = audit_lb26001_acceptance_gate(
        gate_summaries=[_repo_path(path) for path in args.gate_summary],
        staged_summary_path=_repo_path(args.staged_summary),
        requested_bases=list(args.base or []),
        out_path=out,
    )
    print(json.dumps({
        "pass": payload.get("pass"),
        "status": payload.get("status"),
        "primary_pass": payload.get("primary_pass"),
        "reasons": payload.get("reasons", []),
        "report": str(out or ""),
    }, ensure_ascii=False))
    return 0 if payload.get("pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
