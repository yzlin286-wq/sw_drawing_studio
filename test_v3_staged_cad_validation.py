import inspect
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image, ImageDraw

import tools.validation.staged_cad_validation_v3 as staged_module
import tools.validation.real_cad_smoke_v3 as real_cad_smoke
from app.services.job_runner import JobRunner
from tools.validation.staged_cad_validation_v3 import (
    _case_summary,
    _write_displaydim_lifecycle_audit_report,
    _generator_warnings_from_cad_report,
    _resolve_parts,
    _stage_summary,
    _write_no_reference_report,
    _write_reference_compare_v4_report,
    _write_reference_style_report,
    _write_vision_qc_v6_report,
    run_stage,
)


def test_lb26001_006_real_cad_path_uses_facade_qprocess_worker() -> None:
    staged_source = inspect.getsource(staged_module.run_stage)
    smoke_source = inspect.getsource(real_cad_smoke.run_smoke)
    runner_source = inspect.getsource(JobRunner.start_job)

    assert "tools/validation/real_cad_smoke_v3.py" in staged_source
    assert "--lb26001-006-rerun-packet" in staged_source
    assert "lb26001_006_rerun_packet_report" in staged_source
    assert "cad_job_worker.py" not in staged_source
    assert "JobRuntimeFacade" in smoke_source
    assert "facade.start_cad_job" in smoke_source
    assert "SWDS_LB26001_006_RERUN_PACKET_PATH" in inspect.getsource(real_cad_smoke._set_006_rerun_packet_env)
    assert "cad_job_worker.py" not in smoke_source
    assert "QProcess" in runner_source
    assert "proc.start" in runner_source


def test_stage_with_bucketed_failure_is_need_review_not_acceptance_pass() -> None:
    case = _case_summary(
        part=Path("LB26001-A-04-040.SLDPRT"),
        case_dir=Path("drw_output/staged_validation/024_040/example"),
        cad={"pass": False, "run_dir": "run", "reasons": ["final_quality_not_deliverable"]},
        dim={"pass": True, "status": "pass_with_warning"},
        ref={"pass": True, "status": "pass_with_warning"},
        commands={"cad": {"returncode": 1, "timeout": False}},
        style={"pass": True, "status": "pass"},
        vision={"visual_acceptance_pass": True, "status": "pass"},
    )

    summary = _stage_summary(
        stage="024_040",
        out_dir=Path("drw_output/staged_validation/024_040/example"),
        started=0.0,
        cases=[case],
        total=1,
        final=True,
    )

    assert case["status"] == "need_review"
    assert "cad_smoke_not_pass" in case["failure_bucket"]
    assert summary["status"] == "need_review"
    assert summary["pass"] is False
    assert summary["execution_completed"] is True
    assert summary["acceptance_pass"] is False
    assert summary["deliverable_count"] == 0


def test_stage_without_evidence_is_fail() -> None:
    case = _case_summary(
        part=Path("missing.SLDPRT"),
        case_dir=Path("drw_output/staged_validation/024_040/missing"),
        cad={},
        dim={},
        ref={},
        commands={},
        style={},
    )

    summary = _stage_summary(
        stage="024_040",
        out_dir=Path("drw_output/staged_validation/024_040/missing"),
        started=0.0,
        cases=[case],
        total=1,
        final=True,
    )

    assert case["status"] == "fail"
    assert "cad_smoke_report_missing" in case["failure_bucket"]
    assert summary["status"] == "fail"


def test_stage_requires_visual_acceptance_not_api_pass_only() -> None:
    case = _case_summary(
        part=Path("LB26001-A-04-006.SLDPRT"),
        case_dir=Path("drw_output/staged_validation/LB26001_006/api_only"),
        cad={"pass": True, "run_dir": "run"},
        dim={"pass": True, "status": "pass"},
        ref={"pass": True, "status": "pass"},
        commands={},
        style={"pass": True, "status": "pass"},
        vision={"pass": True, "status": "pass"},
        reference_v4={"pass": True, "status": "pass"},
    )

    assert case["deliverable"] is False
    assert case["vision_qc_v6_pass"] is False
    assert "vision_qc_v6_not_pass" in case["failure_bucket"]


