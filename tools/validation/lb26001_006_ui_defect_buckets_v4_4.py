from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
BASE = "LB26001-A-04-006"
SCHEMA = "sw_drawing_studio.lb26001_006_ui_defect_buckets.v4_4"

DEFAULT_REVIEW_DIR = (
    REPO_ROOT
    / "drw_output"
    / "ui_acceptance"
    / "LB26001_006_locked_real_rerun_20260625_041353_visual_review"
)
DEFAULT_CASE_DIR = (
    REPO_ROOT
    / "drw_output"
    / "staged_validation"
    / "LB26001_006_locked_real_rerun_20260625_041353"
    / "01_LB26001-A-04-006"
)
DEFAULT_SUMMARY = (
    REPO_ROOT
    / "drw_output"
    / "staged_validation"
    / "LB26001_006_locked_real_rerun_20260625_041353"
    / "summary.json"
)
DEFAULT_READINESS = REPO_ROOT / "drw_output" / "diagnostics" / "lb26001_006_regression_readiness_v4_2.json"
DEFAULT_OUT = REPO_ROOT / "drw_output" / "diagnostics" / "lb26001_006_ui_defect_buckets_v4_4.json"
DEFAULT_OUT_MD = REPO_ROOT / "drw_output" / "diagnostics" / "lb26001_006_ui_defect_buckets_v4_4.md"

BUCKET_ORDER = [
    "dimension_visual_overdense",
    "dimension_lane_wrong",
    "note_missing_or_wrong",
    "titlebar_incomplete",
    "projection_view_style_mismatch",
    "callout_missing",
]


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_load_error": f"{type(exc).__name__}: {exc}", "_path": str(path)}
    return data if isinstance(data, dict) else {"_load_error": "json root is not object", "_path": str(path)}


def _first_entry(manual_review: dict[str, Any]) -> dict[str, Any]:
    entries = manual_review.get("entries") or []
    if entries and isinstance(entries[0], dict):
        return entries[0]
    return {}


def _vision_issue_map(vision_qc: dict[str, Any]) -> dict[str, dict[str, Any]]:
    issues = vision_qc.get("issues") or []
    result: dict[str, dict[str, Any]] = {}
    for issue in issues:
        if isinstance(issue, dict) and issue.get("key"):
            result[str(issue["key"])] = issue
    return result


def _manual_check(entry: dict[str, Any], key: str) -> tuple[bool | None, str]:
    checklist = entry.get("visual_checklist") or {}
    notes = entry.get("visual_checklist_notes") or {}
    value = checklist.get(key)
    if value is None:
        return None, str(notes.get(key) or "")
    return bool(value), str(notes.get(key) or "")


def _display_dim_counts(reference_style: dict[str, Any]) -> tuple[int, int]:
    reference = reference_style.get("reference") or {}
    generated = reference_style.get("generated") or {}
    return int(reference.get("display_dim_count") or 0), int(generated.get("display_dim_count") or 0)


def _view4_size_ratio(reference_style: dict[str, Any]) -> float:
    reference_views = ((reference_style.get("reference") or {}).get("view_layout") or [])
    generated_views = ((reference_style.get("generated") or {}).get("view_layout") or [])
    if len(reference_views) < 4 or len(generated_views) < 4:
        return 0.0
    ref_size = reference_views[3].get("size_norm") or []
    gen_size = generated_views[3].get("size_norm") or []
    if len(ref_size) < 2 or len(gen_size) < 2:
        return 0.0
    ref_area = float(ref_size[0]) * float(ref_size[1])
    gen_area = float(gen_size[0]) * float(gen_size[1])
    return round(gen_area / ref_area, 4) if ref_area else 0.0


def _bucket(
    key: str,
    *,
    active: bool,
    severity: str,
    evidence: dict[str, Any],
    source_paths: list[str],
    fix_action: str,
    blocks_006_acceptance: bool = True,
) -> dict[str, Any]:
    return {
        "key": key,
        "active": bool(active),
        "severity": severity if active else "info",
        "blocks_006_acceptance": bool(active and blocks_006_acceptance),
        "evidence": evidence,
        "source_paths": source_paths,
        "fix_action": fix_action,
    }


