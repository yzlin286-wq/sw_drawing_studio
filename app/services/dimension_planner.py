from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.services.drawing_blueprint_model import DimensionPlan


MANUFACTURING_CLASSES = {"feature_part", "machined_part", "sheet_metal", "long_thin", "tiny_part"}


def build_dimension_plan(
    *,
    part_class: str,
    reference_dimension_profile: dict[str, Any] | None = None,
    blueprint_context: dict[str, Any] | None = None,
) -> DimensionPlan:
    reference_dimension_profile = reference_dimension_profile or {}
    blueprint_context = blueprint_context or {}

    reference_count = _int(
        reference_dimension_profile.get("display_dim_count")
        or reference_dimension_profile.get("required_display_dim_count")
        or reference_dimension_profile.get("reference_display_dim_count")
    )
    default_floor = _default_display_dim_floor(part_class)
    required_count = reference_count if reference_count > 0 else default_floor

    required_overall = _list(
        reference_dimension_profile.get("required_overall_dims")
        or blueprint_context.get("required_overall_dims")
        or _default_overall_dims(part_class)
    )
    hole_dims = _list(reference_dimension_profile.get("hole_dims") or reference_dimension_profile.get("hole_annotations"))
    slot_dims = _list(reference_dimension_profile.get("slot_dims") or reference_dimension_profile.get("slot_annotations"))
    radius_dims = _list(reference_dimension_profile.get("radius_dims") or reference_dimension_profile.get("radius_annotations"))
    thread_dims = _list(reference_dimension_profile.get("thread_dims") or reference_dimension_profile.get("thread_annotations"))
    datum_dims = _list(reference_dimension_profile.get("datum_dims") or reference_dimension_profile.get("datum_annotations"))
    inspection_dims = _list(reference_dimension_profile.get("inspection_dims"))
    view_slots = _list(blueprint_context.get("view_slots"))
    view_dimension_quotas = _view_dimension_quotas(
        part_class,
        required_count,
        view_slots=view_slots,
    )
    dimension_intent_groups = _dimension_intent_groups(
        part_class,
        required_count,
        view_dimension_quotas=view_dimension_quotas,
        reference_dimension_profile=reference_dimension_profile,
    )

    priority = _merge_unique(
        required_overall
        + hole_dims
        + slot_dims
        + radius_dims
        + thread_dims
        + datum_dims
        + inspection_dims
        + [str(item.get("key") or "") for item in dimension_intent_groups if isinstance(item, dict)]
    )
    if not priority:
        priority = _default_priority(part_class)

    reasons = [
        f"part_class={part_class}",
        f"reference_display_dim_count={reference_count}",
        f"part_class_default_display_dim_floor={default_floor}",
        f"required_display_dim_count={required_count}",
        "notes_do_not_count_as_display_dim",
    ]
    if reference_count:
        reasons.append("reference_profile_controls_display_dim_floor")
    if view_dimension_quotas:
        reasons.append("view_dimension_quotas_control_autodim_prune")
    if dimension_intent_groups:
        reasons.append("dimension_intent_groups_required_for_ui_visual_review")

    return DimensionPlan(
        required_display_dim_count=required_count,
        reference_display_dim_count=reference_count,
        required_overall_dims=required_overall,
        hole_dims=hole_dims,
        slot_dims=slot_dims,
        radius_dims=radius_dims,
        thread_dims=thread_dims,
        datum_dims=datum_dims,
        inspection_dims=inspection_dims,
        dimension_intent_groups=dimension_intent_groups,
        view_dimension_quotas=view_dimension_quotas,
        dimension_priority=priority,
        fallback_policy="need_review_when_real_displaydim_unavailable",
        allow_note_substitution=False,
        source="reference_dimension_profile" if reference_count else "part_class_default",
        reasons=reasons,
    )