def test_lb26001_006_requires_displaydim_lifecycle_audit() -> None:
    case = _case_summary(
        part=Path("LB26001-A-04-006.SLDPRT"),
        case_dir=Path("drw_output/staged_validation/LB26001_006/lifecycle_fail"),
        cad={"pass": True, "run_dir": "run"},
        dim={"pass": True, "status": "pass"},
        ref={"pass": True, "status": "pass"},
        commands={},
        style={"pass": True, "status": "pass"},
        lifecycle={
            "applicable": True,
            "pass": False,
            "status": "fail",
            "blocking_issue_keys": ["final_display_dim_below_reference_floor"],
        },
        vision={"visual_acceptance_pass": True, "status": "pass"},
        reference_v4={"pass": True, "status": "pass"},
    )

    assert case["displaydim_lifecycle_required"] is True
    assert case["displaydim_lifecycle_pass"] is False
    assert case["deliverable"] is False
    assert "displaydim_lifecycle_not_pass" in case["failure_bucket"]
    assert "final_display_dim_below_reference_floor" in case["reasons"]


def test_non_006_does_not_require_displaydim_lifecycle_audit() -> None:
    case = _case_summary(
        part=Path("LB26001-A-04-007.SLDPRT"),
        case_dir=Path("drw_output/staged_validation/LB26001_ref6/non_006"),
        cad={"pass": True, "run_dir": "run"},
        dim={"pass": True, "status": "pass"},
        ref={"pass": True, "status": "pass"},
        commands={},
        style={"pass": True, "status": "pass"},
        vision={"visual_acceptance_pass": True, "status": "pass"},
        reference_v4={"pass": True, "status": "pass"},
    )

    assert case["displaydim_lifecycle_required"] is False
    assert case["displaydim_lifecycle_pass"] is True
    assert "displaydim_lifecycle_report_missing" not in case["failure_bucket"]
    assert case["deliverable"] is True


def test_stage_aborts_before_cad_when_sw_connection_guard_fails() -> None:
    with TemporaryDirectory() as tmp:
        out_dir = Path(tmp) / "stage"
        summary = run_stage(
            "024_040",
            [Path("LB26001-A-04-006.SLDPRT")],
            out_dir,
            timeout_s=1,
            max_rounds=1,
            sw_guard={
                "schema": "sw_drawing_studio.sw_connection_guard.v4",
                "status": "fail",
                "connected": False,
                "safe_to_start_cad_job": False,
                "do_not_continue_batch": True,
                "failure_bucket": "solidworks_com_active_object_timeout",
                "reason": "get_active_object timed out after 1.0s",
                "user_action_required": "Save documents and restart SolidWorks safely.",
            },
        )

        assert summary["status"] == "fail"
        assert summary["processed"] == 0
        assert summary["cases"] == []
        assert summary["preflight_pass"] is False
        assert "sw_connection_guard_not_pass" in summary["failure_bucket"]
        assert "solidworks_com_active_object_timeout" in summary["failure_bucket"]
        assert (out_dir / "sw_connection_guard.json").exists()
        assert (out_dir / "sw_safe_restart_workflow.json").exists()
        assert not any(path.name.startswith("01_") for path in out_dir.iterdir())


