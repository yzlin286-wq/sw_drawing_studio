"""Audit the LB26001-A-04-006 DisplayDim lifecycle from existing artifacts.

The audit is file-only. It explains where real SolidWorks DisplayDim objects
were lost between explicit creation, SaveAs/reopen/prune, sidecar diagnostics,
post-layout repair, and final validation evidence.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
BASE = "LB26001-A-04-006"
DEFAULT_WARNINGS = REPO_ROOT / "drw_output" / "runs" / "9558b08c8f63" / "qc" / "LB26001-A-04-006_v5_warnings.json"
DEFAULT_CAD_SMOKE = (
    REPO_ROOT
    / "drw_output"
    / "staged_validation"
    / "LB26001_006_explicit_displaydim_visible_entities_20260623"
    / "01_LB26001-A-04-006"
    / "cad_smoke.json"
)
DEFAULT_DIMENSION_VALIDATION = (
    REPO_ROOT
    / "drw_output"
    / "staged_validation"
    / "LB26001_006_explicit_displaydim_visible_entities_20260623"
    / "01_LB26001-A-04-006"
    / "dimension_validation.json"
)
DEFAULT_REFERENCE_INTENT_PLAN = REPO_ROOT / "drw_output" / "reference_intent_dimension_plan_006.json"
DEFAULT_OUT_JSON = REPO_ROOT / "drw_output" / "diagnostics" / "lb26001_006_displaydim_lifecycle_audit_v4_2.json"
DEFAULT_OUT_MD = REPO_ROOT / "drw_output" / "diagnostics" / "lb26001_006_displaydim_lifecycle_audit_v4_2.md"

TARGET_MATRIX_STAGES = [
    "pre_saveas",
    "post_saveas_reopen_prune",
    "post_saveas_reopen_prune_guard",
    "pre_export_final",
    "post_layout_final",
]
TARGET_TRACE_REQUIRED_FIELDS = [
    "target_key",
    "view_slot",
    "selected_entity",
    "add_method",
    "display_dim_count_before",
    "display_dim_count_after",
    "target_covered_after_attempt",
    "persisted_after_reopen",
]


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


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except Exception:
        return None


def _first_int_or_none(*values: Any) -> int | None:
    for value in values:
        parsed = _int_or_none(value)
        if parsed is not None:
            return parsed
    return None


def _nested(payload: dict[str, Any], *keys: str) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _reference_intent_targets(plan_path: Path | None) -> list[dict[str, Any]]:
    plan = _read_json(plan_path)
    dimensions = plan.get("dimensions") or []
    if not isinstance(dimensions, list):
        dimensions = []
    targets: list[dict[str, Any]] = []
    for index, item in enumerate(dimensions):
        if not isinstance(item, dict):
            continue
        key = str(item.get("target_key") or item.get("key") or item.get("dimension_key") or "").strip()
        if not key:
            key = f"target_{index + 1:02d}"
        targets.append(
            {
                "target_key": key,
                "group": str(item.get("group") or ""),
                "view_slot": str(item.get("target_view") or item.get("view_slot") or "").strip().lower(),
                "expected_type": str(item.get("expected_type") or ""),
                "expected_add_method": str(item.get("expected_add_method") or ""),
                "priority": _int_or_none(item.get("priority")),
                "required": bool(item.get("required", True)),
            }
        )
    targets.sort(key=lambda item: (item.get("priority") if item.get("priority") is not None else 9999, item["target_key"]))
    return targets


def _coverage_snapshots(warnings: dict[str, Any]) -> list[dict[str, Any]]:
    snapshots = warnings.get("reference_intent_target_coverage") or []
    if not isinstance(snapshots, list):
        return []
    return [item for item in snapshots if isinstance(item, dict)]


def _snapshot_by_stage(warnings: dict[str, Any]) -> dict[str, dict[str, Any]]:
    by_stage: dict[str, dict[str, Any]] = {}
    for item in _coverage_snapshots(warnings):
        stage = str(item.get("stage") or "")
        if stage:
            by_stage[stage] = item
    post_prune_guard = warnings.get("post_prune_dim_guard") or {}
    guard_coverage = post_prune_guard.get("target_coverage_after_guard") or {}
    if isinstance(guard_coverage, dict) and guard_coverage:
        by_stage.setdefault(
            "post_saveas_reopen_prune_guard",
            {"stage": "post_saveas_reopen_prune_guard", **guard_coverage},
        )
    post_layout = warnings.get("post_layout_dim_repair") or {}
    post_layout_final = post_layout.get("target_coverage_final") or {}
    if isinstance(post_layout_final, dict) and post_layout_final:
        by_stage.setdefault("post_layout_final", {"stage": "post_layout_final", **post_layout_final})
    return by_stage


def _target_result_key(item: dict[str, Any]) -> str:
    return str(item.get("target_key") or item.get("key") or item.get("dimension_key") or "").strip()


def _target_results_by_key(results: Any, targets: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    if not isinstance(results, list):
        return {}
    valid = [item for item in results if isinstance(item, dict)]
    by_key: dict[str, dict[str, Any]] = {}
    for item in valid:
        key = _target_result_key(item)
        if key:
            by_key[key] = dict(item)
    if by_key:
        return by_key
    if len(valid) == len(targets):
        for target, item in zip(targets, valid):
            copied = dict(item)
            copied["target_key_inferred_from_plan_order"] = True
            copied.setdefault("target_key", target["target_key"])
            by_key[target["target_key"]] = copied
    return by_key


def _stage_target_result(snapshot: dict[str, Any], target_key: str) -> dict[str, Any]:
    for item in snapshot.get("target_results") or []:
        if isinstance(item, dict) and _target_result_key(item) == target_key:
            return item
    return {}


def _target_coverage_state(snapshot: dict[str, Any] | None, target: dict[str, Any]) -> dict[str, Any]:
    target_key = target["target_key"]
    if not snapshot:
        return {
            "observed": False,
            "covered": None,
            "matched_count": None,
            "persisted_after_reopen": None,
            "source": "coverage_snapshot_missing",
        }
    result = _stage_target_result(snapshot, target_key)
    matched_count = _int_or_none(result.get("matched_count")) if result else None
    missing_keys = [str(value) for value in snapshot.get("missing_target_keys") or []]
    covered_keys = [str(value) for value in snapshot.get("covered_target_keys") or []]
    if matched_count is not None:
        covered = matched_count > 0
        source = "target_results.matched_count"
    elif target_key in covered_keys:
        covered = True
        source = "covered_target_keys"
    elif target_key in missing_keys:
        covered = False
        source = "missing_target_keys"
    elif "missing_target_keys" in snapshot:
        covered = True
        source = "missing_target_keys_inferred"
    else:
        covered = None
        source = "coverage_state_unknown"
    persisted = result.get("persisted_after_reopen") if result else snapshot.get("persisted_after_reopen")
    return {
        "observed": True,
        "covered": covered,
        "matched_count": matched_count,
        "persisted_after_reopen": bool(persisted) if persisted is not None else None,
        "source": source,
        "best_match_score": result.get("best_match_score") if result else None,
        "best_display_dim": result.get("best_display_dim") if result else {},
    }


def _selected_attempt(result: dict[str, Any]) -> dict[str, Any]:
    attempts = [item for item in result.get("attempts") or [] if isinstance(item, dict)]
    for item in attempts:
        if item.get("selected") and (item.get("display_dim_created") or item.get("add_method")):
            return item
    for item in attempts:
        if item.get("selected"):
            return item
    return attempts[0] if attempts else {}


def _attempt_trace(result: dict[str, Any], target: dict[str, Any], final_state: dict[str, Any]) -> dict[str, Any]:
    attempt = _selected_attempt(result)
    target_key = _target_result_key(result) or target["target_key"]
    view_slot = str(result.get("slot") or result.get("view_slot") or target.get("view_slot") or "")
    selected_entity = result.get("selected_entity") or attempt.get("selected_entity") or attempt.get("curve_identity")
    add_method = result.get("add_method") or attempt.get("add_method")
    before = _first_int_or_none(
        result.get("display_dim_count_before"),
        result.get("display_dim_count_before_target"),
        result.get("before"),
        attempt.get("display_dim_count_before"),
        attempt.get("before"),
    )
    after = _first_int_or_none(
        result.get("display_dim_count_after"),
        result.get("after"),
        attempt.get("display_dim_count_after"),
        attempt.get("after"),
    )
    covered_after_attempt = result.get("target_covered_after_attempt")
    if covered_after_attempt is None:
        covered_after_attempt = attempt.get("target_covered_after_attempt")
    persisted_after_reopen = result.get("persisted_after_reopen")
    if persisted_after_reopen is None:
        persisted_after_reopen = final_state.get("persisted_after_reopen")
    trace = {
        "target_key": target_key,
        "view_slot": view_slot,
        "selected_entity": selected_entity,
        "add_method": add_method,
        "expected_add_method": result.get("expected_add_method") or target.get("expected_add_method"),
        "display_dim_count_before": before,
        "display_dim_count_after": after,
        "target_covered_after_attempt": covered_after_attempt,
        "persisted_after_reopen": persisted_after_reopen,
    }
    missing = [
        field
        for field in TARGET_TRACE_REQUIRED_FIELDS
        if trace.get(field) in (None, "", [])
    ]
    trace["target_trace_missing_fields"] = missing
    trace["target_trace_complete"] = not missing
    if result.get("target_key_inferred_from_plan_order"):
        trace["target_key_inferred_from_plan_order"] = True
    return trace


def _coverage_trace_from_final_state(target: dict[str, Any], final_state: dict[str, Any]) -> dict[str, Any]:
    if final_state.get("covered") is not True:
        return {}
    matched_count = _int_or_none(final_state.get("matched_count"))
    best_display_dim = final_state.get("best_display_dim") or {}
    if matched_count is None and not best_display_dim:
        return {}
    evidence_count = matched_count if matched_count is not None else 1
    trace = {
        "target_key": target["target_key"],
        "view_slot": target.get("view_slot"),
        "selected_entity": {
            "source": "coverage_snapshot_target_result",
            "coverage_source": final_state.get("source"),
            "matched_count": matched_count,
            "best_display_dim": best_display_dim,
        },
        "add_method": "existing_display_dim_coverage",
        "expected_add_method": target.get("expected_add_method"),
        "display_dim_count_before": evidence_count,
        "display_dim_count_after": evidence_count,
        "target_covered_after_attempt": True,
        "persisted_after_reopen": final_state.get("persisted_after_reopen"),
        "explicit_add_trace_required": False,
        "trace_source": "existing_display_dim_coverage",
    }
    missing = [
        field
        for field in TARGET_TRACE_REQUIRED_FIELDS
        if trace.get(field) in (None, "", [])
    ]
    trace["target_trace_missing_fields"] = missing
    trace["target_trace_complete"] = not missing
    return trace


def _target_lost_stage(stage_states: list[dict[str, Any]]) -> str:
    last_covered_stage = ""
    for item in stage_states:
        covered = item.get("covered")
        stage = str(item.get("stage") or "")
        if covered is True:
            last_covered_stage = stage
        elif covered is False and last_covered_stage:
            return stage
    final = stage_states[-1] if stage_states else {}
    if final.get("covered") is not True:
        for item in stage_states:
            if item.get("covered") is False:
                return str(item.get("stage") or "")
        return "post_layout_final"
    return ""


def _target_stage_matrix(
    warnings: dict[str, Any],
    *,
    reference_intent_plan_path: Path | None,
) -> dict[str, Any]:
    targets = _reference_intent_targets(reference_intent_plan_path)
    snapshots = _snapshot_by_stage(warnings)
    post_layout_explicit = _nested(warnings, "post_layout_dim_repair", "explicit_display_dims") or {}
    post_prune_explicit = _nested(warnings, "post_prune_dim_guard", "explicit_display_dims") or {}
    post_layout_results = _target_results_by_key(post_layout_explicit.get("target_results"), targets)
    post_prune_results = _target_results_by_key(post_prune_explicit.get("target_results"), targets)
    rows: list[dict[str, Any]] = []
    missing_final: list[str] = []
    trace_incomplete: list[str] = []
    missing_snapshots: list[str] = []
    view_not_found: list[str] = []
    inferred_target_keys: list[str] = []
    for target in targets:
        key = target["target_key"]
        stage_states = []
        for stage in TARGET_MATRIX_STAGES:
            state = _target_coverage_state(snapshots.get(stage), target)
            state["stage"] = stage
            stage_states.append(state)
            if not state["observed"] and stage not in missing_snapshots:
                missing_snapshots.append(stage)
        final_state = next((item for item in stage_states if item["stage"] == "post_layout_final"), {})
        post_layout_result = post_layout_results.get(key) or {}
        post_prune_result = post_prune_results.get(key) or {}
        trace_source = post_layout_result or post_prune_result
        if trace_source:
            trace = _attempt_trace(trace_source, target, final_state)
        else:
            trace = _coverage_trace_from_final_state(target, final_state) or {
                "target_key": key,
                "view_slot": target.get("view_slot"),
                "selected_entity": None,
                "add_method": None,
                "expected_add_method": target.get("expected_add_method"),
                "display_dim_count_before": None,
                "display_dim_count_after": None,
                "target_covered_after_attempt": None,
                "persisted_after_reopen": final_state.get("persisted_after_reopen"),
                "target_trace_missing_fields": TARGET_TRACE_REQUIRED_FIELDS[2:],
                "target_trace_complete": False,
            }
        if trace.get("target_key_inferred_from_plan_order"):
            inferred_target_keys.append(key)
        if not trace.get("target_trace_complete"):
            trace_incomplete.append(key)
        if final_state.get("covered") is not True:
            missing_final.append(key)
        reason = str(post_layout_result.get("reason") or post_prune_result.get("reason") or "")
        if reason == "target_view_not_found":
            view_not_found.append(key)
        rows.append(
            {
                **target,
                "stage_states": stage_states,
                "post_prune_guard_attempt": {
                    "present": bool(post_prune_result),
                    "success": post_prune_result.get("success"),
                    "reason": post_prune_result.get("reason"),
                },
                "post_layout_attempt": {
                    "present": bool(post_layout_result),
                    "success": post_layout_result.get("success"),
                    "reason": post_layout_result.get("reason"),
                    "view_source": post_layout_result.get("view_source"),
                },
                "trace": trace,
                "lost_stage": _target_lost_stage(stage_states),
                "blocking": (
                    final_state.get("covered") is not True
                    or not trace.get("target_trace_complete")
                    or reason == "target_view_not_found"
                ),
            }
        )
    return {
        "target_count": len(targets),
        "required_stage_order": TARGET_MATRIX_STAGES,
        "required_trace_fields": TARGET_TRACE_REQUIRED_FIELDS,
        "missing_snapshot_stages": missing_snapshots,
        "post_layout_final_missing_target_keys": missing_final,
        "target_trace_incomplete_keys": trace_incomplete,
        "target_view_not_found_keys": view_not_found,
        "target_keys_inferred_from_plan_order": inferred_target_keys,
        "rows": rows,
        "pass": bool(targets) and not missing_final and not trace_incomplete and not missing_snapshots and not view_not_found,
    }


def _display_floor(warnings: dict[str, Any], cad_smoke: dict[str, Any], dimension_validation: dict[str, Any]) -> int:
    candidates = [
        _nested(warnings, "drawing_blueprint_v4", "dimension_plan", "required_display_dim_count"),
        _nested(warnings, "drawing_blueprint_v4", "dimension_plan", "reference_display_dim_count"),
        _nested(cad_smoke, "status", "result", "reference_intent_dimension", "required_display_dim_count"),
        _nested(dimension_validation, "reference_display_dim_count"),
        _nested(dimension_validation, "required_display_dim_count"),
    ]
    for value in candidates:
        parsed = _int_or_none(value)
        if parsed:
            return max(12, parsed)
    return 12


def _stage(name: str, count: Any, *, source: str, evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "stage": name,
        "display_dim_count": _int_or_none(count),
        "source": source,
        "evidence": evidence or {},
    }


def _stage_counts(warnings: dict[str, Any], dimension_validation: dict[str, Any]) -> list[dict[str, Any]]:
    reference_autodim = warnings.get("reference_autodim") or {}
    prune = _nested(warnings, "reference_dim_prune", "prune") or {}
    post_prune_guard = warnings.get("post_prune_dim_guard") or {}
    post_layout = warnings.get("post_layout_dim_repair") or {}
    explicit = post_layout.get("explicit_display_dims") or {}
    prune_after = prune.get("after")
    prune_source = "warnings.reference_dim_prune.prune.after"
    if prune.get("discarded_after_failed_prune") and prune.get("after_restored") is not None:
        prune_after = prune.get("after_restored")
        prune_source = "warnings.reference_dim_prune.prune.after_restored"
    dim_validation_count = (
        _nested(dimension_validation, "dimension_validation", "display_dim_count")
        or dimension_validation.get("display_dim_count")
        or dimension_validation.get("generated_display_dim_count")
    )
    return [
        _stage("pre_saveas_explicit_before", reference_autodim.get("before"), source="warnings.reference_autodim.before"),
        _stage("pre_saveas_explicit_after", reference_autodim.get("after"), source="warnings.reference_autodim.after"),
        _stage("post_saveas_reopen_prune_before", prune.get("before"), source="warnings.reference_dim_prune.prune.before"),
        _stage("post_saveas_reopen_prune_after", prune_after, source=prune_source),
        _stage("post_prune_guard_before", post_prune_guard.get("before"), source="warnings.post_prune_dim_guard.before"),
        _stage("post_prune_guard_after", post_prune_guard.get("after"), source="warnings.post_prune_dim_guard.after"),
        _stage("before_sidecar_diagnostic", warnings.get("display_dim_count_before_sidecar"), source="warnings.display_dim_count_before_sidecar"),
        _stage("pre_export_final", warnings.get("display_dim_count_final"), source="warnings.display_dim_count_final"),
        _stage("post_layout_before_repair", post_layout.get("before"), source="warnings.post_layout_dim_repair.before"),
        _stage("post_layout_explicit_after", explicit.get("after"), source="warnings.post_layout_dim_repair.explicit_display_dims.after"),
        _stage(
            "post_layout_final_exact_prune_before",
            post_layout.get("post_layout_final_exact_prune_display_dim_count_before"),
            source="warnings.post_layout_dim_repair.post_layout_final_exact_prune_display_dim_count_before",
        ),
        _stage(
            "post_layout_final_exact_prune_after",
            post_layout.get("post_layout_final_exact_prune_display_dim_count_after"),
            source="warnings.post_layout_dim_repair.post_layout_final_exact_prune_display_dim_count_after",
        ),
        _stage("post_layout_final", post_layout.get("after"), source="warnings.post_layout_dim_repair.after"),
        _stage("dimension_validation_final", dim_validation_count, source="dimension_validation.display_dim_count"),
    ]


def _loss_events(stages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    previous: dict[str, Any] | None = None
    for stage in stages:
        current_count = stage.get("display_dim_count")
        if current_count is None:
            continue
        if previous is not None:
            previous_count = previous.get("display_dim_count")
            if previous_count is not None and current_count < previous_count:
                events.append({
                    "from_stage": previous.get("stage"),
                    "to_stage": stage.get("stage"),
                    "from_count": previous_count,
                    "to_count": current_count,
                    "lost_count": previous_count - current_count,
                })
        previous = stage
    return events


def _coverage_summary(warnings: dict[str, Any]) -> dict[str, Any]:
    snapshots = warnings.get("reference_intent_target_coverage") or []
    if not isinstance(snapshots, list):
        snapshots = []
    stage_names = [
        str(item.get("stage") or "")
        for item in snapshots
        if isinstance(item, dict) and str(item.get("stage") or "")
    ]
    final = next((item for item in snapshots if isinstance(item, dict) and item.get("stage") == "post_layout_final"), {})
    post_prune_guard = next((item for item in snapshots if isinstance(item, dict) and item.get("stage") == "post_saveas_reopen_prune_guard"), {})
    missing_final = list((final or {}).get("missing_target_keys") or [])
    return {
        "snapshot_count": len(snapshots),
        "stages": stage_names,
        "post_prune_guard_present": bool(post_prune_guard),
        "post_layout_final_present": bool(final),
        "post_layout_final_missing_target_keys": missing_final,
        "coverage_delta_present": bool(warnings.get("reference_intent_target_coverage_delta")),
    }


def _slot_rebind_diagnostics_summary(explicit: dict[str, Any]) -> dict[str, Any]:
    diagnostics = [
        item
        for item in explicit.get("slot_rebind_diagnostics") or []
        if isinstance(item, dict)
    ]
    direct_accept_failed_items: list[dict[str, Any]] = []
    recovered_by_persisted_name: list[dict[str, Any]] = []
    persisted_name_failed: list[dict[str, Any]] = []
    details: list[dict[str, Any]] = []
    for item in diagnostics:
        source = str(item.get("source") or "")
        direct_accept_failed = bool(item.get("direct_accept_failed"))
        accepted = bool(item.get("accepted"))
        if direct_accept_failed:
            direct_accept_failed_items.append(item)
            if accepted and "direct_accept_failed_select_by_persisted_name" in source:
                recovered_by_persisted_name.append(item)
            if (not accepted) and (
                "direct_accept_failed_select_by_persisted_name_failed" in source
                or "select_by_persisted_name_failed" in source
            ):
                persisted_name_failed.append(item)
        if direct_accept_failed or "direct_accept_failed_select_by_persisted_name" in source:
            details.append({
                "slot": item.get("slot"),
                "view_name": item.get("view_name") or item.get("matched_view_name"),
                "accepted": accepted,
                "direct_accept_failed": direct_accept_failed,
                "source": source,
                "distance": item.get("distance"),
            })
    summary = explicit.get("slot_rebind_summary") or {}
    if isinstance(summary, list):
        summary = next((item for item in reversed(summary) if isinstance(item, dict)), {})
    if not isinstance(summary, dict):
        summary = {}
    unbound_slots = [
        str(item)
        for item in summary.get("unbound_slots") or []
        if str(item).strip()
    ]
    slot_results = summary.get("slot_results") or {}
    if not isinstance(slot_results, dict):
        slot_results = {}
    slot_failure_reasons: dict[str, int] = {}
    no_view_record_slots: list[str] = []
    no_candidate_slots: list[str] = []
    for slot, item in slot_results.items():
        if not isinstance(item, dict) or item.get("bound"):
            continue
        reason = str(item.get("reason") or "unknown")
        slot_failure_reasons[reason] = slot_failure_reasons.get(reason, 0) + 1
        slot_key = str(slot or "")
        if reason == "no_view_records":
            no_view_record_slots.append(slot_key)
        if reason in {"no_nearby_candidate_distances", "slot_match_not_attempted"}:
            no_candidate_slots.append(slot_key)
    return {
        "slot_rebind_diagnostic_count": len(diagnostics),
        "direct_accept_failed_count": len(direct_accept_failed_items),
        "direct_accept_recovered_by_persisted_name_count": len(recovered_by_persisted_name),
        "direct_accept_persisted_name_failed_count": len(persisted_name_failed),
        "direct_accept_rebind_details": details,
        "slot_rebind_summary_present": bool(summary),
        "slot_rebind_summary": summary,
        "slot_rebind_unbound_slots": sorted(unbound_slots),
        "slot_rebind_failure_reason_counts": slot_failure_reasons,
        "slot_rebind_no_view_record_slots": sorted(no_view_record_slots),
        "slot_rebind_no_candidate_slots": sorted(no_candidate_slots),
    }


def _post_layout_repair_summary(warnings: dict[str, Any]) -> dict[str, Any]:
    repair = warnings.get("post_layout_dim_repair") or {}
    explicit = repair.get("explicit_display_dims") or {}
    target_results = [item for item in explicit.get("target_results") or [] if isinstance(item, dict)]
    reason_counts: dict[str, int] = {}
    for item in target_results:
        reason = str(item.get("reason") or ("success" if item.get("success") else "unknown"))
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
    rebind_summary = _slot_rebind_diagnostics_summary(explicit)
    created_views_refresh = repair.get("created_views_refresh") or {}
    current_doc_refresh = repair.get("current_drawing_doc_refresh") or {}
    return {
        "attempted": bool(repair.get("attempted")),
        "before": _int_or_none(repair.get("before")),
        "after": _int_or_none(repair.get("after")),
        "explicit_attempted": bool(explicit.get("attempted")),
        "explicit_created": _int_or_none(explicit.get("created")),
        "live_view_recovery_failed": bool(explicit.get("live_view_recovery_failed")),
        "live_view_recovery_unbound_slots": list(explicit.get("unbound_slots") or []),
        "created_views_refresh": created_views_refresh,
        "current_drawing_doc_refresh": current_doc_refresh,
        "current_doc_view_count": _int_or_none(created_views_refresh.get("current_doc_view_count")),
        "getviews_count": _int_or_none(created_views_refresh.get("getviews_count")),
        "current_sheet_getviews_count": _int_or_none(created_views_refresh.get("current_sheet_getviews_count")),
        "target_result_count": len(target_results),
        "target_reason_counts": reason_counts,
        "slot_rebind_diagnostics_present": bool(explicit.get("slot_rebind_diagnostics")),
        "slot_view_sources_present": bool(explicit.get("slot_view_sources")),
        "final_acceptance_blockers": list(repair.get("final_acceptance_blockers") or []),
        **rebind_summary,
    }


def _post_prune_guard_summary(warnings: dict[str, Any]) -> dict[str, Any]:
    guard = warnings.get("post_prune_dim_guard") or {}
    explicit = guard.get("explicit_display_dims") or {}
    coverage_after = guard.get("target_coverage_after_guard") or {}
    return {
        "present": bool(guard),
        "attempted": bool(guard.get("attempted")),
        "before": _int_or_none(guard.get("before")),
        "after": _int_or_none(guard.get("after")),
        "repair_reason": str(guard.get("repair_reason") or ""),
        "explicit_created": _int_or_none(explicit.get("created")),
        "missing_target_keys_after_repair": list(guard.get("missing_target_keys_after_repair") or []),
        "target_coverage_after_guard_present": bool(coverage_after),
        "missing_target_keys_after_guard": list(guard.get("missing_target_keys_after_guard") or coverage_after.get("missing_target_keys") or []),
        "slot_rebind_diagnostics_present": bool(explicit.get("slot_rebind_diagnostics")),
        "slot_view_sources_present": bool(explicit.get("slot_view_sources")),
        "save_success": bool((guard.get("save") or {}).get("success")),
    }


def _prune_log_summary(warnings: dict[str, Any]) -> dict[str, Any]:
    prune_sources = [
        ("post_saveas_reopen_prune", _nested(warnings, "reference_dim_prune", "prune") or {}),
        (
            "post_layout_reference_prune",
            _nested(warnings, "post_layout_dim_repair", "post_layout_reference_prune", "prune") or {},
        ),
    ]
    required_fields = ["target_key", "slot", "reason"]
    stages: list[dict[str, Any]] = []
    detail_missing_stages: list[str] = []
    missing_field_items: list[dict[str, Any]] = []
    deleted_target_keys: list[str] = []
    for stage, prune in prune_sources:
        if not isinstance(prune, dict) or not prune:
            continue
        deleted = _int_or_none(prune.get("deleted")) or 0
        deleted_items = [item for item in prune.get("deleted_items") or [] if isinstance(item, dict)]
        delete_plan = [item for item in prune.get("delete_plan") or [] if isinstance(item, dict)]
        stage_info = {
            "stage": stage,
            "deleted": deleted,
            "delete_plan_count": len(delete_plan),
            "deleted_item_count": len(deleted_items),
            "deleted_items": deleted_items,
            "delete_plan": delete_plan,
            "detail_present": deleted <= 0 or bool(deleted_items),
            "required_fields": required_fields,
        }
        if deleted > 0 and not deleted_items:
            detail_missing_stages.append(stage)
        for index, item in enumerate(deleted_items):
            missing = [
                field
                for field in required_fields
                if str(item.get(field) or "").strip() == ""
            ]
            target_key = str(item.get("target_key") or "").strip()
            if target_key:
                deleted_target_keys.append(target_key)
            if missing:
                missing_field_items.append({
                    "stage": stage,
                    "index": index,
                    "missing_fields": missing,
                    "item": item,
                })
        stages.append(stage_info)
    return {
        "stages": stages,
        "deleted_total": sum(int(item.get("deleted") or 0) for item in stages),
        "detail_missing_stages": detail_missing_stages,
        "missing_required_field_items": missing_field_items,
        "deleted_target_keys": _unique(deleted_target_keys),
        "pass": not detail_missing_stages and not missing_field_items,
    }


def _strict_reference_intent_case(warnings: dict[str, Any]) -> bool:
    blueprint = warnings.get("drawing_blueprint_v4") or {}
    plan = blueprint.get("dimension_plan") or {}
    if not isinstance(plan, dict):
        return False
    reasons = {str(item) for item in plan.get("reasons") or []}
    if "explicit_dimension_targets_replace_generic_autodimension_acceptance" in reasons:
        return True
    targets = plan.get("dimension_targets") or []
    if targets and plan.get("allow_note_substitution") is False:
        return True
    return False


def _sidecar_policy_summary(warnings: dict[str, Any]) -> dict[str, Any]:
    strict = _strict_reference_intent_case(warnings)
    mode = warnings.get("dimension_sidecar_mode") or {}
    mode = mode if isinstance(mode, dict) else {}
    events = [
        item
        for item in warnings.get("warnings") or []
        if isinstance(item, dict) and "sidecar" in str(item.get("code") or "").lower()
    ]
    event_codes = [str(item.get("code") or "") for item in events]
    run_event_codes = [
        code
        for code in event_codes
        if code in {"dim_via_sidecar", "dim_sidecar_fail", "dim_sidecar_exc"}
    ]
    stale_path_events: list[dict[str, Any]] = []
    missing_path_events: list[dict[str, Any]] = []
    acceptance_disallowed_events: list[dict[str, Any]] = []
    for event in events:
        code = str(event.get("code") or "")
        if code not in {"dim_via_sidecar", "dim_sidecar_fail", "dim_sidecar_exc", "reference_intent_dimension_sidecar_diagnostic_only"}:
            continue
        drawing_path = str(event.get("drawing_path") or "")
        run_dir = str(event.get("run_dir") or "")
        if code in {
            "dim_via_sidecar",
            "dim_sidecar_fail",
            "dim_sidecar_exc",
            "reference_intent_dimension_sidecar_diagnostic_only",
        } and not drawing_path:
            missing_path_events.append(event)
        normalized = drawing_path.replace("/", "\\").lower()
        if "\\drw_output\\v5\\" in normalized:
            stale_path_events.append(event)
        if strict and event.get("acceptance_allowed") is True:
            acceptance_disallowed_events.append(event)
        if strict and drawing_path and run_dir:
            try:
                path_obj = Path(drawing_path).resolve()
                run_obj = Path(run_dir).resolve()
                if run_obj not in path_obj.parents and path_obj != run_obj:
                    stale_path_events.append(event)
            except Exception:
                pass
    return {
        "strict_reference_intent": strict,
        "mode_present": bool(mode),
        "mode": mode,
        "event_codes": event_codes,
        "run_event_codes": run_event_codes,
        "events": events,
        "diagnostic_only_event_present": "reference_intent_dimension_sidecar_diagnostic_only" in event_codes,
        "skipped_event_present": "reference_intent_dimension_sidecar_skipped" in event_codes,
        "stale_or_outside_run_dir_path_events": stale_path_events,
        "missing_drawing_path_events": missing_path_events,
        "acceptance_disallowed_events": acceptance_disallowed_events,
        "pass": not (
            (strict and not mode)
            or (strict and run_event_codes)
            or stale_path_events
            or missing_path_events
            or acceptance_disallowed_events
        ),
    }


def _blocking_keys(
    *,
    floor: int,
    stages: list[dict[str, Any]],
    losses: list[dict[str, Any]],
    coverage: dict[str, Any],
    post_layout: dict[str, Any],
    post_prune_guard: dict[str, Any],
    target_matrix: dict[str, Any],
    prune_log: dict[str, Any],
    sidecar_policy: dict[str, Any],
) -> list[str]:
    keys: list[str] = []
    final_counts = [
        stage.get("display_dim_count")
        for stage in stages
        if stage.get("stage") in {"post_layout_final", "dimension_validation_final", "pre_export_final"}
        and stage.get("display_dim_count") is not None
    ]
    final_count = final_counts[-1] if final_counts else None
    if final_count is None:
        keys.append("final_display_dim_count_missing")
    elif final_count < floor:
        keys.append("final_display_dim_below_reference_floor")
    if any(item.get("from_stage") == "post_saveas_reopen_prune_after" and item.get("to_stage") == "before_sidecar_diagnostic" for item in losses):
        keys.append("display_dim_lost_between_prune_and_sidecar")
    if any((item.get("to_count") or 0) < floor for item in losses):
        keys.append("display_dim_lifecycle_count_regression")
    if not coverage.get("post_layout_final_present"):
        keys.append("post_layout_final_target_coverage_missing")
    elif coverage.get("post_layout_final_missing_target_keys"):
        keys.append("post_layout_final_targets_missing")
    if not coverage.get("coverage_delta_present"):
        keys.append("target_coverage_delta_missing")
    if post_layout.get("attempted") and post_layout.get("explicit_created") == 0 and (post_layout.get("before") or 0) < floor:
        keys.append("post_layout_explicit_repair_created_zero")
    if int((post_layout.get("target_reason_counts") or {}).get("target_view_not_found") or 0) > 0:
        keys.append("post_layout_target_view_not_found")
    if post_layout.get("live_view_recovery_failed"):
        keys.append("post_layout_live_view_recovery_failed")
    if post_layout.get("attempted") and not post_layout.get("slot_rebind_diagnostics_present"):
        keys.append("post_layout_slot_rebind_diagnostics_missing")
    if post_layout.get("attempted") and not post_layout.get("slot_rebind_summary_present"):
        keys.append("post_layout_slot_rebind_summary_missing")
    if post_layout.get("slot_rebind_unbound_slots"):
        keys.append("post_layout_slot_rebind_unbound_slots")
    if post_layout.get("slot_rebind_no_view_record_slots"):
        keys.append("post_layout_slot_rebind_no_view_records")
    if post_layout.get("slot_rebind_no_candidate_slots"):
        keys.append("post_layout_slot_rebind_no_candidates")
    if (
        int(post_layout.get("direct_accept_persisted_name_failed_count") or 0) > 0
        and (post_layout.get("after") or 0) < floor
    ):
        keys.append("post_layout_direct_accept_rebind_unrecovered")
    if not post_prune_guard.get("present"):
        keys.append("post_prune_guard_missing")
    elif post_prune_guard.get("attempted"):
        if (post_prune_guard.get("after") or 0) < floor:
            keys.append("post_prune_guard_still_below_reference_floor")
        if post_prune_guard.get("missing_target_keys_after_repair") or post_prune_guard.get("missing_target_keys_after_guard"):
            keys.append("post_prune_guard_targets_still_missing")
        if not post_prune_guard.get("target_coverage_after_guard_present"):
            keys.append("post_prune_guard_target_coverage_missing")
        if not post_prune_guard.get("slot_rebind_diagnostics_present"):
            keys.append("post_prune_guard_slot_rebind_diagnostics_missing")
    if not target_matrix.get("target_count"):
        keys.append("target_stage_matrix_plan_missing")
    if target_matrix.get("missing_snapshot_stages"):
        keys.append("target_stage_matrix_snapshot_missing")
    if target_matrix.get("post_layout_final_missing_target_keys"):
        keys.append("target_stage_matrix_post_layout_final_missing")
    if target_matrix.get("target_trace_incomplete_keys"):
        keys.append("target_trace_missing_fields")
    if target_matrix.get("target_view_not_found_keys"):
        keys.append("target_stage_matrix_view_not_found")
    if prune_log.get("detail_missing_stages"):
        keys.append("prune_deleted_items_detail_missing")
    if prune_log.get("missing_required_field_items"):
        keys.append("prune_deleted_item_key_slot_reason_missing")
    if sidecar_policy.get("strict_reference_intent") and not sidecar_policy.get("mode_present"):
        keys.append("strict_reference_intent_sidecar_mode_missing")
    if sidecar_policy.get("strict_reference_intent") and sidecar_policy.get("run_event_codes"):
        keys.append("strict_reference_intent_sidecar_ran")
    if sidecar_policy.get("missing_drawing_path_events"):
        keys.append("sidecar_drawing_path_missing")
    if sidecar_policy.get("stale_or_outside_run_dir_path_events"):
        keys.append("sidecar_drawing_path_not_current_run")
    if sidecar_policy.get("acceptance_disallowed_events"):
        keys.append("sidecar_acceptance_allowed_for_strict_reference_intent")
    return _unique(keys)


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def build_lifecycle_audit(
    *,
    warnings_path: Path = DEFAULT_WARNINGS,
    cad_smoke_path: Path = DEFAULT_CAD_SMOKE,
    dimension_validation_path: Path = DEFAULT_DIMENSION_VALIDATION,
    reference_intent_plan_path: Path = DEFAULT_REFERENCE_INTENT_PLAN,
    out_json: Path | None = None,
    out_md: Path | None = None,
) -> dict[str, Any]:
    warnings = _read_json(warnings_path)
    cad_smoke = _read_json(cad_smoke_path)
    dimension_validation = _read_json(dimension_validation_path)
    floor = _display_floor(warnings, cad_smoke, dimension_validation)
    stages = _stage_counts(warnings, dimension_validation)
    losses = _loss_events(stages)
    coverage = _coverage_summary(warnings)
    post_layout = _post_layout_repair_summary(warnings)
    post_prune_guard = _post_prune_guard_summary(warnings)
    prune_log = _prune_log_summary(warnings)
    sidecar_policy = _sidecar_policy_summary(warnings)
    target_matrix = _target_stage_matrix(
        warnings,
        reference_intent_plan_path=reference_intent_plan_path,
    )
    blocking = _blocking_keys(
        floor=floor,
        stages=stages,
        losses=losses,
        coverage=coverage,
        post_layout=post_layout,
        post_prune_guard=post_prune_guard,
        target_matrix=target_matrix,
        prune_log=prune_log,
        sidecar_policy=sidecar_policy,
    )
    payload = {
        "schema": "sw_drawing_studio.lb26001_006_displaydim_lifecycle_audit.v4_2",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "base": BASE,
        "status": "pass" if not blocking else "fail",
        "pass": not blocking,
        "warnings_path": str(warnings_path),
        "cad_smoke_path": str(cad_smoke_path),
        "dimension_validation_path": str(dimension_validation_path),
        "reference_intent_plan_path": str(reference_intent_plan_path),
        "required_display_dim_floor": floor,
        "stage_counts": stages,
        "loss_events": losses,
        "coverage_summary": coverage,
        "prune_log_summary": prune_log,
        "sidecar_policy_summary": sidecar_policy,
        "post_prune_guard_summary": post_prune_guard,
        "post_layout_repair_summary": post_layout,
        "target_stage_matrix": target_matrix,
        "blocking_issue_keys": blocking,
        "api_is_not_final_judgement": True,
        "ui_screenshot_review_is_final_gate": True,
        "next_actions": _next_actions(blocking),
    }
    if out_json is not None:
        _write_json(out_json, payload)
    if out_md is not None:
        _write_text(out_md, render_markdown(payload))
    return payload


def _next_actions(blocking: list[str]) -> list[str]:
    actions: list[str] = []
    if "display_dim_lost_between_prune_and_sidecar" in blocking:
        actions.append("Inspect SaveAs/reopen/prune persistence before sidecar diagnostics; do not treat pre-prune DisplayDim count as final.")
    if "prune_deleted_items_detail_missing" in blocking or "prune_deleted_item_key_slot_reason_missing" in blocking:
        actions.append("Require every prune deletion log to include deleted_items with target_key, slot, and reason before accepting 006.")
    if "post_layout_target_view_not_found" in blocking or "post_layout_slot_rebind_diagnostics_missing" in blocking:
        actions.append("Use the hardened post-layout slot rebinding path and require slot_rebind_diagnostics in the next CAD run.")
    if "post_layout_slot_rebind_summary_missing" in blocking or "post_layout_slot_rebind_unbound_slots" in blocking:
        actions.append("Require slot_rebind_summary with bound/unbound slots, nearest candidates, and failure reasons for the next post-layout repair attempt.")
    if "post_layout_slot_rebind_no_view_records" in blocking or "post_layout_slot_rebind_no_candidates" in blocking:
        actions.append("Inspect current drawing view enumeration and persisted real_outlines because slot rebinding has no usable view candidates for one or more required slots.")
    if "post_layout_direct_accept_rebind_unrecovered" in blocking:
        actions.append("Inspect post-layout direct IView accept fallback; persisted-name rebinding failed while DisplayDim stayed below floor.")
    if "post_prune_guard_missing" in blocking or "post_prune_guard_still_below_reference_floor" in blocking:
        actions.append("Run the post-saveas/reopen/prune guard before sidecar diagnostics and require it to restore the DisplayDim floor.")
    if "strict_reference_intent_sidecar_ran" in blocking or "strict_reference_intent_sidecar_mode_missing" in blocking:
        actions.append("Keep sidecar diagnostic-only for strict 006 and require dimension_sidecar_mode before accepting any sidecar evidence.")
    if "sidecar_drawing_path_missing" in blocking or "sidecar_drawing_path_not_current_run" in blocking:
        actions.append("When sidecar diagnostics run, log drawing_path/run_dir and require the drawing path to stay under the fresh run_dir, never drw_output/v5.")
    if "post_layout_final_target_coverage_missing" in blocking:
        actions.append("Require a post_layout_final target coverage snapshot before accepting 006.")
    if "target_trace_missing_fields" in blocking or "target_stage_matrix_snapshot_missing" in blocking:
        actions.append("Refresh the next 006 CAD run with per-target trace fields: target_key, view_slot, selected_entity, add_method, before/after counts, coverage, and persisted_after_reopen.")
    if "target_stage_matrix_post_layout_final_missing" in blocking or "target_stage_matrix_view_not_found" in blocking:
        actions.append("Use the target_stage_matrix rows to repair the exact reference-intent targets lost before post_layout_final.")
    actions.append("After SolidWorks readiness clears, rerun only LB26001-A-04-006 through the locked CAD path and refresh this lifecycle audit.")
    return _unique(actions)


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# LB26001-A-04-006 DisplayDim Lifecycle Audit",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- PASS: `{str(payload.get('pass')).lower()}`",
        f"- Required DisplayDim floor: `{payload.get('required_display_dim_floor')}`",
        "",
        "## Stage Counts",
        "",
        "| Stage | Count | Source |",
        "| --- | ---: | --- |",
    ]
    for item in payload.get("stage_counts") or []:
        lines.append(f"| `{item.get('stage')}` | `{item.get('display_dim_count')}` | `{item.get('source')}` |")
    lines.extend(["", "## Loss Events", ""])
    losses = payload.get("loss_events") or []
    if losses:
        for item in losses:
            lines.append(
                f"- `{item.get('from_stage')}` -> `{item.get('to_stage')}`: "
                f"{item.get('from_count')} -> {item.get('to_count')} (lost {item.get('lost_count')})"
            )
    else:
        lines.append("- None")
    prune = payload.get("prune_log_summary") or {}
    lines.extend(
        [
            "",
            "## Prune Deletion Log",
            "",
            f"- Deleted total: `{prune.get('deleted_total')}`",
            f"- Detail missing stages: `{', '.join(prune.get('detail_missing_stages') or []) or 'none'}`",
            f"- Missing key/slot/reason items: `{len(prune.get('missing_required_field_items') or [])}`",
            f"- Deleted target keys: `{', '.join(prune.get('deleted_target_keys') or []) or 'none'}`",
        ]
    )
    sidecar = payload.get("sidecar_policy_summary") or {}
    lines.extend(
        [
            "",
            "## Sidecar Policy",
            "",
            f"- Strict reference-intent: `{str(sidecar.get('strict_reference_intent')).lower()}`",
            f"- Mode present: `{str(sidecar.get('mode_present')).lower()}`",
            f"- Run event codes: `{', '.join(sidecar.get('run_event_codes') or []) or 'none'}`",
            f"- Missing drawing_path events: `{len(sidecar.get('missing_drawing_path_events') or [])}`",
            f"- Stale/outside run_dir path events: `{len(sidecar.get('stale_or_outside_run_dir_path_events') or [])}`",
            f"- Acceptance-disallowed events: `{len(sidecar.get('acceptance_disallowed_events') or [])}`",
            f"- PASS: `{str(sidecar.get('pass')).lower()}`",
        ]
    )
    rebind = payload.get("post_layout_repair_summary") or {}
    lines.extend(
        [
            "",
            "## Post-Layout Slot Rebind",
            "",
            f"- Live view recovery failed: `{str(rebind.get('live_view_recovery_failed')).lower()}`",
            f"- Current doc view count: `{rebind.get('current_doc_view_count')}`",
            f"- DrawingDoc.GetViews count: `{rebind.get('getviews_count')}`",
            f"- CurrentSheet.GetViews count: `{rebind.get('current_sheet_getviews_count')}`",
            f"- Diagnostic count: `{rebind.get('slot_rebind_diagnostic_count')}`",
            f"- Summary present: `{str(rebind.get('slot_rebind_summary_present')).lower()}`",
            f"- Unbound slots: `{', '.join(rebind.get('slot_rebind_unbound_slots') or []) or 'none'}`",
            f"- Failure reasons: `{rebind.get('slot_rebind_failure_reason_counts') or {}}`",
            f"- Direct accept failed: `{rebind.get('direct_accept_failed_count')}`",
            f"- Recovered by persisted name: `{rebind.get('direct_accept_recovered_by_persisted_name_count')}`",
            f"- Persisted-name recovery failed: `{rebind.get('direct_accept_persisted_name_failed_count')}`",
        ]
    )
    matrix = payload.get("target_stage_matrix") or {}
    lines.extend(
        [
            "",
            "## Target Stage Matrix",
            "",
            f"- Target count: `{matrix.get('target_count')}`",
            f"- PASS: `{str(matrix.get('pass')).lower()}`",
            f"- Missing snapshot stages: `{', '.join(matrix.get('missing_snapshot_stages') or []) or 'none'}`",
            f"- Missing post-layout targets: `{', '.join(matrix.get('post_layout_final_missing_target_keys') or []) or 'none'}`",
            f"- Incomplete target traces: `{', '.join(matrix.get('target_trace_incomplete_keys') or []) or 'none'}`",
            "",
            "| Target | View | Method | Lost stage | Post-layout reason | Trace complete |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in matrix.get("rows") or []:
        attempt = row.get("post_layout_attempt") or {}
        trace = row.get("trace") or {}
        lines.append(
            f"| `{row.get('target_key')}` | `{row.get('view_slot')}` | "
            f"`{row.get('expected_add_method')}` | `{row.get('lost_stage') or 'none'}` | "
            f"`{attempt.get('reason') or 'none'}` | `{str(trace.get('target_trace_complete')).lower()}` |"
        )
    lines.extend(["", "## Blocking Issues", ""])
    blocking = payload.get("blocking_issue_keys") or []
    if blocking:
        lines.extend(f"- `{key}`" for key in blocking)
    else:
        lines.append("- None")
    lines.extend(["", "## Next Actions", ""])
    lines.extend(f"- {item}" for item in payload.get("next_actions") or [])
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit LB26001-A-04-006 DisplayDim lifecycle from existing artifacts.")
    parser.add_argument("--warnings", default=str(DEFAULT_WARNINGS))
    parser.add_argument("--cad-smoke", default=str(DEFAULT_CAD_SMOKE))
    parser.add_argument("--dimension-validation", default=str(DEFAULT_DIMENSION_VALIDATION))
    parser.add_argument("--reference-intent-plan", default=str(DEFAULT_REFERENCE_INTENT_PLAN))
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    parser.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    args = parser.parse_args()

    payload = build_lifecycle_audit(
        warnings_path=_repo_path(args.warnings),
        cad_smoke_path=_repo_path(args.cad_smoke),
        dimension_validation_path=_repo_path(args.dimension_validation),
        reference_intent_plan_path=_repo_path(args.reference_intent_plan),
        out_json=_repo_path(args.out_json),
        out_md=_repo_path(args.out_md),
    )
    print(json.dumps({
        "pass": payload.get("pass"),
        "status": payload.get("status"),
        "blocking_issue_keys": payload.get("blocking_issue_keys"),
        "report": str(_repo_path(args.out_json)),
    }, ensure_ascii=False))
    return 0 if payload.get("pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
