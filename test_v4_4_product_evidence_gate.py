from __future__ import annotations

import json
from pathlib import Path
import struct
from tempfile import TemporaryDirectory
import zlib

from tools.validation.product_evidence_gate_v4_4 import (
    BASE,
    DEPENDENT_BASES,
    REQUIRED_REF6_PER_DRAWING_ARTIFACT_KEYS,
    build_product_evidence_gate,
)


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _write_file(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"ok")
    return path


def _write_png(path: Path, width: int = 1200, height: int = 800) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    raw = b"".join(b"\x00" + (b"\xff\xff\xff" * width) for _ in range(height))
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )
    path.write_bytes(png)
    return path


def _write_final_artifact(path: Path, key: str) -> Path:
    if key == "exe_ui_robot_result":
        return _write_json(path, {"mode": "windows_exe_ui_robot", "pass": True})
    if key == "exe_ui_text_quality_spotcheck":
        return _write_json(
            path,
            {
                "schema": "sw_drawing_studio.exe_stability_2h_visual_spotcheck.v4_4",
                "status": "pass",
                "pass": True,
                "stability_json_pass": True,
                "ui_text_quality_pass": True,
                "spotchecked_screenshot": "drw_output/ui_acceptance/exe_stability_2h_v3/screenshots/final.png",
                "blocking_issue_keys": [],
                "source_fix": {
                    "rebuild_required": False,
                    "rerun_2h_exe_stability_required": False,
                },
            },
        )
    if key == "cad_smoke":
        return _write_json(
            path,
            {
                "mode": "windows_exe_cad_smoke",
                "pass": True,
                "used_job_runtime_facade": True,
                "used_qprocess": True,
                "run_id": "smoke_run",
                "run_dir": "drw_output/runs/smoke_run",
                "artifact_mtime_ok": True,
                "required_artifacts": {
                    "slddrw": True,
                    "pdf": True,
                    "dxf": True,
                    "png": True,
                    "manifest": True,
                    "qc": True,
                    "vision": True,
                    "final_quality": True,
                    "sw_session": True,
                    "job_event_log": True,
                },
            },
        )
    if key == "dimension_validation_smoke":
        return _write_json(
            path,
            {
                "status": "pass",
                "pass": True,
                "true_display_dim_count": 12,
                "note_as_displaydim_count": 0,
                "note_substitution_count": 0,
                "note_annotations_counted_as_displaydim": False,
            },
        )
    if key == "reference_compare_smoke":
        return _write_json(path, {"status": "pass", "pass": True, "reference_compare_pass": True})
    if key == "stability_20min_mock":
        return _write_json(path, {"mode": "source_qt_mock_stability", "pass": True, "duration_observed_s": 1201.0})
    if key == "stability_2h_ui":
        return _write_json(path, {"mode": "windows_exe_navigation_stability", "pass": True, "duration_observed_s": 7201.0})
    return _write_file(path)


def _requested_ref6_matrix(
    root: Path,
    *,
    requested_pass: bool,
    missing_artifact_key: str = "",
    invalid_screenshot_base: str = "",
) -> list[dict]:
    rows: list[dict] = []
    for base in [BASE, *DEPENDENT_BASES]:
        screenshot = root / "ui_acceptance" / "ref6" / f"{base}_ui_visual_review.png"
        if requested_pass:
            if invalid_screenshot_base == base:
                _write_file(screenshot)
            else:
                _write_png(screenshot)
        artifacts: dict[str, str] = {}
        missing: list[str] = []
        for key in REQUIRED_REF6_PER_DRAWING_ARTIFACT_KEYS:
            artifact = root / "ref6_evidence" / base / f"{key}.json"
            if requested_pass and not (base == BASE and key == missing_artifact_key):
                _write_json(artifact, {"base": base, "artifact": key, "pass": True})
            artifacts[key] = str(artifact)
            if not artifact.exists():
                missing.append(key)
        closure_required = base == BASE
        closure_pass = requested_pass if closure_required else True
        rows.append(
            {
                "base": base,
                "status": "pass" if requested_pass else "blocked_by_006",
                "acceptance_status": "pass" if requested_pass else "blocked_by_006",
                "pass": requested_pass,
                "application_ui_screenshot_required": True,
                "application_ui_screenshot_present": requested_pass,
                "application_ui_screenshot_file_count": 1 if requested_pass else 0,
                "application_ui_screenshot_content_check_pass": requested_pass,
                "ui_screenshot_files": [str(screenshot)] if requested_pass else [],
                "application_ui_screenshot_paths_existing_application_ui": [str(screenshot)] if requested_pass else [],
                "manual_visual_judgement_required": True,
                "manual_visual_judgement_present": requested_pass,
                "manual_visual_judgement_pass": requested_pass,
                "manual_visual_checklist_required": True,
                "manual_visual_checklist_pass": requested_pass,
                "manual_visual_checklist_failed_items": [] if requested_pass else ["display_dimensions"],
                "application_ui_source_mode": "drawing_review_workbench_direct_host" if requested_pass else "",
                "solidworks_probe_allowed_during_screenshot_review": False if requested_pass else None,
                "ui_screenshot_review_no_solidworks_probe_pass": requested_pass,
                "side_by_side_reference_generated_layout_pass": requested_pass,
                "side_by_side_reference_generated_layout": {
                    "required": True,
                    "pass": requested_pass,
                    "left_panel": "reference_drawing",
                    "right_panel": "generated_drawing",
                    "reference_loaded": requested_pass,
                    "generated_loaded": requested_pass,
                    "api_only_acceptance_allowed": False,
                },
                "ui_defect_bucket_closure_required": closure_required,
                "ui_defect_bucket_closure_pass": closure_pass,
                "ui_defect_bucket_missing_keys": [] if closure_pass else ["dimension_visual_overdense"],
                "ui_defect_bucket_failed_keys": [],
                "missing_ui_acceptance_requirements": [] if requested_pass and not missing else ["required_per_drawing_artifacts"],
                "api_only_acceptance_allowed": False,
                "final_judgement_source": "application_drawing_review_ui_screenshot_manual_visual_judgement",
                "vision_qc_v6_visual_acceptance_pass": requested_pass,
                "reference_compare_v4_pass": requested_pass,
                "required_artifact_keys": list(REQUIRED_REF6_PER_DRAWING_ARTIFACT_KEYS),
                "required_artifacts": artifacts,
                "required_artifacts_present": not missing,
                "missing_required_artifacts": missing,
            }
        )
    return rows