def test_lb26001_006_stage_aborts_before_sw_com_when_readiness_fails() -> None:
    with TemporaryDirectory() as tmp:
        out_dir = Path(tmp) / "stage"
        summary = run_stage(
            "LB26001_006",
            [Path("LB26001-A-04-006.SLDPRT")],
            out_dir,
            timeout_s=1,
            max_rounds=1,
            sw_guard={
                "schema": "sw_drawing_studio.sw_connection_guard.v4",
                "status": "pass",
                "connected": True,
                "safe_to_start_cad_job": True,
                "do_not_continue_batch": False,
            },
            lb26001_readiness={
                "schema": "sw_drawing_studio.lb26001_006_regression_readiness.v4_2",
                "status": "blocked",
                "ready_to_start_locked_006_cad": False,
                "blocking_issue_keys": ["solidworks_not_responding"],
                "ui_visual_review_gate": "drw_output/ui_acceptance/LB26001_006/closed_loop_strict_final_20260624/ui_visual_review_gate_summary.json",
                "lb26001_expansion_gate": "drw_output/ui_acceptance/LB26001_006/closed_loop_strict_final_20260624/lb26001_acceptance_gate_v4_2.json",
                "solidworks_lock_present": True,
                "solidworks_lock_stale": True,
                "solidworks_lock_conflict": {
                    "reason": "solidworks_lock_is_stale",
                    "fix_suggestion": "Confirm stale owner before next lock acquisition.",
                },
                "solidworks_lock_owner": {
                    "owner_job_id": "old-health",
                    "owner_run_id": "system_health_old-health",
                    "operation": "solidworks_com_probe:get_active_object",
                },
                "solidworks_lock_fix_suggestion": "Confirm stale owner before next lock acquisition.",
                "safe_recovery_guidance": {
                    "manual_recovery_required": True,
                    "automatic_restart_allowed": False,
                    "steps": ["Manually save or close unsaved SolidWorks work."],
                },
                "issues": [
                    {
                        "key": "solidworks_not_responding",
                        "severity": "critical",
                        "fix_suggestion": "Save documents and restart SolidWorks safely.",
                    }
                ],
            },
        )

        assert summary["status"] == "fail"
        assert summary["processed"] == 0
        assert summary["cases"] == []
        assert summary["preflight_pass"] is False
        assert summary["readiness_preflight_pass"] is False
        assert summary["rerun_packet_preflight_pass"] is False
        assert summary["sw_connection_guard_skipped_due_to_readiness"] is True
        assert summary["sw_connection_guard_skipped_due_to_006_preflight"] is True
        assert "lb26001_006_readiness_not_ready" in summary["failure_bucket"]
        assert "lb26001_006_rerun_packet_blocked_by_readiness" in summary["failure_bucket"]
        assert "lb26001_006_rerun_packet_not_ready" not in summary["failure_bucket"]
        assert "solidworks_not_responding" in summary["failure_bucket"]
        assert "sw_connection_guard_not_pass" not in summary["failure_bucket"]
        assert summary["lb26001_006_readiness_status"] == "blocked"
        assert summary["lb26001_006_rerun_packet_build_ready"] is True
        assert summary["lb26001_006_rerun_packet_blocked_only_by_readiness"] is True
        assert summary["lb26001_006_manual_recovery_required"] is True
        assert summary["lb26001_006_automatic_restart_allowed"] is False
        assert summary["lb26001_006_solidworks_lock_present"] is True
        assert summary["lb26001_006_solidworks_lock_stale"] is True
        assert summary["lb26001_006_solidworks_lock_conflict"]["reason"] == "solidworks_lock_is_stale"
        assert summary["lb26001_006_solidworks_lock_owner"]["owner_job_id"] == "old-health"
        assert summary["lb26001_006_solidworks_lock_fix_suggestion"] == "Confirm stale owner before next lock acquisition."
        assert "closed_loop_strict_final_20260624" in summary["lb26001_006_ui_visual_review_gate"]
        assert summary["lb26001_006_safe_recovery_guidance"]["steps"] == [
            "Manually save or close unsaved SolidWorks work."
        ]
        assert (out_dir / "lb26001_006_regression_readiness_v4_2.json").exists()
        assert summary["lb26001_006_readiness_report_md"] == str(
            out_dir / "lb26001_006_regression_readiness_v4_2.md"
        )
        assert (out_dir / "lb26001_006_regression_readiness_v4_2.md").exists()
        assert (out_dir / "lb26001_006_rerun_packet_v4_2.json").exists()
        assert not (out_dir / "sw_connection_guard.json").exists()
        assert not any(path.name.startswith("01_") for path in out_dir.iterdir())


