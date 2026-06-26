from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from app.services.application_ui_screenshot_validator import validate_application_ui_screenshots
from app.services.dimension_visual_validator import validate_dimension_visuals
from app.services.drawing_object_detector import detect_drawing_objects, load_image_metrics
from app.services.generated_png_source_evidence import generated_png_source_evidence
from app.services.notes_detector import detect_notes
from app.services.titlebar_detector import detect_titlebar
from app.services.vision_issue_schema import REQUIRED_ISSUE_FIELDS


VERSION = "v6"
SCHEMA = "sw_drawing_studio.vision_qc_v6"
LB_BASE_RE = re.compile(r"LB\d{5}-[A-Z]-\d{2}-\d{3}")


def run_vision_qc_v6(
    *,
    png_path: Path | str,
    run_dir: Path | str,
    blueprint_path: Path | str | None = None,
    qc_json_path: Path | str | None = None,
    reference_png_path: Path | str | None = None,
    manual_review_path: Path | str | None = None,
    out_path: Path | str | None = None,
) -> dict[str, Any]:
    start = time.time()
    run_dir = Path(run_dir)
    png_path = Path(png_path)
    qc_json_path = Path(qc_json_path) if qc_json_path else None
    blueprint_path = _resolve_blueprint_path(run_dir, blueprint_path)
    reference_png_path = Path(reference_png_path) if reference_png_path else None
    manual_review_path = Path(manual_review_path) if manual_review_path else None

    blueprint, blueprint_error = _read_json(blueprint_path)
    qc_data, qc_error = _read_json(qc_json_path)
    manual_review, manual_review_error = _read_json(manual_review_path)
    inferred_base = _drawing_base(blueprint, png_path, reference_png_path, manual_review)
    if blueprint and inferred_base and not str(blueprint.get("base") or "").strip():
        blueprint = dict(blueprint)
        blueprint["base"] = inferred_base
    issues: list[dict[str, Any]] = []

    result: dict[str, Any] = {
        "schema": SCHEMA,
        "version": VERSION,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "base": str(blueprint.get("base") or inferred_base or ""),
        "source_png": str(png_path),
        "reference_png": str(reference_png_path) if reference_png_path else "",
        "manual_review": str(manual_review_path) if manual_review_path else "",
        "run_dir": str(run_dir),
        "drawing_blueprint": str(blueprint_path) if blueprint_path else "",
        "source_qc": str(qc_json_path) if qc_json_path else "",
        "success": False,
        "visual_acceptance_pass": False,
        "api_is_not_final_judgement": True,
        "issues": issues,
        "summary": {
            "total": 0,
            "critical": 0,
            "major": 0,
            "minor": 0,
            "info": 0,
        },
        "checks": {},
        "duration_s": 0.0,
    }

    if not png_path.exists():
        issues.append(_issue(
            "png_missing",
            "critical",
            [0.0, 0.0, 1.0, 1.0],
            "vision_qc_v6",
            1.0,
            {"png_path": str(png_path)},
            "Generate a fresh PNG from the current PDF/SLDDRW before visual acceptance.",
            "PNG preview is missing; visual review cannot proceed.",
        ))
        _finalize(result, out_path or run_dir / "qc" / "vision_qc_v6.json", start)
        return result

    if not blueprint:
        issues.append(_issue(
            "drawing_blueprint_missing",
            "major",
            [0.0, 0.0, 1.0, 1.0],
            "drawing_blueprint",
            0.95,
            {"blueprint_path": str(blueprint_path or ""), "read_error": blueprint_error},
            "Create drawing_blueprint.json before accepting the generated drawing.",
            "DrawingBlueprint is missing or unreadable.",
        ))
    if qc_error and qc_json_path:
        issues.append(_issue(
            "qc_json_read_warning",
            "minor",
            [0.0, 0.0, 1.0, 1.0],
            "geometry_qc",
            0.75,
            {"qc_json_path": str(qc_json_path), "read_error": qc_error},
            "Regenerate QC JSON so image and geometry evidence can be correlated.",
            "QC JSON could not be read.",
        ))

    drawing_objects = detect_drawing_objects(png_path)
    result["checks"]["drawing_objects"] = drawing_objects
    if not drawing_objects.get("success"):
        issues.append(_issue(
            "png_read_error",
            "critical",
            [0.0, 0.0, 1.0, 1.0],
            "image_detector",
            1.0,
            drawing_objects,
            "Regenerate the PNG and rerun visual QC.",
            "PNG exists but could not be decoded.",
        ))
        _finalize(result, out_path or run_dir / "qc" / "vision_qc_v6.json", start)
        return result
    if not drawing_objects.get("ink_present"):
        issues.append(_issue(
            "png_visual_blank",
            "critical",
            [0.0, 0.0, 1.0, 1.0],
            "image_detector",
            0.98,
            {"ink_ratio": drawing_objects.get("ink_ratio"), "ink_bbox": drawing_objects.get("ink_bbox")},
            "Regenerate drawing views and render a fresh PNG.",
            "Generated PNG is visually blank or nearly blank.",
        ))

    required_views = _required_view_slots(blueprint)
    if required_views:
        detected_views = int(drawing_objects.get("view_frame_count") or 0)
        if detected_views < min(len(required_views), 2):
            issues.append(_issue(
                "view_frames_lower_than_blueprint",
                "major",
                _bbox_or_full(drawing_objects.get("ink_bbox")),
                "drawing_object_detector",
                0.55,
                {"required_view_slots": required_views, "detected_view_frame_count": detected_views},
                "Review view creation against DrawingBlueprint.view_plan and rerun UI screenshot review.",
                "Detected view-like regions are lower than the DrawingBlueprint expectation.",
            ))

    titlebar = detect_titlebar(png_path, blueprint=blueprint)
    result["checks"]["titlebar"] = titlebar
    sheet_artifacts = _reference_sheet_template_artifact_check(blueprint, titlebar)
    result["checks"]["reference_sheet_template_artifacts"] = sheet_artifacts
    if sheet_artifacts.get("default_template_artifacts_present"):
        issues.append(_issue(
            "reference_titleblock_artifacts_present",
            "major",
            titlebar.get("box_norm") or [0.68, 0.0, 0.32, 0.18],
            "reference_sheet_template_policy",
            0.78,
            sheet_artifacts,
            "Remove the default GB frame/titleblock and render only the compact reference-style sheet fields before screenshot review.",
            "The same-name reference policy forbids default template/titleblock artifacts, but the generated titlebar region still looks like a large template grid.",
        ))
    elif not titlebar.get("detected") and not sheet_artifacts.get("default_template_artifacts_forbidden"):
        issues.append(_issue(
            "titlebar_missing_or_empty",
            "major",
            titlebar.get("box_norm") or [0.68, 0.0, 0.32, 0.18],
            "titlebar_detector",
            0.7,
            titlebar,
            "Fill or render the titlebar from DrawingBlueprint.titlebar_plan before acceptance.",
            "Titlebar region has too little visual evidence.",
        ))

    notes = detect_notes(png_path, blueprint=blueprint)
    result["checks"]["notes"] = notes
    if notes.get("requires_technical_requirements") and not notes.get("technical_requirements_detected"):
        issues.append(_issue(
            "technical_requirements_missing_or_empty",
            "major",
            notes.get("box_norm") or [0.58, 0.18, 0.4, 0.17],
            "notes_detector",
            0.72,
            notes,
            "Insert notes_plan technical requirements into the learned notes area and rerun screenshot review.",
            "Required notes/technical requirements are not visually proven.",
        ))

    dimensions = validate_dimension_visuals(png_path, blueprint=blueprint, drawing_objects=drawing_objects)
    result["checks"]["dimension_visuals"] = dimensions
    if not dimensions.get("visual_dimension_coverage_pass"):
        issues.append(_issue(
            "dimension_visual_candidates_lower_than_blueprint",
            "major",
            _bbox_or_full(drawing_objects.get("ink_bbox")),
            "dimension_visual_validator",
            0.62,
            dimensions,
            "Generate real DisplayDim objects according to DrawingBlueprint.dimension_plan; do not replace them with Notes.",
            "Dimension text/arrow visual candidates are below the DrawingBlueprint requirement.",
        ))
    if not dimensions.get("visual_dimension_density_pass"):
        issues.append(_issue(
            "dimension_visual_overdense",
            "major",
            _bbox_or_full(drawing_objects.get("ink_bbox")),
            "dimension_visual_validator",
            0.58,
            dimensions,
            "Reduce redundant dimension placement and follow reference-specific dimension grouping.",
            "Dimension visual candidates appear too dense for the blueprint baseline.",
        ))
    if not dimensions.get("visual_dimension_cluster_pass"):
        issues.append(_issue(
            "dimension_visual_clustered_unreadable",
            "major",
            dimensions.get("dimension_text_cluster_bbox_norm") or _bbox_or_full(drawing_objects.get("ink_bbox")),
            "dimension_visual_validator",
            0.64,
            dimensions,
            "Arrange reference-intent dimensions into readable lanes around the learned view layout; reject clustered AutoDimension-like output.",
            "Dimension text candidates are clustered into a small local region, matching the UI screenshot readability failure.",
        ))

    symbols = _symbol_checks(blueprint, drawing_objects)
    result["checks"]["symbols"] = symbols
    for item in symbols.get("missing", []):
        issues.append(_issue(
            item["key"],
            "minor",
            _bbox_or_full(drawing_objects.get("ink_bbox")),
            "drawing_object_detector",
            item["confidence"],
            item,
            item["fix_suggestion"],
            item["description"],
        ))

    reference_callouts = _reference_callout_checks(blueprint, manual_review, inferred_base)
    result["checks"]["reference_callouts"] = reference_callouts
    if reference_callouts.get("required") and not reference_callouts.get("pass"):
        issues.append(_issue(
            "reference_callout_visual_check_missing",
            "major",
            reference_callouts.get("bbox_norm") or _bbox_or_full(drawing_objects.get("ink_bbox")),
            "reference_callout_ui_review",
            0.82,
            reference_callouts,
            "In the Drawing Review UI screenshot judgement, explicitly confirm each same-name reference callout such as M4-6H, hole-size callouts, and Ra3.2/rest roughness before accepting 006.",
            "Reference manufacturing callouts are required, but the application UI screenshot review has not proven every required callout is present.",
        ))

    if reference_png_path and reference_png_path.exists():
        reference_compare = _compare_reference_png(png_path, reference_png_path)
        result["checks"]["reference_visual_compare"] = reference_compare
        if not reference_compare.get("coarse_layout_match", False):
            issues.append(_issue(
                "reference_visual_layout_mismatch",
                "major",
                _bbox_or_full(drawing_objects.get("ink_bbox")),
                "reference_visual_compare",
                0.6,
                reference_compare,
                "Align generated layout to the same-name reference and rerun application UI screenshot review.",
                "Generated PNG screenshot-grid ink layout differs from the same-name reference PNG.",
            ))

    ui_review = _ui_review_check(blueprint, manual_review, manual_review_error, manual_review_path, inferred_base)
    result["checks"]["ui_screenshot_review"] = ui_review
    if not ui_review.get("pass", False):
        issues.append(_issue(
            "manual_ui_screenshot_review_required",
            "major",
            [0.0, 0.0, 1.0, 1.0],
            "ui_screenshot_review",
            1.0,
            ui_review,
            "Open the generated and same-name reference drawings in the application Drawing Review UI, capture a screenshot, and record a passing manual judgement before acceptance.",
            "DrawingBlueprint requires application UI screenshot review; no passing manual UI judgement is attached.",
        ))

    result["checks"]["geometry_qc_supporting"] = _supporting_geometry_summary(qc_data)
    _finalize(result, out_path or run_dir / "qc" / "vision_qc_v6.json", start)
    return result