def _fixture(
    root: Path,
    *,
    readiness_ready: bool = True,
    regeneration_pass: bool = True,
    acceptance_pass: bool = True,
    requested_pass: bool = True,
    requested_missing_artifact_key: str = "",
    requested_invalid_screenshot_base: str = "",
    final_artifacts: bool = True,
    raw_issue_schema_pass: bool = True,
    normalized_issue_schema_pass: bool = True,
    visual_audit_schema_gap_pass: bool | None = None,
    visual_audit_schema_gap_counters: bool = True,
    rerun_packet_build_ready: bool = True,
    rerun_packet_real_cad_allowed_now: bool | None = None,
    ui_defect_buckets_ready: bool = True,
    ui_visual_review_pass: bool | None = None,
    ui_visual_review_screenshot_exists: bool = True,
    ui_visual_review_screenshot_valid: bool = True,
    entrypoint_report_pass: bool = True,
    ui_thread_subprocess_call_count: int = 0,
    ui_thread_heavy_work_count: int = 0,
    ui_threadpool_worker_count: int = 0,
    lock_test_report_pass: bool = True,
    conflict_report_ok: bool = True,
    idle_solidworks_without_lock: bool = False,
    readiness_sampling_schema: bool = True,
    readiness_unsaved_title_observed: bool = False,
    reference_plan_complete: bool = True,
    reference_plan_note_substitution: bool = False,
    reference_contract_locked: bool = True,
    regeneration_ui_contract: bool = True,
) -> dict[str, Path]:
    gap_pass = (
        bool(raw_issue_schema_pass and normalized_issue_schema_pass and final_artifacts)
        if visual_audit_schema_gap_pass is None
        else visual_audit_schema_gap_pass
    )
    gap_check_passes = [
        True,
        raw_issue_schema_pass,
        True,
        normalized_issue_schema_pass,
        final_artifacts,
        True,
        gap_pass,
    ]
    gap_counter_payload = (
        {
            "check_count": len(gap_check_passes),
            "passed_check_count": sum(1 for item in gap_check_passes if item),
            "failed_check_count": sum(1 for item in gap_check_passes if not item),
        }
        if visual_audit_schema_gap_counters
        else {}
    )
    packet_real_cad_allowed = (
        bool(rerun_packet_build_ready and readiness_ready)
        if rerun_packet_real_cad_allowed_now is None
        else rerun_packet_real_cad_allowed_now
    )
    packet_status = (
        "offline_prerequisites_missing"
        if not rerun_packet_build_ready
        else "ready_for_locked_006_rerun"
        if packet_real_cad_allowed
        else "blocked_by_solidworks_readiness"
    )
    ui_review_pass = acceptance_pass if ui_visual_review_pass is None else ui_visual_review_pass
    ui_screenshot = root / "ui_acceptance" / "screenshots" / f"01_{BASE}_ui_visual_review.png"
    if ui_visual_review_screenshot_exists:
        if ui_visual_review_screenshot_valid:
            _write_png(ui_screenshot)
        else:
            _write_file(ui_screenshot)
    required_active_defect_buckets = [
        "dimension_visual_overdense",
        "dimension_lane_wrong",
        "note_missing_or_wrong",
        "titlebar_incomplete",
        "projection_view_style_mismatch",
    ]
    defect_bucket_keys = [*required_active_defect_buckets, "callout_missing"]
    if not ui_defect_buckets_ready:
        defect_bucket_keys.remove("dimension_lane_wrong")
    ui_defect_visual_pass = bool(acceptance_pass and ui_review_pass and ui_defect_buckets_ready)
    ui_defect_status = "pass" if ui_defect_visual_pass else "needs_006_fix" if readiness_ready else "blocked_by_solidworks_readiness"
    ui_defect_active = [] if ui_defect_visual_pass else [key for key in defect_bucket_keys if key != "callout_missing"]
    ui_defect_buckets = [
        {
            "key": key,
            "active": key in ui_defect_active,
            "severity": "major" if key in ui_defect_active else "info",
            "blocks_006_acceptance": key in ui_defect_active,
            "evidence": {"fixture": True},
            "source_paths": [str(ui_screenshot)],
            "fix_action": "fixture correction",
        }
        for key in defect_bucket_keys
    ]
    screenshot_visual_observations = [
        {
            "bucket": key,
            "observation_key": f"{key}_application_ui_screenshot_observation",
            "source": "application_drawing_review_ui_screenshot",
            "source_paths": [str(ui_screenshot)],
            "visual_check": "reference_match" if key == "callout_missing" else "display_dimensions",
            "visual_check_pass": None if key == "callout_missing" else False,
            "manual_note": "fixture screenshot observation",
            "visual_fact": "fixture visual fact",
            "reference_expectation": "fixture reference expectation",
            "generated_failure": "fixture generated failure",
            "repair_signal": "fixture repair signal",
            "supports_active_bucket": key in ui_defect_active,
            "next_screenshot_check_required": True,
            "api_or_displaydim_metric_alone_can_close": False,
        }
        for key in defect_bucket_keys
    ]
    bucket_closure_contract = []
    for key in defect_bucket_keys:
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
            item["required_callout_keys"] = ["thread_callout_m4_6h", "hole_callout_4x3_3", "surface_finish_rest_3_2"]
            item["absence_check_keys"] = ["radius_callout", "chamfer_callout"]
        bucket_closure_contract.append(item)
    required_dim_keys = [
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
    ]
    dim_keys = required_dim_keys if reference_plan_complete else required_dim_keys[:-1]
    dimensions = [
        {
            "key": key,
            "source_reference": "3D转2D测试图纸/LB26001-A-04-006.SLDDRW",
            "target_view": "front" if not key.startswith("projection") and key != "small_feature_location" else "right",
            "expected_type": "linear_horizontal",
            "is_manufacturing_dimension": True,
            "fallback_policy": "need_review_when_real_displaydim_unavailable",
            "source_reference_evidence": {"source_text": key},
            "reference_value": 1,
            "reference_value_status": "visual_reading_recorded",
            "create_as": "Note" if reference_plan_note_substitution else "SolidWorks DisplayDim",
            "forbid_note_substitution": not reference_plan_note_substitution,
            "generic_autodimension_acceptance_allowed": False,
        }
        for key in dim_keys
    ]
    operations = [
        {
            "operation": "create_or_verify_display_dimension",
            "dimension_key": item["key"],
            "source_reference_evidence": item["source_reference_evidence"],
            "is_manufacturing_dimension": True,
        }
        for item in dimensions
    ]
    view_plan = [
        {
            "slot": "front",
            "required": True,
            "reference_view_name": "工程图视图1",
            "center_norm": [0.3704, 0.8074],
            "outline_norm": [0.1626, 0.772, 0.5781, 0.8429],
        },
        {
            "slot": "right",
            "required": True,
            "reference_view_name": "工程图视图2",
            "center_norm": [0.7259, 0.8074],
            "outline_norm": [0.7017, 0.772, 0.7502, 0.8429],
        },
        {
            "slot": "top",
            "required": True,
            "reference_view_name": "工程图视图3",
            "center_norm": [0.3704, 0.5948],
            "outline_norm": [0.1626, 0.5605, 0.5781, 0.629],
        },
        {
            "slot": "iso",
            "required": True,
            "reference_view_name": "工程图视图4",
            "center_norm": [0.8025, 0.478],
            "outline_norm": [0.7163, 0.3929, 0.8887, 0.5631],
        },
    ]
    layout_plan = {
        "sheet_size": {"width": 0.297, "height": 0.21},
        "views": view_plan,
        "notes_box_norm": [0.58, 0.64, 0.96, 0.82],
        "titlebar_box_norm": [0.60, 0.02, 0.96, 0.13],
        "bottom_notice_box_norm": [0.30, 0.16, 0.66, 0.24],
        "projection_view_style_match_required": True,
        "compact_titlebar_fields_required": True,
        "reference_style_notes_required": True,
        "sheet_template_policy": {
            "policy": "strip_default_template_artifacts",
            "skip_builtin_gb_frame_titleblock": True,
            "default_template_artifacts_allowed": False,
            "suppress_default_titlebar_fields": True,
            "application_ui_screenshot_required": True,
        },
        "reference_titlebar_policy": {
            "schema": "sw_drawing_studio.reference_titlebar_policy.v4_4",
            "suppress_default_titlebar_fields": True,
            "suppress_drawing_no_name_visible_note": True,
            "render_reference_bottom_notice": True,
            "bottom_notice_text": "细节尺寸较多，未注尺寸请核对3D图档",
            "bottom_notice_box_norm": [0.30, 0.16, 0.66, 0.24],
            "default_template_artifacts_allowed": False,
            "api_or_reference_json_alone_can_close": False,
            "application_ui_screenshot_required": True,
        },
        "reference_view_outline_policy": {
            "schema": "sw_drawing_studio.reference_view_outline_policy.v4_4",
            "view_outline_size_match_required": True,
            "view_outline_size_tolerance": 0.18,
            "independent_view_scale_allowed": True,
            "downscale_oversized_views_only": True,
            "target_outlines_required": True,
            "api_or_reference_json_alone_can_close": False,
            "application_ui_screenshot_required": True,
        },
        "view_outline_size_match_required": True,
        "view_outline_size_tolerance": 0.18,
        "independent_view_scale_allowed": True,
    }
    reference_layout_policy = {
        "schema": "sw_drawing_studio.reference_layout_policy.v4_4",
        "base": BASE,
        "view_plan": view_plan,
        "layout_plan": layout_plan,
        "reference_titlebar_policy": layout_plan["reference_titlebar_policy"],
        "reference_view_outline_policy": layout_plan["reference_view_outline_policy"],
        "ui_defect_repair_layout_targets": {
            "target_buckets": [
                "projection_view_style_mismatch",
                "note_missing_or_wrong",
                "titlebar_incomplete",
            ],
            "notes_box_norm": layout_plan["notes_box_norm"],
            "titlebar_box_norm": layout_plan["titlebar_box_norm"],
            "bottom_notice_box_norm": layout_plan["bottom_notice_box_norm"],
            "suppress_default_titlebar_fields": True,
            "view_outline_size_match_required": True,
            "application_ui_screenshot_required": True,
        },
    }
    reference_dimension_lane_policy = {
        "schema": "sw_drawing_studio.reference_dimension_lane_policy.v4_4",
        "base": BASE,
        "target_buckets": ["dimension_visual_overdense", "dimension_lane_wrong"],
        "required_target_count": 12,
        "max_visible_display_dim_count": 12,
        "reference_lane_geometry_issue_count_after_required": 0,
        "compact_local_lanes_required": True,
        "reject_generic_autodim_survivors": True,
        "reject_far_lane": True,
        "reject_diagonal_or_cross_region_leaders": True,
        "allow_compact_top_view_side_lanes": True,
        "top_view_side_lane_max_gap_m": 0.018,
        "api_or_displaydim_metric_alone_can_close": False,
        "application_ui_screenshot_required": True,
        "lane_targets": [
            {
                "target_key": item["key"],
                "target_view": item["target_view"],
                "expected_type": item["expected_type"],
                "preferred_side": item.get("preferred_side", "above"),
                "lane_family": "outside_top",
                "lane_index": 0,
                "station": 0.5,
                "readability_required": True,
            }
            for item in dimensions
        ],
    }
    readiness_payload = {
        "status": "ready" if readiness_ready else "blocked",
        "ready_to_start_locked_006_cad": readiness_ready,
        "blocking_issue_keys": []
        if readiness_ready and not readiness_unsaved_title_observed
        else ["solidworks_unsaved_document_visible"]
        if readiness_unsaved_title_observed
        else ["solidworks_not_running"],
    }
    if readiness_sampling_schema:
        readiness_payload["solidworks_process"] = {
            "source": "process_probe",
            "process_present": readiness_ready or readiness_unsaved_title_observed,
            "process_count": 1 if readiness_ready or readiness_unsaved_title_observed else 0,
            "processes": [
                {
                    "pid": 14144,
                    "process_name": "SLDWORKS",
                    "responding": True,
                    "main_window_title": "SOLIDWORKS Premium 2025 SP5.0 - [装配体6 *]"
                    if readiness_unsaved_title_observed
                    else "SOLIDWORKS Premium 2025 SP5.0",
                    "observed_titles": [
                        "SOLIDWORKS Premium 2025 SP5.0 - [installed_validation_shaft.SLDPRT [查看中]]",
                        "SOLIDWORKS Premium 2025 SP5.0 - [装配体6 *]",
                    ]
                    if readiness_unsaved_title_observed
                    else ["SOLIDWORKS Premium 2025 SP5.0"],
                }
            ]
            if readiness_ready or readiness_unsaved_title_observed
            else [],
            "pid": 14144 if readiness_ready or readiness_unsaved_title_observed else None,
            "responding": True if readiness_ready or readiness_unsaved_title_observed else None,
            "main_window_title": "SOLIDWORKS Premium 2025 SP5.0 - [装配体6 *]"
            if readiness_unsaved_title_observed
            else "SOLIDWORKS Premium 2025 SP5.0",
            "sample_count": 5,
            "observation_count": 5 if readiness_ready or readiness_unsaved_title_observed else 0,
            "unsaved_title_observed": readiness_unsaved_title_observed,
            "probe_errors": [],
        }
    paths = {
        "stability": _write_json(
            root / "stability.json",
            {
                "status": "warning" if idle_solidworks_without_lock else "pass",
                "pass": not idle_solidworks_without_lock,
                "warning_reasons": ["solidworks_conflict_monitor_warning_or_fail"] if idle_solidworks_without_lock else [],
                "entrypoint_summary": {
                    "unguarded_or_unknown_count": 0,
                    "ui_thread_direct_risk_count": 0,
                    "ui_thread_subprocess_call_count": ui_thread_subprocess_call_count,
                    "ui_thread_heavy_work_count": ui_thread_heavy_work_count,
                    "ui_threadpool_worker_count": ui_threadpool_worker_count,
                    "service_direct_risk_count": 0,
                    "system_health_ui_thread_direct_probe_count": 0,
                },
            },
        ),
        "entrypoint": _write_json(
            root / "unguarded_solidworks_entrypoints.json",
            {
                "schema": "sw_drawing_studio.unguarded_solidworks_entrypoints.v4_4",
                "status": "pass" if entrypoint_report_pass else "warning",
                "entrypoint_count": 10,
                "unguarded_or_unknown_count": 0 if entrypoint_report_pass else 1,
                "ui_thread_direct_risk_count": 0 if entrypoint_report_pass else 1,
                "ui_thread_subprocess_call_count": ui_thread_subprocess_call_count,
                "ui_thread_heavy_work_count": ui_thread_heavy_work_count,
                "ui_threadpool_worker_count": ui_threadpool_worker_count,
                "service_direct_risk_count": 0,
                "system_health_ui_thread_direct_probe_count": 0,
                "external_addin_host_lock_contract_status": "pass" if entrypoint_report_pass else "fail",
            },
        ),
        "lock_test": _write_json(
            root / "solidworks_lock_test_result.json",
            {
                "schema": "sw_drawing_studio.solidworks_lock_test_result.v4_4",
                "status": "pass" if lock_test_report_pass else "fail",
                "pass": lock_test_report_pass,
                "failure": "" if lock_test_report_pass else "second_owner_not_blocked",
                "checks": [
                    {"key": "first_job_acquires_lock", "status": "pass"},
                    {"key": "second_job_blocked_by_owner", "status": "pass" if lock_test_report_pass else "fail"},
                ],
            },
        ),
        "conflict": _write_json(
            root / "conflict_report.json",
            {
                "schema": "sw_drawing_studio.solidworks_conflict_report.v1",
                "level": "WARNING" if idle_solidworks_without_lock else "OK" if conflict_report_ok else "WARNING",
                "lock": None,
                "lock_owner": {},
                "lock_reason": "no_active_solidworks_lock"
                if (conflict_report_ok or idle_solidworks_without_lock)
                else "solidworks_process_detected",
                "fix_suggestion": ""
                if conflict_report_ok
                else "真实 CAD / Add-in / OpenDoc6 操作前必须通过 worker 获取全局锁"
                if idle_solidworks_without_lock
                else "Close or serialize SolidWorks before CAD work.",
                "counts": {
                    "solidworks_processes": 1 if idle_solidworks_without_lock else 0 if conflict_report_ok else 1,
                    "cad_job_workers": 0,
                    "batch_job_workers": 0,
                    "waiting_jobs": 0,
                    "smoke_leftovers": 0,
                    "dialog_guards": 0,
                },
                "findings": [
                    {
                        "severity": "WARNING",
                        "key": "solidworks_running_without_lock",
                        "message": "SW running but no active SolidWorks global lock.",
                    }
                ]
                if idle_solidworks_without_lock
                else [],
            },
        ),
        "readiness": _write_json(
            root / "readiness.json",
            readiness_payload,
        ),
        "reference": _write_json(
            root / "reference.json",
            {
                "base": BASE,
                "pass": True,
                "status": "plan_proof_pass_requires_locked_cad_run",
                "report_is_drawing_acceptance_evidence": False,
                "api_only_acceptance_allowed": False,
                "dimension_summary": {"count": 12},
            },
        ),
        "reference_intent_plan": _write_json(
            root / "reference_intent_dimension_plan_006.json",
            {
                "schema": "sw_drawing_studio.reference_intent_dimension_plan.v4_4",
                "base": BASE,
                "status": "plan_ready_requires_cad_worker_lock",
                "required_display_dim_count": 12,
                "reference_display_dim_count": 12,
                "allow_note_substitution": False,
                "ui_screenshot_acceptance_required": True,
                "api_is_supporting_only": True,
                "reference_layout_policy": reference_layout_policy,
                "view_plan": view_plan,
                "layout_plan": layout_plan,
                "ui_defect_repair_layout_targets": reference_layout_policy["ui_defect_repair_layout_targets"],
                "reference_dimension_lane_policy": reference_dimension_lane_policy,
                "dimensions": dimensions,
                "reference_callouts": [
                    {
                        "key": "thread_callout_m4_6h",
                        "target_view": "top",
                        "expected_type": "thread_callout",
                        "source_reference": "3D转2D测试图纸/LB26001-A-04-006.SLDDRW",
                        "is_manufacturing_dimension": True,
                        "fallback_policy": "need_review_when_real_callout_unavailable",
                        "source_reference_evidence": {"source_text": "M4-6H"},
                        "reference_value": "M4-6H 完全贯穿",
                        "reference_value_status": "visual_reading_recorded",
                        "forbid_note_substitution_for_displaydim": True,
                        "create_as": "SolidWorks hole/thread callout, not a substitute DisplayDim",
                    },
                    {
                        "key": "hole_callout_4x3_3",
                        "target_view": "top",
                        "expected_type": "hole_callout",
                        "source_reference": "3D杞?D娴嬭瘯鍥剧焊/LB26001-A-04-006.SLDDRW",
                        "is_manufacturing_dimension": True,
                        "fallback_policy": "need_review_when_real_callout_unavailable",
                        "source_reference_evidence": {"source_text": "4-3.3"},
                        "reference_value": "4-3.3 through",
                        "reference_value_status": "visual_reading_recorded",
                        "forbid_note_substitution_for_displaydim": True,
                        "create_as": "SolidWorks hole callout, not a substitute DisplayDim",
                    },
                    {
                        "key": "surface_finish_rest_3_2",
                        "target_view": "sheet_notes",
                        "expected_type": "surface_finish_callout",
                        "source_reference": "3D转2D测试图纸/LB26001-A-04-006.SLDDRW",
                        "is_manufacturing_dimension": True,
                        "fallback_policy": "need_review_when_real_callout_unavailable",
                        "source_reference_evidence": {"source_text": "3.2 其余"},
                        "reference_value": "3.2 其余",
                        "reference_value_status": "visual_reading_recorded",
                        "create_as": "manufacturing note/symbol; does not count as DisplayDim",
                    },
                    {
                        "key": "radius_callout",
                        "target_view": "front/top/right",
                        "expected_type": "radius_callout",
                        "source_reference": "3D转2D测试图纸/LB26001-A-04-006.SLDDRW",
                        "is_manufacturing_dimension": False,
                        "fallback_policy": "do_not_create_unless_geometry_or_reference_proves_feature",
                        "source_reference_evidence": {"source_text": "", "extraction_method": "manual_visual_absence_check"},
                        "reference_value": None,
                    },
                    {
                        "key": "chamfer_callout",
                        "target_view": "front/top/right",
                        "expected_type": "chamfer_callout",
                        "source_reference": "3D转2D测试图纸/LB26001-A-04-006.SLDDRW",
                        "is_manufacturing_dimension": False,
                        "fallback_policy": "do_not_create_unless_geometry_or_reference_proves_feature",
                        "source_reference_evidence": {"source_text": "", "extraction_method": "manual_visual_absence_check"},
                        "reference_value": None,
                    },
                ],
            },
        ),
        "reference_intent_contract": _write_json(
            root / "reference_intent_dimension_contract_006.json",
            {
                "schema": "sw_drawing_studio.reference_intent_dimension_execution_contract.v4_4",
                "base": BASE,
                "status": "contract_ready_requires_cad_worker_lock",
                "requires_solidworks_lock": reference_contract_locked,
                "ui_thread_may_execute": not reference_contract_locked,
                "direct_com_called": False,
                "allowed_entrypoint": "cad_job_worker",
                "operation_count": len(operations),
                "operations": operations,
            },
        ),
        "rerun_packet": _write_json(
            root / "rerun_packet.json",
            {
                "schema": "sw_drawing_studio.lb26001_006_rerun_packet.v4_2",
                "base": BASE,
                "status": packet_status,
                "pass": False,
                "report_is_acceptance_evidence": False,
                "packet_build_ready": rerun_packet_build_ready,
                "real_cad_allowed_now": packet_real_cad_allowed,
                "readiness_ready": readiness_ready,
                "readiness_status": "ready" if readiness_ready else "blocked",
                "offline_prerequisite_missing_keys": []
                if rerun_packet_build_ready
                else ["generator_repair_signatures_present"],
                "api_only_acceptance_allowed": False,
                "application_ui_screenshot_is_final_gate": True,
                "source_signatures": {
                    "generator": {
                        "pass": rerun_packet_build_ready,
                        "missing_signatures": []
                        if rerun_packet_build_ready
                        else ["reference_callout_review_plan_required"],
                    },
                    "cad_job_worker": {"pass": True, "missing_signatures": []},
                },
            },
        ),
        "ui_defect_buckets": _write_json(
            root / "ui_defect_buckets.json",
            {
                "schema": "sw_drawing_studio.lb26001_006_ui_defect_buckets.v4_4",
                "base": BASE,
                "status": ui_defect_status,
                "pass": ui_defect_visual_pass,
                "release_ready": False,
                "api_only_acceptance_allowed": False,
                "application_ui_screenshot_is_final_gate": True,
                "solidworks_readiness": {
                    "status": "ready" if readiness_ready else "blocked",
                    "ready_to_start_locked_006_cad": readiness_ready,
                    "blocking_issue_keys": [] if readiness_ready else ["solidworks_not_running"],
                },
                "ui_final_gate": {
                    "review_mode": "application_drawing_review_ui_screenshot",
                    "visual_acceptance_pass": ui_defect_visual_pass,
                    "ui_report_screenshot_pass": True,
                    "ui_report_evidence_capture_pass": True,
                    "failed_visual_checklist_items": [] if ui_defect_visual_pass else ["display_dimensions"],
                },
                "active_bucket_count": len(ui_defect_active),
                "active_buckets": ui_defect_active,
                "required_bucket_keys": required_active_defect_buckets + ["callout_missing"],
                "missing_bucket_keys": [],
                "required_next_screenshot_check_buckets": required_active_defect_buckets + ["callout_missing"],
                "next_screenshot_checklist": [
                    {"bucket": key, "required": True}
                    for key in required_active_defect_buckets
                ] + [{
                    "bucket": "callout_missing",
                    "required": True,
                    "required_callout_keys": [
                        "thread_callout_m4_6h",
                        "hole_callout_4x3_3",
                        "surface_finish_rest_3_2",
                    ],
                    "absence_check_keys": ["radius_callout", "chamfer_callout"],
                }],
                "bucket_closure_contract": bucket_closure_contract,
                "missing_bucket_closure_contract_keys": [],
                "screenshot_visual_observations": screenshot_visual_observations,
                "buckets": ui_defect_buckets,
            },
        ),
        "regeneration": _write_json(
            root / "regeneration.json",
            {
                "schema": "sw_drawing_studio.lb26001_006_regeneration_evidence_gate.v4_4",
                "base": BASE,
                "pass": regeneration_pass,
                "status": "regeneration_evidence_pass_requires_application_ui_screenshot_review" if regeneration_pass else "blocked_by_missing_fresh_006_run",
                "release_ready": False,
                "run_id": "run006" if regeneration_pass else "",
                "run_dir": str(root / "runs" / "run006") if regeneration_pass else "",
                "report_is_drawing_acceptance_evidence": False,
                "api_only_acceptance_allowed": False if regeneration_ui_contract else True,
                "ui_screenshot_acceptance_required": regeneration_ui_contract,
                "application_drawing_review_ui_required": regeneration_ui_contract,
                "solidworks_runtime_called": False if regeneration_ui_contract else True,
                "blocking_issue_keys": [] if regeneration_pass else ["explicit_006_run_evidence_source"],
            },
        ),
        "acceptance": _write_json(
            root / "acceptance.json",
            {
                "base": BASE,
                "pass": acceptance_pass,
                "status": "pass" if acceptance_pass else "blocked_by_006",
                "application_ui_screenshot_is_final_gate": True,
                "blocking_issue_keys": [] if acceptance_pass else ["manual_visual_checklist_not_pass"],
                "ui_closure_evidence": {
                    "direct_ui_screenshot_recheck_method_ok": True,
                    "direct_ui_screenshot_recheck_pass": acceptance_pass,
                    "manual_visual_checklist_pass": acceptance_pass,
                    "manual_visual_checklist_failed_items": [] if acceptance_pass else ["display_dimensions"],
                },
            },
        ),
        "ui_visual_review": _write_json(
            root / "ui_visual_review.json",
            {
                "schema": "sw_drawing_studio.ui_visual_review.v4_4",
                "status": "pass" if ui_review_pass else "need_review",
                "pass": ui_review_pass,
                "visual_acceptance_pass": ui_review_pass,
                "review_method": "application_drawing_review_ui_screenshot",
                "application_ui_screenshot_is_final_gate": True,
                "application_ui_source_mode": "drawing_review_workbench_direct_host",
                "solidworks_probe_allowed_during_screenshot_review": False,
                "ui_screenshot_review_no_solidworks_probe_all_pass": ui_review_pass,
                "api_only_acceptance_allowed": False,
                "pass_count": 1 if ui_review_pass else 0,
                "fail_count": 0 if ui_review_pass else 1,
                "blocking_issue_keys": [] if ui_review_pass else ["vision_qc_v6_with_ui_not_pass"],
                "entries": [
                    {
                        "base": BASE,
                        "status": "pass" if ui_review_pass else "need_review",
                        "pass": ui_review_pass,
                        "visual_acceptance_pass": ui_review_pass,
                        "application_ui_screenshot": str(ui_screenshot),
                        "application_ui_source_mode": "drawing_review_workbench_direct_host",
                        "solidworks_probe_allowed_during_screenshot_review": False,
                        "side_by_side_reference_generated_layout": {
                            "required": True,
                            "pass": ui_review_pass,
                            "left_panel": "reference_drawing",
                            "right_panel": "generated_drawing",
                            "left_reference_png": str(root / "reference.png"),
                            "right_generated_png": str(root / "generated.png"),
                            "comparison_png": str(ui_screenshot),
                            "reference_loaded": ui_review_pass,
                            "generated_loaded": ui_review_pass,
                            "api_only_acceptance_allowed": False,
                        },
                        "checks": {
                            "ui_report_entry_pass": True,
                            "ui_screenshot_review_no_solidworks_probe_pass": ui_review_pass,
                            "manual_review_entry_screenshot_pass": True,
                            "side_by_side_reference_generated_layout_pass": ui_review_pass,
                            "ui_defect_bucket_closure_pass": ui_review_pass,
                            "vision_qc_v6_visual_acceptance_pass": ui_review_pass,
                            "reference_compare_v4_pass": ui_review_pass,
                            "generated_png_source_pass": True,
                        },
                        "blocking_issue_keys": [] if ui_review_pass else ["vision_qc_v6_with_ui_not_pass"],
                    }
                ],
            },
        ),
        "requested": _write_json(
            root / "requested.json",
            {
                "schema": "sw_drawing_studio.lb26001_requested_drawings_status.v4_2",
                "pass": requested_pass,
                "status": "pass" if requested_pass else "blocked_by_006",
                "pass_count": 6 if requested_pass else 0,
                "not_pass_count": 0 if requested_pass else 6,
                "per_drawing_ui_acceptance_pass_count": 6 if requested_pass else 0,
                "primary_acceptance_proof_status": "pass" if requested_pass else "blocked_by_006",
                "per_drawing_ui_review_matrix": _requested_ref6_matrix(
                    root,
                    requested_pass=requested_pass,
                    missing_artifact_key=requested_missing_artifact_key,
                    invalid_screenshot_base=requested_invalid_screenshot_base,
                ),
            },
        ),
        "issue_schema": _write_json(
            root / "issue_schema_validation.json",
            {
                "status": "pass" if raw_issue_schema_pass else "fail",
                "pass": raw_issue_schema_pass,
                "issue_count": 10,
                "noncompliant_issue_count": 0 if raw_issue_schema_pass else 7,
                "failure_bucket": [] if raw_issue_schema_pass else ["vision_issue_schema_incomplete"],
            },
        ),
        "normalized_issue_schema": _write_json(
            root / "issue_schema_validation_normalized.json",
            {
                "status": "pass" if normalized_issue_schema_pass else "fail",
                "pass": normalized_issue_schema_pass,
                "issue_count": 10,
                "noncompliant_issue_count": 0 if normalized_issue_schema_pass else 1,
                "failure_bucket": [] if normalized_issue_schema_pass else ["normalized_issue_schema_incomplete"],
            },
        ),
        "visual_audit_schema_gap": _write_json(
            root / "visual_audit_schema_gap_v4_4.json",
            {
                "schema": "sw_drawing_studio.visual_audit_schema_gap.v4_4",
                "status": "pass" if gap_pass else "raw_issue_schema_noncompliant",
                "pass": gap_pass,
                **gap_counter_payload,
                "raw_noncompliant_issue_count": 0 if raw_issue_schema_pass else 7,
                "normalized_noncompliant_issue_count": 0 if normalized_issue_schema_pass else 1,
                "visual_audit_report_final_present": final_artifacts,
                "visual_audit_full_scope_allowed_now": gap_pass,
                "normalized_supporting_only": True,
                "normalized_cannot_replace_raw": True,
                "raw_issue_backfill_overlay_present": True,
                "raw_issue_backfill_overlay_ready": True,
                "raw_issue_backfill_overlay_cannot_replace_raw": True,
                "raw_issue_backfill_overlay_summary": {
                    "status": "overlay_ready_requires_human_review",
                    "pass": True,
                    "raw_failure_count": 0 if raw_issue_schema_pass else 7,
                    "overlay_record_count": 0 if raw_issue_schema_pass else 7,
                    "missing_replacement_count": 0,
                    "lossy_overlay_record_count": 0 if raw_issue_schema_pass else 5,
                    "jsonl_line_count": 0 if raw_issue_schema_pass else 7,
                    "jsonl_sha256": "fixture-sha256",
                    "historical_artifacts_modified": False,
                    "normalized_cannot_replace_raw": True,
                },
                "blocking_issue_keys": [] if gap_pass else ["raw_issue_schema_pass"],
            },
        ),
    }
    final = {
        "dist_exe": root / "dist" / "sw_drawing_studio.exe",
        "release_log": root / "release_log_v3_0.md",
        "validation_log": root / "validation_log_v3_0.md",
        "ui_acceptance_report": root / "ui_acceptance_report_v3_0.md",
        "exe_ui_robot_result": root / "exe_ui_robot_result_v3_0.json",
        "exe_ui_text_quality_spotcheck": root / "drw_output" / "diagnostics" / "exe_stability_2h_visual_spotcheck_v4_4.json",
        "cad_smoke": root / "cad_smoke_v3_0.json",
        "dimension_validation_smoke": root / "dimension_validation_smoke.json",
        "reference_compare_smoke": root / "reference_compare_smoke.json",
        "reference_comparison_report": root / "drw_output" / "reference_comparison_report_v3_0.xlsx",
        "visual_audit_report": root / "drw_output" / "visual_audit_report_v3_0.xlsx",
        "visual_audit_index": root / "drw_output" / "visual_audit_index.json",
        "stability_20min_mock": root / "stability_20min_mock_v3_0.json",
        "stability_2h_ui": root / "stability_2h_ui_v3_0.json",
    }
    if final_artifacts:
        for key, path in final.items():
            _write_final_artifact(path, key)
    paths["final_artifacts"] = final  # type: ignore[assignment]
    return paths


