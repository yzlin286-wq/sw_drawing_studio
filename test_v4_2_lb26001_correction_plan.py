import json
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.validation.lb26001_correction_plan_v4_2 import (
    build_correction_plan,
    render_markdown,
)


def test_correction_plan_combines_reference_standard_ui_failures_and_006_gate() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        reference_dir = root / "3D转2D测试图纸"
        reference_dir.mkdir()
        for base in ["LB26001-A-04-006", "LB26001-A-04-007"]:
            (reference_dir / f"{base}.SLDPRT").write_text("part", encoding="utf-8")
            (reference_dir / f"{base}.SLDDRW").write_text("drawing", encoding="utf-8")

        standard = {
            "status": "standard_ready",
            "sample_rules": [
                {
                    "base": "LB26001-A-04-006",
                    "reference_drawing": str(reference_dir / "LB26001-A-04-006.SLDDRW"),
                    "required_view_count": 4,
                    "required_view_types": {"7": 2, "4": 2},
                    "required_projected_view_count": 2,
                    "display_dim_floor": 12,
                    "layout_slots_center_norm": {"front": [0.37, 0.8]},
                    "layout_tolerance_norm": 0.08,
                    "section_policy": {"automatic_section_or_detail_allowed": False},
                },
                {
                    "base": "LB26001-A-04-007",
                    "reference_drawing": str(reference_dir / "LB26001-A-04-007.SLDDRW"),
                    "required_view_count": 4,
                    "required_view_types": {"7": 2, "4": 2},
                    "required_projected_view_count": 2,
                    "display_dim_floor": 8,
                    "layout_slots_center_norm": {"front": [0.32, 0.73]},
                    "layout_tolerance_norm": 0.08,
                    "section_policy": {"automatic_section_or_detail_allowed": False},
                },
            ],
        }
        requested_status = {
            "status": "blocked_by_006",
            "base_results": [
                {
                    "base": "LB26001-A-04-006",
                    "status": "manual_visual_checklist_failed",
                    "pass": False,
                    "application_ui_screenshot_gate_pass": False,
                    "application_ui_screenshot_content_check_pass": True,
                    "application_ui_screenshot_paths_existing_application_ui": ["006_ui.png"],
                    "generated_png_source_pass": True,
                    "source_ui_report": "ui-report.json",
                    "latest_manual_review": "manual.json",
                    "latest_manual_visual_checklist": {
                        "reference_match": False,
                        "view_layout": False,
                        "display_dimensions": False,
                        "dimension_readability": False,
                        "title_block": False,
                        "manufacturing_notes": False,
                    },
                    "manual_visual_checklist_failed_items": [
                        "reference_match",
                        "view_layout",
                        "display_dimensions",
                        "dimension_readability",
                        "title_block",
                        "manufacturing_notes",
                    ],
                    "latest_manual_visual_checklist_notes": {
                        "title_block": "Generated titleblock does not match the reference.",
                    },
                    "latest_manual_findings": [
                        "Generated drawing still uses the wrong titleblock.",
                    ],
                    "latest_manual_required_correction": (
                        "Implement explicit reference-intent dimension groups for 006 first."
                    ),
                },
                {
                    "base": "LB26001-A-04-007",
                    "status": "manual_visual_checklist_failed",
                    "pass": False,
                    "application_ui_screenshot_gate_pass": False,
                    "application_ui_screenshot_content_check_pass": True,
                    "application_ui_screenshot_paths_existing_application_ui": ["007_ui.png"],
                    "generated_png_source_pass": True,
                    "latest_manual_visual_checklist": {"title_block": False},
                    "manual_visual_checklist_failed_items": ["title_block"],
                },
            ],
        }
        readiness = {
            "status": "blocked",
            "blocking_issue_keys": [
                "solidworks_not_responding",
                "solidworks_unsaved_document_visible",
            ],
        }

        plan = build_correction_plan(
            standard=standard,
            requested_status=requested_status,
            readiness=readiness,
            reference_dir=reference_dir,
            requested_bases=["LB26001-A-04-006", "LB26001-A-04-007"],
        )
        markdown = render_markdown(plan)

    assert plan["schema"] == "sw_drawing_studio.lb26001_correction_plan.v4_2"
    assert plan["status"] == "blocked_by_solidworks_readiness"
    assert plan["pass"] is False
    assert plan["report_is_acceptance_evidence"] is False
    assert plan["api_only_acceptance_allowed"] is False
    assert plan["ui_screenshot_review_is_final_gate"] is True
    assert plan["visual_validation_policy"]["per_drawing_application_ui_screenshot_required"] is True
    assert plan["visual_validation_policy"]["final_judgement_source"] == (
        "application_drawing_review_ui_screenshot_manual_visual_judgement"
    )
    assert plan["visual_validation_policy"]["required_bases"] == [
        "LB26001-A-04-006",
        "LB26001-A-04-007",
    ]
    assert plan["expansion_allowed_after_006"] is False
    assert plan["readiness_blocking_issue_keys"] == [
        "solidworks_not_responding",
        "solidworks_unsaved_document_visible",
    ]

    by_base = {item["base"]: item for item in plan["entries"]}
    first = by_base["LB26001-A-04-006"]
    second = by_base["LB26001-A-04-007"]
    assert first["correction_stage"] == "pilot_006_first"
    assert first["real_cad_regression_allowed_now"] is False
    assert first["blocked_by_readiness"] is True
    assert first["reference_standard"]["display_dim_floor"] == 12
    assert first["reference_standard"]["required_view_types"] == {"7": 2, "4": 2}
    assert first["reference_standard"]["sheet_template_policy"]["policy"] == "strip_default_template_artifacts"
    assert first["reference_standard"]["sheet_template_policy"]["default_template_artifacts_allowed"] is False
    assert first["reference_intent_trace_policy"]["required"] is True
    assert first["reference_intent_trace_policy"]["final_stage_required"] == "post_layout_final"
    assert first["reference_intent_trace_policy"]["generic_autodimension_acceptance_allowed"] is False
    assert "selected_entity" in first["reference_intent_trace_policy"]["required_fields"]
    assert first["current_ui_status"]["generated_png_source_pass"] is True
    assert first["current_ui_status"]["application_ui_screenshot_content_check_pass"] is True
    assert first["current_ui_status"]["ui_screenshot_file_count"] == 0
    assert first["current_ui_status"]["ui_visual_review_status"] == ""
    assert first["current_ui_status"]["application_ui_screenshot_paths_existing_application_ui"] == ["006_ui.png"]
    assert first["current_ui_status"]["latest_manual_required_correction"].startswith("Implement explicit")
    assert first["visual_validation_required"]["application_drawing_review_ui_screenshot_required"] is True
    assert first["visual_validation_required"]["manual_visual_judgement_required"] is True
    assert first["visual_validation_required"]["api_only_acceptance_allowed"] is False
    assert first["visual_validation_required"]["final_judgement_source"] == (
        "application_drawing_review_ui_screenshot_manual_visual_judgement"
    )
    assert first["ui_visual_failures"]["failed_checklist_items"] == [
        "reference_match",
        "view_layout",
        "display_dimensions",
        "dimension_readability",
        "title_block",
        "manufacturing_notes",
    ]
    assert first["ui_visual_failures"]["checklist_notes"]["title_block"] == (
        "Generated titleblock does not match the reference."
    )
    assert any(action["check"] == "display_dimensions" for action in first["correction_actions"])
    assert second["correction_stage"] == "gated_after_006_pass"
    assert second["blocked_until_006_passes"] is True
    assert second["reference_intent_trace_policy"]["required"] is False
    assert "LB26001-A-04-006" in markdown
    assert "application UI screenshot review remains the final gate" in markdown


