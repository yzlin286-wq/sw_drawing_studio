from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.validation.lb26001_006_ui_defect_buckets_v4_4 import build_report, render_markdown


def _write(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        manual = _write(
            root / "manual.json",
            {
                "overall_status": "FAIL",
                "visual_acceptance_pass": False,
                "review_mode": "application_drawing_review_ui_screenshot",
                "entries": [{
                    "visual_checklist": {
                        "reference_match": False,
                        "view_layout": False,
                        "display_dimensions": False,
                        "dimension_readability": False,
                        "title_block": False,
                        "manufacturing_notes": False,
                    },
                    "visual_checklist_notes": {
                        "display_dimensions": "The final sheet still contains 24 visible DisplayDims.",
                        "dimension_readability": "Dimension text clusters reduce readability.",
                        "title_block": "The title/data area differs from the reference.",
                        "manufacturing_notes": "Notes are not formatted like the reference.",
                        "view_layout": "View scale and organization do not match.",
                        "reference_match": "Generated drawing differs materially.",
                    },
                }],
            },
        )
        ui_report = _write(
            root / "ui_report.json",
            {"screenshot_pass": True, "evidence_capture_pass": True},
        )
        summary = _write(
            root / "summary.json",
            {"cases": [{"run_dir": str(root / "run")}]},
        )
        _write(
            root / "run" / "qc" / "LB26001-A-04-006_v5_warnings.json",
            {"warnings": [{"code": "prop_missing", "key": "材质"}]},
        )
        vision = _write(
            root / "vision.json",
            {
                "issues": [
                    {
                        "key": "dimension_visual_overdense",
                        "evidence": {"dimension_text_candidate_count": 118, "dimension_arrow_candidate_count": 29},
                    },
                    {
                        "key": "dimension_visual_clustered_unreadable",
                        "evidence": {
                            "dimension_text_cluster_bbox_norm": [0.5, 0.6, 0.1, 0.1],
                            "max_local_dimension_text_cluster_count": 32,
                        },
                    },
                    {
                        "key": "reference_titleblock_artifacts_present",
                        "evidence": {"default_template_artifacts_present": True},
                    },
                ],
                "checks": {
                    "notes": {"detected": True, "technical_requirements_detected": True, "required_notes": ["技术要求："]},
                    "reference_visual_compare": {"grid_l1_delta": 0.47, "occupied_cell_jaccard": 0.63},
                },
            },
        )
        reference_style = _write(
            root / "style.json",
            {
                "reference": {"display_dim_count": 12, "view_layout": [{}, {}, {}, {"size_norm": [0.17, 0.17]}]},
                "generated": {"display_dim_count": 24, "view_layout": [{}, {}, {}, {"size_norm": [0.32, 0.30]}]},
            },
        )
        readiness = _write(
            root / "readiness.json",
            {
                "status": "blocked",
                "ready_to_start_locked_006_cad": False,
                "blocking_issue_keys": ["solidworks_not_running"],
                "safe_recovery_guidance": {"automatic_restart_allowed": False, "manual_recovery_required": True},
            },
        )

        report = build_report(
            manual_review_path=manual,
            ui_report_path=ui_report,
            staged_summary_path=summary,
            vision_qc_path=vision,
            reference_style_path=reference_style,
            readiness_path=readiness,
        )
        assert report["schema"] == "sw_drawing_studio.lb26001_006_ui_defect_buckets.v4_4"
        assert report["status"] == "blocked_by_solidworks_readiness"
        assert report["pass"] is False
        assert report["expansion_allowed_now"] is False
        active = set(report["active_buckets"])
        assert "dimension_visual_overdense" in active
        assert "dimension_lane_wrong" in active
        assert "note_missing_or_wrong" in active
        assert "titlebar_incomplete" in active
        assert "projection_view_style_mismatch" in active
        assert "callout_missing" not in active
        assert report["required_bucket_keys"] == [
            "dimension_visual_overdense",
            "dimension_lane_wrong",
            "note_missing_or_wrong",
            "titlebar_incomplete",
            "projection_view_style_mismatch",
            "callout_missing",
        ]
        assert report["missing_bucket_keys"] == []
        assert set(report["required_next_screenshot_check_buckets"]) == set(report["required_bucket_keys"])
        checklist = {item["bucket"]: item for item in report["next_screenshot_checklist"]}
        assert set(checklist) == set(report["required_bucket_keys"])
        assert checklist["callout_missing"]["required_callout_keys"] == [
            "thread_callout_m4_6h",
            "surface_finish_rest_3_2",
        ]
        assert checklist["callout_missing"]["absence_check_keys"] == ["radius_callout", "chamfer_callout"]
        assert report["reference_callout_review_required_keys"] == ["thread_callout_m4_6h", "surface_finish_rest_3_2"]
        assert report["reference_callout_absence_check_keys"] == ["radius_callout", "chamfer_callout"]
        assert report["source_artifacts"]["manual_review"] == str(manual)
        assert report["solidworks_readiness"]["blocking_issue_keys"] == ["solidworks_not_running"]
        markdown = render_markdown(report)
        assert "Do not run full_129" in markdown
        assert "dimension_visual_overdense" in markdown
        assert "callout_missing" in markdown

    print("PASS test_v4_4_lb26001_006_ui_defect_buckets")


if __name__ == "__main__":
    main()