def _build(paths: dict[str, Path]) -> dict:
    return build_product_evidence_gate(
        stability_gate_path=paths["stability"],
        entrypoint_report_path=paths["entrypoint"],
        lock_test_report_path=paths["lock_test"],
        conflict_report_path=paths["conflict"],
        readiness_path=paths["readiness"],
        reference_proof_path=paths["reference"],
        reference_intent_plan_path=paths["reference_intent_plan"],
        reference_intent_contract_path=paths["reference_intent_contract"],
        rerun_packet_path=paths["rerun_packet"],
        ui_defect_buckets_path=paths["ui_defect_buckets"],
        regeneration_gate_path=paths["regeneration"],
        acceptance_proof_path=paths["acceptance"],
        ui_visual_review_path=paths["ui_visual_review"],
        requested_status_path=paths["requested"],
        issue_schema_validation_path=paths["issue_schema"],
        normalized_issue_schema_validation_path=paths["normalized_issue_schema"],
        visual_audit_schema_gap_path=paths["visual_audit_schema_gap"],
        final_artifacts=paths["final_artifacts"],  # type: ignore[arg-type]
    )


def test_product_evidence_gate_can_pass_complete_fixture() -> None:
    with TemporaryDirectory() as tmp:
        result = _build(_fixture(Path(tmp)))

        assert result["pass"] is True
        assert result["status"] == "pass"
        assert result["release_ready"] is True
        assert result["allowed_actions"]["full_129_allowed"] is True
        assert not result["blocking_issue_keys"]


