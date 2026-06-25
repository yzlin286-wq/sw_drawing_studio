from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
BASE = "LB26001-A-04-006"
PLAN_SCHEMA = "sw_drawing_studio.reference_intent_dimension_plan.v4_4"
CONTRACT_SCHEMA = "sw_drawing_studio.reference_intent_dimension_execution_contract.v4_4"
PROOF_SCHEMA = "sw_drawing_studio.lb26001_006_reference_intent_proof.v4_4"
DEFAULT_PLAN = REPO_ROOT / "drw_output" / "reference_intent_dimension_plan_006.json"
DEFAULT_CONTRACT = REPO_ROOT / "drw_output" / "reference_intent_dimension_contract_006.json"
DEFAULT_OUT_JSON = REPO_ROOT / "drw_output" / "diagnostics" / "lb26001_006_reference_intent_proof_v4_4.json"
DEFAULT_OUT_MD = REPO_ROOT / "drw_output" / "diagnostics" / "lb26001_006_reference_intent_proof_v4_4.md"

REQUIRED_DIMENSION_FIELDS = {
    "source_reference",
    "target_view",
    "expected_type",
    "is_manufacturing_dimension",
    "fallback_policy",
    "source_reference_evidence",
    "reference_value",
    "expected_add_method",
    "create_as",
    "forbid_note_substitution",
    "generic_autodimension_acceptance_allowed",
}

REQUIRED_DIMENSION_KEYS = {
    "overall_length",
    "overall_width",
    "overall_height",
    "left_end_offset",
    "right_end_offset",
    "hole_diameter",
    "hole_x_location",
    "hole_y_location",
    "hole_pitch",
    "projection_view_width",
    "projection_view_height",
    "small_feature_location",
}

EXPECTED_VALUES: dict[str, Any] = {
    "overall_length": 230,
    "overall_width": 12,
    "overall_height": 13,
    "left_end_offset": 10,
    "right_end_offset": 10,
    "hole_x_location": [10, 80, 150, 220],
    "hole_y_location": 6,
    "hole_pitch": [70, 70, 70],
    "projection_view_width": 12,
    "projection_view_height": 13,
    "small_feature_location": 6,
}

EXPECTED_VIEWS = {
    "overall_length": "front",
    "overall_width": "top",
    "overall_height": "right",
    "left_end_offset": "top",
    "right_end_offset": "top",
    "hole_diameter": "top",
    "hole_x_location": "top",
    "hole_y_location": "top",
    "hole_pitch": "top",
    "projection_view_width": "right",
    "projection_view_height": "right",
    "small_feature_location": "right",
}

EXPECTED_TYPES = {
    "overall_length": "linear_horizontal",
    "overall_width": "linear_vertical",
    "overall_height": "linear_vertical",
    "left_end_offset": "linear_horizontal",
    "right_end_offset": "linear_horizontal",
    "hole_diameter": "diameter",
    "hole_x_location": "linear_horizontal",
    "hole_y_location": "linear_vertical",
    "hole_pitch": "linear_horizontal",
    "projection_view_width": "linear_horizontal",
    "projection_view_height": "linear_vertical",
    "small_feature_location": "linear_vertical",
}


