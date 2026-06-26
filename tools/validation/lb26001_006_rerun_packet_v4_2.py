"""Build the no-COM rerun packet for the next LB26001-A-04-006 CAD test.

The packet is a readiness/orchestration artifact, not acceptance evidence. It
binds the current UI screenshot failure, learned correction plan, source-level
repair signatures, and SolidWorks readiness state into one file before any real
CAD worker is allowed to run.
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
REQUIRED_VISUAL_CHECKS = [
    "reference_match",
    "view_layout",
    "display_dimensions",
    "dimension_readability",
    "title_block",
    "manufacturing_notes",
]
REQUIRED_ACTIVE_UI_DEFECT_BUCKETS = {
    "dimension_visual_overdense",
    "dimension_lane_wrong",
    "note_missing_or_wrong",
    "titlebar_incomplete",
    "projection_view_style_mismatch",
}
REQUIRED_UI_DEFECT_BUCKETS = REQUIRED_ACTIVE_UI_DEFECT_BUCKETS | {"callout_missing"}
REQUIRED_CALLOUT_KEYS = {"thread_callout_m4_6h", "hole_callout_4x3_3", "surface_finish_rest_3_2"}
CALLOUT_ABSENCE_CHECK_KEYS = {"radius_callout", "chamfer_callout"}
REQUIRED_CLOSURE_EVIDENCE_KEYS = {
    "fresh_run_manifest",
    "generated_slddrw_pdf_dxf_png",
    "reference_compare_v4",
    "vision_qc_v6",
    "application_drawing_review_ui_screenshot",
    "manual_visual_judgement",
}

DEFAULT_READINESS = REPO_ROOT / "drw_output" / "diagnostics" / "lb26001_006_regression_readiness_v4_2.json"
DEFAULT_REQUESTED_STATUS = REPO_ROOT / "drw_output" / "diagnostics" / "lb26001_requested_drawings_status_v4_2.json"
DEFAULT_CORRECTION_PLAN = REPO_ROOT / "drw_output" / "reference_style_profile" / "lb26001_correction_plan_v4_2.json"
DEFAULT_CORRECTION_PLAN_SOURCE = REPO_ROOT / "tools" / "validation" / "lb26001_correction_plan_v4_2.py"
DEFAULT_REFERENCE_INTENT_PLAN = REPO_ROOT / "drw_output" / "reference_intent_dimension_plan_006.json"
DEFAULT_REFERENCE_INTENT_CONTRACT = REPO_ROOT / "drw_output" / "reference_intent_dimension_contract_006.json"
DEFAULT_UI_DEFECT_BUCKETS = REPO_ROOT / "drw_output" / "diagnostics" / "lb26001_006_ui_defect_buckets_v4_4.json"
DEFAULT_REFERENCE_INTENT_EXECUTOR_SOURCE = REPO_ROOT / "app" / "services" / "reference_intent_dimension_executor.py"
DEFAULT_CAD_WORKER_SOURCE = REPO_ROOT / "app" / "workers" / "cad_job_worker.py"
DEFAULT_PRODUCT_EVIDENCE_GATE_SOURCE = REPO_ROOT / "tools" / "validation" / "product_evidence_gate_v4_4.py"
DEFAULT_GENERATOR_SOURCE = REPO_ROOT / ".trae" / "specs" / "build-v6-and-validate-exe-ui" / "drw_generate_v6.py"
DEFAULT_REFERENCE_COMPARE_SOURCE = REPO_ROOT / "app" / "services" / "reference_compare_v4.py"
DEFAULT_VISION_QC_V6_SOURCE = REPO_ROOT / "app" / "services" / "vision_qc_v6.py"
DEFAULT_APPLICATION_UI_SCREENSHOT_VALIDATOR_SOURCE = REPO_ROOT / "app" / "services" / "application_ui_screenshot_validator.py"
DEFAULT_DIMENSION_VISUAL_VALIDATOR_SOURCE = REPO_ROOT / "app" / "services" / "dimension_visual_validator.py"
DEFAULT_DIMENSION_ARRANGE_SOURCE = REPO_ROOT / "app" / "services" / "dimension_arrange_service.py"
DEFAULT_LIFECYCLE_AUDIT_SOURCE = REPO_ROOT / "tools" / "validation" / "lb26001_006_displaydim_lifecycle_audit_v4_2.py"
DEFAULT_STAGED_VALIDATION_SOURCE = REPO_ROOT / "tools" / "validation" / "staged_cad_validation_v3.py"
DEFAULT_REAL_CAD_SMOKE_SOURCE = REPO_ROOT / "tools" / "validation" / "real_cad_smoke_v3.py"
DEFAULT_DRAWING_VISUAL_REVIEW_SUITE_SOURCE = REPO_ROOT / "tools" / "ui_robot" / "drawing_visual_review_suite.py"
DEFAULT_MANUAL_VISUAL_JUDGEMENT_TEMPLATE_SOURCE = REPO_ROOT / "tools" / "validation" / "manual_visual_judgement_template_v4.py"
DEFAULT_APPLY_UI_REVIEW_SOURCE = REPO_ROOT / "tools" / "validation" / "apply_ui_visual_review_v4.py"
DEFAULT_ACCEPTANCE_GATE_SOURCE = REPO_ROOT / "tools" / "validation" / "lb26001_acceptance_gate_v4_2.py"
DEFAULT_ACCEPTANCE_PROOF_SOURCE = REPO_ROOT / "tools" / "validation" / "lb26001_006_acceptance_proof_v4_2.py"
DEFAULT_OUT_JSON = REPO_ROOT / "drw_output" / "diagnostics" / "lb26001_006_rerun_packet_v4_2.json"
DEFAULT_OUT_MD = REPO_ROOT / "drw_output" / "diagnostics" / "lb26001_006_rerun_packet_v4_2.md"

GENERATOR_SIGNATURES = {
    "post_layout_view_family_rebind": "view_family_heuristic:type7_front",
    "post_layout_projected_view_rebind": "view_family_heuristic:type4_right",
    "coverage_delta_diagnostics": "reference_intent_target_coverage_delta",
    "coverage_based_post_layout_repair": "_reference_intent_post_layout_repair_reason",
    "final_acceptance_blockers": "_reference_intent_final_acceptance_blockers",
    "final_acceptance_over_cap_blocker": "display_dim_over_reference_intent_cap",
    "visible_entity_rank": "_reference_intent_entity_rank",
    "created_but_uncovered_detection": "created_but_target_not_covered",
    "generator_final_blocker_warning": "post_layout_reference_intent_final_blocked",
    "post_layout_persisted_name_rebind": "select_by_persisted_name",
    "post_layout_direct_accept_rebind": "direct_accept_failed_select_by_persisted_name",
    "post_layout_slot_rebind_diagnostics": "slot_rebind_diagnostics",
    "post_layout_slot_rebind_summary": "slot_rebind_summary",
    "post_layout_slot_rebind_unbound_slots": "unbound_slots",
    "post_layout_slot_rebind_nearest_candidates": "nearest_candidates",
    "post_prune_guard_coverage_snapshot": "post_saveas_reopen_prune_guard",
    "post_layout_reference_view_name_candidate_rebind": "reference_view_name_candidate_select",
    "post_layout_live_view_chain_scan_rebind": "live_view_chain_scan",
    "post_layout_live_getviews_scan_rebind": "live_getviews_scan",
    "post_layout_live_created_views_scan_rebind": "live_created_views_scan",
    "post_layout_reopen_getviews_refresh": "reference_intent_created_views_refreshed",
    "post_layout_created_views_refresh_source": "post_layout_reopen_getviews_refresh",
    "post_layout_current_doc_refreshed": "post_layout_current_drawing_doc_refreshed",
    "post_layout_view_materialization_probe": "post_layout_reopen_view_materialization_probe",
    "post_layout_view_materialization_fallback": "post_layout_reopen_view_materialization_fallback_open_options",
    "post_layout_view_materialization_fallback_option_1": '"to_open_options": 1',
    "post_layout_view_materialization_before_rebind": "post_layout_reopen_view_materialization_before_rebind",
    "post_layout_live_view_recovery_blocker": "post_layout_live_view_recovery_failed",
    "post_layout_reopen_force_rebuild_before_rebind": "post_layout_reopen_force_rebuild_wait",
    "post_layout_refresh_actions_recorded": "refresh_actions",
    "post_layout_refresh_record_count_recorded": '"record_count": len(records_)',
    "post_layout_current_doc_view_count": "current_doc_view_count",
    "post_layout_getviews_count": "getviews_count",
    "post_layout_current_sheet_getviews_count": "current_sheet_getviews_count",
    "post_layout_after_prune_coverage": "post_layout_after_prune",
    "post_layout_prune_guard_explicit_repair": "post_layout_prune_guard_explicit_display_dims",
    "post_layout_prune_guard_blocker": "post_layout_prune_guard_still_blocked",
    "post_layout_prune_guard_after_arrange_coverage": "post_layout_prune_guard_after_arrange",
    "post_layout_prune_guard_arrange_guard_repair": "post_layout_prune_guard_arrange_guard_explicit_display_dims",
    "post_layout_prune_guard_after_arrange_blocker": "post_layout_prune_guard_after_arrange_still_blocked",
    "post_layout_final_exact_prune": "post_layout_final_exact_prune",
    "post_layout_final_exact_prune_failed": "post_layout_final_exact_prune_failed",
    "post_layout_final_exact_prune_defer_failed_restore": "post_layout_final_exact_prune_restore_deferred",
    "post_layout_final_exact_prune_repair": '"post_layout_final_exact_prune_repair": _post_layout_final_exact_prune_repair',
    "post_layout_final_exact_prune_repair_blocker": "post_layout_final_exact_prune_repair_still_blocked",
    "post_layout_prune_defer_failed_restore": "restore_on_failed_prune=False",
    "post_layout_prune_repair_handoff": "caller_will_repair_failed_prune",
    "reference_outline_layout_extraction": "_v4_blueprint_layout_outlines",
    "reference_outline_scale_hint": "_reference_outline_scale_hint",
    "persisted_layout_target_outlines": "target_outlines=_layout_outlines_for_solver",
    "persisted_layout_target_tolerance": "target_outline_tolerance=0.28",
    "persisted_layout_start_scale": "start_scale=chosen",
    "persisted_layout_primary_outline_blocking": "target_outline_size_blocking_issues",
    "persisted_layout_iso_outline_warning": "target_outline_size_warning_issues",
    "persisted_layout_scale_direction": "target_outline_scale_direction",
    "drawing_doc_getviews_candidates": "_drawing_doc_getviews_candidates",
    "expected_add_method_trace": "expected_add_method",
    "raw_target_key_trace": '"target_key": target_key',
    "raw_view_slot_trace": '"view_slot": slot',
    "raw_selected_entity_trace": '"selected_entity": entity_identity',
    "raw_before_after_count_trace": '"display_dim_count_before": before_one',
    "raw_target_covered_trace": '"target_covered_after_attempt": target_covered_after_attempt',
    "prune_deleted_item_target_key": '"target_key": target_match.get("target_key", "")',
    "prune_deleted_item_reason": "over_quota_or_low_reference_intent_score",
    "reference_intent_best_target_prune_protection": "reference_intent_best_target_displaydim_protected",
    "reference_intent_exact_target_cap": "reference_intent_exact_target_cap",
    "ui_defect_delete_generic_before_duplicate_target": "generic_non_reference_intent_displaydim",
    "ui_defect_block_generic_after_prune": "generic_non_reference_intent_displaydim_survived_after_prune",
    "reference_intent_delete_target_rank": "target_rank",
    "reference_intent_delete_priority_evidence": '"delete_priority": list(_delete_priority(item, annotated_before))',
    "generator_top_view_local_reference_lanes": "generator_top_view_local_reference_lanes",
    "physical_displaydim_dedupe": "physical_displaydim_dedupe",
    "sidecar_mode_written": "dimension_sidecar_mode",
    "sidecar_diagnostic_only_warning": "reference_intent_dimension_sidecar_diagnostic_only",
    "sidecar_event_drawing_path": '"drawing_path": str(slddrw)',
    "sidecar_event_acceptance_allowed": '"acceptance_allowed": not _skip_generic_model_dim_import',
    "strict_sidecar_acceptance_forbidden": '"acceptance_allowed": False',
    "ui_correction_evidence_env": "LB26001_006_UI_CORRECTION_EVIDENCE_PATH",
    "ui_correction_evidence_source_input": "lb26001_006_ui_correction_evidence_path",
    "ui_correction_evidence_warning": "lb26001_006_ui_correction_evidence_attached",
    "ui_defect_buckets_env": "LB26001_006_UI_DEFECT_BUCKETS_PATH",
    "ui_defect_buckets_source_input": "lb26001_006_ui_defect_buckets_path",
    "ui_defect_bucket_constraints": "reference_intent_ui_defect_bucket_constraints",
    "ui_defect_reject_autodim": "ui_defect_bucket_reject_generic_autodim_survivors",
    "ui_defect_compact_lanes": "ui_defect_bucket_compact_local_lanes",
    "ui_defect_compact_notes": "ui_defect_bucket_reference_style_notes",
    "ui_defect_compact_reference_roughness_note": '"3.2"',
    "ui_defect_compact_titlebar": "ui_defect_bucket_compact_titlebar_fields",
    "ui_defect_suppress_default_titlebar_fields": "ui_defect_bucket_suppress_default_titlebar_fields",
    "ui_defect_reference_titlebar_policy": "DrawingBlueprint.reference_titlebar_policy",
    "ui_defect_strict_target_match": "ui_defect_strict_reference_intent_target_match",
    "reference_callout_review_plan": "reference_callout_review_plan_required",
    "ui_defect_reference_callout_review_plan": "ui_defect_bucket_reference_callout_review_plan",
    "reference_callout_required_keys": "reference_callout_review_required_keys",
    "ui_defect_bucket_closure_contract": "ui_defect_bucket_closure_contract",
    "ui_defect_bucket_closure_pass_conditions": "ui_review_bucket_pass_conditions",
    "ui_defect_screenshot_visual_observations": "ui_defect_screenshot_visual_observations",
    "reference_intent_delete_equivalence_dedupe": "reference_intent_delete_equivalence_dedupe",
    "reference_intent_delete_equivalence_key": "reference_intent_delete_equivalence_key",
    "reference_dimension_lane_policy_attached": "reference_dimension_lane_policy_attached",
    "reference_dimension_lane_policy_top_side_gap": "top_view_side_lane_max_gap_m",
    "reference_dimension_lane_policy_issue_floor": "reference_lane_geometry_issue_count_after_required",
    "reference_view_outline_size_correction": "reference_view_outline_size_correction",
    "reference_view_outline_size_match_required": "view_outline_size_match_required",
    "generator_reference_lane_geometry_guard": "reference_lane_geometry_guard",
    "generator_reference_lane_geometry_issue_count": "reference_lane_geometry_issue_count_after",
}

CAD_WORKER_SIGNATURES = {
    "ui_correction_evidence_helper": "_prepare_lb26001_006_ui_correction_evidence",
    "ui_correction_evidence_sidecar": "lb26001_006_ui_correction_evidence.json",
    "ui_correction_evidence_rerun_packet_env": "SWDS_LB26001_006_RERUN_PACKET_PATH",
    "ui_defect_bucket_report_default": "lb26001_006_ui_defect_buckets_v4_4.json",
    "ui_defect_bucket_generator_env": "LB26001_006_UI_DEFECT_BUCKETS_PATH",
    "ui_correction_evidence_generator_env": "LB26001_006_UI_CORRECTION_EVIDENCE_PATH",
    "ui_correction_evidence_manifest_key": "ui_correction_evidence",
}

REFERENCE_INTENT_EXECUTOR_SIGNATURES = {
    "callout_operations": "callout_operations",
    "manufacturing_callout_operation": "create_or_verify_reference_callout",
    "absence_callout_operation": "verify_absent_reference_callout",
    "callout_operation_count": "callout_operation_count",
    "callout_worker_lock": '"requires_solidworks_lock": True',
    "callout_worker_entrypoint": '"allowed_entrypoint": "cad_job_worker"',
    "callout_ui_screenshot_gate": '"ui_screenshot_acceptance_required"',
}

PRODUCT_EVIDENCE_GATE_SIGNATURES = {
    "callout_operation_contract": '"callout_operation_contract": callout_operation_contract',
    "callout_operation_contract_function": "def _callout_operation_contract",
    "manufacturing_callout_operation": "create_or_verify_reference_callout",
    "absence_callout_operation": "verify_absent_reference_callout",
    "callout_worker_entrypoint": "cad_job_worker",
    "callout_ui_screenshot_gate": "ui_screenshot_acceptance_required",
}

REFERENCE_COMPARE_SIGNATURES = {
    "post_layout_final_required": "reference_intent_post_layout_final_coverage_missing",
    "generator_final_blocker_consumed": "post_layout_reference_intent_final_blocked",
    "lost_target_keys_reported": "lost_target_keys",
    "stage_delta_reported": "stage_delta",
}

VISION_QC_V6_SIGNATURES = {
    "ui_screenshot_final_gate": "manual_ui_screenshot_review_required",
    "ui_screenshot_content_validator": "validate_application_ui_screenshots",
    "ui_screenshot_content_pass_gate": "ui_screenshot_content_check_pass",
    "reference_sheet_template_artifact_check": "_reference_sheet_template_artifact_check",
    "reference_titleblock_artifact_issue": "reference_titleblock_artifacts_present",
    "reference_visual_grid_signature": "_ink_grid_signature",
    "reference_visual_grid_layout_match": "grid_layout_match",
    "dimension_cluster_issue": "dimension_visual_clustered_unreadable",
    "reference_callout_check": "_reference_callout_checks",
    "reference_callout_issue": "reference_callout_visual_check_missing",
    "reference_callout_manual_checklist": "reference_callout_checklist",
    "reference_callout_not_displaydim": "notes_do_not_count_as_display_dim",
    "template_policy_supporting_api_guard": "api_is_not_final_judgement",
}

DIMENSION_ARRANGE_SIGNATURES = {
    "top_view_local_reference_lanes": "Reference-style long-thin drawings keep top-view dimensions",
    "top_view_no_far_right_callout": "creates cross-view leader lines like the 006 visual review fail",
    "reference_lane_geometry_guard": "reference_lane_geometry_guard",
    "reference_lane_geometry_issue_count": "reference_lane_geometry_issue_count_after",
    "reference_lane_diagonal_leader_guard": "reference_lane_diagonal_or_cross_region_leader",
    "reference_dimension_lane_policy": "reference_dimension_lane_policy",
    "compact_top_side_lane_gap_policy": "top_view_side_lane_max_gap_m",
}

APPLICATION_UI_SCREENSHOT_VALIDATOR_SIGNATURES = {
    "single_screenshot_validator": "validate_application_ui_screenshot",
    "multi_screenshot_validator": "validate_application_ui_screenshots",
    "minimum_size_gate": "min_size_pass",
    "aspect_ratio_gate": "aspect_pass",
    "top_chrome_gate": "top_chrome_pass",
    "left_navigation_gate": "left_nav_pass",
    "bottom_log_gate": "bottom_log_pass",
    "side_by_side_review_gate": '"side_by_side_review_region_pass": side_by_side_pass',
    "side_by_side_region_helper": "_side_by_side_review_region_pass",
    "passing_paths_output": "passing_paths",
}

DIMENSION_VISUAL_VALIDATOR_SIGNATURES = {
    "dimension_cluster_summary": "_dimension_text_cluster_summary",
    "dimension_cluster_count": "max_local_dimension_text_cluster_count",
    "dimension_cluster_pass_gate": "visual_dimension_cluster_pass",
    "reference_style_readability_gate": "_reference_style_dimension_readability_required",
}

LIFECYCLE_AUDIT_SIGNATURES = {
    "display_dim_lifecycle_schema": "sw_drawing_studio.lb26001_006_displaydim_lifecycle_audit.v4_2",
    "post_prune_guard_audited": "post_prune_dim_guard",
    "post_prune_guard_coverage_audited": "target_coverage_after_guard",
    "prune_to_sidecar_loss_detected": "display_dim_lost_between_prune_and_sidecar",
    "post_layout_diagnostics_required": "post_layout_slot_rebind_diagnostics_missing",
    "post_layout_final_coverage_required": "post_layout_final_target_coverage_missing",
    "post_layout_direct_accept_rebind_audited": "direct_accept_failed_select_by_persisted_name",
    "target_stage_matrix_audited": "target_stage_matrix",
    "target_trace_fields_required": "target_trace_missing_fields",
    "existing_display_dim_coverage_trace": "existing_display_dim_coverage",
    "post_layout_target_matrix_view_not_found": "target_stage_matrix_view_not_found",
    "post_layout_slot_rebind_summary_missing": "post_layout_slot_rebind_summary_missing",
    "post_layout_slot_rebind_unbound_slots": "post_layout_slot_rebind_unbound_slots",
    "post_layout_live_view_recovery_failed": "post_layout_live_view_recovery_failed",
    "post_layout_live_view_counts_audited": "current_sheet_getviews_count",
    "prune_deleted_items_detail_audited": "prune_deleted_items_detail_missing",
    "prune_deleted_key_slot_reason_audited": "prune_deleted_item_key_slot_reason_missing",
    "sidecar_policy_audited": "sidecar_policy_summary",
    "strict_sidecar_mode_blocker": "strict_reference_intent_sidecar_mode_missing",
    "strict_sidecar_ran_blocker": "strict_reference_intent_sidecar_ran",
    "sidecar_path_blocker": "sidecar_drawing_path_not_current_run",
    "strict_sidecar_acceptance_blocker": "sidecar_acceptance_allowed_for_strict_reference_intent",
}

STAGED_VALIDATION_SIGNATURES = {
    "case_lifecycle_audit_writer": "_write_displaydim_lifecycle_audit_report",
    "case_lifecycle_report_output": "displaydim_lifecycle_audit.json",
    "case_lifecycle_not_pass_bucket": "displaydim_lifecycle_not_pass",
    "case_lifecycle_required_flag": "displaydim_lifecycle_required",
    "case_lifecycle_blocks_deliverable": "and lifecycle_pass",
    "vision_qc_requires_visual_acceptance": 'vision.get("visual_acceptance_pass")',
    "passes_stage_packet_to_smoke": "--lb26001-006-rerun-packet",
    "stage_packet_report_variable": "lb26001_006_rerun_packet_report",
}

REAL_CAD_SMOKE_SIGNATURES = {
    "packet_env_helper": "_set_006_rerun_packet_env",
    "packet_env_key": "SWDS_LB26001_006_RERUN_PACKET_PATH",
    "packet_cli_argument": "--lb26001-006-rerun-packet",
    "packet_report_field": "lb26001_006_rerun_packet_report",
    "direct_guard_packet_report_path": "packet_report_path",
    "facade_start_after_packet_env": "facade.start_cad_job",
}

DRAWING_VISUAL_REVIEW_SUITE_SIGNATURES = {
    "application_ui_source_mode": "source_qt_application_ui_screenshot",
    "application_ui_source_label": "Drawing Review page",
    "ui_screenshot_final_gate": "ui_screenshot_is_final_gate",
    "per_drawing_ui_required": "per_drawing_application_ui_screenshot_required",
    "api_only_acceptance_forbidden": "api_only_acceptance_allowed",
    "manual_judgement_template_written": "write_manual_visual_judgement_template",
    "manual_judgement_pending_status": "pending_manual_visual_judgement",
    "generated_png_source_evidence": "generated_png_source_evidence",
    "fresh_generated_png_strict_source": "strict_source_pass",
    "reference_and_generated_png_entry": '"reference_png": str(reference_png)',
}

MANUAL_VISUAL_JUDGEMENT_TEMPLATE_SIGNATURES = {
    "overall_pending_status": "PENDING_MANUAL_REVIEW",
    "entry_pending_status": '"manual_status": "PENDING"',
    "all_required_checklist_items": "required_visual_checklist_items",
    "checklist_defaults_to_null": '"visual_checklist": {key: None for key in REQUIRED_VISUAL_CHECKS}',
    "checklist_notes_defaults_empty": '"visual_checklist_notes": {key: "" for key in REQUIRED_VISUAL_CHECKS}',
    "application_ui_review_required": "application_ui_screenshot_review_required",
    "api_only_acceptance_forbidden": "api_only_acceptance_allowed",
    "ui_screenshot_final_gate": "ui_screenshot_review_is_final_gate",
    "pass_only_after_all_checks_true": "Set manual_status to PASS only when every visual_checklist item is true.",
    "template_writer": "write_manual_visual_judgement_template",
}

CORRECTION_PLAN_SIGNATURES = {
    "direct_ui_findings_keyword_mapping": "FINDING_CHECK_KEYWORDS",
    "direct_ui_findings_inferred_checks": "_inferred_check_notes_from_findings",
    "effective_failed_visual_checks": "effective_failed_visual_checks",
    "application_ui_screenshot_content_status": "application_ui_screenshot_content_check_pass",
    "per_drawing_visual_validation_policy": "per_drawing_application_ui_screenshot_required",
    "final_judgement_application_ui_source": "application_drawing_review_ui_screenshot_manual_visual_judgement",
    "current_missing_ui_requirements": "current_missing_ui_acceptance_requirements",
    "direct_ui_screenshot_source_type": "direct_ui_screenshot_finding",
    "direct_ui_findings_used_flag": "direct_ui_findings_used_for_correction",
}

APPLY_UI_REVIEW_SIGNATURES = {
    "ui_report_entry_gate": "ui_report_entry_pass",
    "manual_screenshot_binding_gate": "manual_review_entry_screenshot_pass",
    "manual_review_entries_all_pass": "manual_review_entries_all_pass",
    "ui_defect_bucket_closure_review_gate": "ui_defect_bucket_closure_not_proven",
    "ui_defect_bucket_closure_all_pass": "ui_defect_bucket_closure_all_pass",
    "ui_defect_buckets_cli_input": "--ui-defect-buckets",
    "application_ui_report_source_check": "_source_ui_report_application_ui_ok",
    "generated_png_source_gate": "generated_png_source_pass",
}

ACCEPTANCE_GATE_SIGNATURES = {
    "manual_visual_checklist_pass_required": "manual_visual_checklist_ok",
    "ui_screenshot_method_required": "ui_screenshot_review_method_ok",
    "staged_summary_lifecycle_input": "staged_summary_path",
    "displaydim_lifecycle_report_gate": "displaydim_lifecycle_report_exists",
    "displaydim_lifecycle_missing_blocker": "displaydim_lifecycle_report_missing",
    "displaydim_lifecycle_not_pass_blocker": "displaydim_lifecycle_not_pass",
    "manual_case_blocker_reported": "manual_visual_case_not_pass",
    "manual_checklist_blocker_reported": "manual_visual_checklist_missing_or_incomplete",
    "application_ui_source_blocker_reported": "application_ui_screenshot_source_report_invalid",
    "application_ui_screenshot_content_blocker": "application_ui_screenshot_content_invalid",
    "fresh_png_source_blocker_reported": "generated_png_source_evidence_not_current_run",
}

ACCEPTANCE_PROOF_SIGNATURES = {
    "supplemental_checklist_gate": "DEFAULT_SUPPLEMENTAL_CHECKLIST_GATE",
    "supplemental_checklist_base_merge": "supplemental_checklist_base",
    "displaydim_lifecycle_report_evidence": "displaydim_lifecycle_report_exists",
    "displaydim_lifecycle_report_missing_blocker": "displaydim_lifecycle_report_missing",
    "displaydim_lifecycle_not_pass_blocker": "displaydim_lifecycle_not_pass",
    "application_ui_source_report_blocker": "application_ui_source_report_invalid",
    "manual_visual_case_blocker": "manual_visual_case_not_pass",
    "manual_visual_checklist_missing_blocker": "manual_visual_checklist_missing",
    "manual_visual_checklist_not_pass_blocker": "manual_visual_checklist_not_pass",
    "direct_ui_screenshot_recheck_blocker": "direct_ui_screenshot_recheck_not_pass",
    "fresh_png_source_blocker": "generated_png_source_not_current_run",
}


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


def _repo_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


def _base_map(payload: dict[str, Any], key: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in payload.get(key) or []:
        if not isinstance(item, dict):
            continue
        base = str(item.get("base") or "").strip()
        if base:
            result[base] = item
    return result


def _signature_status(path: Path, signatures: dict[str, str]) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except Exception:
        text = ""
    items = [
        {"key": key, "signature": signature, "present": signature in text}
        for key, signature in signatures.items()
    ]
    return {
        "path": str(path),
        "exists": path.exists(),
        "pass": bool(path.exists()) and all(item["present"] for item in items),
        "required_signatures": items,
        "missing_signatures": [item["key"] for item in items if not item["present"]],
    }


def _reference_intent_artifact_status(path: Path, expected_keys: list[str] | None = None) -> dict[str, Any]:
    payload = _read_json(path)
    expected = expected_keys or []
    text = json.dumps(payload, ensure_ascii=False)
    missing = [key for key in expected if key not in text]
    return {
        "path": str(path),
        "exists": path.exists(),
        "pass": path.exists() and not missing,
        "missing_expected_keys": missing,
    }


def _ui_defect_bucket_status(path: Path) -> dict[str, Any]:
    payload = _read_json(path)
    source_artifacts = payload.get("source_artifacts") if isinstance(payload.get("source_artifacts"), dict) else {}
    required_source_artifact_keys = ["manual_review", "ui_report", "staged_summary"]
    source_artifact_exists = {
        key: _nonempty_file(source_artifacts.get(key))
        for key in required_source_artifact_keys
    }
    missing_source_artifact_keys = [
        key for key in required_source_artifact_keys if not source_artifact_exists.get(key)
    ]
    generated_at_parse_ok = _parse_generated_at(payload.get("generated_at")) is not None
    active_buckets = [
        str(item)
        for item in (payload.get("active_buckets") or [])
        if str(item).strip()
    ]
    expected_active = REQUIRED_ACTIVE_UI_DEFECT_BUCKETS
    expected_all = REQUIRED_UI_DEFECT_BUCKETS
    next_check_buckets = {
        str(item)
        for item in (payload.get("required_next_screenshot_check_buckets") or [])
        if str(item).strip()
    }
    checklist_items = [item for item in payload.get("next_screenshot_checklist") or [] if isinstance(item, dict)]
    checklist_buckets = {str(item.get("bucket") or "") for item in checklist_items}
    callout_check = next((item for item in checklist_items if item.get("bucket") == "callout_missing"), {})
    callout_closure_contract = {}
    callout_next_check_ok = (
        REQUIRED_CALLOUT_KEYS <= set(callout_check.get("required_callout_keys") or [])
        and CALLOUT_ABSENCE_CHECK_KEYS <= set(callout_check.get("absence_check_keys") or [])
    )
    closure_items = [item for item in payload.get("bucket_closure_contract") or [] if isinstance(item, dict)]
    closure_by_bucket = {str(item.get("bucket") or ""): item for item in closure_items}
    missing_closure_contract = sorted(expected_all - set(closure_by_bucket))
    incomplete_closure_contracts: dict[str, list[str]] = {}
    for bucket in sorted(expected_all):
        item = closure_by_bucket.get(bucket) or {}
        missing_fields: list[str] = []
        if not item.get("source_failure_evidence"):
            missing_fields.append("source_failure_evidence")
        if not item.get("repair_inputs"):
            missing_fields.append("repair_inputs")
        if not item.get("implementation_guard_keys"):
            missing_fields.append("implementation_guard_keys")
        post_evidence = set(item.get("post_rerun_required_evidence") or [])
        if not REQUIRED_CLOSURE_EVIDENCE_KEYS <= post_evidence:
            missing_fields.append("post_rerun_required_evidence")
        if not str(item.get("ui_review_pass_condition") or "").strip():
            missing_fields.append("ui_review_pass_condition")
        if bucket == "callout_missing":
            if not REQUIRED_CALLOUT_KEYS <= set(item.get("required_callout_keys") or []):
                missing_fields.append("required_callout_keys")
            if not CALLOUT_ABSENCE_CHECK_KEYS <= set(item.get("absence_check_keys") or []):
                missing_fields.append("absence_check_keys")
            if "reference_callout_checklist" not in post_evidence:
                missing_fields.append("reference_callout_checklist")
        if missing_fields:
            incomplete_closure_contracts[bucket] = missing_fields
    callout_closure_contract = closure_by_bucket.get("callout_missing") or {}
    callout_closure_contract_ok = (
        REQUIRED_CALLOUT_KEYS <= set(callout_closure_contract.get("required_callout_keys") or [])
        and CALLOUT_ABSENCE_CHECK_KEYS <= set(callout_closure_contract.get("absence_check_keys") or [])
        and "reference_callout_checklist" in set(callout_closure_contract.get("post_rerun_required_evidence") or [])
    )
    observation_items = [
        item for item in payload.get("screenshot_visual_observations") or [] if isinstance(item, dict)
    ]
    observation_buckets = {
        str(item.get("bucket") or "")
        for item in observation_items
        if str(item.get("bucket") or "").strip()
    }
    active_observation_buckets = {
        str(item.get("bucket") or "")
        for item in observation_items
        if item.get("supports_active_bucket") is True
    }
    missing_active_observation_buckets = sorted(expected_active - active_observation_buckets)
    callout_observation = next((item for item in observation_items if item.get("bucket") == "callout_missing"), {})
    callout_observation_ok = (
        callout_observation.get("next_screenshot_check_required") is True
        and callout_observation.get("api_or_displaydim_metric_alone_can_close") is False
    )
    missing_active = sorted(expected_active - set(active_buckets))
    missing_next_check = sorted(expected_all - next_check_buckets)
    missing_checklist = sorted(expected_all - checklist_buckets)
    pass_ = (
        path.exists()
        and payload.get("schema") == "sw_drawing_studio.lb26001_006_ui_defect_buckets.v4_4"
        and payload.get("base") == PRIMARY_BASE
        and generated_at_parse_ok
        and payload.get("pass") is False
        and payload.get("application_ui_screenshot_is_final_gate") is True
        and payload.get("api_only_acceptance_allowed") is False
        and payload.get("expansion_allowed_now") is False
        and not missing_source_artifact_keys
        and not missing_active
        and not missing_next_check
        and not missing_checklist
        and callout_next_check_ok
        and not missing_closure_contract
        and not incomplete_closure_contracts
        and callout_closure_contract_ok
        and not missing_active_observation_buckets
        and callout_observation_ok
    )
    return {
        "path": str(path),
        "exists": path.exists(),
        "schema": payload.get("schema"),
        "generated_at": payload.get("generated_at"),
        "generated_at_parse_ok": generated_at_parse_ok,
        "status": payload.get("status"),
        "pass": pass_,
        "source_artifacts": {key: source_artifacts.get(key, "") for key in required_source_artifact_keys},
        "source_artifact_exists": source_artifact_exists,
        "missing_source_artifact_keys": missing_source_artifact_keys,
        "active_bucket_count": len(active_buckets),
        "active_buckets": active_buckets,
        "missing_required_active_buckets": missing_active,
        "required_next_screenshot_check_buckets": sorted(next_check_buckets),
        "missing_next_screenshot_check_buckets": missing_next_check,
        "missing_next_screenshot_checklist_buckets": missing_checklist,
        "required_callout_keys": sorted(REQUIRED_CALLOUT_KEYS),
        "callout_absence_check_keys": sorted(CALLOUT_ABSENCE_CHECK_KEYS),
        "next_screenshot_required_callout_keys": list(callout_check.get("required_callout_keys") or []),
        "closure_contract_required_callout_keys": list(
            callout_closure_contract.get("required_callout_keys") or []
        ),
        "callout_next_check_ok": callout_next_check_ok,
        "bucket_closure_contract_buckets": sorted(set(closure_by_bucket)),
        "missing_bucket_closure_contract_keys": missing_closure_contract,
        "incomplete_bucket_closure_contracts": incomplete_closure_contracts,
        "callout_closure_contract_ok": callout_closure_contract_ok,
        "screenshot_visual_observation_buckets": sorted(observation_buckets),
        "missing_active_screenshot_visual_observation_buckets": missing_active_observation_buckets,
        "callout_screenshot_visual_observation_ok": callout_observation_ok,
        "solidworks_readiness": payload.get("solidworks_readiness") or {},
    }


def _nonempty_file(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        path = Path(value)
        return path.exists() and path.is_file() and path.stat().st_size > 0
    except OSError:
        return False


def _parse_generated_at(value: Any) -> float | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return time.mktime(time.strptime(text[:19], fmt))
        except ValueError:
            continue
    return None


def _prerequisite(key: str, passed: bool, evidence: dict[str, Any], fix_suggestion: str) -> dict[str, Any]:
    return {
        "key": key,
        "pass": bool(passed),
        "evidence": evidence,
        "fix_suggestion": fix_suggestion,
    }


def _readiness_ready(readiness: dict[str, Any]) -> bool:
    return bool(readiness.get("ready_to_start_locked_006_cad")) and not bool(readiness.get("blocking_issue_keys"))


def _ordered_next_gates() -> list[dict[str, str]]:
    return [
        {
            "gate": "no_com_readiness_audit",
            "command": "python tools\\validation\\lb26001_006_regression_readiness_v4_2.py --out drw_output\\diagnostics\\lb26001_006_regression_readiness_v4_2.json",
            "acceptance": "ready_to_start_locked_006_cad must be true before real CAD starts.",
        },
        {
            "gate": "locked_006_real_cad_rerun",
            "command": "python tools\\validation\\staged_cad_validation_v3.py --stage LB26001_006 --timeout-s 900 --max-rounds 1 --out-dir drw_output\\staged_validation\\LB26001_006_<timestamp>",
            "execution_path": "staged_cad_validation_v3.py -> real_cad_smoke_v3.py -> JobRuntimeFacade.start_cad_job -> JobRunner/QProcess -> cad_job_worker.py -> SolidWorks global lock",
            "acceptance": "One 006-only JobRuntimeFacade.start_cad_job / QProcess CAD worker run, protected by the SolidWorks global lock, with a staged summary for the application UI screenshot review.",
        },
        {
            "gate": "dimension_validation",
            "command": "python tools\\validation\\dimension_validation_smoke_v3.py --run-dir <fresh_run_dir> --out drw_output\\dimension_validation_006_v4_2.json",
            "acceptance": "Final persisted/exported real DisplayDim count must be >= 12; Note/OCR/sidecar text is not accepted.",
        },
        {
            "gate": "displaydim_lifecycle_audit",
            "command": (
                "python tools\\validation\\lb26001_006_displaydim_lifecycle_audit_v4_2.py "
                "--warnings <fresh_run_dir>\\qc\\LB26001-A-04-006_v5_warnings.json "
                "--cad-smoke <fresh_case_dir>\\cad_smoke.json "
                "--dimension-validation <fresh_case_dir>\\dimension_validation.json "
                "--out-json drw_output\\diagnostics\\lb26001_006_displaydim_lifecycle_audit_v4_2_<run_id>.json "
                "--out-md drw_output\\diagnostics\\lb26001_006_displaydim_lifecycle_audit_v4_2_<run_id>.md"
            ),
            "acceptance": "pre-save, post-save/reopen, post-prune, post-layout, and final export must all preserve at least 12 real DisplayDim targets with no sidecar acceptance.",
        },
        {
            "gate": "reference_compare_v3",
            "command": "python tools\\validation\\reference_compare_smoke_v3.py --run-dir <fresh_run_dir> --part <copied_input_part> --out <fresh_case_dir>\\reference_compare.json",
            "acceptance": "Same-name reference drawing comparison must pass or pass_with_warning with no strict 006 blockers.",
        },
        {
            "gate": "reference_style",
            "command": "python tools\\validation\\reference_style_profile_v3.py --bases LB26001-A-04-006 --stage-summary <fresh_summary.json> --out-dir drw_output\\reference_style_profile\\LB26001_006_<run_id>",
            "acceptance": "Same-name reference style report must pass: view family, layout centers, DisplayDim floor, and no default template pollution.",
        },
        {
            "gate": "strict_reference_compare_v4",
            "command": "python tools\\validation\\reference_compare_v4.py --run-dir <fresh_run_dir> --base LB26001-A-04-006 --out drw_output\\reference_compare_v4_006_v4_2.json",
            "acceptance": "View family/layout, target coverage, title block policy, and post_layout_final coverage must pass.",
        },
        {
            "gate": "vision_qc_v6",
            "command": "verify <fresh_case_dir>\\vision_qc_v6.json from staged_cad_validation_v3.py or run app.services.vision_qc_v6.run_vision_qc_v6 on the fresh generated PNG/reference PNG",
            "acceptance": "vision_qc_v6 must pass with reference visual layout, readable dimensions, title block/template policy, and UI screenshot review requirements satisfied.",
        },
        {
            "gate": "drawing_review_application_ui_screenshot",
            "command": "python tools\\ui_robot\\drawing_visual_review_suite.py --summary <fresh_summary.json> --base LB26001-A-04-006 --out-dir drw_output\\ui_acceptance\\LB26001_006_<timestamp>_visual_review",
            "acceptance": "The Drawing Review application UI must show reference and generated drawing screenshots for visual judgement.",
        },
        {
            "gate": "manual_visual_judgement",
            "command": "write <fresh_manual_visual_judgement.json> from the application UI screenshot",
            "acceptance": "Every required checklist item must be true: reference_match, view_layout, display_dimensions, dimension_readability, title_block, manufacturing_notes.",
        },
        {
            "gate": "with_ui_closure",
            "command": "python tools\\validation\\apply_ui_visual_review_v4.py --summary <fresh_summary.json> --ui-report <fresh_drawing_visual_review_report.json> --manual-review <fresh_manual_visual_judgement.json> --out-dir <fresh_closed_loop_dir> --base LB26001-A-04-006",
            "acceptance": "vision_qc_v6_with_ui_review and reference_compare_v4_with_ui_review must both pass.",
        },
        {
            "gate": "lb26001_expansion_gate",
            "command": "python tools\\validation\\lb26001_acceptance_gate_v4_2.py --gate-summary <fresh_ui_visual_review_gate_summary.json> --staged-summary <fresh_staged_summary.json>",
            "acceptance": "Only after 006 passes lifecycle/v3/v4/v6 and application UI screenshot gates may 007/008/009/015/022 proceed.",
        },
    ]


def build_rerun_packet(
    *,
    readiness: dict[str, Any],
    requested_status: dict[str, Any],
    correction_plan: dict[str, Any],
    reference_intent_plan_path: Path = DEFAULT_REFERENCE_INTENT_PLAN,
    reference_intent_contract_path: Path = DEFAULT_REFERENCE_INTENT_CONTRACT,
    ui_defect_buckets_path: Path = DEFAULT_UI_DEFECT_BUCKETS,
    correction_plan_source_path: Path = DEFAULT_CORRECTION_PLAN_SOURCE,
    reference_intent_executor_source_path: Path = DEFAULT_REFERENCE_INTENT_EXECUTOR_SOURCE,
    product_evidence_gate_source_path: Path = DEFAULT_PRODUCT_EVIDENCE_GATE_SOURCE,
    cad_worker_source_path: Path = DEFAULT_CAD_WORKER_SOURCE,
    generator_source_path: Path = DEFAULT_GENERATOR_SOURCE,
    reference_compare_source_path: Path = DEFAULT_REFERENCE_COMPARE_SOURCE,
    vision_qc_v6_source_path: Path = DEFAULT_VISION_QC_V6_SOURCE,
    application_ui_screenshot_validator_source_path: Path = DEFAULT_APPLICATION_UI_SCREENSHOT_VALIDATOR_SOURCE,
    dimension_visual_validator_source_path: Path = DEFAULT_DIMENSION_VISUAL_VALIDATOR_SOURCE,
    dimension_arrange_source_path: Path = DEFAULT_DIMENSION_ARRANGE_SOURCE,
    lifecycle_audit_source_path: Path = DEFAULT_LIFECYCLE_AUDIT_SOURCE,
    staged_validation_source_path: Path = DEFAULT_STAGED_VALIDATION_SOURCE,
    real_cad_smoke_source_path: Path = DEFAULT_REAL_CAD_SMOKE_SOURCE,
    drawing_visual_review_suite_source_path: Path = DEFAULT_DRAWING_VISUAL_REVIEW_SUITE_SOURCE,
    manual_visual_judgement_template_source_path: Path = DEFAULT_MANUAL_VISUAL_JUDGEMENT_TEMPLATE_SOURCE,
    apply_ui_review_source_path: Path = DEFAULT_APPLY_UI_REVIEW_SOURCE,
    acceptance_gate_source_path: Path = DEFAULT_ACCEPTANCE_GATE_SOURCE,
    acceptance_proof_source_path: Path = DEFAULT_ACCEPTANCE_PROOF_SOURCE,
) -> dict[str, Any]:
    requested_by_base = _base_map(requested_status, "base_results")
    correction_by_base = _base_map(correction_plan, "entries")
    current_006 = requested_by_base.get(PRIMARY_BASE, {})
    correction_006 = correction_by_base.get(PRIMARY_BASE, {})
    correction_ui_failures = correction_006.get("ui_visual_failures") if isinstance(correction_006.get("ui_visual_failures"), dict) else {}
    correction_effective_checks = list(correction_ui_failures.get("effective_failed_visual_checks") or [])
    current_failed_items = list(current_006.get("manual_visual_checklist_failed_items") or []) or correction_effective_checks
    correction_actions = list(correction_006.get("correction_actions") or [])
    correction_ui_status = correction_006.get("current_ui_status") if isinstance(correction_006.get("current_ui_status"), dict) else {}
    correction_plan_matches_current_006 = bool(correction_ui_status) and (
        str(correction_ui_status.get("status") or "") == str(current_006.get("status") or "")
        and str(correction_ui_status.get("latest_manual_review") or "") == str(current_006.get("latest_manual_review") or "")
        and bool(correction_ui_status.get("generated_png_source_pass")) == bool(current_006.get("generated_png_source_pass"))
        and bool(correction_ui_status.get("application_ui_screenshot_content_check_pass"))
        == bool(current_006.get("application_ui_screenshot_content_check_pass"))
    )
    cad_worker_signatures = _signature_status(cad_worker_source_path, CAD_WORKER_SIGNATURES)
    reference_intent_executor_signatures = _signature_status(
        reference_intent_executor_source_path,
        REFERENCE_INTENT_EXECUTOR_SIGNATURES,
    )
    product_evidence_gate_signatures = _signature_status(
        product_evidence_gate_source_path,
        PRODUCT_EVIDENCE_GATE_SIGNATURES,
    )
    generator_signatures = _signature_status(generator_source_path, GENERATOR_SIGNATURES)
    reference_compare_signatures = _signature_status(reference_compare_source_path, REFERENCE_COMPARE_SIGNATURES)
    vision_qc_v6_signatures = _signature_status(vision_qc_v6_source_path, VISION_QC_V6_SIGNATURES)
    application_ui_screenshot_validator_signatures = _signature_status(
        application_ui_screenshot_validator_source_path,
        APPLICATION_UI_SCREENSHOT_VALIDATOR_SIGNATURES,
    )
    dimension_visual_signatures = _signature_status(
        dimension_visual_validator_source_path,
        DIMENSION_VISUAL_VALIDATOR_SIGNATURES,
    )
    dimension_arrange_signatures = _signature_status(
        dimension_arrange_source_path,
        DIMENSION_ARRANGE_SIGNATURES,
    )
    lifecycle_audit_signatures = _signature_status(lifecycle_audit_source_path, LIFECYCLE_AUDIT_SIGNATURES)
    staged_validation_signatures = _signature_status(staged_validation_source_path, STAGED_VALIDATION_SIGNATURES)
    real_cad_smoke_signatures = _signature_status(real_cad_smoke_source_path, REAL_CAD_SMOKE_SIGNATURES)
    drawing_visual_review_signatures = _signature_status(
        drawing_visual_review_suite_source_path,
        DRAWING_VISUAL_REVIEW_SUITE_SIGNATURES,
    )
    manual_visual_judgement_template_signatures = _signature_status(
        manual_visual_judgement_template_source_path,
        MANUAL_VISUAL_JUDGEMENT_TEMPLATE_SIGNATURES,
    )
    correction_plan_signatures = _signature_status(correction_plan_source_path, CORRECTION_PLAN_SIGNATURES)
    apply_ui_review_signatures = _signature_status(apply_ui_review_source_path, APPLY_UI_REVIEW_SIGNATURES)
    acceptance_gate_signatures = _signature_status(acceptance_gate_source_path, ACCEPTANCE_GATE_SIGNATURES)
    acceptance_proof_signatures = _signature_status(acceptance_proof_source_path, ACCEPTANCE_PROOF_SIGNATURES)
    reference_intent_plan = _reference_intent_artifact_status(
        reference_intent_plan_path,
        expected_keys=["target_key", "post_layout_final", "AddDiameterDimension2"],
    )
    reference_intent_contract = _reference_intent_artifact_status(
        reference_intent_contract_path,
        expected_keys=[
            "target_key",
            "selected_entity",
            "persisted_after_reopen",
            "callout_operations",
            "callout_operation_count",
            "create_or_verify_reference_callout",
            "verify_absent_reference_callout",
            "thread_callout_m4_6h",
            "hole_callout_4x3_3",
            "surface_finish_rest_3_2",
            "radius_callout",
            "chamfer_callout",
        ],
    )
    ui_defect_buckets = _ui_defect_bucket_status(ui_defect_buckets_path)

    readiness_blockers = [str(item) for item in readiness.get("blocking_issue_keys") or [] if str(item).strip()]
    prerequisites = [
        _prerequisite(
            "readiness_report_loaded",
            bool(readiness),
            {
                "status": readiness.get("status"),
                "ready_to_start_locked_006_cad": readiness.get("ready_to_start_locked_006_cad"),
                "blocking_issue_keys": readiness_blockers,
            },
            "Regenerate lb26001_006_regression_readiness_v4_2.json.",
        ),
        _prerequisite(
            "requested_six_drawing_ui_status_loaded",
            bool(requested_by_base) and all(base in requested_by_base for base in REQUESTED_BASES),
            {
                "status": requested_status.get("status"),
                "pass_count": requested_status.get("pass_count"),
                "not_pass_count": requested_status.get("not_pass_count"),
                "requested_bases": requested_status.get("requested_bases"),
            },
            "Regenerate lb26001_requested_drawings_status_v4_2.json with all six requested bases.",
        ),
        _prerequisite(
            "six_requested_drawings_recorded_as_ui_failed",
            requested_status.get("pass_count") == 0
            and requested_status.get("not_pass_count") == len(REQUESTED_BASES)
            and requested_status.get("all_generated_drawings_currently_unqualified") is True,
            {
                "pass_count": requested_status.get("pass_count"),
                "not_pass_count": requested_status.get("not_pass_count"),
                "all_generated_drawings_currently_unqualified": requested_status.get("all_generated_drawings_currently_unqualified"),
            },
            "Refresh the requested drawing status so application UI screenshot failures are explicit.",
        ),
        _prerequisite(
            "006_application_ui_fail_is_latest_gate",
            current_006.get("application_ui_screenshot_review_present") is True
            and current_006.get("manual_visual_checklist_pass") is False
            and bool(current_006.get("latest_manual_review")),
            {
                "status": current_006.get("status"),
                "latest_manual_review": current_006.get("latest_manual_review"),
                "source_ui_report": current_006.get("source_ui_report"),
                "failed_items": current_006.get("manual_visual_checklist_failed_items"),
            },
            "Capture/close a Drawing Review UI screenshot judgement for 006 before considering a rerun packet complete.",
        ),
        _prerequisite(
            "correction_plan_ready",
            correction_plan.get("correction_plan_ready") is True and not correction_plan.get("missing_reference_rules"),
            {
                "status": correction_plan.get("status"),
                "correction_plan_ready": correction_plan.get("correction_plan_ready"),
                "missing_reference_rules": correction_plan.get("missing_reference_rules"),
            },
            "Regenerate lb26001_correction_plan_v4_2.json from current standard/status/readiness inputs.",
        ),
        _prerequisite(
            "correction_plan_matches_current_006_status",
            correction_plan_matches_current_006,
            {
                "requested_status": current_006.get("status"),
                "correction_status": correction_ui_status.get("status"),
                "requested_latest_manual_review": current_006.get("latest_manual_review"),
                "correction_latest_manual_review": correction_ui_status.get("latest_manual_review"),
                "requested_generated_png_source_pass": current_006.get("generated_png_source_pass"),
                "correction_generated_png_source_pass": correction_ui_status.get("generated_png_source_pass"),
                "requested_ui_screenshot_content_check_pass": current_006.get("application_ui_screenshot_content_check_pass"),
                "correction_ui_screenshot_content_check_pass": correction_ui_status.get("application_ui_screenshot_content_check_pass"),
            },
            "Regenerate lb26001_correction_plan_v4_2.json after refreshing the requested six-drawing status.",
        ),
        _prerequisite(
            "006_correction_entry_present",
            bool(correction_006) and correction_006.get("correction_stage") == "pilot_006_first",
            {
                "correction_stage": correction_006.get("correction_stage"),
                "blocked_by_readiness": correction_006.get("blocked_by_readiness"),
                "reference_intent_trace_policy": correction_006.get("reference_intent_trace_policy"),
            },
            "Ensure the correction plan keeps 006 as the pilot gate.",
        ),
        _prerequisite(
            "006_effective_ui_corrections_present",
            bool(current_006.get("pass")) or (bool(current_failed_items) and bool(correction_actions)),
            {
                "requested_status": current_006.get("status"),
                "failed_visual_checklist_items": current_failed_items,
                "correction_action_count": len(correction_actions),
                "direct_ui_findings_used_for_correction": correction_ui_failures.get("direct_ui_findings_used_for_correction") is True,
            },
            "Regenerate the correction plan so the latest UI screenshot findings become actionable correction items.",
        ),
        _prerequisite(
            "006_reference_intent_plan_ready",
            reference_intent_plan["pass"],
            reference_intent_plan,
            "Regenerate the 006 reference-intent dimension plan with target keys and post_layout_final requirements.",
        ),
        _prerequisite(
            "006_reference_intent_contract_ready",
            reference_intent_contract["pass"],
            reference_intent_contract,
            "Regenerate the 006 worker contract with target_key, selected_entity, and persisted_after_reopen fields.",
        ),
        _prerequisite(
            "006_ui_defect_buckets_ready",
            ui_defect_buckets["pass"],
            ui_defect_buckets,
            "Regenerate lb26001_006_ui_defect_buckets_v4_4.json from the latest application Drawing Review UI screenshot failure.",
        ),
        _prerequisite(
            "cad_worker_ui_correction_evidence_signatures_present",
            cad_worker_signatures["pass"],
            cad_worker_signatures,
            "Restore cad_job_worker so the next 006 run writes UI correction evidence sidecar and passes its path to the generator.",
        ),
        _prerequisite(
            "reference_intent_executor_callout_signatures_present",
            reference_intent_executor_signatures["pass"],
            reference_intent_executor_signatures,
            "Restore reference_intent_dimension_executor.py so the next 006 worker contract includes locked callout and absence-check operations.",
        ),
        _prerequisite(
            "product_gate_callout_contract_signatures_present",
            product_evidence_gate_signatures["pass"],
            product_evidence_gate_signatures,
            "Restore Product Evidence Gate callout operation contract checks before allowing another 006 rerun.",
        ),
        _prerequisite(
            "generator_repair_signatures_present",
            generator_signatures["pass"],
            generator_signatures,
            "Restore generator logic for view-family rebinding, target coverage deltas, and final post-layout blockers.",
        ),
        _prerequisite(
            "strict_v4_compare_signatures_present",
            reference_compare_signatures["pass"],
            reference_compare_signatures,
            "Restore strict v4 comparison handling for post_layout_final coverage, lost targets, and generator blockers.",
        ),
        _prerequisite(
            "vision_qc_v6_ui_template_policy_signatures_present",
            vision_qc_v6_signatures["pass"],
            vision_qc_v6_signatures,
            "Restore v6 visual QC handling for application UI screenshot gating and reference-style titleblock/template artifact rejection.",
        ),
        _prerequisite(
            "application_ui_screenshot_validator_signatures_present",
            application_ui_screenshot_validator_signatures["pass"],
            application_ui_screenshot_validator_signatures,
            "Restore application_ui_screenshot_validator.py so arbitrary PNGs cannot masquerade as Drawing Review application UI screenshots.",
        ),
        _prerequisite(
            "dimension_visual_readability_signatures_present",
            dimension_visual_signatures["pass"],
            dimension_visual_signatures,
            "Restore dimension visual readability clustering checks so dense reference-style dimensions cannot pass by API count alone.",
        ),
        _prerequisite(
            "dimension_arrange_reference_lane_signatures_present",
            dimension_arrange_signatures["pass"],
            dimension_arrange_signatures,
            "Restore dimension arrange logic so long-thin top-view dimensions stay in local reference lanes instead of far-right callout lanes that create cross-view leaders.",
        ),
        _prerequisite(
            "displaydim_lifecycle_audit_ready",
            lifecycle_audit_signatures["pass"],
            lifecycle_audit_signatures,
            "Restore the no-COM lifecycle audit so the next 006 rerun can explain DisplayDim losses by stage.",
        ),
        _prerequisite(
            "staged_validation_lifecycle_ui_gate_signatures_present",
            staged_validation_signatures["pass"],
            staged_validation_signatures,
            "Restore staged_cad_validation_v3 so each 006 staged case writes DisplayDim lifecycle evidence, requires application UI visual acceptance before deliverability, and passes the stage-local rerun packet to real_cad_smoke_v3.",
        ),
        _prerequisite(
            "real_cad_smoke_packet_env_signatures_present",
            real_cad_smoke_signatures["pass"],
            real_cad_smoke_signatures,
            "Restore real_cad_smoke_v3 so the 006 direct/staged smoke path writes the rerun packet report and sets SWDS_LB26001_006_RERUN_PACKET_PATH before JobRuntimeFacade starts the CAD worker.",
        ),
        _prerequisite(
            "drawing_visual_review_suite_source_signatures_present",
            drawing_visual_review_signatures["pass"],
            drawing_visual_review_signatures,
            "Restore drawing_visual_review_suite.py so 006 UI closure is captured from the Drawing Review application page with generated/reference PNG evidence and a manual judgement template, not from handwritten API-only JSON.",
        ),
        _prerequisite(
            "manual_visual_judgement_template_signatures_present",
            manual_visual_judgement_template_signatures["pass"],
            manual_visual_judgement_template_signatures,
            "Restore manual_visual_judgement_template_v4.py so generated templates remain pending, checklist-complete, and impossible to mistake for acceptance evidence.",
        ),
        _prerequisite(
            "correction_plan_source_signatures_present",
            correction_plan_signatures["pass"],
            correction_plan_signatures,
            "Restore correction-plan logic that maps direct UI screenshot findings into effective visual checks and correction actions.",
        ),
        _prerequisite(
            "apply_ui_visual_review_gate_signatures_present",
            apply_ui_review_signatures["pass"],
            apply_ui_review_signatures,
            "Restore the UI closure tool signatures for application screenshot entries, manual screenshot binding, and generated PNG source checks.",
        ),
        _prerequisite(
            "acceptance_gate_manual_ui_signatures_present",
            acceptance_gate_signatures["pass"],
            acceptance_gate_signatures,
            "Restore the LB26001 acceptance gate signatures that require manual case PASS, complete visual checklist, application UI source, and fresh PNG source.",
        ),
        _prerequisite(
            "006_acceptance_proof_manual_ui_signatures_present",
            acceptance_proof_signatures["pass"],
            acceptance_proof_signatures,
            "Restore the 006 proof signatures that expose application UI source, manual case, manual checklist, and fresh PNG blockers.",
        ),
    ]
    offline_missing = [item["key"] for item in prerequisites if not item["pass"]]
    offline_ready = not offline_missing
    real_cad_allowed_now = bool(offline_ready and _readiness_ready(readiness))

    if offline_missing:
        status = "offline_prerequisites_missing"
    elif real_cad_allowed_now:
        status = "ready_for_locked_006_rerun"
    else:
        status = "blocked_by_solidworks_readiness"

    return {
        "schema": "sw_drawing_studio.lb26001_006_rerun_packet.v4_2",
        "generated_at": _now(),
        "base": PRIMARY_BASE,
        "status": status,
        "pass": False,
        "report_is_acceptance_evidence": False,
        "packet_build_ready": offline_ready,
        "real_cad_allowed_now": real_cad_allowed_now,
        "readiness_ready": _readiness_ready(readiness),
        "readiness_status": readiness.get("status"),
        "readiness_blocking_issue_keys": readiness_blockers,
        "offline_prerequisite_missing_keys": offline_missing,
        "must_not_run_real_cad_when_blocked": True,
        "api_is_not_final_judgement": True,
        "api_only_acceptance_allowed": False,
        "application_ui_screenshot_is_final_gate": True,
        "requested_bases": REQUESTED_BASES,
        "expansion_policy": {
            "006_must_pass_first": True,
            "blocked_bases_until_006_passes": [base for base in REQUESTED_BASES if base != PRIMARY_BASE],
            "expansion_allowed_now": bool(real_cad_allowed_now and current_006.get("pass") is True),
        },
        "ui_screenshot_validation_policy": {
            "per_drawing_application_ui_screenshot_required": True,
            "required_review_mode": "application_drawing_review_ui_screenshot",
            "required_visual_checklist": REQUIRED_VISUAL_CHECKS,
            "manual_case_pass_required": True,
            "fresh_generated_png_under_run_dir_required": True,
            "supporting_api_metrics_do_not_override_visual_fail": True,
            "api_only_acceptance_allowed": False,
        },
        "post_rerun_acceptance_requirements": [
            {
                "key": "fresh_generated_png_source_evidence",
                "required": True,
                "current_pass": current_006.get("generated_png_source_pass") is True,
                "evidence": current_006.get("generated_png_source_evidence"),
                "fix_suggestion": "After the next locked CAD rerun, capture Drawing Review UI evidence from the PNG under drw_output/runs/<run_id>/drawing/.",
            },
            {
                "key": "displaydim_lifecycle_audit_pass",
                "required": True,
                "current_pass": False,
                "evidence": {
                    "required_floor": 12,
                    "required_stages": [
                        "pre_saveas",
                        "post_saveas_reopen_prune",
                        "post_saveas_reopen_prune_guard",
                        "pre_export_final",
                        "post_layout_final",
                    ],
                    "sidecar_acceptance_allowed": False,
                    "slot_rebind_summary_required": True,
                },
                "fix_suggestion": "After the next locked CAD rerun, run the 006 DisplayDim lifecycle audit and require it to pass before any UI-backed acceptance or expansion.",
            },
            {
                "key": "reference_compare_v3_pass",
                "required": True,
                "current_pass": False,
                "evidence": {"report": "<fresh_case_dir>\\reference_compare.json"},
                "fix_suggestion": "After the next locked CAD rerun, require the same-name reference comparison report to pass before UI-backed acceptance.",
            },
            {
                "key": "reference_style_pass",
                "required": True,
                "current_pass": False,
                "evidence": {"report": "<fresh_case_dir>\\reference_style.json"},
                "fix_suggestion": "After the next locked CAD rerun, require the strict reference-style report to pass before UI-backed acceptance.",
            },
            {
                "key": "vision_qc_v6_pass",
                "required": True,
                "current_pass": False,
                "evidence": {"report": "<fresh_case_dir>\\vision_qc_v6.json"},
                "fix_suggestion": "After the next locked CAD rerun, require v6 visual QC to pass before final Drawing Review UI closure.",
            },
            {
                "key": "application_ui_screenshot_manual_visual_pass",
                "required": True,
                "current_pass": current_006.get("manual_visual_checklist_pass") is True,
                "evidence": {
            "latest_manual_review": current_006.get("latest_manual_review"),
            "failed_items": current_failed_items,
            "latest_manual_findings": current_006.get("latest_manual_findings"),
            "comparison_image": current_006.get("comparison_image"),
            "correction_actions": correction_actions,
        },
            "fix_suggestion": "After the next locked CAD rerun, write a PASS manual visual checklist from the application Drawing Review UI screenshot.",
        },
        ],
        "current_006_ui_verdict": {
            "status": current_006.get("status"),
            "pass": current_006.get("pass"),
            "latest_manual_review": current_006.get("latest_manual_review"),
            "source_ui_report": current_006.get("source_ui_report"),
            "source_ui_report_mode": current_006.get("source_ui_report_mode"),
            "generated_png_source_pass": current_006.get("generated_png_source_pass"),
            "application_ui_screenshot_content_check_pass": current_006.get("application_ui_screenshot_content_check_pass"),
            "failed_visual_checklist_items": current_failed_items,
            "latest_manual_visual_checklist": current_006.get("latest_manual_visual_checklist"),
            "latest_manual_visual_checklist_notes": current_006.get("latest_manual_visual_checklist_notes"),
            "latest_manual_findings": current_006.get("latest_manual_findings"),
            "correction_plan_direct_ui_findings_used_for_correction": correction_ui_failures.get("direct_ui_findings_used_for_correction") is True,
            "correction_plan_effective_failed_visual_checks": correction_effective_checks,
            "correction_actions": correction_actions,
            "latest_manual_required_correction": current_006.get("latest_manual_required_correction"),
            "ui_screenshot_files": current_006.get("ui_screenshot_files"),
            "application_ui_screenshot_paths_existing_application_ui": current_006.get(
                "application_ui_screenshot_paths_existing_application_ui"
            ),
            "comparison_image": current_006.get("comparison_image"),
            "generated_png": current_006.get("generated_png"),
            "reference_png": current_006.get("reference_png"),
        },
        "ui_defect_buckets": ui_defect_buckets,
        "offline_prerequisites": prerequisites,
        "source_signatures": {
            "cad_job_worker": cad_worker_signatures,
            "reference_intent_dimension_executor": reference_intent_executor_signatures,
            "product_evidence_gate_v4_4": product_evidence_gate_signatures,
            "generator": generator_signatures,
            "reference_compare_v4": reference_compare_signatures,
            "vision_qc_v6": vision_qc_v6_signatures,
            "application_ui_screenshot_validator": application_ui_screenshot_validator_signatures,
            "dimension_visual_validator": dimension_visual_signatures,
            "dimension_arrange_service": dimension_arrange_signatures,
            "displaydim_lifecycle_audit": lifecycle_audit_signatures,
            "staged_cad_validation_v3": staged_validation_signatures,
            "real_cad_smoke_v3": real_cad_smoke_signatures,
            "drawing_visual_review_suite": drawing_visual_review_signatures,
            "manual_visual_judgement_template_v4": manual_visual_judgement_template_signatures,
            "lb26001_correction_plan_v4_2": correction_plan_signatures,
            "apply_ui_visual_review_v4": apply_ui_review_signatures,
            "lb26001_acceptance_gate_v4_2": acceptance_gate_signatures,
            "lb26001_006_acceptance_proof_v4_2": acceptance_proof_signatures,
        },
        "reference_intent_artifacts": {
            "plan": reference_intent_plan,
            "contract": reference_intent_contract,
        },
        "ordered_next_gates": _ordered_next_gates(),
    }


def render_markdown(packet: dict[str, Any]) -> str:
    lines = [
        "# LB26001-A-04-006 v4.2 rerun packet",
        "",
        f"- Generated at: `{packet.get('generated_at')}`",
        f"- Status: `{packet.get('status')}`",
        f"- Real CAD allowed now: `{packet.get('real_cad_allowed_now')}`",
        f"- Readiness blockers: `{', '.join(packet.get('readiness_blocking_issue_keys') or []) or 'none'}`",
        f"- Offline missing prerequisites: `{', '.join(packet.get('offline_prerequisite_missing_keys') or []) or 'none'}`",
        "- This packet is not acceptance evidence; the application UI screenshot judgement remains the final gate.",
        "",
        "## Current UI Verdict",
        "",
    ]
    verdict = packet.get("current_006_ui_verdict") or {}
    lines.extend(
        [
            f"- Status: `{verdict.get('status')}`",
            f"- Latest manual review: `{verdict.get('latest_manual_review') or ''}`",
            f"- Failed visual checks: `{', '.join(verdict.get('failed_visual_checklist_items') or []) or 'none'}`",
            f"- Comparison image: `{verdict.get('comparison_image') or ''}`",
            f"- Required correction: {verdict.get('latest_manual_required_correction') or ''}",
        ]
    )
    findings = [str(item) for item in verdict.get("latest_manual_findings") or [] if str(item).strip()]
    if findings:
        lines.extend(["", "## Latest UI Findings", ""])
        for finding in findings:
            lines.append(f"- {finding}")
    lines.extend(["", "## Next Gates", ""])
    for index, gate in enumerate(packet.get("ordered_next_gates") or [], start=1):
        lines.append(f"{index}. `{gate.get('gate')}` - {gate.get('acceptance')}")
    lines.extend(["", "## Block Policy", ""])
    if packet.get("real_cad_allowed_now"):
        lines.append("006 may be run once through the locked CAD path, then must be closed through Drawing Review UI screenshots.")
    else:
        lines.append("Do not run real CAD while readiness or offline prerequisites are blocked.")
    lines.append("")
    return "\n".join(lines)


def write_rerun_packet(
    *,
    readiness_path: Path = DEFAULT_READINESS,
    requested_status_path: Path = DEFAULT_REQUESTED_STATUS,
    correction_plan_path: Path = DEFAULT_CORRECTION_PLAN,
    reference_intent_plan_path: Path = DEFAULT_REFERENCE_INTENT_PLAN,
    reference_intent_contract_path: Path = DEFAULT_REFERENCE_INTENT_CONTRACT,
    ui_defect_buckets_path: Path = DEFAULT_UI_DEFECT_BUCKETS,
    correction_plan_source_path: Path = DEFAULT_CORRECTION_PLAN_SOURCE,
    reference_intent_executor_source_path: Path = DEFAULT_REFERENCE_INTENT_EXECUTOR_SOURCE,
    product_evidence_gate_source_path: Path = DEFAULT_PRODUCT_EVIDENCE_GATE_SOURCE,
    cad_worker_source_path: Path = DEFAULT_CAD_WORKER_SOURCE,
    generator_source_path: Path = DEFAULT_GENERATOR_SOURCE,
    reference_compare_source_path: Path = DEFAULT_REFERENCE_COMPARE_SOURCE,
    vision_qc_v6_source_path: Path = DEFAULT_VISION_QC_V6_SOURCE,
    application_ui_screenshot_validator_source_path: Path = DEFAULT_APPLICATION_UI_SCREENSHOT_VALIDATOR_SOURCE,
    dimension_visual_validator_source_path: Path = DEFAULT_DIMENSION_VISUAL_VALIDATOR_SOURCE,
    dimension_arrange_source_path: Path = DEFAULT_DIMENSION_ARRANGE_SOURCE,
    lifecycle_audit_source_path: Path = DEFAULT_LIFECYCLE_AUDIT_SOURCE,
    staged_validation_source_path: Path = DEFAULT_STAGED_VALIDATION_SOURCE,
    real_cad_smoke_source_path: Path = DEFAULT_REAL_CAD_SMOKE_SOURCE,
    drawing_visual_review_suite_source_path: Path = DEFAULT_DRAWING_VISUAL_REVIEW_SUITE_SOURCE,
    manual_visual_judgement_template_source_path: Path = DEFAULT_MANUAL_VISUAL_JUDGEMENT_TEMPLATE_SOURCE,
    apply_ui_review_source_path: Path = DEFAULT_APPLY_UI_REVIEW_SOURCE,
    acceptance_gate_source_path: Path = DEFAULT_ACCEPTANCE_GATE_SOURCE,
    acceptance_proof_source_path: Path = DEFAULT_ACCEPTANCE_PROOF_SOURCE,
    out_json: Path = DEFAULT_OUT_JSON,
    out_md: Path = DEFAULT_OUT_MD,
) -> dict[str, Any]:
    packet = build_rerun_packet(
        readiness=_read_json(readiness_path),
        requested_status=_read_json(requested_status_path),
        correction_plan=_read_json(correction_plan_path),
        reference_intent_plan_path=reference_intent_plan_path,
        reference_intent_contract_path=reference_intent_contract_path,
        ui_defect_buckets_path=ui_defect_buckets_path,
        correction_plan_source_path=correction_plan_source_path,
        reference_intent_executor_source_path=reference_intent_executor_source_path,
        product_evidence_gate_source_path=product_evidence_gate_source_path,
        cad_worker_source_path=cad_worker_source_path,
        generator_source_path=generator_source_path,
        reference_compare_source_path=reference_compare_source_path,
        vision_qc_v6_source_path=vision_qc_v6_source_path,
        application_ui_screenshot_validator_source_path=application_ui_screenshot_validator_source_path,
        dimension_visual_validator_source_path=dimension_visual_validator_source_path,
        dimension_arrange_source_path=dimension_arrange_source_path,
        lifecycle_audit_source_path=lifecycle_audit_source_path,
        staged_validation_source_path=staged_validation_source_path,
        real_cad_smoke_source_path=real_cad_smoke_source_path,
        drawing_visual_review_suite_source_path=drawing_visual_review_suite_source_path,
        manual_visual_judgement_template_source_path=manual_visual_judgement_template_source_path,
        apply_ui_review_source_path=apply_ui_review_source_path,
        acceptance_gate_source_path=acceptance_gate_source_path,
        acceptance_proof_source_path=acceptance_proof_source_path,
    )
    _write_json(out_json, packet)
    _write_text(out_md, render_markdown(packet))
    return packet


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the no-COM LB26001-A-04-006 rerun packet.")
    parser.add_argument("--readiness", default=str(DEFAULT_READINESS))
    parser.add_argument("--requested-status", default=str(DEFAULT_REQUESTED_STATUS))
    parser.add_argument("--correction-plan", default=str(DEFAULT_CORRECTION_PLAN))
    parser.add_argument("--correction-plan-source", default=str(DEFAULT_CORRECTION_PLAN_SOURCE))
    parser.add_argument("--reference-intent-executor-source", default=str(DEFAULT_REFERENCE_INTENT_EXECUTOR_SOURCE))
    parser.add_argument("--product-evidence-gate-source", default=str(DEFAULT_PRODUCT_EVIDENCE_GATE_SOURCE))
    parser.add_argument("--cad-worker-source", default=str(DEFAULT_CAD_WORKER_SOURCE))
    parser.add_argument("--reference-intent-plan", default=str(DEFAULT_REFERENCE_INTENT_PLAN))
    parser.add_argument("--reference-intent-contract", default=str(DEFAULT_REFERENCE_INTENT_CONTRACT))
    parser.add_argument("--ui-defect-buckets", default=str(DEFAULT_UI_DEFECT_BUCKETS))
    parser.add_argument("--generator-source", default=str(DEFAULT_GENERATOR_SOURCE))
    parser.add_argument("--reference-compare-source", default=str(DEFAULT_REFERENCE_COMPARE_SOURCE))
    parser.add_argument(
        "--application-ui-screenshot-validator-source",
        default=str(DEFAULT_APPLICATION_UI_SCREENSHOT_VALIDATOR_SOURCE),
    )
    parser.add_argument("--dimension-arrange-source", default=str(DEFAULT_DIMENSION_ARRANGE_SOURCE))
    parser.add_argument("--lifecycle-audit-source", default=str(DEFAULT_LIFECYCLE_AUDIT_SOURCE))
    parser.add_argument("--staged-validation-source", default=str(DEFAULT_STAGED_VALIDATION_SOURCE))
    parser.add_argument("--real-cad-smoke-source", default=str(DEFAULT_REAL_CAD_SMOKE_SOURCE))
    parser.add_argument("--drawing-visual-review-source", default=str(DEFAULT_DRAWING_VISUAL_REVIEW_SUITE_SOURCE))
    parser.add_argument(
        "--manual-visual-judgement-template-source",
        default=str(DEFAULT_MANUAL_VISUAL_JUDGEMENT_TEMPLATE_SOURCE),
    )
    parser.add_argument("--apply-ui-review-source", default=str(DEFAULT_APPLY_UI_REVIEW_SOURCE))
    parser.add_argument("--acceptance-gate-source", default=str(DEFAULT_ACCEPTANCE_GATE_SOURCE))
    parser.add_argument("--acceptance-proof-source", default=str(DEFAULT_ACCEPTANCE_PROOF_SOURCE))
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    parser.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    args = parser.parse_args()

    packet = write_rerun_packet(
        readiness_path=_repo_path(args.readiness),
        requested_status_path=_repo_path(args.requested_status),
        correction_plan_path=_repo_path(args.correction_plan),
        correction_plan_source_path=_repo_path(args.correction_plan_source),
        reference_intent_executor_source_path=_repo_path(args.reference_intent_executor_source),
        product_evidence_gate_source_path=_repo_path(args.product_evidence_gate_source),
        cad_worker_source_path=_repo_path(args.cad_worker_source),
        reference_intent_plan_path=_repo_path(args.reference_intent_plan),
        reference_intent_contract_path=_repo_path(args.reference_intent_contract),
        ui_defect_buckets_path=_repo_path(args.ui_defect_buckets),
        generator_source_path=_repo_path(args.generator_source),
        reference_compare_source_path=_repo_path(args.reference_compare_source),
        application_ui_screenshot_validator_source_path=_repo_path(args.application_ui_screenshot_validator_source),
        dimension_arrange_source_path=_repo_path(args.dimension_arrange_source),
        lifecycle_audit_source_path=_repo_path(args.lifecycle_audit_source),
        staged_validation_source_path=_repo_path(args.staged_validation_source),
        real_cad_smoke_source_path=_repo_path(args.real_cad_smoke_source),
        drawing_visual_review_suite_source_path=_repo_path(args.drawing_visual_review_source),
        manual_visual_judgement_template_source_path=_repo_path(args.manual_visual_judgement_template_source),
        apply_ui_review_source_path=_repo_path(args.apply_ui_review_source),
        acceptance_gate_source_path=_repo_path(args.acceptance_gate_source),
        acceptance_proof_source_path=_repo_path(args.acceptance_proof_source),
        out_json=_repo_path(args.out_json),
        out_md=_repo_path(args.out_md),
    )
    print(
        json.dumps(
            {
                "status": packet.get("status"),
                "packet_build_ready": packet.get("packet_build_ready"),
                "real_cad_allowed_now": packet.get("real_cad_allowed_now"),
                "readiness_blocking_issue_keys": packet.get("readiness_blocking_issue_keys"),
                "offline_prerequisite_missing_keys": packet.get("offline_prerequisite_missing_keys"),
                "out_json": str(_repo_path(args.out_json)),
                "out_md": str(_repo_path(args.out_md)),
            },
            ensure_ascii=False,
        )
    )
    return 0 if packet.get("packet_build_ready") else 1


if __name__ == "__main__":
    raise SystemExit(main())