def _drawing_base(
    blueprint: dict[str, Any],
    png_path: Path,
    reference_png_path: Path | None,
    manual_review: dict[str, Any],
) -> str:
    explicit = str(blueprint.get("base") or "").strip()
    if explicit:
        return explicit
    for value in [png_path, reference_png_path]:
        match = LB_BASE_RE.search(str(value or ""))
        if match:
            return match.group(0)
    for container_key in ["cases", "entries"]:
        for item in manual_review.get(container_key) or []:
            if not isinstance(item, dict):
                continue
            for key in ["base", "generated_png", "reference_png", "ui_screenshot"]:
                match = LB_BASE_RE.search(str(item.get(key) or ""))
                if match:
                    return match.group(0)
    return ""


def _resolve_blueprint_path(run_dir: Path, path: Path | str | None) -> Path | None:
    if path:
        return Path(path)
    candidate = run_dir / "qc" / "drawing_blueprint.json"
    return candidate if candidate.exists() else None


def _read_json(path: Path | None) -> tuple[dict[str, Any], str]:
    if not path:
        return {}, "path_missing"
    if not path.exists():
        return {}, "file_missing"
    try:
        return json.loads(path.read_text(encoding="utf-8-sig")), ""
    except Exception as exc:
        return {}, str(exc)