def write_dimension_plan(plan: DimensionPlan, path: Path | str) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan.__dict__, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def apply_reference_intent_dimension_targets(
    plan: DimensionPlan,
    *,
    base: str,
    reference_profile: dict[str, Any] | None = None,
) -> DimensionPlan:
    """Attach explicit v4.2 reference-intent targets to a DimensionPlan.

    This is offline-only: it builds the target contract from the learned
    reference profile and does not touch SolidWorks COM.
    """
    if base != "LB26001-A-04-006":
        return plan
    try:
        from app.services.reference_intent_dimension_planner import build_reference_intent_dimension_plan

        intent_plan = build_reference_intent_dimension_plan(base, reference_profile=reference_profile or None)
    except Exception as exc:
        if f"reference_intent_dimension_plan_failed:{exc}" not in plan.reasons:
            plan.reasons.append(f"reference_intent_dimension_plan_failed:{exc}")
        return plan

    targets = []
    for item in intent_plan.get("dimensions") or []:
        if not isinstance(item, dict):
            continue
        target = {
            "key": str(item.get("key") or ""),
            "group": str(item.get("group") or ""),
            "functional_role": str(item.get("functional_role") or ""),
            "reading_group": str(item.get("reading_group") or ""),
            "readability_group": str(item.get("readability_group") or ""),
            "manufacturing_story_role": str(item.get("manufacturing_story_role") or ""),
            "source_reference": str(item.get("source_reference") or ""),
            "target_view": str(item.get("target_view") or ""),
            "expected_type": str(item.get("expected_type") or ""),
            "expected_add_method": str(item.get("expected_add_method") or ""),
            "preferred_side": str(item.get("preferred_side") or ""),
            "placement_lane": dict(item.get("placement_lane") or {}),
            "allowed_witness_entity": dict(item.get("allowed_witness_entity") or {}),
            "prune_protection_policy": dict(item.get("prune_protection_policy") or {}),
            "priority": _int(item.get("priority")),
            "fallback_policy": str(item.get("fallback_policy") or "need_review_when_real_displaydim_unavailable"),
            "create_as": "SolidWorks DisplayDim",
            "forbid_note_substitution": True,
            "avoid_generic_model_annotation": bool(item.get("avoid_generic_model_annotation", True)),
            "generic_autodimension_acceptance_allowed": bool(item.get("generic_autodimension_acceptance_allowed", False)),
            "trace_required_fields": list(item.get("trace_required_fields") or []),
            "acceptance_trace": dict(item.get("acceptance_trace") or {}),
            "ui_visual_checklist_items": list(item.get("ui_visual_checklist_items") or []),
        }
        if target["key"]:
            targets.append(target)
    if not targets:
        return plan

    required_count = _int(intent_plan.get("required_display_dim_count"))
    reference_count = _int(intent_plan.get("reference_display_dim_count"))
    plan.required_display_dim_count = max(plan.required_display_dim_count, required_count, len(targets))
    plan.reference_display_dim_count = max(plan.reference_display_dim_count, reference_count)
    plan.dimension_targets = targets
    plan.reference_callouts = [
        dict(item)
        for item in (intent_plan.get("reference_callouts") or [])
        if isinstance(item, dict)
    ]
    plan.dimension_priority = _merge_unique([item["key"] for item in targets] + plan.dimension_priority)
    if intent_plan.get("dimension_groups"):
        plan.dimension_intent_groups = list(intent_plan.get("dimension_groups") or plan.dimension_intent_groups)
    if base == "LB26001-A-04-006":
        plan.view_dimension_quotas = {"front": 3, "top": 6, "right": 3}
    plan.fallback_policy = "need_review_when_real_displaydim_unavailable"
    plan.allow_note_substitution = False
    plan.source = "reference_intent_dimension_plan_v4_2"
    for reason in [
        "reference_intent_dimension_targets_control_worker_execution",
        "explicit_dimension_targets_replace_generic_autodimension_acceptance",
        "ui_screenshot_review_is_final_gate",
    ]:
        if reason not in plan.reasons:
            plan.reasons.append(reason)
    return plan


def _default_display_dim_floor(part_class: str) -> int:
    if part_class in {"fastener", "spring", "purchased_part", "assembly"}:
        return 0
    if part_class == "tiny_part":
        return 3
    if part_class == "long_thin":
        return 4
    return 5 if part_class in MANUFACTURING_CLASSES else 3


def _default_overall_dims(part_class: str) -> list[str]:
    if part_class == "long_thin":
        return ["overall_length", "overall_diameter"]
    if part_class == "sheet_metal":
        return ["overall_length", "overall_width", "thickness"]
    if part_class in {"fastener", "spring", "purchased_part"}:
        return ["specification", "overall_length"]
    return ["overall_length", "overall_width", "overall_height"]


