from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from tools.validation.manual_visual_judgement_template_v4 import (
    build_manual_visual_judgement_template,
)


def _ui_report(base: str) -> dict:
    return {
        "schema": "sw_drawing_studio.drawing_visual_review_ui.v1",
        "mode": "source_qt_application_ui_screenshot",
        "entries": [
            {
                "base": base,
                "ui_screenshot": {"path": f"screenshots/{base}.png", "pass": True},
                "reference_png": f"reference/{base}.png",
                "generated_png": f"runs/{base}.png",
                "comparison_png": {"path": f"comparison/{base}.png"},
            }
        ],
    }


def _defect_buckets(base: str) -> dict:
    required = [
        "dimension_visual_overdense",
        "dimension_lane_wrong",
        "note_missing_or_wrong",
        "titlebar_incomplete",
        "projection_view_style_mismatch",
        "callout_missing",
    ]
    return {
        "schema": "sw_drawing_studio.lb26001_006_ui_defect_buckets.v4_4",
        "base": base,
        "required_next_screenshot_check_buckets": required,
        "next_screenshot_checklist": [
            {
                "bucket": key,
                "expected_ui_evidence": f"{key} visible closure evidence",
                "pass_condition": f"{key} pass condition",
            }
            for key in required
        ],
        "bucket_closure_contract": [
            {
                "bucket": key,
                "ui_review_pass_condition": f"{key} closure condition",
                "post_rerun_required_evidence": ["application_drawing_review_ui_screenshot"],
                "api_or_displaydim_metric_alone_can_close": False,
            }
            for key in required
        ],
    }


def test_manual_visual_judgement_template_includes_006_bucket_closure_checklist() -> None:
    base = "LB26001-A-04-006"
    defects = _defect_buckets(base)
    defects["bucket_closure_contract"][-1]["required_callout_keys"] = [
        "thread_callout_m4_6h",
        "surface_finish_rest_3_2",
    ]
    defects["bucket_closure_contract"][-1]["absence_check_keys"] = [
        "radius_callout",
        "chamfer_callout",
    ]
    defects["bucket_closure_contract"][-1]["reference_callout_checklist_required"] = True

    with TemporaryDirectory() as tmp:
        template = build_manual_visual_judgement_template(
            ui_report=_ui_report(base),
            ui_report_path=Path(tmp) / "drawing_visual_review_report.json",
            bases=[base],
            ui_defect_buckets=defects,
        )

    entry = template["entries"][0]
    checklist = entry["ui_defect_bucket_closure_checklist"]
    assert template["visual_acceptance_pass"] is False
    assert template["ui_defect_bucket_closure_template_available"] is True
    assert entry["manual_status"] == "PENDING"
    assert entry["ui_defect_bucket_closure_required"] is True
    assert entry["required_ui_defect_bucket_keys"] == defects["required_next_screenshot_check_buckets"]
    assert set(checklist) == set(defects["required_next_screenshot_check_buckets"])
    assert all(item["pass"] is None for item in checklist.values())
    assert all(item["visual_acceptance_pass"] is None for item in checklist.values())
    assert all(item["api_or_displaydim_metric_alone_can_close"] is False for item in checklist.values())
    assert entry["reference_callout_checklist"]["required"] is True
    assert set(entry["reference_callout_checklist"]["required_callout_keys"]) == {
        "thread_callout_m4_6h",
        "surface_finish_rest_3_2",
    }
    assert set(entry["reference_callout_checklist"]["absence_check_keys"]) == {
        "radius_callout",
        "chamfer_callout",
    }


def test_manual_visual_judgement_template_does_not_apply_006_buckets_to_other_bases() -> None:
    with TemporaryDirectory() as tmp:
        template = build_manual_visual_judgement_template(
            ui_report=_ui_report("LB26001-A-04-007"),
            ui_report_path=Path(tmp) / "drawing_visual_review_report.json",
            bases=["LB26001-A-04-007"],
            ui_defect_buckets=_defect_buckets("LB26001-A-04-006"),
        )

    entry = template["entries"][0]
    assert template["ui_defect_bucket_closure_template_available"] is False
    assert "ui_defect_bucket_closure_checklist" not in entry
    assert "reference_callout_checklist" not in entry


if __name__ == "__main__":
    test_manual_visual_judgement_template_includes_006_bucket_closure_checklist()
    test_manual_visual_judgement_template_does_not_apply_006_buckets_to_other_bases()
    print("PASS test_v4_4_manual_visual_judgement_template")
