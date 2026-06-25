from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any


SCHEMA = "sw_drawing_studio.reference_compare.v4"
VERSION = "v4.0"
STRICT_REFERENCE_INTENT_BASES = {
    "LB26001-A-04-006",
    "LB26001-A-04-007",
    "LB26001-A-04-008",
    "LB26001-A-04-009",
    "LB26001-A-04-015",
    "LB26001-A-04-022",
}
REQUIRED_ISSUE_FIELDS = [
    "key",
    "severity",
    "bbox",
    "source",
    "confidence",
    "evidence",
    "fix_suggestion",
    "auto_fix_available",
    "human_review_status",
]


def compare_reference_v4(
    *,
    blueprint: dict[str, Any] | str | Path | None,
    reference_profile: dict[str, Any] | str | Path | None = None,
    reference_profiles: dict[str, Any] | str | Path | None = None,
    base: str = "",
    dimension_validation: dict[str, Any] | str | Path | None = None,
    vision_qc: dict[str, Any] | str | Path | None = None,
    generator_warnings: dict[str, Any] | str | Path | None = None,
    legacy_reference_compare: dict[str, Any] | str | Path | None = None,
    legacy_reference_style: dict[str, Any] | str | Path | None = None,
    out_path: str | Path | None = None,
) -> dict[str, Any]:
    """Build the strict v4 reference comparison gate.

    This service intentionally consumes existing artifacts only. It does not
    call SolidWorks, OCR, model inference, or UI automation.
    """
    blueprint_data, blueprint_source = _load_json(blueprint)
    dimension_data, dimension_source = _load_json(dimension_validation)
    vision_data, vision_source = _load_json(vision_qc)
    generator_warnings_data, generator_warnings_source = _load_json(generator_warnings)
    legacy_ref_data, legacy_ref_source = _load_json(legacy_reference_compare)
    legacy_style_data, legacy_style_source = _load_json(legacy_reference_style)
    reference_data, reference_source = _resolve_reference_profile(
        reference_profile=reference_profile,
        reference_profiles=reference_profiles,
        base=base or str(blueprint_data.get("base") or ""),
    )

    base_name = base or str(blueprint_data.get("base") or reference_data.get("base") or "")
    validation = blueprint_data.get("validation_plan") or {}
    thresholds = {
        "view_match": _float(validation.get("view_match_min"), 0.90),
        "dimension_match": _float(validation.get("dimension_match_min"), 0.80),
        "titlebar_match": _float(validation.get("titlebar_match_min"), 0.85),
        "notes_match": _float(validation.get("notes_match_min"), 0.85),
        "layout_match": _float(validation.get("layout_match_min"), 0.80),
    }
    issues: list[dict[str, Any]] = []

    if legacy_ref_data.get("status") == "no_reference" and not reference_data:
        payload = _base_payload(
            base=base_name,
            blueprint_source=blueprint_source,
            reference_source=reference_source,
            dimension_source=dimension_source,
            vision_source=vision_source,
            generator_warnings_source=generator_warnings_source,
            legacy_ref_source=legacy_ref_source,
            legacy_style_source=legacy_style_source,
            thresholds=thresholds,
        )
        payload.update({
            "status": "no_reference",
            "pass": True,
            "visual_acceptance_pass": bool(vision_data.get("visual_acceptance_pass")),
            "reasons": ["no_same_name_reference_slddrw"],
            "failure_bucket": [],
            "fix_suggestions": list(legacy_ref_data.get("fix_suggestions") or []),
        })
        _write_if_requested(payload, out_path)
        return payload

    if not blueprint_data:
        issues.append(_issue(
            "drawing_blueprint_missing",
            "critical",
            "reference_compare_v4",
            {"source": blueprint_source},
            "Generate drawing_blueprint.json before accepting the drawing.",
        ))
    if not reference_data:
        issues.append(_issue(
            "reference_profile_missing",
            "critical",
            "reference_compare_v4",
            {"base": base_name, "source": reference_source},
            "Learn or attach the same-name reference drawing profile before v4 acceptance.",
        ))
    if not dimension_data:
        issues.append(_issue(
            "dimension_validation_missing",
            "critical",
            "reference_compare_v4",
            {"source": dimension_source},
            "Run dimension_validation before reference_compare_v4.",
        ))
    if not vision_data:
        issues.append(_issue(
            "vision_qc_v6_missing",
            "critical",
            "reference_compare_v4",
            {"source": vision_source},
            "Run vision_qc_v6 with application UI screenshot evidence before reference_compare_v4.",
        ))

    reference_views = _reference_view_summary(reference_data)
    generated_views = _blueprint_view_summary(blueprint_data)
    view_match = _view_match(reference_views, generated_views)
    _append_view_issues(issues, reference_views, generated_views)
    _append_projected_view_issues(issues, blueprint_data, validation)

    reference_dims = _int(reference_data.get("display_dim_count"))
    required_dims = max(
        reference_dims,
        _int(((blueprint_data.get("dimension_plan") or {}).get("reference_display_dim_count"))),
        _int(((blueprint_data.get("dimension_plan") or {}).get("required_display_dim_count"))),
    )
    generated_dims, generated_dim_source = _generated_display_dim_count(
        dimension_data,
        vision_data,
        legacy_ref_data,
    )
    note_dim_count = _generated_note_dim_count(dimension_data, vision_data)
    dimension_match = 1.0 if required_dims <= 0 and generated_dims > 0 else _ratio_score(generated_dims, required_dims)
    _append_dimension_issues(
        issues,
        generated_dims=generated_dims,
        generated_dim_source=generated_dim_source,
        required_dims=required_dims,
        reference_dims=reference_dims,
        note_dim_count=note_dim_count,
        blueprint=blueprint_data,
    )
    _append_dimension_source_issues(
        issues,
        dimension_data=dimension_data,
        generated_dim_source=generated_dim_source,
        blueprint=blueprint_data,
        base=base_name,
    )
    target_coverage = _reference_intent_target_coverage(generator_warnings_data, blueprint_data)
    _append_reference_intent_target_coverage_issues(issues, target_coverage, blueprint_data)
    _append_reference_intent_final_blocker_issues(issues, generator_warnings_data)

    titlebar_match = _titlebar_match(blueprint_data, vision_data, legacy_style_data)
    notes_match = _notes_match(blueprint_data, vision_data)
    layout_match = _layout_match(vision_data, legacy_style_data)
    symbol_match = _symbol_match(blueprint_data, vision_data)
    drawing_purpose_match = _drawing_purpose_match(blueprint_data)
    _append_visual_issues(issues, blueprint_data, vision_data, titlebar_match, notes_match, layout_match, symbol_match)
    _append_score_issues(
        issues,
        {
            "view_match": view_match,
            "dimension_match": dimension_match,
            "titlebar_match": titlebar_match,
            "notes_match": notes_match,
            "layout_match": layout_match,
        },
        thresholds,
    )

    scores = {
        "view_match": round(view_match, 3),
        "dimension_match": round(dimension_match, 3),
        "titlebar_match": round(titlebar_match, 3),
        "notes_match": round(notes_match, 3),
        "layout_match": round(layout_match, 3),
        "symbol_match": round(symbol_match, 3),
        "drawing_purpose_match": round(drawing_purpose_match, 3),
    }
    scores["overall_score"] = round(
        scores["view_match"] * 0.22
        + scores["dimension_match"] * 0.24
        + scores["titlebar_match"] * 0.14
        + scores["notes_match"] * 0.14
        + scores["layout_match"] * 0.14
        + scores["symbol_match"] * 0.08
        + scores["drawing_purpose_match"] * 0.04,
        3,
    )

    severity_set = {str(item.get("severity") or "") for item in issues}
    if "critical" in severity_set:
        status = "fail"
    elif issues:
        status = "need_review"
    else:
        status = "pass"

    payload = _base_payload(
        base=base_name,
        blueprint_source=blueprint_source,
        reference_source=reference_source,
        dimension_source=dimension_source,
        vision_source=vision_source,
        generator_warnings_source=generator_warnings_source,
        legacy_ref_source=legacy_ref_source,
        legacy_style_source=legacy_style_source,
        thresholds=thresholds,
    )
    payload.update({
        "status": status,
        "pass": status == "pass",
        "visual_acceptance_pass": bool(vision_data.get("visual_acceptance_pass")),
        "api_is_not_final_judgement": True,
        "scores": scores,
        "view_match_score": scores["view_match"],
        "dimension_match_score": scores["dimension_match"],
        "titlebar_match_score": scores["titlebar_match"],
        "notes_match_score": scores["notes_match"],
        "layout_match_score": scores["layout_match"],
        "symbol_match_score": scores["symbol_match"],
        "drawing_purpose_match_score": scores["drawing_purpose_match"],
        "overall_score": scores["overall_score"],
        "reference": {
            "base": reference_data.get("base") or base_name,
            "view_count": reference_views["view_count"],
            "view_types": reference_views["view_types"],
            "display_dim_count": reference_dims,
            "sheet_size": reference_data.get("sheet_size") or {},
            "scale": reference_data.get("scale"),
            "roughness_symbol_count": len(reference_data.get("roughness_symbols") or []),
            "datum_symbol_count": len(reference_data.get("datum_symbols") or []),
            "notes_count": len(reference_data.get("normalized_notes") or reference_data.get("notes_raw_text") or []),
        },
        "generated": {
            "base": blueprint_data.get("base") or base_name,
            "view_count": generated_views["view_count"],
            "view_types": generated_views["view_types"],
            "display_dim_count": generated_dims,
            "display_dim_count_source": generated_dim_source,
            "note_dim_count": note_dim_count,
            "reference_intent_target_coverage": target_coverage,
            "drawing_purpose": blueprint_data.get("drawing_purpose") or "",
            "part_class": blueprint_data.get("part_class") or "",
            "projected_view_methods": generated_views["projected_view_methods"],
        },
        "differences": issues,
        "reasons": [str(item.get("key")) for item in issues if item.get("severity") in {"critical", "major"}],
        "failure_bucket": _failure_buckets(issues),
        "fix_suggestions": _unique([str(item.get("fix_suggestion") or "") for item in issues]),
    })
    _write_if_requested(payload, out_path)
    return payload