def test_correction_plan_maps_direct_ui_findings_without_checklist_to_actions() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        reference_dir = root / "references"
        reference_dir.mkdir()
        (reference_dir / "LB26001-A-04-006.SLDPRT").write_text("part", encoding="utf-8")
        (reference_dir / "LB26001-A-04-006.SLDDRW").write_text("drawing", encoding="utf-8")
        standard = {
            "sample_rules": [
                {
                    "base": "LB26001-A-04-006",
                    "reference_drawing": str(reference_dir / "LB26001-A-04-006.SLDDRW"),
                    "required_view_count": 4,
                    "required_view_types": {"7": 2, "4": 2},
                    "display_dim_floor": 12,
                }
            ]
        }
        requested_status = {
            "status": "blocked_by_006",
            "base_results": [
                {
                    "base": "LB26001-A-04-006",
                    "status": "generated_png_source_invalid",
                    "pass": False,
                    "latest_manual_status": "fail",
                    "application_ui_screenshot_gate_pass": False,
                    "application_ui_screenshot_content_check_pass": True,
                    "application_ui_screenshot_paths_existing_application_ui": ["006_ui.png"],
                    "generated_png_source_pass": False,
                    "latest_manual_review": "codex_direct_ui_screenshot_recheck_20260624.json",
                    "manual_visual_checklist_failed_items": [],
                    "manual_visual_checklist_missing_items": [],
                    "latest_manual_visual_checklist": {},
                    "latest_manual_visual_checklist_notes": {},
                    "latest_manual_findings": [
                        "generated view layout differs from the same-name reference",
                        "dimension placement is dense and not reference-like",
                        "manufacturing notes/title-block treatment does not match the reference",
                    ],
                }
            ],
        }

        plan = build_correction_plan(
            standard=standard,
            requested_status=requested_status,
            readiness={"status": "ready", "blocking_issue_keys": []},
            reference_dir=reference_dir,
            requested_bases=["LB26001-A-04-006"],
        )

    entry = plan["entries"][0]
    failures = entry["ui_visual_failures"]
    action_by_check = {item["check"]: item for item in entry["correction_actions"]}
    assert failures["failed_checklist_items"] == []
    assert failures["missing_checklist_items"] == []
    assert failures["direct_ui_findings_used_for_correction"] is True
    assert set(failures["effective_failed_visual_checks"]) >= {
        "reference_match",
        "view_layout",
        "display_dimensions",
        "dimension_readability",
        "title_block",
        "manufacturing_notes",
    }
    assert action_by_check["view_layout"]["source_type"] == "direct_ui_screenshot_finding"
    assert "view layout differs" in action_by_check["view_layout"]["source_note"]
    assert action_by_check["display_dimensions"]["source_type"] == "direct_ui_screenshot_finding"
    assert action_by_check["title_block"]["source_type"] == "direct_ui_screenshot_finding"


if __name__ == "__main__":
    test_correction_plan_combines_reference_standard_ui_failures_and_006_gate()
    test_correction_plan_maps_direct_ui_findings_without_checklist_to_actions()
    print("PASS test_v4_2_lb26001_correction_plan")