def build_report(
    *,
    manual_review_path: Path,
    ui_report_path: Path,
    staged_summary_path: Path,
    vision_qc_path: Path,
    reference_style_path: Path,
    readiness_path: Path,
) -> dict[str, Any]:
    manual_review = _read_json(manual_review_path)
    ui_report = _read_json(ui_report_path)
    staged_summary = _read_json(staged_summary_path)
    vision_qc = _read_json(vision_qc_path)
    reference_style = _read_json(reference_style_path)
    readiness = _read_json(readiness_path)

    entry = _first_entry(manual_review)
    issue_map = _vision_issue_map(vision_qc)
    ref_dim_count, gen_dim_count = _display_dim_counts(reference_style)
    display_dimensions_ok, display_dimensions_note = _manual_check(entry, "display_dimensions")
    dimension_readability_ok, dimension_readability_note = _manual_check(entry, "dimension_readability")
    manufacturing_notes_ok, manufacturing_notes_note = _manual_check(entry, "manufacturing_notes")
    title_block_ok, title_block_note = _manual_check(entry, "title_block")
    view_layout_ok, view_layout_note = _manual_check(entry, "view_layout")
    reference_match_ok, reference_match_note = _manual_check(entry, "reference_match")

    warnings_path = ""
    cases = staged_summary.get("cases") or []
    if cases and isinstance(cases[0], dict):
        run_dir = cases[0].get("run_dir") or ""
        if run_dir:
            warnings_path = str(Path(run_dir) / "qc" / f"{BASE}_v5_warnings.json")
    warnings = _read_json(Path(warnings_path)) if warnings_path else {}
    warning_items = warnings.get("warnings") or []
    prop_missing = [
        item for item in warning_items if isinstance(item, dict) and item.get("code") == "prop_missing"
    ]

    dense_issue = issue_map.get("dimension_visual_overdense") or {}
    clustered_issue = issue_map.get("dimension_visual_clustered_unreadable") or {}
    title_issue = issue_map.get("reference_titleblock_artifacts_present") or {}
    notes_check = (vision_qc.get("checks") or {}).get("notes") or {}
    visual_compare = (vision_qc.get("checks") or {}).get("reference_visual_compare") or {}

    buckets = [
        _bucket(
            "dimension_visual_overdense",
            active=(
                display_dimensions_ok is False
                or gen_dim_count > ref_dim_count > 0
                or bool(dense_issue)
            ),
            severity="major",
            evidence={
                "manual_display_dimensions_pass": display_dimensions_ok,
                "manual_note": display_dimensions_note,
                "reference_display_dim_count": ref_dim_count,
                "generated_display_dim_count": gen_dim_count,
                "vision_issue_present": bool(dense_issue),
                "dimension_text_candidate_count": ((dense_issue.get("evidence") or {}).get("dimension_text_candidate_count")),
                "dimension_arrow_candidate_count": ((dense_issue.get("evidence") or {}).get("dimension_arrow_candidate_count")),
            },
            source_paths=[str(manual_review_path), str(reference_style_path), str(vision_qc_path)],
            fix_action=(
                "Keep only the reference-intent manufacturing DisplayDim set after physical DisplayDim de-duplication; "
                "reject extra generic AutoDimension survivors before export."
            ),
        ),
        _bucket(
            "dimension_lane_wrong",
            active=(dimension_readability_ok is False or bool(clustered_issue)),
            severity="major",
            evidence={
                "manual_dimension_readability_pass": dimension_readability_ok,
                "manual_note": dimension_readability_note,
                "vision_cluster_issue_present": bool(clustered_issue),
                "cluster_bbox_norm": ((clustered_issue.get("evidence") or {}).get("dimension_text_cluster_bbox_norm")),
                "max_local_dimension_text_cluster_count": (
                    (clustered_issue.get("evidence") or {}).get("max_local_dimension_text_cluster_count")
                ),
            },
            source_paths=[str(manual_review_path), str(vision_qc_path)],
            fix_action=(
                "Place long thin-part dimensions in compact local top/bottom lanes and block diagonal or cross-region "
                "leader geometry from surviving final arrange."
            ),
        ),
        _bucket(
            "note_missing_or_wrong",
            active=(manufacturing_notes_ok is False),
            severity="major",
            evidence={
                "manual_manufacturing_notes_pass": manufacturing_notes_ok,
                "manual_note": manufacturing_notes_note,
                "vision_notes_detected": notes_check.get("detected"),
                "technical_requirements_detected": notes_check.get("technical_requirements_detected"),
                "required_notes": notes_check.get("required_notes") or [],
            },
            source_paths=[str(manual_review_path), str(vision_qc_path)],
            fix_action=(
                "Render the reference-style manufacturing notes/roughness text in the compact reference note region, "
                "not as generic default technical-requirement text."
            ),
        ),
        _bucket(
            "titlebar_incomplete",
            active=(title_block_ok is False or bool(title_issue) or bool(prop_missing)),
            severity="major",
            evidence={
                "manual_title_block_pass": title_block_ok,
                "manual_note": title_block_note,
                "vision_title_issue_present": bool(title_issue),
                "default_template_artifacts_present": ((title_issue.get("evidence") or {}).get("default_template_artifacts_present")),
                "missing_property_keys": [str(item.get("key")) for item in prop_missing],
            },
            source_paths=[str(manual_review_path), str(vision_qc_path), warnings_path],
            fix_action=(
                "Suppress default template artifacts and fill only the compact fields visible in the reference drawing."
            ),
        ),
        _bucket(
            "projection_view_style_mismatch",
            active=(view_layout_ok is False),
            severity="major",
            evidence={
                "manual_view_layout_pass": view_layout_ok,
                "manual_note": view_layout_note,
                "reference_match_pass": reference_match_ok,
                "reference_match_note": reference_match_note,
                "generated_iso_to_reference_iso_area_ratio": _view4_size_ratio(reference_style),
                "grid_l1_delta": visual_compare.get("grid_l1_delta"),
                "occupied_cell_jaccard": visual_compare.get("occupied_cell_jaccard"),
            },
            source_paths=[str(manual_review_path), str(reference_style_path), str(vision_qc_path)],
            fix_action=(
                "Match the reference view family scale and projection composition, especially the small right projection "
                "and compact isometric view footprint."
            ),
        ),
        _bucket(
            "callout_missing",
            active=False,
            severity="info",
            evidence={
                "manual_reference_match_pass": reference_match_ok,
                "manual_reference_match_note": reference_match_note,
                "reason": "Latest evidence proves note/layout/density failures, but does not independently prove a specific callout is absent.",
            },
            source_paths=[str(manual_review_path)],
            fix_action=(
                "On the next UI screenshot pass, explicitly check M4-6H through-thread, 4-3.3 hole callout, and Ra3.2 rest roughness callout."
            ),
            blocks_006_acceptance=False,
        ),
    ]

    active_buckets = [item["key"] for item in buckets if item["active"]]
    bucket_keys = {str(item.get("key") or "") for item in buckets}
    required_bucket_keys = list(BUCKET_ORDER)
    required_next_screenshot_check_buckets = list(BUCKET_ORDER)
    solidworks_blocking = list(readiness.get("blocking_issue_keys") or [])
    ready = bool(readiness.get("ready_to_start_locked_006_cad"))
    visual_pass = bool(manual_review.get("visual_acceptance_pass"))
    status = "needs_006_fix"
    if solidworks_blocking:
        status = "blocked_by_solidworks_readiness"
    elif visual_pass and not active_buckets:
        status = "pass"

    return {
        "schema": SCHEMA,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "base": BASE,
        "status": status,
        "pass": status == "pass",
        "release_ready": False,
        "api_is_not_final_judgement": True,
        "api_only_acceptance_allowed": False,
        "application_ui_screenshot_is_final_gate": True,
        "expansion_allowed_now": False,
        "solidworks_readiness": {
            "status": readiness.get("status") or "",
            "ready_to_start_locked_006_cad": ready,
            "blocking_issue_keys": solidworks_blocking,
            "automatic_restart_allowed": bool((readiness.get("safe_recovery_guidance") or {}).get("automatic_restart_allowed")),
            "manual_recovery_required": bool((readiness.get("safe_recovery_guidance") or {}).get("manual_recovery_required")),
        },
        "ui_final_gate": {
            "manual_review_path": str(manual_review_path),
            "ui_report_path": str(ui_report_path),
            "overall_status": manual_review.get("overall_status") or "",
            "visual_acceptance_pass": visual_pass,
            "review_mode": manual_review.get("review_mode") or entry.get("review_mode") or "",
            "failed_visual_checklist_items": [
                key for key, value in (entry.get("visual_checklist") or {}).items() if value is False
            ],
            "ui_report_screenshot_pass": bool(ui_report.get("screenshot_pass")),
            "ui_report_evidence_capture_pass": bool(ui_report.get("evidence_capture_pass")),
        },
        "active_bucket_count": len(active_buckets),
        "active_buckets": active_buckets,
        "required_bucket_keys": required_bucket_keys,
        "missing_bucket_keys": sorted(set(required_bucket_keys) - bucket_keys),
        "required_next_screenshot_check_buckets": required_next_screenshot_check_buckets,
        "next_screenshot_checklist": _next_screenshot_checklist(required_next_screenshot_check_buckets),
        "reference_callout_review_required_keys": ["thread_callout_m4_6h", "surface_finish_rest_3_2"],
        "reference_callout_absence_check_keys": ["radius_callout", "chamfer_callout"],
        "source_artifacts": {
            "manual_review": str(manual_review_path),
            "ui_report": str(ui_report_path),
            "staged_summary": str(staged_summary_path),
            "vision_qc_v6": str(vision_qc_path),
            "reference_style": str(reference_style_path),
            "readiness": str(readiness_path),
            "warnings": warnings_path,
        },
        "buckets": buckets,
        "next_allowed_action": (
            "Start SolidWorks manually, rerun readiness, then run exactly one locked 006 CAD worker."
            if solidworks_blocking
            else "Run exactly one locked 006 CAD worker, then repeat Drawing Review UI screenshot judgement."
        ),
        "do_not": [
            "Do not run full_129.",
            "Do not run LB26001_36.",
            "Do not expand to 007/008/009/015/022 before 006 passes the application UI screenshot gate.",
            "Do not use API pass, DisplayDim pass, or reference JSON pass as final acceptance.",
        ],
    }