def _load_json(value: dict[str, Any] | str | Path | None) -> tuple[dict[str, Any], str]:
    if value is None:
        return {}, "missing"
    if isinstance(value, dict):
        return value, "inline"
    path = Path(value)
    if not path.exists():
        return {}, str(path)
    try:
        return json.loads(path.read_text(encoding="utf-8-sig")), str(path)
    except Exception as exc:
        return {}, f"{path}: {exc}"


def _resolve_reference_profile(
    *,
    reference_profile: dict[str, Any] | str | Path | None,
    reference_profiles: dict[str, Any] | str | Path | None,
    base: str,
) -> tuple[dict[str, Any], str]:
    payload, source = _load_json(reference_profile)
    if payload and "profiles" not in payload:
        return payload, source
    if payload:
        profiles_payload = payload
        profiles_source = source
    else:
        profiles_payload, profiles_source = _load_json(reference_profiles)
    profiles = profiles_payload.get("profiles") or {}
    if not profiles:
        return {}, profiles_source or "missing"
    if base in profiles:
        return profiles[base], profiles_source
    stem = Path(base).stem
    if stem in profiles:
        return profiles[stem], profiles_source
    for key, item in profiles.items():
        if Path(str(key)).stem == stem or Path(str(item.get("base") or "")).stem == stem:
            return item, profiles_source
    return {}, profiles_source


