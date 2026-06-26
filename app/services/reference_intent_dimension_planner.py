from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REFERENCE_PROFILES = REPO_ROOT / "drw_output" / "reference_style_profile" / "reference_profiles_v4.json"
DEFAULT_OUT_006 = REPO_ROOT / "drw_output" / "reference_intent_dimension_plan_006.json"
SCHEMA = "sw_drawing_studio.reference_intent_dimension_plan.v4_4"
TRACE_REQUIRED_FIELDS = [
    "target_key",
    "view_slot",
    "selected_entity",
    "add_method",
    "display_dim_count_before",
    "display_dim_count_after",
    "target_covered_after_attempt",
    "persisted_after_reopen",
]
TRACE_REQUIRED_STAGES = [
    "pre_saveas",
    "post_saveas_reopen_prune",
    "pre_export_final",
    "post_layout_final",
]


def load_reference_profile(base: str, profiles_path: Path | str = DEFAULT_REFERENCE_PROFILES) -> dict[str, Any]:
    data = json.loads(Path(profiles_path).read_text(encoding="utf-8-sig"))
    profile = (data.get("profiles") or {}).get(base)
    if not isinstance(profile, dict):
        raise KeyError(f"reference profile not found for {base}")
    return profile


def build_reference_intent_dimension_plan(
    base: str,
    *,
    reference_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    profile = reference_profile or load_reference_profile(base)
    source_reference = str(profile.get("source_reference") or "")
    reference_display_dim_count = _int(profile.get("display_dim_count"))
    view_slots = _semantic_view_slots(profile.get("view_positions") or [])

    if base == "LB26001-A-04-006":
        dimensions = _lb26001_006_dimensions(source_reference)
        required_count = max(12, reference_display_dim_count, len(dimensions))
        dimension_groups = _lb26001_006_groups()
        reference_layout_policy = _lb26001_006_reference_layout_policy(profile, view_slots, source_reference)
    else:
        dimensions = _generic_dimensions(base, source_reference)
        required_count = max(reference_display_dim_count, len(dimensions))
        dimension_groups = _generic_groups(dimensions)
        reference_layout_policy = {}

    plan = {
        "schema": SCHEMA,
        "version": "v4.4",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "base": base,
        "source_reference": source_reference,
        "reference_display_dim_count": reference_display_dim_count,
        "required_display_dim_count": required_count,
        "allow_note_substitution": False,
        "api_is_supporting_only": True,
        "ui_screenshot_acceptance_required": True,
        "reference_view_slots": view_slots,
        "reference_layout_policy": reference_layout_policy,
        "view_plan": reference_layout_policy.get("view_plan", []),
        "layout_plan": reference_layout_policy.get("layout_plan", {}),
        "ui_defect_repair_layout_targets": reference_layout_policy.get("ui_defect_repair_layout_targets", {}),
        "reference_extraction": _reference_extraction_summary(base, source_reference, reference_display_dim_count),
        "dimension_groups": dimension_groups,
        "dimensions": dimensions,
        "reference_callouts": _reference_callouts(base, source_reference),
        "acceptance_trace_requirements": {
            "required_fields": list(TRACE_REQUIRED_FIELDS),
            "required_stages": list(TRACE_REQUIRED_STAGES),
            "final_stage_required": "post_layout_final",
            "all_dimension_targets_must_persist_after_reopen": True,
            "generic_autodimension_acceptance_allowed": False,
        },
        "fallback_policy": "need_review_when_real_displaydim_unavailable",
        "status": "plan_ready_requires_cad_worker_lock",
        "reasons": [
            "reference_intent_dimensions_replace_generic_autodimension",
            "notes_do_not_count_as_display_dim",
            "ui_screenshot_review_is_final_gate",
        ],
    }
    _validate_plan(plan)
    return plan


def write_reference_intent_dimension_plan(plan: dict[str, Any], path: Path | str = DEFAULT_OUT_006) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def _lb26001_006_dimensions(source_reference: str) -> list[dict[str, Any]]:
    dims = [
        ("overall_length", "overall_envelope", "front", "linear_horizontal", "above", 10),
        ("overall_width", "overall_envelope", "top", "linear_vertical", "right", 11),
        ("overall_height", "overall_envelope", "right", "linear_vertical", "right", 12),
        ("left_end_offset", "end_offsets", "top", "linear_horizontal", "below", 20),
        ("right_end_offset", "end_offsets", "top", "linear_horizontal", "below", 21),
        ("hole_diameter", "hole_locations", "top", "diameter", "callout_right", 30),
        ("hole_x_location", "hole_locations", "top", "linear_horizontal", "above", 31),
        ("hole_y_location", "hole_locations", "top", "linear_vertical", "callout_right", 32),
        ("hole_pitch", "hole_locations", "top", "linear_horizontal", "above", 33),
        ("projection_view_width", "small_projected_view", "right", "linear_horizontal", "above", 40),
        ("projection_view_height", "small_projected_view", "right", "linear_vertical", "right", 41),
        ("small_feature_location", "small_projected_view", "right", "linear_vertical", "left", 42),
    ]
    return [
        _dimension_record(
            key=key,
            group=group,
            source_reference=source_reference,
            target_view=target_view,
            expected_type=expected_type,
            preferred_side=preferred_side,
            priority=priority,
        )
        for key, group, target_view, expected_type, preferred_side, priority in dims
    ]


def _lb26001_006_groups() -> list[dict[str, Any]]:
    return [
        {
            "key": "overall_envelope",
            "label": "overall length/width/height",
            "reading_order": 1,
            "placement_policy": "outside_view_envelope_lanes",
            "target_views": ["front", "top", "right"],
            "required_count": 3,
            "source_reference_rule": "match same-name 006 envelope dimensions",
        },
        {
            "key": "end_offsets",
            "label": "left and right end offsets",
            "reading_order": 2,
            "placement_policy": "below_long_axis_and_separated_by_station",
            "target_views": ["top"],
            "required_count": 2,
            "source_reference_rule": "keep end-offset dimensions outside the long top view",
        },
        {
            "key": "hole_locations",
            "label": "hole diameter and center locations",
            "reading_order": 3,
            "placement_policy": "compact_callout_and_pitch_lanes_near_top_view",
            "target_views": ["top"],
            "required_count": 4,
            "source_reference_rule": "group hole callouts into the compact right-side leader lane seen in the same-name reference",
        },
        {
            "key": "small_projected_view",
            "label": "right-side projected view size and small-feature location",
            "reading_order": 4,
            "placement_policy": "local_lanes_around_projected_right_view",
            "target_views": ["right"],
            "required_count": 3,
            "source_reference_rule": "dimension the small projection without replacing it with a named view",
        },
        {
            "key": "radius_chamfer_thread",
            "label": "radius/chamfer/thread callouts when detected",
            "reading_order": 5,
            "placement_policy": "only_when_geometry_or_reference_proves_feature",
            "target_views": ["front", "top", "right"],
            "required_count": 0,
            "optional": True,
            "source_reference_rule": "add only when geometry/reference notes prove the feature is present",
        },
    ]


def _generic_dimensions(base: str, source_reference: str) -> list[dict[str, Any]]:
    return [
        _dimension_record(
            key="overall_length",
            group="overall_envelope",
            source_reference=source_reference,
            target_view="front",
            expected_type="linear_horizontal",
            preferred_side="above",
            priority=10,
        ),
        _dimension_record(
            key="overall_width",
            group="overall_envelope",
            source_reference=source_reference,
            target_view="front",
            expected_type="linear_vertical",
            preferred_side="left",
            priority=11,
        ),
    ]


def _generic_groups(dimensions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "key": "overall_envelope",
            "label": "overall envelope",
            "target_views": sorted({str(item.get("target_view")) for item in dimensions}),
            "required_count": len(dimensions),
            "source_reference_rule": "fallback until a same-name reference-intent plan is authored",
        }
    ]


