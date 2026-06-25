from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.services.dimension_planner import apply_reference_intent_dimension_targets, build_dimension_plan
from app.services.drawing_blueprint_model import (
    AnnotationPlan,
    DrawingBlueprint,
    TitlebarPlan,
    ValidationPlan,
    ViewPlan,
)
from app.services.drawing_layout_composer import compose_layout
from app.services.notes_blueprint_builder import build_notes_plan
from app.services.reference_dimension_profile_service import build_reference_dimension_profile
from app.services.reference_notes_profile_service import build_reference_notes_profile
from app.services.reference_titlebar_profile_service import build_reference_titlebar_profile


def build_drawing_blueprint(
    *,
    base: str,
    part_class: str,
    part_understanding: dict[str, Any] | None = None,
    reference_profile: dict[str, Any] | None = None,
    titlebar_profile: dict[str, Any] | None = None,
    notes_profile: dict[str, Any] | None = None,
    manufacturing_intent: str = "make_or_inspect",
) -> DrawingBlueprint:
    part_understanding = part_understanding or {}
    reference_profile = reference_profile or {}
    reference_dimension_profile = build_reference_dimension_profile(reference_profile)
    if notes_profile is None:
        notes_profile = build_reference_notes_profile(reference_profile)
    if titlebar_profile is None:
        titlebar_profile = build_reference_titlebar_profile(
            base=base,
            reference_profile=reference_profile,
            part_path=part_understanding.get("part_path"),
        )

    view_plan = build_view_plan(part_class=part_class, reference_profile=reference_profile)
    dimension_plan = build_dimension_plan(
        part_class=part_class,
        reference_dimension_profile=reference_dimension_profile,
        blueprint_context={
            "base": base,
            "part_understanding": part_understanding,
            "view_slots": [item.slot for item in view_plan],
        },
    )
    dimension_plan = apply_reference_intent_dimension_targets(
        dimension_plan,
        base=base,
        reference_profile=reference_profile,
    )
    notes_plan = build_notes_plan(part_class=part_class, reference_notes_profile=notes_profile)
    titlebar_plan = TitlebarPlan(
        fields=titlebar_profile.get("fields") or {},
        missing_fields=titlebar_profile.get("missing_fields") or [],
        source=titlebar_profile.get("source") or "filename",
    )
    note_text = _note_text(notes_plan)
    annotation_plan = AnnotationPlan(
        roughness_required=bool(
            notes_profile.get("roughness")
            or reference_profile.get("roughness_symbols")
            or _contains_any(note_text, ["Ra", "roughness", "粗糙度"])
        ),
        datum_required=bool(
            notes_profile.get("datum")
            or reference_profile.get("datum_symbols")
            or _contains_any(note_text, ["datum", "基准"])
        ),
        center_marks_required=bool(reference_profile.get("center_marks")),
        centerlines_required=bool(reference_profile.get("centerlines")),
        symbols=_symbols(reference_profile),
        source="reference_profile" if reference_profile else "part_class_default",
        reasons=["reference_symbols_preserved" if reference_profile else "no_reference_symbols"],
    )
    layout_plan = compose_layout(
        view_plan=view_plan,
        sheet_size=reference_profile.get("sheet_size") or {},
    )
    layout_plan["sheet_template_policy"] = _sheet_template_policy(reference_profile)
    layout_plan["dimension_lane_policy"] = _dimension_lane_policy(dimension_plan.dimension_targets)
    notes_title_policy = _notes_title_policy(
        reference_profile=reference_profile,
        sheet_template_policy=layout_plan["sheet_template_policy"],
        titlebar_plan=titlebar_plan,
        note_text=note_text,
    )

    warnings: list[str] = []
    if not reference_profile:
        warnings.append("reference_profile_missing_part_class_defaults_used")
    if titlebar_plan.missing_fields:
        warnings.extend([f"titlebar_missing:{field}" for field in titlebar_plan.missing_fields])
    if not layout_plan["sheet_template_policy"].get("default_template_artifacts_allowed", True):
        warnings.append("reference_sheet_template_policy:strip_default_template_artifacts")

    return DrawingBlueprint(
        base=base,
        part_class=part_class,
        drawing_purpose=_drawing_purpose(part_class),
        manufacturing_intent=manufacturing_intent,
        reference_storyboard=_reference_storyboard(
            base=base,
            view_plan=view_plan,
            reference_profile=reference_profile,
        ),
        view_roles=_view_roles(view_plan),
        notes_title_policy=notes_title_policy,
        visual_acceptance_checklist=_visual_acceptance_checklist(),
        reference_base=reference_profile.get("base") or "",
        view_plan=view_plan,
        dimension_plan=dimension_plan,
        annotation_plan=annotation_plan,
        titlebar_plan=titlebar_plan,
        notes_plan=notes_plan,
        validation_plan=ValidationPlan(
            require_true_display_dim=part_class not in {"fastener", "spring", "purchased_part", "assembly"},
            reasons=["ui_screenshot_is_final_visual_gate", "api_metrics_are_supporting_evidence_only"],
        ),
        layout_plan=layout_plan,
        source_inputs={
            "part_understanding": part_understanding,
            "reference_profile_schema": reference_profile.get("schema") or "",
            "titlebar_profile_schema": titlebar_profile.get("schema") or "",
            "notes_profile_schema": notes_profile.get("schema") or "",
        },
        warnings=warnings,
        reasons=[
            "reference_profile_preferred" if reference_profile else "part_class_default_used",
            "note_annotations_do_not_count_as_displaydim",
            "projected_views_must_use_projection_api",
        ],
    )