def build_reference_intent_proof(
    *,
    plan_path: Path = DEFAULT_PLAN,
    contract_path: Path = DEFAULT_CONTRACT,
    out_json: Path | None = None,
    out_md: Path | None = None,
) -> dict[str, Any]:
    plan = _read_json(plan_path)
    contract = _read_json(contract_path)
    checks: list[dict[str, Any]] = []

    _check_plan_identity(checks, plan_path, plan)
    _check_dimension_contract(checks, plan)
    _check_dimension_values(checks, plan)
    _check_reference_callouts(checks, plan)
    _check_policy(checks, plan)
    _check_execution_contract(checks, contract_path, contract, plan)

    failed = [item for item in checks if item["status"] != "pass"]
    payload = {
        "schema": PROOF_SCHEMA,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "base": BASE,
        "status": "plan_proof_pass_requires_locked_cad_run" if not failed else "fail",
        "pass": not failed,
        "release_ready": False,
        "report_is_drawing_acceptance_evidence": False,
        "api_only_acceptance_allowed": False,
        "ui_screenshot_acceptance_required": True,
        "notes_count_as_displaydim": False,
        "solidworks_com_called": False,
        "source_files": {
            "plan": str(plan_path),
            "contract": str(contract_path),
            "source_reference": str(plan.get("source_reference") or ""),
            "reference_png": str((plan.get("reference_extraction") or {}).get("reference_png") or ""),
        },
        "dimension_summary": _dimension_summary(plan),
        "callout_summary": _callout_summary(plan),
        "checks": checks,
        "blocking_issue_keys": [item["key"] for item in failed],
        "next_required_action": (
            "Run exactly one locked 006 CAD worker via JobRuntimeFacade, then judge the result in the application "
            "Drawing Review UI screenshot workflow."
        ),
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
        f"# {payload.get('base')} Reference Intent Proof v4.4",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- PASS: `{str(payload.get('pass')).lower()}`",
        "- Release ready: `false`",
        "- Drawing acceptance evidence: `false`",
        "- API-only acceptance allowed: `false`",
        "- UI screenshot acceptance required: `true`",
        "",
        "## Coverage",
        "",
    ]
    dims = payload.get("dimension_summary") or {}
    callouts = payload.get("callout_summary") or {}
    lines.extend(
        [
            f"- DisplayDim target count: `{dims.get('count')}`",
            f"- Required target keys present: `{str(dims.get('required_keys_present')).lower()}`",
            f"- Right projected view target keys: `{', '.join(dims.get('right_projected_view_keys') or [])}`",
            f"- Required callouts present: `{str(callouts.get('required_callouts_present')).lower()}`",
            f"- Absence-checked callouts: `{', '.join(callouts.get('absence_checked_callouts') or [])}`",
            "",
            "## Checks",
            "",
        ]
    )
    for item in payload.get("checks") or []:
        lines.append(f"- `{item.get('status')}` `{item.get('key')}`: {item.get('message')}")
    lines.extend(["", "## Blocking Issues", ""])
    keys = payload.get("blocking_issue_keys") or []
    lines.extend([f"- `{key}`" for key in keys] or ["- None"])
    lines.append("")
    return "\n".join(lines)


def _read_json(path: Path) -> dict[str, Any]:
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
        "status": "pass" if passed else "fail",
        "message": message,
        "details": details or {},
    })


def _check_plan_identity(checks: list[dict[str, Any]], plan_path: Path, plan: dict[str, Any]) -> None:
    source_reference = Path(str(plan.get("source_reference") or ""))
    reference_png = Path(str((plan.get("reference_extraction") or {}).get("reference_png") or ""))
    _add_check(checks, "plan_file_exists", plan_path.exists(), "reference intent plan artifact exists")
    _add_check(checks, "plan_schema", plan.get("schema") == PLAN_SCHEMA, "reference intent plan schema is v4.4")
    _add_check(checks, "plan_base", plan.get("base") == BASE, "reference intent plan is for LB26001-A-04-006")
    _add_check(
        checks,
        "source_reference_exists",
        source_reference.exists() and source_reference.suffix.lower() == ".slddrw",
        "same-name source reference SLDDRW exists",
        {"source_reference": str(source_reference)},
    )
    _add_check(
        checks,
        "reference_png_exists",
        reference_png.exists() and reference_png.stat().st_size > 0 if reference_png.exists() else False,
        "reference PNG used for visual value reading exists",
        {"reference_png": str(reference_png)},
    )