def _required_view_slots(blueprint: dict[str, Any]) -> list[str]:
    result: list[str] = []
    for item in blueprint.get("view_plan") or []:
        if not isinstance(item, dict) or item.get("required") is False:
            continue
        slot = str(item.get("slot") or "").strip()
        if slot:
            result.append(slot)
    return result


def _symbol_checks(blueprint: dict[str, Any], drawing_objects: dict[str, Any]) -> dict[str, Any]:
    annotation = blueprint.get("annotation_plan") or {}
    notes = blueprint.get("notes_plan") or {}
    missing: list[dict[str, Any]] = []
    if annotation.get("centerlines_required") and int(drawing_objects.get("centerline_candidate_count") or 0) <= 0:
        missing.append({
            "key": "centerline_visual_missing",
            "confidence": 0.5,
            "description": "Centerline candidates are not visually detected.",
            "fix_suggestion": "Add centerlines/center marks where required by the blueprint/reference.",
        })
    if annotation.get("center_marks_required") and int(drawing_objects.get("center_mark_candidate_count") or 0) <= 0:
        missing.append({
            "key": "center_mark_visual_missing",
            "confidence": 0.5,
            "description": "Center mark candidates are not visually detected.",
            "fix_suggestion": "Add center marks for circular/hole features before acceptance.",
        })
    if annotation.get("section_arrows_required") and int(drawing_objects.get("section_arrow_candidate_count") or 0) <= 0:
        missing.append({
            "key": "section_arrow_visual_missing",
            "confidence": 0.5,
            "description": "Section arrow candidates are not visually detected.",
            "fix_suggestion": "Create section arrows only when the DrawingBlueprint requires a section view.",
        })
    required_notes = " ".join(str(x) for x in (notes.get("required_notes") or notes.get("raw_reference_notes") or []))
    if ("Ra" in required_notes or "roughness" in required_notes.lower()) and not annotation.get("roughness_required"):
        missing.append({
            "key": "roughness_plan_not_marked_required",
            "confidence": 0.65,
            "description": "Reference notes mention roughness but annotation_plan does not require a roughness symbol.",
            "fix_suggestion": "Propagate roughness requirements from notes/reference profile into annotation_plan.",
        })
    return {
        "centerline_candidate_count": drawing_objects.get("centerline_candidate_count", 0),
        "center_mark_candidate_count": drawing_objects.get("center_mark_candidate_count", 0),
        "section_arrow_candidate_count": drawing_objects.get("section_arrow_candidate_count", 0),
        "missing": missing,
    }


