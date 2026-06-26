from __future__ import annotations

import argparse
import json
import struct
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "sw_drawing_studio.product_evidence_gate.v4_4"
BASE = "LB26001-A-04-006"
DEPENDENT_BASES = [
    "LB26001-A-04-007",
    "LB26001-A-04-008",
    "LB26001-A-04-009",
    "LB26001-A-04-015",
    "LB26001-A-04-022",
]
REQUIRED_UI_REVIEW_SOURCE_MODE = "drawing_review_workbench_direct_host"

DEFAULT_STABILITY_GATE = REPO_ROOT / "drw_output" / "diagnostics" / "solidworks_stability_gate_v4_4.json"
DEFAULT_ENTRYPOINT_REPORT = REPO_ROOT / "drw_output" / "diagnostics" / "unguarded_solidworks_entrypoints.json"
DEFAULT_LOCK_TEST_REPORT = REPO_ROOT / "drw_output" / "diagnostics" / "solidworks_lock_test_result.json"
DEFAULT_CONFLICT_REPORT = REPO_ROOT / "drw_output" / "diagnostics" / "conflict_report.json"
DEFAULT_READINESS = REPO_ROOT / "drw_output" / "diagnostics" / "lb26001_006_regression_readiness_v4_2.json"
DEFAULT_REFERENCE_PROOF = REPO_ROOT / "drw_output" / "diagnostics" / "lb26001_006_reference_intent_proof_v4_4.json"
DEFAULT_REFERENCE_INTENT_PLAN = REPO_ROOT / "drw_output" / "reference_intent_dimension_plan_006.json"
DEFAULT_REFERENCE_INTENT_CONTRACT = REPO_ROOT / "drw_output" / "reference_intent_dimension_contract_006.json"
DEFAULT_RERUN_PACKET = REPO_ROOT / "drw_output" / "diagnostics" / "lb26001_006_rerun_packet_v4_2.json"
DEFAULT_UI_DEFECT_BUCKETS = REPO_ROOT / "drw_output" / "diagnostics" / "lb26001_006_ui_defect_buckets_v4_4.json"
DEFAULT_REGENERATION_GATE = REPO_ROOT / "drw_output" / "diagnostics" / "lb26001_006_regeneration_evidence_gate_v4_4.json"
DEFAULT_ACCEPTANCE_PROOF = REPO_ROOT / "drw_output" / "diagnostics" / "lb26001_006_acceptance_proof_v4_2.json"
DEFAULT_UI_VISUAL_REVIEW = (
    REPO_ROOT
    / "drw_output"
    / "ui_acceptance"
    / "LB26001_006_locked_real_rerun_20260625_041353_visual_review"
    / "closed_loop"
    / "ui_visual_review.json"
)
DEFAULT_REQUESTED_STATUS = REPO_ROOT / "drw_output" / "diagnostics" / "lb26001_requested_drawings_status_v4_2.json"
DEFAULT_OUT_JSON = REPO_ROOT / "drw_output" / "diagnostics" / "product_evidence_gate_v4_4.json"
DEFAULT_OUT_MD = REPO_ROOT / "drw_output" / "diagnostics" / "product_evidence_gate_v4_4.md"

DEFAULT_FINAL_ARTIFACTS = {
    "dist_exe": REPO_ROOT / "dist" / "sw_drawing_studio.exe",
    "release_log": REPO_ROOT / "release_log_v3_0.md",
    "validation_log": REPO_ROOT / "validation_log_v3_0.md",
    "ui_acceptance_report": REPO_ROOT / "ui_acceptance_report_v3_0.md",
    "exe_ui_robot_result": REPO_ROOT / "exe_ui_robot_result_v3_0.json",
    "exe_ui_text_quality_spotcheck": REPO_ROOT / "drw_output" / "diagnostics" / "exe_stability_2h_visual_spotcheck_v4_4.json",
    "cad_smoke": REPO_ROOT / "cad_smoke_v3_0.json",
    "dimension_validation_smoke": REPO_ROOT / "dimension_validation_smoke.json",
    "reference_compare_smoke": REPO_ROOT / "reference_compare_smoke.json",
    "reference_comparison_report": REPO_ROOT / "drw_output" / "reference_comparison_report_v3_0.xlsx",
    "visual_audit_report": REPO_ROOT / "drw_output" / "visual_audit_report_v3_0.xlsx",
    "visual_audit_index": REPO_ROOT / "drw_output" / "visual_audit_index.json",
    "stability_20min_mock": REPO_ROOT / "stability_20min_mock_v3_0.json",
    "stability_2h_ui": REPO_ROOT / "stability_2h_ui_v3_0.json",
}
DEFAULT_ISSUE_SCHEMA_VALIDATION = REPO_ROOT / "drw_output" / "issue_schema_validation.json"
DEFAULT_NORMALIZED_ISSUE_SCHEMA_VALIDATION = REPO_ROOT / "drw_output" / "issue_schema_validation_normalized.json"
DEFAULT_VISUAL_AUDIT_SCHEMA_GAP = REPO_ROOT / "drw_output" / "diagnostics" / "visual_audit_schema_gap_v4_4.json"
REQUIRED_ACTIVE_006_DEFECT_BUCKETS = {
    "dimension_visual_overdense",
    "dimension_lane_wrong",
    "note_missing_or_wrong",
    "titlebar_incomplete",
    "projection_view_style_mismatch",
}
REQUIRED_006_DEFECT_BUCKETS = REQUIRED_ACTIVE_006_DEFECT_BUCKETS | {"callout_missing"}
REQUIRED_CALLOUT_KEYS = {"thread_callout_m4_6h", "hole_callout_4x3_3", "surface_finish_rest_3_2"}
CALLOUT_ABSENCE_CHECK_KEYS = {"radius_callout", "chamfer_callout"}
REQUIRED_CLOSURE_EVIDENCE_KEYS = {
    "application_drawing_review_ui_screenshot",
    "manual_visual_judgement",
}
REQUIRED_REF6_PER_DRAWING_ARTIFACT_KEYS = [
    "drawing_blueprint",
    "dimension_validation",
    "reference_compare",
    "vision_qc",
    "ui_visual_review",
]
MIN_UI_SCREENSHOT_WIDTH = 1000
MIN_UI_SCREENSHOT_HEIGHT = 600