def _check_dimension_contract(checks: list[dict[str, Any]], plan: dict[str, Any]) -> None:
    dims = _dimensions_by_key(plan)
    missing_keys = sorted(REQUIRED_DIMENSION_KEYS - set(dims))
    extra_keys = sorted(set(dims) - REQUIRED_DIMENSION_KEYS)
    _add_check(
        checks,
        "required_dimension_keys",
        not missing_keys and not extra_keys,
        "006 has exactly the required 12 reference-intent DisplayDim targets",
        {"missing": missing_keys, "extra": extra_keys, "keys": sorted(dims)},
    )
    field_failures: dict[str, list[str]] = {}
    policy_failures: list[str] = []
    for key, item in dims.items():
        missing_fields = [field for field in REQUIRED_DIMENSION_FIELDS if field not in item or item.get(field) in ("", None)]
        if missing_fields:
            field_failures[key] = sorted(missing_fields)
        if item.get("is_manufacturing_dimension") is not True:
            policy_failures.append(f"{key}:is_manufacturing_dimension")
        if item.get("create_as") != "SolidWorks DisplayDim":
            policy_failures.append(f"{key}:create_as")
        if item.get("forbid_note_substitution") is not True:
            policy_failures.append(f"{key}:forbid_note_substitution")
        if item.get("generic_autodimension_acceptance_allowed") is not False:
            policy_failures.append(f"{key}:generic_autodimension_acceptance_allowed")
        if str(item.get("fallback_policy") or "") != "need_review_when_real_displaydim_unavailable":
            policy_failures.append(f"{key}:fallback_policy")
    _add_check(
        checks,
        "required_dimension_fields",
        not field_failures,
        "every DisplayDim target has source_reference, target_view, expected_type, manufacturing flag, fallback policy, and evidence",
        {"failures": field_failures},
    )
    _add_check(
        checks,
        "displaydim_not_note_policy",
        not policy_failures,
        "all 12 manufacturing targets must be real SolidWorks DisplayDim, not Note or generic AutoDimension acceptance",
        {"failures": policy_failures},
    )


def _check_dimension_values(checks: list[dict[str, Any]], plan: dict[str, Any]) -> None:
    dims = _dimensions_by_key(plan)
    value_failures: list[str] = []
    view_failures: list[str] = []
    type_failures: list[str] = []
    for key, expected in EXPECTED_VALUES.items():
        if dims.get(key, {}).get("reference_value") != expected:
            value_failures.append(key)
    hole = dims.get("hole_diameter", {}).get("reference_value") or {}
    if not (
        isinstance(hole, dict)
        and hole.get("hole_count") == 4
        and float(hole.get("diameter_mm") or 0) == 3.3
        and hole.get("thread") == "M4-6H"
        and hole.get("through") is True
    ):
        value_failures.append("hole_diameter")
    for key, expected in EXPECTED_VIEWS.items():
        if dims.get(key, {}).get("target_view") != expected:
            view_failures.append(key)
    for key, expected in EXPECTED_TYPES.items():
        if dims.get(key, {}).get("expected_type") != expected:
            type_failures.append(key)
    right_keys = ["projection_view_width", "projection_view_height", "small_feature_location"]
    _add_check(
        checks,
        "reference_values",
        not value_failures,
        "visual reference values cover total length/width/height, end offsets, hole stations, pitch, and right projection",
        {"failures": value_failures},
    )
    _add_check(
        checks,
        "target_views",
        not view_failures,
        "reference-intent targets are assigned to the correct front/top/right view",
        {"failures": view_failures},
    )
    _add_check(
        checks,
        "expected_dimension_types",
        not type_failures,
        "reference-intent targets use expected linear/diameter types",
        {"failures": type_failures},
    )
    _add_check(
        checks,
        "right_projected_view_dimensions",
        all(key in dims and dims[key].get("target_view") == "right" for key in right_keys),
        "right-side small projected view has width, height, and small-feature location targets",
        {"keys": right_keys},
    )