def test_lb26001_006_stage_aborts_before_sw_com_when_rerun_packet_fails() -> None:
    with TemporaryDirectory() as tmp:
        out_dir = Path(tmp) / "stage"
        summary = run_stage(
            "LB26001_006",
            [Path("LB26001-A-04-006.SLDPRT")],
            out_dir,
            timeout_s=1,
            max_rounds=1,
            sw_guard={
                "schema": "sw_drawing_studio.sw_connection_guard.v4",
                "status": "pass",
                "connected": True,
                "safe_to_start_cad_job": True,
                "do_not_continue_batch": False,
            },
            lb26001_readiness={
                "schema": "sw_drawing_studio.lb26001_006_regression_readiness.v4_2",
                "status": "ready",
                "ready_to_start_locked_006_cad": True,
                "blocking_issue_keys": [],
                "issues": [],
            },
            lb26001_rerun_packet={
                "schema": "sw_drawing_studio.lb26001_006_rerun_packet.v4_2",
                "status": "offline_prerequisites_missing",
                "real_cad_allowed_now": False,
                "offline_prerequisite_missing_keys": ["006_application_ui_fail_is_latest_gate"],
                "source_signatures": {
                    "generator": {"pass": True},
                    "lb26001_correction_plan_v4_2": {"pass": False},
                    "apply_ui_visual_review_v4": {"pass": False},
                },
                "current_006_ui_verdict": {
                    "latest_manual_review": "manual_visual_judgement.json",
                    "comparison_image": "006_reference_vs_generated.png",
                    "latest_manual_findings": [
                        "Generated drawing still fails the UI screenshot comparison.",
                    ],
                    "latest_manual_visual_checklist": {
                        "view_layout": False,
                        "display_dimensions": False,
                    },
                    "latest_manual_visual_checklist_notes": {
                        "view_layout": "View layout differs from the reference.",
                    },
                    "latest_manual_required_correction": "Repair 006 from UI screenshot evidence.",
                    "ui_screenshot_files": ["006_ui.png"],
                    "application_ui_screenshot_paths_existing_application_ui": ["006_ui_existing.png"],
                    "generated_png": "006_generated.png",
                    "reference_png": "006_reference.png",
                    "failed_visual_checklist_items": [
                        "view_layout",
                        "display_dimensions",
                    ],
                    "correction_actions": [
                        {"check": "view_layout"},
                        {"check": "display_dimensions"},
                    ],
                },
                "offline_prerequisites": [
                    {
                        "key": "006_application_ui_fail_is_latest_gate",
                        "pass": False,
                        "fix_suggestion": "Close the latest Drawing Review UI screenshot judgement before CAD.",
                    },
                    {
                        "key": "correction_plan_matches_current_006_status",
                        "pass": False,
                        "fix_suggestion": "Regenerate the correction plan from current requested-status.",
                    },
                    {
                        "key": "006_effective_ui_corrections_present",
                        "pass": True,
                        "fix_suggestion": "Regenerate the correction plan so UI findings become actions.",
                    },
                    {
                        "key": "correction_plan_source_signatures_present",
                        "pass": False,
                        "fix_suggestion": "Restore correction-plan direct UI finding mapping.",
                    },
                ],
            },
        )

        assert summary["status"] == "fail"
        assert summary["processed"] == 0
        assert summary["cases"] == []
        assert summary["preflight_pass"] is False
        assert summary["readiness_preflight_pass"] is True
        assert summary["rerun_packet_preflight_pass"] is False
        assert summary["sw_connection_guard_skipped_due_to_readiness"] is False
        assert summary["sw_connection_guard_skipped_due_to_006_preflight"] is True
        assert summary["lb26001_006_rerun_packet_status"] == "offline_prerequisites_missing"
        assert summary["lb26001_006_source_signature_summary"] == {
            "generator": True,
            "lb26001_correction_plan_v4_2": False,
            "apply_ui_visual_review_v4": False,
        }
        assert summary["lb26001_006_offline_prerequisite_summary"]["006_application_ui_fail_is_latest_gate"] is False
        assert summary["lb26001_006_offline_prerequisite_summary"]["correction_plan_matches_current_006_status"] is False
        assert summary["lb26001_006_offline_prerequisite_summary"]["006_effective_ui_corrections_present"] is True
        assert summary["lb26001_006_correction_plan_freshness_pass"] is False
        assert summary["lb26001_006_effective_ui_corrections_present"] is True
        assert summary["lb26001_006_correction_plan_source_signature_pass"] is False
        assert summary["lb26001_006_failed_visual_checks"] == [
            "view_layout",
            "display_dimensions",
        ]
        assert summary["lb26001_006_correction_action_count"] == 2
        assert summary["lb26001_006_comparison_image"] == "006_reference_vs_generated.png"
        assert summary["lb26001_006_latest_manual_findings"] == [
            "Generated drawing still fails the UI screenshot comparison."
        ]
        assert summary["lb26001_006_latest_manual_required_correction"] == (
            "Repair 006 from UI screenshot evidence."
        )
        assert summary["lb26001_006_ui_evidence"]["latest_manual_visual_checklist"]["view_layout"] is False
        assert summary["lb26001_006_ui_evidence"]["latest_manual_visual_checklist_notes"]["view_layout"] == (
            "View layout differs from the reference."
        )
        assert summary["lb26001_006_ui_evidence"]["ui_screenshot_files"] == ["006_ui.png"]
        assert summary["lb26001_006_ui_evidence"]["application_ui_screenshot_paths_existing_application_ui"] == [
            "006_ui_existing.png"
        ]
        assert summary["lb26001_006_ui_evidence"]["generated_png"] == "006_generated.png"
        assert summary["lb26001_006_ui_evidence"]["reference_png"] == "006_reference.png"
        assert "lb26001_006_rerun_packet_not_ready" in summary["failure_bucket"]
        assert "lb26001_006_readiness_not_ready" not in summary["failure_bucket"]
        assert "006_application_ui_fail_is_latest_gate" in summary["failure_bucket"]
        assert "sw_connection_guard_not_pass" not in summary["failure_bucket"]
        assert (out_dir / "lb26001_006_regression_readiness_v4_2.json").exists()
        assert (out_dir / "lb26001_006_rerun_packet_v4_2.json").exists()
        assert not (out_dir / "sw_connection_guard.json").exists()
        assert not any(path.name.startswith("01_") for path in out_dir.iterdir())