def test_product_evidence_gate_checks_are_boolean_machine_readable() -> None:
    with TemporaryDirectory() as tmp:
        result = _build(_fixture(Path(tmp), readiness_ready=False))

        checks = result["checks"]
        assert checks
        assert all(isinstance(item.get("pass"), bool) for item in checks)
        assert all((item["status"] == "pass") == item["pass"] for item in checks)
        assert result["check_count"] == len(checks)
        assert result["passed_check_count"] == sum(1 for item in checks if item["pass"] is True)
        assert result["failed_check_count"] == sum(1 for item in checks if item["pass"] is False)
        assert set(result["blocking_issue_keys"]) == {
            item["key"] for item in checks if item["pass"] is False
        }


def test_product_evidence_gate_blocks_when_solidworks_readiness_is_blocked() -> None:
    with TemporaryDirectory() as tmp:
        result = _build(_fixture(Path(tmp), readiness_ready=False))

        assert result["pass"] is False
        assert result["status"] == "blocked_by_solidworks_readiness"
        assert result["allowed_actions"]["locked_006_cad_rerun_allowed_now"] is False
        assert result["allowed_actions"]["expand_007_008_009_015_022_allowed"] is False
        assert result["allowed_actions"]["lb26001_36_allowed"] is False
        assert result["allowed_actions"]["full_129_allowed"] is False
        assert "solidworks_readiness_for_006" in set(result["blocking_issue_keys"])
        assert "lb26001_006_rerun_packet_ready" not in set(result["blocking_issue_keys"])
        assert "lb26001_006_rerun_packet_readiness_state_current" not in set(result["blocking_issue_keys"])