def build_product_evidence_gate(
    *,
    stability_gate_path: Path = DEFAULT_STABILITY_GATE,
    entrypoint_report_path: Path = DEFAULT_ENTRYPOINT_REPORT,
    lock_test_report_path: Path = DEFAULT_LOCK_TEST_REPORT,
    conflict_report_path: Path = DEFAULT_CONFLICT_REPORT,
    readiness_path: Path = DEFAULT_READINESS,
    reference_proof_path: Path = DEFAULT_REFERENCE_PROOF,
    reference_intent_plan_path: Path = DEFAULT_REFERENCE_INTENT_PLAN,
    reference_intent_contract_path: Path = DEFAULT_REFERENCE_INTENT_CONTRACT,
    rerun_packet_path: Path = DEFAULT_RERUN_PACKET,
    ui_defect_buckets_path: Path = DEFAULT_UI_DEFECT_BUCKETS,
    regeneration_gate_path: Path = DEFAULT_REGENERATION_GATE,
    acceptance_proof_path: Path = DEFAULT_ACCEPTANCE_PROOF,
    ui_visual_review_path: Path = DEFAULT_UI_VISUAL_REVIEW,
    requested_status_path: Path = DEFAULT_REQUESTED_STATUS,
    issue_schema_validation_path: Path = DEFAULT_ISSUE_SCHEMA_VALIDATION,
    normalized_issue_schema_validation_path: Path = DEFAULT_NORMALIZED_ISSUE_SCHEMA_VALIDATION,
    visual_audit_schema_gap_path: Path = DEFAULT_VISUAL_AUDIT_SCHEMA_GAP,
    final_artifacts: dict[str, Path] | None = None,
    out_json: Path | None = None,
    out_md: Path | None = None,
) -> dict[str, Any]:
    final_artifacts = final_artifacts or DEFAULT_FINAL_ARTIFACTS
    stability_gate = _read_json(stability_gate_path)
    entrypoint_report = _read_json(entrypoint_report_path)
    lock_test_report = _read_json(lock_test_report_path)
    conflict_report = _read_json(conflict_report_path)
    readiness = _read_json(readiness_path)
    reference_proof = _read_json(reference_proof_path)
    reference_intent_plan = _read_json(reference_intent_plan_path)
    reference_intent_contract = _read_json(reference_intent_contract_path)
    rerun_packet = _read_json(rerun_packet_path)
    ui_defect_buckets = _read_json(ui_defect_buckets_path)
    regeneration_gate = _read_json(regeneration_gate_path)
    acceptance_proof = _read_json(acceptance_proof_path)
    ui_visual_review = _read_json(ui_visual_review_path)
    requested_status = _read_json(requested_status_path)
    issue_schema_validation = _read_json(issue_schema_validation_path)
    normalized_issue_schema_validation = _read_json(normalized_issue_schema_validation_path)
    visual_audit_schema_gap = _read_json(visual_audit_schema_gap_path)
    readiness_ok = readiness.get("ready_to_start_locked_006_cad") is True and readiness.get("status") == "ready"
    idle_solidworks_prelock_ok = _idle_solidworks_prelock_ok(conflict_report, readiness, rerun_packet)
    strict_stability_ok = (
        stability_gate.get("pass") is True
        and stability_gate.get("status") == "pass"
        and not list(stability_gate.get("warning_reasons") or [])
    )
    stability_ok_for_locked_006 = strict_stability_ok or (
        idle_solidworks_prelock_ok
        and stability_gate.get("status") == "warning"
        and set(stability_gate.get("warning_reasons") or []) <= {"solidworks_conflict_monitor_warning_or_fail"}
    )
    strict_conflict_ok = conflict_report.get("level") == "OK" and _counts_all_zero(conflict_report.get("counts"))
    conflict_ok_for_locked_006 = strict_conflict_ok or idle_solidworks_prelock_ok

    checks: list[dict[str, Any]] = []
    _add_check(
        checks,
        "solidworks_stability_gate_pass",
        stability_ok_for_locked_006,
        "SolidWorks stability gate must pass with no warnings, except a single idle SolidWorks pre-lock process is allowed for the next locked 006 rerun.",
        {
            "path": str(stability_gate_path),
            "status": stability_gate.get("status"),
            "pass": stability_gate.get("pass"),
            "warning_reasons": stability_gate.get("warning_reasons") or [],
            "strict_stability_ok": strict_stability_ok,
            "idle_solidworks_prelock_allowed_for_locked_006": idle_solidworks_prelock_ok,
        },
    )
    entrypoint_summary = stability_gate.get("entrypoint_summary") or {}
    _add_check(
        checks,
        "ui_thread_direct_risk_zero",
        int(entrypoint_summary.get("unguarded_or_unknown_count") or 0) == 0
        and int(entrypoint_summary.get("ui_thread_direct_risk_count") or 0) == 0
        and int(entrypoint_summary.get("ui_thread_subprocess_call_count") or 0) == 0
        and int(entrypoint_summary.get("ui_thread_heavy_work_count") or 0) == 0
        and int(entrypoint_summary.get("ui_threadpool_worker_count") or 0) == 0
        and int(entrypoint_summary.get("service_direct_risk_count") or 0) == 0
        and int(entrypoint_summary.get("system_health_ui_thread_direct_probe_count") or 0) == 0
        and entrypoint_summary.get("system_health_probe_lock_contract_status") == "pass",
        "UI/service direct SolidWorks, probe, QThreadPool, OCR/YOLO/batch, and blocking-risk buckets must remain zero.",
        entrypoint_summary,
    )
    _add_check(
        checks,
        "solidworks_entrypoint_scan_report_pass",
        entrypoint_report.get("status") == "pass"
        and int(entrypoint_report.get("unguarded_or_unknown_count") or 0) == 0
        and int(entrypoint_report.get("ui_thread_direct_risk_count") or 0) == 0
        and int(entrypoint_report.get("ui_thread_subprocess_call_count") or 0) == 0
        and int(entrypoint_report.get("ui_thread_heavy_work_count") or 0) == 0
        and int(entrypoint_report.get("ui_threadpool_worker_count") or 0) == 0
        and int(entrypoint_report.get("service_direct_risk_count") or 0) == 0
        and int(entrypoint_report.get("system_health_ui_thread_direct_probe_count") or 0) == 0
        and entrypoint_report.get("external_addin_host_lock_contract_status") == "pass"
        and entrypoint_report.get("system_health_probe_lock_contract_status") == "pass",
        "Raw SolidWorks entrypoint scan must prove no UI/service direct COM, probe, QThreadPool, OCR/YOLO/batch, subprocess, or sleep risks.",
        _entrypoint_report_summary(entrypoint_report_path, entrypoint_report),
    )
    _add_check(
        checks,
        "solidworks_lock_test_report_pass",
        lock_test_report.get("pass") is True
        and lock_test_report.get("status") == "pass"
        and _all_lock_checks_pass(lock_test_report.get("checks")),
        "SolidWorks global-lock test report must pass every lock ownership/conflict check.",
        _lock_test_summary(lock_test_report_path, lock_test_report),
    )
    _add_check(
        checks,
        "solidworks_conflict_report_ok",
        conflict_ok_for_locked_006,
        "Current conflict report must be OK, or show exactly one idle SolidWorks process waiting for a worker-owned global lock before the 006 rerun.",
        {
            **_conflict_report_summary(conflict_report_path, conflict_report),
            "strict_conflict_ok": strict_conflict_ok,
            "idle_solidworks_prelock_allowed_for_locked_006": idle_solidworks_prelock_ok,
        },
    )
    _add_check(
        checks,
        "solidworks_readiness_for_006",
        readiness_ok,
        "Readiness must allow exactly one locked 006 CAD rerun before any real CAD action.",
        {
            "path": str(readiness_path),
            "status": readiness.get("status"),
            "ready_to_start_locked_006_cad": readiness.get("ready_to_start_locked_006_cad"),
            "blocking_issue_keys": readiness.get("blocking_issue_keys") or [],
        },
    )
    readiness_sampling_ok, readiness_sampling_details = _readiness_title_sampling_check(readiness_path, readiness)
    _add_check(
        checks,
        "solidworks_readiness_title_sampling_guard",
        readiness_sampling_ok,
        "006 readiness must include multi-sample SolidWorks title evidence and must not observe an unsaved document marker.",
        readiness_sampling_details,
    )
    rerun_packet_ready = (
        rerun_packet.get("packet_build_ready") is True
        and rerun_packet.get("base") == BASE
        and not list(rerun_packet.get("offline_prerequisite_missing_keys") or [])
        and rerun_packet.get("report_is_acceptance_evidence") is False
        and rerun_packet.get("api_only_acceptance_allowed") is False
        and rerun_packet.get("application_ui_screenshot_is_final_gate") is True
    )
    rerun_packet_state_current = bool(
        rerun_packet_ready
        and (
            (
                readiness_ok
                and rerun_packet.get("real_cad_allowed_now") is True
                and rerun_packet.get("status") == "ready_for_locked_006_rerun"
            )
            or (
                not readiness_ok
                and rerun_packet.get("real_cad_allowed_now") is False
                and rerun_packet.get("status") == "blocked_by_solidworks_readiness"
            )
        )
    )
    _add_check(
        checks,
        "lb26001_006_rerun_packet_ready",
        rerun_packet_ready,
        "006 rerun packet must have all offline defect-closure prerequisites and source signatures before a locked rerun.",
        _rerun_packet_summary(rerun_packet_path, rerun_packet),
    )
    _add_check(
        checks,
        "lb26001_006_rerun_packet_readiness_state_current",
        rerun_packet_state_current,
        "006 rerun packet readiness state must match the current readiness result before real CAD can start.",
        {
            "path": str(rerun_packet_path),
            "readiness_path": str(readiness_path),
            "readiness_ok": readiness_ok,
            "readiness_status": readiness.get("status"),
            "packet_status": rerun_packet.get("status"),
            "packet_readiness_ready": rerun_packet.get("readiness_ready"),
            "real_cad_allowed_now": rerun_packet.get("real_cad_allowed_now"),
            "expected_packet_status": "ready_for_locked_006_rerun" if readiness_ok else "blocked_by_solidworks_readiness",
        },
    )
    ui_defect_buckets_ok, ui_defect_buckets_details = _ui_defect_buckets_check(
        ui_defect_buckets_path,
        ui_defect_buckets,
        readiness,
    )
    _add_check(
        checks,
        "lb26001_006_ui_defect_buckets_ready",
        ui_defect_buckets_ok,
        "006 UI screenshot defect buckets must be current and complete before the next locked 006 rerun.",
        ui_defect_buckets_details,
    )
    _add_check(
        checks,
        "reference_intent_006_proof_pass",
        reference_proof.get("pass") is True
        and reference_proof.get("base") == BASE
        and reference_proof.get("report_is_drawing_acceptance_evidence") is False
        and reference_proof.get("api_only_acceptance_allowed") is False,
        "006 reference-intent plan proof must pass while remaining supporting evidence only.",
        {
            "path": str(reference_proof_path),
            "status": reference_proof.get("status"),
            "pass": reference_proof.get("pass"),
            "base": reference_proof.get("base"),
            "dimension_count": (reference_proof.get("dimension_summary") or {}).get("count"),
        },
    )
    plan_ok, plan_details = _reference_intent_plan_check(reference_intent_plan_path, reference_intent_plan)
    _add_check(
        checks,
        "reference_intent_006_plan_complete",
        plan_ok,
        "006 reference-intent dimension plan must directly define the required manufacturing DisplayDim targets and callout policy.",
        plan_details,
    )
    contract_ok, contract_details = _reference_intent_contract_check(
        reference_intent_contract_path,
        reference_intent_contract,
        reference_intent_plan,
        plan_details,
    )
    _add_check(
        checks,
        "reference_intent_006_contract_locked_worker_only",
        contract_ok,
        "006 reference-intent execution contract must require SolidWorks global lock, forbid UI-thread execution, and mirror the plan operation-by-operation.",
        contract_details,
    )
    _add_check(
        checks,
        "regeneration_006_fresh_evidence_pass",
        _regeneration_gate_pass(regeneration_gate),
        "006 must have a fresh run evidence gate PASS before UI screenshot review can close acceptance.",
        _regeneration_gate_summary(regeneration_gate_path, regeneration_gate),
    )
    ui_closure = acceptance_proof.get("ui_closure_evidence") or {}
    _add_check(
        checks,
        "application_ui_006_acceptance_pass",
        acceptance_proof.get("pass") is True
        and acceptance_proof.get("base") == BASE
        and acceptance_proof.get("application_ui_screenshot_is_final_gate") is True
        and ui_closure.get("direct_ui_screenshot_recheck_method_ok") is True
        and ui_closure.get("direct_ui_screenshot_recheck_pass") is True
        and ui_closure.get("manual_visual_checklist_pass") is True,
        "006 must pass the application Drawing Review UI screenshot and manual visual checklist.",
        {
            "path": str(acceptance_proof_path),
            "status": acceptance_proof.get("status"),
            "pass": acceptance_proof.get("pass"),
            "blocking_issue_keys": acceptance_proof.get("blocking_issue_keys") or [],
            "manual_visual_checklist_failed_items": ui_closure.get("manual_visual_checklist_failed_items") or [],
        },
    )
    _add_check(
        checks,
        "canonical_006_ui_visual_review_pass",
        _canonical_ui_visual_review_pass(ui_visual_review),
        "006 canonical ui_visual_review.json must pass using application Drawing Review UI screenshot evidence.",
        _ui_visual_review_summary(ui_visual_review_path, ui_visual_review),
    )
    requested_ref6_ok, requested_ref6_details = _requested_ref6_status_check(
        requested_status_path,
        requested_status,
    )
    _add_check(
        checks,
        "requested_ref6_ui_status_pass",
        requested_ref6_ok,
        "All six requested reference samples must have application UI screenshot PASS plus per-drawing DrawingBlueprint, dimension, reference, vision, and UI visual-review evidence.",
        requested_ref6_details,
    )

    final_artifact_evidence = _final_artifact_evidence(final_artifacts)
    exe_ui_robot_result = _read_json(final_artifacts.get("exe_ui_robot_result", Path()))
    exe_ui_text_quality_spotcheck = _read_json(final_artifacts.get("exe_ui_text_quality_spotcheck", Path()))
    cad_smoke = _read_json(final_artifacts.get("cad_smoke", Path()))
    dimension_validation_smoke = _read_json(final_artifacts.get("dimension_validation_smoke", Path()))
    reference_compare_smoke = _read_json(final_artifacts.get("reference_compare_smoke", Path()))
    stability_20min_mock = _read_json(final_artifacts.get("stability_20min_mock", Path()))
    stability_2h_ui = _read_json(final_artifacts.get("stability_2h_ui", Path()))
    visual_audit_index = _read_json(final_artifacts.get("visual_audit_index", Path()))
    exe_ui_evidence_ok, exe_ui_evidence_details = _exe_ui_evidence_contract(
        final_artifacts,
        final_artifact_evidence,
        exe_ui_robot_result,
        stability_20min_mock,
        stability_2h_ui,
        exe_ui_text_quality_spotcheck,
    )
    _add_check(
        checks,
        "final_release_artifacts_present",
        all(item.get("exists") and int(item.get("size_bytes") or 0) > 0 for item in final_artifact_evidence.values()),
        "Final release artifacts must exist before release/full_129 completion can be claimed.",
        final_artifact_evidence,
    )
    _add_check(
        checks,
        "exe_ui_and_stability_proof_pass",
        bool((final_artifact_evidence.get("dist_exe") or {}).get("exists"))
        and _pass_flag(exe_ui_robot_result)
        and _mode_has_any(exe_ui_robot_result, ["exe", "windows"])
        and _pass_flag(stability_20min_mock)
        and _duration_at_least(stability_20min_mock, 1200.0)
        and _pass_flag(stability_2h_ui)
        and _duration_at_least(stability_2h_ui, 7200.0)
        and _mode_has_any(stability_2h_ui, ["exe", "windows"])
        and _pass_flag(exe_ui_text_quality_spotcheck)
        and exe_ui_text_quality_spotcheck.get("ui_text_quality_pass") is True
        and exe_ui_text_quality_spotcheck.get("stability_json_pass") is True
        and exe_ui_evidence_ok,
        (
            "Final EXE/UI evidence must include dist/sw_drawing_studio.exe, EXE-level UI robot PASS, "
            "20-minute mock stability PASS, 2-hour Windows EXE UI stability PASS, and readable Chinese UI text "
            "spot-check PASS."
        ),
        {
            "dist_exe": final_artifact_evidence.get("dist_exe") or {},
            "exe_ui_robot_result": _ui_stability_summary(final_artifacts.get("exe_ui_robot_result", Path()), exe_ui_robot_result),
            "stability_20min_mock": _ui_stability_summary(final_artifacts.get("stability_20min_mock", Path()), stability_20min_mock),
            "stability_2h_ui": _ui_stability_summary(final_artifacts.get("stability_2h_ui", Path()), stability_2h_ui),
            "exe_ui_text_quality_spotcheck": _exe_ui_text_quality_summary(
                final_artifacts.get("exe_ui_text_quality_spotcheck", Path()),
                exe_ui_text_quality_spotcheck,
            ),
            "exe_ui_evidence_contract": exe_ui_evidence_details,
        },
    )
    _add_check(
        checks,
        "cad_smoke_dimension_reference_proof_pass",
        _cad_smoke_semantic_pass(cad_smoke)
        and _dimension_validation_smoke_semantic_pass(dimension_validation_smoke)
        and _reference_compare_smoke_semantic_pass(reference_compare_smoke),
        (
            "Final CAD/dimension/reference smoke evidence must be semantic PASS: fresh CAD output through "
            "JobRuntimeFacade/qprocess, true DisplayDim validation, and reference comparison proof."
        ),
        {
            "cad_smoke": _cad_smoke_summary(final_artifacts.get("cad_smoke", Path()), cad_smoke),
            "dimension_validation_smoke": _dimension_validation_smoke_summary(
                final_artifacts.get("dimension_validation_smoke", Path()),
                dimension_validation_smoke,
            ),
            "reference_compare_smoke": _reference_compare_smoke_summary(
                final_artifacts.get("reference_compare_smoke", Path()),
                reference_compare_smoke,
            ),
        },
    )
    visual_audit_report = final_artifact_evidence.get("visual_audit_report") or {}
    visual_audit_index_evidence = final_artifact_evidence.get("visual_audit_index") or {}
    visual_audit_schema_gap_counter_ok, visual_audit_schema_gap_counter_details = (
        _visual_audit_schema_gap_counter_contract(visual_audit_schema_gap)
    )
    visual_audit_schema_gap_source_ok, visual_audit_schema_gap_source_details = (
        _visual_audit_schema_gap_source_agreement(
            visual_audit_schema_gap,
            issue_schema_validation,
            normalized_issue_schema_validation,
            issue_schema_validation_path,
            normalized_issue_schema_validation_path,
        )
    )
    visual_audit_index_ok, visual_audit_index_details = _visual_audit_index_contract(
        visual_audit_schema_gap,
        final_artifacts.get("visual_audit_index", Path()),
        visual_audit_index_evidence,
        visual_audit_index,
    )
    visual_audit_backfill_overlay_ok, visual_audit_backfill_overlay_details = (
        _visual_audit_backfill_overlay_contract(visual_audit_schema_gap, issue_schema_validation)
    )
    visual_audit_repair_plan_ok, visual_audit_repair_plan_details = _visual_audit_repair_plan_contract(
        visual_audit_schema_gap,
        issue_schema_validation,
    )
    visual_audit_report_freshness_ok, visual_audit_report_freshness_details = (
        _visual_audit_report_freshness_contract(
            final_artifacts.get("visual_audit_report", Path()),
            visual_audit_report,
            final_artifacts.get("visual_audit_index", Path()),
            visual_audit_index,
            issue_schema_validation_path,
            issue_schema_validation,
            normalized_issue_schema_validation_path,
            normalized_issue_schema_validation,
            visual_audit_schema_gap_path,
            visual_audit_schema_gap,
        )
    )
    _add_check(
        checks,
        "visual_audit_schema_proof_pass",
        (
            bool(visual_audit_report.get("exists"))
            and issue_schema_validation.get("pass") is True
            and int(issue_schema_validation.get("noncompliant_issue_count") or 0) == 0
            and normalized_issue_schema_validation.get("pass") is True
            and int(normalized_issue_schema_validation.get("noncompliant_issue_count") or 0) == 0
            and visual_audit_schema_gap.get("pass") is True
            and visual_audit_schema_gap_counter_ok
            and visual_audit_schema_gap_source_ok
            and visual_audit_index_ok
            and visual_audit_backfill_overlay_ok
            and visual_audit_repair_plan_ok
            and visual_audit_report_freshness_ok
            and visual_audit_schema_gap.get("normalized_supporting_only") is True
            and visual_audit_schema_gap.get("normalized_cannot_replace_raw") is True
        ),
        (
            "Final Visual Audit must have visual_audit_report_v3_0.xlsx plus raw and normalized issue schema "
            "proof plus the v4.4 schema-gap diagnostic; normalized proof alone does not replace raw historical "
            "issue compliance."
        ),
        {
            "visual_audit_report": visual_audit_report,
            "issue_schema_validation": {
                "path": str(issue_schema_validation_path),
                "status": issue_schema_validation.get("status"),
                "pass": issue_schema_validation.get("pass"),
                "issue_count": issue_schema_validation.get("issue_count"),
                "noncompliant_issue_count": issue_schema_validation.get("noncompliant_issue_count"),
                "failure_bucket": issue_schema_validation.get("failure_bucket") or [],
            },
            "normalized_issue_schema_validation": {
                "path": str(normalized_issue_schema_validation_path),
                "status": normalized_issue_schema_validation.get("status"),
                "pass": normalized_issue_schema_validation.get("pass"),
                "issue_count": normalized_issue_schema_validation.get("issue_count"),
                "noncompliant_issue_count": normalized_issue_schema_validation.get("noncompliant_issue_count"),
                "failure_bucket": normalized_issue_schema_validation.get("failure_bucket") or [],
            },
            "visual_audit_schema_gap": {
                "path": str(visual_audit_schema_gap_path),
                "status": visual_audit_schema_gap.get("status"),
                "pass": visual_audit_schema_gap.get("pass"),
                "check_count": visual_audit_schema_gap.get("check_count"),
                "passed_check_count": visual_audit_schema_gap.get("passed_check_count"),
                "failed_check_count": visual_audit_schema_gap.get("failed_check_count"),
                "counter_contract": visual_audit_schema_gap_counter_details,
                "source_agreement": visual_audit_schema_gap_source_details,
                "visual_audit_index_contract": visual_audit_index_details,
                "backfill_overlay_contract": visual_audit_backfill_overlay_details,
                "repair_plan_contract": visual_audit_repair_plan_details,
                "visual_audit_report_freshness_contract": visual_audit_report_freshness_details,
                "raw_noncompliant_issue_count": visual_audit_schema_gap.get("raw_noncompliant_issue_count"),
                "normalized_noncompliant_issue_count": visual_audit_schema_gap.get("normalized_noncompliant_issue_count"),
                "visual_audit_report_final_present": visual_audit_schema_gap.get("visual_audit_report_final_present"),
                "visual_audit_full_scope_allowed_now": visual_audit_schema_gap.get("visual_audit_full_scope_allowed_now"),
                "normalized_supporting_only": visual_audit_schema_gap.get("normalized_supporting_only"),
                "normalized_cannot_replace_raw": visual_audit_schema_gap.get("normalized_cannot_replace_raw"),
                "raw_issue_backfill_overlay_present": visual_audit_schema_gap.get("raw_issue_backfill_overlay_present"),
                "raw_issue_backfill_overlay_ready": visual_audit_schema_gap.get("raw_issue_backfill_overlay_ready"),
                "raw_issue_backfill_overlay_cannot_replace_raw": visual_audit_schema_gap.get(
                    "raw_issue_backfill_overlay_cannot_replace_raw"
                ),
                "raw_issue_backfill_overlay_summary": visual_audit_schema_gap.get(
                    "raw_issue_backfill_overlay_summary"
                ) or {},
                "raw_issue_repair_plan_present": visual_audit_schema_gap.get("raw_issue_repair_plan_present"),
                "raw_issue_repair_plan_ready": visual_audit_schema_gap.get("raw_issue_repair_plan_ready"),
                "raw_issue_repair_plan_cannot_replace_raw": visual_audit_schema_gap.get(
                    "raw_issue_repair_plan_cannot_replace_raw"
                ),
                "raw_issue_repair_plan_summary": visual_audit_schema_gap.get(
                    "raw_issue_repair_plan_summary"
                ) or {},
                "blocking_issue_keys": visual_audit_schema_gap.get("blocking_issue_keys") or [],
            },
            "normalized_proof_is_supporting_only": True,
        },
    )

    failed = [item for item in checks if item["status"] != "pass"]
    passed_count = sum(1 for item in checks if item.get("pass") is True)
    failed_count = sum(1 for item in checks if item.get("pass") is False)
    status = _status_from_checks(checks)
    allowed_actions = _allowed_actions(
        stability_ok=(
            _check_pass(checks, "solidworks_stability_gate_pass")
            and _check_pass(checks, "ui_thread_direct_risk_zero")
            and _check_pass(checks, "solidworks_entrypoint_scan_report_pass")
            and _check_pass(checks, "solidworks_lock_test_report_pass")
            and _check_pass(checks, "solidworks_conflict_report_ok")
        ),
        readiness_ok=(
            _check_pass(checks, "solidworks_readiness_for_006")
            and _check_pass(checks, "solidworks_readiness_title_sampling_guard")
        ),
        reference_ok=_check_pass(checks, "reference_intent_006_proof_pass"),
        reference_plan_ok=(
            _check_pass(checks, "reference_intent_006_plan_complete")
            and _check_pass(checks, "reference_intent_006_contract_locked_worker_only")
        ),
        rerun_packet_ok=(
            _check_pass(checks, "lb26001_006_rerun_packet_ready")
            and _check_pass(checks, "lb26001_006_rerun_packet_readiness_state_current")
            and _check_pass(checks, "lb26001_006_ui_defect_buckets_ready")
        ),
        regeneration_ok=_check_pass(checks, "regeneration_006_fresh_evidence_pass"),
        acceptance_ok=(
            _check_pass(checks, "application_ui_006_acceptance_pass")
            and _check_pass(checks, "canonical_006_ui_visual_review_pass")
        ),
        requested_ok=_check_pass(checks, "requested_ref6_ui_status_pass"),
        final_artifacts_ok=_check_pass(checks, "final_release_artifacts_present"),
        exe_ui_stability_ok=_check_pass(checks, "exe_ui_and_stability_proof_pass"),
        cad_smoke_reference_ok=_check_pass(checks, "cad_smoke_dimension_reference_proof_pass"),
        visual_audit_schema_ok=_check_pass(checks, "visual_audit_schema_proof_pass"),
    )
    payload = {
        "schema": SCHEMA,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "status": status,
        "pass": not failed,
        "release_ready": bool(not failed and allowed_actions["release_allowed"]),
        "base": BASE,
        "dependent_bases": DEPENDENT_BASES,
        "api_only_acceptance_allowed": False,
        "application_ui_screenshot_is_final_gate": True,
        "do_not_run_full_129": not allowed_actions["full_129_allowed"],
        "do_not_run_LB26001_36": not allowed_actions["lb26001_36_allowed"],
        "do_not_expand_007_008_009_015_022": not allowed_actions["expand_007_008_009_015_022_allowed"],
        "allowed_actions": allowed_actions,
        "checks": checks,
        "check_count": len(checks),
        "passed_check_count": passed_count,
        "failed_check_count": failed_count,
        "blocking_issue_keys": [item["key"] for item in failed],
        "source_artifacts": {
            "stability_gate": str(stability_gate_path),
            "entrypoint_report": str(entrypoint_report_path),
            "lock_test_report": str(lock_test_report_path),
            "conflict_report": str(conflict_report_path),
            "readiness": str(readiness_path),
            "reference_proof": str(reference_proof_path),
            "reference_intent_plan": str(reference_intent_plan_path),
            "reference_intent_contract": str(reference_intent_contract_path),
            "rerun_packet": str(rerun_packet_path),
            "ui_defect_buckets": str(ui_defect_buckets_path),
            "regeneration_gate": str(regeneration_gate_path),
            "acceptance_proof": str(acceptance_proof_path),
            "ui_visual_review": str(ui_visual_review_path),
            "requested_status": str(requested_status_path),
            "issue_schema_validation": str(issue_schema_validation_path),
            "normalized_issue_schema_validation": str(normalized_issue_schema_validation_path),
            "visual_audit_schema_gap": str(visual_audit_schema_gap_path),
            "final_artifacts": {key: str(path) for key, path in final_artifacts.items()},
        },
        "next_required_action": _next_required_action(status),
    }
    if out_json is not None:
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if out_md is not None:
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text(render_markdown(payload), encoding="utf-8")
    return payload


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Product Evidence Gate v4.4",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- PASS: `{str(payload.get('pass')).lower()}`",
        f"- Release ready: `{str(payload.get('release_ready')).lower()}`",
        f"- Do not run full_129: `{str(payload.get('do_not_run_full_129')).lower()}`",
        f"- Do not run LB26001_36: `{str(payload.get('do_not_run_LB26001_36')).lower()}`",
        f"- Do not expand 007/008/009/015/022: `{str(payload.get('do_not_expand_007_008_009_015_022')).lower()}`",
        "",
        "## Allowed Actions",
        "",
    ]
    for key, value in (payload.get("allowed_actions") or {}).items():
        lines.append(f"- `{key}`: `{str(value).lower()}`")
    lines.extend(["", "## Checks", ""])
    for item in payload.get("checks") or []:
        lines.append(f"- `{item.get('status')}` `{item.get('key')}`: {item.get('message')}")
    lines.extend(["", "## Blocking Issues", ""])
    keys = payload.get("blocking_issue_keys") or []
    lines.extend([f"- `{key}`" for key in keys] or ["- None"])
    lines.extend(["", "## Next Required Action", "", str(payload.get("next_required_action") or ""), ""])
    return "\n".join(lines)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _add_check(
    checks: list[dict[str, Any]],
    key: str,
    passed: bool,
    message: str,
    details: dict[str, Any] | None = None,
) -> None:
    checks.append({
        "key": key,
        "pass": passed,
        "status": "pass" if passed else "fail",
        "message": message,
        "details": details or {},
    })