def _dimension_record(
    *,
    key: str,
    group: str,
    source_reference: str,
    target_view: str,
    expected_type: str,
    preferred_side: str,
    priority: int,
) -> dict[str, Any]:
    expected_add_method = _expected_add_method(expected_type)
    reference_evidence = _reference_evidence_for_dimension(
        key=key,
        source_reference=source_reference,
        target_view=target_view,
        expected_type=expected_type,
    )
    drafting_logic = _drafting_logic_for_target(
        key=key,
        group=group,
        target_view=target_view,
        expected_type=expected_type,
        preferred_side=preferred_side,
        priority=priority,
    )
    return {
        "key": key,
        "target_key": key,
        "group": group,
        "functional_role": drafting_logic["functional_role"],
        "reading_group": drafting_logic["reading_group"],
        "readability_group": drafting_logic["readability_group"],
        "manufacturing_story_role": drafting_logic["manufacturing_story_role"],
        "source_reference": source_reference,
        "target_view": target_view,
        "expected_type": expected_type,
        "is_manufacturing_dimension": True,
        "reference_value": reference_evidence["reference_value"],
        "reference_value_unit": reference_evidence["reference_value_unit"],
        "reference_value_status": reference_evidence["reference_value_status"],
        "source_reference_evidence": reference_evidence,
        "expected_add_method": expected_add_method,
        "preferred_side": preferred_side,
        "placement_lane": drafting_logic["placement_lane"],
        "allowed_witness_entity": drafting_logic["allowed_witness_entity"],
        "prune_protection_policy": drafting_logic["prune_protection_policy"],
        "priority": priority,
        "required": True,
        "create_as": "SolidWorks DisplayDim",
        "fallback_policy": "need_review_when_real_displaydim_unavailable",
        "forbid_note_substitution": True,
        "avoid_generic_model_annotation": True,
        "generic_autodimension_acceptance_allowed": False,
        "trace_required_fields": list(TRACE_REQUIRED_FIELDS),
        "acceptance_trace": {
            "must_record_target_key": True,
            "must_record_view_slot": True,
            "must_record_selected_entity": True,
            "must_record_add_method": expected_add_method,
            "must_record_before_after_count": True,
            "must_prove_target_covered_after_attempt": True,
            "must_persist_after_reopen": True,
            "final_required_stage": "post_layout_final",
        },
        "ui_visual_checklist_items": [
            "reference_match",
            "display_dimensions",
            "dimension_readability",
        ],
    }