def test_product_evidence_gate_blocks_old_readiness_without_title_sampling() -> None:
    with TemporaryDirectory() as tmp:
        result = _build(_fixture(Path(tmp), readiness_ready=True, readiness_sampling_schema=False))

        assert result["pass"] is False
        assert result["status"] == "blocked_by_solidworks_readiness"
        assert result["allowed_actions"]["locked_006_cad_rerun_allowed_now"] is False
        assert "solidworks_readiness_title_sampling_guard" in set(result["blocking_issue_keys"])
        check = next(item for item in result["checks"] if item["key"] == "solidworks_readiness_title_sampling_guard")
        assert "solidworks_process.sample_count>=5" in check["details"]["missing_or_invalid_sampling_fields"]
        assert "solidworks_process.unsaved_title_observed_false" in check["details"]["missing_or_invalid_sampling_fields"]


def test_product_evidence_gate_blocks_ready_readiness_when_unsaved_title_was_observed() -> None:
    with TemporaryDirectory() as tmp:
        result = _build(
            _fixture(Path(tmp), readiness_ready=True, readiness_unsaved_title_observed=True)
        )

        assert result["pass"] is False
        assert result["status"] == "blocked_by_solidworks_readiness"
        assert result["allowed_actions"]["locked_006_cad_rerun_allowed_now"] is False
        assert "solidworks_readiness_title_sampling_guard" in set(result["blocking_issue_keys"])
        check = next(item for item in result["checks"] if item["key"] == "solidworks_readiness_title_sampling_guard")
        assert check["details"]["unsaved_title_observed"] is True
        assert any(title.endswith("*]") for title in check["details"]["observed_titles"])


def test_product_evidence_gate_blocks_when_raw_entrypoint_report_has_ui_risk() -> None:
    with TemporaryDirectory() as tmp:
        result = _build(_fixture(Path(tmp), entrypoint_report_pass=False))

        assert result["pass"] is False
        assert result["status"] == "blocked_by_solidworks_stability_gate"
        assert result["allowed_actions"]["locked_006_cad_rerun_allowed_now"] is False
        assert result["allowed_actions"]["full_129_allowed"] is False
        assert "solidworks_entrypoint_scan_report_pass" in set(result["blocking_issue_keys"])
        check = next(item for item in result["checks"] if item["key"] == "solidworks_entrypoint_scan_report_pass")
        assert check["details"]["ui_thread_direct_risk_count"] == 1


def test_product_evidence_gate_blocks_when_ui_threadpool_worker_returns() -> None:
    with TemporaryDirectory() as tmp:
        result = _build(_fixture(Path(tmp), ui_threadpool_worker_count=1))

        assert result["pass"] is False
        assert result["status"] == "blocked_by_solidworks_stability_gate"
        assert result["allowed_actions"]["locked_006_cad_rerun_allowed_now"] is False
        assert "ui_thread_direct_risk_zero" in set(result["blocking_issue_keys"])
        assert "solidworks_entrypoint_scan_report_pass" in set(result["blocking_issue_keys"])
        entrypoint_check = next(
            item for item in result["checks"] if item["key"] == "solidworks_entrypoint_scan_report_pass"
        )
        assert entrypoint_check["details"]["ui_threadpool_worker_count"] == 1


def test_product_evidence_gate_blocks_when_ui_shell_subprocess_returns() -> None:
    with TemporaryDirectory() as tmp:
        result = _build(_fixture(Path(tmp), ui_thread_subprocess_call_count=1))

        assert result["pass"] is False
        assert result["status"] == "blocked_by_solidworks_stability_gate"
        assert result["allowed_actions"]["locked_006_cad_rerun_allowed_now"] is False
        assert "ui_thread_direct_risk_zero" in set(result["blocking_issue_keys"])
        assert "solidworks_entrypoint_scan_report_pass" in set(result["blocking_issue_keys"])
        entrypoint_check = next(
            item for item in result["checks"] if item["key"] == "solidworks_entrypoint_scan_report_pass"
        )
        assert entrypoint_check["details"]["ui_thread_subprocess_call_count"] == 1


def test_product_evidence_gate_blocks_when_ui_heavy_work_returns() -> None:
    with TemporaryDirectory() as tmp:
        result = _build(_fixture(Path(tmp), ui_thread_heavy_work_count=1))

        assert result["pass"] is False
        assert result["status"] == "blocked_by_solidworks_stability_gate"
        assert result["allowed_actions"]["locked_006_cad_rerun_allowed_now"] is False
        assert "ui_thread_direct_risk_zero" in set(result["blocking_issue_keys"])
        assert "solidworks_entrypoint_scan_report_pass" in set(result["blocking_issue_keys"])
        entrypoint_check = next(
            item for item in result["checks"] if item["key"] == "solidworks_entrypoint_scan_report_pass"
        )
        assert entrypoint_check["details"]["ui_thread_heavy_work_count"] == 1


def test_product_evidence_gate_blocks_when_lock_test_report_fails() -> None:
    with TemporaryDirectory() as tmp:
        result = _build(_fixture(Path(tmp), lock_test_report_pass=False))

        assert result["pass"] is False
        assert result["status"] == "blocked_by_solidworks_stability_gate"
        assert result["allowed_actions"]["locked_006_cad_rerun_allowed_now"] is False
        assert "solidworks_lock_test_report_pass" in set(result["blocking_issue_keys"])
        check = next(item for item in result["checks"] if item["key"] == "solidworks_lock_test_report_pass")
        assert check["details"]["failed_checks"] == ["second_job_blocked_by_owner"]


def test_product_evidence_gate_blocks_when_conflict_report_warns() -> None:
    with TemporaryDirectory() as tmp:
        result = _build(_fixture(Path(tmp), conflict_report_ok=False))

        assert result["pass"] is False
        assert result["status"] == "blocked_by_solidworks_stability_gate"
        assert result["allowed_actions"]["locked_006_cad_rerun_allowed_now"] is False
        assert "solidworks_conflict_report_ok" in set(result["blocking_issue_keys"])
        check = next(item for item in result["checks"] if item["key"] == "solidworks_conflict_report_ok")
        assert check["details"]["counts"]["solidworks_processes"] == 1


def test_product_evidence_gate_allows_idle_solidworks_prelock_for_locked_006_only() -> None:
    with TemporaryDirectory() as tmp:
        result = _build(
            _fixture(
                Path(tmp),
                idle_solidworks_without_lock=True,
                regeneration_pass=False,
                acceptance_pass=False,
                requested_pass=False,
                final_artifacts=False,
            )
        )

        assert result["pass"] is False
        assert result["status"] == "blocked_by_006_regeneration_evidence"
        assert result["allowed_actions"]["locked_006_cad_rerun_allowed_now"] is True
        assert result["allowed_actions"]["006_application_ui_review_allowed_now"] is False
        assert result["allowed_actions"]["expand_007_008_009_015_022_allowed"] is False
        assert result["allowed_actions"]["full_129_allowed"] is False
        stability_check = next(item for item in result["checks"] if item["key"] == "solidworks_stability_gate_pass")
        conflict_check = next(item for item in result["checks"] if item["key"] == "solidworks_conflict_report_ok")
        assert stability_check["details"]["idle_solidworks_prelock_allowed_for_locked_006"] is True
        assert conflict_check["details"]["idle_solidworks_prelock_allowed_for_locked_006"] is True


def test_product_evidence_gate_blocks_when_reference_intent_plan_missing_target() -> None:
    with TemporaryDirectory() as tmp:
        result = _build(_fixture(Path(tmp), reference_plan_complete=False))

        assert result["pass"] is False
        assert result["status"] == "blocked_by_006_reference_intent"
        assert result["allowed_actions"]["locked_006_cad_rerun_allowed_now"] is False
        assert result["allowed_actions"]["full_129_allowed"] is False
        assert "reference_intent_006_plan_complete" in set(result["blocking_issue_keys"])
        check = next(item for item in result["checks"] if item["key"] == "reference_intent_006_plan_complete")
        assert check["details"]["missing_dimension_keys"] == ["small_feature_location"]


def test_product_evidence_gate_blocks_when_reference_callout_lacks_evidence() -> None:
    with TemporaryDirectory() as tmp:
        paths = _fixture(Path(tmp))
        plan_path = paths["reference_intent_plan"]
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        radius_callout = next(item for item in plan["reference_callouts"] if item["key"] == "radius_callout")
        radius_callout["source_reference_evidence"] = {}
        _write_json(plan_path, plan)

        result = _build(paths)

        assert result["pass"] is False
        assert result["status"] == "blocked_by_006_reference_intent"
        assert result["allowed_actions"]["locked_006_cad_rerun_allowed_now"] is False
        assert "reference_intent_006_plan_complete" in set(result["blocking_issue_keys"])
        check = next(item for item in result["checks"] if item["key"] == "reference_intent_006_plan_complete")
        assert check["details"]["callout_missing_fields"] == {"radius_callout": ["source_reference_evidence"]}


def test_product_evidence_gate_blocks_when_reference_intent_plan_uses_note_substitution() -> None:
    with TemporaryDirectory() as tmp:
        result = _build(_fixture(Path(tmp), reference_plan_note_substitution=True))

        assert result["pass"] is False
        assert result["status"] == "blocked_by_006_reference_intent"
        assert result["allowed_actions"]["locked_006_cad_rerun_allowed_now"] is False
        assert "reference_intent_006_plan_complete" in set(result["blocking_issue_keys"])
        check = next(item for item in result["checks"] if item["key"] == "reference_intent_006_plan_complete")
        assert "overall_length" in set(check["details"]["note_substitution_keys"])


def test_product_evidence_gate_blocks_when_reference_intent_contract_is_not_lock_owned() -> None:
    with TemporaryDirectory() as tmp:
        result = _build(_fixture(Path(tmp), reference_contract_locked=False))

        assert result["pass"] is False
        assert result["status"] == "blocked_by_006_reference_intent"
        assert result["allowed_actions"]["locked_006_cad_rerun_allowed_now"] is False
        assert "reference_intent_006_contract_locked_worker_only" in set(result["blocking_issue_keys"])
        check = next(
            item for item in result["checks"] if item["key"] == "reference_intent_006_contract_locked_worker_only"
        )
        assert check["details"]["requires_solidworks_lock"] is False
        assert check["details"]["ui_thread_may_execute"] is True


def test_product_evidence_gate_blocks_locked_006_when_rerun_packet_offline_missing() -> None:
    with TemporaryDirectory() as tmp:
        result = _build(_fixture(Path(tmp), rerun_packet_build_ready=False))

        assert result["pass"] is False
        assert result["status"] == "blocked_by_006_rerun_packet"
        assert result["allowed_actions"]["locked_006_cad_rerun_allowed_now"] is False
        assert result["allowed_actions"]["full_129_allowed"] is False
        assert "lb26001_006_rerun_packet_ready" in set(result["blocking_issue_keys"])
        check = next(item for item in result["checks"] if item["key"] == "lb26001_006_rerun_packet_ready")
        assert check["details"]["offline_prerequisite_missing_keys"] == ["generator_repair_signatures_present"]
        assert check["details"]["source_signature_summary"]["generator"]["pass"] is False