def _check_pass(checks: list[dict[str, Any]], key: str) -> bool:
    for item in checks:
        if item.get("key") == key:
            return item.get("status") == "pass"
    return False


def _status_from_checks(checks: list[dict[str, Any]]) -> str:
    if (
        not _check_pass(checks, "solidworks_stability_gate_pass")
        or not _check_pass(checks, "ui_thread_direct_risk_zero")
        or not _check_pass(checks, "solidworks_entrypoint_scan_report_pass")
        or not _check_pass(checks, "solidworks_lock_test_report_pass")
        or not _check_pass(checks, "solidworks_conflict_report_ok")
    ):
        return "blocked_by_solidworks_stability_gate"
    if not _check_pass(checks, "reference_intent_006_proof_pass"):
        return "blocked_by_006_reference_intent"
    if (
        not _check_pass(checks, "reference_intent_006_plan_complete")
        or not _check_pass(checks, "reference_intent_006_contract_locked_worker_only")
    ):
        return "blocked_by_006_reference_intent"
    if (
        not _check_pass(checks, "solidworks_readiness_for_006")
        or not _check_pass(checks, "solidworks_readiness_title_sampling_guard")
    ):
        return "blocked_by_solidworks_readiness"
    if (
        not _check_pass(checks, "lb26001_006_rerun_packet_ready")
        or not _check_pass(checks, "lb26001_006_rerun_packet_readiness_state_current")
        or not _check_pass(checks, "lb26001_006_ui_defect_buckets_ready")
    ):
        return "blocked_by_006_rerun_packet"
    if not _check_pass(checks, "regeneration_006_fresh_evidence_pass"):
        return "blocked_by_006_regeneration_evidence"
    if not _check_pass(checks, "application_ui_006_acceptance_pass") or not _check_pass(checks, "canonical_006_ui_visual_review_pass"):
        return "blocked_by_006_application_ui_review"
    if not _check_pass(checks, "requested_ref6_ui_status_pass"):
        return "blocked_by_requested_ref6_ui_review"
    if (
        not _check_pass(checks, "final_release_artifacts_present")
        or not _check_pass(checks, "exe_ui_and_stability_proof_pass")
        or not _check_pass(checks, "cad_smoke_dimension_reference_proof_pass")
        or not _check_pass(checks, "visual_audit_schema_proof_pass")
    ):
        return "warning_not_release_ready"
    return "pass"


def _allowed_actions(
    *,
    stability_ok: bool,
    readiness_ok: bool,
    reference_ok: bool,
    reference_plan_ok: bool,
    rerun_packet_ok: bool,
    regeneration_ok: bool,
    acceptance_ok: bool,
    requested_ok: bool,
    final_artifacts_ok: bool,
    exe_ui_stability_ok: bool,
    cad_smoke_reference_ok: bool,
    visual_audit_schema_ok: bool,
) -> dict[str, bool]:
    locked_006 = bool(stability_ok and readiness_ok and reference_ok and reference_plan_ok and rerun_packet_ok)
    ui_review = bool(regeneration_ok)
    expand_ref6 = bool(stability_ok and readiness_ok and regeneration_ok and acceptance_ok)
    ref6_complete = bool(requested_ok)
    lb26001_36 = bool(stability_ok and readiness_ok and reference_plan_ok and rerun_packet_ok and ref6_complete)
    full_129 = bool(
        lb26001_36
        and final_artifacts_ok
        and exe_ui_stability_ok
        and cad_smoke_reference_ok
        and visual_audit_schema_ok
    )
    return {
        "locked_006_cad_rerun_allowed_now": locked_006,
        "006_application_ui_review_allowed_now": ui_review,
        "expand_007_008_009_015_022_allowed": expand_ref6,
        "requested_ref6_complete": ref6_complete,
        "lb26001_36_allowed": lb26001_36,
        "medium_30_allowed": lb26001_36,
        "visual_audit_full_scope_allowed": lb26001_36,
        "full_129_allowed": full_129,
        "release_allowed": full_129,
    }


def _final_artifact_evidence(final_artifacts: dict[str, Path]) -> dict[str, dict[str, Any]]:
    evidence: dict[str, dict[str, Any]] = {}
    for key, path in final_artifacts.items():
        exists = path.exists() and path.is_file()
        mtime_epoch = path.stat().st_mtime if exists else None
        evidence[key] = {
            "path": str(path),
            "exists": exists,
            "size_bytes": path.stat().st_size if exists else 0,
            "mtime_epoch": mtime_epoch,
            "mtime_local": _format_epoch(mtime_epoch),
        }
    return evidence


def _entrypoint_report_summary(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": str(path),
        "schema": payload.get("schema"),
        "generated_at": payload.get("generated_at"),
        "status": payload.get("status"),
        "entrypoint_count": payload.get("entrypoint_count"),
        "unguarded_or_unknown_count": payload.get("unguarded_or_unknown_count"),
        "ui_thread_direct_risk_count": payload.get("ui_thread_direct_risk_count"),
        "ui_thread_subprocess_call_count": payload.get("ui_thread_subprocess_call_count"),
        "ui_thread_heavy_work_count": payload.get("ui_thread_heavy_work_count"),
        "ui_threadpool_worker_count": payload.get("ui_threadpool_worker_count"),
        "service_direct_risk_count": payload.get("service_direct_risk_count"),
        "system_health_ui_thread_direct_probe_count": payload.get("system_health_ui_thread_direct_probe_count"),
        "external_addin_host_lock_contract_status": payload.get("external_addin_host_lock_contract_status"),
        "system_health_probe_lock_contract_status": payload.get("system_health_probe_lock_contract_status"),
    }