def write_drawing_blueprint(blueprint: DrawingBlueprint, path: Path | str) -> Path:
    return blueprint.write_json(path)


def build_view_plan(*, part_class: str, reference_profile: dict[str, Any] | None = None) -> list[ViewPlan]:
    reference_profile = reference_profile or {}
    positions = [item for item in reference_profile.get("view_positions") or [] if isinstance(item, dict)]
    if positions:
        return _reference_view_plan(positions)
    return _default_view_plan(part_class)


def _reference_storyboard(
    *,
    base: str,
    view_plan: list[ViewPlan],
    reference_profile: dict[str, Any],
) -> dict[str, Any]:
    slots = [item.slot for item in view_plan if item.required]
    if base == "LB26001-A-04-006":
        return {
            "source": "same_name_reference",
            "narrative": "readable_manufacturing_drawing",
            "primary_reading_order": ["front", "top", "right", "iso"],
            "view_story": {
                "front": "long_envelope_and_end_identity",
                "top": "hole_location_relationships_and_long_axis_offsets",
                "right": "small_projected_section_and_transverse_size",
                "iso": "compact_part_recognition_only",
            },
            "dimension_story": [
                "overall_envelope_outside_views",
                "end_offsets_below_long_axis",
                "hole_callouts_grouped_near_top_view",
                "projected_view_size_next_to_right_view",
            ],
            "reference_view_slots": slots,
            "api_metrics_are_supporting_only": True,
            "ui_screenshot_is_final_gate": True,
        }
    return {
        "source": "reference_profile" if reference_profile else "part_class_default",
        "narrative": "make_or_inspect",
        "primary_reading_order": slots,
        "dimension_story": ["overall_first", "features_next", "notes_and_title_last"],
        "api_metrics_are_supporting_only": True,
        "ui_screenshot_is_final_gate": True,
    }


def _view_roles(view_plan: list[ViewPlan]) -> dict[str, Any]:
    role_defaults = {
        "front": {
            "role": "primary_shape_story",
            "dimension_lane_policy": "outer_envelope_and_end_identity",
            "allow_dimension_targets": True,
        },
        "top": {
            "role": "functional_feature_relationships",
            "dimension_lane_policy": "hole_offsets_pitch_and_callouts",
            "allow_dimension_targets": True,
        },
        "right": {
            "role": "projected_small_feature_size",
            "dimension_lane_policy": "local_projection_lanes",
            "allow_dimension_targets": True,
        },
        "iso": {
            "role": "visual_part_recognition",
            "dimension_lane_policy": "no_primary_manufacturing_dimensions",
            "allow_dimension_targets": False,
        },
    }
    result: dict[str, Any] = {}
    for item in view_plan:
        result[item.slot] = {
            **role_defaults.get(
                item.slot,
                {
                    "role": "supporting_view",
                    "dimension_lane_policy": "local_readability_lanes",
                    "allow_dimension_targets": True,
                },
            ),
            "view_type": item.view_type,
            "create_method": item.create_method,
            "projected_from": item.projected_from,
            "required": item.required,
            "center_norm": list(item.center_norm or []),
            "outline_norm": list(item.outline_norm or []),
        }
    return result