def _check_reference_callouts(checks: list[dict[str, Any]], plan: dict[str, Any]) -> None:
    callouts = _callouts_by_key(plan)
    required = {"thread_callout_m4_6h", "surface_finish_rest_3_2", "radius_callout", "chamfer_callout"}
    _add_check(
        checks,
        "reference_callout_keys",
        required <= set(callouts),
        "reference callouts cover M4-6H, surface finish, and radius/chamfer absence checks",
        {"missing": sorted(required - set(callouts)), "keys": sorted(callouts)},
    )
    thread = callouts.get("thread_callout_m4_6h") or {}
    surface = callouts.get("surface_finish_rest_3_2") or {}
    radius = callouts.get("radius_callout") or {}
    chamfer = callouts.get("chamfer_callout") or {}
    _add_check(
        checks,
        "thread_callout_policy",
        thread.get("is_manufacturing_dimension") is True
        and thread.get("expected_type") == "thread_callout"
        and thread.get("reference_value") == "M4-6H 完全贯穿"
        and thread.get("forbid_note_substitution_for_displaydim") is True
        and "DisplayDim" not in str(thread.get("create_as") or "").split(",")[0],
        "M4-6H callout is required visual manufacturing evidence and cannot replace DisplayDim",
        {"callout": thread},
    )
    _add_check(
        checks,
        "surface_finish_policy",
        surface.get("is_manufacturing_dimension") is True
        and surface.get("expected_type") == "surface_finish_callout"
        and surface.get("reference_value") == "3.2 其余"
        and "does not count as DisplayDim" in str(surface.get("create_as") or ""),
        "3.2 rest surface-finish note is required callout evidence but does not count as DisplayDim",
        {"callout": surface},
    )
    absence_ok = all(
        item.get("is_manufacturing_dimension") is False
        and item.get("reference_value") is None
        and str(item.get("fallback_policy") or "").startswith("do_not_create_unless")
        for item in [radius, chamfer]
    )
    _add_check(
        checks,
        "radius_chamfer_absence_policy",
        absence_ok,
        "radius/chamfer are recorded as visually absent and must not be fabricated",
        {"radius": radius, "chamfer": chamfer},
    )


def _check_policy(checks: list[dict[str, Any]], plan: dict[str, Any]) -> None:
    _add_check(
        checks,
        "api_and_ui_policy",
        plan.get("allow_note_substitution") is False
        and plan.get("api_is_supporting_only") is True
        and plan.get("ui_screenshot_acceptance_required") is True,
        "plan requires UI screenshot acceptance and forbids Note substitution",
        {
            "allow_note_substitution": plan.get("allow_note_substitution"),
            "api_is_supporting_only": plan.get("api_is_supporting_only"),
            "ui_screenshot_acceptance_required": plan.get("ui_screenshot_acceptance_required"),
        },
    )
    trace = plan.get("acceptance_trace_requirements") or {}
    required_fields = set(trace.get("required_fields") or [])
    trace_ok = {
        "target_key",
        "view_slot",
        "selected_entity",
        "add_method",
        "display_dim_count_before",
        "display_dim_count_after",
        "target_covered_after_attempt",
        "persisted_after_reopen",
    } <= required_fields and trace.get("final_stage_required") == "post_layout_final"
    _add_check(
        checks,
        "acceptance_trace_requirements",
        trace_ok,
        "plan requires selected entity, add method, before/after counts, target coverage, and post-layout persistence trace",
        trace,
    )