def _base_payload(
    *,
    base: str,
    blueprint_source: str,
    reference_source: str,
    dimension_source: str,
    vision_source: str,
    generator_warnings_source: str,
    legacy_ref_source: str,
    legacy_style_source: str,
    thresholds: dict[str, float],
) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "base": base,
        "mode": "reference_compare_v4",
        "thresholds": thresholds,
        "artifacts": {
            "drawing_blueprint": blueprint_source,
            "reference_profile": reference_source,
            "dimension_validation": dimension_source,
            "vision_qc_v6": vision_source,
            "generator_warnings": generator_warnings_source,
            "legacy_reference_compare": legacy_ref_source,
            "legacy_reference_style": legacy_style_source,
        },
    }


def _write_if_requested(payload: dict[str, Any], out_path: str | Path | None) -> None:
    if not out_path:
        return
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _reference_view_summary(reference: dict[str, Any]) -> dict[str, Any]:
    view_types = {str(k): _int(v) for k, v in (reference.get("view_types") or {}).items()}
    return {
        "view_count": _int(reference.get("view_count")) or sum(view_types.values()),
        "view_types": {k: v for k, v in view_types.items() if v > 0},
    }


def _blueprint_view_summary(blueprint: dict[str, Any]) -> dict[str, Any]:
    plans = [item for item in blueprint.get("view_plan") or [] if isinstance(item, dict) and item.get("required") is not False]
    counts: Counter[str] = Counter()
    projected_methods: list[dict[str, Any]] = []
    for item in plans:
        sw_type = str(item.get("sw_view_type") or "")
        if not sw_type:
            sw_type = "4" if _is_projected_view(item) else "7"
        counts[sw_type] += 1
        if _is_projected_view(item):
            projected_methods.append({
                "slot": item.get("slot") or "",
                "sw_view_type": sw_type,
                "create_method": item.get("create_method") or "",
                "projected_from": item.get("projected_from") or "",
            })
    return {
        "view_count": len(plans),
        "view_types": dict(counts),
        "projected_view_methods": projected_methods,
    }