def test_core_12_stage_resolves_validation_set() -> None:
    parts = _resolve_parts("core_12", [])

    assert len(parts) == 12
    assert all(path.exists() for path in parts)
    assert any(path.name == "LB26001-A-04-001.SLDPRT" for path in parts)


def test_lb26001_006_stage_resolves_single_required_first_case() -> None:
    parts = _resolve_parts("LB26001_006", [])

    assert len(parts) == 1
    assert parts[0].exists()
    assert parts[0].name == "LB26001-A-04-006.SLDPRT"


def test_lb26001_36_stage_resolves_validation_set() -> None:
    parts = _resolve_parts("LB26001_36", [])

    assert len(parts) == 36
    assert all(path.exists() for path in parts)
    assert parts[0].name == "LB26001-A-04-001.SLDPRT"
    assert parts[-1].name == "LB26001-A-04-050.SLDPRT"
    assert not any(path.name == "LB26001-A-04-043.SLDPRT" for path in parts)


def test_lb26001_36_requires_97_percent_deliverable_target() -> None:
    passing_cases = [
        {
            "deliverable": True,
            "status": "pass",
            "failure_bucket": [],
        }
        for _ in range(35)
    ]
    review_case = {
        "deliverable": False,
        "status": "need_review",
        "failure_bucket": ["reference_compare_not_pass"],
    }

    summary = _stage_summary(
        stage="LB26001_36",
        out_dir=Path("drw_output/staged_validation/LB26001_36/example"),
        started=0.0,
        cases=passing_cases + [review_case],
        total=36,
        final=True,
    )

    assert summary["required_deliverable_count"] == 35
    assert summary["acceptance_pass"] is True
    assert summary["execution_completed"] is True
    assert summary["status"] == "pass_with_warning"
    assert summary["pass"] is True


def test_no_reference_report_is_explicit_pass_evidence() -> None:
    with TemporaryDirectory() as tmp:
        out = Path(tmp) / "reference_compare.json"
        payload = _write_no_reference_report(
            part=Path("3D转2D测试图纸/no_reference_part.SLDPRT"),
            run_dir=Path("drw_output/runs/example"),
            out_path=out,
        )

    assert payload["status"] == "no_reference"
    assert payload["pass"] is True
    assert payload["reasons"] == ["no_same_name_reference_slddrw"]


def test_reference_style_report_blocks_view_type_drift() -> None:
    with TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        reference_report = tmp_path / "reference_compare.json"
        dimension_report = tmp_path / "dimension_validation.json"
        style_report = tmp_path / "reference_style.json"

        reference_report.write_text(
            """
{
  "pass": true,
  "status": "pass",
  "reference_metrics": {
    "success": true,
    "view_count": 2,
    "view_types": {"7": 1, "4": 1},
    "display_dim_count": 2,
    "view_outlines": [
      {"name": "front", "type": "7", "outline": [0.04, 0.11, 0.12, 0.18]},
      {"name": "top", "type": "4", "outline": [0.04, 0.03, 0.12, 0.09]}
    ],
    "sheet": {"paper_size": [0.297, 0.21]}
  },
  "generated_metrics": {
    "success": true,
    "view_count": 3,
    "view_types": {"7": 1, "4": 1, "3": 1},
    "display_dim_count": 2,
    "view_outlines": [
      {"name": "front", "type": "7", "outline": [0.04, 0.11, 0.12, 0.18]},
      {"name": "top", "type": "4", "outline": [0.04, 0.03, 0.12, 0.09]},
      {"name": "section", "type": "3", "outline": [0.16, 0.10, 0.24, 0.17]}
    ],
    "sheet": {"paper_size": [0.297, 0.21]}
  }
}
""".strip(),
            encoding="utf-8",
        )
        dimension_report.write_text('{"pass": true, "display_dim_count": 2}', encoding="utf-8")

        style = _write_reference_style_report(
            part=Path("LB26001-A-04-008.SLDPRT"),
            reference_report=reference_report,
            dimension_report=dimension_report,
            out_path=style_report,
        )
        case = _case_summary(
            part=Path("LB26001-A-04-008.SLDPRT"),
            case_dir=tmp_path,
            cad={"pass": True, "run_dir": "run"},
            dim={"pass": True, "status": "pass"},
            ref={"pass": True, "status": "pass"},
            commands={},
            style=style,
            vision={"visual_acceptance_pass": True, "status": "pass"},
        )

    keys = [item["key"] for item in style["differences"]]
    assert style["pass"] is False
    assert style["status"] == "need_review"
    assert "view_count_not_equal_reference" in keys
    assert "view_type_extra_than_reference" in keys
    assert case["deliverable"] is False
    assert "reference_style_not_pass" in case["failure_bucket"]