def _notes_title_policy(
    *,
    reference_profile: dict[str, Any],
    sheet_template_policy: dict[str, Any],
    titlebar_plan: TitlebarPlan,
    note_text: str,
) -> dict[str, Any]:
    compact_reference = not sheet_template_policy.get("default_template_artifacts_allowed", True)
    return {
        "source": "same_name_reference" if reference_profile else "part_class_default",
        "title_block_mode": "compact_reference_fields" if compact_reference else "standard_gb_titleblock",
        "strip_default_template_artifacts": bool(compact_reference),
        "preserve_reference_notes_zone": bool(compact_reference),
        "required_title_fields": list(titlebar_plan.required_fields or []),
        "present_title_fields": sorted((titlebar_plan.fields or {}).keys()),
        "missing_title_fields": list(titlebar_plan.missing_fields or []),
        "manufacturing_notes_required": True,
        "required_note_topics": [
            "general_tolerance",
            "surface_roughness",
            "technical_requirements",
            "material_or_specification",
        ],
        "reference_notes_present": bool(note_text.strip()),
        "notes_must_not_replace_display_dimensions": True,
    }


def _visual_acceptance_checklist() -> list[str]:
    return [
        "reference_match",
        "view_layout",
        "display_dimensions",
        "dimension_readability",
        "title_block",
        "manufacturing_notes",
    ]


def _dimension_lane_policy(targets: list[dict[str, Any]]) -> dict[str, Any]:
    lane_targets = []
    for target in targets or []:
        lane = target.get("placement_lane") if isinstance(target, dict) else None
        if not isinstance(lane, dict):
            continue
        lane_targets.append({
            "target_key": str(target.get("key") or ""),
            "view_slot": str(lane.get("view_slot") or target.get("target_view") or ""),
            "reading_group": str(target.get("reading_group") or ""),
            "side": str(lane.get("side") or target.get("preferred_side") or ""),
            "lane_family": str(lane.get("lane_family") or ""),
            "lane_index": lane.get("lane_index", 0),
            "station": lane.get("station", 0.5),
            "readability_required": bool(lane.get("readability_required", True)),
        })
    return {
        "source": "reference_intent_dimension_targets" if lane_targets else "part_class_default",
        "lane_targets": lane_targets,
        "avoid_view_overlap": True,
        "avoid_title_notes_zone": True,
        "fallback_when_unreadable": "rearrange_before_validation",
        "final_gate": "ui_screenshot_visual_review",
    }


def _sheet_template_policy(reference_profile: dict[str, Any]) -> dict[str, Any]:
    if reference_profile:
        return {
            "source": "reference_profile",
            "policy": "strip_default_template_artifacts",
            "default_template_artifacts_allowed": False,
            "skip_builtin_gb_frame_titleblock": True,
            "visible_titlebar_mode": "compact_reference_fields",
            "reason": "same-name reference controls visible sheet/titleblock style",
        }
    return {
        "source": "part_class_default",
        "policy": "allow_default_template",
        "default_template_artifacts_allowed": True,
        "skip_builtin_gb_frame_titleblock": False,
        "visible_titlebar_mode": "standard_gb_titleblock",
        "reason": "no same-name reference profile available",
    }


def _reference_view_plan(positions: list[dict[str, Any]]) -> list[ViewPlan]:
    slots = _semantic_slots(positions)
    plans: list[ViewPlan] = []
    for slot, item in slots:
        sw_type = str(item.get("type") or "")
        is_projected = sw_type == "4"
        plans.append(
            ViewPlan(
                slot=slot,
                view_type="projected" if is_projected else ("iso" if slot == "iso" else "named"),
                required=True,
                source="reference_profile",
                center_norm=_float_list(item.get("center_norm")),
                scale="reference",
                sw_view_type=sw_type,
                create_method="projection_api" if is_projected else "named_view",
                projected_from="front" if is_projected else "",
                outline_norm=_outline_from_position(item),
                reasons=[
                    "same_name_reference_view_position",
                    "projected_view_requires_projection_api" if is_projected else "named_or_model_view_from_reference",
                ],
            )
        )
    return plans


