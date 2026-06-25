import json
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.validation.lb26001_006_displaydim_lifecycle_audit_v4_2 import build_lifecycle_audit


def _write(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _cad_smoke(root: Path) -> Path:
    return _write(
        root / "cad_smoke.json",
        {
            "status": {
                "result": {
                    "reference_intent_dimension": {
                        "required_display_dim_count": 12,
                    }
                }
            }
        },
    )


def _dimension_validation(root: Path, count: int) -> Path:
    return _write(root / "dimension_validation.json", {"display_dim_count": count})


def _reference_plan(root: Path) -> Path:
    return _write(
        root / "reference_intent_dimension_plan_006.json",
        {
            "dimensions": [
                {
                    "key": "overall_length",
                    "target_key": "overall_length",
                    "group": "overall_envelope",
                    "target_view": "front",
                    "expected_type": "linear_horizontal",
                    "expected_add_method": "AddHorizontalDimension2",
                    "priority": 10,
                    "required": True,
                },
                {
                    "key": "hole_pitch",
                    "target_key": "hole_pitch",
                    "group": "hole_locations",
                    "target_view": "top",
                    "expected_type": "linear_horizontal",
                    "expected_add_method": "AddHorizontalDimension2",
                    "priority": 33,
                    "required": True,
                },
            ]
        },
    )


def _coverage(stage: str, *, persisted_after_reopen: bool = False) -> dict:
    return {
        "stage": stage,
        "target_count": 2,
        "covered_count": 2,
        "covered_target_keys": ["overall_length", "hole_pitch"],
        "missing_target_keys": [],
        "persisted_after_reopen": persisted_after_reopen,
        "target_results": [
            {
                "target_key": "overall_length",
                "matched_count": 1,
                "persisted_after_reopen": persisted_after_reopen,
            },
            {
                "target_key": "hole_pitch",
                "matched_count": 1,
                "persisted_after_reopen": persisted_after_reopen,
            },
        ],
    }


def _strict_blueprint() -> dict:
    return {
        "dimension_plan": {
            "reasons": ["explicit_dimension_targets_replace_generic_autodimension_acceptance"],
            "allow_note_substitution": False,
            "dimension_targets": [
                {"target_key": "overall_length"},
                {"target_key": "hole_pitch"},
            ],
        }
    }


def _slot_rebind_summary(*, bound: bool = True) -> dict:
    slots = ["front", "top"]
    return {
        "expected_slots": slots,
        "bound_slots": slots if bound else ["front"],
        "unbound_slots": [] if bound else ["top"],
        "current_view_record_count": 2,
        "persisted_view_record_count": 0,
        "match_threshold": 0.05,
        "slot_results": {
            "front": {
                "bound": True,
                "reason": "bound",
                "source": "current_doc_views",
                "layout_center_present": True,
                "nearest_candidates": [{"view_name": "Drawing View1", "distance": 0.0}],
            },
            "top": {
                "bound": bound,
                "reason": "bound" if bound else "all_rebind_attempts_failed",
                "source": "current_doc_views" if bound else "",
                "layout_center_present": True,
                "nearest_candidates": [{"view_name": "Drawing View3", "distance": 0.012}],
            },
        },
    }


def _passing_warnings(root: Path) -> Path:
    run_dir = root / "runs" / "pass_006"
    drawing_path = run_dir / "drawing" / "LB26001-A-04-006.SLDDRW"
    return _write(
        root / "warnings.json",
        {
            "drawing_blueprint_v4": _strict_blueprint(),
            "reference_autodim": {"before": 11, "after": 12},
            "reference_dim_prune": {"prune": {"before": 12, "after": 12}},
            "post_prune_dim_guard": {
                "attempted": False,
                "before": 12,
                "after": 12,
                "repair_reason": "",
                "target_coverage_after_guard": {"missing_target_keys": []},
                "missing_target_keys_after_guard": [],
            },
            "display_dim_count_before_sidecar": 12,
            "display_dim_count_final": 12,
            "dimension_sidecar_mode": {
                "run_sidecar": False,
                "diagnostic_only": True,
                "reason": "reference_intent_sidecar_not_allowed_for_acceptance",
            },
            "warnings": [
                {
                    "code": "reference_intent_dimension_sidecar_diagnostic_only",
                    "drawing_path": str(drawing_path),
                    "run_dir": str(run_dir),
                    "diagnostic_only": True,
                    "acceptance_allowed": False,
                }
            ],
            "reference_intent_target_coverage": [
                _coverage("pre_saveas"),
                _coverage("post_saveas_reopen_prune"),
                _coverage("post_saveas_reopen_prune_guard", persisted_after_reopen=True),
                _coverage("pre_export_final", persisted_after_reopen=True),
                _coverage("post_layout_final", persisted_after_reopen=True),
            ],
            "reference_intent_target_coverage_delta": {"target_count": 12},
            "post_layout_dim_repair": {
                "attempted": True,
                "before": 12,
                "after": 12,
                "explicit_display_dims": {
                    "attempted": True,
                    "before": 12,
                    "after": 12,
                    "created": 0,
                    "target_results": [
                        {
                            "key": "overall_length",
                            "slot": "front",
                            "success": True,
                            "display_dim_count_before_target": 0,
                            "after": 12,
                            "target_covered_after_attempt": True,
                            "persisted_after_reopen": True,
                            "attempts": [
                                {
                                    "selected": True,
                                    "curve_identity": {"kind": "line", "id": "edge-1"},
                                    "add_method": "AddHorizontalDimension2",
                                    "before": 0,
                                    "after": 12,
                                    "target_covered_after_attempt": True,
                                }
                            ],
                        },
                        {
                            "key": "hole_pitch",
                            "slot": "top",
                            "success": True,
                            "display_dim_count_before_target": 12,
                            "after": 12,
                            "target_covered_after_attempt": True,
                            "persisted_after_reopen": True,
                            "attempts": [
                                {
                                    "selected": True,
                                    "curve_identity": {"kind": "line", "id": "edge-2"},
                                    "add_method": "AddHorizontalDimension2",
                                    "before": 12,
                                    "after": 12,
                                    "target_covered_after_attempt": True,
                                }
                            ],
                        },
                    ],
                    "slot_rebind_diagnostics": [{"slot": "front", "accepted": True}],
                    "slot_rebind_summary": _slot_rebind_summary(),
                    "slot_view_sources": {"front": "current_doc_views"},
                },
                "final_acceptance_blockers": [],
            },
        },
    )


def test_displaydim_lifecycle_audit_passes_complete_persistent_chain() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        result = build_lifecycle_audit(
            warnings_path=_passing_warnings(root),
            cad_smoke_path=_cad_smoke(root),
            dimension_validation_path=_dimension_validation(root, 12),
            reference_intent_plan_path=_reference_plan(root),
            out_json=root / "audit.json",
            out_md=root / "audit.md",
        )

    assert result["status"] == "pass"
    assert result["pass"] is True
    assert result["blocking_issue_keys"] == []
    assert result["loss_events"] == []
    assert result["coverage_summary"]["post_prune_guard_present"] is True
    assert result["post_prune_guard_summary"]["target_coverage_after_guard_present"] is True
    assert result["post_layout_repair_summary"]["direct_accept_failed_count"] == 0
    assert result["post_layout_repair_summary"]["slot_rebind_summary_present"] is True
    assert result["post_layout_repair_summary"]["slot_rebind_unbound_slots"] == []
    assert result["target_stage_matrix"]["pass"] is True
    assert result["target_stage_matrix"]["post_layout_final_missing_target_keys"] == []
    assert result["target_stage_matrix"]["target_trace_incomplete_keys"] == []
    assert result["sidecar_policy_summary"]["pass"] is True
    assert result["sidecar_policy_summary"]["strict_reference_intent"] is True


def test_displaydim_lifecycle_audit_uses_restored_count_for_discarded_prune() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        warnings_path = _passing_warnings(root)
        payload = json.loads(warnings_path.read_text(encoding="utf-8"))
        prune = payload["reference_dim_prune"]["prune"]
        prune["before"] = 15
        prune["after"] = 11
        prune["success"] = False
        prune["discarded_after_failed_prune"] = True
        prune["after_restored"] = 12
        warnings_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        result = build_lifecycle_audit(
            warnings_path=warnings_path,
            cad_smoke_path=_cad_smoke(root),
            dimension_validation_path=_dimension_validation(root, 12),
            reference_intent_plan_path=_reference_plan(root),
            out_json=root / "audit.json",
            out_md=root / "audit.md",
        )

    prune_after = next(
        item for item in result["stage_counts"]
        if item["stage"] == "post_saveas_reopen_prune_after"
    )
    assert result["status"] == "pass"
    assert prune_after["display_dim_count"] == 12
    assert prune_after["source"] == "warnings.reference_dim_prune.prune.after_restored"
    assert "display_dim_lifecycle_count_regression" not in result["blocking_issue_keys"]


def test_displaydim_lifecycle_audit_accepts_existing_final_displaydim_coverage_trace() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        warnings_path = _passing_warnings(root)
        payload = json.loads(warnings_path.read_text(encoding="utf-8"))
        target_results = payload["post_layout_dim_repair"]["explicit_display_dims"]["target_results"]
        payload["post_layout_dim_repair"]["explicit_display_dims"]["target_results"] = [
            item for item in target_results if item.get("key") == "overall_length"
        ]
        warnings = _write(root / "warnings_existing_coverage.json", payload)
        result = build_lifecycle_audit(
            warnings_path=warnings,
            cad_smoke_path=_cad_smoke(root),
            dimension_validation_path=_dimension_validation(root, 12),
            reference_intent_plan_path=_reference_plan(root),
        )

    assert result["status"] == "pass"
    assert result["pass"] is True
    assert result["target_stage_matrix"]["target_trace_incomplete_keys"] == []
    hole_row = next(
        item
        for item in result["target_stage_matrix"]["rows"]
        if item["target_key"] == "hole_pitch"
    )
    assert hole_row["trace"]["trace_source"] == "existing_display_dim_coverage"
    assert hole_row["trace"]["add_method"] == "existing_display_dim_coverage"
    assert hole_row["trace"]["explicit_add_trace_required"] is False


def test_displaydim_lifecycle_audit_finds_prune_to_sidecar_regression() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        warnings = _write(
            root / "warnings.json",
            {
                "drawing_blueprint_v4": _strict_blueprint(),
                "reference_autodim": {"before": 12, "after": 12},
                "reference_dim_prune": {"prune": {"before": 15, "after": 14, "deleted": 1}},
                "display_dim_count_before_sidecar": 11,
                "display_dim_count_final": 11,
                "warnings": [
                    {
                        "code": "dim_sidecar_fail",
                        "msg": "error: cannot activate/open drawing",
                        "fallback_mode": "python_invoke_member",
                    }
                ],
                "post_layout_dim_repair": {
                    "attempted": True,
                    "before": 11,
                    "after": 11,
                    "explicit_display_dims": {
                        "attempted": True,
                        "before": 11,
                        "after": 11,
                        "created": 0,
                        "slot_rebind_summary": _slot_rebind_summary(bound=False),
                        "target_results": [
                            {"key": "overall_length", "reason": "target_view_not_found"},
                            {"key": "hole_pitch", "reason": "target_view_not_found"},
                        ],
                    },
                },
            },
        )
        result = build_lifecycle_audit(
            warnings_path=warnings,
            cad_smoke_path=_cad_smoke(root),
            dimension_validation_path=_dimension_validation(root, 11),
            reference_intent_plan_path=_reference_plan(root),
        )

    keys = set(result["blocking_issue_keys"])
    assert result["status"] == "fail"
    assert "final_display_dim_below_reference_floor" in keys
    assert "display_dim_lost_between_prune_and_sidecar" in keys
    assert "display_dim_lifecycle_count_regression" in keys
    assert "post_layout_target_view_not_found" in keys
    assert "post_layout_slot_rebind_diagnostics_missing" in keys
    assert "post_prune_guard_missing" in keys
    assert "prune_deleted_items_detail_missing" in keys
    assert "target_stage_matrix_snapshot_missing" in keys
    assert "target_trace_missing_fields" in keys
    assert "target_stage_matrix_view_not_found" in keys
    assert "strict_reference_intent_sidecar_mode_missing" in keys
    assert "strict_reference_intent_sidecar_ran" in keys
    assert "sidecar_drawing_path_missing" in keys
    assert "post_layout_slot_rebind_unbound_slots" in keys
    assert result["target_stage_matrix"]["target_view_not_found_keys"] == ["overall_length", "hole_pitch"]
    assert result["sidecar_policy_summary"]["run_event_codes"] == ["dim_sidecar_fail"]
    assert result["post_layout_repair_summary"]["slot_rebind_unbound_slots"] == ["top"]
    assert any(
        item["from_stage"] == "post_saveas_reopen_prune_after"
        and item["to_stage"] == "before_sidecar_diagnostic"
        for item in result["loss_events"]
    )


def test_displaydim_lifecycle_audit_rejects_sidecar_evidence_from_stale_path() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        warnings_path = _passing_warnings(root)
        payload = json.loads(warnings_path.read_text(encoding="utf-8"))
        payload["warnings"] = [
            {
                "code": "reference_intent_dimension_sidecar_diagnostic_only",
                "drawing_path": r"C:\Users\Vision\Desktop\SW 相关\drw_output\v5\LB26001-A-04-006.SLDDRW",
                "run_dir": str(root / "runs" / "fresh_006"),
                "diagnostic_only": True,
                "acceptance_allowed": False,
            }
        ]
        warnings = _write(root / "warnings_stale_sidecar.json", payload)
        result = build_lifecycle_audit(
            warnings_path=warnings,
            cad_smoke_path=_cad_smoke(root),
            dimension_validation_path=_dimension_validation(root, 12),
            reference_intent_plan_path=_reference_plan(root),
        )

    keys = set(result["blocking_issue_keys"])
    assert result["pass"] is False
    assert "sidecar_drawing_path_not_current_run" in keys
    assert result["sidecar_policy_summary"]["pass"] is False


def test_displaydim_lifecycle_audit_requires_prune_deleted_item_key_slot_reason() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        warnings = _write(
            root / "warnings.json",
            {
                "reference_autodim": {"before": 12, "after": 12},
                "reference_dim_prune": {
                    "prune": {
                        "before": 13,
                        "after": 12,
                        "deleted": 1,
                        "deleted_items": [
                            {
                                "target_key": "hole_pitch",
                                "slot": "top",
                            }
                        ],
                    }
                },
                "post_prune_dim_guard": {
                    "attempted": False,
                    "before": 12,
                    "after": 12,
                    "target_coverage_after_guard": {"missing_target_keys": []},
                    "missing_target_keys_after_guard": [],
                    "explicit_display_dims": {"slot_rebind_diagnostics": [{"slot": "top"}]},
                },
                "display_dim_count_before_sidecar": 12,
                "display_dim_count_final": 12,
                "reference_intent_target_coverage": [
                    _coverage("pre_saveas"),
                    _coverage("post_saveas_reopen_prune", persisted_after_reopen=True),
                    _coverage("post_saveas_reopen_prune_guard", persisted_after_reopen=True),
                    _coverage("pre_export_final", persisted_after_reopen=True),
                    _coverage("post_layout_final", persisted_after_reopen=True),
                ],
                "reference_intent_target_coverage_delta": {"target_count": 2},
                "post_layout_dim_repair": {
                    "attempted": True,
                    "before": 12,
                    "after": 12,
                    "explicit_display_dims": {
                        "attempted": True,
                        "created": 0,
                        "target_results": [
                            {
                                "target_key": "overall_length",
                                "view_slot": "front",
                                "selected_entity": "edge-1",
                                "add_method": "AddHorizontalDimension2",
                                "display_dim_count_before": 12,
                                "display_dim_count_after": 12,
                                "target_covered_after_attempt": True,
                                "persisted_after_reopen": True,
                                "success": True,
                            },
                            {
                                "target_key": "hole_pitch",
                                "view_slot": "top",
                                "selected_entity": "edge-2",
                                "add_method": "AddHorizontalDimension2",
                                "display_dim_count_before": 12,
                                "display_dim_count_after": 12,
                                "target_covered_after_attempt": True,
                                "persisted_after_reopen": True,
                                "success": True,
                            },
                        ],
                        "slot_rebind_diagnostics": [{"slot": "front", "accepted": True}],
                        "slot_rebind_summary": _slot_rebind_summary(),
                        "slot_view_sources": {"front": "current_doc_views"},
                    },
                    "final_acceptance_blockers": [],
                },
            },
        )
        result = build_lifecycle_audit(
            warnings_path=warnings,
            cad_smoke_path=_cad_smoke(root),
            dimension_validation_path=_dimension_validation(root, 12),
            reference_intent_plan_path=_reference_plan(root),
        )

    keys = set(result["blocking_issue_keys"])
    assert result["pass"] is False
    assert "prune_deleted_item_key_slot_reason_missing" in keys
    assert result["prune_log_summary"]["missing_required_field_items"][0]["missing_fields"] == ["reason"]


def test_displaydim_lifecycle_audit_requires_final_coverage_snapshot_and_diagnostics() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        warnings = _write(
            root / "warnings.json",
            {
                "reference_autodim": {"before": 12, "after": 12},
                "reference_dim_prune": {"prune": {"before": 12, "after": 12}},
                "post_prune_dim_guard": {
                    "attempted": True,
                    "before": 11,
                    "after": 11,
                    "repair_reason": "display_dim_floor_gap",
                    "explicit_display_dims": {"created": 0},
                    "missing_target_keys_after_repair": ["hole_pitch"],
                    "target_coverage_after_guard": {"missing_target_keys": ["hole_pitch"]},
                    "missing_target_keys_after_guard": ["hole_pitch"],
                },
                "display_dim_count_before_sidecar": 12,
                "display_dim_count_final": 12,
                "reference_intent_target_coverage": [{"stage": "pre_saveas", "missing_target_keys": []}],
                "post_layout_dim_repair": {
                    "attempted": True,
                    "before": 12,
                    "after": 12,
                    "explicit_display_dims": {
                        "attempted": True,
                        "created": 0,
                        "target_results": [],
                        "slot_rebind_summary": {
                            "expected_slots": ["front", "top"],
                            "bound_slots": [],
                            "unbound_slots": ["front", "top"],
                            "current_view_record_count": 0,
                            "persisted_view_record_count": 0,
                            "slot_results": {
                                "front": {"bound": False, "reason": "no_view_records"},
                                "top": {"bound": False, "reason": "no_view_records"},
                            },
                        },
                    },
                },
            },
        )
        result = build_lifecycle_audit(
            warnings_path=warnings,
            cad_smoke_path=_cad_smoke(root),
            dimension_validation_path=_dimension_validation(root, 12),
            reference_intent_plan_path=_reference_plan(root),
        )

    keys = set(result["blocking_issue_keys"])
    assert result["pass"] is False
    assert "post_layout_final_target_coverage_missing" in keys
    assert "target_coverage_delta_missing" in keys
    assert "post_layout_slot_rebind_diagnostics_missing" in keys
    assert "post_layout_slot_rebind_unbound_slots" in keys
    assert "post_layout_slot_rebind_no_view_records" in keys
    assert "post_prune_guard_still_below_reference_floor" in keys
    assert "post_prune_guard_targets_still_missing" in keys
    assert "post_prune_guard_slot_rebind_diagnostics_missing" in keys
    assert "post_prune_guard_target_coverage_missing" not in keys


def test_displaydim_lifecycle_audit_reports_direct_accept_rebind_recovery_and_failure() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        warnings = _write(
            root / "warnings.json",
            {
                "reference_autodim": {"before": 12, "after": 12},
                "reference_dim_prune": {"prune": {"before": 12, "after": 12}},
                "post_prune_dim_guard": {
                    "attempted": False,
                    "before": 12,
                    "after": 12,
                    "target_coverage_after_guard": {"missing_target_keys": []},
                    "missing_target_keys_after_guard": [],
                },
                "display_dim_count_before_sidecar": 11,
                "display_dim_count_final": 11,
                "reference_intent_target_coverage": [
                    {"stage": "pre_saveas", "missing_target_keys": []},
                    {"stage": "post_saveas_reopen_prune_guard", "missing_target_keys": []},
                    {"stage": "post_layout_final", "missing_target_keys": ["hole_pitch"]},
                ],
                "reference_intent_target_coverage_delta": {"lost_target_keys": ["hole_pitch"]},
                "post_layout_dim_repair": {
                    "attempted": True,
                    "before": 11,
                    "after": 11,
                    "explicit_display_dims": {
                        "attempted": True,
                        "before": 11,
                        "after": 11,
                        "created": 0,
                        "target_results": [],
                        "slot_rebind_diagnostics": [
                            {
                                "slot": "front",
                                "view_name": "Drawing View1",
                                "accepted": True,
                                "direct_accept_failed": True,
                                "source": "current_doc_layout_match|direct_accept_failed_select_by_persisted_name",
                                "distance": 0.002,
                            },
                            {
                                "slot": "right",
                                "view_name": "Drawing View3",
                                "accepted": False,
                                "direct_accept_failed": True,
                                "source": "current_doc_layout_match|direct_accept_failed_select_by_persisted_name_failed",
                                "distance": 0.004,
                            },
                        ],
                        "slot_rebind_summary": {
                            "expected_slots": ["front", "right"],
                            "bound_slots": ["front"],
                            "unbound_slots": ["right"],
                            "current_view_record_count": 2,
                            "persisted_view_record_count": 1,
                            "slot_results": {
                                "front": {"bound": True, "reason": "bound"},
                                "right": {
                                    "bound": False,
                                    "reason": "all_rebind_attempts_failed",
                                    "nearest_candidates": [{"view_name": "Drawing View3", "distance": 0.004}],
                                },
                            },
                        },
                        "slot_view_sources": {"front": "current_doc_layout_match", "right": "current_doc_layout_match"},
                    },
                },
            },
        )
        result = build_lifecycle_audit(
            warnings_path=warnings,
            cad_smoke_path=_cad_smoke(root),
            dimension_validation_path=_dimension_validation(root, 11),
            reference_intent_plan_path=_reference_plan(root),
        )

    summary = result["post_layout_repair_summary"]
    keys = set(result["blocking_issue_keys"])
    assert summary["slot_rebind_diagnostic_count"] == 2
    assert summary["direct_accept_failed_count"] == 2
    assert summary["direct_accept_recovered_by_persisted_name_count"] == 1
    assert summary["direct_accept_persisted_name_failed_count"] == 1
    assert summary["direct_accept_rebind_details"][0]["slot"] == "front"
    assert summary["slot_rebind_unbound_slots"] == ["right"]
    assert "post_layout_direct_accept_rebind_unrecovered" in keys


def test_displaydim_lifecycle_audit_reports_live_view_recovery_failure() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        warnings = _write(
            root / "warnings.json",
            {
                "drawing_blueprint_v4": _strict_blueprint(),
                "reference_autodim": {"before": 12, "after": 12},
                "reference_dim_prune": {"prune": {"before": 12, "after": 12}},
                "post_prune_dim_guard": {
                    "attempted": False,
                    "before": 12,
                    "after": 12,
                    "target_coverage_after_guard": {"missing_target_keys": []},
                    "missing_target_keys_after_guard": [],
                },
                "display_dim_count_before_sidecar": 12,
                "display_dim_count_final": 11,
                "reference_intent_target_coverage": [
                    _coverage("pre_saveas"),
                    _coverage("post_saveas_reopen_prune", persisted_after_reopen=True),
                    _coverage("post_saveas_reopen_prune_guard", persisted_after_reopen=True),
                    _coverage("pre_export_final", persisted_after_reopen=True),
                    {
                        **_coverage("post_layout_final", persisted_after_reopen=True),
                        "covered_count": 1,
                        "covered_target_keys": ["overall_length"],
                        "missing_target_keys": ["hole_pitch"],
                    },
                ],
                "reference_intent_target_coverage_delta": {"target_count": 2},
                "post_layout_dim_repair": {
                    "attempted": True,
                    "before": 12,
                    "after": 12,
                    "created_views_refresh": {
                        "current_doc_view_count": 1,
                        "getviews_count": 0,
                        "current_sheet_getviews_count": 0,
                        "record_count": 0,
                        "unbound_slots": ["front", "top"],
                    },
                    "explicit_display_dims": {
                        "attempted": True,
                        "before": 12,
                        "after": 12,
                        "created": 0,
                        "live_view_recovery_failed": True,
                        "unbound_slots": ["front", "top"],
                        "target_results": [
                            {
                                "target_key": "hole_pitch",
                                "view_slot": "top",
                                "reason": "post_layout_live_view_recovery_failed",
                                "selected_entity": None,
                                "add_method": "",
                                "display_dim_count_before": 12,
                                "display_dim_count_after": 12,
                                "target_covered_after_attempt": False,
                                "persisted_after_reopen": False,
                                "success": False,
                            }
                        ],
                        "slot_rebind_diagnostics": [{"slot": "top", "accepted": False}],
                        "slot_rebind_summary": _slot_rebind_summary(bound=False),
                    },
                },
            },
        )
        out_md = root / "audit.md"
        result = build_lifecycle_audit(
            warnings_path=warnings,
            cad_smoke_path=_cad_smoke(root),
            dimension_validation_path=_dimension_validation(root, 11),
            reference_intent_plan_path=_reference_plan(root),
            out_md=out_md,
        )
        md_text = out_md.read_text(encoding="utf-8")

    summary = result["post_layout_repair_summary"]
    keys = set(result["blocking_issue_keys"])
    assert summary["live_view_recovery_failed"] is True
    assert summary["current_doc_view_count"] == 1
    assert summary["getviews_count"] == 0
    assert summary["current_sheet_getviews_count"] == 0
    assert "post_layout_live_view_recovery_failed" in keys
    assert "Live view recovery failed" in md_text


if __name__ == "__main__":
    test_displaydim_lifecycle_audit_passes_complete_persistent_chain()
    test_displaydim_lifecycle_audit_finds_prune_to_sidecar_regression()
    test_displaydim_lifecycle_audit_rejects_sidecar_evidence_from_stale_path()
    test_displaydim_lifecycle_audit_requires_prune_deleted_item_key_slot_reason()
    test_displaydim_lifecycle_audit_requires_final_coverage_snapshot_and_diagnostics()
    test_displaydim_lifecycle_audit_reports_direct_accept_rebind_recovery_and_failure()
    test_displaydim_lifecycle_audit_reports_live_view_recovery_failure()
    print("PASS test_v4_2_lb26001_006_displaydim_lifecycle_audit")