def _drafting_logic_for_target(
    *,
    key: str,
    group: str,
    target_view: str,
    expected_type: str,
    preferred_side: str,
    priority: int,
) -> dict[str, Any]:
    group_reading_order = {
        "overall_envelope": "01_overall_envelope",
        "end_offsets": "02_end_offsets",
        "hole_locations": "03_hole_locations",
        "small_projected_view": "04_small_projected_view",
    }
    functional_roles = {
        "overall_length": "overall_envelope_length",
        "overall_width": "overall_envelope_width",
        "overall_height": "overall_envelope_height",
        "left_end_offset": "left_end_machining_stop",
        "right_end_offset": "right_end_machining_stop",
        "hole_diameter": "hole_size_for_drilling_and_inspection",
        "hole_x_location": "hole_center_long_axis_location",
        "hole_y_location": "hole_center_transverse_location",
        "hole_pitch": "hole_center_to_center_pitch",
        "projection_view_width": "projected_view_width",
        "projection_view_height": "projected_view_height",
        "small_feature_location": "small_feature_transverse_location",
    }
    stations = {
        "overall_length": 0.50,
        "overall_width": 0.58,
        "overall_height": 0.56,
        "left_end_offset": 0.18,
        "right_end_offset": 0.82,
        "hole_diameter": 0.54,
        "hole_x_location": 0.38,
        "hole_y_location": 0.46,
        "hole_pitch": 0.70,
        "projection_view_width": 0.50,
        "projection_view_height": 0.50,
        "small_feature_location": 0.35,
    }
    lane_indices = {
        "overall_length": 0,
        "overall_width": 0,
        "overall_height": 0,
        "left_end_offset": 0,
        "right_end_offset": 1,
        "hole_diameter": 0,
        "hole_x_location": 1,
        "hole_y_location": 1,
        "hole_pitch": 2,
        "projection_view_width": 0,
        "projection_view_height": 0,
        "small_feature_location": 1,
    }
    witness_by_type = {
        "diameter": ["circular_edges", "hole_edges", "visible_model_edges"],
        "linear_horizontal": ["visible_linear_edges", "hole_center_edges", "silhouette_edges"],
        "linear_vertical": ["visible_linear_edges", "projection_edges", "silhouette_edges"],
    }
    witness = witness_by_type.get(str(expected_type or ""), ["visible_model_edges"])
    return {
        "functional_role": functional_roles.get(key, str(key or group or "manufacturing_dimension")),
        "reading_group": group_reading_order.get(group, "99_supporting_dimensions"),
        "readability_group": str(group or "supporting_dimensions"),
        "manufacturing_story_role": _manufacturing_story_role(group, target_view),
        "placement_lane": {
            "view_slot": target_view,
            "side": preferred_side,
            "lane_family": _lane_family(preferred_side),
            "lane_index": lane_indices.get(key, 0),
            "station": stations.get(key, 0.5),
            "outside_gap_m": 0.010,
            "stack_gap_m": 0.004,
            "avoid_view_overlap": True,
            "avoid_title_notes_zone": True,
            "readability_required": True,
        },
        "allowed_witness_entity": {
            "preferred": witness,
            "reject": ["title_block_line", "note_text", "cosmetic_thread_annotation"],
            "must_be_visible_in_target_view": True,
        },
        "prune_protection_policy": {
            "protected": True,
            "delete_only_if_target_covered_elsewhere": True,
            "delete_only_if_final_floor_preserved": True,
            "required_final_stage": "post_layout_final",
            "blocker_when_lost": "reference_intent_target_lost_after_prune",
            "reason": "reference_intent_target_real_displaydim_must_persist",
        },
    }