def _semantic_slots(positions: list[dict[str, Any]]) -> list[tuple[str, dict[str, Any]]]:
    indexed = [(index, item, _point(item)) for index, item in enumerate(positions)]
    indexed = [item for item in indexed if item[2]]
    if not indexed:
        return [("front", positions[0])] if positions else []

    base_items = [item for item in indexed if str(item[1].get("type") or "") != "4"]
    projected = [item for item in indexed if str(item[1].get("type") or "") == "4"]
    front = max(base_items or indexed, key=lambda item: (item[2][1], -item[2][0], -item[0]))
    result: list[tuple[str, dict[str, Any]]] = [("front", front[1])]

    remaining_projected = [item for item in projected if item is not front]
    if remaining_projected:
        fx, fy = front[2]
        top = min(
            remaining_projected,
            key=lambda item: (
                0 if item[2][1] < fy else 1,
                abs(item[2][0] - fx),
                abs(item[2][1] - fy),
                item[0],
            ),
        )
        result.append(("top", top[1]))
        remaining_projected = [item for item in remaining_projected if item is not top]
    if remaining_projected:
        fx, fy = front[2]
        right = max(
            remaining_projected,
            key=lambda item: (
                item[2][0] - fx,
                -abs(item[2][1] - fy),
                -item[0],
            ),
        )
        result.append(("right", right[1]))

    remaining_base = [item for item in base_items if item is not front]
    if remaining_base:
        iso = max(remaining_base, key=lambda item: (item[2][0], -item[0]))
        result.append(("iso", iso[1]))
    return result


def _default_view_plan(part_class: str) -> list[ViewPlan]:
    if part_class in {"fastener", "spring", "purchased_part"}:
        slots = ["front", "iso"]
    elif part_class == "sheet_metal":
        slots = ["front", "flat_pattern"]
    elif part_class == "long_thin":
        slots = ["front", "right"]
    else:
        slots = ["front", "top", "right", "iso"]
    centers = {
        "front": [0.34, 0.68],
        "top": [0.34, 0.40],
        "right": [0.68, 0.68],
        "iso": [0.78, 0.48],
        "flat_pattern": [0.34, 0.40],
    }
    plans = []
    for slot in slots:
        is_projected = slot in {"top", "right", "flat_pattern"}
        plans.append(
            ViewPlan(
                slot=slot,
                view_type="projected" if is_projected else slot,
                source="part_class_default",
                center_norm=centers.get(slot, [0.5, 0.5]),
                create_method="projection_api" if is_projected else "named_view",
                projected_from="front" if is_projected else "",
                reasons=["part_class_default_view_plan"],
            )
        )
    return plans


def _symbols(reference_profile: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for key in ["roughness_symbols", "datum_symbols", "center_marks", "centerlines"]:
        values = reference_profile.get(key) or []
        if values:
            result.append({"type": key, "items": values, "source": "reference_profile"})
    return result


def _note_text(notes_plan: Any) -> str:
    values: list[str] = []
    for attr in ("required_notes", "optional_notes", "raw_reference_notes", "warning_notes"):
        values.extend(str(item) for item in getattr(notes_plan, attr, []) or [])
    for item in getattr(notes_plan, "normalized_notes", []) or []:
        if isinstance(item, dict):
            values.append(str(item.get("text") or ""))
        else:
            values.append(str(item))
    return "\n".join(values)


def _contains_any(text: str, needles: list[str]) -> bool:
    lower = str(text or "").lower()
    return any(str(needle).lower() in lower for needle in needles)


def _drawing_purpose(part_class: str) -> str:
    if part_class in {"fastener", "spring", "purchased_part"}:
        return "procurement_or_assembly"
    if part_class == "assembly":
        return "assembly"
    return "manufacturing"


def _point(item: dict[str, Any]) -> tuple[float, float] | None:
    values = _float_list(item.get("center_norm"))
    if len(values) >= 2:
        return values[0], values[1]
    return None


def _float_list(value: Any) -> list[float]:
    if not isinstance(value, list):
        return []
    result: list[float] = []
    for item in value:
        try:
            result.append(round(float(item), 4))
        except Exception:
            pass
    return result


def _outline_from_position(item: dict[str, Any]) -> list[float]:
    center = _float_list(item.get("center_norm"))
    size = _float_list(item.get("size_norm"))
    if len(center) >= 2 and len(size) >= 2:
        return [
            round(center[0] - size[0] / 2, 4),
            round(center[1] - size[1] / 2, 4),
            round(center[0] + size[0] / 2, 4),
            round(center[1] + size[1] / 2, 4),
        ]
    return []


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Build a v4 DrawingBlueprint JSON from a reference profile sample.")
    parser.add_argument("--base", required=True)
    parser.add_argument("--part-class", default="machined_part")
    parser.add_argument("--reference-profiles", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    payload = json.loads(Path(args.reference_profiles).read_text(encoding="utf-8"))
    reference_profile = (payload.get("profiles") or {}).get(args.base) or {}
    blueprint = build_drawing_blueprint(
        base=args.base,
        part_class=args.part_class,
        reference_profile=reference_profile,
    )
    write_drawing_blueprint(blueprint, args.out)
    print(json.dumps({"pass": True, "out": args.out, "base": args.base}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