def _view_match(reference: dict[str, Any], generated: dict[str, Any]) -> float:
    ref_count = _int(reference.get("view_count"))
    gen_count = _int(generated.get("view_count"))
    if ref_count <= 0 or gen_count <= 0:
        return 0.0
    count_score = 1.0 if ref_count == gen_count else min(ref_count, gen_count) / max(ref_count, gen_count)
    ref_types = reference.get("view_types") or {}
    gen_types = generated.get("view_types") or {}
    if not ref_types:
        type_score = 0.0
    else:
        matched = 0
        required = 0
        for key, ref_value in ref_types.items():
            ref_int = _int(ref_value)
            required += ref_int
            matched += min(ref_int, _int(gen_types.get(key)))
        type_score = matched / required if required else 0.0
    return round(count_score * 0.5 + type_score * 0.5, 3)


def _append_view_issues(issues: list[dict[str, Any]], reference: dict[str, Any], generated: dict[str, Any]) -> None:
    ref_count = _int(reference.get("view_count"))
    gen_count = _int(generated.get("view_count"))
    if ref_count and gen_count < ref_count:
        issues.append(_issue(
            "view_count_lower_than_reference",
            "major",
            "reference_compare_v4.view_count",
            {"reference": ref_count, "generated": gen_count},
            "Create every required view from DrawingBlueprint.view_plan before acceptance.",
        ))
    if ref_count and gen_count > ref_count:
        issues.append(_issue(
            "view_count_higher_than_reference",
            "major",
            "reference_compare_v4.view_count",
            {"reference": ref_count, "generated": gen_count},
            "Do not add extra view families that are absent from the same-name reference drawing.",
        ))
    ref_types = reference.get("view_types") or {}
    gen_types = generated.get("view_types") or {}
    for key, count in ref_types.items():
        if _int(gen_types.get(key)) < _int(count):
            issues.append(_issue(
                "view_type_lower_than_reference",
                "major",
                "reference_compare_v4.view_types",
                {"view_type": key, "reference": _int(count), "generated": _int(gen_types.get(key))},
                "Match the reference drawing view type family before acceptance.",
            ))
    for key, count in gen_types.items():
        if key not in ref_types and _int(count) > 0:
            issues.append(_issue(
                "view_type_extra_than_reference",
                "major",
                "reference_compare_v4.view_types",
                {"view_type": key, "reference": 0, "generated": _int(count)},
                "Remove generated view types that are not present in the reference drawing.",
            ))


def _append_projected_view_issues(issues: list[dict[str, Any]], blueprint: dict[str, Any], validation: dict[str, Any]) -> None:
    if validation.get("forbid_named_view_as_projected", True) is False:
        return
    for item in blueprint.get("view_plan") or []:
        if not isinstance(item, dict) or item.get("required") is False:
            continue
        if not _is_projected_view(item):
            continue
        if str(item.get("create_method") or "") != "projection_api":
            issues.append(_issue(
                "projected_view_not_projection_api",
                "critical",
                "drawing_blueprint.view_plan",
                {
                    "slot": item.get("slot") or "",
                    "view_type": item.get("view_type") or "",
                    "sw_view_type": item.get("sw_view_type") or "",
                    "create_method": item.get("create_method") or "",
                },
                "Create projected views with the SolidWorks projection API; named views cannot stand in for projected views.",
            ))


def _append_dimension_issues(
    issues: list[dict[str, Any]],
    *,
    generated_dims: int,
    generated_dim_source: str,
    required_dims: int,
    reference_dims: int,
    note_dim_count: int,
    blueprint: dict[str, Any],
) -> None:
    if required_dims <= 0:
        issues.append(_issue(
            "reference_display_dim_baseline_missing",
            "major",
            "reference_compare_v4.dimension",
            {"reference_display_dim_count": reference_dims, "required_display_dim_count": required_dims},
            "Learn the same-name reference DisplayDim baseline; do not use a universal dim_total gate.",
        ))
    if generated_dims < required_dims:
        issues.append(_issue(
            "display_dim_lower_than_reference",
            "critical",
            "reference_compare_v4.dimension",
            {
                "reference_display_dim_count": reference_dims,
                "required_display_dim_count": required_dims,
                "generated_display_dim_count": generated_dims,
                "generated_display_dim_count_source": generated_dim_source,
            },
            "Generate real SolidWorks DisplayDim objects until the drawing reaches the reference baseline.",
        ))
    dimension_plan = blueprint.get("dimension_plan") or {}
    if note_dim_count > 0 and dimension_plan.get("allow_note_substitution", False) is False:
        issues.append(_issue(
            "note_dimensions_not_counted_as_display_dim",
            "minor",
            "reference_compare_v4.dimension",
            {"note_dim_count": note_dim_count, "generated_display_dim_count": generated_dims},
            "Keep Note annotations separate; only real DisplayDim objects count toward the reference dimension baseline.",
        ))