def _lane_family(preferred_side: str) -> str:
    side = str(preferred_side or "").strip().lower()
    if side in {"above", "top"}:
        return "outside_top"
    if side in {"below", "bottom"}:
        return "outside_bottom"
    if side in {"left", "callout_left"}:
        return "outside_left"
    if side in {"right", "callout_right"}:
        return "outside_right"
    return "outside_auxiliary"


def _manufacturing_story_role(group: str, target_view: str) -> str:
    if group == "overall_envelope":
        return "establish_part_envelope_before_feature_details"
    if group == "end_offsets":
        return "locate_machining_stops_from_part_ends"
    if group == "hole_locations":
        return "locate_and_size_holes_for_drilling_inspection"
    if group == "small_projected_view":
        return "explain_small_projection_without_overloading_primary_view"
    return f"support_{target_view}_view_reading"


def _reference_extraction_summary(base: str, source_reference: str, display_dim_count: int) -> dict[str, Any]:
    if base != "LB26001-A-04-006":
        return {
            "source_reference": source_reference,
            "status": "generic_reference_plan_no_visual_value_extraction",
            "display_dim_count": display_dim_count,
        }
    return {
        "source_reference": source_reference,
        "reference_png": str(REPO_ROOT / "drw_output" / "case_library" / f"{base}.png"),
        "status": "visual_reference_png_values_recorded",
        "display_dim_count": display_dim_count,
        "visual_reading_notes": [
            "Overall long-axis station values visible on top view: 0, 10, 80, 150, 220, 230.",
            "Transverse station values visible on top/right views: 0, 6, 12.",
            "Front/right height station values visible: 0, 13.",
            "Hole callout visible near top view: 4-⌀3.3 完全贯穿; M4-6H 完全贯穿.",
            "Surface finish note visible near upper-right title area: 3.2 其余.",
            "No radius or chamfer callout is visually present in the reference PNG.",
        ],
        "value_units": "mm unless noted otherwise",
        "displaydim_values_require_locked_cad_extraction": True,
        "api_and_png_reading_are_supporting_only": True,
        "ui_screenshot_acceptance_required": True,
    }