def test_product_evidence_gate_blocks_locked_006_when_rerun_packet_state_is_stale() -> None:
    with TemporaryDirectory() as tmp:
        result = _build(_fixture(Path(tmp), readiness_ready=True, rerun_packet_real_cad_allowed_now=False))

        assert result["pass"] is False
        assert result["status"] == "blocked_by_006_rerun_packet"
        assert result["allowed_actions"]["locked_006_cad_rerun_allowed_now"] is False
        assert result["allowed_actions"]["full_129_allowed"] is False
        assert "lb26001_006_rerun_packet_readiness_state_current" in set(result["blocking_issue_keys"])
        check = next(
            item for item in result["checks"] if item["key"] == "lb26001_006_rerun_packet_readiness_state_current"
        )
        assert check["details"]["readiness_ok"] is True
        assert check["details"]["expected_packet_status"] == "ready_for_locked_006_rerun"


def test_product_evidence_gate_blocks_locked_006_when_ui_defect_buckets_are_incomplete() -> None:
    with TemporaryDirectory() as tmp:
        result = _build(_fixture(Path(tmp), ui_defect_buckets_ready=False))

        assert result["pass"] is False
        assert result["status"] == "blocked_by_006_rerun_packet"
        assert result["allowed_actions"]["locked_006_cad_rerun_allowed_now"] is False
        assert result["allowed_actions"]["full_129_allowed"] is False
        assert "lb26001_006_ui_defect_buckets_ready" in set(result["blocking_issue_keys"])
        check = next(item for item in result["checks"] if item["key"] == "lb26001_006_ui_defect_buckets_ready")
        assert check["details"]["missing_bucket_keys"] == ["dimension_lane_wrong"]
        assert check["details"]["defect_plan_ready"] is False
        assert check["details"]["defect_closure_pass"] is False


def test_product_evidence_gate_blocks_locked_006_when_callout_next_screenshot_check_is_missing() -> None:
    with TemporaryDirectory() as tmp:
        paths = _fixture(Path(tmp))
        ui_defect_path = paths["ui_defect_buckets"]
        payload = json.loads(ui_defect_path.read_text(encoding="utf-8"))
        payload["required_next_screenshot_check_buckets"] = [
            key for key in payload["required_next_screenshot_check_buckets"] if key != "callout_missing"
        ]
        payload["next_screenshot_checklist"] = [
            item for item in payload["next_screenshot_checklist"] if item.get("bucket") != "callout_missing"
        ]
        _write_json(ui_defect_path, payload)

        result = _build(paths)

        assert result["pass"] is False
        assert result["status"] == "blocked_by_006_rerun_packet"
        assert result["allowed_actions"]["locked_006_cad_rerun_allowed_now"] is False
        assert "lb26001_006_ui_defect_buckets_ready" in set(result["blocking_issue_keys"])
        check = next(item for item in result["checks"] if item["key"] == "lb26001_006_ui_defect_buckets_ready")
        assert check["details"]["missing_next_check_buckets"] == ["callout_missing"]
        assert check["details"]["missing_next_checklist_buckets"] == ["callout_missing"]
        assert check["details"]["callout_next_check_ok"] is False


def test_product_evidence_gate_blocks_locked_006_when_bucket_closure_contract_is_missing() -> None:
    with TemporaryDirectory() as tmp:
        paths = _fixture(Path(tmp))
        ui_defect_path = paths["ui_defect_buckets"]
        payload = json.loads(ui_defect_path.read_text(encoding="utf-8"))
        payload["bucket_closure_contract"] = [
            item for item in payload["bucket_closure_contract"] if item.get("bucket") != "dimension_lane_wrong"
        ]
        _write_json(ui_defect_path, payload)

        result = _build(paths)

        assert result["pass"] is False
        assert result["status"] == "blocked_by_006_rerun_packet"
        assert result["allowed_actions"]["locked_006_cad_rerun_allowed_now"] is False
        assert "lb26001_006_ui_defect_buckets_ready" in set(result["blocking_issue_keys"])
        check = next(item for item in result["checks"] if item["key"] == "lb26001_006_ui_defect_buckets_ready")
        assert check["details"]["missing_bucket_closure_contract_keys"] == ["dimension_lane_wrong"]


def test_product_evidence_gate_blocks_locked_006_when_callout_closure_contract_is_incomplete() -> None:
    with TemporaryDirectory() as tmp:
        paths = _fixture(Path(tmp))
        ui_defect_path = paths["ui_defect_buckets"]
        payload = json.loads(ui_defect_path.read_text(encoding="utf-8"))
        for item in payload["bucket_closure_contract"]:
            if item.get("bucket") == "callout_missing":
                item.pop("required_callout_keys", None)
                item.pop("absence_check_keys", None)
        _write_json(ui_defect_path, payload)

        result = _build(paths)

        assert result["pass"] is False
        assert result["status"] == "blocked_by_006_rerun_packet"
        assert result["allowed_actions"]["locked_006_cad_rerun_allowed_now"] is False
        assert "lb26001_006_ui_defect_buckets_ready" in set(result["blocking_issue_keys"])
        check = next(item for item in result["checks"] if item["key"] == "lb26001_006_ui_defect_buckets_ready")
        assert check["details"]["callout_closure_contract_ok"] is False
        assert check["details"]["incomplete_bucket_closure_contracts"]["callout_missing"] == [
            "required_callout_keys",
            "absence_check_keys",
        ]


def test_product_evidence_gate_blocks_locked_006_when_active_screenshot_observation_is_missing() -> None:
    with TemporaryDirectory() as tmp:
        paths = _fixture(Path(tmp), acceptance_pass=False, requested_pass=False)
        ui_defect_path = paths["ui_defect_buckets"]
        payload = json.loads(ui_defect_path.read_text(encoding="utf-8"))
        payload["screenshot_visual_observations"] = [
            item
            for item in payload["screenshot_visual_observations"]
            if item.get("bucket") != "dimension_visual_overdense"
        ]
        _write_json(ui_defect_path, payload)

        result = _build(paths)

        assert result["pass"] is False
        assert result["status"] == "blocked_by_006_rerun_packet"
        assert result["allowed_actions"]["locked_006_cad_rerun_allowed_now"] is False
        assert "lb26001_006_ui_defect_buckets_ready" in set(result["blocking_issue_keys"])
        check = next(item for item in result["checks"] if item["key"] == "lb26001_006_ui_defect_buckets_ready")
        assert check["details"]["missing_active_screenshot_visual_observation_buckets"] == [
            "dimension_visual_overdense"
        ]


def test_product_evidence_gate_blocks_expansion_when_006_ui_acceptance_fails() -> None:
    with TemporaryDirectory() as tmp:
        result = _build(_fixture(Path(tmp), acceptance_pass=False, requested_pass=False))

        assert result["pass"] is False
        assert result["status"] == "blocked_by_006_application_ui_review"
        assert result["do_not_expand_007_008_009_015_022"] is True
        assert result["allowed_actions"]["expand_007_008_009_015_022_allowed"] is False
        assert "application_ui_006_acceptance_pass" in set(result["blocking_issue_keys"])


def test_product_evidence_gate_blocks_when_regeneration_gate_relaxes_ui_contract() -> None:
    with TemporaryDirectory() as tmp:
        result = _build(_fixture(Path(tmp), regeneration_ui_contract=False))

        assert result["pass"] is False
        assert result["status"] == "blocked_by_006_regeneration_evidence"
        assert result["allowed_actions"]["006_application_ui_review_allowed_now"] is False
        assert result["allowed_actions"]["expand_007_008_009_015_022_allowed"] is False
        assert "regeneration_006_fresh_evidence_pass" in set(result["blocking_issue_keys"])
        check = next(item for item in result["checks"] if item["key"] == "regeneration_006_fresh_evidence_pass")
        assert check["details"]["api_only_acceptance_allowed"] is True
        assert check["details"]["ui_screenshot_acceptance_required"] is False
        assert check["details"]["application_drawing_review_ui_required"] is False
        assert check["details"]["solidworks_runtime_called"] is True


def test_product_evidence_gate_blocks_expansion_when_canonical_ui_visual_review_fails() -> None:
    with TemporaryDirectory() as tmp:
        result = _build(_fixture(Path(tmp), acceptance_pass=True, ui_visual_review_pass=False))

        assert result["pass"] is False
        assert result["status"] == "blocked_by_006_application_ui_review"
        assert result["do_not_expand_007_008_009_015_022"] is True
        assert result["allowed_actions"]["expand_007_008_009_015_022_allowed"] is False
        assert "canonical_006_ui_visual_review_pass" in set(result["blocking_issue_keys"])
        check = next(item for item in result["checks"] if item["key"] == "canonical_006_ui_visual_review_pass")
        assert check["details"]["base_entry"]["application_ui_screenshot_exists"] is True
        assert check["details"]["base_entry"]["visual_acceptance_pass"] is False


def test_product_evidence_gate_blocks_when_canonical_ui_bucket_closure_missing() -> None:
    with TemporaryDirectory() as tmp:
        paths = _fixture(Path(tmp), acceptance_pass=True, ui_visual_review_pass=True)
        payload = json.loads(paths["ui_visual_review"].read_text(encoding="utf-8"))
        payload["entries"][0]["checks"].pop("ui_defect_bucket_closure_pass", None)
        paths["ui_visual_review"].write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        result = _build(paths)

        assert result["pass"] is False
        assert result["status"] == "blocked_by_006_application_ui_review"
        assert result["allowed_actions"]["expand_007_008_009_015_022_allowed"] is False
        assert "canonical_006_ui_visual_review_pass" in set(result["blocking_issue_keys"])
        check = next(item for item in result["checks"] if item["key"] == "canonical_006_ui_visual_review_pass")
        assert check["details"]["base_entry"]["checks"].get("ui_defect_bucket_closure_pass") is None


def test_product_evidence_gate_blocks_when_canonical_ui_side_by_side_layout_missing() -> None:
    with TemporaryDirectory() as tmp:
        paths = _fixture(Path(tmp), acceptance_pass=True, ui_visual_review_pass=True)
        payload = json.loads(paths["ui_visual_review"].read_text(encoding="utf-8"))
        payload["entries"][0]["checks"].pop("side_by_side_reference_generated_layout_pass", None)
        payload["entries"][0].pop("side_by_side_reference_generated_layout", None)
        paths["ui_visual_review"].write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        result = _build(paths)

        assert result["pass"] is False
        assert result["status"] == "blocked_by_006_application_ui_review"
        assert result["allowed_actions"]["expand_007_008_009_015_022_allowed"] is False
        assert "canonical_006_ui_visual_review_pass" in set(result["blocking_issue_keys"])
        check = next(item for item in result["checks"] if item["key"] == "canonical_006_ui_visual_review_pass")
        assert check["details"]["base_entry"]["checks"].get("side_by_side_reference_generated_layout_pass") is None