def test_vision_qc_v6_report_blocks_staged_deliverable_without_ui_review() -> None:
    with TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        run_dir = tmp_path / "runs" / "case"
        drawing_dir = run_dir / "drawing"
        qc_dir = run_dir / "qc"
        drawing_dir.mkdir(parents=True)
        qc_dir.mkdir(parents=True)
        base = "LB26001-A-04-006"
        png = drawing_dir / f"{base}_v5.PNG"
        image = Image.new("RGB", (640, 420), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle([80, 80, 260, 150], outline="black", width=2)
        draw.line([430, 360, 620, 360], fill="black", width=1)
        image.save(png)
        (qc_dir / "drawing_blueprint.json").write_text(
            """
{
  "schema": "sw_drawing_studio.drawing_blueprint.v4",
  "base": "LB26001-A-04-006",
  "part_class": "machined_part",
  "view_plan": [{"slot": "front", "required": true, "center_norm": [0.37, 0.80]}],
  "dimension_plan": {"required_display_dim_count": 1, "allow_note_substitution": false},
  "notes_plan": {},
  "validation_plan": {"require_ui_visual_review": true},
  "layout_plan": {"titlebar_box_norm": [0.68, 0.0, 1.0, 0.18]}
}
""".strip(),
            encoding="utf-8",
        )
        (qc_dir / f"{base}_v5_qc.json").write_text('{"pass": true, "display_dim_count": 1}', encoding="utf-8")
        case_dir = tmp_path / "case"
        report = _write_vision_qc_v6_report(
            part=Path(f"{base}.SLDPRT"),
            run_dir=run_dir,
            case_dir=case_dir,
            out_path=case_dir / "vision_qc_v6.json",
        )
        case = _case_summary(
            part=Path(f"{base}.SLDPRT"),
            case_dir=case_dir,
            cad={"pass": True, "run_dir": str(run_dir)},
            dim={"pass": True, "status": "pass"},
            ref={"pass": True, "status": "pass"},
            commands={},
            style={"pass": True, "status": "pass"},
            vision=report,
        )

    assert report["status"] == "need_review"
    assert report["visual_acceptance_pass"] is False
    assert any(issue["key"] == "manual_ui_screenshot_review_required" for issue in report["issues"])
    assert case["deliverable"] is False
    assert "vision_qc_v6_not_pass" in case["failure_bucket"]


def test_reference_compare_v4_report_blocks_staged_deliverable() -> None:
    case = _case_summary(
        part=Path("LB26001-A-04-006.SLDPRT"),
        case_dir=Path("drw_output/staged_validation/LB26001_ref6/example"),
        cad={"pass": True, "run_dir": "run"},
        dim={"pass": True, "status": "pass"},
        ref={"pass": True, "status": "pass"},
        commands={},
        style={"pass": True, "status": "pass"},
        vision={"visual_acceptance_pass": True, "status": "pass"},
        reference_v4={
            "pass": False,
            "status": "need_review",
            "reasons": ["ui_screenshot_visual_acceptance_not_passed"],
        },
    )

    assert case["deliverable"] is False
    assert case["reference_compare_v4_pass"] is False
    assert case["reference_compare_v4_status"] == "need_review"
    assert "reference_compare_v4_not_pass" in case["failure_bucket"]


def test_reference_compare_v4_report_consumes_cad_generator_warnings() -> None:
    with TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        run_dir = tmp_path / "runs" / "case"
        qc_dir = run_dir / "qc"
        qc_dir.mkdir(parents=True)
        case_dir = tmp_path / "case"
        case_dir.mkdir()
        base = "LB26001-A-04-006"
        blueprint = {
            "schema": "sw_drawing_studio.drawing_blueprint.v4",
            "base": base,
            "part_class": "machined_part",
            "drawing_purpose": "manufacturing",
            "view_plan": [
                {"slot": "front", "view_type": "named", "required": True, "sw_view_type": "7", "create_method": "named_view"},
                {"slot": "top", "view_type": "projected", "required": True, "sw_view_type": "4", "create_method": "projection_api", "projected_from": "front"},
                {"slot": "right", "view_type": "projected", "required": True, "sw_view_type": "4", "create_method": "projection_api", "projected_from": "front"},
                {"slot": "iso", "view_type": "iso", "required": True, "sw_view_type": "7", "create_method": "named_view"},
            ],
            "dimension_plan": {
                "required_display_dim_count": 12,
                "reference_display_dim_count": 12,
                "allow_note_substitution": False,
                "dimension_targets": [
                    {"key": "overall_length"},
                    {"key": "hole_pitch"},
                    {"key": "projection_view_height"},
                ],
            },
            "annotation_plan": {"roughness_required": True},
            "titlebar_plan": {"required_fields": ["drawing_no", "name", "material"], "missing_fields": []},
            "notes_plan": {"required_notes": ["TECHNICAL REQUIREMENTS"], "raw_reference_notes": ["TECHNICAL REQUIREMENTS"]},
            "validation_plan": {"require_ui_visual_review": True},
        }
        profiles = {
            "profiles": {
                base: {
                    "base": base,
                    "view_count": 4,
                    "view_types": {"7": 2, "4": 2},
                    "display_dim_count": 12,
                    "normalized_notes": [{"text": "TECHNICAL REQUIREMENTS"}],
                    "roughness_symbols": [{}],
                    "datum_symbols": [],
                }
            }
        }
        warnings = {
            "reference_intent_target_coverage": [
                {
                    "stage": "post_layout_final",
                    "display_dim_count": 12,
                    "target_count": 3,
                    "covered_count": 3,
                    "covered_target_keys": ["overall_length", "hole_pitch", "projection_view_height"],
                    "missing_target_keys": [],
                    "persisted_after_reopen": True,
                }
            ]
        }
        vision = {
            "visual_acceptance_pass": True,
            "status": "pass",
            "checks": {
                "ui_screenshot_review": {"required": True, "pass": True},
                "titlebar": {"detected": True},
                "notes": {"detected": True, "technical_requirements_detected": True},
                "reference_visual_compare": {"coarse_layout_match": True},
                "symbols": {"missing": []},
            },
            "issues": [],
        }
        dimension = {"pass": True, "dimension_validation": {"display_dim_count": 12, "note_dim_count": 0}}
        blueprint_path = qc_dir / "drawing_blueprint.json"
        warnings_path = qc_dir / f"{base}_v5_warnings.json"
        profiles_path = tmp_path / "reference_profiles_v4.json"
        cad_report = case_dir / "cad_smoke.json"
        dimension_report = case_dir / "dimension_validation.json"
        vision_report = case_dir / "vision_qc_v6.json"
        reference_report = case_dir / "reference_compare.json"
        style_report = case_dir / "reference_style.json"
        out = case_dir / "reference_compare_v4.json"
        blueprint_path.write_text(staged_module.json.dumps(blueprint, ensure_ascii=False), encoding="utf-8")
        warnings_path.write_text(staged_module.json.dumps(warnings, ensure_ascii=False), encoding="utf-8")
        profiles_path.write_text(staged_module.json.dumps(profiles, ensure_ascii=False), encoding="utf-8")
        cad_report.write_text(
            staged_module.json.dumps({"artifacts": {"warnings_json": {"path": str(warnings_path)}}}, ensure_ascii=False),
            encoding="utf-8",
        )
        dimension_report.write_text(staged_module.json.dumps(dimension, ensure_ascii=False), encoding="utf-8")
        vision_report.write_text(staged_module.json.dumps(vision, ensure_ascii=False), encoding="utf-8")
        reference_report.write_text('{"pass": true, "status": "pass"}', encoding="utf-8")
        style_report.write_text('{"pass": true, "status": "pass"}', encoding="utf-8")
        original_profiles = staged_module.DEFAULT_REFERENCE_PROFILES_V4
        staged_module.DEFAULT_REFERENCE_PROFILES_V4 = profiles_path
        try:
            payload = _write_reference_compare_v4_report(
                Path(f"{base}.SLDPRT"),
                run_dir,
                case_dir,
                cad_report,
                dimension_report,
                vision_report,
                reference_report,
                style_report,
                out,
            )
        finally:
            staged_module.DEFAULT_REFERENCE_PROFILES_V4 = original_profiles

    assert payload["pass"] is True
    assert payload["artifacts"]["generator_warnings"] == str(warnings_path)
    assert payload["generated"]["reference_intent_target_coverage"]["missing_target_keys"] == []


def test_generator_warnings_from_cad_report_prefers_report_artifact() -> None:
    with TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        run_dir = tmp_path / "run"
        warnings = run_dir / "qc" / "explicit_warnings.json"
        warnings.parent.mkdir(parents=True)
        warnings.write_text("{}", encoding="utf-8")
        cad_report = tmp_path / "cad_smoke.json"
        cad_report.write_text(
            staged_module.json.dumps({"artifacts": {"warnings_json": {"path": str(warnings)}}}, ensure_ascii=False),
            encoding="utf-8",
        )

        result = _generator_warnings_from_cad_report(cad_report, run_dir, "LB26001-A-04-006")

    assert result == warnings


def test_displaydim_lifecycle_audit_missing_warnings_blocks_006_case() -> None:
    with TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        case_dir = tmp_path / "case"
        case_dir.mkdir()
        cad_report = case_dir / "cad_smoke.json"
        dimension_report = case_dir / "dimension_validation.json"
        out_json = case_dir / "displaydim_lifecycle_audit.json"
        out_md = case_dir / "displaydim_lifecycle_audit.md"
        cad_report.write_text(staged_module.json.dumps({"pass": True, "run_dir": str(run_dir)}), encoding="utf-8")
        dimension_report.write_text(staged_module.json.dumps({"pass": True}), encoding="utf-8")

        payload = _write_displaydim_lifecycle_audit_report(
            Path("LB26001-A-04-006.SLDPRT"),
            run_dir,
            cad_report,
            dimension_report,
            out_json,
            out_md,
        )
        out_json_exists = out_json.exists()
        out_md_exists = out_md.exists()

    assert payload["applicable"] is True
    assert payload["pass"] is False
    assert "displaydim_lifecycle_warnings_missing" in payload["blocking_issue_keys"]
    assert payload["ui_screenshot_review_is_final_gate"] is True
    assert out_json_exists is True
    assert out_md_exists is True


def test_no_reference_style_report_is_explicit_pass_evidence() -> None:
    with TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        reference_report = tmp_path / "reference_compare.json"
        style_report = tmp_path / "reference_style.json"
        no_ref = _write_no_reference_report(
            part=Path("3D转2D测试图纸/no_reference_part.SLDPRT"),
            run_dir=Path("drw_output/runs/example"),
            out_path=reference_report,
        )
        style = _write_reference_style_report(
            part=Path("3D转2D测试图纸/no_reference_part.SLDPRT"),
            reference_report=reference_report,
            dimension_report=tmp_path / "dimension_validation.json",
            out_path=style_report,
        )

    assert no_ref["pass"] is True
    assert style["status"] == "no_reference"
    assert style["pass"] is True
    assert style["reasons"] == ["no_same_name_reference_slddrw"]


if __name__ == "__main__":
    test_lb26001_006_real_cad_path_uses_facade_qprocess_worker()
    test_stage_with_bucketed_failure_is_need_review_not_acceptance_pass()
    test_stage_without_evidence_is_fail()
    test_stage_requires_visual_acceptance_not_api_pass_only()
    test_stage_aborts_before_cad_when_sw_connection_guard_fails()
    test_lb26001_006_stage_aborts_before_sw_com_when_readiness_fails()
    test_lb26001_006_stage_aborts_before_sw_com_when_rerun_packet_fails()
    test_core_12_stage_resolves_validation_set()
    test_lb26001_006_stage_resolves_single_required_first_case()
    test_lb26001_36_stage_resolves_validation_set()
    test_lb26001_36_requires_97_percent_deliverable_target()
    test_no_reference_report_is_explicit_pass_evidence()
    test_reference_style_report_blocks_view_type_drift()
    test_vision_qc_v6_report_blocks_staged_deliverable_without_ui_review()
    test_reference_compare_v4_report_blocks_staged_deliverable()
    test_reference_compare_v4_report_consumes_cad_generator_warnings()
    test_generator_warnings_from_cad_report_prefers_report_artifact()
    test_displaydim_lifecycle_audit_missing_warnings_blocks_006_case()
    test_no_reference_style_report_is_explicit_pass_evidence()
    print("PASS test_v3_staged_cad_validation")