def _reference_evidence_for_dimension(
    *,
    key: str,
    source_reference: str,
    target_view: str,
    expected_type: str,
) -> dict[str, Any]:
    reference_png = str(REPO_ROOT / "drw_output" / "case_library" / "LB26001-A-04-006.png")
    values: dict[str, dict[str, Any]] = {
        "overall_length": {
            "reference_value": 230,
            "reference_value_unit": "mm",
            "visual_reading": "Long-axis overall dimension reads 230.",
            "source_text": "230",
        },
        "overall_width": {
            "reference_value": 12,
            "reference_value_unit": "mm",
            "visual_reading": "Top/right transverse overall station reads 0 to 12.",
            "source_text": "0, 12",
        },
        "overall_height": {
            "reference_value": 13,
            "reference_value_unit": "mm",
            "visual_reading": "Front/right vertical station reads 0 to 13.",
            "source_text": "0, 13",
        },
        "left_end_offset": {
            "reference_value": 10,
            "reference_value_unit": "mm",
            "visual_reading": "First hole center station is 10 from left datum.",
            "source_text": "0, 10",
        },
        "right_end_offset": {
            "reference_value": 10,
            "reference_value_unit": "mm",
            "visual_reading": "Last hole center station 220 to overall 230 leaves 10 right end offset.",
            "source_text": "220, 230",
        },
        "hole_diameter": {
            "reference_value": {"hole_count": 4, "diameter_mm": 3.3, "thread": "M4-6H", "through": True},
            "reference_value_unit": "callout",
            "visual_reading": "Hole/thread callout reads 4-⌀3.3 完全贯穿 and M4-6H 完全贯穿.",
            "source_text": "4-⌀3.3 完全贯穿; M4-6H 完全贯穿",
        },
        "hole_x_location": {
            "reference_value": [10, 80, 150, 220],
            "reference_value_unit": "mm",
            "visual_reading": "Hole center x stations are visible as 10, 80, 150, 220 from the left datum.",
            "source_text": "10, 80, 150, 220",
        },
        "hole_y_location": {
            "reference_value": 6,
            "reference_value_unit": "mm",
            "visual_reading": "Hole centerline is centered between transverse stations 0 and 12, with station 6 shown.",
            "source_text": "0, 6, 12",
        },
        "hole_pitch": {
            "reference_value": [70, 70, 70],
            "reference_value_unit": "mm",
            "visual_reading": "Successive x stations 10, 80, 150, 220 imply 70 mm pitch.",
            "source_text": "10, 80, 150, 220",
        },
        "projection_view_width": {
            "reference_value": 12,
            "reference_value_unit": "mm",
            "visual_reading": "Right projected view horizontal station reads 0 to 12.",
            "source_text": "0, 12",
        },
        "projection_view_height": {
            "reference_value": 13,
            "reference_value_unit": "mm",
            "visual_reading": "Right projected view vertical station reads 0 to 13.",
            "source_text": "0, 13",
        },
        "small_feature_location": {
            "reference_value": 6,
            "reference_value_unit": "mm",
            "visual_reading": "Small projected feature aligns to center station 6 within the 12 mm width.",
            "source_text": "0, 6, 12",
        },
    }
    evidence = values.get(key)
    if not evidence:
        evidence = {
            "reference_value": None,
            "reference_value_unit": "",
            "visual_reading": "No visual value reading recorded for this generic dimension.",
            "source_text": "",
        }
    return {
        "source_reference": source_reference,
        "reference_png": reference_png,
        "target_view": target_view,
        "expected_type": expected_type,
        "extraction_method": "manual_visual_reading_from_reference_png_plus_reference_metrics",
        "reference_value": evidence["reference_value"],
        "reference_value_unit": evidence["reference_value_unit"],
        "reference_value_status": "visual_reading_recorded",
        "visual_reading": evidence["visual_reading"],
        "source_text": evidence["source_text"],
        "requires_locked_displaydim_value_confirmation": True,
        "confidence": "visual_readable_supporting_evidence",
    }


