import json
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.validation.lb26001_006_rerun_packet_v4_2 import (
    ACCEPTANCE_GATE_SIGNATURES,
    ACCEPTANCE_PROOF_SIGNATURES,
    APPLY_UI_REVIEW_SIGNATURES,
    APPLICATION_UI_SCREENSHOT_VALIDATOR_SIGNATURES,
    CAD_WORKER_SIGNATURES,
    CORRECTION_PLAN_SIGNATURES,
    DIMENSION_ARRANGE_SIGNATURES,
    DIMENSION_VISUAL_VALIDATOR_SIGNATURES,
    DRAWING_VISUAL_REVIEW_SUITE_SIGNATURES,
    GENERATOR_SIGNATURES,
    LIFECYCLE_AUDIT_SIGNATURES,
    MANUAL_VISUAL_JUDGEMENT_TEMPLATE_SIGNATURES,
    REAL_CAD_SMOKE_SIGNATURES,
    REFERENCE_COMPARE_SIGNATURES,
    STAGED_VALIDATION_SIGNATURES,
    VISION_QC_V6_SIGNATURES,
    build_rerun_packet,
    render_markdown,
)


def _source_file(path: Path, signatures: dict[str, str], *, omit: str = "") -> Path:
    text = "\n".join(value for key, value in signatures.items() if key != omit)
    path.write_text(text, encoding="utf-8")
    return path