def _append_dimension_source_issues(
    issues: list[dict[str, Any]],
    *,
    dimension_data: dict[str, Any],
    generated_dim_source: str,
    blueprint: dict[str, Any],
    base: str,
) -> None:
    if not _is_strict_reference_intent_case(base, blueprint):
        return
    dimension_validation = dimension_data.get("dimension_validation") or {}
    policy = str(dimension_validation.get("dimension_evidence_policy") or "")
    sidecar_policy_allowed = dimension_validation.get("sidecar_policy_allowed")
    strict_reported = dimension_validation.get("strict_reference_intent_case")
    suspicious = (
        "sidecar" in policy.lower()
        or "note" in policy.lower()
        or policy == "strict_reference_intent_display_dim_required"
        or sidecar_policy_allowed is False and policy and policy != "display_dim"
    )
    if not suspicious:
        return
    issues.append(_issue(
        "strict_reference_intent_display_dim_source_not_real",
        "critical",
        "reference_compare_v4.dimension_source",
        {
            "base": base,
            "generated_display_dim_count_source": generated_dim_source,
            "dimension_evidence_policy": policy,
            "sidecar_policy_allowed": sidecar_policy_allowed,
            "strict_reference_intent_case": strict_reported,
        },
        "For strict LB26001 reference-intent drawings, only real SolidWorks DisplayDim evidence can satisfy the dimension gate; sidecar/Note/OCR evidence is diagnostic only.",
    ))


def _is_strict_reference_intent_case(base: str, blueprint: dict[str, Any]) -> bool:
    if str(base or blueprint.get("base") or "") in STRICT_REFERENCE_INTENT_BASES:
        return True
    dimension_plan = blueprint.get("dimension_plan") or {}
    return bool(dimension_plan.get("dimension_targets"))


def _reference_intent_target_coverage(
    generator_warnings: dict[str, Any],
    blueprint: dict[str, Any],
) -> dict[str, Any]:
    dimension_plan = blueprint.get("dimension_plan") or {}
    expected_targets = [
        str(item.get("key") or "")
        for item in (dimension_plan.get("dimension_targets") or [])
        if isinstance(item, dict) and str(item.get("key") or "")
    ]
    if not expected_targets:
        return {
            "required": False,
            "expected_target_count": 0,
            "latest_stage": "",
            "covered_target_keys": [],
            "missing_target_keys": [],
            "coverage_present": False,
        }

    snapshots = []
    for item in generator_warnings.get("reference_intent_target_coverage") or []:
        if isinstance(item, dict):
            snapshots.append(item)
    for item in generator_warnings.get("warnings") or []:
        if isinstance(item, dict) and item.get("code") == "reference_intent_target_coverage":
            snapshots.append(item)
    stage_delta = _reference_intent_target_coverage_delta(generator_warnings)

    preferred_order = [
        "post_layout_final",
        "post_layout_reopen_before_repair",
        "pre_export_final",
        "post_saveas_reopen_prune",
        "pre_saveas",
    ]
    by_stage = {str(item.get("stage") or ""): item for item in snapshots}
    latest = {}
    for stage in preferred_order:
        if stage in by_stage:
            latest = by_stage[stage]
            break
    if not latest and snapshots:
        latest = snapshots[-1]

    expected_set = set(expected_targets)
    covered = [str(item) for item in latest.get("covered_target_keys") or [] if str(item) in expected_set]
    missing_from_latest = [str(item) for item in latest.get("missing_target_keys") or [] if str(item)]
    if latest:
        missing = sorted(expected_set - set(covered) | (set(missing_from_latest) & expected_set))
    else:
        missing = sorted(expected_set)

    return {
        "required": True,
        "expected_target_count": len(expected_targets),
        "expected_target_keys": expected_targets,
        "coverage_present": bool(latest),
        "final_stage_required": True,
        "final_stage_present": "post_layout_final" in by_stage,
        "snapshot_count": len(snapshots),
        "latest_stage": str(latest.get("stage") or ""),
        "latest_display_dim_count": _int(latest.get("display_dim_count")),
        "covered_count": len(covered),
        "covered_target_keys": covered,
        "missing_target_keys": missing,
        "lost_target_keys": [
            str(item)
            for item in stage_delta.get("lost_target_keys") or []
            if str(item) in expected_set
        ],
        "stage_delta": stage_delta,
        "persisted_after_reopen": bool(latest.get("persisted_after_reopen")),
        "latest_snapshot": latest,
    }