def _reference_callouts(base: str, source_reference: str) -> list[dict[str, Any]]:
    if base != "LB26001-A-04-006":
        return []
    reference_png = str(REPO_ROOT / "drw_output" / "case_library" / f"{base}.png")
    common = {
        "source_reference": source_reference,
        "reference_png": reference_png,
        "fallback_policy": "need_review_when_real_callout_unavailable",
        "api_is_supporting_only": True,
        "ui_screenshot_acceptance_required": True,
    }
    return [
        {
            **common,
            "key": "thread_callout_m4_6h",
            "target_view": "top",
            "expected_type": "thread_callout",
            "is_manufacturing_dimension": True,
            "reference_value": "M4-6H 完全贯穿",
            "source_reference_evidence": {
                "visual_reading": "Thread callout near top view reads M4-6H 完全贯穿.",
                "source_text": "M4-6H 完全贯穿",
                "extraction_method": "manual_visual_reading_from_reference_png",
            },
            "forbid_note_substitution_for_displaydim": True,
            "create_as": "SolidWorks hole/thread callout or attached manufacturing callout, not a substitute DisplayDim",
        },
        {
            **common,
            "key": "hole_callout_4x3_3",
            "target_view": "top",
            "expected_type": "hole_callout",
            "is_manufacturing_dimension": True,
            "reference_value": "4-3.3 through",
            "source_reference_evidence": {
                "visual_reading": "Hole callout near top view reads 4-3.3 through.",
                "source_text": "4-3.3",
                "extraction_method": "manual_visual_reading_from_reference_png",
            },
            "forbid_note_substitution_for_displaydim": True,
            "create_as": "SolidWorks hole callout or attached manufacturing callout, not a substitute DisplayDim",
        },
        {
            **common,
            "key": "surface_finish_rest_3_2",
            "target_view": "sheet_notes",
            "expected_type": "surface_finish_callout",
            "is_manufacturing_dimension": True,
            "reference_value": "3.2 其余",
            "source_reference_evidence": {
                "visual_reading": "Upper-right sheet note reads 3.2 其余.",
                "source_text": "3.2 其余",
                "extraction_method": "manual_visual_reading_from_reference_png",
            },
            "create_as": "manufacturing note/symbol; does not count as DisplayDim",
        },
        {
            **common,
            "key": "radius_callout",
            "target_view": "front/top/right",
            "expected_type": "radius_callout",
            "is_manufacturing_dimension": False,
            "reference_value": None,
            "source_reference_evidence": {
                "visual_reading": "No radius callout is visually present in the reference PNG.",
                "source_text": "",
                "extraction_method": "manual_visual_absence_check",
            },
            "fallback_policy": "do_not_create_unless_geometry_or_reference_proves_feature",
        },
        {
            **common,
            "key": "chamfer_callout",
            "target_view": "front/top/right",
            "expected_type": "chamfer_callout",
            "is_manufacturing_dimension": False,
            "reference_value": None,
            "source_reference_evidence": {
                "visual_reading": "No chamfer callout is visually present in the reference PNG.",
                "source_text": "",
                "extraction_method": "manual_visual_absence_check",
            },
            "fallback_policy": "do_not_create_unless_geometry_or_reference_proves_feature",
        },
    ]