def _check_execution_contract(
    checks: list[dict[str, Any]],
    contract_path: Path,
    contract: dict[str, Any],
    plan: dict[str, Any],
) -> None:
    operations = contract.get("operations") or []
    operation_keys = {str(item.get("dimension_key") or "") for item in operations if isinstance(item, dict)}
    _add_check(checks, "contract_file_exists", contract_path.exists(), "reference-intent execution contract exists")
    _add_check(checks, "contract_schema", contract.get("schema") == CONTRACT_SCHEMA, "execution contract schema is v4.4")
    _add_check(checks, "contract_base", contract.get("base") == BASE, "execution contract is for LB26001-A-04-006")
    _add_check(
        checks,
        "contract_lock_policy",
        contract.get("requires_solidworks_lock") is True
        and contract.get("ui_thread_may_execute") is False
        and contract.get("allowed_entrypoint") == "cad_job_worker"
        and contract.get("direct_com_called") is False,
        "execution contract can only run through the CAD worker while holding the SolidWorks global lock",
        {
            "requires_solidworks_lock": contract.get("requires_solidworks_lock"),
            "ui_thread_may_execute": contract.get("ui_thread_may_execute"),
            "allowed_entrypoint": contract.get("allowed_entrypoint"),
            "direct_com_called": contract.get("direct_com_called"),
        },
    )
    _add_check(
        checks,
        "contract_operations",
        int(contract.get("operation_count") or 0) == len(REQUIRED_DIMENSION_KEYS)
        and operation_keys == REQUIRED_DIMENSION_KEYS
        and operation_keys == set(_dimensions_by_key(plan)),
        "execution contract has one locked worker operation for each required DisplayDim target",
        {
            "operation_count": contract.get("operation_count"),
            "operation_keys": sorted(operation_keys),
        },
    )
    op_failures: list[str] = []
    for item in operations:
        key = str(item.get("dimension_key") or "")
        if item.get("requires_solidworks_lock") is not True:
            op_failures.append(f"{key}:requires_solidworks_lock")
        if item.get("allowed_entrypoint") != "cad_job_worker":
            op_failures.append(f"{key}:allowed_entrypoint")
        if item.get("forbid_note_substitution") is not True:
            op_failures.append(f"{key}:forbid_note_substitution")
        if item.get("generic_autodimension_acceptance_allowed") is not False:
            op_failures.append(f"{key}:generic_autodimension_acceptance_allowed")
        if not item.get("source_reference") or not item.get("target_view") or not item.get("expected_type"):
            op_failures.append(f"{key}:required_fields")
    _add_check(
        checks,
        "contract_operation_policy",
        not op_failures,
        "each contract operation keeps lock, entrypoint, no-Note, and no-generic-AutoDimension acceptance policy",
        {"failures": op_failures},
    )


def _dimensions_by_key(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("key") or ""): item
        for item in plan.get("dimensions") or []
        if isinstance(item, dict) and str(item.get("key") or "")
    }


def _callouts_by_key(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("key") or ""): item
        for item in plan.get("reference_callouts") or []
        if isinstance(item, dict) and str(item.get("key") or "")
    }


def _dimension_summary(plan: dict[str, Any]) -> dict[str, Any]:
    dims = _dimensions_by_key(plan)
    return {
        "count": len(dims),
        "keys": sorted(dims),
        "required_keys_present": REQUIRED_DIMENSION_KEYS <= set(dims),
        "right_projected_view_keys": [
            key for key in ["projection_view_width", "projection_view_height", "small_feature_location"]
            if key in dims and dims[key].get("target_view") == "right"
        ],
    }


def _callout_summary(plan: dict[str, Any]) -> dict[str, Any]:
    callouts = _callouts_by_key(plan)
    return {
        "count": len(callouts),
        "keys": sorted(callouts),
        "required_callouts_present": {"thread_callout_m4_6h", "surface_finish_rest_3_2"} <= set(callouts),
        "absence_checked_callouts": [
            key for key in ["radius_callout", "chamfer_callout"]
            if key in callouts and callouts[key].get("reference_value") is None
        ],
    }


def _repo_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


def main() -> int:
    parser = argparse.ArgumentParser(description="Build offline proof for the 006 reference-intent dimension plan.")
    parser.add_argument("--plan", default=str(DEFAULT_PLAN))
    parser.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    parser.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    args = parser.parse_args()

    payload = build_reference_intent_proof(
        plan_path=_repo_path(args.plan),
        contract_path=_repo_path(args.contract),
        out_json=_repo_path(args.out_json),
        out_md=_repo_path(args.out_md),
    )
    print(json.dumps({
        "status": payload.get("status"),
        "pass": payload.get("pass"),
        "blocking_issue_keys": payload.get("blocking_issue_keys"),
        "out_json": str(_repo_path(args.out_json)),
        "out_md": str(_repo_path(args.out_md)),
    }, ensure_ascii=False))
    return 0 if payload.get("pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