def test_product_evidence_gate_blocks_when_canonical_ui_no_probe_proof_missing() -> None:
    with TemporaryDirectory() as tmp:
        paths = _fixture(Path(tmp), acceptance_pass=True, ui_visual_review_pass=True)
        payload = json.loads(paths["ui_visual_review"].read_text(encoding="utf-8"))
        payload.pop("application_ui_source_mode", None)
        payload.pop("solidworks_probe_allowed_during_screenshot_review", None)
        payload.pop("ui_screenshot_review_no_solidworks_probe_all_pass", None)
        payload["entries"][0].pop("application_ui_source_mode", None)
        payload["entries"][0].pop("solidworks_probe_allowed_during_screenshot_review", None)
        payload["entries"][0]["checks"].pop("ui_screenshot_review_no_solidworks_probe_pass", None)
        paths["ui_visual_review"].write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        result = _build(paths)

        assert result["pass"] is False
        assert result["status"] == "blocked_by_006_application_ui_review"
        assert result["allowed_actions"]["expand_007_008_009_015_022_allowed"] is False
        assert "canonical_006_ui_visual_review_pass" in set(result["blocking_issue_keys"])
        check = next(item for item in result["checks"] if item["key"] == "canonical_006_ui_visual_review_pass")
        assert check["details"]["application_ui_source_mode"] is None
        assert check["details"]["base_entry"]["checks"].get("ui_screenshot_review_no_solidworks_probe_pass") is None


def test_product_evidence_gate_blocks_expansion_when_canonical_ui_screenshot_missing() -> None:
    with TemporaryDirectory() as tmp:
        result = _build(
            _fixture(Path(tmp), acceptance_pass=True, ui_visual_review_pass=True, ui_visual_review_screenshot_exists=False)
        )

        assert result["pass"] is False
        assert result["status"] == "blocked_by_006_application_ui_review"
        assert result["allowed_actions"]["expand_007_008_009_015_022_allowed"] is False
        assert "canonical_006_ui_visual_review_pass" in set(result["blocking_issue_keys"])
        check = next(item for item in result["checks"] if item["key"] == "canonical_006_ui_visual_review_pass")
        assert check["details"]["base_entry"]["application_ui_screenshot_exists"] is False


def test_product_evidence_gate_blocks_expansion_when_canonical_ui_screenshot_is_not_image() -> None:
    with TemporaryDirectory() as tmp:
        result = _build(
            _fixture(
                Path(tmp),
                acceptance_pass=True,
                ui_visual_review_pass=True,
                ui_visual_review_screenshot_valid=False,
            )
        )

        assert result["pass"] is False
        assert result["status"] == "blocked_by_006_application_ui_review"
        assert result["allowed_actions"]["expand_007_008_009_015_022_allowed"] is False
        assert "canonical_006_ui_visual_review_pass" in set(result["blocking_issue_keys"])
        check = next(item for item in result["checks"] if item["key"] == "canonical_006_ui_visual_review_pass")
        assert check["details"]["base_entry"]["application_ui_screenshot_exists"] is True
        assert check["details"]["base_entry"]["application_ui_screenshot_decode_pass"] is False
        assert check["details"]["base_entry"]["application_ui_screenshot_valid"] is False


def test_product_evidence_gate_allows_ref6_expansion_only_after_006_passes() -> None:
    with TemporaryDirectory() as tmp:
        result = _build(_fixture(Path(tmp), acceptance_pass=True, requested_pass=False))

        assert result["pass"] is False
        assert result["status"] == "blocked_by_requested_ref6_ui_review"
        assert result["allowed_actions"]["expand_007_008_009_015_022_allowed"] is True
        assert result["allowed_actions"]["requested_ref6_complete"] is False
        assert result["allowed_actions"]["lb26001_36_allowed"] is False
        assert result["allowed_actions"]["full_129_allowed"] is False


def test_product_evidence_gate_blocks_ref6_complete_when_per_drawing_artifact_missing() -> None:
    with TemporaryDirectory() as tmp:
        result = _build(
            _fixture(
                Path(tmp),
                acceptance_pass=True,
                requested_pass=True,
                requested_missing_artifact_key="vision_qc",
            )
        )

        assert result["pass"] is False
        assert result["status"] == "blocked_by_requested_ref6_ui_review"
        assert result["allowed_actions"]["requested_ref6_complete"] is False
        assert result["allowed_actions"]["lb26001_36_allowed"] is False
        assert "requested_ref6_ui_status_pass" in set(result["blocking_issue_keys"])
        check = next(item for item in result["checks"] if item["key"] == "requested_ref6_ui_status_pass")
        assert check["details"]["missing_required_artifacts_by_base"][BASE] == ["vision_qc"]


def test_product_evidence_gate_blocks_ref6_complete_when_per_drawing_screenshot_is_invalid() -> None:
    with TemporaryDirectory() as tmp:
        result = _build(
            _fixture(
                Path(tmp),
                acceptance_pass=True,
                requested_pass=True,
                requested_invalid_screenshot_base=DEPENDENT_BASES[0],
            )
        )

        assert result["pass"] is False
        assert result["status"] == "blocked_by_requested_ref6_ui_review"
        assert result["allowed_actions"]["requested_ref6_complete"] is False
        assert "requested_ref6_ui_status_pass" in set(result["blocking_issue_keys"])
        check = next(item for item in result["checks"] if item["key"] == "requested_ref6_ui_status_pass")
        invalid = check["details"]["invalid_application_ui_screenshots_by_base"][DEPENDENT_BASES[0]][0]
        assert invalid["decode_pass"] is False
        assert invalid["valid_ui_screenshot"] is False


def test_product_evidence_gate_blocks_ref6_complete_when_no_probe_or_side_by_side_missing() -> None:
    with TemporaryDirectory() as tmp:
        paths = _fixture(Path(tmp), acceptance_pass=True, requested_pass=True)
        payload = json.loads(paths["requested"].read_text(encoding="utf-8"))
        row = payload["per_drawing_ui_review_matrix"][0]
        row.pop("application_ui_source_mode", None)
        row.pop("solidworks_probe_allowed_during_screenshot_review", None)
        row.pop("ui_screenshot_review_no_solidworks_probe_pass", None)
        row.pop("side_by_side_reference_generated_layout_pass", None)
        row.pop("side_by_side_reference_generated_layout", None)
        _write_json(paths["requested"], payload)

        result = _build(paths)

        assert result["pass"] is False
        assert result["status"] == "blocked_by_requested_ref6_ui_review"
        assert result["allowed_actions"]["requested_ref6_complete"] is False
        assert result["allowed_actions"]["lb26001_36_allowed"] is False
        assert "requested_ref6_ui_status_pass" in set(result["blocking_issue_keys"])
        check = next(item for item in result["checks"] if item["key"] == "requested_ref6_ui_status_pass")
        failed = check["details"]["incomplete_required_checks_by_base"][BASE]
        assert "ui_screenshot_review_no_solidworks_probe_pass" in failed
        assert "side_by_side_reference_generated_layout_pass" in failed


def test_product_evidence_gate_blocks_ref6_complete_when_006_bucket_closure_is_missing() -> None:
    with TemporaryDirectory() as tmp:
        paths = _fixture(Path(tmp), acceptance_pass=True, requested_pass=True)
        payload = json.loads(paths["requested"].read_text(encoding="utf-8"))
        for item in payload["per_drawing_ui_review_matrix"]:
            if item.get("base") == BASE:
                item["ui_defect_bucket_closure_required"] = True
                item["ui_defect_bucket_closure_pass"] = False
                item["ui_defect_bucket_missing_keys"] = ["dimension_visual_overdense"]
                break
        _write_json(paths["requested"], payload)

        result = _build(paths)

        assert result["pass"] is False
        assert result["status"] == "blocked_by_requested_ref6_ui_review"
        assert result["allowed_actions"]["requested_ref6_complete"] is False
        assert "requested_ref6_ui_status_pass" in set(result["blocking_issue_keys"])
        check = next(item for item in result["checks"] if item["key"] == "requested_ref6_ui_status_pass")
        assert "ui_defect_bucket_closure_pass" in check["details"]["incomplete_required_checks_by_base"][BASE]
        assert check["details"]["per_base_summary"][BASE]["ui_defect_bucket_missing_keys"] == [
            "dimension_visual_overdense"
        ]


def test_product_evidence_gate_blocks_release_when_final_artifacts_are_missing() -> None:
    with TemporaryDirectory() as tmp:
        result = _build(_fixture(Path(tmp), final_artifacts=False))

        assert result["pass"] is False
        assert result["status"] == "warning_not_release_ready"
        assert result["release_ready"] is False
        assert result["allowed_actions"]["full_129_allowed"] is False
        assert "final_release_artifacts_present" in set(result["blocking_issue_keys"])


def test_product_evidence_gate_blocks_release_when_raw_issue_schema_fails() -> None:
    with TemporaryDirectory() as tmp:
        result = _build(_fixture(Path(tmp), raw_issue_schema_pass=False, normalized_issue_schema_pass=True))

        assert result["pass"] is False
        assert result["status"] == "warning_not_release_ready"
        assert result["release_ready"] is False
        assert result["allowed_actions"]["full_129_allowed"] is False
        assert "visual_audit_schema_proof_pass" in set(result["blocking_issue_keys"])
        check = next(item for item in result["checks"] if item["key"] == "visual_audit_schema_proof_pass")
        assert check["details"]["normalized_proof_is_supporting_only"] is True
        assert check["details"]["visual_audit_schema_gap"]["pass"] is False
        assert check["details"]["visual_audit_schema_gap"]["normalized_supporting_only"] is True
        assert check["details"]["visual_audit_schema_gap"]["raw_issue_backfill_overlay_ready"] is True
        assert check["details"]["visual_audit_schema_gap"]["raw_issue_backfill_overlay_cannot_replace_raw"] is True
        assert (
            check["details"]["visual_audit_schema_gap"]["raw_issue_backfill_overlay_summary"]["overlay_record_count"]
            == 7
        )


def test_product_evidence_gate_blocks_release_when_visual_audit_schema_gap_is_missing() -> None:
    with TemporaryDirectory() as tmp:
        paths = _fixture(Path(tmp))
        paths["visual_audit_schema_gap"].unlink()

        result = _build(paths)

        assert result["pass"] is False
        assert result["status"] == "warning_not_release_ready"
        assert result["release_ready"] is False
        assert result["allowed_actions"]["full_129_allowed"] is False
        assert "visual_audit_schema_proof_pass" in set(result["blocking_issue_keys"])
        check = next(item for item in result["checks"] if item["key"] == "visual_audit_schema_proof_pass")
        assert check["details"]["visual_audit_schema_gap"]["pass"] is None