def _lb26001_006_reference_layout_policy(
    profile: dict[str, Any],
    view_slots: dict[str, dict[str, Any]],
    source_reference: str,
) -> dict[str, Any]:
    sheet_size = profile.get("sheet_size") or {"width": 0.297, "height": 0.21}
    view_plan: list[dict[str, Any]] = []
    for slot in ["front", "top", "right", "iso"]:
        slot_data = view_slots.get(slot) or {}
        position = _position_for_slot(profile.get("view_positions") or [], slot_data)
        if not position:
            continue
        center_norm = _norm_pair(position.get("center_norm"))
        size_norm = _norm_pair(position.get("size_norm"))
        outline_norm = _outline_norm(position, sheet_size, center_norm, size_norm)
        if not center_norm or not outline_norm:
            continue
        view_plan.append({
            "slot": slot,
            "required": True,
            "reference_view_name": slot_data.get("reference_view_name") or position.get("name") or "",
            "sw_view_type": slot_data.get("sw_view_type") or str(position.get("type") or ""),
            "expected_create_method": slot_data.get("expected_create_method") or "reference_profile",
            "center_norm": center_norm,
            "size_norm": size_norm,
            "outline_norm": outline_norm,
            "box_norm": outline_norm,
            "source": "reference_profiles_v4.view_positions",
        })

    layout_plan = {
        "source": "reference_intent_dimension_plan_006.reference_layout_policy",
        "sheet_size": sheet_size,
        "views": view_plan,
        "notes_box_norm": [0.58, 0.64, 0.96, 0.82],
        "titlebar_box_norm": [0.60, 0.02, 0.96, 0.13],
        "projection_view_style_match_required": True,
        "compact_titlebar_fields_required": True,
        "reference_style_notes_required": True,
    }
    return {
        "schema": "sw_drawing_studio.reference_layout_policy.v4_4",
        "base": "LB26001-A-04-006",
        "source_reference": source_reference,
        "source_profile": profile.get("source_profile", ""),
        "view_plan": view_plan,
        "layout_plan": layout_plan,
        "ui_defect_repair_layout_targets": {
            "source": "application_ui_screenshot_failed_buckets",
            "target_buckets": [
                "projection_view_style_mismatch",
                "note_missing_or_wrong",
                "titlebar_incomplete",
            ],
            "required_view_slots": [item["slot"] for item in view_plan],
            "notes_box_norm": layout_plan["notes_box_norm"],
            "titlebar_box_norm": layout_plan["titlebar_box_norm"],
            "api_or_reference_json_alone_can_close": False,
            "application_ui_screenshot_required": True,
        },
    }


def _position_for_slot(positions: list[dict[str, Any]], slot_data: dict[str, Any]) -> dict[str, Any]:
    ref_name = str(slot_data.get("reference_view_name") or "")
    ref_type = str(slot_data.get("sw_view_type") or "")
    for item in positions:
        if not isinstance(item, dict):
            continue
        if str(item.get("name") or "") == ref_name and str(item.get("type") or "") == ref_type:
            return item
    return {}


def _norm_pair(value: Any) -> list[float]:
    if not isinstance(value, list) or len(value) < 2:
        return []
    try:
        return [round(max(0.0, min(1.0, float(value[0]))), 6), round(max(0.0, min(1.0, float(value[1]))), 6)]
    except Exception:
        return []


def _outline_norm(
    position: dict[str, Any],
    sheet_size: dict[str, Any],
    center_norm: list[float],
    size_norm: list[float],
) -> list[float]:
    outline_m = position.get("outline_m")
    try:
        width = float(sheet_size.get("width") or 0.297)
        height = float(sheet_size.get("height") or 0.21)
    except Exception:
        width, height = 0.297, 0.21
    if isinstance(outline_m, list) and len(outline_m) >= 4 and width > 0 and height > 0:
        try:
            x0 = float(outline_m[0]) / width
            y0 = float(outline_m[1]) / height
            x1 = float(outline_m[2]) / width
            y1 = float(outline_m[3]) / height
            return _norm_box([x0, y0, x1, y1])
        except Exception:
            pass
    if center_norm and size_norm:
        cx, cy = center_norm[:2]
        sx, sy = size_norm[:2]
        return _norm_box([cx - sx / 2.0, cy - sy / 2.0, cx + sx / 2.0, cy + sy / 2.0])
    return []


def _norm_box(value: list[float]) -> list[float]:
    x0, y0, x1, y1 = [float(item) for item in value[:4]]
    if x1 < x0:
        x0, x1 = x1, x0
    if y1 < y0:
        y0, y1 = y1, y0
    return [
        round(max(0.0, min(1.0, x0)), 6),
        round(max(0.0, min(1.0, y0)), 6),
        round(max(0.0, min(1.0, x1)), 6),
        round(max(0.0, min(1.0, y1)), 6),
    ]


def _expected_add_method(expected_type: str) -> str:
    value = str(expected_type or "").strip().lower()
    if "diameter" in value:
        return "AddDiameterDimension2"
    if "horizontal" in value:
        return "AddHorizontalDimension2"
    if "vertical" in value:
        return "AddVerticalDimension2"
    return "AddDimension2"