def _reference_intent_target_coverage_delta(generator_warnings: dict[str, Any]) -> dict[str, Any]:
    direct = generator_warnings.get("reference_intent_target_coverage_delta")
    if isinstance(direct, dict):
        return direct
    for item in generator_warnings.get("warnings") or []:
        if isinstance(item, dict) and item.get("code") == "reference_intent_target_coverage_stage_delta":
            return item
    return {}


def _append_reference_intent_target_coverage_issues(
    issues: list[dict[str, Any]],
    target_coverage: dict[str, Any],
    blueprint: dict[str, Any],
) -> None:
    if not target_coverage.get("required"):
        return
    if not target_coverage.get("coverage_present"):
        issues.append(_issue(
            "reference_intent_target_coverage_missing",
            "major",
            "reference_compare_v4.dimension_targets",
            {
                "expected_target_count": target_coverage.get("expected_target_count"),
                "expected_target_keys": target_coverage.get("expected_target_keys"),
            },
            "Run the v4.2 generator with reference_intent_target_coverage snapshots before accepting this drawing.",
        ))
        return
    if target_coverage.get("final_stage_required") and not target_coverage.get("final_stage_present"):
        issues.append(_issue(
            "reference_intent_post_layout_final_coverage_missing",
            "critical",
            "reference_compare_v4.dimension_targets",
            {
                "expected_target_keys": target_coverage.get("expected_target_keys"),
                "snapshot_count": target_coverage.get("snapshot_count"),
                "latest_stage": target_coverage.get("latest_stage"),
            },
            "Run the v4.2 generator through SaveAs, Close/Reopen, post-layout repair, and final export so post_layout_final target coverage is available before accepting this drawing.",
        ))
    missing = list(target_coverage.get("missing_target_keys") or [])
    if missing:
        issues.append(_issue(
            "reference_intent_targets_missing_after_persistence",
            "critical",
            "reference_compare_v4.dimension_targets",
            {
                "latest_stage": target_coverage.get("latest_stage"),
                "covered_target_keys": target_coverage.get("covered_target_keys"),
                "missing_target_keys": missing,
                "lost_target_keys": target_coverage.get("lost_target_keys", []),
                "stage_delta": target_coverage.get("stage_delta", {}),
                "latest_display_dim_count": target_coverage.get("latest_display_dim_count"),
                "persisted_after_reopen": target_coverage.get("persisted_after_reopen"),
            },
            "Fix explicit SolidWorks DisplayDim persistence until every required reference-intent target survives SaveAs, Close/Reopen, post-layout repair, and export.",
        ))


def _append_reference_intent_final_blocker_issues(
    issues: list[dict[str, Any]],
    generator_warnings: dict[str, Any],
) -> None:
    blockers = _reference_intent_final_blockers(generator_warnings)
    if not blockers:
        return
    issues.append(_issue(
        "post_layout_reference_intent_final_blocked",
        "critical",
        "generator.post_layout_dim_repair",
        {
            "blockers": blockers,
            "warning_codes": [
                str(item.get("code") or "")
                for item in generator_warnings.get("warnings") or []
                if isinstance(item, dict) and item.get("code")
            ],
        },
        "Fix the generator so post_layout_final has no DisplayDim floor gap and no missing reference-intent target keys before accepting the drawing.",
    ))