def _next_screenshot_checklist(bucket_keys: list[str]) -> list[dict[str, Any]]:
    labels = {
        "dimension_visual_overdense": "visible DisplayDim density matches the 12-target reference-intent set",
        "dimension_lane_wrong": "dimension text/leaders stay in compact local reference lanes without cross-region clutter",
        "note_missing_or_wrong": "manufacturing notes and roughness text match the reference note region",
        "titlebar_incomplete": "title/data area uses only the compact reference-like fields",
        "projection_view_style_mismatch": "front/top/right/iso view scale and composition match the reference",
        "callout_missing": "M4-6H through-thread, 4-3.3 hole callout, Ra3.2 rest roughness, and radius/chamfer absence are explicitly checked",
    }
    checklist: list[dict[str, Any]] = []
    for key in bucket_keys:
        item = {
            "bucket": key,
            "required": True,
            "review_method": "application_drawing_review_ui_screenshot",
            "expected_ui_evidence": labels.get(key, key),
            "pass_condition": "manual_visual_judgement must mark this bucket pass for LB26001-A-04-006",
        }
        if key == "callout_missing":
            item["required_callout_keys"] = ["thread_callout_m4_6h", "surface_finish_rest_3_2"]
            item["absence_check_keys"] = ["radius_callout", "chamfer_callout"]
            item["pass_condition"] = (
                "manual_visual_judgement reference_callout_checklist proves required callouts present "
                "and radius/chamfer are not fabricated"
            )
        checklist.append(item)
    return checklist


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# {BASE} UI Defect Buckets v4.4",
        "",
        f"- Status: `{report.get('status')}`",
        f"- pass: `{report.get('pass')}`",
        f"- release_ready: `{report.get('release_ready')}`",
        f"- Active buckets: `{', '.join(report.get('active_buckets') or []) or 'none'}`",
        f"- SolidWorks readiness: `{(report.get('solidworks_readiness') or {}).get('status')}`",
        "",
        "## Required Next Screenshot Checks",
        "",
    ]
    for item in report.get("next_screenshot_checklist") or []:
        lines.append(f"- `{item.get('bucket')}`: {item.get('expected_ui_evidence')}")
    lines.extend([
        "",
        "## Bucket Evidence",
    ])
    for bucket in report.get("buckets") or []:
        lines.extend([
            "",
            f"### {bucket.get('key')}",
            "",
            f"- active: `{bucket.get('active')}`",
            f"- severity: `{bucket.get('severity')}`",
            f"- blocks_006_acceptance: `{bucket.get('blocks_006_acceptance')}`",
            f"- fix_action: {bucket.get('fix_action')}",
        ])
    lines.extend([
        "",
        "## Next Allowed Action",
        "",
        str(report.get("next_allowed_action") or ""),
        "",
        "## Do Not",
        "",
    ])
    for item in report.get("do_not") or []:
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build LB26001-A-04-006 UI defect bucket evidence.")
    parser.add_argument("--manual-review", default=str(DEFAULT_REVIEW_DIR / "manual_visual_judgement.json"))
    parser.add_argument("--ui-report", default=str(DEFAULT_REVIEW_DIR / "drawing_visual_review_report.json"))
    parser.add_argument("--staged-summary", default=str(DEFAULT_SUMMARY))
    parser.add_argument("--vision-qc", default=str(DEFAULT_CASE_DIR / "vision_qc_v6.json"))
    parser.add_argument("--reference-style", default=str(DEFAULT_CASE_DIR / "reference_style.json"))
    parser.add_argument("--readiness", default=str(DEFAULT_READINESS))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    args = parser.parse_args()

    report = build_report(
        manual_review_path=Path(args.manual_review),
        ui_report_path=Path(args.ui_report),
        staged_summary_path=Path(args.staged_summary),
        vision_qc_path=Path(args.vision_qc),
        reference_style_path=Path(args.reference_style),
        readiness_path=Path(args.readiness),
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({"status": report["status"], "pass": report["pass"], "out": str(out)}, ensure_ascii=False))
    return 0 if report["status"] in {"pass", "needs_006_fix", "blocked_by_solidworks_readiness"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