def _semantic_view_slots(view_positions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    positions = [item for item in view_positions if isinstance(item, dict)]
    result: dict[str, dict[str, Any]] = {}
    type7 = [item for item in positions if str(item.get("type")) == "7"]
    type4 = [item for item in positions if str(item.get("type")) == "4"]
    if type7:
        front = max(type7, key=lambda item: (_size_width(item), _center_y(item)))
        result["front"] = _view_slot(front, "named_or_standard")
        for item in type7:
            if item is not front:
                result.setdefault("iso", _view_slot(item, "named_or_standard"))
    if type4:
        right = max(type4, key=lambda item: (_center_x(item), _center_y(item)))
        result["right"] = _view_slot(right, "projection_api")
        for item in type4:
            if item is not right:
                result.setdefault("top", _view_slot(item, "projection_api"))
    for item in positions:
        if any(_same_view(item, slot) for slot in result.values()):
            continue
        result[f"extra_{len(result) + 1}"] = _view_slot(item, "unknown")
    return result


def _view_slot(item: dict[str, Any], expected_create_method: str) -> dict[str, Any]:
    return {
        "reference_view_name": str(item.get("name") or ""),
        "sw_view_type": str(item.get("type") or ""),
        "center_norm": list(item.get("center_norm") or []),
        "size_norm": list(item.get("size_norm") or []),
        "expected_create_method": expected_create_method,
    }


def _validate_plan(plan: dict[str, Any]) -> None:
    missing: list[str] = []
    for item in plan.get("dimensions") or []:
        for field in (
            "source_reference",
            "target_view",
            "expected_type",
            "is_manufacturing_dimension",
            "expected_add_method",
            "fallback_policy",
            "source_reference_evidence",
            "functional_role",
            "reading_group",
            "placement_lane",
            "allowed_witness_entity",
            "prune_protection_policy",
        ):
            if not item.get(field):
                missing.append(f"{item.get('key', '<unknown>')}:{field}")
        if item.get("target_key") != item.get("key"):
            missing.append(f"{item.get('key', '<unknown>')}:target_key")
        trace_fields = set(item.get("trace_required_fields") or [])
        for field in TRACE_REQUIRED_FIELDS:
            if field not in trace_fields:
                missing.append(f"{item.get('key', '<unknown>')}:trace_required_fields.{field}")
        if item.get("generic_autodimension_acceptance_allowed") is not False:
            missing.append(f"{item.get('key', '<unknown>')}:generic_autodimension_acceptance_allowed")
    if missing:
        raise ValueError("dimension plan missing required fields: " + ", ".join(missing))
    if plan.get("allow_note_substitution"):
        raise ValueError("reference intent dimensions must not allow Note substitution")


def _same_view(item: dict[str, Any], slot: dict[str, Any]) -> bool:
    return (
        str(item.get("name") or "") == str(slot.get("reference_view_name") or "")
        and str(item.get("type") or "") == str(slot.get("sw_view_type") or "")
    )


def _center_x(item: dict[str, Any]) -> float:
    return _float_at(item.get("center_norm"), 0)


def _center_y(item: dict[str, Any]) -> float:
    return _float_at(item.get("center_norm"), 1)


def _size_width(item: dict[str, Any]) -> float:
    return _float_at(item.get("size_norm"), 0)


def _float_at(value: Any, index: int) -> float:
    try:
        return float((value or [])[index])
    except Exception:
        return 0.0


def _int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except Exception:
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a reference-intent dimension plan without SolidWorks COM.")
    parser.add_argument("--base", default="LB26001-A-04-006")
    parser.add_argument("--profiles", default=str(DEFAULT_REFERENCE_PROFILES))
    parser.add_argument("--out", default=str(DEFAULT_OUT_006))
    args = parser.parse_args()

    profile = load_reference_profile(args.base, args.profiles)
    plan = build_reference_intent_dimension_plan(args.base, reference_profile=profile)
    out = write_reference_intent_dimension_plan(plan, args.out)
    print(json.dumps({"status": plan["status"], "base": args.base, "out": str(out)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