def _reference_intent_final_blockers(generator_warnings: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for item in generator_warnings.get("warnings") or []:
        if not isinstance(item, dict):
            continue
        if item.get("code") != "post_layout_reference_intent_final_blocked":
            continue
        for blocker in item.get("blockers") or []:
            if isinstance(blocker, dict):
                blockers.append(blocker)
    post_layout = generator_warnings.get("post_layout_dim_repair") or {}
    for blocker in post_layout.get("final_acceptance_blockers") or []:
        if isinstance(blocker, dict) and blocker not in blockers:
            blockers.append(blocker)
    return blockers


def _append_visual_issues(
    issues: list[dict[str, Any]],
    blueprint: dict[str, Any],
    vision: dict[str, Any],
    titlebar_match: float,
    notes_match: float,
    layout_match: float,
    symbol_match: float,
) -> None:
    validation = blueprint.get("validation_plan") or {}
    require_ui = bool(validation.get("require_ui_visual_review", True))
    if require_ui:
        ui_review = (vision.get("checks") or {}).get("ui_screenshot_review") or {}
        if not vision.get("visual_acceptance_pass") or not ui_review.get("pass"):
            issues.append(_issue(
                "ui_screenshot_visual_acceptance_not_passed",
                "major",
                "application_ui_screenshot_review",
                {
                    "vision_qc_status": vision.get("status") or "",
                    "visual_acceptance_pass": vision.get("visual_acceptance_pass"),
                    "ui_screenshot_review": ui_review,
                    "api_is_not_final_judgement": True,
                },
                "Use the application Drawing Review UI to screenshot and judge this drawing against the reference before acceptance.",
            ))
    if titlebar_match < 0.85:
        issues.append(_issue(
            "titlebar_match_below_threshold",
            "major",
            "vision_qc_v6.titlebar",
            {"titlebar_match": round(titlebar_match, 3)},
            "Fill and visually render the titlebar fields from DrawingBlueprint.titlebar_plan.",
        ))
    if notes_match < 0.85:
        issues.append(_issue(
            "notes_match_below_threshold",
            "major",
            "vision_qc_v6.notes",
            {"notes_match": round(notes_match, 3)},
            "Render the learned notes and technical requirements in the reference notes area.",
        ))
    if layout_match < 0.80:
        issues.append(_issue(
            "layout_match_below_threshold",
            "major",
            "vision_qc_v6.layout",
            {"layout_match": round(layout_match, 3)},
            "Align view placement, titlebar, notes, and coarse ink layout with the same-name reference.",
        ))
    if symbol_match < 0.80:
        issues.append(_issue(
            "symbol_match_below_threshold",
            "major",
            "vision_qc_v6.symbols",
            {"symbol_match": round(symbol_match, 3)},
            "Render required roughness, datum, centerline, center mark, and section-arrow symbols from the blueprint.",
        ))


def _append_score_issues(
    issues: list[dict[str, Any]],
    scores: dict[str, float],
    thresholds: dict[str, float],
) -> None:
    for key, threshold in thresholds.items():
        score = scores.get(key, 0.0)
        if score < threshold:
            issues.append(_issue(
                f"{key}_score_below_v4_threshold",
                "major",
                "reference_compare_v4.score",
                {"score": round(score, 3), "threshold": threshold},
                "Correct the drawing against the same-name reference before accepting the staged case.",
            ))


def _generated_display_dim_count(
    dimension: dict[str, Any],
    vision: dict[str, Any],
    legacy_ref: dict[str, Any],
) -> tuple[int, str]:
    candidates = [
        (dimension.get("display_dim_count"), "dimension_validation.display_dim_count"),
        ((dimension.get("dimension_validation") or {}).get("display_dim_count"), "dimension_validation.dimension_validation.display_dim_count"),
        ((dimension.get("dimension_validation") or {}).get("existing_display_dim_count"), "dimension_validation.dimension_validation.existing_display_dim_count"),
        (((dimension.get("dimension_validation") or {}).get("dimension_sources") or {}).get("display_dim_count"), "dimension_validation.dimension_sources.display_dim_count"),
        (((vision.get("checks") or {}).get("geometry_qc_supporting") or {}).get("display_dim_count"), "vision_qc_v6.geometry_qc_supporting.display_dim_count"),
        ((legacy_ref.get("generated_metrics") or {}).get("display_dim_count"), "legacy_reference_compare.generated_metrics.display_dim_count"),
    ]
    for value, source in candidates:
        count = _int(value)
        if count > 0:
            return count, source
    return 0, "missing"


def _generated_note_dim_count(dimension: dict[str, Any], vision: dict[str, Any]) -> int:
    candidates = [
        dimension.get("note_dim_count"),
        (dimension.get("dimension_validation") or {}).get("note_dim_count"),
        (((dimension.get("dimension_validation") or {}).get("dimension_sources") or {}).get("note_dim_count")),
        (((vision.get("checks") or {}).get("geometry_qc_supporting") or {}).get("note_dim_count")),
    ]
    return max(_int(value) for value in candidates)


def _titlebar_match(blueprint: dict[str, Any], vision: dict[str, Any], legacy_style: dict[str, Any]) -> float:
    issues = _vision_issue_keys(vision)
    if "titlebar_missing_or_empty" in issues:
        return 0.0
    titlebar = (vision.get("checks") or {}).get("titlebar") or {}
    if titlebar.get("detected") is True:
        return 1.0
    titlebar_plan = blueprint.get("titlebar_plan") or {}
    required = titlebar_plan.get("required_fields") or []
    missing = titlebar_plan.get("missing_fields") or []
    if required:
        return max(0.0, 1.0 - (len(missing) / max(len(required), 1)))
    if legacy_style.get("pass") is True:
        return 1.0
    return 0.0 if vision else 0.5


def _notes_match(blueprint: dict[str, Any], vision: dict[str, Any]) -> float:
    issues = _vision_issue_keys(vision)
    if "technical_requirements_missing_or_empty" in issues:
        return 0.0
    notes_check = (vision.get("checks") or {}).get("notes") or {}
    notes_plan = blueprint.get("notes_plan") or {}
    requires_notes = bool(notes_plan.get("required_notes") or notes_plan.get("raw_reference_notes"))
    if not requires_notes:
        return 1.0
    if notes_check.get("technical_requirements_detected") is True or notes_check.get("detected") is True:
        return 1.0
    return 0.0 if vision else 0.5


def _layout_match(vision: dict[str, Any], legacy_style: dict[str, Any]) -> float:
    issues = _vision_issue_keys(vision)
    if "reference_visual_layout_mismatch" in issues:
        return 0.0
    compare = (vision.get("checks") or {}).get("reference_visual_compare") or {}
    if compare.get("coarse_layout_match") is True:
        return 1.0
    if compare:
        return 0.5
    if legacy_style.get("layout_style_score") is not None:
        return _float(legacy_style.get("layout_style_score"), 0.0)
    return 1.0 if legacy_style.get("pass") is True else 0.5


def _symbol_match(blueprint: dict[str, Any], vision: dict[str, Any]) -> float:
    issues = _vision_issue_keys(vision)
    blockers = {
        "roughness_plan_not_marked_required",
        "centerline_visual_missing",
        "center_mark_visual_missing",
        "section_arrow_visual_missing",
    }
    if blockers & issues:
        return 0.5
    symbols = (vision.get("checks") or {}).get("symbols") or {}
    if symbols.get("missing"):
        return 0.5
    annotation = blueprint.get("annotation_plan") or {}
    if any(annotation.get(key) for key in ["roughness_required", "datum_required", "center_marks_required", "centerlines_required", "section_arrows_required"]):
        return 1.0 if symbols else 0.5
    return 1.0


def _drawing_purpose_match(blueprint: dict[str, Any]) -> float:
    part_class = str(blueprint.get("part_class") or "")
    purpose = str(blueprint.get("drawing_purpose") or "")
    if part_class in {"fastener", "spring", "purchased_part"}:
        return 1.0 if purpose in {"procurement_or_assembly", "assembly", "procurement"} else 0.0
    if part_class == "assembly":
        return 1.0 if purpose == "assembly" else 0.0
    return 1.0 if purpose == "manufacturing" else 0.0


def _vision_issue_keys(vision: dict[str, Any]) -> set[str]:
    return {str(item.get("key") or "") for item in vision.get("issues") or [] if isinstance(item, dict)}


def _is_projected_view(item: dict[str, Any]) -> bool:
    return str(item.get("view_type") or "") == "projected" or str(item.get("sw_view_type") or "") == "4"


def _ratio_score(generated: int, required: int) -> float:
    if required <= 0:
        return 0.0
    return round(min(max(generated, 0) / required, 1.0), 3)


def _int(value: Any) -> int:
    try:
        return int(float(value))
    except Exception:
        return 0


def _float(value: Any, default: float) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _issue(
    key: str,
    severity: str,
    source: str,
    evidence: dict[str, Any],
    fix_suggestion: str,
) -> dict[str, Any]:
    issue = {
        "key": key,
        "severity": severity,
        "bbox": [0.0, 0.0, 1.0, 1.0],
        "source": source,
        "confidence": 1.0,
        "evidence": evidence,
        "fix_suggestion": fix_suggestion,
        "auto_fix_available": False,
        "human_review_status": "pending",
    }
    for field in REQUIRED_ISSUE_FIELDS:
        issue.setdefault(field, "unknown")
    return issue


def _failure_buckets(issues: list[dict[str, Any]]) -> list[str]:
    buckets = []
    for item in issues:
        key = str(item.get("key") or "")
        if key:
            buckets.append(key)
    return sorted(set(buckets))


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result