def _reference_callout_checks(
    blueprint: dict[str, Any],
    manual_review: dict[str, Any],
    base: str = "",
) -> dict[str, Any]:
    # reference_callout_visual_check_missing:
    # This is a UI-evidence gate for manufacturing callouts, not a DisplayDim
    # substitute and not an API acceptance shortcut.
    callouts = _required_reference_callouts(blueprint)
    if not callouts:
        return {
            "required": False,
            "pass": True,
            "source": "DrawingBlueprint.dimension_plan.reference_callouts",
            "api_is_not_final_judgement": True,
            "notes_do_not_count_as_display_dim": True,
        }
    checklist = _manual_reference_callout_checklist(manual_review, base)
    confirmed: list[str] = []
    missing: list[str] = []
    failed: list[str] = []
    callout_results: list[dict[str, Any]] = []
    for item in callouts:
        key = str(item.get("key") or "").strip()
        expected_type = str(item.get("expected_type") or "").strip()
        source_text = str(
            ((item.get("source_reference_evidence") or {}).get("source_text"))
            or item.get("reference_value")
            or ""
        )
        aliases = _reference_callout_aliases(key, expected_type, source_text)
        value = None
        matched_alias = ""
        for alias in aliases:
            if alias in checklist:
                value = checklist.get(alias)
                matched_alias = alias
                break
        if value is True:
            confirmed.append(key)
        elif value is False:
            failed.append(key)
        else:
            missing.append(key)
        callout_results.append({
            "key": key,
            "expected_type": expected_type,
            "source_text": source_text,
            "confirmed": value is True,
            "failed": value is False,
            "matched_alias": matched_alias,
            "create_as": str(item.get("create_as") or ""),
            "forbid_note_substitution_for_displaydim": bool(
                item.get("forbid_note_substitution_for_displaydim")
                or item.get("forbid_note_substitution")
            ),
        })
    layout = blueprint.get("layout_plan") or {}
    bbox = layout.get("notes_box_norm") or [0.58, 0.18, 0.40, 0.17]
    return {
        "required": True,
        "pass": not missing and not failed,
        "source": "DrawingBlueprint.dimension_plan.reference_callouts",
        "base": base,
        "required_count": len(callouts),
        "confirmed_count": len(confirmed),
        "confirmed_callouts": confirmed,
        "missing_required_callouts": missing,
        "failed_required_callouts": failed,
        "manual_callout_checklist_present": bool(checklist),
        "manual_callout_checklist_keys": sorted(checklist),
        "callouts": callout_results,
        "bbox_norm": bbox,
        "api_is_not_final_judgement": True,
        "ui_screenshot_acceptance_required": True,
        "notes_do_not_count_as_display_dim": True,
    }