def _artifact(path: Path, keys: list[str]) -> Path:
    path.write_text(
        json.dumps({key: True for key in keys}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def _requested_status(*, generated_png_source_pass: bool = True, include_failed_items: bool = True) -> dict:
    bases = [
        "LB26001-A-04-006",
        "LB26001-A-04-007",
        "LB26001-A-04-008",
        "LB26001-A-04-009",
        "LB26001-A-04-015",
        "LB26001-A-04-022",
    ]
    return {
        "status": "blocked_by_006",
        "pass_count": 0,
        "not_pass_count": 6,
        "all_generated_drawings_currently_unqualified": True,
        "requested_bases": bases,
        "base_results": [
            {
                "base": base,
                "status": "manual_visual_checklist_failed",
                "pass": False,
                "application_ui_screenshot_review_present": True,
                "manual_visual_checklist_pass": False,
                "application_ui_screenshot_content_check_pass": True,
                "generated_png_source_pass": generated_png_source_pass,
                "generated_png_source_evidence": {"under_run_dir": generated_png_source_pass},
                "latest_manual_review": f"{base}_manual.json",
                "source_ui_report": "drawing_visual_review_report.json",
                "source_ui_report_mode": "source_qt_application_ui_screenshot",
                "manual_visual_checklist_failed_items": [
                    "reference_match",
                    "view_layout",
                    "display_dimensions",
                    "dimension_readability",
                    "title_block",
                    "manufacturing_notes",
                ] if include_failed_items else [],
                "latest_manual_required_correction": "Rerun 006 first through UI screenshot closure.",
                "ui_screenshot_files": [f"{base}.png"],
                "application_ui_screenshot_paths_existing_application_ui": [f"{base}_ui.png"],
                "comparison_image": f"{base}_reference_vs_generated.png",
                "generated_png": f"{base}_generated.png",
                "reference_png": f"{base}_reference.png",
                "latest_manual_visual_checklist": {
                    "reference_match": False,
                    "view_layout": False,
                    "display_dimensions": False,
                },
                "latest_manual_visual_checklist_notes": {
                    "reference_match": "Generated drawing does not match the same-name reference.",
                },
                "latest_manual_findings": [
                    "Generated drawing still fails the application UI screenshot comparison.",
                ],
            }
            for base in bases
        ],
    }


def _correction_plan(
    *,
    generated_png_source_pass: bool = True,
    stale_manual_review: bool = False,
    screenshot_content_pass: bool = True,
) -> dict:
    return {
        "status": "blocked_by_solidworks_readiness",
        "correction_plan_ready": True,
        "missing_reference_rules": [],
        "entries": [
            {
                "base": "LB26001-A-04-006",
                "correction_stage": "pilot_006_first",
                "blocked_by_readiness": True,
                "current_ui_status": {
                    "status": "manual_visual_checklist_failed",
                    "latest_manual_review": "stale_manual.json" if stale_manual_review else "LB26001-A-04-006_manual.json",
                    "generated_png_source_pass": generated_png_source_pass,
                    "application_ui_screenshot_content_check_pass": screenshot_content_pass,
                },
                "reference_intent_trace_policy": {
                    "required": True,
                    "final_stage_required": "post_layout_final",
                },
                "ui_visual_failures": {
                    "direct_ui_findings_used_for_correction": True,
                    "effective_failed_visual_checks": [
                        "reference_match",
                        "view_layout",
                        "display_dimensions",
                        "dimension_readability",
                        "title_block",
                        "manufacturing_notes",
                    ],
                },
                "correction_actions": [
                    {
                        "check": "view_layout",
                        "source_type": "direct_ui_screenshot_finding",
                        "correction_action": "Use the learned normalized layout slots.",
                    },
                    {
                        "check": "display_dimensions",
                        "source_type": "direct_ui_screenshot_finding",
                        "correction_action": "Create explicit reference-intent SolidWorks DisplayDim objects.",
                    },
                ],
            }
        ],
    }


def _build_packet_fixture(
    *,
    readiness_ready: bool,
    omit_generator_signature: str = "",
    omit_cad_worker_signature: str = "",
    omit_lifecycle_audit_signature: str = "",
    omit_vision_qc_v6_signature: str = "",
    omit_application_ui_screenshot_validator_signature: str = "",
    omit_dimension_arrange_signature: str = "",
    omit_dimension_visual_signature: str = "",
    omit_acceptance_gate_signature: str = "",
    omit_acceptance_proof_signature: str = "",
    omit_correction_plan_signature: str = "",
    omit_staged_validation_signature: str = "",
    omit_real_cad_smoke_signature: str = "",
    omit_drawing_visual_review_signature: str = "",
    omit_manual_visual_judgement_template_signature: str = "",
    generated_png_source_pass: bool = True,
    include_failed_items: bool = True,
    stale_correction_plan: bool = False,
    stale_screenshot_content_status: bool = False,
    omit_ui_defect_callout_next_check: bool = False,
    omit_ui_defect_closure_contract_bucket: str = "",
    omit_ui_defect_callout_closure_keys: bool = False,
    omit_ui_defect_screenshot_observation_bucket: str = "",
) -> dict:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        generator_source = _source_file(root / "drw_generate_v6.py", GENERATOR_SIGNATURES, omit=omit_generator_signature)
        cad_worker_source = _source_file(
            root / "cad_job_worker.py",
            CAD_WORKER_SIGNATURES,
            omit=omit_cad_worker_signature,
        )
        reference_compare_source = _source_file(root / "reference_compare_v4.py", REFERENCE_COMPARE_SIGNATURES)
        vision_qc_v6_source = _source_file(
            root / "vision_qc_v6.py",
            VISION_QC_V6_SIGNATURES,
            omit=omit_vision_qc_v6_signature,
        )
        application_ui_screenshot_validator_source = _source_file(
            root / "application_ui_screenshot_validator.py",
            APPLICATION_UI_SCREENSHOT_VALIDATOR_SIGNATURES,
            omit=omit_application_ui_screenshot_validator_signature,
        )
        dimension_arrange_source = _source_file(
            root / "dimension_arrange_service.py",
            DIMENSION_ARRANGE_SIGNATURES,
            omit=omit_dimension_arrange_signature,
        )
        dimension_visual_source = _source_file(
            root / "dimension_visual_validator.py",
            DIMENSION_VISUAL_VALIDATOR_SIGNATURES,
            omit=omit_dimension_visual_signature,
        )
        lifecycle_audit_source = _source_file(
            root / "lb26001_006_displaydim_lifecycle_audit_v4_2.py",
            LIFECYCLE_AUDIT_SIGNATURES,
            omit=omit_lifecycle_audit_signature,
        )
        staged_validation_source = _source_file(
            root / "staged_cad_validation_v3.py",
            STAGED_VALIDATION_SIGNATURES,
            omit=omit_staged_validation_signature,
        )
        real_cad_smoke_source = _source_file(
            root / "real_cad_smoke_v3.py",
            REAL_CAD_SMOKE_SIGNATURES,
            omit=omit_real_cad_smoke_signature,
        )
        drawing_visual_review_source = _source_file(
            root / "drawing_visual_review_suite.py",
            DRAWING_VISUAL_REVIEW_SUITE_SIGNATURES,
            omit=omit_drawing_visual_review_signature,
        )
        manual_visual_judgement_template_source = _source_file(
            root / "manual_visual_judgement_template_v4.py",
            MANUAL_VISUAL_JUDGEMENT_TEMPLATE_SIGNATURES,
            omit=omit_manual_visual_judgement_template_signature,
        )
        correction_plan_source = _source_file(
            root / "lb26001_correction_plan_v4_2.py",
            CORRECTION_PLAN_SIGNATURES,
            omit=omit_correction_plan_signature,
        )
        apply_ui_review_source = _source_file(root / "apply_ui_visual_review_v4.py", APPLY_UI_REVIEW_SIGNATURES)
        acceptance_gate_source = _source_file(
            root / "lb26001_acceptance_gate_v4_2.py",
            ACCEPTANCE_GATE_SIGNATURES,
            omit=omit_acceptance_gate_signature,
        )
        acceptance_proof_source = _source_file(
            root / "lb26001_006_acceptance_proof_v4_2.py",
            ACCEPTANCE_PROOF_SIGNATURES,
            omit=omit_acceptance_proof_signature,
        )
        plan = _artifact(
            root / "reference_intent_dimension_plan_006.json",
            ["target_key", "post_layout_final", "AddDiameterDimension2"],
        )
        contract = _artifact(
            root / "reference_intent_dimension_contract_006.json",
            ["target_key", "selected_entity", "persisted_after_reopen"],
        )
        ui_defect_buckets = root / "lb26001_006_ui_defect_buckets_v4_4.json"
        required_active_buckets = [
            "dimension_visual_overdense",
            "dimension_lane_wrong",
            "note_missing_or_wrong",
            "titlebar_incomplete",
            "projection_view_style_mismatch",
        ]
        required_next_buckets = required_active_buckets + ([] if omit_ui_defect_callout_next_check else ["callout_missing"])
        next_screenshot_checklist = [
            {"bucket": key, "required": True}
            for key in required_active_buckets
        ]
        if not omit_ui_defect_callout_next_check:
            next_screenshot_checklist.append({
                "bucket": "callout_missing",
                "required": True,
                "required_callout_keys": ["thread_callout_m4_6h", "surface_finish_rest_3_2"],
                "absence_check_keys": ["radius_callout", "chamfer_callout"],
            })
        screenshot_visual_observations = []
        for key in required_active_buckets + ["callout_missing"]:
            if key == omit_ui_defect_screenshot_observation_bucket:
                continue
            screenshot_visual_observations.append({
                "bucket": key,
                "observation_key": f"{key}_application_ui_screenshot_observation",
                "source": "application_drawing_review_ui_screenshot",
                "source_paths": ["LB26001-A-04-006_ui.png"],
                "visual_check": "reference_match" if key == "callout_missing" else "display_dimensions",
                "visual_check_pass": None if key == "callout_missing" else False,
                "manual_note": "fixture screenshot observation",
                "visual_fact": "fixture visual fact",
                "reference_expectation": "fixture reference expectation",
                "generated_failure": "fixture generated failure",
                "repair_signal": "fixture repair signal",
                "supports_active_bucket": key != "callout_missing",
                "next_screenshot_check_required": True,
                "api_or_displaydim_metric_alone_can_close": False,
            })
        bucket_closure_contract = []
        for key in required_active_buckets + ["callout_missing"]:
            if key == omit_ui_defect_closure_contract_bucket:
                continue
            item = {
                "bucket": key,
                "source_failure_evidence": [
                    "application_drawing_review_ui_screenshot",
                    "manual_visual_judgement_failed_checklist",
                ],
                "repair_inputs": [
                    "reference_intent_dimension_plan_006",
                    "reference_intent_dimension_contract_006",
                    "lb26001_006_ui_defect_buckets_v4_4",
                ],
                "implementation_guard_keys": ["generator.ui_defect_bucket_constraints"],
                "post_rerun_required_evidence": [
                    "fresh_run_manifest",
                    "application_drawing_review_ui_screenshot",
                    "manual_visual_judgement",
                ],
                "ui_review_pass_condition": "fixture pass condition",
                "api_or_displaydim_metric_alone_can_close": False,
            }
            if key == "callout_missing":
                item["post_rerun_required_evidence"].append("reference_callout_checklist")
                if not omit_ui_defect_callout_closure_keys:
                    item["required_callout_keys"] = ["thread_callout_m4_6h", "surface_finish_rest_3_2"]
                    item["absence_check_keys"] = ["radius_callout", "chamfer_callout"]
            bucket_closure_contract.append(item)
        ui_defect_buckets.write_text(
            json.dumps(
                {
                    "base": "LB26001-A-04-006",
                    "status": "blocked_by_solidworks_readiness",
                    "pass": False,
                    "api_only_acceptance_allowed": False,
                    "application_ui_screenshot_is_final_gate": True,
                    "expansion_allowed_now": False,
                    "active_buckets": required_active_buckets,
                    "required_bucket_keys": required_active_buckets + ["callout_missing"],
                    "missing_bucket_keys": [],
                    "required_next_screenshot_check_buckets": required_next_buckets,
                    "next_screenshot_checklist": next_screenshot_checklist,
                    "reference_callout_review_required_keys": ["thread_callout_m4_6h", "surface_finish_rest_3_2"],
                    "reference_callout_absence_check_keys": ["radius_callout", "chamfer_callout"],
                    "screenshot_visual_observations": screenshot_visual_observations,
                    "bucket_closure_contract": bucket_closure_contract,
                    "missing_bucket_closure_contract_keys": [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        readiness = {
            "status": "ready" if readiness_ready else "blocked",
            "ready_to_start_locked_006_cad": readiness_ready,
            "blocking_issue_keys": [] if readiness_ready else ["solidworks_not_responding"],
        }
        packet = build_rerun_packet(
            readiness=readiness,
            requested_status=_requested_status(
                generated_png_source_pass=generated_png_source_pass,
                include_failed_items=include_failed_items,
            ),
            correction_plan=_correction_plan(
                generated_png_source_pass=generated_png_source_pass,
                stale_manual_review=stale_correction_plan,
                screenshot_content_pass=not stale_screenshot_content_status,
            ),
            reference_intent_plan_path=plan,
            reference_intent_contract_path=contract,
            ui_defect_buckets_path=ui_defect_buckets,
            cad_worker_source_path=cad_worker_source,
            correction_plan_source_path=correction_plan_source,
            generator_source_path=generator_source,
            reference_compare_source_path=reference_compare_source,
            vision_qc_v6_source_path=vision_qc_v6_source,
            application_ui_screenshot_validator_source_path=application_ui_screenshot_validator_source,
            dimension_arrange_source_path=dimension_arrange_source,
            dimension_visual_validator_source_path=dimension_visual_source,
            lifecycle_audit_source_path=lifecycle_audit_source,
            staged_validation_source_path=staged_validation_source,
            real_cad_smoke_source_path=real_cad_smoke_source,
            drawing_visual_review_suite_source_path=drawing_visual_review_source,
            manual_visual_judgement_template_source_path=manual_visual_judgement_template_source,
            apply_ui_review_source_path=apply_ui_review_source,
            acceptance_gate_source_path=acceptance_gate_source,
            acceptance_proof_source_path=acceptance_proof_source,
        )
        markdown = render_markdown(packet)
    return {"packet": packet, "markdown": markdown}


def test_006_rerun_packet_blocks_real_cad_when_solidworks_readiness_is_blocked() -> None:
    result = _build_packet_fixture(readiness_ready=False)
    packet = result["packet"]

    assert packet["schema"] == "sw_drawing_studio.lb26001_006_rerun_packet.v4_2"
    assert packet["status"] == "blocked_by_solidworks_readiness"
    assert packet["packet_build_ready"] is True
    assert packet["real_cad_allowed_now"] is False
    assert packet["readiness_blocking_issue_keys"] == ["solidworks_not_responding"]
    assert packet["application_ui_screenshot_is_final_gate"] is True
    assert packet["api_only_acceptance_allowed"] is False
    assert packet["ui_screenshot_validation_policy"]["per_drawing_application_ui_screenshot_required"] is True
    assert packet["ui_screenshot_validation_policy"]["api_only_acceptance_allowed"] is False
    assert packet["current_006_ui_verdict"]["status"] == "manual_visual_checklist_failed"
    assert "display_dimensions" in packet["current_006_ui_verdict"]["failed_visual_checklist_items"]
    assert packet["current_006_ui_verdict"]["comparison_image"] == (
        "LB26001-A-04-006_reference_vs_generated.png"
    )
    assert packet["current_006_ui_verdict"]["latest_manual_findings"] == [
        "Generated drawing still fails the application UI screenshot comparison."
    ]
    assert packet["current_006_ui_verdict"]["latest_manual_visual_checklist"]["reference_match"] is False
    assert packet["current_006_ui_verdict"]["application_ui_screenshot_paths_existing_application_ui"] == [
        "LB26001-A-04-006_ui.png"
    ]
    assert "LB26001-A-04-006_reference_vs_generated.png" in result["markdown"]
    assert packet["source_signatures"]["generator"]["pass"] is True
    assert packet["source_signatures"]["cad_job_worker"]["pass"] is True
    assert packet["source_signatures"]["reference_compare_v4"]["pass"] is True
    assert packet["source_signatures"]["vision_qc_v6"]["pass"] is True
    assert packet["source_signatures"]["application_ui_screenshot_validator"]["pass"] is True
    assert packet["source_signatures"]["dimension_visual_validator"]["pass"] is True
    assert packet["source_signatures"]["displaydim_lifecycle_audit"]["pass"] is True
    assert packet["source_signatures"]["staged_cad_validation_v3"]["pass"] is True
    assert packet["source_signatures"]["real_cad_smoke_v3"]["pass"] is True
    assert packet["source_signatures"]["drawing_visual_review_suite"]["pass"] is True
    assert packet["source_signatures"]["manual_visual_judgement_template_v4"]["pass"] is True
    assert packet["source_signatures"]["lb26001_correction_plan_v4_2"]["pass"] is True
    assert packet["source_signatures"]["apply_ui_visual_review_v4"]["pass"] is True
    assert packet["source_signatures"]["lb26001_acceptance_gate_v4_2"]["pass"] is True
    assert packet["source_signatures"]["lb26001_006_acceptance_proof_v4_2"]["pass"] is True
    assert packet["reference_intent_artifacts"]["plan"]["pass"] is True
    assert packet["reference_intent_artifacts"]["contract"]["pass"] is True
    assert packet["ui_defect_buckets"]["pass"] is True
    assert "dimension_visual_overdense" in packet["ui_defect_buckets"]["active_buckets"]
    assert "callout_missing" in packet["ui_defect_buckets"]["required_next_screenshot_check_buckets"]
    assert packet["ui_defect_buckets"]["callout_next_check_ok"] is True
    assert "dimension_lane_wrong" in packet["ui_defect_buckets"]["bucket_closure_contract_buckets"]
    assert packet["ui_defect_buckets"]["missing_bucket_closure_contract_keys"] == []
    assert packet["ui_defect_buckets"]["incomplete_bucket_closure_contracts"] == {}
    assert packet["ui_defect_buckets"]["callout_closure_contract_ok"] is True
    assert packet["ui_defect_buckets"]["missing_active_screenshot_visual_observation_buckets"] == []
    assert packet["ui_defect_buckets"]["callout_screenshot_visual_observation_ok"] is True
    assert packet["expansion_policy"]["006_must_pass_first"] is True
    assert "LB26001-A-04-006" in result["markdown"]
    assert "Do not run real CAD" in result["markdown"]


def test_006_rerun_packet_allows_one_locked_rerun_when_offline_and_readiness_pass() -> None:
    packet = _build_packet_fixture(readiness_ready=True)["packet"]

    assert packet["status"] == "ready_for_locked_006_rerun"
    assert packet["packet_build_ready"] is True
    assert packet["readiness_ready"] is True
    assert packet["real_cad_allowed_now"] is True
    gate_names = [item["gate"] for item in packet["ordered_next_gates"]]
    assert gate_names[0] == "no_com_readiness_audit"
    assert gate_names.index("dimension_validation") < gate_names.index("displaydim_lifecycle_audit")
    assert gate_names.index("displaydim_lifecycle_audit") < gate_names.index("reference_compare_v3")
    assert gate_names.index("reference_compare_v3") < gate_names.index("reference_style")
    assert gate_names.index("reference_style") < gate_names.index("strict_reference_compare_v4")
    assert gate_names.index("displaydim_lifecycle_audit") < gate_names.index("strict_reference_compare_v4")
    assert gate_names.index("strict_reference_compare_v4") < gate_names.index("vision_qc_v6")
    assert gate_names.index("vision_qc_v6") < gate_names.index("drawing_review_application_ui_screenshot")
    assert "drawing_review_application_ui_screenshot" in gate_names
    assert "manual_visual_judgement" in gate_names
    assert "with_ui_closure" in gate_names
    lifecycle_gate = next(item for item in packet["ordered_next_gates"] if item["gate"] == "displaydim_lifecycle_audit")
    assert "lb26001_006_displaydim_lifecycle_audit_v4_2.py" in lifecycle_gate["command"]
    assert "post-layout" in lifecycle_gate["acceptance"]
    style_gate = next(item for item in packet["ordered_next_gates"] if item["gate"] == "reference_style")
    assert "reference_style_profile_v3.py" in style_gate["command"]
    vision_gate = next(item for item in packet["ordered_next_gates"] if item["gate"] == "vision_qc_v6")
    assert "vision_qc_v6" in vision_gate["acceptance"]


def test_006_rerun_packet_does_not_require_future_fresh_png_before_rerun() -> None:
    packet = _build_packet_fixture(
        readiness_ready=True,
        generated_png_source_pass=False,
    )["packet"]

    assert packet["status"] == "ready_for_locked_006_rerun"
    assert packet["packet_build_ready"] is True
    assert packet["real_cad_allowed_now"] is True
    assert "006_fresh_generated_png_source_evidence" not in packet["offline_prerequisite_missing_keys"]
    post_requirements = {item["key"]: item for item in packet["post_rerun_acceptance_requirements"]}
    assert post_requirements["fresh_generated_png_source_evidence"]["required"] is True
    assert post_requirements["fresh_generated_png_source_evidence"]["current_pass"] is False
    assert post_requirements["displaydim_lifecycle_audit_pass"]["required"] is True
    assert post_requirements["displaydim_lifecycle_audit_pass"]["current_pass"] is False
    assert post_requirements["displaydim_lifecycle_audit_pass"]["evidence"]["slot_rebind_summary_required"] is True
    assert post_requirements["reference_compare_v3_pass"]["required"] is True
    assert post_requirements["reference_style_pass"]["required"] is True
    assert post_requirements["vision_qc_v6_pass"]["required"] is True


def test_006_rerun_packet_uses_correction_plan_effective_checks_when_status_failed_items_empty() -> None:
    packet = _build_packet_fixture(
        readiness_ready=False,
        include_failed_items=False,
    )["packet"]

    verdict = packet["current_006_ui_verdict"]
    assert verdict["correction_plan_direct_ui_findings_used_for_correction"] is True
    assert "display_dimensions" in verdict["failed_visual_checklist_items"]
    assert "title_block" in verdict["failed_visual_checklist_items"]
    assert verdict["correction_actions"][0]["source_type"] == "direct_ui_screenshot_finding"
    post_requirements = {item["key"]: item for item in packet["post_rerun_acceptance_requirements"]}
    manual_requirement = post_requirements["application_ui_screenshot_manual_visual_pass"]
    assert "display_dimensions" in manual_requirement["evidence"]["failed_items"]
    assert manual_requirement["evidence"]["comparison_image"] == (
        "LB26001-A-04-006_reference_vs_generated.png"
    )
    assert manual_requirement["evidence"]["latest_manual_findings"] == [
        "Generated drawing still fails the application UI screenshot comparison."
    ]
    assert manual_requirement["evidence"]["correction_actions"][1]["check"] == "display_dimensions"


def test_006_rerun_packet_blocks_stale_correction_plan_ui_status() -> None:
    packet = _build_packet_fixture(
        readiness_ready=True,
        stale_correction_plan=True,
    )["packet"]

    assert packet["status"] == "offline_prerequisites_missing"
    assert packet["packet_build_ready"] is False
    assert packet["real_cad_allowed_now"] is False
    assert "correction_plan_matches_current_006_status" in packet["offline_prerequisite_missing_keys"]
    prerequisite = {
        item["key"]: item for item in packet["offline_prerequisites"]
    }["correction_plan_matches_current_006_status"]
    assert prerequisite["evidence"]["requested_latest_manual_review"] == "LB26001-A-04-006_manual.json"
    assert prerequisite["evidence"]["correction_latest_manual_review"] == "stale_manual.json"


def test_006_rerun_packet_blocks_stale_correction_plan_screenshot_content_status() -> None:
    packet = _build_packet_fixture(
        readiness_ready=True,
        stale_screenshot_content_status=True,
    )["packet"]

    assert packet["status"] == "offline_prerequisites_missing"
    assert packet["packet_build_ready"] is False
    assert packet["real_cad_allowed_now"] is False
    assert "correction_plan_matches_current_006_status" in packet["offline_prerequisite_missing_keys"]
    prerequisite = {
        item["key"]: item for item in packet["offline_prerequisites"]
    }["correction_plan_matches_current_006_status"]
    assert prerequisite["evidence"]["requested_ui_screenshot_content_check_pass"] is True
    assert prerequisite["evidence"]["correction_ui_screenshot_content_check_pass"] is False


def test_006_rerun_packet_blocks_when_correction_plan_source_signature_missing() -> None:
    packet = _build_packet_fixture(
        readiness_ready=True,
        omit_correction_plan_signature="direct_ui_findings_inferred_checks",
    )["packet"]

    assert packet["status"] == "offline_prerequisites_missing"
    assert packet["packet_build_ready"] is False
    assert packet["real_cad_allowed_now"] is False
    assert "correction_plan_source_signatures_present" in packet["offline_prerequisite_missing_keys"]
    assert packet["source_signatures"]["lb26001_correction_plan_v4_2"]["missing_signatures"] == [
        "direct_ui_findings_inferred_checks"
    ]


def test_006_rerun_packet_blocks_when_cad_worker_ui_evidence_signature_missing() -> None:
    packet = _build_packet_fixture(
        readiness_ready=True,
        omit_cad_worker_signature="ui_correction_evidence_generator_env",
    )["packet"]

    assert packet["status"] == "offline_prerequisites_missing"
    assert packet["packet_build_ready"] is False
    assert packet["real_cad_allowed_now"] is False
    assert "cad_worker_ui_correction_evidence_signatures_present" in packet["offline_prerequisite_missing_keys"]
    assert packet["source_signatures"]["cad_job_worker"]["missing_signatures"] == [
        "ui_correction_evidence_generator_env"
    ]


def test_006_rerun_packet_blocks_when_source_repair_signature_is_missing() -> None:
    packet = _build_packet_fixture(
        readiness_ready=True,
        omit_generator_signature="created_but_uncovered_detection",
    )["packet"]

    assert packet["status"] == "offline_prerequisites_missing"
    assert packet["packet_build_ready"] is False
    assert packet["real_cad_allowed_now"] is False
    assert "generator_repair_signatures_present" in packet["offline_prerequisite_missing_keys"]
    assert packet["source_signatures"]["generator"]["missing_signatures"] == [
        "created_but_uncovered_detection"
    ]


def test_006_rerun_packet_blocks_when_generator_sidecar_signature_is_missing() -> None:
    packet = _build_packet_fixture(
        readiness_ready=True,
        omit_generator_signature="sidecar_diagnostic_only_warning",
    )["packet"]

    assert packet["status"] == "offline_prerequisites_missing"
    assert packet["packet_build_ready"] is False
    assert packet["real_cad_allowed_now"] is False
    assert "generator_repair_signatures_present" in packet["offline_prerequisite_missing_keys"]
    assert packet["source_signatures"]["generator"]["missing_signatures"] == [
        "sidecar_diagnostic_only_warning"
    ]


def test_006_rerun_packet_blocks_when_generator_slot_summary_signature_is_missing() -> None:
    packet = _build_packet_fixture(
        readiness_ready=True,
        omit_generator_signature="post_layout_slot_rebind_summary",
    )["packet"]

    assert packet["status"] == "offline_prerequisites_missing"
    assert packet["packet_build_ready"] is False
    assert packet["real_cad_allowed_now"] is False
    assert "generator_repair_signatures_present" in packet["offline_prerequisite_missing_keys"]
    assert packet["source_signatures"]["generator"]["missing_signatures"] == [
        "post_layout_slot_rebind_summary"
    ]


def test_006_rerun_packet_blocks_when_generator_getviews_refresh_signature_is_missing() -> None:
    packet = _build_packet_fixture(
        readiness_ready=True,
        omit_generator_signature="post_layout_reopen_getviews_refresh",
    )["packet"]

    assert packet["status"] == "offline_prerequisites_missing"
    assert packet["packet_build_ready"] is False
    assert packet["real_cad_allowed_now"] is False
    assert "generator_repair_signatures_present" in packet["offline_prerequisite_missing_keys"]
    assert packet["source_signatures"]["generator"]["missing_signatures"] == [
        "post_layout_reopen_getviews_refresh"
    ]


def test_006_rerun_packet_blocks_when_generator_getviews_refresh_diagnostic_is_missing() -> None:
    packet = _build_packet_fixture(
        readiness_ready=True,
        omit_generator_signature="post_layout_refresh_actions_recorded",
    )["packet"]

    assert packet["status"] == "offline_prerequisites_missing"
    assert packet["packet_build_ready"] is False
    assert packet["real_cad_allowed_now"] is False
    assert "generator_repair_signatures_present" in packet["offline_prerequisite_missing_keys"]
    assert packet["source_signatures"]["generator"]["missing_signatures"] == [
        "post_layout_refresh_actions_recorded"
    ]


def test_006_rerun_packet_blocks_when_generator_post_layout_prune_guard_is_missing() -> None:
    packet = _build_packet_fixture(
        readiness_ready=True,
        omit_generator_signature="post_layout_prune_guard_explicit_repair",
    )["packet"]

    assert packet["status"] == "offline_prerequisites_missing"
    assert packet["packet_build_ready"] is False
    assert packet["real_cad_allowed_now"] is False
    assert "generator_repair_signatures_present" in packet["offline_prerequisite_missing_keys"]
    assert packet["source_signatures"]["generator"]["missing_signatures"] == [
        "post_layout_prune_guard_explicit_repair"
    ]


def test_006_rerun_packet_blocks_when_generator_prune_guard_arrange_guard_is_missing() -> None:
    packet = _build_packet_fixture(
        readiness_ready=True,
        omit_generator_signature="post_layout_prune_guard_arrange_guard_repair",
    )["packet"]

    assert packet["status"] == "offline_prerequisites_missing"
    assert packet["packet_build_ready"] is False
    assert packet["real_cad_allowed_now"] is False
    assert "generator_repair_signatures_present" in packet["offline_prerequisite_missing_keys"]
    assert packet["source_signatures"]["generator"]["missing_signatures"] == [
        "post_layout_prune_guard_arrange_guard_repair"
    ]


def test_006_rerun_packet_blocks_when_generator_final_exact_prune_failure_guard_is_missing() -> None:
    packet = _build_packet_fixture(
        readiness_ready=True,
        omit_generator_signature="post_layout_final_exact_prune_failed",
    )["packet"]

    assert packet["status"] == "offline_prerequisites_missing"
    assert packet["packet_build_ready"] is False
    assert packet["real_cad_allowed_now"] is False
    assert "generator_repair_signatures_present" in packet["offline_prerequisite_missing_keys"]
    assert packet["source_signatures"]["generator"]["missing_signatures"] == [
        "post_layout_final_exact_prune_failed"
    ]


def test_006_rerun_packet_blocks_when_generator_displaydim_dedupe_is_missing() -> None:
    packet = _build_packet_fixture(
        readiness_ready=True,
        omit_generator_signature="physical_displaydim_dedupe",
    )["packet"]

    assert packet["status"] == "offline_prerequisites_missing"
    assert packet["packet_build_ready"] is False
    assert packet["real_cad_allowed_now"] is False
    assert "generator_repair_signatures_present" in packet["offline_prerequisite_missing_keys"]
    assert packet["source_signatures"]["generator"]["missing_signatures"] == [
        "physical_displaydim_dedupe"
    ]


def test_006_rerun_packet_blocks_when_generator_ui_defect_bucket_constraints_missing() -> None:
    packet = _build_packet_fixture(
        readiness_ready=True,
        omit_generator_signature="ui_defect_bucket_constraints",
    )["packet"]

    assert packet["status"] == "offline_prerequisites_missing"
    assert packet["packet_build_ready"] is False
    assert packet["real_cad_allowed_now"] is False
    assert "generator_repair_signatures_present" in packet["offline_prerequisite_missing_keys"]
    assert packet["source_signatures"]["generator"]["missing_signatures"] == [
        "ui_defect_bucket_constraints"
    ]


def test_006_rerun_packet_blocks_when_generator_strict_target_match_missing() -> None:
    packet = _build_packet_fixture(
        readiness_ready=True,
        omit_generator_signature="ui_defect_strict_target_match",
    )["packet"]

    assert packet["status"] == "offline_prerequisites_missing"
    assert packet["packet_build_ready"] is False
    assert packet["real_cad_allowed_now"] is False
    assert "generator_repair_signatures_present" in packet["offline_prerequisite_missing_keys"]
    assert packet["source_signatures"]["generator"]["missing_signatures"] == [
        "ui_defect_strict_target_match"
    ]


def test_006_rerun_packet_blocks_when_generator_reference_callout_review_plan_missing() -> None:
    packet = _build_packet_fixture(
        readiness_ready=True,
        omit_generator_signature="reference_callout_required_keys",
    )["packet"]

    assert packet["status"] == "offline_prerequisites_missing"
    assert packet["packet_build_ready"] is False
    assert packet["real_cad_allowed_now"] is False
    assert "generator_repair_signatures_present" in packet["offline_prerequisite_missing_keys"]
    assert packet["source_signatures"]["generator"]["missing_signatures"] == [
        "reference_callout_required_keys"
    ]


def test_006_rerun_packet_blocks_when_generator_bucket_closure_contract_missing() -> None:
    packet = _build_packet_fixture(
        readiness_ready=True,
        omit_generator_signature="ui_defect_bucket_closure_contract",
    )["packet"]

    assert packet["status"] == "offline_prerequisites_missing"
    assert packet["packet_build_ready"] is False
    assert packet["real_cad_allowed_now"] is False
    assert "generator_repair_signatures_present" in packet["offline_prerequisite_missing_keys"]
    assert packet["source_signatures"]["generator"]["missing_signatures"] == [
        "ui_defect_bucket_closure_contract"
    ]


def test_006_rerun_packet_blocks_when_generator_delete_equivalence_dedupe_missing() -> None:
    packet = _build_packet_fixture(
        readiness_ready=True,
        omit_generator_signature="reference_intent_delete_equivalence_dedupe",
    )["packet"]

    assert packet["status"] == "offline_prerequisites_missing"
    assert packet["packet_build_ready"] is False
    assert packet["real_cad_allowed_now"] is False
    assert "generator_repair_signatures_present" in packet["offline_prerequisite_missing_keys"]
    assert packet["source_signatures"]["generator"]["missing_signatures"] == [
        "reference_intent_delete_equivalence_dedupe"
    ]


def test_006_rerun_packet_blocks_when_reference_lane_geometry_guard_missing() -> None:
    packet = _build_packet_fixture(
        readiness_ready=True,
        omit_dimension_arrange_signature="reference_lane_geometry_issue_count",
    )["packet"]

    assert packet["status"] == "offline_prerequisites_missing"
    assert packet["packet_build_ready"] is False
    assert packet["real_cad_allowed_now"] is False
    assert "dimension_arrange_reference_lane_signatures_present" in packet["offline_prerequisite_missing_keys"]
    assert packet["source_signatures"]["dimension_arrange_service"]["missing_signatures"] == [
        "reference_lane_geometry_issue_count"
    ]


def test_006_rerun_packet_blocks_when_ui_defect_callout_next_check_missing() -> None:
    packet = _build_packet_fixture(
        readiness_ready=True,
        omit_ui_defect_callout_next_check=True,
    )["packet"]

    assert packet["status"] == "offline_prerequisites_missing"
    assert packet["packet_build_ready"] is False
    assert packet["real_cad_allowed_now"] is False
    assert "006_ui_defect_buckets_ready" in packet["offline_prerequisite_missing_keys"]
    assert packet["ui_defect_buckets"]["missing_next_screenshot_check_buckets"] == ["callout_missing"]
    assert packet["ui_defect_buckets"]["missing_next_screenshot_checklist_buckets"] == ["callout_missing"]
    assert packet["ui_defect_buckets"]["callout_next_check_ok"] is False


def test_006_rerun_packet_blocks_when_ui_defect_bucket_closure_contract_missing() -> None:
    packet = _build_packet_fixture(
        readiness_ready=True,
        omit_ui_defect_closure_contract_bucket="dimension_lane_wrong",
    )["packet"]

    assert packet["status"] == "offline_prerequisites_missing"
    assert packet["packet_build_ready"] is False
    assert packet["real_cad_allowed_now"] is False
    assert "006_ui_defect_buckets_ready" in packet["offline_prerequisite_missing_keys"]
    assert packet["ui_defect_buckets"]["missing_bucket_closure_contract_keys"] == ["dimension_lane_wrong"]


def test_006_rerun_packet_blocks_when_ui_defect_callout_closure_contract_incomplete() -> None:
    packet = _build_packet_fixture(
        readiness_ready=True,
        omit_ui_defect_callout_closure_keys=True,
    )["packet"]

    assert packet["status"] == "offline_prerequisites_missing"
    assert packet["packet_build_ready"] is False
    assert packet["real_cad_allowed_now"] is False
    assert "006_ui_defect_buckets_ready" in packet["offline_prerequisite_missing_keys"]
    assert packet["ui_defect_buckets"]["callout_closure_contract_ok"] is False
    assert packet["ui_defect_buckets"]["incomplete_bucket_closure_contracts"]["callout_missing"] == [
        "required_callout_keys",
        "absence_check_keys",
    ]


def test_006_rerun_packet_blocks_when_active_ui_defect_screenshot_observation_missing() -> None:
    packet = _build_packet_fixture(
        readiness_ready=True,
        omit_ui_defect_screenshot_observation_bucket="dimension_visual_overdense",
    )["packet"]

    assert packet["status"] == "offline_prerequisites_missing"
    assert packet["packet_build_ready"] is False
    assert packet["real_cad_allowed_now"] is False
    assert "006_ui_defect_buckets_ready" in packet["offline_prerequisite_missing_keys"]
    assert packet["ui_defect_buckets"]["missing_active_screenshot_visual_observation_buckets"] == [
        "dimension_visual_overdense"
    ]


def test_006_rerun_packet_blocks_when_cad_worker_ui_defect_env_missing() -> None:
    packet = _build_packet_fixture(
        readiness_ready=True,
        omit_cad_worker_signature="ui_defect_bucket_generator_env",
    )["packet"]

    assert packet["status"] == "offline_prerequisites_missing"
    assert packet["packet_build_ready"] is False
    assert packet["real_cad_allowed_now"] is False
    assert "cad_worker_ui_correction_evidence_signatures_present" in packet["offline_prerequisite_missing_keys"]
    assert packet["source_signatures"]["cad_job_worker"]["missing_signatures"] == [
        "ui_defect_bucket_generator_env"
    ]


def test_006_rerun_packet_blocks_when_reference_outline_scale_hint_is_missing() -> None:
    packet = _build_packet_fixture(
        readiness_ready=True,
        omit_generator_signature="reference_outline_scale_hint",
    )["packet"]

    assert packet["status"] == "offline_prerequisites_missing"
    assert packet["packet_build_ready"] is False
    assert packet["real_cad_allowed_now"] is False
    assert "generator_repair_signatures_present" in packet["offline_prerequisite_missing_keys"]
    assert packet["source_signatures"]["generator"]["missing_signatures"] == [
        "reference_outline_scale_hint"
    ]


def test_006_rerun_packet_blocks_when_exact_target_cap_signature_is_missing() -> None:
    packet = _build_packet_fixture(
        readiness_ready=True,
        omit_generator_signature="reference_intent_exact_target_cap",
    )["packet"]

    assert packet["status"] == "offline_prerequisites_missing"
    assert packet["packet_build_ready"] is False
    assert packet["real_cad_allowed_now"] is False
    assert "generator_repair_signatures_present" in packet["offline_prerequisite_missing_keys"]
    assert packet["source_signatures"]["generator"]["missing_signatures"] == [
        "reference_intent_exact_target_cap"
    ]


def test_006_rerun_packet_blocks_when_generator_live_view_recovery_blocker_is_missing() -> None:
    packet = _build_packet_fixture(
        readiness_ready=True,
        omit_generator_signature="post_layout_live_view_recovery_blocker",
    )["packet"]

    assert packet["status"] == "offline_prerequisites_missing"
    assert packet["packet_build_ready"] is False
    assert packet["real_cad_allowed_now"] is False
    assert "generator_repair_signatures_present" in packet["offline_prerequisite_missing_keys"]
    assert packet["source_signatures"]["generator"]["missing_signatures"] == [
        "post_layout_live_view_recovery_blocker"
    ]


def test_006_rerun_packet_blocks_when_generator_view_materialization_fallback_is_missing() -> None:
    packet = _build_packet_fixture(
        readiness_ready=True,
        omit_generator_signature="post_layout_view_materialization_fallback",
    )["packet"]

    assert packet["status"] == "offline_prerequisites_missing"
    assert packet["packet_build_ready"] is False
    assert packet["real_cad_allowed_now"] is False
    assert "generator_repair_signatures_present" in packet["offline_prerequisite_missing_keys"]
    assert packet["source_signatures"]["generator"]["missing_signatures"] == [
        "post_layout_view_materialization_fallback"
    ]


def test_006_rerun_packet_blocks_when_generator_before_rebind_materialization_is_missing() -> None:
    packet = _build_packet_fixture(
        readiness_ready=True,
        omit_generator_signature="post_layout_view_materialization_before_rebind",
    )["packet"]

    assert packet["status"] == "offline_prerequisites_missing"
    assert packet["packet_build_ready"] is False
    assert packet["real_cad_allowed_now"] is False
    assert "generator_repair_signatures_present" in packet["offline_prerequisite_missing_keys"]
    assert packet["source_signatures"]["generator"]["missing_signatures"] == [
        "post_layout_view_materialization_before_rebind"
    ]


def test_006_rerun_packet_blocks_when_lifecycle_rebind_audit_signature_missing() -> None:
    packet = _build_packet_fixture(
        readiness_ready=True,
        omit_lifecycle_audit_signature="post_layout_direct_accept_rebind_audited",
    )["packet"]

    assert packet["status"] == "offline_prerequisites_missing"
    assert packet["packet_build_ready"] is False
    assert packet["real_cad_allowed_now"] is False
    assert "displaydim_lifecycle_audit_ready" in packet["offline_prerequisite_missing_keys"]
    assert packet["source_signatures"]["displaydim_lifecycle_audit"]["missing_signatures"] == [
        "post_layout_direct_accept_rebind_audited"
    ]


def test_006_rerun_packet_blocks_when_lifecycle_sidecar_audit_signature_missing() -> None:
    packet = _build_packet_fixture(
        readiness_ready=True,
        omit_lifecycle_audit_signature="strict_sidecar_ran_blocker",
    )["packet"]

    assert packet["status"] == "offline_prerequisites_missing"
    assert packet["packet_build_ready"] is False
    assert packet["real_cad_allowed_now"] is False
    assert "displaydim_lifecycle_audit_ready" in packet["offline_prerequisite_missing_keys"]
    assert packet["source_signatures"]["displaydim_lifecycle_audit"]["missing_signatures"] == [
        "strict_sidecar_ran_blocker"
    ]


def test_006_rerun_packet_blocks_when_lifecycle_slot_summary_signature_missing() -> None:
    packet = _build_packet_fixture(
        readiness_ready=True,
        omit_lifecycle_audit_signature="post_layout_slot_rebind_summary_missing",
    )["packet"]

    assert packet["status"] == "offline_prerequisites_missing"
    assert packet["packet_build_ready"] is False
    assert packet["real_cad_allowed_now"] is False
    assert "displaydim_lifecycle_audit_ready" in packet["offline_prerequisite_missing_keys"]
    assert packet["source_signatures"]["displaydim_lifecycle_audit"]["missing_signatures"] == [
        "post_layout_slot_rebind_summary_missing"
    ]


def test_006_rerun_packet_blocks_when_lifecycle_live_view_blocker_signature_missing() -> None:
    packet = _build_packet_fixture(
        readiness_ready=True,
        omit_lifecycle_audit_signature="post_layout_live_view_recovery_failed",
    )["packet"]

    assert packet["status"] == "offline_prerequisites_missing"
    assert packet["packet_build_ready"] is False
    assert packet["real_cad_allowed_now"] is False
    assert "displaydim_lifecycle_audit_ready" in packet["offline_prerequisite_missing_keys"]
    assert packet["source_signatures"]["displaydim_lifecycle_audit"]["missing_signatures"] == [
        "post_layout_live_view_recovery_failed"
    ]


def test_006_rerun_packet_blocks_when_staged_ui_lifecycle_gate_signature_missing() -> None:
    packet = _build_packet_fixture(
        readiness_ready=True,
        omit_staged_validation_signature="vision_qc_requires_visual_acceptance",
    )["packet"]

    assert packet["status"] == "offline_prerequisites_missing"
    assert packet["packet_build_ready"] is False
    assert packet["real_cad_allowed_now"] is False
    assert "staged_validation_lifecycle_ui_gate_signatures_present" in packet["offline_prerequisite_missing_keys"]
    assert packet["source_signatures"]["staged_cad_validation_v3"]["missing_signatures"] == [
        "vision_qc_requires_visual_acceptance"
    ]


def test_006_rerun_packet_blocks_when_real_cad_smoke_packet_env_signature_missing() -> None:
    packet = _build_packet_fixture(
        readiness_ready=True,
        omit_real_cad_smoke_signature="packet_env_key",
    )["packet"]

    assert packet["status"] == "offline_prerequisites_missing"
    assert packet["packet_build_ready"] is False
    assert packet["real_cad_allowed_now"] is False
    assert "real_cad_smoke_packet_env_signatures_present" in packet["offline_prerequisite_missing_keys"]
    assert packet["source_signatures"]["real_cad_smoke_v3"]["missing_signatures"] == [
        "packet_env_key"
    ]


def test_006_rerun_packet_blocks_when_drawing_visual_review_source_signature_missing() -> None:
    packet = _build_packet_fixture(
        readiness_ready=True,
        omit_drawing_visual_review_signature="fresh_generated_png_strict_source",
    )["packet"]

    assert packet["status"] == "offline_prerequisites_missing"
    assert packet["packet_build_ready"] is False
    assert packet["real_cad_allowed_now"] is False
    assert "drawing_visual_review_suite_source_signatures_present" in packet["offline_prerequisite_missing_keys"]
    assert packet["source_signatures"]["drawing_visual_review_suite"]["missing_signatures"] == [
        "fresh_generated_png_strict_source"
    ]


def test_006_rerun_packet_blocks_when_manual_visual_judgement_template_signature_missing() -> None:
    packet = _build_packet_fixture(
        readiness_ready=True,
        omit_manual_visual_judgement_template_signature="checklist_defaults_to_null",
    )["packet"]

    assert packet["status"] == "offline_prerequisites_missing"
    assert packet["packet_build_ready"] is False
    assert packet["real_cad_allowed_now"] is False
    assert "manual_visual_judgement_template_signatures_present" in packet["offline_prerequisite_missing_keys"]
    assert packet["source_signatures"]["manual_visual_judgement_template_v4"]["missing_signatures"] == [
        "checklist_defaults_to_null"
    ]


def test_006_rerun_packet_blocks_when_v6_template_policy_signature_missing() -> None:
    packet = _build_packet_fixture(
        readiness_ready=True,
        omit_vision_qc_v6_signature="reference_titleblock_artifact_issue",
    )["packet"]

    assert packet["status"] == "offline_prerequisites_missing"
    assert packet["packet_build_ready"] is False
    assert packet["real_cad_allowed_now"] is False
    assert "vision_qc_v6_ui_template_policy_signatures_present" in packet["offline_prerequisite_missing_keys"]
    assert packet["source_signatures"]["vision_qc_v6"]["missing_signatures"] == [
        "reference_titleblock_artifact_issue"
    ]


def test_006_rerun_packet_blocks_when_v6_reference_grid_signature_missing() -> None:
    packet = _build_packet_fixture(
        readiness_ready=True,
        omit_vision_qc_v6_signature="reference_visual_grid_layout_match",
    )["packet"]

    assert packet["status"] == "offline_prerequisites_missing"
    assert packet["packet_build_ready"] is False
    assert packet["real_cad_allowed_now"] is False
    assert "vision_qc_v6_ui_template_policy_signatures_present" in packet["offline_prerequisite_missing_keys"]
    assert packet["source_signatures"]["vision_qc_v6"]["missing_signatures"] == [
        "reference_visual_grid_layout_match"
    ]


def test_006_rerun_packet_blocks_when_v6_reference_callout_signature_missing() -> None:
    packet = _build_packet_fixture(
        readiness_ready=True,
        omit_vision_qc_v6_signature="reference_callout_issue",
    )["packet"]

    assert packet["status"] == "offline_prerequisites_missing"
    assert packet["packet_build_ready"] is False
    assert packet["real_cad_allowed_now"] is False
    assert "vision_qc_v6_ui_template_policy_signatures_present" in packet["offline_prerequisite_missing_keys"]
    assert packet["source_signatures"]["vision_qc_v6"]["missing_signatures"] == [
        "reference_callout_issue"
    ]


def test_006_rerun_packet_blocks_when_application_ui_screenshot_validator_signature_missing() -> None:
    packet = _build_packet_fixture(
        readiness_ready=True,
        omit_application_ui_screenshot_validator_signature="side_by_side_review_gate",
    )["packet"]

    assert packet["status"] == "offline_prerequisites_missing"
    assert packet["packet_build_ready"] is False
    assert packet["real_cad_allowed_now"] is False
    assert "application_ui_screenshot_validator_signatures_present" in packet["offline_prerequisite_missing_keys"]
    assert packet["source_signatures"]["application_ui_screenshot_validator"]["missing_signatures"] == [
        "side_by_side_review_gate"
    ]


def test_006_rerun_packet_blocks_when_dimension_visual_readability_signature_missing() -> None:
    packet = _build_packet_fixture(
        readiness_ready=True,
        omit_dimension_visual_signature="dimension_cluster_pass_gate",
    )["packet"]

    assert packet["status"] == "offline_prerequisites_missing"
    assert packet["packet_build_ready"] is False
    assert packet["real_cad_allowed_now"] is False
    assert "dimension_visual_readability_signatures_present" in packet["offline_prerequisite_missing_keys"]
    assert packet["source_signatures"]["dimension_visual_validator"]["missing_signatures"] == [
        "dimension_cluster_pass_gate"
    ]


def test_006_rerun_packet_blocks_when_manual_ui_acceptance_signature_is_missing() -> None:
    packet = _build_packet_fixture(
        readiness_ready=True,
        omit_acceptance_gate_signature="manual_visual_checklist_pass_required",
    )["packet"]

    assert packet["status"] == "offline_prerequisites_missing"
    assert packet["packet_build_ready"] is False
    assert packet["real_cad_allowed_now"] is False
    assert "acceptance_gate_manual_ui_signatures_present" in packet["offline_prerequisite_missing_keys"]
    assert packet["source_signatures"]["lb26001_acceptance_gate_v4_2"]["missing_signatures"] == [
        "manual_visual_checklist_pass_required"
    ]


def test_006_rerun_packet_blocks_when_acceptance_gate_lifecycle_signature_is_missing() -> None:
    packet = _build_packet_fixture(
        readiness_ready=True,
        omit_acceptance_gate_signature="displaydim_lifecycle_missing_blocker",
    )["packet"]

    assert packet["status"] == "offline_prerequisites_missing"
    assert packet["packet_build_ready"] is False
    assert packet["real_cad_allowed_now"] is False
    assert "acceptance_gate_manual_ui_signatures_present" in packet["offline_prerequisite_missing_keys"]
    assert packet["source_signatures"]["lb26001_acceptance_gate_v4_2"]["missing_signatures"] == [
        "displaydim_lifecycle_missing_blocker"
    ]


def test_006_rerun_packet_blocks_when_acceptance_proof_supplemental_signature_is_missing() -> None:
    packet = _build_packet_fixture(
        readiness_ready=True,
        omit_acceptance_proof_signature="supplemental_checklist_gate",
    )["packet"]

    assert packet["status"] == "offline_prerequisites_missing"
    assert packet["packet_build_ready"] is False
    assert packet["real_cad_allowed_now"] is False
    assert "006_acceptance_proof_manual_ui_signatures_present" in packet["offline_prerequisite_missing_keys"]
    assert packet["source_signatures"]["lb26001_006_acceptance_proof_v4_2"]["missing_signatures"] == [
        "supplemental_checklist_gate"
    ]


def test_006_rerun_packet_blocks_when_acceptance_proof_lifecycle_signature_is_missing() -> None:
    packet = _build_packet_fixture(
        readiness_ready=True,
        omit_acceptance_proof_signature="displaydim_lifecycle_report_missing_blocker",
    )["packet"]

    assert packet["status"] == "offline_prerequisites_missing"
    assert packet["packet_build_ready"] is False
    assert packet["real_cad_allowed_now"] is False
    assert "006_acceptance_proof_manual_ui_signatures_present" in packet["offline_prerequisite_missing_keys"]
    assert packet["source_signatures"]["lb26001_006_acceptance_proof_v4_2"]["missing_signatures"] == [
        "displaydim_lifecycle_report_missing_blocker"
    ]


if __name__ == "__main__":
    test_006_rerun_packet_blocks_real_cad_when_solidworks_readiness_is_blocked()
    test_006_rerun_packet_allows_one_locked_rerun_when_offline_and_readiness_pass()
    test_006_rerun_packet_does_not_require_future_fresh_png_before_rerun()
    test_006_rerun_packet_uses_correction_plan_effective_checks_when_status_failed_items_empty()
    test_006_rerun_packet_blocks_stale_correction_plan_ui_status()
    test_006_rerun_packet_blocks_stale_correction_plan_screenshot_content_status()
    test_006_rerun_packet_blocks_when_correction_plan_source_signature_missing()
    test_006_rerun_packet_blocks_when_cad_worker_ui_evidence_signature_missing()
    test_006_rerun_packet_blocks_when_source_repair_signature_is_missing()
    test_006_rerun_packet_blocks_when_generator_sidecar_signature_is_missing()
    test_006_rerun_packet_blocks_when_generator_slot_summary_signature_is_missing()
    test_006_rerun_packet_blocks_when_generator_getviews_refresh_signature_is_missing()
    test_006_rerun_packet_blocks_when_generator_getviews_refresh_diagnostic_is_missing()
    test_006_rerun_packet_blocks_when_generator_post_layout_prune_guard_is_missing()
    test_006_rerun_packet_blocks_when_generator_prune_guard_arrange_guard_is_missing()
    test_006_rerun_packet_blocks_when_generator_final_exact_prune_failure_guard_is_missing()
    test_006_rerun_packet_blocks_when_generator_displaydim_dedupe_is_missing()
    test_006_rerun_packet_blocks_when_generator_ui_defect_bucket_constraints_missing()
    test_006_rerun_packet_blocks_when_generator_strict_target_match_missing()
    test_006_rerun_packet_blocks_when_generator_reference_callout_review_plan_missing()
    test_006_rerun_packet_blocks_when_generator_bucket_closure_contract_missing()
    test_006_rerun_packet_blocks_when_generator_delete_equivalence_dedupe_missing()
    test_006_rerun_packet_blocks_when_reference_lane_geometry_guard_missing()
    test_006_rerun_packet_blocks_when_ui_defect_callout_next_check_missing()
    test_006_rerun_packet_blocks_when_ui_defect_bucket_closure_contract_missing()
    test_006_rerun_packet_blocks_when_ui_defect_callout_closure_contract_incomplete()
    test_006_rerun_packet_blocks_when_active_ui_defect_screenshot_observation_missing()
    test_006_rerun_packet_blocks_when_cad_worker_ui_defect_env_missing()
    test_006_rerun_packet_blocks_when_reference_outline_scale_hint_is_missing()
    test_006_rerun_packet_blocks_when_exact_target_cap_signature_is_missing()
    test_006_rerun_packet_blocks_when_generator_live_view_recovery_blocker_is_missing()
    test_006_rerun_packet_blocks_when_generator_view_materialization_fallback_is_missing()
    test_006_rerun_packet_blocks_when_generator_before_rebind_materialization_is_missing()
    test_006_rerun_packet_blocks_when_lifecycle_rebind_audit_signature_missing()
    test_006_rerun_packet_blocks_when_lifecycle_sidecar_audit_signature_missing()
    test_006_rerun_packet_blocks_when_lifecycle_slot_summary_signature_missing()
    test_006_rerun_packet_blocks_when_lifecycle_live_view_blocker_signature_missing()
    test_006_rerun_packet_blocks_when_staged_ui_lifecycle_gate_signature_missing()
    test_006_rerun_packet_blocks_when_real_cad_smoke_packet_env_signature_missing()
    test_006_rerun_packet_blocks_when_drawing_visual_review_source_signature_missing()
    test_006_rerun_packet_blocks_when_manual_visual_judgement_template_signature_missing()
    test_006_rerun_packet_blocks_when_v6_template_policy_signature_missing()
    test_006_rerun_packet_blocks_when_v6_reference_grid_signature_missing()
    test_006_rerun_packet_blocks_when_v6_reference_callout_signature_missing()
    test_006_rerun_packet_blocks_when_application_ui_screenshot_validator_signature_missing()
    test_006_rerun_packet_blocks_when_dimension_visual_readability_signature_missing()
    test_006_rerun_packet_blocks_when_manual_ui_acceptance_signature_is_missing()
    test_006_rerun_packet_blocks_when_acceptance_gate_lifecycle_signature_is_missing()
    test_006_rerun_packet_blocks_when_acceptance_proof_supplemental_signature_is_missing()
    test_006_rerun_packet_blocks_when_acceptance_proof_lifecycle_signature_is_missing()
    print("PASS test_v4_2_lb26001_006_rerun_packet")