def _lock_test_summary(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    checks = [item for item in payload.get("checks") or [] if isinstance(item, dict)]
    failed = [item.get("key") for item in checks if item.get("status") != "pass"]
    return {
        "path": str(path),
        "schema": payload.get("schema"),
        "generated_at": payload.get("generated_at"),
        "status": payload.get("status"),
        "pass": payload.get("pass"),
        "failure": payload.get("failure"),
        "check_count": len(checks),
        "failed_checks": failed,
    }


def _conflict_report_summary(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": str(path),
        "schema": payload.get("schema"),
        "generated_at": payload.get("generated_at"),
        "level": payload.get("level"),
        "counts": payload.get("counts") or {},
        "lock_reason": payload.get("lock_reason"),
        "fix_suggestion": payload.get("fix_suggestion"),
    }


def _readiness_title_sampling_check(path: Path, payload: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    process = payload.get("solidworks_process") if isinstance(payload.get("solidworks_process"), dict) else {}
    sample_count = int(process.get("sample_count") or 0)
    observation_count = int(process.get("observation_count") or 0)
    unsaved_title_observed = process.get("unsaved_title_observed")
    processes = [item for item in process.get("processes") or [] if isinstance(item, dict)]
    observed_titles: list[str] = []
    for item in processes:
        title = str(item.get("main_window_title") or "")
        if title:
            observed_titles.append(title)
        for extra_title in item.get("observed_titles") or []:
            extra_title = str(extra_title or "")
            if extra_title:
                observed_titles.append(extra_title)
    observed_titles = list(dict.fromkeys(observed_titles))
    missing_fields = []
    if sample_count < 5:
        missing_fields.append("solidworks_process.sample_count>=5")
    if observation_count < 1 and process.get("process_present") is not False:
        missing_fields.append("solidworks_process.observation_count>=1")
    if unsaved_title_observed is not False:
        missing_fields.append("solidworks_process.unsaved_title_observed_false")
    ok = (
        payload.get("status") == "ready"
        and payload.get("ready_to_start_locked_006_cad") is True
        and sample_count >= 5
        and observation_count >= 1
        and unsaved_title_observed is False
        and "solidworks_unsaved_document_visible" not in set(payload.get("blocking_issue_keys") or [])
    )
    return ok, {
        "path": str(path),
        "status": payload.get("status"),
        "ready_to_start_locked_006_cad": payload.get("ready_to_start_locked_006_cad"),
        "blocking_issue_keys": payload.get("blocking_issue_keys") or [],
        "sample_count": sample_count,
        "observation_count": observation_count,
        "unsaved_title_observed": unsaved_title_observed,
        "process_present": process.get("process_present"),
        "process_count": process.get("process_count"),
        "pid": process.get("pid"),
        "main_window_title": process.get("main_window_title"),
        "observed_titles": observed_titles,
        "missing_or_invalid_sampling_fields": missing_fields,
    }


def _idle_solidworks_prelock_ok(
    conflict_report: dict[str, Any],
    readiness: dict[str, Any],
    rerun_packet: dict[str, Any],
) -> bool:
    if not (
        readiness.get("status") == "ready"
        and readiness.get("ready_to_start_locked_006_cad") is True
        and rerun_packet.get("status") == "ready_for_locked_006_rerun"
        and rerun_packet.get("packet_build_ready") is True
        and rerun_packet.get("real_cad_allowed_now") is True
        and not list(rerun_packet.get("offline_prerequisite_missing_keys") or [])
    ):
        return False
    counts = conflict_report.get("counts") or {}
    if int(counts.get("solidworks_processes") or 0) != 1:
        return False
    for key in ("cad_job_workers", "batch_job_workers", "waiting_jobs", "smoke_leftovers", "dialog_guards"):
        if int(counts.get(key) or 0) != 0:
            return False
    if conflict_report.get("level") != "WARNING":
        return False
    if conflict_report.get("lock") not in (None, {}):
        return False
    owner = conflict_report.get("lock_owner") or {}
    if isinstance(owner, dict) and owner:
        return False
    if str(conflict_report.get("lock_reason") or "") != "no_active_solidworks_lock":
        return False
    findings = [item for item in conflict_report.get("findings") or [] if isinstance(item, dict)]
    keys = {str(item.get("key") or "") for item in findings}
    return "solidworks_running_without_lock" in keys


def _reference_intent_plan_check(path: Path, payload: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    dims = [item for item in payload.get("dimensions") or [] if isinstance(item, dict)]
    callouts = [item for item in payload.get("reference_callouts") or [] if isinstance(item, dict)]
    layout_policy = payload.get("reference_layout_policy") or {}
    lane_policy = payload.get("reference_dimension_lane_policy") or {}
    view_plan = payload.get("view_plan") or layout_policy.get("view_plan") or []
    layout_plan = payload.get("layout_plan") or layout_policy.get("layout_plan") or {}
    titlebar_policy = (
        payload.get("reference_titlebar_policy")
        or layout_plan.get("reference_titlebar_policy")
        or layout_policy.get("reference_titlebar_policy")
        or {}
    )
    outline_policy = (
        payload.get("reference_view_outline_policy")
        or layout_plan.get("reference_view_outline_policy")
        or layout_policy.get("reference_view_outline_policy")
        or {}
    )
    sheet_template_policy = layout_plan.get("sheet_template_policy") or {}
    view_items = [item for item in view_plan if isinstance(item, dict)]
    lane_targets = [item for item in lane_policy.get("lane_targets") or [] if isinstance(item, dict)]
    dim_keys = {str(item.get("key") or "") for item in dims}
    callout_keys = {str(item.get("key") or "") for item in callouts}
    view_slots = {str(item.get("slot") or "") for item in view_items}
    lane_target_keys = {str(item.get("target_key") or "") for item in lane_targets}
    required_dim_keys = {
        "overall_length",
        "overall_width",
        "overall_height",
        "left_end_offset",
        "right_end_offset",
        "hole_x_location",
        "hole_y_location",
        "hole_pitch",
        "hole_diameter",
        "projection_view_width",
        "projection_view_height",
        "small_feature_location",
    }
    required_callouts = {
        "thread_callout_m4_6h",
        "hole_callout_4x3_3",
        "surface_finish_rest_3_2",
        "radius_callout",
        "chamfer_callout",
    }
    required_fields = {
        "source_reference",
        "target_view",
        "expected_type",
        "is_manufacturing_dimension",
        "fallback_policy",
        "source_reference_evidence",
        "reference_value",
        "reference_value_status",
    }
    required_callout_fields = {
        "source_reference",
        "reference_png",
        "target_view",
        "expected_type",
        "is_manufacturing_dimension",
        "fallback_policy",
        "source_reference_evidence",
        "reference_value",
    }
    dim_missing_fields = {
        str(item.get("key") or f"index_{index}"): sorted(field for field in required_fields if field not in item)
        for index, item in enumerate(dims)
    }
    dim_missing_fields = {key: value for key, value in dim_missing_fields.items() if value}
    callout_missing_fields = {
        str(item.get("key") or f"index_{index}"): sorted(
            field for field in required_callout_fields if _callout_field_missing(item, field)
        )
        for index, item in enumerate(callouts)
    }
    callout_missing_fields = {key: value for key, value in callout_missing_fields.items() if value}
    note_substitution_keys = [
        str(item.get("key") or "")
        for item in dims
        if item.get("create_as") != "SolidWorks DisplayDim" or item.get("forbid_note_substitution") is not True
    ]
    generic_autodim_allowed_keys = [
        str(item.get("key") or "")
        for item in dims
        if item.get("generic_autodimension_acceptance_allowed") is not False
    ]
    dimension_evidence_contract = _dimension_evidence_contract(dims)
    callout_evidence_contract = _callout_evidence_contract(callouts)
    required_layout_slots = {"front", "top", "right", "iso"}
    missing_layout_slots = sorted(required_layout_slots - view_slots)
    layout_outline_failures = {
        str(item.get("slot") or f"index_{index}"): [
            key for key in ["center_norm", "outline_norm", "reference_view_name"]
            if (
                (key == "center_norm" and not _valid_norm_pair(item.get(key)))
                or (key == "outline_norm" and not _valid_norm_box(item.get(key)))
                or (key == "reference_view_name" and not str(item.get(key) or ""))
            )
        ]
        for index, item in enumerate(view_items)
    }
    layout_outline_failures = {key: value for key, value in layout_outline_failures.items() if value}
    missing_layout_boxes = [
        key for key in ["notes_box_norm", "titlebar_box_norm"]
        if not _valid_norm_box(layout_plan.get(key))
    ]
    titlebar_policy_failures = []
    if titlebar_policy.get("schema") != "sw_drawing_studio.reference_titlebar_policy.v4_4":
        titlebar_policy_failures.append("schema")
    for key in [
        "suppress_default_titlebar_fields",
        "suppress_drawing_no_name_visible_note",
        "render_reference_bottom_notice",
        "application_ui_screenshot_required",
    ]:
        if titlebar_policy.get(key) is not True:
            titlebar_policy_failures.append(key)
    if titlebar_policy.get("default_template_artifacts_allowed") is not False:
        titlebar_policy_failures.append("default_template_artifacts_allowed")
    if titlebar_policy.get("api_or_reference_json_alone_can_close") is not False:
        titlebar_policy_failures.append("api_or_reference_json_alone_can_close")
    if not str(titlebar_policy.get("bottom_notice_text") or "").strip():
        titlebar_policy_failures.append("bottom_notice_text")
    if not _valid_norm_box(titlebar_policy.get("bottom_notice_box_norm") or layout_plan.get("bottom_notice_box_norm")):
        titlebar_policy_failures.append("bottom_notice_box_norm")
    for key, expected in [
        ("skip_builtin_gb_frame_titleblock", True),
        ("default_template_artifacts_allowed", False),
        ("suppress_default_titlebar_fields", True),
        ("application_ui_screenshot_required", True),
    ]:
        if sheet_template_policy.get(key) is not expected:
            titlebar_policy_failures.append(f"sheet_template_policy.{key}")
    outline_policy_failures = []
    if outline_policy.get("schema") != "sw_drawing_studio.reference_view_outline_policy.v4_4":
        outline_policy_failures.append("schema")
    for key in [
        "view_outline_size_match_required",
        "independent_view_scale_allowed",
        "downscale_oversized_views_only",
        "target_outlines_required",
        "application_ui_screenshot_required",
    ]:
        if outline_policy.get(key) is not True:
            outline_policy_failures.append(key)
    if outline_policy.get("api_or_reference_json_alone_can_close") is not False:
        outline_policy_failures.append("api_or_reference_json_alone_can_close")
    try:
        outline_tolerance = float(outline_policy.get("view_outline_size_tolerance"))
    except Exception:
        outline_tolerance = 0.0
    if not (0.05 <= outline_tolerance <= 0.30):
        outline_policy_failures.append("view_outline_size_tolerance")
    missing_lane_targets = sorted(required_dim_keys - lane_target_keys)
    lane_policy_failures = []
    if lane_policy.get("schema") != "sw_drawing_studio.reference_dimension_lane_policy.v4_4":
        lane_policy_failures.append("schema")
    for key in [
        "compact_local_lanes_required",
        "reject_generic_autodim_survivors",
        "reject_far_lane",
        "reject_diagonal_or_cross_region_leaders",
        "application_ui_screenshot_required",
    ]:
        if lane_policy.get(key) is not True:
            lane_policy_failures.append(key)
    if lane_policy.get("api_or_displaydim_metric_alone_can_close") is not False:
        lane_policy_failures.append("api_or_displaydim_metric_alone_can_close")
    try:
        max_visible_display_dim_count = int(lane_policy.get("max_visible_display_dim_count"))
    except Exception:
        max_visible_display_dim_count = -1
    try:
        required_lane_issue_count_after = int(lane_policy.get("reference_lane_geometry_issue_count_after_required"))
    except Exception:
        required_lane_issue_count_after = -1
    if max_visible_display_dim_count != len(required_dim_keys):
        lane_policy_failures.append("max_visible_display_dim_count")
    if required_lane_issue_count_after != 0:
        lane_policy_failures.append("reference_lane_geometry_issue_count_after_required")
    details = {
        "path": str(path),
        "schema": payload.get("schema"),
        "generated_at": payload.get("generated_at"),
        "base": payload.get("base"),
        "status": payload.get("status"),
        "dimension_count": len(dims),
        "required_display_dim_count": payload.get("required_display_dim_count"),
        "reference_display_dim_count": payload.get("reference_display_dim_count"),
        "allow_note_substitution": payload.get("allow_note_substitution"),
        "ui_screenshot_acceptance_required": payload.get("ui_screenshot_acceptance_required"),
        "api_is_supporting_only": payload.get("api_is_supporting_only"),
        "required_callout_keys": sorted(required_callouts),
        "reference_callout_keys": sorted(callout_keys),
        "required_visual_callout_keys": sorted(REQUIRED_CALLOUT_KEYS),
        "callout_absence_check_keys": sorted(CALLOUT_ABSENCE_CHECK_KEYS),
        "missing_dimension_keys": sorted(required_dim_keys - dim_keys),
        "missing_callout_keys": sorted(required_callouts - callout_keys),
        "dimension_missing_fields": dim_missing_fields,
        "dimension_evidence_contract": dimension_evidence_contract,
        "callout_missing_fields": callout_missing_fields,
        "callout_evidence_contract": callout_evidence_contract,
        "note_substitution_keys": sorted(filter(None, note_substitution_keys)),
        "generic_autodim_allowed_keys": sorted(filter(None, generic_autodim_allowed_keys)),
        "callout_note_substitution_forbidden": _callouts_forbid_displaydim_substitution(callouts),
        "reference_layout_policy_schema": layout_policy.get("schema"),
        "required_layout_slots": sorted(required_layout_slots),
        "reference_layout_slots": sorted(view_slots),
        "missing_layout_slots": missing_layout_slots,
        "layout_outline_failures": layout_outline_failures,
        "missing_layout_boxes": missing_layout_boxes,
        "projection_view_style_match_required": layout_plan.get("projection_view_style_match_required"),
        "compact_titlebar_fields_required": layout_plan.get("compact_titlebar_fields_required"),
        "reference_style_notes_required": layout_plan.get("reference_style_notes_required"),
        "sheet_template_policy": sheet_template_policy,
        "reference_titlebar_policy_schema": titlebar_policy.get("schema"),
        "suppress_default_titlebar_fields": titlebar_policy.get("suppress_default_titlebar_fields"),
        "suppress_drawing_no_name_visible_note": titlebar_policy.get("suppress_drawing_no_name_visible_note"),
        "render_reference_bottom_notice": titlebar_policy.get("render_reference_bottom_notice"),
        "bottom_notice_box_norm": titlebar_policy.get("bottom_notice_box_norm")
        or layout_plan.get("bottom_notice_box_norm"),
        "titlebar_policy_failures": titlebar_policy_failures,
        "reference_view_outline_policy_schema": outline_policy.get("schema"),
        "view_outline_size_match_required": outline_policy.get("view_outline_size_match_required"),
        "view_outline_size_tolerance": outline_policy.get("view_outline_size_tolerance"),
        "independent_view_scale_allowed": outline_policy.get("independent_view_scale_allowed"),
        "downscale_oversized_views_only": outline_policy.get("downscale_oversized_views_only"),
        "outline_policy_failures": outline_policy_failures,
        "reference_dimension_lane_policy_schema": lane_policy.get("schema"),
        "lane_target_count": len(lane_targets),
        "lane_target_keys": sorted(lane_target_keys),
        "missing_lane_targets": missing_lane_targets,
        "lane_policy_failures": lane_policy_failures,
        "max_visible_display_dim_count": lane_policy.get("max_visible_display_dim_count"),
        "reference_lane_geometry_issue_count_after_required": lane_policy.get(
            "reference_lane_geometry_issue_count_after_required"
        ),
        "top_view_side_lane_max_gap_m": lane_policy.get("top_view_side_lane_max_gap_m"),
    }
    passed = bool(
        payload.get("schema") == "sw_drawing_studio.reference_intent_dimension_plan.v4_4"
        and payload.get("base") == BASE
        and payload.get("status") == "plan_ready_requires_cad_worker_lock"
        and len(dims) == 12
        and int(payload.get("required_display_dim_count") or 0) == 12
        and payload.get("allow_note_substitution") is False
        and payload.get("ui_screenshot_acceptance_required") is True
        and payload.get("api_is_supporting_only") is True
        and not details["missing_dimension_keys"]
        and not details["missing_callout_keys"]
        and not dim_missing_fields
        and dimension_evidence_contract.get("pass") is True
        and not callout_missing_fields
        and callout_evidence_contract.get("pass") is True
        and not note_substitution_keys
        and not generic_autodim_allowed_keys
        and details["callout_note_substitution_forbidden"] is True
        and bool(layout_policy)
        and not missing_layout_slots
        and not layout_outline_failures
        and not missing_layout_boxes
        and layout_plan.get("projection_view_style_match_required") is True
        and layout_plan.get("compact_titlebar_fields_required") is True
        and layout_plan.get("reference_style_notes_required") is True
        and not titlebar_policy_failures
        and not outline_policy_failures
        and bool(lane_policy)
        and not missing_lane_targets
        and not lane_policy_failures
    )
    return passed, details


def _reference_intent_contract_check(
    path: Path,
    payload: dict[str, Any],
    plan_payload: dict[str, Any],
    plan_details: dict[str, Any],
) -> tuple[bool, dict[str, Any]]:
    operations = [item for item in payload.get("operations") or [] if isinstance(item, dict)]
    callout_operations = [item for item in payload.get("callout_operations") or [] if isinstance(item, dict)]
    op_keys = {str(item.get("dimension_key") or "") for item in operations}
    operation_plan_alignment_contract = _operation_plan_alignment_contract(operations, plan_payload)
    callout_operation_contract = _callout_operation_contract(callout_operations, plan_payload)
    missing_from_contract = sorted(
        set(plan_details.get("missing_dimension_keys") or [])
        or (
            {
                "overall_length",
                "overall_width",
                "overall_height",
                "left_end_offset",
                "right_end_offset",
                "hole_x_location",
                "hole_y_location",
                "hole_pitch",
                "hole_diameter",
                "projection_view_width",
                "projection_view_height",
                "small_feature_location",
            }
            - op_keys
        )
    )
    operations_missing_evidence = [
        str(item.get("dimension_key") or f"index_{index}")
        for index, item in enumerate(operations)
        if not item.get("source_reference_evidence")
    ]
    non_manufacturing_ops = [
        str(item.get("dimension_key") or f"index_{index}")
        for index, item in enumerate(operations)
        if item.get("is_manufacturing_dimension") is not True
    ]
    details = {
        "path": str(path),
        "schema": payload.get("schema"),
        "generated_at": payload.get("generated_at"),
        "base": payload.get("base"),
        "status": payload.get("status"),
        "requires_solidworks_lock": payload.get("requires_solidworks_lock"),
        "ui_thread_may_execute": payload.get("ui_thread_may_execute"),
        "direct_com_called": payload.get("direct_com_called"),
        "allowed_entrypoint": payload.get("allowed_entrypoint"),
        "operation_count": payload.get("operation_count"),
        "operations_len": len(operations),
        "callout_operation_count": payload.get("callout_operation_count"),
        "callout_operations_len": len(callout_operations),
        "missing_dimension_operations": missing_from_contract,
        "operations_missing_evidence": operations_missing_evidence,
        "non_manufacturing_operations": non_manufacturing_ops,
        "operation_plan_alignment_contract": operation_plan_alignment_contract,
        "callout_operation_contract": callout_operation_contract,
    }
    passed = bool(
        payload.get("schema") == "sw_drawing_studio.reference_intent_dimension_execution_contract.v4_4"
        and payload.get("base") == BASE
        and payload.get("status") == "contract_ready_requires_cad_worker_lock"
        and payload.get("requires_solidworks_lock") is True
        and payload.get("ui_thread_may_execute") is False
        and payload.get("direct_com_called") is False
        and int(payload.get("operation_count") or 0) == 12
        and len(operations) == 12
        and not missing_from_contract
        and not operations_missing_evidence
        and not non_manufacturing_ops
        and operation_plan_alignment_contract.get("pass") is True
        and int(payload.get("callout_operation_count") or 0) == 5
        and len(callout_operations) == 5
        and callout_operation_contract.get("pass") is True
    )
    return passed, details


def _callout_operation_contract(
    callout_operations: list[dict[str, Any]],
    plan_payload: dict[str, Any],
) -> dict[str, Any]:
    plan_callouts = [item for item in plan_payload.get("reference_callouts") or [] if isinstance(item, dict)]
    plan_by_key = {str(item.get("key") or ""): item for item in plan_callouts if str(item.get("key") or "")}
    operation_keys = [str(item.get("callout_key") or "") for item in callout_operations]
    operation_keys_set = set(filter(None, operation_keys))
    duplicate_operation_keys = sorted(
        key for key in set(operation_keys) if key and operation_keys.count(key) > 1
    )
    missing_plan_callouts = sorted(set(plan_by_key) - operation_keys_set)
    extra_operation_keys = sorted(operation_keys_set - set(plan_by_key))
    missing_required_fields: dict[str, list[str]] = {}
    mismatch_by_key: dict[str, list[str]] = {}
    required_operation_fields = [
        "operation",
        "callout_key",
        "target_view",
        "expected_type",
        "source_reference",
        "reference_png",
        "source_reference_evidence",
        "create_as",
        "fallback_policy",
        "api_is_supporting_only",
        "ui_screenshot_acceptance_required",
        "requires_solidworks_lock",
        "allowed_entrypoint",
    ]
    plan_alignment_fields = [
        "target_view",
        "expected_type",
        "source_reference",
        "reference_png",
        "source_reference_evidence",
        "create_as",
        "fallback_policy",
        "is_manufacturing_dimension",
        "reference_value",
        "reference_value_status",
        "forbid_note_substitution_for_displaydim",
        "api_is_supporting_only",
        "ui_screenshot_acceptance_required",
    ]
    for index, operation in enumerate(callout_operations):
        key = str(operation.get("callout_key") or f"index_{index}")
        missing = [field for field in required_operation_fields if field not in operation]
        if missing:
            missing_required_fields[key] = missing
        mismatches: list[str] = []
        plan_item = plan_by_key.get(str(operation.get("callout_key") or ""))
        if not plan_item:
            mismatches.append("callout_key_not_in_plan")
            expected_operation = ""
        else:
            expected_operation = (
                "verify_absent_reference_callout"
                if plan_item.get("is_manufacturing_dimension") is False
                else "create_or_verify_reference_callout"
            )
            if operation.get("callout_key") != plan_item.get("key"):
                mismatches.append("callout_key")
            for field in plan_alignment_fields:
                if field in plan_item and operation.get(field) != plan_item.get(field):
                    mismatches.append(field)
        if operation.get("operation") != expected_operation:
            mismatches.append("operation")
        if operation.get("requires_solidworks_lock") is not True:
            mismatches.append("requires_solidworks_lock")
        if operation.get("allowed_entrypoint") != "cad_job_worker":
            mismatches.append("allowed_entrypoint")
        if operation.get("api_is_supporting_only") is not True:
            mismatches.append("api_is_supporting_only")
        if operation.get("ui_screenshot_acceptance_required") is not True:
            mismatches.append("ui_screenshot_acceptance_required")
        if plan_item and plan_item.get("is_manufacturing_dimension") is True:
            if not str(operation.get("reference_value") or "").strip():
                mismatches.append("reference_value")
            create_as = str(operation.get("create_as") or "")
            if "substitute DisplayDim" not in create_as and "does not count as DisplayDim" not in create_as:
                mismatches.append("create_as_displaydim_substitution_policy")
        if plan_item and plan_item.get("is_manufacturing_dimension") is False:
            evidence = operation.get("source_reference_evidence") if isinstance(operation.get("source_reference_evidence"), dict) else {}
            if operation.get("reference_value") is not None:
                mismatches.append("absence_reference_value")
            if evidence.get("extraction_method") != "manual_visual_absence_check":
                mismatches.append("absence_extraction_method")
            if str(operation.get("fallback_policy") or "") != "do_not_create_unless_geometry_or_reference_proves_feature":
                mismatches.append("absence_fallback_policy")
        if mismatches:
            mismatch_by_key[key] = sorted(set(mismatches))
    return {
        "pass": bool(
            plan_by_key
            and not duplicate_operation_keys
            and not missing_plan_callouts
            and not extra_operation_keys
            and not missing_required_fields
            and not mismatch_by_key
        ),
        "plan_callout_count": len(plan_by_key),
        "operation_count": len(callout_operations),
        "required_callout_keys": sorted(REQUIRED_CALLOUT_KEYS),
        "absence_check_keys": sorted(CALLOUT_ABSENCE_CHECK_KEYS),
        "duplicate_operation_keys": duplicate_operation_keys,
        "missing_plan_callouts": missing_plan_callouts,
        "extra_operation_keys": extra_operation_keys,
        "missing_required_fields": missing_required_fields,
        "mismatch_count": len(mismatch_by_key),
        "mismatch_by_key": mismatch_by_key,
    }


def _operation_plan_alignment_contract(
    operations: list[dict[str, Any]],
    plan_payload: dict[str, Any],
) -> dict[str, Any]:
    plan_dimensions = [item for item in plan_payload.get("dimensions") or [] if isinstance(item, dict)]
    plan_by_key = {str(item.get("key") or ""): item for item in plan_dimensions if str(item.get("key") or "")}
    operation_keys = [str(item.get("dimension_key") or "") for item in operations]
    duplicate_operation_keys = sorted(
        key for key in set(operation_keys) if key and operation_keys.count(key) > 1
    )
    operation_keys_set = set(filter(None, operation_keys))
    missing_plan_operations = sorted(set(plan_by_key) - operation_keys_set)
    extra_operation_keys = sorted(operation_keys_set - set(plan_by_key))
    missing_required_fields: dict[str, list[str]] = {}
    mismatch_by_key: dict[str, list[str]] = {}
    required_operation_fields = [
        "operation",
        "dimension_key",
        "target_view",
        "expected_type",
        "expected_add_method",
        "source_reference",
        "source_reference_evidence",
        "create_as",
        "fallback_policy",
        "forbid_note_substitution",
        "avoid_generic_model_annotation",
        "generic_autodimension_acceptance_allowed",
        "trace_required_fields",
        "acceptance_trace",
        "requires_solidworks_lock",
        "allowed_entrypoint",
        "placement_lane",
    ]
    plan_alignment_fields = [
        "target_view",
        "expected_type",
        "expected_add_method",
        "source_reference",
        "source_reference_evidence",
        "create_as",
        "fallback_policy",
        "forbid_note_substitution",
        "avoid_generic_model_annotation",
        "generic_autodimension_acceptance_allowed",
        "trace_required_fields",
        "acceptance_trace",
        "placement_lane",
        "allowed_witness_entity",
        "prune_protection_policy",
    ]
    for index, operation in enumerate(operations):
        key = str(operation.get("dimension_key") or f"index_{index}")
        missing = [field for field in required_operation_fields if field not in operation]
        if missing:
            missing_required_fields[key] = missing
        mismatches: list[str] = []
        plan_item = plan_by_key.get(str(operation.get("dimension_key") or ""))
        if not plan_item:
            mismatches.append("dimension_key_not_in_plan")
        else:
            if operation.get("dimension_key") != plan_item.get("key"):
                mismatches.append("dimension_key")
            for field in plan_alignment_fields:
                if field in plan_item and operation.get(field) != plan_item.get(field):
                    mismatches.append(field)
        if operation.get("operation") != "create_or_verify_display_dimension":
            mismatches.append("operation")
        if operation.get("create_as") != "SolidWorks DisplayDim":
            mismatches.append("create_as")
        if operation.get("forbid_note_substitution") is not True:
            mismatches.append("forbid_note_substitution")
        if operation.get("avoid_generic_model_annotation") is not True:
            mismatches.append("avoid_generic_model_annotation")
        if operation.get("generic_autodimension_acceptance_allowed") is not False:
            mismatches.append("generic_autodimension_acceptance_allowed")
        if operation.get("requires_solidworks_lock") is not True:
            mismatches.append("requires_solidworks_lock")
        if operation.get("allowed_entrypoint") != "cad_job_worker":
            mismatches.append("allowed_entrypoint")
        placement_lane = operation.get("placement_lane") or {}
        if isinstance(placement_lane, dict) and operation.get("target_view") != placement_lane.get("view_slot"):
            mismatches.append("placement_lane.view_slot")
        acceptance_trace = operation.get("acceptance_trace") or {}
        if isinstance(acceptance_trace, dict) and acceptance_trace.get("must_record_add_method") != operation.get(
            "expected_add_method"
        ):
            mismatches.append("acceptance_trace.must_record_add_method")
        if mismatches:
            mismatch_by_key[key] = sorted(set(mismatches))
    return {
        "pass": bool(
            plan_by_key
            and not duplicate_operation_keys
            and not missing_plan_operations
            and not extra_operation_keys
            and not missing_required_fields
            and not mismatch_by_key
        ),
        "plan_dimension_count": len(plan_by_key),
        "operation_count": len(operations),
        "duplicate_operation_keys": duplicate_operation_keys,
        "missing_plan_operations": missing_plan_operations,
        "extra_operation_keys": extra_operation_keys,
        "missing_required_fields": missing_required_fields,
        "mismatch_count": len(mismatch_by_key),
        "mismatch_by_key": mismatch_by_key,
    }


def _dimension_evidence_contract(dims: list[dict[str, Any]]) -> dict[str, Any]:
    mismatch_by_key: dict[str, list[str]] = {}
    for index, item in enumerate(dims):
        key = str(item.get("key") or f"index_{index}")
        evidence = item.get("source_reference_evidence") if isinstance(item.get("source_reference_evidence"), dict) else {}
        mismatches: list[str] = []
        if not evidence:
            mismatches.append("source_reference_evidence")
        if str(evidence.get("source_reference") or "") != str(item.get("source_reference") or ""):
            mismatches.append("source_reference")
        if str(evidence.get("target_view") or "") != str(item.get("target_view") or ""):
            mismatches.append("target_view")
        if str(evidence.get("expected_type") or "") != str(item.get("expected_type") or ""):
            mismatches.append("expected_type")
        if not _values_match(evidence.get("reference_value"), item.get("reference_value")):
            mismatches.append("reference_value")
        if str(evidence.get("reference_value_unit") or "") != str(item.get("reference_value_unit") or ""):
            mismatches.append("reference_value_unit")
        if str(evidence.get("reference_value_status") or "") != str(item.get("reference_value_status") or ""):
            mismatches.append("reference_value_status")
        if not (str(evidence.get("source_text") or "").strip() or str(evidence.get("visual_reading") or "").strip()):
            mismatches.append("source_text_or_visual_reading")
        if mismatches:
            mismatch_by_key[key] = sorted(set(mismatches))
    return {
        "pass": not mismatch_by_key,
        "checked_dimension_count": len(dims),
        "mismatch_count": len(mismatch_by_key),
        "mismatch_by_key": mismatch_by_key,
    }


def _callout_evidence_contract(callouts: list[dict[str, Any]]) -> dict[str, Any]:
    mismatch_by_key: dict[str, list[str]] = {}
    for index, item in enumerate(callouts):
        key = str(item.get("key") or f"index_{index}")
        evidence = item.get("source_reference_evidence") if isinstance(item.get("source_reference_evidence"), dict) else {}
        mismatches: list[str] = []
        if not evidence:
            mismatches.append("source_reference_evidence")
        if str(evidence.get("source_reference") or "") != str(item.get("source_reference") or ""):
            mismatches.append("source_reference")
        if str(evidence.get("reference_png") or "") != str(item.get("reference_png") or ""):
            mismatches.append("reference_png")
        if str(evidence.get("target_view") or "") != str(item.get("target_view") or ""):
            mismatches.append("target_view")
        if str(evidence.get("expected_type") or "") != str(item.get("expected_type") or ""):
            mismatches.append("expected_type")
        if not _values_match(evidence.get("reference_value"), item.get("reference_value")):
            mismatches.append("reference_value")
        if not str(evidence.get("visual_reading") or "").strip():
            mismatches.append("visual_reading")
        if not str(evidence.get("extraction_method") or "").strip():
            mismatches.append("extraction_method")
        if item.get("is_manufacturing_dimension") is True and not str(evidence.get("source_text") or "").strip():
            mismatches.append("source_text")
        if item.get("is_manufacturing_dimension") is False:
            if evidence.get("extraction_method") != "manual_visual_absence_check":
                mismatches.append("absence_extraction_method")
            if item.get("reference_value") is not None:
                mismatches.append("absence_reference_value")
        if mismatches:
            mismatch_by_key[key] = sorted(set(mismatches))
    return {
        "pass": not mismatch_by_key,
        "checked_callout_count": len(callouts),
        "mismatch_count": len(mismatch_by_key),
        "mismatch_by_key": mismatch_by_key,
    }


def _values_match(left: Any, right: Any) -> bool:
    if left == right:
        return True
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return abs(float(left) - float(right)) < 1e-9
    return False


def _callouts_forbid_displaydim_substitution(callouts: list[dict[str, Any]]) -> bool:
    for item in callouts:
        key = str(item.get("key") or "")
        if key in {"thread_callout_m4_6h", "hole_callout_4x3_3", "surface_finish_rest_3_2"}:
            text = str(item.get("create_as") or "")
            if "DisplayDim" in text and "not" not in text:
                return False
        if item.get("forbid_note_substitution_for_displaydim") is False:
            return False
    return True


def _callout_field_missing(item: dict[str, Any], field: str) -> bool:
    if field not in item:
        return True
    if field == "reference_value":
        return False
    if field == "is_manufacturing_dimension":
        return not isinstance(item.get(field), bool)
    return not bool(item.get(field))


def _valid_norm_pair(value: Any) -> bool:
    if not isinstance(value, list) or len(value) < 2:
        return False
    try:
        return all(0.0 <= float(item) <= 1.0 for item in value[:2])
    except Exception:
        return False


def _valid_norm_box(value: Any) -> bool:
    if not isinstance(value, list) or len(value) < 4:
        return False
    try:
        x0, y0, x1, y1 = [float(item) for item in value[:4]]
    except Exception:
        return False
    return 0.0 <= x0 < x1 <= 1.0 and 0.0 <= y0 < y1 <= 1.0


def _all_lock_checks_pass(value: Any) -> bool:
    if not isinstance(value, list) or not value:
        return False
    return all(isinstance(item, dict) and item.get("status") == "pass" for item in value)


def _counts_all_zero(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    try:
        return all(int(item or 0) == 0 for item in value.values())
    except (TypeError, ValueError):
        return False


def _rerun_packet_summary(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": str(path),
        "status": payload.get("status"),
        "base": payload.get("base"),
        "packet_build_ready": payload.get("packet_build_ready"),
        "real_cad_allowed_now": payload.get("real_cad_allowed_now"),
        "readiness_ready": payload.get("readiness_ready"),
        "readiness_status": payload.get("readiness_status"),
        "report_is_acceptance_evidence": payload.get("report_is_acceptance_evidence"),
        "api_only_acceptance_allowed": payload.get("api_only_acceptance_allowed"),
        "application_ui_screenshot_is_final_gate": payload.get("application_ui_screenshot_is_final_gate"),
        "offline_prerequisite_missing_keys": payload.get("offline_prerequisite_missing_keys") or [],
        "source_signature_summary": _source_signature_summary(payload.get("source_signatures")),
    }


def _ui_defect_buckets_check(
    path: Path,
    payload: dict[str, Any],
    readiness: dict[str, Any],
) -> tuple[bool, dict[str, Any]]:
    buckets = [item for item in payload.get("buckets") or [] if isinstance(item, dict)]
    bucket_keys = {str(item.get("key") or "") for item in buckets}
    active_buckets = {str(item.get("key") or "") for item in buckets if item.get("active") is True}
    active_blockers = {
        str(item.get("key") or "")
        for item in buckets
        if item.get("active") is True and item.get("blocks_006_acceptance") is True
    }
    missing_bucket_keys = sorted(REQUIRED_006_DEFECT_BUCKETS - bucket_keys)
    missing_active_bucket_keys = sorted(REQUIRED_ACTIVE_006_DEFECT_BUCKETS - active_buckets)
    active_without_blocker_keys = sorted(REQUIRED_ACTIVE_006_DEFECT_BUCKETS - active_blockers)
    next_check_buckets = {str(item) for item in payload.get("required_next_screenshot_check_buckets") or []}
    checklist_items = [item for item in payload.get("next_screenshot_checklist") or [] if isinstance(item, dict)]
    checklist_buckets = {str(item.get("bucket") or "") for item in checklist_items}
    missing_next_check_buckets = sorted(REQUIRED_006_DEFECT_BUCKETS - next_check_buckets)
    missing_next_checklist_buckets = sorted(REQUIRED_006_DEFECT_BUCKETS - checklist_buckets)
    callout_check = next((item for item in checklist_items if item.get("bucket") == "callout_missing"), {})
    callout_next_check_ok = (
        REQUIRED_CALLOUT_KEYS <= set(callout_check.get("required_callout_keys") or [])
        and CALLOUT_ABSENCE_CHECK_KEYS <= set(callout_check.get("absence_check_keys") or [])
    )
    closure_items = [item for item in payload.get("bucket_closure_contract") or [] if isinstance(item, dict)]
    closure_by_bucket = {str(item.get("bucket") or ""): item for item in closure_items}
    missing_closure_contract_keys = sorted(REQUIRED_006_DEFECT_BUCKETS - set(closure_by_bucket))
    incomplete_closure_contracts: dict[str, list[str]] = {}
    for bucket in sorted(REQUIRED_006_DEFECT_BUCKETS):
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
    missing_active_observation_buckets = sorted(
        REQUIRED_ACTIVE_006_DEFECT_BUCKETS - active_observation_buckets
    )
    callout_observation = next((item for item in observation_items if item.get("bucket") == "callout_missing"), {})
    callout_observation_ok = (
        callout_observation.get("next_screenshot_check_required") is True
        and callout_observation.get("api_or_displaydim_metric_alone_can_close") is False
    )
    readiness_summary = payload.get("solidworks_readiness") if isinstance(payload.get("solidworks_readiness"), dict) else {}
    ui_final_gate = payload.get("ui_final_gate") if isinstance(payload.get("ui_final_gate"), dict) else {}
    readiness_status_current = readiness.get("status") or ""
    readiness_ready_current = readiness.get("ready_to_start_locked_006_cad") is True
    readiness_synced = (
        readiness_summary.get("status") == readiness_status_current
        and (readiness_summary.get("ready_to_start_locked_006_cad") is True) == readiness_ready_current
    )
    visual_pass = ui_final_gate.get("visual_acceptance_pass") is True
    report_pass = payload.get("pass") is True and payload.get("status") == "pass"
    defect_closure_pass = bool(report_pass and visual_pass and int(payload.get("active_bucket_count") or 0) == 0)
    defect_plan_ready = bool(
        payload.get("status") in {"needs_006_fix", "blocked_by_solidworks_readiness"}
        and visual_pass is False
        and not missing_bucket_keys
        and not missing_active_bucket_keys
        and not active_without_blocker_keys
        and not missing_next_check_buckets
        and not missing_next_checklist_buckets
        and callout_next_check_ok
        and not missing_closure_contract_keys
        and not incomplete_closure_contracts
        and callout_closure_contract_ok
        and not missing_active_observation_buckets
        and callout_observation_ok
    )
    details = {
        "path": str(path),
        "schema": payload.get("schema"),
        "generated_at": payload.get("generated_at"),
        "base": payload.get("base"),
        "status": payload.get("status"),
        "pass": payload.get("pass"),
        "release_ready": payload.get("release_ready"),
        "api_only_acceptance_allowed": payload.get("api_only_acceptance_allowed"),
        "application_ui_screenshot_is_final_gate": payload.get("application_ui_screenshot_is_final_gate"),
        "ui_final_gate_review_mode": ui_final_gate.get("review_mode"),
        "ui_final_gate_visual_acceptance_pass": ui_final_gate.get("visual_acceptance_pass"),
        "ui_report_screenshot_pass": ui_final_gate.get("ui_report_screenshot_pass"),
        "ui_report_evidence_capture_pass": ui_final_gate.get("ui_report_evidence_capture_pass"),
        "readiness_synced": readiness_synced,
        "readiness_status": readiness_summary.get("status"),
        "current_readiness_status": readiness_status_current,
        "active_bucket_count": payload.get("active_bucket_count"),
        "active_buckets": sorted(active_buckets),
        "bucket_keys": sorted(bucket_keys),
        "missing_bucket_keys": missing_bucket_keys,
        "missing_active_bucket_keys": missing_active_bucket_keys,
        "active_without_blocker_keys": active_without_blocker_keys,
        "required_next_screenshot_check_buckets": sorted(next_check_buckets),
        "missing_next_check_buckets": missing_next_check_buckets,
        "missing_next_checklist_buckets": missing_next_checklist_buckets,
        "required_callout_keys": sorted(REQUIRED_CALLOUT_KEYS),
        "callout_absence_check_keys": sorted(CALLOUT_ABSENCE_CHECK_KEYS),
        "next_screenshot_required_callout_keys": list(callout_check.get("required_callout_keys") or []),
        "closure_contract_required_callout_keys": list(
            callout_closure_contract.get("required_callout_keys") or []
        ),
        "callout_next_check_ok": callout_next_check_ok,
        "bucket_closure_contract_buckets": sorted(set(closure_by_bucket)),
        "missing_bucket_closure_contract_keys": missing_closure_contract_keys,
        "incomplete_bucket_closure_contracts": incomplete_closure_contracts,
        "callout_closure_contract_ok": callout_closure_contract_ok,
        "screenshot_visual_observation_buckets": sorted(observation_buckets),
        "missing_active_screenshot_visual_observation_buckets": missing_active_observation_buckets,
        "callout_screenshot_visual_observation_ok": callout_observation_ok,
        "defect_plan_ready": defect_plan_ready,
        "defect_closure_pass": defect_closure_pass,
    }
    passed = bool(
        payload.get("schema") == "sw_drawing_studio.lb26001_006_ui_defect_buckets.v4_4"
        and payload.get("base") == BASE
        and payload.get("release_ready") is False
        and payload.get("api_only_acceptance_allowed") is False
        and payload.get("application_ui_screenshot_is_final_gate") is True
        and ui_final_gate.get("review_mode") == "application_drawing_review_ui_screenshot"
        and ui_final_gate.get("ui_report_screenshot_pass") is True
        and ui_final_gate.get("ui_report_evidence_capture_pass") is True
        and readiness_synced
        and not missing_bucket_keys
        and not missing_next_check_buckets
        and not missing_next_checklist_buckets
        and callout_next_check_ok
        and not missing_closure_contract_keys
        and not incomplete_closure_contracts
        and callout_closure_contract_ok
        and (
            defect_closure_pass
            or (not missing_active_observation_buckets and callout_observation_ok)
        )
        and (defect_plan_ready or defect_closure_pass)
    )
    return passed, details


def _regeneration_gate_pass(payload: dict[str, Any]) -> bool:
    return bool(
        payload.get("schema") == "sw_drawing_studio.lb26001_006_regeneration_evidence_gate.v4_4"
        and payload.get("pass") is True
        and payload.get("base") == BASE
        and payload.get("status") == "regeneration_evidence_pass_requires_application_ui_screenshot_review"
        and bool(payload.get("run_id"))
        and bool(payload.get("run_dir"))
        and payload.get("report_is_drawing_acceptance_evidence") is False
        and payload.get("api_only_acceptance_allowed") is False
        and payload.get("ui_screenshot_acceptance_required") is True
        and payload.get("application_drawing_review_ui_required") is True
        and payload.get("solidworks_runtime_called") is False
        and not (payload.get("blocking_issue_keys") or [])
    )


def _regeneration_gate_summary(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": str(path),
        "schema": payload.get("schema"),
        "status": payload.get("status"),
        "pass": payload.get("pass"),
        "base": payload.get("base"),
        "run_id": payload.get("run_id"),
        "run_dir": payload.get("run_dir"),
        "report_is_drawing_acceptance_evidence": payload.get("report_is_drawing_acceptance_evidence"),
        "api_only_acceptance_allowed": payload.get("api_only_acceptance_allowed"),
        "ui_screenshot_acceptance_required": payload.get("ui_screenshot_acceptance_required"),
        "application_drawing_review_ui_required": payload.get("application_drawing_review_ui_required"),
        "solidworks_runtime_called": payload.get("solidworks_runtime_called"),
        "blocking_issue_keys": payload.get("blocking_issue_keys") or [],
    }


def _source_signature_summary(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict):
        return {}
    summary: dict[str, dict[str, Any]] = {}
    for key, item in value.items():
        if not isinstance(item, dict):
            continue
        summary[str(key)] = {
            "pass": item.get("pass"),
            "missing_signatures": item.get("missing_signatures") or [],
        }
    return summary


def _requested_ref6_status_check(path: Path, payload: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    required_bases = [BASE, *DEPENDENT_BASES]
    matrix = payload.get("per_drawing_ui_review_matrix") or []
    matrix_by_base = {
        str(item.get("base") or ""): item
        for item in matrix
        if isinstance(item, dict) and str(item.get("base") or "")
    }
    missing_bases = [base for base in required_bases if base not in matrix_by_base]
    not_pass_bases: list[str] = []
    missing_artifacts: dict[str, list[str]] = {}
    invalid_screenshots: dict[str, list[dict[str, Any]]] = {}
    missing_ui_requirements: dict[str, list[str]] = {}
    api_only_bases: list[str] = []
    incomplete_checks: dict[str, list[str]] = {}
    per_base_summary: dict[str, dict[str, Any]] = {}

    for base in required_bases:
        item = matrix_by_base.get(base) or {}
        artifact_paths = item.get("required_artifacts") if isinstance(item.get("required_artifacts"), dict) else {}
        item_missing_artifacts = [
            key for key in REQUIRED_REF6_PER_DRAWING_ARTIFACT_KEYS if not _nonempty_file(artifact_paths.get(key))
        ]
        if item_missing_artifacts:
            missing_artifacts[base] = item_missing_artifacts

        screenshot_values = list(item.get("ui_screenshot_files") or [])
        if not screenshot_values:
            screenshot_values = list(item.get("application_ui_screenshot_paths_existing_application_ui") or [])
        screenshot_evidence = [_image_file_evidence(value) for value in screenshot_values]
        valid_screenshot = any(bool(entry.get("valid_ui_screenshot")) for entry in screenshot_evidence)
        if not valid_screenshot:
            invalid_screenshots[base] = screenshot_evidence or [{"failure": "missing_application_ui_screenshot"}]

        item_missing_requirements = list(item.get("missing_ui_acceptance_requirements") or [])
        if item_missing_requirements:
            missing_ui_requirements[base] = item_missing_requirements

        if item.get("api_only_acceptance_allowed") is not False:
            api_only_bases.append(base)

        failed_checks: list[str] = []
        required_booleans = {
            "application_ui_screenshot_present": item.get("application_ui_screenshot_present") is True,
            "application_ui_screenshot_content_check_pass": item.get("application_ui_screenshot_content_check_pass") is True,
            "manual_visual_judgement_present": item.get("manual_visual_judgement_present") is True,
            "manual_visual_judgement_pass": item.get("manual_visual_judgement_pass") is True,
            "manual_visual_checklist_pass": item.get("manual_visual_checklist_pass") is True,
            "ui_screenshot_review_no_solidworks_probe_pass": (
                item.get("application_ui_source_mode") == REQUIRED_UI_REVIEW_SOURCE_MODE
                and item.get("solidworks_probe_allowed_during_screenshot_review") is False
                and item.get("ui_screenshot_review_no_solidworks_probe_pass") is True
            ),
            "side_by_side_reference_generated_layout_pass": item.get(
                "side_by_side_reference_generated_layout_pass"
            ) is True,
            "ui_defect_bucket_closure_pass": (
                (base != BASE and not bool(item.get("ui_defect_bucket_closure_required")))
                or item.get("ui_defect_bucket_closure_pass") is True
            ),
            "vision_qc_v6_visual_acceptance_pass": item.get("vision_qc_v6_visual_acceptance_pass") is True,
            "reference_compare_v4_pass": item.get("reference_compare_v4_pass") is True,
            "required_artifacts_present": item.get("required_artifacts_present") is True and not item_missing_artifacts,
            "valid_application_ui_screenshot_file": valid_screenshot,
        }
        for key, ok in required_booleans.items():
            if not ok:
                failed_checks.append(key)
        if failed_checks:
            incomplete_checks[base] = failed_checks
        if item.get("pass") is not True:
            not_pass_bases.append(base)

        per_base_summary[base] = {
            "present": bool(item),
            "pass": item.get("pass"),
            "status": item.get("status"),
            "acceptance_status": item.get("acceptance_status"),
            "ui_visual_review_status": item.get("ui_visual_review_status"),
            "application_ui_screenshot_present": item.get("application_ui_screenshot_present"),
            "application_ui_screenshot_content_check_pass": item.get("application_ui_screenshot_content_check_pass"),
            "valid_application_ui_screenshot_file": valid_screenshot,
            "manual_visual_judgement_present": item.get("manual_visual_judgement_present"),
            "manual_visual_judgement_pass": item.get("manual_visual_judgement_pass"),
            "application_ui_source_mode": item.get("application_ui_source_mode"),
            "application_ui_source_mode_required": REQUIRED_UI_REVIEW_SOURCE_MODE,
            "solidworks_probe_allowed_during_screenshot_review": item.get(
                "solidworks_probe_allowed_during_screenshot_review"
            ),
            "ui_screenshot_review_no_solidworks_probe_pass": item.get(
                "ui_screenshot_review_no_solidworks_probe_pass"
            ),
            "side_by_side_reference_generated_layout_pass": item.get(
                "side_by_side_reference_generated_layout_pass"
            ),
            "ui_defect_bucket_closure_required": item.get("ui_defect_bucket_closure_required"),
            "ui_defect_bucket_closure_pass": item.get("ui_defect_bucket_closure_pass"),
            "ui_defect_bucket_missing_keys": list(item.get("ui_defect_bucket_missing_keys") or []),
            "ui_defect_bucket_failed_keys": list(item.get("ui_defect_bucket_failed_keys") or []),
            "vision_qc_v6_visual_acceptance_pass": item.get("vision_qc_v6_visual_acceptance_pass"),
            "reference_compare_v4_pass": item.get("reference_compare_v4_pass"),
            "required_artifacts_present": item.get("required_artifacts_present"),
            "missing_required_artifacts": item_missing_artifacts,
            "required_artifacts": artifact_paths,
            "missing_ui_acceptance_requirements": item_missing_requirements,
        }

    pass_gate = bool(
        payload.get("schema") == "sw_drawing_studio.lb26001_requested_drawings_status.v4_2"
        and payload.get("pass") is True
        and payload.get("pass_count") == len(required_bases)
        and payload.get("per_drawing_ui_acceptance_pass_count") == len(required_bases)
        and not missing_bases
        and not not_pass_bases
        and not missing_artifacts
        and not invalid_screenshots
        and not missing_ui_requirements
        and not api_only_bases
        and not incomplete_checks
    )
    details = {
        "path": str(path),
        "schema": payload.get("schema"),
        "status": payload.get("status"),
        "pass": payload.get("pass"),
        "pass_count": payload.get("pass_count"),
        "not_pass_count": payload.get("not_pass_count"),
        "per_drawing_ui_acceptance_pass_count": payload.get("per_drawing_ui_acceptance_pass_count"),
        "primary_acceptance_proof_status": payload.get("primary_acceptance_proof_status"),
        "required_bases": required_bases,
        "required_per_drawing_artifact_keys": list(REQUIRED_REF6_PER_DRAWING_ARTIFACT_KEYS),
        "missing_bases": missing_bases,
        "not_pass_bases": not_pass_bases,
        "missing_required_artifacts_by_base": missing_artifacts,
        "invalid_application_ui_screenshots_by_base": invalid_screenshots,
        "missing_ui_acceptance_requirements_by_base": missing_ui_requirements,
        "api_only_acceptance_allowed_bases": api_only_bases,
        "incomplete_required_checks_by_base": incomplete_checks,
        "per_base_summary": per_base_summary,
    }
    return pass_gate, details


def _canonical_ui_visual_review_pass(payload: dict[str, Any]) -> bool:
    entries = [item for item in payload.get("entries") or [] if isinstance(item, dict)]
    base_entry = next((item for item in entries if item.get("base") == BASE), {})
    screenshot_evidence = _image_file_evidence(base_entry.get("application_ui_screenshot"))
    checks = base_entry.get("checks") or {}
    return bool(
        payload.get("pass") is True
        and payload.get("status") == "pass"
        and payload.get("application_ui_screenshot_is_final_gate") is True
        and payload.get("application_ui_source_mode") == REQUIRED_UI_REVIEW_SOURCE_MODE
        and payload.get("solidworks_probe_allowed_during_screenshot_review") is False
        and payload.get("ui_screenshot_review_no_solidworks_probe_all_pass") is True
        and payload.get("api_only_acceptance_allowed") is False
        and payload.get("review_method") == "application_drawing_review_ui_screenshot"
        and base_entry.get("pass") is True
        and base_entry.get("visual_acceptance_pass") is True
        and base_entry.get("application_ui_source_mode") == REQUIRED_UI_REVIEW_SOURCE_MODE
        and base_entry.get("solidworks_probe_allowed_during_screenshot_review") is False
        and screenshot_evidence["valid_ui_screenshot"]
        and checks.get("ui_report_entry_pass") is True
        and checks.get("ui_screenshot_review_no_solidworks_probe_pass") is True
        and checks.get("manual_review_entry_screenshot_pass") is True
        and checks.get("side_by_side_reference_generated_layout_pass") is True
        and checks.get("ui_defect_bucket_closure_pass") is True
        and checks.get("vision_qc_v6_visual_acceptance_pass") is True
        and checks.get("reference_compare_v4_pass") is True
    )


def _ui_visual_review_summary(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    entries = [item for item in payload.get("entries") or [] if isinstance(item, dict)]
    base_entry = next((item for item in entries if item.get("base") == BASE), {})
    screenshot = base_entry.get("application_ui_screenshot")
    screenshot_evidence = _image_file_evidence(screenshot)
    return {
        "path": str(path),
        "status": payload.get("status"),
        "pass": payload.get("pass"),
        "visual_acceptance_pass": payload.get("visual_acceptance_pass"),
        "review_method": payload.get("review_method"),
        "application_ui_screenshot_is_final_gate": payload.get("application_ui_screenshot_is_final_gate"),
        "application_ui_source_mode": payload.get("application_ui_source_mode"),
        "application_ui_source_mode_required": REQUIRED_UI_REVIEW_SOURCE_MODE,
        "solidworks_probe_allowed_during_screenshot_review": payload.get(
            "solidworks_probe_allowed_during_screenshot_review"
        ),
        "ui_screenshot_review_no_solidworks_probe_all_pass": payload.get(
            "ui_screenshot_review_no_solidworks_probe_all_pass"
        ),
        "api_only_acceptance_allowed": payload.get("api_only_acceptance_allowed"),
        "pass_count": payload.get("pass_count"),
        "fail_count": payload.get("fail_count"),
        "blocking_issue_keys": payload.get("blocking_issue_keys") or [],
        "base_entry": {
            "present": bool(base_entry),
            "base": base_entry.get("base"),
            "status": base_entry.get("status"),
            "pass": base_entry.get("pass"),
            "visual_acceptance_pass": base_entry.get("visual_acceptance_pass"),
            "application_ui_screenshot": screenshot,
            "application_ui_source_mode": base_entry.get("application_ui_source_mode"),
            "solidworks_probe_allowed_during_screenshot_review": base_entry.get(
                "solidworks_probe_allowed_during_screenshot_review"
            ),
            "application_ui_screenshot_exists": screenshot_evidence["exists"],
            "application_ui_screenshot_size_bytes": screenshot_evidence["size_bytes"],
            "application_ui_screenshot_decode_pass": screenshot_evidence["decode_pass"],
            "application_ui_screenshot_width": screenshot_evidence["width"],
            "application_ui_screenshot_height": screenshot_evidence["height"],
            "application_ui_screenshot_min_dimensions_pass": screenshot_evidence["min_dimensions_pass"],
            "application_ui_screenshot_valid": screenshot_evidence["valid_ui_screenshot"],
            "application_ui_screenshot_failure": screenshot_evidence["failure"],
            "side_by_side_reference_generated_layout": base_entry.get(
                "side_by_side_reference_generated_layout"
            ) or {},
            "blocking_issue_keys": base_entry.get("blocking_issue_keys") or [],
            "checks": base_entry.get("checks") or {},
        },
    }


def _image_file_evidence(value: Any) -> dict[str, Any]:
    path = _resolve_path(value)
    evidence = {
        "path": str(path or value or ""),
        "exists": False,
        "size_bytes": 0,
        "decode_pass": False,
        "width": None,
        "height": None,
        "min_width": MIN_UI_SCREENSHOT_WIDTH,
        "min_height": MIN_UI_SCREENSHOT_HEIGHT,
        "min_dimensions_pass": False,
        "valid_ui_screenshot": False,
        "failure": "",
    }
    if path is None:
        evidence["failure"] = "missing_path"
        return evidence
    try:
        evidence["exists"] = path.exists() and path.is_file()
        if not evidence["exists"]:
            evidence["failure"] = "file_missing"
            return evidence
        evidence["size_bytes"] = path.stat().st_size
        if evidence["size_bytes"] <= 0:
            evidence["failure"] = "empty_file"
            return evidence
        width, height = _read_image_dimensions(path)
        evidence["decode_pass"] = bool(width and height)
        evidence["width"] = width
        evidence["height"] = height
        evidence["min_dimensions_pass"] = bool(
            width is not None
            and height is not None
            and width >= MIN_UI_SCREENSHOT_WIDTH
            and height >= MIN_UI_SCREENSHOT_HEIGHT
        )
        evidence["valid_ui_screenshot"] = bool(evidence["decode_pass"] and evidence["min_dimensions_pass"])
        if not evidence["decode_pass"]:
            evidence["failure"] = "image_decode_failed"
        elif not evidence["min_dimensions_pass"]:
            evidence["failure"] = "image_too_small"
    except Exception as exc:
        evidence["failure"] = f"{type(exc).__name__}: {exc}"
    return evidence


def _read_image_dimensions(path: Path) -> tuple[int | None, int | None]:
    try:
        with path.open("rb") as handle:
            header = handle.read(32)
        if header.startswith(b"\x89PNG\r\n\x1a\n") and header[12:16] == b"IHDR":
            width, height = struct.unpack(">II", header[16:24])
            return int(width), int(height)
    except Exception:
        pass
    try:
        from PIL import Image

        with Image.open(path) as image:
            width, height = image.size
        return int(width), int(height)
    except Exception:
        return None, None


def _resolve_path(value: Any) -> Path | None:
    if not value:
        return None
    path = Path(str(value))
    if not path.is_absolute():
        path = (REPO_ROOT / path).resolve()
    return path


def _nonempty_file(value: Any) -> bool:
    try:
        path = _resolve_path(value)
        if path is None:
            return False
        return path.exists() and path.is_file() and path.stat().st_size > 0
    except Exception:
        return False


def _nonempty_file_from_root(value: Any, root: Path) -> bool:
    try:
        path = _resolve_from_root(value, root)
        if path is None:
            return False
        return path.exists() and path.is_file() and path.stat().st_size > 0
    except Exception:
        return False


def _resolve_from_root(value: Any, root: Path) -> Path | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    path = Path(text)
    return path if path.is_absolute() else (root / path).resolve()


def _artifact_root_from_dist(dist_path: Path) -> Path:
    try:
        resolved = dist_path.resolve()
        if resolved.parent.name.lower() == "dist":
            return resolved.parent.parent
    except Exception:
        pass
    return REPO_ROOT


def _payload_exe_targets_dist(payload: dict[str, Any], dist_path: Path, artifact_root: Path) -> bool:
    try:
        exe_path = _resolve_from_root(payload.get("exe"), artifact_root)
        return exe_path is not None and exe_path.resolve() == dist_path.resolve()
    except Exception:
        return False


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _pass_flag(payload: dict[str, Any]) -> bool:
    return payload.get("pass") is True or str(payload.get("status") or "").lower() == "pass"


def _duration_at_least(payload: dict[str, Any], minimum_s: float) -> bool:
    duration = payload.get("duration_observed_s", payload.get("duration_s"))
    try:
        return float(duration) >= minimum_s
    except (TypeError, ValueError):
        return False


def _mode_has_any(payload: dict[str, Any], tokens: list[str]) -> bool:
    mode = str(payload.get("mode") or payload.get("source") or "").lower()
    exe = str(payload.get("exe") or "").lower()
    return any(token.lower() in mode or token.lower() in exe for token in tokens)


def _exe_ui_evidence_contract(
    final_artifacts: dict[str, Path],
    final_evidence: dict[str, dict[str, Any]],
    exe_ui_robot_result: dict[str, Any],
    stability_20min_mock: dict[str, Any],
    stability_2h_ui: dict[str, Any],
    exe_ui_text_quality_spotcheck: dict[str, Any],
) -> tuple[bool, dict[str, Any]]:
    dist_path = final_artifacts.get("dist_exe", Path())
    dist_evidence = final_evidence.get("dist_exe") or {}
    artifact_root = _artifact_root_from_dist(dist_path)
    dist_mtime = _float_or_none(dist_evidence.get("mtime_epoch"))
    evidence_mtimes = {
        key: _float_or_none((final_evidence.get(key) or {}).get("mtime_epoch"))
        for key in [
            "exe_ui_robot_result",
            "stability_20min_mock",
            "stability_2h_ui",
            "exe_ui_text_quality_spotcheck",
        ]
    }
    spotchecked_screenshot = exe_ui_text_quality_spotcheck.get("spotchecked_screenshot")
    checks = {
        "dist_exe_exists": dist_evidence.get("exists") is True,
        "dist_exe_has_content": int(dist_evidence.get("size_bytes") or 0) > 0,
        "dist_exe_mtime_present": dist_mtime is not None,
        "exe_ui_robot_result_exists": (final_evidence.get("exe_ui_robot_result") or {}).get("exists") is True,
        "stability_20min_mock_exists": (final_evidence.get("stability_20min_mock") or {}).get("exists") is True,
        "stability_2h_ui_exists": (final_evidence.get("stability_2h_ui") or {}).get("exists") is True,
        "exe_ui_text_quality_spotcheck_exists": (
            final_evidence.get("exe_ui_text_quality_spotcheck") or {}
        ).get("exists")
        is True,
        "exe_ui_robot_result_not_older_than_dist_exe": _epoch_not_older(
            evidence_mtimes["exe_ui_robot_result"],
            dist_mtime,
        ),
        "stability_20min_mock_not_older_than_dist_exe": _epoch_not_older(
            evidence_mtimes["stability_20min_mock"],
            dist_mtime,
        ),
        "stability_2h_ui_not_older_than_dist_exe": _epoch_not_older(
            evidence_mtimes["stability_2h_ui"],
            dist_mtime,
        ),
        "exe_ui_text_quality_spotcheck_not_older_than_dist_exe": _epoch_not_older(
            evidence_mtimes["exe_ui_text_quality_spotcheck"],
            dist_mtime,
        ),
        "exe_ui_robot_targets_dist_exe": _payload_exe_targets_dist(
            exe_ui_robot_result,
            dist_path,
            artifact_root,
        ),
        "stability_2h_ui_targets_dist_exe": _payload_exe_targets_dist(
            stability_2h_ui,
            dist_path,
            artifact_root,
        ),
        "text_quality_rebuild_not_required": (
            (exe_ui_text_quality_spotcheck.get("source_fix") or {}).get("rebuild_required") is False
        ),
        "text_quality_2h_rerun_not_required": (
            (exe_ui_text_quality_spotcheck.get("source_fix") or {}).get("rerun_2h_exe_stability_required") is False
        ),
        "text_quality_spotchecked_screenshot_exists": _nonempty_file_from_root(
            spotchecked_screenshot,
            artifact_root,
        ),
    }
    mismatch_keys = [key for key, value in checks.items() if value is not True]
    details = {
        "pass": not mismatch_keys,
        "dist_exe_path": str(dist_path),
        "artifact_root": str(artifact_root),
        "dist_exe_mtime_epoch": dist_mtime,
        "dist_exe_mtime_local": _format_epoch(dist_mtime),
        "evidence_mtimes": {
            key: {
                "mtime_epoch": value,
                "mtime_local": _format_epoch(value),
            }
            for key, value in evidence_mtimes.items()
        },
        "exe_ui_robot_exe": exe_ui_robot_result.get("exe"),
        "stability_2h_ui_exe": stability_2h_ui.get("exe"),
        "spotchecked_screenshot": spotchecked_screenshot,
        "rebuild_required": ((exe_ui_text_quality_spotcheck.get("source_fix") or {}).get("rebuild_required")),
        "rerun_2h_exe_stability_required": (
            (exe_ui_text_quality_spotcheck.get("source_fix") or {}).get("rerun_2h_exe_stability_required")
        ),
        **checks,
        "mismatch_keys": mismatch_keys,
    }
    return bool(details["pass"]), details


def _ui_stability_summary(path: Path | None, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": str(path or ""),
        "exists": bool(path and path.exists()),
        "mode": payload.get("mode"),
        "exe": payload.get("exe"),
        "status": payload.get("status"),
        "pass": payload.get("pass"),
        "duration_observed_s": payload.get("duration_observed_s", payload.get("duration_s")),
        "duration_requested_s": payload.get("duration_requested_s"),
    }


def _exe_ui_text_quality_summary(path: Path | None, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": str(path or ""),
        "exists": bool(path and path.exists()),
        "status": payload.get("status"),
        "pass": payload.get("pass"),
        "stability_json_pass": payload.get("stability_json_pass"),
        "ui_text_quality_pass": payload.get("ui_text_quality_pass"),
        "spotchecked_screenshot": payload.get("spotchecked_screenshot"),
        "blocking_issue_keys": payload.get("blocking_issue_keys") or [],
        "rebuild_required": ((payload.get("source_fix") or {}).get("rebuild_required")),
        "rerun_2h_exe_stability_required": ((payload.get("source_fix") or {}).get("rerun_2h_exe_stability_required")),
    }


def _cad_smoke_semantic_pass(payload: dict[str, Any]) -> bool:
    return bool(
        _pass_flag(payload)
        and _job_runtime_facade_proof(payload)
        and _qprocess_worker_proof(payload)
        and bool(payload.get("run_id"))
        and bool(payload.get("run_dir"))
        and _fresh_artifact_proof(payload)
        and _required_artifact_proof(
            payload,
            [
                "slddrw",
                "pdf",
                "dxf",
                "png",
                "manifest",
                "qc",
                "vision",
                "final_quality",
                "sw_session",
                "job_event_log",
            ],
        )
    )


def _dimension_validation_smoke_semantic_pass(payload: dict[str, Any]) -> bool:
    display_dim_count = _first_int(payload, ["true_display_dim_count", "display_dim_count", "displaydim_count"])
    note_count_keys = ["note_as_displaydim_count", "note_substitution_count", "notes_counted_as_displaydim_count"]
    note_count_proven = any(key in payload for key in note_count_keys)
    note_counts_zero = all(_first_int(payload, [key]) == 0 for key in note_count_keys if key in payload)
    bool_note_flags_clear = payload.get("note_annotations_counted_as_displaydim") is not True
    return bool(
        _pass_flag(payload)
        and display_dim_count > 0
        and note_count_proven
        and note_counts_zero
        and bool_note_flags_clear
    )


def _reference_compare_smoke_semantic_pass(payload: dict[str, Any]) -> bool:
    blocking = payload.get("blocking_issue_keys") or payload.get("failed_checks") or []
    explicit_compare_pass = (
        payload.get("reference_compare_pass") is True
        or payload.get("visual_reference_compare_pass") is True
        or payload.get("drawing_reference_compare_pass") is True
    )
    no_reference_accepted = bool(
        payload.get("accepted_no_reference_reason") is True
        and str(payload.get("no_reference_reason") or "").strip()
    )
    return bool(_pass_flag(payload) and not blocking and (explicit_compare_pass or no_reference_accepted))


def _cad_smoke_summary(path: Path | None, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": str(path or ""),
        "exists": bool(path and path.exists()),
        "status": payload.get("status"),
        "pass": payload.get("pass"),
        "mode": payload.get("mode"),
        "run_id": payload.get("run_id"),
        "run_dir": payload.get("run_dir"),
        "job_runtime_facade_proof": _job_runtime_facade_proof(payload),
        "qprocess_worker_proof": _qprocess_worker_proof(payload),
        "fresh_artifact_proof": _fresh_artifact_proof(payload),
        "required_artifact_proof": _required_artifact_proof(
            payload,
            [
                "slddrw",
                "pdf",
                "dxf",
                "png",
                "manifest",
                "qc",
                "vision",
                "final_quality",
                "sw_session",
                "job_event_log",
            ],
        ),
    }


def _dimension_validation_smoke_summary(path: Path | None, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": str(path or ""),
        "exists": bool(path and path.exists()),
        "status": payload.get("status"),
        "pass": payload.get("pass"),
        "true_display_dim_count": _first_int(payload, ["true_display_dim_count", "display_dim_count", "displaydim_count"]),
        "note_as_displaydim_count": payload.get("note_as_displaydim_count"),
        "note_substitution_count": payload.get("note_substitution_count"),
        "notes_counted_as_displaydim_count": payload.get("notes_counted_as_displaydim_count"),
        "note_annotations_counted_as_displaydim": payload.get("note_annotations_counted_as_displaydim"),
    }


def _reference_compare_smoke_summary(path: Path | None, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": str(path or ""),
        "exists": bool(path and path.exists()),
        "status": payload.get("status"),
        "pass": payload.get("pass"),
        "reference_compare_pass": payload.get("reference_compare_pass"),
        "visual_reference_compare_pass": payload.get("visual_reference_compare_pass"),
        "drawing_reference_compare_pass": payload.get("drawing_reference_compare_pass"),
        "accepted_no_reference_reason": payload.get("accepted_no_reference_reason"),
        "no_reference_reason": payload.get("no_reference_reason"),
        "blocking_issue_keys": payload.get("blocking_issue_keys") or [],
        "failed_checks": payload.get("failed_checks") or [],
    }


def _visual_audit_schema_gap_counter_contract(payload: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    required_keys = ["check_count", "passed_check_count", "failed_check_count"]
    missing_keys = [key for key in required_keys if key not in payload]
    invalid_keys: list[str] = []
    values: dict[str, int | None] = {}
    for key in required_keys:
        value = payload.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            invalid_keys.append(key)
            values[key] = None
        else:
            values[key] = value

    total_matches = False
    passed = values.get("passed_check_count")
    failed = values.get("failed_check_count")
    total = values.get("check_count")
    if total is not None and passed is not None and failed is not None:
        total_matches = total == passed + failed and total > 0
        if not total_matches:
            invalid_keys.append("check_count_total")
        if payload.get("pass") is True and failed != 0:
            invalid_keys.append("failed_check_count_for_pass")
        if payload.get("pass") is False and failed <= 0:
            invalid_keys.append("failed_check_count_for_fail")

    checks = payload.get("checks")
    checks_count = 0
    checks_count_matches = False
    check_pass_counts_match = False
    check_pass_boolean_failures: list[int] = []
    if not isinstance(checks, list) or not checks:
        invalid_keys.append("checks")
    else:
        checks_count = len(checks)
        passed_in_checks = 0
        failed_in_checks = 0
        for index, check in enumerate(checks):
            if not isinstance(check, dict) or not isinstance(check.get("pass"), bool):
                check_pass_boolean_failures.append(index)
                continue
            if check.get("pass") is True:
                passed_in_checks += 1
            else:
                failed_in_checks += 1
        checks_count_matches = total == checks_count
        check_pass_counts_match = passed == passed_in_checks and failed == failed_in_checks
        if check_pass_boolean_failures:
            invalid_keys.append("checks_pass_boolean")
        if not checks_count_matches:
            invalid_keys.append("checks_count")
        if not check_pass_counts_match:
            invalid_keys.append("checks_pass_counts")

    invalid_keys = sorted(set(invalid_keys))
    return (
        not missing_keys
        and not invalid_keys
        and total_matches
        and checks_count_matches
        and check_pass_counts_match,
        {
            "pass": (
                not missing_keys
                and not invalid_keys
                and total_matches
                and checks_count_matches
                and check_pass_counts_match
            ),
            "required_keys": required_keys,
            "missing_keys": missing_keys,
            "invalid_keys": invalid_keys,
            "check_count": values.get("check_count"),
            "passed_check_count": values.get("passed_check_count"),
            "failed_check_count": values.get("failed_check_count"),
            "total_matches": total_matches,
            "checks_present": isinstance(checks, list) and bool(checks),
            "checks_count": checks_count,
            "checks_count_matches": checks_count_matches,
            "check_pass_counts_match": check_pass_counts_match,
            "check_pass_boolean_failures": check_pass_boolean_failures,
            "stale_report_without_counters_blocked": bool(missing_keys),
        },
    )


def _visual_audit_schema_gap_source_agreement(
    gap: dict[str, Any],
    raw: dict[str, Any],
    normalized: dict[str, Any],
    raw_path: Path,
    normalized_path: Path,
) -> tuple[bool, dict[str, Any]]:
    source_artifacts = gap.get("source_artifacts") if isinstance(gap.get("source_artifacts"), dict) else {}
    raw_expected_pass = raw.get("pass") is True and _optional_int(raw.get("noncompliant_issue_count")) == 0
    normalized_expected_pass = (
        normalized.get("pass") is True and _optional_int(normalized.get("noncompliant_issue_count")) == 0
    )
    raw_expected_count = _optional_int(raw.get("noncompliant_issue_count"))
    normalized_expected_count = _optional_int(normalized.get("noncompliant_issue_count"))
    raw_gap_count = _optional_int(gap.get("raw_noncompliant_issue_count"))
    normalized_gap_count = _optional_int(gap.get("normalized_noncompliant_issue_count"))
    raw_generated_at = _parse_generated_at(raw.get("generated_at"))
    normalized_generated_at = _parse_generated_at(normalized.get("generated_at"))
    gap_generated_at = _parse_generated_at(gap.get("generated_at"))

    details = {
        "pass": False,
        "gap_generated_at": gap.get("generated_at"),
        "raw_generated_at": raw.get("generated_at"),
        "normalized_generated_at": normalized.get("generated_at"),
        "raw_source_path": source_artifacts.get("raw_issue_schema_validation", ""),
        "normalized_source_path": source_artifacts.get("normalized_issue_schema_validation", ""),
        "raw_expected_path": str(raw_path),
        "normalized_expected_path": str(normalized_path),
        "generated_at_parse_ok": bool(
            gap_generated_at is not None
            and raw_generated_at is not None
            and normalized_generated_at is not None
        ),
        "gap_generated_at_not_older_than_raw": bool(
            gap_generated_at is not None and raw_generated_at is not None and gap_generated_at >= raw_generated_at
        ),
        "gap_generated_at_not_older_than_normalized": bool(
            gap_generated_at is not None
            and normalized_generated_at is not None
            and gap_generated_at >= normalized_generated_at
        ),
        "raw_source_path_matches": _path_values_match(source_artifacts.get("raw_issue_schema_validation"), raw_path),
        "normalized_source_path_matches": _path_values_match(
            source_artifacts.get("normalized_issue_schema_validation"),
            normalized_path,
        ),
        "raw_issue_schema_pass_matches": gap.get("raw_issue_schema_pass") is raw_expected_pass,
        "normalized_issue_schema_pass_matches": gap.get("normalized_issue_schema_pass") is normalized_expected_pass,
        "raw_noncompliant_issue_count_matches": raw_gap_count == raw_expected_count,
        "normalized_noncompliant_issue_count_matches": normalized_gap_count == normalized_expected_count,
        "raw_expected_pass": raw_expected_pass,
        "normalized_expected_pass": normalized_expected_pass,
        "raw_gap_pass": gap.get("raw_issue_schema_pass"),
        "normalized_gap_pass": gap.get("normalized_issue_schema_pass"),
        "raw_expected_noncompliant_issue_count": raw_expected_count,
        "normalized_expected_noncompliant_issue_count": normalized_expected_count,
        "raw_gap_noncompliant_issue_count": raw_gap_count,
        "normalized_gap_noncompliant_issue_count": normalized_gap_count,
        "mismatch_keys": [],
    }
    mismatch_keys = [
        key
        for key in [
            "generated_at_parse_ok",
            "gap_generated_at_not_older_than_raw",
            "gap_generated_at_not_older_than_normalized",
            "raw_source_path_matches",
            "normalized_source_path_matches",
            "raw_issue_schema_pass_matches",
            "normalized_issue_schema_pass_matches",
            "raw_noncompliant_issue_count_matches",
            "normalized_noncompliant_issue_count_matches",
        ]
        if details.get(key) is not True
    ]
    details["mismatch_keys"] = mismatch_keys
    details["pass"] = not mismatch_keys
    return bool(details["pass"]), details


def _visual_audit_index_contract(
    gap: dict[str, Any],
    index_path: Path,
    index_evidence: dict[str, Any],
    index: dict[str, Any],
) -> tuple[bool, dict[str, Any]]:
    source_artifacts = gap.get("source_artifacts") if isinstance(gap.get("source_artifacts"), dict) else {}
    total_files = _optional_int(index.get("total_files"))
    total_bases = _optional_int(index.get("total_bases"))
    index_generated_at = _parse_generated_at(index.get("generated_at"))
    gap_generated_at = _parse_generated_at(gap.get("generated_at"))
    index_mtime = _file_mtime_epoch(index_path)
    checks = {
        "index_exists": index_evidence.get("exists") is True,
        "index_has_content": int(index_evidence.get("size_bytes") or 0) > 0,
        "source_path_matches_index": _path_values_match(source_artifacts.get("visual_audit_index"), index_path),
        "gap_index_present_matches": gap.get("visual_audit_index_present") is True,
        "index_total_files_positive": total_files is not None and total_files > 0,
        "index_total_bases_positive": total_bases is not None and total_bases > 0,
        "index_generated_at_parse_ok": index_generated_at is not None,
        "gap_generated_at_parse_ok": gap_generated_at is not None,
        "gap_generated_at_not_older_than_index": bool(
            gap_generated_at is not None
            and index_generated_at is not None
            and gap_generated_at >= index_generated_at
        ),
        "index_mtime_present": index_mtime is not None,
        "index_mtime_not_older_than_index_generated_at": _epoch_not_older(index_mtime, index_generated_at),
    }
    mismatch_keys = [key for key, value in checks.items() if value is not True]
    details = {
        "pass": not mismatch_keys,
        "index_path": str(index_path),
        "source_path": source_artifacts.get("visual_audit_index", ""),
        "index_mtime_epoch": index_mtime,
        "index_mtime_local": _format_epoch(index_mtime),
        "index_generated_at": index.get("generated_at"),
        "gap_generated_at": gap.get("generated_at"),
        "total_files": index.get("total_files"),
        "total_bases": index.get("total_bases"),
        "gap_visual_audit_index_present": gap.get("visual_audit_index_present"),
        **checks,
        "mismatch_keys": mismatch_keys,
    }
    return bool(details["pass"]), details


def _visual_audit_report_freshness_contract(
    report_path: Path,
    report_evidence: dict[str, Any],
    index_path: Path,
    index: dict[str, Any],
    raw_path: Path,
    raw: dict[str, Any],
    normalized_path: Path,
    normalized: dict[str, Any],
    gap_path: Path,
    gap: dict[str, Any],
) -> tuple[bool, dict[str, Any]]:
    report_mtime = _file_mtime_epoch(report_path)
    index_mtime = _file_mtime_epoch(index_path)
    raw_mtime = _file_mtime_epoch(raw_path)
    normalized_mtime = _file_mtime_epoch(normalized_path)
    gap_mtime = _file_mtime_epoch(gap_path)
    index_generated_at = _parse_generated_at(index.get("generated_at"))
    raw_generated_at = _parse_generated_at(raw.get("generated_at"))
    normalized_generated_at = _parse_generated_at(normalized.get("generated_at"))
    gap_generated_at = _parse_generated_at(gap.get("generated_at"))
    checks = {
        "report_exists": report_evidence.get("exists") is True,
        "report_has_content": int(report_evidence.get("size_bytes") or 0) > 0,
        "report_mtime_present": report_mtime is not None,
        "index_file_mtime_present": index_mtime is not None,
        "raw_file_mtime_present": raw_mtime is not None,
        "normalized_file_mtime_present": normalized_mtime is not None,
        "gap_file_mtime_present": gap_mtime is not None,
        "index_generated_at_parse_ok": index_generated_at is not None,
        "raw_generated_at_parse_ok": raw_generated_at is not None,
        "normalized_generated_at_parse_ok": normalized_generated_at is not None,
        "gap_generated_at_parse_ok": gap_generated_at is not None,
        "report_mtime_not_older_than_index_mtime": _epoch_not_older(report_mtime, index_mtime),
        "report_mtime_not_older_than_raw_mtime": _epoch_not_older(report_mtime, raw_mtime),
        "report_mtime_not_older_than_normalized_mtime": _epoch_not_older(report_mtime, normalized_mtime),
        "report_mtime_not_older_than_gap_mtime": _epoch_not_older(report_mtime, gap_mtime),
        "report_mtime_not_older_than_index_generated_at": _epoch_not_older(report_mtime, index_generated_at),
        "report_mtime_not_older_than_raw_generated_at": _epoch_not_older(report_mtime, raw_generated_at),
        "report_mtime_not_older_than_normalized_generated_at": _epoch_not_older(
            report_mtime,
            normalized_generated_at,
        ),
        "report_mtime_not_older_than_gap_generated_at": _epoch_not_older(report_mtime, gap_generated_at),
    }
    mismatch_keys = [key for key, value in checks.items() if value is not True]
    details = {
        "pass": not mismatch_keys,
        "report_path": str(report_path),
        "index_path": str(index_path),
        "raw_issue_schema_path": str(raw_path),
        "normalized_issue_schema_path": str(normalized_path),
        "visual_audit_schema_gap_path": str(gap_path),
        "report_mtime_epoch": report_mtime,
        "report_mtime_local": _format_epoch(report_mtime),
        "index_mtime_epoch": index_mtime,
        "index_mtime_local": _format_epoch(index_mtime),
        "raw_mtime_epoch": raw_mtime,
        "raw_mtime_local": _format_epoch(raw_mtime),
        "normalized_mtime_epoch": normalized_mtime,
        "normalized_mtime_local": _format_epoch(normalized_mtime),
        "gap_mtime_epoch": gap_mtime,
        "gap_mtime_local": _format_epoch(gap_mtime),
        "index_generated_at": index.get("generated_at"),
        "raw_generated_at": raw.get("generated_at"),
        "normalized_generated_at": normalized.get("generated_at"),
        "gap_generated_at": gap.get("generated_at"),
        **checks,
        "mismatch_keys": mismatch_keys,
    }
    return bool(details["pass"]), details


def _visual_audit_backfill_overlay_contract(
    gap: dict[str, Any],
    raw: dict[str, Any],
) -> tuple[bool, dict[str, Any]]:
    source_artifacts = gap.get("source_artifacts") if isinstance(gap.get("source_artifacts"), dict) else {}
    summary = (
        gap.get("raw_issue_backfill_overlay_summary")
        if isinstance(gap.get("raw_issue_backfill_overlay_summary"), dict)
        else {}
    )
    raw_count = _optional_int(raw.get("noncompliant_issue_count"))
    overlay_count = _optional_int(summary.get("overlay_record_count"))
    raw_failure_count = _optional_int(summary.get("raw_failure_count"))
    jsonl_line_count = _optional_int(summary.get("jsonl_line_count"))
    jsonl_sha256 = str(summary.get("jsonl_sha256") or "")
    missing_replacement_count = _optional_int(summary.get("missing_replacement_count"))
    lossy_overlay_record_count = _optional_int(summary.get("lossy_overlay_record_count"))
    raw_generated_at = _parse_generated_at(raw.get("generated_at"))
    overlay_generated_at = _parse_generated_at(summary.get("generated_at"))
    active = gap.get("raw_issue_backfill_overlay_present") is True or gap.get("raw_issue_backfill_overlay_ready") is True
    details = {
        "pass": False,
        "active": active,
        "present": gap.get("raw_issue_backfill_overlay_present"),
        "ready": gap.get("raw_issue_backfill_overlay_ready"),
        "source_path": source_artifacts.get("raw_issue_backfill_overlay", ""),
        "summary_path": summary.get("path", ""),
        "summary_exists": summary.get("exists") is True,
        "source_path_matches_summary": _path_values_match(
            source_artifacts.get("raw_issue_backfill_overlay"),
            _resolve_path(summary.get("path")) or Path(),
        ),
        "overlay_generated_at": summary.get("generated_at"),
        "raw_generated_at": raw.get("generated_at"),
        "generated_at_parse_ok": overlay_generated_at is not None and raw_generated_at is not None,
        "overlay_generated_at_not_older_than_raw": bool(
            overlay_generated_at is not None and raw_generated_at is not None and overlay_generated_at >= raw_generated_at
        ),
        "top_level_cannot_replace_raw": gap.get("raw_issue_backfill_overlay_cannot_replace_raw") is True,
        "summary_pass": summary.get("pass") is True,
        "summary_release_ready_false": summary.get("release_ready") is False,
        "summary_cannot_replace_raw": summary.get("normalized_cannot_replace_raw") is True,
        "historical_artifacts_not_modified": summary.get("historical_artifacts_modified") is False,
        "raw_expected_noncompliant_issue_count": raw_count,
        "raw_failure_count": raw_failure_count,
        "overlay_record_count": overlay_count,
        "jsonl_line_count": jsonl_line_count,
        "jsonl_sha256": jsonl_sha256,
        "missing_replacement_count": missing_replacement_count,
        "lossy_overlay_record_count": lossy_overlay_record_count,
        "raw_failure_count_matches_raw": raw_failure_count == raw_count,
        "overlay_record_count_matches_raw": overlay_count == raw_count,
        "jsonl_line_count_matches_overlay": jsonl_line_count == overlay_count,
        "jsonl_sha256_valid": _is_sha256_hex(jsonl_sha256),
        "missing_replacement_count_zero": missing_replacement_count == 0,
        "lossy_overlay_record_count_nonnegative": (
            lossy_overlay_record_count is not None and lossy_overlay_record_count >= 0
        ),
        "mismatch_keys": [],
    }
    if not active:
        details["pass"] = True
        return True, details
    mismatch_keys = [
        key
        for key in [
            "summary_exists",
            "source_path_matches_summary",
            "generated_at_parse_ok",
            "overlay_generated_at_not_older_than_raw",
            "top_level_cannot_replace_raw",
            "summary_pass",
            "summary_release_ready_false",
            "summary_cannot_replace_raw",
            "historical_artifacts_not_modified",
            "raw_failure_count_matches_raw",
            "overlay_record_count_matches_raw",
            "jsonl_line_count_matches_overlay",
            "jsonl_sha256_valid",
            "missing_replacement_count_zero",
            "lossy_overlay_record_count_nonnegative",
        ]
        if details.get(key) is not True
    ]
    details["mismatch_keys"] = mismatch_keys
    details["pass"] = not mismatch_keys
    return bool(details["pass"]), details


def _visual_audit_repair_plan_contract(
    gap: dict[str, Any],
    raw: dict[str, Any],
) -> tuple[bool, dict[str, Any]]:
    source_artifacts = gap.get("source_artifacts") if isinstance(gap.get("source_artifacts"), dict) else {}
    summary = (
        gap.get("raw_issue_repair_plan_summary")
        if isinstance(gap.get("raw_issue_repair_plan_summary"), dict)
        else {}
    )
    raw_count = _optional_int(raw.get("noncompliant_issue_count"))
    repair_raw_count = _optional_int(summary.get("raw_noncompliant_issue_count"))
    missing_replacement_count = _optional_int(summary.get("missing_replacement_count"))
    lossy_normalized_issue_count = _optional_int(summary.get("lossy_normalized_issue_count"))
    raw_generated_at = _parse_generated_at(raw.get("generated_at"))
    repair_generated_at = _parse_generated_at(summary.get("generated_at"))
    active = gap.get("raw_issue_repair_plan_present") is True or gap.get("raw_issue_repair_plan_ready") is True
    details = {
        "pass": False,
        "active": active,
        "present": gap.get("raw_issue_repair_plan_present"),
        "ready": gap.get("raw_issue_repair_plan_ready"),
        "source_path": source_artifacts.get("raw_issue_repair_plan", ""),
        "summary_path": summary.get("path", ""),
        "summary_exists": summary.get("exists") is True,
        "source_path_matches_summary": _path_values_match(
            source_artifacts.get("raw_issue_repair_plan"),
            _resolve_path(summary.get("path")) or Path(),
        ),
        "repair_generated_at": summary.get("generated_at"),
        "raw_generated_at": raw.get("generated_at"),
        "generated_at_parse_ok": repair_generated_at is not None and raw_generated_at is not None,
        "repair_generated_at_not_older_than_raw": bool(
            repair_generated_at is not None and raw_generated_at is not None and repair_generated_at >= raw_generated_at
        ),
        "top_level_cannot_replace_raw": gap.get("raw_issue_repair_plan_cannot_replace_raw") is True,
        "summary_pass": summary.get("pass") is True,
        "summary_release_ready_false": summary.get("release_ready") is False,
        "summary_cannot_replace_raw": summary.get("normalized_cannot_replace_raw") is True,
        "historical_artifacts_not_modified": summary.get("historical_artifacts_modified") is False,
        "raw_expected_noncompliant_issue_count": raw_count,
        "repair_raw_noncompliant_issue_count": repair_raw_count,
        "missing_replacement_count": missing_replacement_count,
        "lossy_normalized_issue_count": lossy_normalized_issue_count,
        "repair_raw_count_matches_raw": repair_raw_count == raw_count,
        "missing_replacement_count_zero": missing_replacement_count == 0,
        "lossy_normalized_issue_count_nonnegative": (
            lossy_normalized_issue_count is not None and lossy_normalized_issue_count >= 0
        ),
        "lossy_normalized_issue_count_not_greater_than_raw": (
            lossy_normalized_issue_count is not None
            and raw_count is not None
            and lossy_normalized_issue_count <= raw_count
        ),
        "mismatch_keys": [],
    }
    if not active:
        details["pass"] = True
        return True, details
    mismatch_keys = [
        key
        for key in [
            "summary_exists",
            "source_path_matches_summary",
            "generated_at_parse_ok",
            "repair_generated_at_not_older_than_raw",
            "top_level_cannot_replace_raw",
            "summary_pass",
            "summary_release_ready_false",
            "summary_cannot_replace_raw",
            "historical_artifacts_not_modified",
            "repair_raw_count_matches_raw",
            "missing_replacement_count_zero",
            "lossy_normalized_issue_count_nonnegative",
            "lossy_normalized_issue_count_not_greater_than_raw",
        ]
        if details.get(key) is not True
    ]
    details["mismatch_keys"] = mismatch_keys
    details["pass"] = not mismatch_keys
    return bool(details["pass"]), details


def _path_values_match(value: Any, expected: Path) -> bool:
    try:
        path = _resolve_path(value)
        return path is not None and path.resolve() == expected.resolve()
    except Exception:
        return False


def _optional_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


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


def _file_mtime_epoch(path: Path) -> float | None:
    try:
        return path.stat().st_mtime if path.exists() and path.is_file() else None
    except OSError:
        return None


def _format_epoch(value: float | None) -> str:
    if value is None:
        return ""
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(value))


def _epoch_not_older(value: float | None, reference: float | None) -> bool:
    return bool(value is not None and reference is not None and value >= reference - 1.0)


def _is_sha256_hex(value: str) -> bool:
    return len(value) == 64 and all(ch in "0123456789abcdefABCDEF" for ch in value)


def _job_runtime_facade_proof(payload: dict[str, Any]) -> bool:
    if _any_truthy(payload, ["used_job_runtime_facade", "job_runtime_facade", "facade_routed"]):
        return True
    text = _selected_payload_text(payload, ["route", "runner", "entrypoint", "runtime", "facade", "worker", "launch_path"])
    compact = text.replace("_", "").replace("-", "")
    return "jobruntimefacade" in compact


def _qprocess_worker_proof(payload: dict[str, Any]) -> bool:
    if _any_truthy(payload, ["used_qprocess", "qprocess", "qprocess_worker", "worker_qprocess"]):
        return True
    text = _selected_payload_text(payload, ["route", "runner", "entrypoint", "runtime", "worker", "launch_path", "mode"])
    return "qprocess" in text


def _fresh_artifact_proof(payload: dict[str, Any]) -> bool:
    if _any_truthy(payload, ["artifact_mtime_ok", "fresh_artifacts", "fresh_artifacts_pass"]):
        return True
    artifact_freshness = payload.get("artifact_freshness")
    if isinstance(artifact_freshness, dict) and _any_truthy(artifact_freshness, ["pass", "artifact_mtime_ok", "fresh"]):
        return True
    checks = payload.get("freshness_checks") or payload.get("artifact_freshness_checks")
    if isinstance(checks, list) and checks:
        return all(isinstance(item, dict) and _record_passes(item) for item in checks)
    return False


def _required_artifact_proof(payload: dict[str, Any], required_keys: list[str]) -> bool:
    artifacts = (
        payload.get("required_artifacts")
        or payload.get("artifact_presence")
        or payload.get("artifacts")
        or payload.get("outputs")
    )
    if isinstance(artifacts, dict):
        normalized = {str(key).lower(): value for key, value in artifacts.items()}
        for required in required_keys:
            candidates = [value for key, value in normalized.items() if required in key]
            if not candidates or not any(_artifact_value_passes(value) for value in candidates):
                return False
        return True
    if isinstance(artifacts, list):
        for required in required_keys:
            matches = [
                item
                for item in artifacts
                if isinstance(item, dict)
                and required in _selected_payload_text(item, ["key", "name", "type", "artifact", "path"])
            ]
            if not matches or not any(_record_passes(item) for item in matches):
                return False
        return True
    return False


def _artifact_value_passes(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, dict):
        return _record_passes(value)
    return bool(value)


def _record_passes(payload: dict[str, Any]) -> bool:
    if payload.get("pass") is True or payload.get("exists") is True or payload.get("fresh") is True:
        return True
    status = str(payload.get("status") or "").lower()
    return status in {"pass", "passed", "ok", "fresh", "exists"}


def _any_truthy(payload: dict[str, Any], keys: list[str]) -> bool:
    for key in keys:
        value = payload.get(key)
        if value is True:
            return True
        if isinstance(value, str) and value.strip().lower() in {"true", "yes", "pass", "passed", "ok"}:
            return True
    return False


def _selected_payload_text(payload: dict[str, Any], keys: list[str]) -> str:
    values: list[str] = []
    for key in keys:
        value = payload.get(key)
        if isinstance(value, (str, int, float, bool)):
            values.append(str(value))
        elif isinstance(value, (list, dict)):
            values.append(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return " ".join(values).lower()


def _first_int(payload: dict[str, Any], keys: list[str]) -> int:
    for key in keys:
        try:
            return int(payload.get(key))
        except (TypeError, ValueError):
            continue
    return 0


def _next_required_action(status: str) -> str:
    if status == "blocked_by_solidworks_readiness":
        return "Start SolidWorks manually, rerun readiness, then run exactly one locked 006 CAD worker."
    if status == "blocked_by_006_regeneration_evidence":
        return "Produce a fresh 006 run through the locked CAD worker and pass the regeneration evidence gate."
    if status == "blocked_by_006_rerun_packet":
        return "Refresh the 006 rerun packet and source-signature evidence before starting any locked 006 CAD rerun."
    if status == "blocked_by_006_application_ui_review":
        return "Open Drawing Review in the application, capture side-by-side screenshots, and pass the manual visual checklist."
    if status == "blocked_by_requested_ref6_ui_review":
        return "Only after 006 passes, process 007/008/009/015/022 with per-drawing UI screenshot evidence."
    if status == "warning_not_release_ready":
        return "Complete final EXE, stability, Visual Audit raw/normalized issue schema proof, and release artifacts before release."
    if status == "pass":
        return "All product evidence gates passed."
    return "Fix the failing product evidence checks before advancing the validation stage."


def _repo_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v4.4 product evidence gate report.")
    parser.add_argument("--stability-gate", default=str(DEFAULT_STABILITY_GATE))
    parser.add_argument("--entrypoint-report", default=str(DEFAULT_ENTRYPOINT_REPORT))
    parser.add_argument("--lock-test-report", default=str(DEFAULT_LOCK_TEST_REPORT))
    parser.add_argument("--conflict-report", default=str(DEFAULT_CONFLICT_REPORT))
    parser.add_argument("--readiness", default=str(DEFAULT_READINESS))
    parser.add_argument("--reference-proof", default=str(DEFAULT_REFERENCE_PROOF))
    parser.add_argument("--reference-intent-plan", default=str(DEFAULT_REFERENCE_INTENT_PLAN))
    parser.add_argument("--reference-intent-contract", default=str(DEFAULT_REFERENCE_INTENT_CONTRACT))
    parser.add_argument("--rerun-packet", default=str(DEFAULT_RERUN_PACKET))
    parser.add_argument("--ui-defect-buckets", default=str(DEFAULT_UI_DEFECT_BUCKETS))
    parser.add_argument("--regeneration-gate", default=str(DEFAULT_REGENERATION_GATE))
    parser.add_argument("--acceptance-proof", default=str(DEFAULT_ACCEPTANCE_PROOF))
    parser.add_argument("--ui-visual-review", default=str(DEFAULT_UI_VISUAL_REVIEW))
    parser.add_argument("--requested-status", default=str(DEFAULT_REQUESTED_STATUS))
    parser.add_argument("--issue-schema-validation", default=str(DEFAULT_ISSUE_SCHEMA_VALIDATION))
    parser.add_argument("--normalized-issue-schema-validation", default=str(DEFAULT_NORMALIZED_ISSUE_SCHEMA_VALIDATION))
    parser.add_argument("--visual-audit-schema-gap", default=str(DEFAULT_VISUAL_AUDIT_SCHEMA_GAP))
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    parser.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    args = parser.parse_args()
    payload = build_product_evidence_gate(
        stability_gate_path=_repo_path(args.stability_gate),
        entrypoint_report_path=_repo_path(args.entrypoint_report),
        lock_test_report_path=_repo_path(args.lock_test_report),
        conflict_report_path=_repo_path(args.conflict_report),
        readiness_path=_repo_path(args.readiness),
        reference_proof_path=_repo_path(args.reference_proof),
        reference_intent_plan_path=_repo_path(args.reference_intent_plan),
        reference_intent_contract_path=_repo_path(args.reference_intent_contract),
        rerun_packet_path=_repo_path(args.rerun_packet),
        ui_defect_buckets_path=_repo_path(args.ui_defect_buckets),
        regeneration_gate_path=_repo_path(args.regeneration_gate),
        acceptance_proof_path=_repo_path(args.acceptance_proof),
        ui_visual_review_path=_repo_path(args.ui_visual_review),
        requested_status_path=_repo_path(args.requested_status),
        issue_schema_validation_path=_repo_path(args.issue_schema_validation),
        normalized_issue_schema_validation_path=_repo_path(args.normalized_issue_schema_validation),
        visual_audit_schema_gap_path=_repo_path(args.visual_audit_schema_gap),
        out_json=_repo_path(args.out_json),
        out_md=_repo_path(args.out_md),
    )
    print(json.dumps({
        "status": payload.get("status"),
        "pass": payload.get("pass"),
        "blocking_issue_keys": payload.get("blocking_issue_keys"),
        "allowed_actions": payload.get("allowed_actions"),
        "out_json": str(_repo_path(args.out_json)),
        "out_md": str(_repo_path(args.out_md)),
    }, ensure_ascii=False))
    return 0 if payload.get("pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