def _required_reference_callouts(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    dimension_plan = blueprint.get("dimension_plan") or {}
    raw = (
        blueprint.get("reference_callouts")
        or dimension_plan.get("reference_callouts")
        or []
    )
    result: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        fallback = str(item.get("fallback_policy") or "").strip()
        key = str(item.get("key") or "").strip()
        if not key:
            continue
        if fallback.startswith("do_not_create_unless"):
            continue
        if item.get("is_manufacturing_dimension") is False:
            continue
        result.append(dict(item))
    return result


def _manual_reference_callout_checklist(manual_review: dict[str, Any], base: str = "") -> dict[str, bool]:
    keys = [
        "reference_callout_checklist",
        "callout_checklist",
        "manufacturing_callout_checklist",
        "ui_callout_checklist",
    ]
    merged: dict[str, bool] = {}

    def add_values(container: dict[str, Any]) -> None:
        for key in keys:
            value = container.get(key)
            if not isinstance(value, dict):
                continue
            for raw_key, raw_value in value.items():
                normalized = _normalize_callout_key(raw_key)
                if normalized:
                    merged[normalized] = raw_value is True

    add_values(manual_review)
    for container_key in ["cases", "entries"]:
        for item in manual_review.get(container_key) or []:
            if not isinstance(item, dict):
                continue
            entry_base = str(item.get("base") or "")
            if base and entry_base and entry_base != base:
                continue
            add_values(item)
    return merged


def _reference_callout_aliases(key: str, expected_type: str, source_text: str) -> list[str]:
    aliases = [
        _normalize_callout_key(key),
        _normalize_callout_key(expected_type),
        _normalize_callout_key(source_text),
    ]
    if "m4" in _normalize_callout_key(source_text) or "m4" in _normalize_callout_key(key):
        aliases.extend([
            "m4_6h",
            "thread_callout_m4_6h",
            "thread_callout",
        ])
    if "3_2" in _normalize_callout_key(source_text) or "roughness" in _normalize_callout_key(expected_type):
        aliases.extend([
            "ra3_2",
            "surface_finish_rest_3_2",
            "surface_finish_callout",
            "roughness",
        ])
    if "3_3" in _normalize_callout_key(source_text) or "hole" in _normalize_callout_key(key):
        aliases.extend([
            "hole_callout",
            "hole_callout_4x3_3",
            "hole_diameter",
            "hole_size_callout",
            "4_3_3",
        ])
    return [item for item in _unique_text(aliases) if item]


def _normalize_callout_key(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    replacements = {
        "⌀": "diameter",
        "φ": "diameter",
        "Φ": "diameter",
        "√": "",
        "-": "_",
        ".": "_",
        " ": "_",
        "/": "_",
        "\\": "_",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"[^a-z0-9_\u4e00-\u9fff]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text


def _reference_sheet_template_artifact_check(
    blueprint: dict[str, Any],
    titlebar: dict[str, Any],
) -> dict[str, Any]:
    layout = (blueprint or {}).get("layout_plan") or {}
    policy = layout.get("sheet_template_policy") or {}
    policy = policy if isinstance(policy, dict) else {}
    policy_name = str(policy.get("policy") or "")
    forbidden = (
        policy.get("default_template_artifacts_allowed") is False
        or policy.get("skip_builtin_gb_frame_titleblock") is True
        or policy_name == "strip_default_template_artifacts"
    )
    line_count = int(titlebar.get("line_candidate_count") or 0)
    ink_density = float(titlebar.get("ink_density") or 0.0)
    grid_like = bool(titlebar.get("detected")) and (line_count >= 3 or ink_density >= 0.0025)
    return {
        "source": "DrawingBlueprint.layout_plan.sheet_template_policy",
        "policy": policy_name,
        "visible_titlebar_mode": str(policy.get("visible_titlebar_mode") or ""),
        "default_template_artifacts_forbidden": bool(forbidden),
        "default_template_artifacts_present": bool(forbidden and grid_like),
        "titlebar_detected": bool(titlebar.get("detected")),
        "titlebar_line_candidate_count": line_count,
        "titlebar_ink_density": ink_density,
        "api_is_not_final_judgement": True,
    }


def _ui_review_check(
    blueprint: dict[str, Any],
    manual_review: dict[str, Any],
    manual_review_error: str,
    manual_review_path: Path | None,
    fallback_base: str = "",
) -> dict[str, Any]:
    validation = blueprint.get("validation_plan") or {}
    required = bool(validation.get("require_ui_visual_review", True))
    if not required:
        return {
            "required": False,
            "pass": True,
            "source": "drawing_blueprint.validation_plan",
        }
    status = str(
        manual_review.get("overall_status")
        or manual_review.get("status")
        or manual_review.get("verdict")
        or ""
    ).lower()
    passed = status in {"pass", "passed", "ok", "accepted"} or manual_review.get("visual_acceptance_pass") is True
    method = str(manual_review.get("method") or manual_review.get("review_mode") or "").lower()
    method_ok = (
        "application" in method
        and ("drawing_review" in method or "drawing review" in method)
        and "screenshot" in method
    )
    base = str(blueprint.get("base") or fallback_base or "")
    screenshot_evidence = _manual_review_screenshot_evidence(manual_review, manual_review_path, base)
    case_match = _manual_review_case_match(manual_review, base)
    evidence_ok = bool(screenshot_evidence.get("ui_screenshot_evidence_present"))
    content_ok = bool(screenshot_evidence.get("ui_screenshot_content_check_pass"))
    report_ok = bool(screenshot_evidence.get("source_ui_report_application_ui_ok"))
    case_ok = bool(case_match.get("pass"))
    source_blueprint = blueprint
    if base and not str(blueprint.get("base") or "").strip():
        source_blueprint = dict(blueprint)
        source_blueprint["base"] = base
    source_required = _generated_png_source_required(source_blueprint)
    source_ok = (not source_required) or bool(screenshot_evidence.get("generated_png_source_pass"))
    return {
        "required": True,
        "pass": bool(passed and method_ok and evidence_ok and content_ok and report_ok and case_ok and source_ok),
        "manual_review_status": status,
        "manual_review_error": manual_review_error,
        "manual_review_method": method,
        "manual_review_method_ok": method_ok,
        "ui_screenshot_evidence_present": evidence_ok,
        "ui_screenshot_paths": screenshot_evidence.get("ui_screenshot_paths", []),
        "ui_screenshot_paths_existing": screenshot_evidence.get("ui_screenshot_paths_existing", []),
        "ui_screenshot_paths_existing_application_ui": screenshot_evidence.get("ui_screenshot_paths_existing_application_ui", []),
        "ui_screenshot_content_check_pass": content_ok,
        "ui_screenshot_content_checks": screenshot_evidence.get("ui_screenshot_content_checks", []),
        "source_ui_report": screenshot_evidence.get("source_ui_report", ""),
        "source_ui_report_exists": screenshot_evidence.get("source_ui_report_exists", False),
        "source_ui_report_schema": screenshot_evidence.get("source_ui_report_schema", ""),
        "source_ui_report_mode": screenshot_evidence.get("source_ui_report_mode", ""),
        "source_ui_report_application_ui_ok": report_ok,
        "case_match": case_match,
        "generated_png_source_required": source_required,
        "generated_png_source_pass": bool(screenshot_evidence.get("generated_png_source_pass")),
        "generated_png_source_evidence": screenshot_evidence.get("generated_png_source_evidence", {}),
        "source": "application_ui_screenshot_review",
        "api_is_not_final_judgement": True,
    }


def _manual_review_screenshot_evidence(
    manual_review: dict[str, Any],
    manual_review_path: Path | None,
    base: str = "",
) -> dict[str, Any]:
    paths: list[str] = []
    generated_png_evidence: dict[str, Any] = {}
    source_report_schema = ""
    source_report_mode = ""
    source_report_application_ui_ok = False
    for key in ["ui_screenshot", "application_ui_screenshot", "screenshot"]:
        value = manual_review.get(key)
        if isinstance(value, str) and value:
            paths.append(value)
    for container_key in ["cases", "entries"]:
        for item in manual_review.get(container_key) or []:
            if not isinstance(item, dict):
                continue
            for key in ["ui_screenshot", "application_ui_screenshot", "screenshot"]:
                value = item.get(key)
                if isinstance(value, str) and value:
                    paths.append(value)

    source_report = str(manual_review.get("source_ui_report") or manual_review.get("drawing_visual_review_report") or "")
    report_exists = False
    if source_report:
        report_path = _resolve_review_path(source_report, manual_review_path)
        report_exists = report_path.exists() and report_path.stat().st_size > 0
        if report_exists:
            report, _error = _read_json(report_path)
            source_report_schema = str(report.get("schema") or "")
            source_report_mode = str(report.get("mode") or "")
            source_report_application_ui_ok = _source_ui_report_application_ui_ok(report)
            for entry in report.get("entries") or []:
                if not isinstance(entry, dict):
                    continue
                entry_base = str(entry.get("base") or "")
                if base and entry_base and entry_base != base:
                    continue
                ui_screenshot = entry.get("ui_screenshot") or {}
                path_text = ""
                if isinstance(ui_screenshot, dict):
                    path_text = str(ui_screenshot.get("path") or "")
                elif isinstance(ui_screenshot, str):
                    path_text = ui_screenshot
                if path_text:
                    paths.append(path_text)
                evidence = entry.get("generated_png_evidence") or {}
                if isinstance(evidence, dict) and evidence and not generated_png_evidence:
                    generated_png_evidence = evidence
                if not generated_png_evidence:
                    inferred = generated_png_source_evidence(
                        base=entry_base or base,
                        run_dir=entry.get("run_dir"),
                        generated_png=entry.get("generated_png"),
                        source="drawing_visual_review_report_path_inference",
                        base_dir=report_path.parent,
                    )
                    if inferred.get("path") or inferred.get("reasons"):
                        generated_png_evidence = inferred

    existing = []
    existing_paths: list[Path] = []
    for item in _unique_text(paths):
        path = _resolve_review_path(item, manual_review_path)
        if path.exists() and path.is_file() and path.stat().st_size > 0:
            existing.append(item)
            existing_paths.append(path)
    screenshot_content = validate_application_ui_screenshots(existing_paths)

    return {
        "ui_screenshot_evidence_present": bool(existing),
        "ui_screenshot_paths": _unique_text(paths),
        "ui_screenshot_paths_existing": existing,
        "ui_screenshot_paths_existing_application_ui": screenshot_content.get("passing_paths", []),
        "ui_screenshot_content_check_pass": bool(screenshot_content.get("pass")),
        "ui_screenshot_content_checks": screenshot_content.get("checks", []),
        "source_ui_report": source_report,
        "source_ui_report_exists": report_exists,
        "source_ui_report_schema": source_report_schema,
        "source_ui_report_mode": source_report_mode,
        "source_ui_report_application_ui_ok": source_report_application_ui_ok,
        "generated_png_source_pass": bool(generated_png_evidence.get("strict_source_pass")),
        "generated_png_source_evidence": generated_png_evidence,
    }


def _source_ui_report_application_ui_ok(report: dict[str, Any]) -> bool:
    schema = str(report.get("schema") or "").lower()
    mode = str(report.get("mode") or "").lower()
    return (
        "drawing_visual_review_ui" in schema
        and "application" in mode
        and "screenshot" in mode
    )


def _generated_png_source_required(blueprint: dict[str, Any]) -> bool:
    base = str(blueprint.get("base") or "")
    if base in {
        "LB26001-A-04-006",
        "LB26001-A-04-007",
        "LB26001-A-04-008",
        "LB26001-A-04-009",
        "LB26001-A-04-015",
        "LB26001-A-04-022",
    }:
        return True
    dimension_plan = blueprint.get("dimension_plan") or {}
    return bool(dimension_plan.get("dimension_targets"))


REQUIRED_MANUAL_VISUAL_CHECKS = (
    "reference_match",
    "view_layout",
    "display_dimensions",
    "dimension_readability",
    "title_block",
    "manufacturing_notes",
)


def _manual_review_case_match(manual_review: dict[str, Any], base: str) -> dict[str, Any]:
    if not base:
        return {"required": False, "pass": True, "reason": "blueprint_base_missing"}
    entries = []
    for container_key in ["cases", "entries"]:
        for item in manual_review.get(container_key) or []:
            if isinstance(item, dict):
                entries.append(item)
    if not entries:
        return {
            "required": True,
            "pass": False,
            "reason": "no_case_entries",
            "base": base,
            "visual_checklist_required": True,
            "required_visual_checklist_items": list(REQUIRED_MANUAL_VISUAL_CHECKS),
        }
    matching = [item for item in entries if str(item.get("base") or "") == base]
    if not matching:
        return {"required": True, "pass": False, "reason": "base_missing", "base": base}
    passed_values = []
    status_values = []
    checklist_values = []
    missing_checklist_items: list[str] = []
    failed_checklist_items: list[str] = []
    for item in matching:
        status = str(
            item.get("manual_status")
            or item.get("verdict")
            or item.get("status")
            or ""
        ).lower()
        status_ok = status in {"pass", "passed", "ok", "accepted"} or item.get("visual_acceptance_pass") is True
        checklist = _manual_visual_checklist_result(item)
        status_values.append(status_ok)
        checklist_values.append(bool(checklist.get("pass")))
        for key in checklist.get("missing", []):
            if key not in missing_checklist_items:
                missing_checklist_items.append(key)
        for key in checklist.get("failed", []):
            if key not in failed_checklist_items:
                failed_checklist_items.append(key)
        passed_values.append(status_ok and bool(checklist.get("pass")))
    return {
        "required": True,
        "pass": all(passed_values),
        "base": base,
        "matching_count": len(matching),
        "manual_case_status_pass": all(status_values),
        "visual_checklist_required": True,
        "visual_checklist_pass": all(checklist_values),
        "required_visual_checklist_items": list(REQUIRED_MANUAL_VISUAL_CHECKS),
        "missing_visual_checklist_items": missing_checklist_items,
        "failed_visual_checklist_items": failed_checklist_items,
        "not_passed_visual_checklist_items": sorted(set(missing_checklist_items + failed_checklist_items)),
    }


def _manual_visual_checklist_result(item: dict[str, Any]) -> dict[str, Any]:
    raw = (
        item.get("visual_checklist")
        or item.get("ui_visual_checklist")
        or item.get("checklist")
        or {}
    )
    checklist = raw if isinstance(raw, dict) else {}
    missing = [key for key in REQUIRED_MANUAL_VISUAL_CHECKS if key not in checklist or checklist.get(key) is None]
    failed = [key for key in REQUIRED_MANUAL_VISUAL_CHECKS if checklist.get(key) is False]
    return {
        "required": True,
        "pass": not missing and not failed,
        "missing": missing,
        "failed": failed,
        "not_passed": sorted(set(missing + failed)),
        "provided": sorted(str(key) for key in checklist),
    }


def _resolve_review_path(path_text: str, manual_review_path: Path | None) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    if manual_review_path is not None:
        local = manual_review_path.parent / path
        if local.exists():
            return local
    return Path.cwd() / path


def _unique_text(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def _compare_reference_png(generated_png: Path, reference_png: Path) -> dict[str, Any]:
    generated = detect_drawing_objects(generated_png)
    reference = detect_drawing_objects(reference_png)
    if not generated.get("success") or not reference.get("success"):
        return {"success": False, "reason": "png_decode_failed", "generated": generated, "reference": reference}
    g = generated.get("ink_bbox") or [0, 0, 0, 0]
    r = reference.get("ink_bbox") or [0, 0, 0, 0]
    g_center = [g[0] + g[2] / 2.0, g[1] + g[3] / 2.0]
    r_center = [r[0] + r[2] / 2.0, r[1] + r[3] / 2.0]
    center_delta = abs(g_center[0] - r_center[0]) + abs(g_center[1] - r_center[1])
    area_g = max(0.0, g[2] * g[3])
    area_r = max(0.0001, r[2] * r[3])
    area_ratio = area_g / area_r
    generated_grid = _ink_grid_signature(generated_png)
    reference_grid = _ink_grid_signature(reference_png)
    grid_l1_delta = sum(
        abs(float(gv) - float(rv))
        for gv, rv in zip(generated_grid["ink_shares"], reference_grid["ink_shares"])
    )
    generated_cells = {tuple(cell) for cell in generated_grid["occupied_cells"]}
    reference_cells = {tuple(cell) for cell in reference_grid["occupied_cells"]}
    cell_union = generated_cells | reference_cells
    cell_intersection = generated_cells & reference_cells
    occupied_cell_jaccard = len(cell_intersection) / len(cell_union) if cell_union else 1.0
    bbox_layout_match = center_delta <= 0.18 and 0.45 <= area_ratio <= 2.2
    grid_layout_match = grid_l1_delta <= 0.72 and occupied_cell_jaccard >= 0.45
    return {
        "success": True,
        "generated_ink_bbox": g,
        "reference_ink_bbox": r,
        "center_delta": round(center_delta, 4),
        "area_ratio": round(area_ratio, 4),
        "bbox_layout_match": bbox_layout_match,
        "grid_rows": generated_grid["rows"],
        "grid_cols": generated_grid["cols"],
        "generated_grid_ink_shares": generated_grid["ink_shares"],
        "reference_grid_ink_shares": reference_grid["ink_shares"],
        "generated_occupied_cells": generated_grid["occupied_cells"],
        "reference_occupied_cells": reference_grid["occupied_cells"],
        "grid_l1_delta": round(grid_l1_delta, 4),
        "occupied_cell_jaccard": round(occupied_cell_jaccard, 4),
        "grid_layout_match": grid_layout_match,
        "coarse_layout_match": bbox_layout_match and grid_layout_match,
    }


def _ink_grid_signature(png_path: Path, rows: int = 3, cols: int = 4) -> dict[str, Any]:
    metrics = load_image_metrics(png_path)
    mask = metrics.mask
    height, width = mask.shape
    total_ink = max(1, int(mask.sum()))
    ink_ratios: list[float] = []
    ink_shares: list[float] = []
    occupied_cells: list[list[int]] = []

    for row in range(rows):
        top = int(round(row * height / rows))
        bottom = int(round((row + 1) * height / rows))
        for col in range(cols):
            left = int(round(col * width / cols))
            right = int(round((col + 1) * width / cols))
            cell = mask[top:bottom, left:right]
            cell_area = max(1, int(cell.size))
            cell_ink = int(cell.sum())
            ink_ratio = float(cell_ink) / float(cell_area)
            ink_share = float(cell_ink) / float(total_ink)
            ink_ratios.append(round(ink_ratio, 5))
            ink_shares.append(round(ink_share, 5))
            if ink_ratio >= 0.003 or ink_share >= 0.035:
                occupied_cells.append([row, col])

    return {
        "rows": rows,
        "cols": cols,
        "ink_ratios": ink_ratios,
        "ink_shares": ink_shares,
        "occupied_cells": occupied_cells,
        "total_ink": total_ink,
    }


def _supporting_geometry_summary(qc_data: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": "geometry_qc_supporting_only",
        "pass": qc_data.get("pass"),
        "display_dim_count": qc_data.get("display_dim_count"),
        "dimension_grade": qc_data.get("dimension_grade", ""),
        "hard_fail": qc_data.get("hard_fail", []),
        "warnings": qc_data.get("warnings", []),
        "api_is_not_final_judgement": True,
    }


def _issue(
    key: str,
    severity: str,
    bbox: list[float],
    source: str,
    confidence: float,
    evidence: Any,
    fix_suggestion: str,
    description: str,
) -> dict[str, Any]:
    issue = {
        "key": key,
        "severity": severity,
        "bbox": _issue_bbox(bbox),
        "source": source,
        "confidence": round(max(0.0, min(1.0, float(confidence))), 3),
        "evidence": evidence if isinstance(evidence, dict) else {"value": evidence},
        "fix_suggestion": fix_suggestion,
        "auto_fix_available": False,
        "human_review_status": "pending",
        "description": description,
    }
    for field in REQUIRED_ISSUE_FIELDS:
        issue.setdefault(field, "unknown")
    return issue


def _issue_bbox(value: Any) -> list[float]:
    if isinstance(value, list) and len(value) >= 4:
        try:
            x, y, w, h = [float(item) for item in value[:4]]
            if w <= 0 or h <= 0:
                return [0.0, 0.0, 1.0, 1.0]
            return [round(_clamp(x), 4), round(_clamp(y), 4), round(_clamp(w), 4), round(_clamp(h), 4)]
        except Exception:
            pass
    return [0.0, 0.0, 1.0, 1.0]


def _bbox_or_full(value: Any) -> list[float]:
    return _issue_bbox(value)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _finalize(result: dict[str, Any], out_path: Path | str, start: float) -> None:
    summary = result["summary"]
    for issue in result["issues"]:
        sev = str(issue.get("severity") or "info")
        summary[sev] = int(summary.get(sev, 0)) + 1
        summary["total"] = int(summary.get("total", 0)) + 1
    result["success"] = True
    result["visual_acceptance_pass"] = summary["critical"] == 0 and summary["major"] == 0
    result["status"] = "pass" if result["visual_acceptance_pass"] else "need_review"
    result["duration_s"] = round(time.time() - start, 3)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    result["output_path"] = str(out)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Run v6 visual QC from a generated drawing PNG and DrawingBlueprint.")
    parser.add_argument("--png", required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--blueprint")
    parser.add_argument("--qc-json")
    parser.add_argument("--reference-png")
    parser.add_argument("--manual-review")
    parser.add_argument("--out")
    args = parser.parse_args()

    result = run_vision_qc_v6(
        png_path=args.png,
        run_dir=args.run_dir,
        blueprint_path=args.blueprint,
        qc_json_path=args.qc_json,
        reference_png_path=args.reference_png,
        manual_review_path=args.manual_review,
        out_path=args.out,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
