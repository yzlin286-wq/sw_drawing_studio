"""Create a manual visual judgement template from Drawing Review UI evidence.

The template is intentionally non-passing. A human reviewer must inspect the
application UI screenshots and fill every visual checklist item before v6/v4
acceptance can pass.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_UI_DEFECT_BUCKETS = REPO_ROOT / "drw_output" / "diagnostics" / "lb26001_006_ui_defect_buckets_v4_4.json"
REQUIRED_VISUAL_CHECKS = (
    "reference_match",
    "view_layout",
    "display_dimensions",
    "dimension_readability",
    "title_block",
    "manufacturing_notes",
)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _artifact_path_text(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("path") or value.get("file") or "")
    return str(value or "")


def _comparison_png_text(entry: dict[str, Any]) -> str:
    value = entry.get("comparison_png") or entry.get("comparison_image")
    if isinstance(value, dict):
        return str(value.get("path") or value.get("output") or "")
    return str(value or "")


def _selected_entries(ui_report: dict[str, Any], bases: list[str] | None) -> list[dict[str, Any]]:
    requested = {base for base in bases or [] if base}
    entries = [item for item in ui_report.get("entries") or [] if isinstance(item, dict)]
    if not requested:
        return entries
    return [item for item in entries if str(item.get("base") or "") in requested]


def _ui_defect_buckets_for_base(ui_defect_buckets: dict[str, Any], base: str) -> dict[str, Any]:
    required_base = str(ui_defect_buckets.get("base") or "").strip()
    if not ui_defect_buckets or (required_base and required_base != base):
        return {}
    required = [
        str(item or "").strip()
        for item in ui_defect_buckets.get("required_next_screenshot_check_buckets") or []
        if str(item or "").strip()
    ]
    contracts_by_bucket = {
        str(item.get("bucket") or ""): item
        for item in ui_defect_buckets.get("bucket_closure_contract") or []
        if isinstance(item, dict) and str(item.get("bucket") or "")
    }
    next_checks_by_bucket = {
        str(item.get("bucket") or ""): item
        for item in ui_defect_buckets.get("next_screenshot_checklist") or []
        if isinstance(item, dict) and str(item.get("bucket") or "")
    }
    if not required:
        return {}

    closure_checklist: dict[str, dict[str, Any]] = {}
    closure_notes: dict[str, str] = {}
    contracts: list[dict[str, Any]] = []
    for bucket in required:
        contract = contracts_by_bucket.get(bucket, {})
        next_check = next_checks_by_bucket.get(bucket, {})
        closure_checklist[bucket] = {
            "pass": None,
            "visual_acceptance_pass": None,
            "ui_review_pass_condition": str(
                contract.get("ui_review_pass_condition")
                or next_check.get("pass_condition")
                or "Manual UI screenshot review must close this defect bucket."
            ),
            "expected_ui_evidence": str(next_check.get("expected_ui_evidence") or ""),
            "api_or_displaydim_metric_alone_can_close": False,
        }
        closure_notes[bucket] = ""
        contracts.append(
            {
                "bucket": bucket,
                "ui_review_pass_condition": closure_checklist[bucket]["ui_review_pass_condition"],
                "post_rerun_required_evidence": list(contract.get("post_rerun_required_evidence") or []),
                "required_callout_keys": list(contract.get("required_callout_keys") or []),
                "absence_check_keys": list(contract.get("absence_check_keys") or []),
                "api_or_displaydim_metric_alone_can_close": False,
            }
        )

    callout_contract = contracts_by_bucket.get("callout_missing", {})
    return {
        "ui_defect_bucket_closure_required": True,
        "required_ui_defect_bucket_keys": required,
        "ui_defect_bucket_closure_checklist": closure_checklist,
        "ui_defect_bucket_closure_notes": closure_notes,
        "ui_defect_bucket_closure_contract": contracts,
        "reference_callout_checklist": {
            "required": bool(callout_contract.get("reference_callout_checklist_required")),
            "required_callout_keys": {
                str(key): None for key in callout_contract.get("required_callout_keys") or []
            },
            "absence_check_keys": {
                str(key): None for key in callout_contract.get("absence_check_keys") or []
            },
            "api_or_displaydim_metric_alone_can_close": False,
        },
    }


def build_manual_visual_judgement_template(
    *,
    ui_report: dict[str, Any],
    ui_report_path: Path,
    bases: list[str] | None = None,
    ui_defect_buckets: dict[str, Any] | None = None,
) -> dict[str, Any]:
    defects = ui_defect_buckets if ui_defect_buckets is not None else _read_json(DEFAULT_UI_DEFECT_BUCKETS)
    entries: list[dict[str, Any]] = []
    for item in _selected_entries(ui_report, bases):
        base = str(item.get("base") or "").strip()
        if not base:
            continue
        defect_closure = _ui_defect_buckets_for_base(defects, base)
        entries.append(
            {
                "base": base,
                "manual_status": "PENDING",
                "visual_acceptance_pass": False,
                "ui_screenshot": _artifact_path_text(item.get("ui_screenshot")),
                "reference_png": str(item.get("reference_png") or ""),
                "generated_png": str(item.get("generated_png") or ""),
                "comparison_png": _comparison_png_text(item),
                "source_ui_report": str(ui_report_path),
                "drawing_visual_review_report": str(ui_report_path),
                "review_mode": "application_drawing_review_ui_screenshot",
                "application_ui_screenshot_review_required": True,
                "ui_screenshot_is_final_gate": True,
                "api_only_acceptance_allowed": False,
                "api_is_not_final_judgement": True,
                "visual_checklist": {key: None for key in REQUIRED_VISUAL_CHECKS},
                "visual_checklist_notes": {key: "" for key in REQUIRED_VISUAL_CHECKS},
                **defect_closure,
                "findings": [],
                "required_correction": "",
                "reviewer": "",
                "reviewed_at": "",
            }
        )

    return {
        "schema": "sw_drawing_studio.manual_visual_judgement.v4_2.template",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "template_status": "requires_human_visual_judgement",
        "overall_status": "PENDING_MANUAL_REVIEW",
        "visual_acceptance_pass": False,
        "review_mode": "application_drawing_review_ui_screenshot",
        "source_ui_report": str(ui_report_path),
        "drawing_visual_review_report": str(ui_report_path),
        "required_visual_checklist_items": list(REQUIRED_VISUAL_CHECKS),
        "ui_defect_bucket_closure_template_available": any(
            bool(entry.get("ui_defect_bucket_closure_required")) for entry in entries
        ),
        "ui_defect_bucket_closure_source": str(DEFAULT_UI_DEFECT_BUCKETS if ui_defect_buckets is None else ""),
        "api_is_not_final_judgement": True,
        "api_only_acceptance_allowed": False,
        "ui_screenshot_review_is_final_gate": True,
        "instructions": [
            "Inspect the application Drawing Review UI screenshot for each entry.",
            "Set manual_status to PASS only when every visual_checklist item is true.",
            "For LB26001-A-04-006, set every ui_defect_bucket_closure_checklist bucket pass only from the application UI screenshot.",
            "Do not use API, OCR, sidecar, or file creation alone as the drawing acceptance decision.",
        ],
        "entries": entries,
    }


def write_manual_visual_judgement_template(
    *,
    ui_report: dict[str, Any],
    ui_report_path: Path,
    out_path: Path,
    bases: list[str] | None = None,
    ui_defect_buckets: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = build_manual_visual_judgement_template(
        ui_report=ui_report,
        ui_report_path=ui_report_path,
        bases=bases,
        ui_defect_buckets=ui_defect_buckets,
    )
    _write_json(out_path, payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a manual visual judgement template from a Drawing Review UI report.")
    parser.add_argument("--ui-report", required=True)
    parser.add_argument("--out", default="")
    parser.add_argument("--base", action="append", default=[])
    parser.add_argument("--ui-defect-buckets", default=str(DEFAULT_UI_DEFECT_BUCKETS))
    args = parser.parse_args()

    ui_report_path = Path(args.ui_report)
    out_path = Path(args.out) if args.out else ui_report_path.parent / "manual_visual_judgement_template.json"
    payload = write_manual_visual_judgement_template(
        ui_report=_read_json(ui_report_path),
        ui_report_path=ui_report_path,
        out_path=out_path,
        bases=args.base,
        ui_defect_buckets=_read_json(Path(args.ui_defect_buckets)),
    )
    print(
        json.dumps(
            {
                "template": str(out_path),
                "entry_count": len(payload.get("entries") or []),
                "visual_acceptance_pass": payload.get("visual_acceptance_pass"),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