def test_product_evidence_gate_blocks_release_when_visual_audit_schema_gap_counters_are_missing() -> None:
    with TemporaryDirectory() as tmp:
        result = _build(_fixture(Path(tmp), visual_audit_schema_gap_counters=False))

        assert result["pass"] is False
        assert result["status"] == "warning_not_release_ready"
        assert result["release_ready"] is False
        assert result["allowed_actions"]["full_129_allowed"] is False
        assert "visual_audit_schema_proof_pass" in set(result["blocking_issue_keys"])
        check = next(item for item in result["checks"] if item["key"] == "visual_audit_schema_proof_pass")
        counter_contract = check["details"]["visual_audit_schema_gap"]["counter_contract"]
        assert counter_contract["pass"] is False
        assert counter_contract["stale_report_without_counters_blocked"] is True
        assert counter_contract["missing_keys"] == [
            "check_count",
            "passed_check_count",
            "failed_check_count",
        ]


def test_product_evidence_gate_blocks_release_when_exe_stability_is_not_proven() -> None:
    with TemporaryDirectory() as tmp:
        paths = _fixture(Path(tmp))
        _write_json(paths["final_artifacts"]["stability_2h_ui"], {"mode": "windows_exe_navigation_stability", "pass": True, "duration_observed_s": 7100.0})  # type: ignore[index]

        result = _build(paths)

        assert result["pass"] is False
        assert result["status"] == "warning_not_release_ready"
        assert result["release_ready"] is False
        assert result["allowed_actions"]["full_129_allowed"] is False
        assert "exe_ui_and_stability_proof_pass" in set(result["blocking_issue_keys"])


def test_product_evidence_gate_blocks_when_exe_ui_text_quality_spotcheck_fails() -> None:
    with TemporaryDirectory() as tmp:
        paths = _fixture(Path(tmp))
        _write_json(
            paths["final_artifacts"]["exe_ui_text_quality_spotcheck"],  # type: ignore[index]
            {
                "schema": "sw_drawing_studio.exe_stability_2h_visual_spotcheck.v4_4",
                "status": "warning_text_quality_issue",
                "pass": False,
                "stability_json_pass": True,
                "ui_text_quality_pass": False,
                "spotchecked_screenshot": "drw_output/ui_acceptance/exe_stability_2h_v3/screenshots/final.png",
                "blocking_issue_keys": ["system_health_mojibake_in_final_screenshot"],
                "source_fix": {
                    "rebuild_required": True,
                    "rerun_2h_exe_stability_required": True,
                },
            },
        )

        result = _build(paths)

        assert result["pass"] is False
        assert result["status"] == "warning_not_release_ready"
        assert result["release_ready"] is False
        assert result["allowed_actions"]["full_129_allowed"] is False
        assert "exe_ui_and_stability_proof_pass" in set(result["blocking_issue_keys"])
        check = next(item for item in result["checks"] if item["key"] == "exe_ui_and_stability_proof_pass")
        details = check["details"]["exe_ui_text_quality_spotcheck"]
        assert details["ui_text_quality_pass"] is False
        assert details["rebuild_required"] is True


def test_product_evidence_gate_rejects_source_ui_robot_as_exe_evidence() -> None:
    with TemporaryDirectory() as tmp:
        paths = _fixture(Path(tmp))
        _write_json(paths["final_artifacts"]["exe_ui_robot_result"], {"mode": "source_qt_ui_robot", "pass": True})  # type: ignore[index]

        result = _build(paths)

        assert result["pass"] is False
        assert result["status"] == "warning_not_release_ready"
        assert result["allowed_actions"]["full_129_allowed"] is False
        assert "exe_ui_and_stability_proof_pass" in set(result["blocking_issue_keys"])


def test_product_evidence_gate_blocks_release_when_cad_smoke_is_api_only() -> None:
    with TemporaryDirectory() as tmp:
        paths = _fixture(Path(tmp))
        _write_json(
            paths["final_artifacts"]["cad_smoke"],  # type: ignore[index]
            {
                "mode": "api_only_file_presence_probe",
                "pass": True,
                "run_id": "smoke_run",
                "run_dir": "drw_output/runs/smoke_run",
                "required_artifacts": {
                    "slddrw": True,
                    "pdf": True,
                    "dxf": True,
                    "png": True,
                    "manifest": True,
                    "qc": True,
                    "vision": True,
                    "final_quality": True,
                    "sw_session": True,
                    "job_event_log": True,
                },
            },
        )

        result = _build(paths)

        assert result["pass"] is False
        assert result["status"] == "warning_not_release_ready"
        assert result["release_ready"] is False
        assert result["allowed_actions"]["full_129_allowed"] is False
        assert "cad_smoke_dimension_reference_proof_pass" in set(result["blocking_issue_keys"])
        check = next(item for item in result["checks"] if item["key"] == "cad_smoke_dimension_reference_proof_pass")
        assert check["details"]["cad_smoke"]["job_runtime_facade_proof"] is False
        assert check["details"]["cad_smoke"]["qprocess_worker_proof"] is False
        assert check["details"]["cad_smoke"]["fresh_artifact_proof"] is False


def test_product_evidence_gate_blocks_release_when_dimension_smoke_counts_notes_as_displaydim() -> None:
    with TemporaryDirectory() as tmp:
        paths = _fixture(Path(tmp))
        _write_json(
            paths["final_artifacts"]["dimension_validation_smoke"],  # type: ignore[index]
            {
                "status": "pass",
                "pass": True,
                "true_display_dim_count": 12,
                "note_as_displaydim_count": 2,
                "note_substitution_count": 0,
                "note_annotations_counted_as_displaydim": True,
            },
        )

        result = _build(paths)

        assert result["pass"] is False
        assert result["status"] == "warning_not_release_ready"
        assert result["release_ready"] is False
        assert result["allowed_actions"]["full_129_allowed"] is False
        assert "cad_smoke_dimension_reference_proof_pass" in set(result["blocking_issue_keys"])
        check = next(item for item in result["checks"] if item["key"] == "cad_smoke_dimension_reference_proof_pass")
        assert check["details"]["dimension_validation_smoke"]["note_as_displaydim_count"] == 2
        assert check["details"]["dimension_validation_smoke"]["note_annotations_counted_as_displaydim"] is True


def test_product_evidence_gate_tool_is_file_only() -> None:
    source = Path("tools/validation/product_evidence_gate_v4_4.py").read_text(encoding="utf-8")
    forbidden = [
        "win32com",
        "pythoncom",
        "GetActiveObject",
        "Dispatch(",
        "OpenDoc6",
        "subprocess.run",
        "QProcess",
    ]
    for token in forbidden:
        assert token not in source


if __name__ == "__main__":
    test_product_evidence_gate_can_pass_complete_fixture()
    test_product_evidence_gate_checks_are_boolean_machine_readable()
    test_product_evidence_gate_blocks_when_solidworks_readiness_is_blocked()
    test_product_evidence_gate_blocks_old_readiness_without_title_sampling()
    test_product_evidence_gate_blocks_ready_readiness_when_unsaved_title_was_observed()
    test_product_evidence_gate_blocks_when_raw_entrypoint_report_has_ui_risk()
    test_product_evidence_gate_blocks_when_ui_threadpool_worker_returns()
    test_product_evidence_gate_blocks_when_ui_shell_subprocess_returns()
    test_product_evidence_gate_blocks_when_ui_heavy_work_returns()
    test_product_evidence_gate_blocks_when_lock_test_report_fails()
    test_product_evidence_gate_blocks_when_conflict_report_warns()
    test_product_evidence_gate_allows_idle_solidworks_prelock_for_locked_006_only()
    test_product_evidence_gate_blocks_when_reference_intent_plan_missing_target()
    test_product_evidence_gate_blocks_when_reference_callout_lacks_evidence()
    test_product_evidence_gate_blocks_when_reference_intent_plan_uses_note_substitution()
    test_product_evidence_gate_blocks_when_reference_intent_contract_is_not_lock_owned()
    test_product_evidence_gate_blocks_locked_006_when_rerun_packet_offline_missing()
    test_product_evidence_gate_blocks_locked_006_when_rerun_packet_state_is_stale()
    test_product_evidence_gate_blocks_locked_006_when_ui_defect_buckets_are_incomplete()
    test_product_evidence_gate_blocks_locked_006_when_callout_next_screenshot_check_is_missing()
    test_product_evidence_gate_blocks_locked_006_when_bucket_closure_contract_is_missing()
    test_product_evidence_gate_blocks_locked_006_when_callout_closure_contract_is_incomplete()
    test_product_evidence_gate_blocks_locked_006_when_active_screenshot_observation_is_missing()
    test_product_evidence_gate_blocks_expansion_when_006_ui_acceptance_fails()
    test_product_evidence_gate_blocks_when_regeneration_gate_relaxes_ui_contract()
    test_product_evidence_gate_blocks_expansion_when_canonical_ui_visual_review_fails()
    test_product_evidence_gate_blocks_when_canonical_ui_bucket_closure_missing()
    test_product_evidence_gate_blocks_when_canonical_ui_side_by_side_layout_missing()
    test_product_evidence_gate_blocks_when_canonical_ui_no_probe_proof_missing()
    test_product_evidence_gate_blocks_expansion_when_canonical_ui_screenshot_missing()
    test_product_evidence_gate_blocks_expansion_when_canonical_ui_screenshot_is_not_image()
    test_product_evidence_gate_allows_ref6_expansion_only_after_006_passes()
    test_product_evidence_gate_blocks_ref6_complete_when_per_drawing_artifact_missing()
    test_product_evidence_gate_blocks_ref6_complete_when_per_drawing_screenshot_is_invalid()
    test_product_evidence_gate_blocks_ref6_complete_when_no_probe_or_side_by_side_missing()
    test_product_evidence_gate_blocks_ref6_complete_when_006_bucket_closure_is_missing()
    test_product_evidence_gate_blocks_release_when_final_artifacts_are_missing()
    test_product_evidence_gate_blocks_release_when_raw_issue_schema_fails()
    test_product_evidence_gate_blocks_release_when_visual_audit_schema_gap_is_missing()
    test_product_evidence_gate_blocks_release_when_visual_audit_schema_gap_counters_are_missing()
    test_product_evidence_gate_blocks_release_when_exe_stability_is_not_proven()
    test_product_evidence_gate_blocks_when_exe_ui_text_quality_spotcheck_fails()
    test_product_evidence_gate_rejects_source_ui_robot_as_exe_evidence()
    test_product_evidence_gate_blocks_release_when_cad_smoke_is_api_only()
    test_product_evidence_gate_blocks_release_when_dimension_smoke_counts_notes_as_displaydim()
    test_product_evidence_gate_tool_is_file_only()
    print("PASS test_v4_4_product_evidence_gate")