def _default_priority(part_class: str) -> list[str]:
    if part_class == "sheet_metal":
        return ["overall_length", "overall_width", "thickness", "bend_radius", "hole_diameter", "hole_position"]
    if part_class == "long_thin":
        return [
            "overall_envelope",
            "end_offsets",
            "hole_positions",
            "projected_view_size",
            "inspection_reference",
            "overall_length",
            "overall_diameter",
            "chamfer",
            "roughness",
        ]
    if part_class in {"fastener", "spring", "purchased_part"}:
        return ["specification", "overall_length", "supplier_note"]
    return [
        "overall_length",
        "overall_width",
        "overall_height",
        "hole_diameter",
        "hole_position",
        "slot_size",
        "radius",
        "chamfer",
    ]


def _list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _view_dimension_quotas(
    part_class: str,
    required_count: int,
    *,
    view_slots: list[str] | None = None,
) -> dict[str, int]:
    count = _int(required_count)
    if count <= 0 or part_class != "long_thin":
        return {}

    available = [slot for slot in (view_slots or ["front", "top", "right", "iso"]) if slot]
    if not available:
        available = ["front"]

    if count <= 2:
        quotas = {"front": 1, "top": max(0, count - 1)}
    elif count <= 4:
        quotas = {"front": 2, "top": count - 2}
    else:
        right = 2 if count >= 8 else 1
        if count >= 20:
            right = max(right, int(round(count * 0.16)))
        front = max(2, int(round(count * 0.35)))
        if count >= 12:
            front = max(front, 4)
        front = min(front, max(0, count - right))
        top = max(0, count - front - right)
        quotas = {"front": front, "top": top, "right": right}

    filtered: dict[str, int] = {}
    overflow = 0
    for slot, quota in quotas.items():
        if slot in available:
            filtered[slot] = _int(quota)
        else:
            overflow += _int(quota)
    if overflow:
        fallback_slot = next((slot for slot in ("top", "front", "right", "iso") if slot in available), available[0])
        filtered[fallback_slot] = filtered.get(fallback_slot, 0) + overflow
    for slot in available:
        filtered.setdefault(slot, 0)
    return {slot: quota for slot, quota in filtered.items() if quota > 0}


def _dimension_intent_groups(
    part_class: str,
    required_count: int,
    *,
    view_dimension_quotas: dict[str, int],
    reference_dimension_profile: dict[str, Any],
) -> list[dict[str, Any]]:
    if part_class != "long_thin" or required_count <= 0:
        return []
    source = "reference_dimension_profile" if _int(reference_dimension_profile.get("display_dim_count")) else "part_class_long_thin"
    groups = [
        {
            "key": "overall_envelope",
            "label": "overall length/width envelope",
            "slots": [slot for slot in ("front", "top") if view_dimension_quotas.get(slot)],
            "target_count": min(2, required_count),
            "priority": 10,
            "required": True,
            "source": source,
        },
        {
            "key": "end_offsets",
            "label": "end offsets and machining stops",
            "slots": [slot for slot in ("front", "top") if view_dimension_quotas.get(slot)],
            "target_count": 2 if required_count >= 6 else 1,
            "priority": 20,
            "required": required_count >= 6,
            "source": source,
        },
        {
            "key": "hole_positions",
            "label": "hole center positions along the long axis",
            "slots": [slot for slot in ("top", "front") if view_dimension_quotas.get(slot)],
            "target_count": max(0, min(4, view_dimension_quotas.get("top", 0))),
            "priority": 30,
            "required": required_count >= 8,
            "source": source,
        },
        {
            "key": "projected_view_size",
            "label": "small projected view size",
            "slots": [slot for slot in ("right",) if view_dimension_quotas.get(slot)],
            "target_count": min(2, view_dimension_quotas.get("right", 0)),
            "priority": 40,
            "required": bool(view_dimension_quotas.get("right")),
            "source": source,
        },
        {
            "key": "inspection_reference",
            "label": "inspection-friendly reference dimensions",
            "slots": [slot for slot in ("front", "top", "right") if view_dimension_quotas.get(slot)],
            "target_count": min(3, max(1, required_count - 9)),
            "priority": 50,
            "required": required_count >= 12,
            "source": source,
        },
    ]
    return [group for group in groups if group["slots"] and _int(group.get("target_count")) > 0]


def _int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except Exception:
        return 0


def _merge_unique(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = value.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(key)
    return result
