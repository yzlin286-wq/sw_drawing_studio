from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any


SCHEMA = "sw_drawing_studio.reference_intent_dimension_execution_contract.v4_4"


def build_execution_contract(
    plan: dict[str, Any],
    *,
    drawing_path: Path | str | None = None,
    run_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Convert a reference-intent plan into a CAD-worker contract without calling COM."""
    operations = []
    for index, item in enumerate(plan.get("dimensions") or [], start=1):
        operations.append({
            "index": index,
            "operation": "create_or_verify_display_dimension",
            "dimension_key": item.get("key", ""),
            "group": item.get("group", ""),
            "functional_role": item.get("functional_role", ""),
            "reading_group": item.get("reading_group", ""),
            "readability_group": item.get("readability_group", ""),
            "manufacturing_story_role": item.get("manufacturing_story_role", ""),
            "target_view": item.get("target_view", ""),
            "expected_type": item.get("expected_type", ""),
            "expected_add_method": item.get("expected_add_method", ""),
            "preferred_side": item.get("preferred_side", ""),
            "placement_lane": dict(item.get("placement_lane") or {}),
            "allowed_witness_entity": dict(item.get("allowed_witness_entity") or {}),
            "prune_protection_policy": dict(item.get("prune_protection_policy") or {}),
            "source_reference": item.get("source_reference", ""),
            "is_manufacturing_dimension": bool(item.get("is_manufacturing_dimension")),
            "reference_value": item.get("reference_value"),
            "reference_value_unit": item.get("reference_value_unit", ""),
            "reference_value_status": item.get("reference_value_status", ""),
            "source_reference_evidence": dict(item.get("source_reference_evidence") or {}),
            "create_as": item.get("create_as", "SolidWorks DisplayDim"),
            "fallback_policy": item.get("fallback_policy", "need_review_when_real_displaydim_unavailable"),
            "forbid_note_substitution": True,
            "avoid_generic_model_annotation": item.get("avoid_generic_model_annotation", True),
            "generic_autodimension_acceptance_allowed": item.get("generic_autodimension_acceptance_allowed", False),
            "trace_required_fields": list(item.get("trace_required_fields") or []),
            "acceptance_trace": dict(item.get("acceptance_trace") or {}),
            "requires_solidworks_lock": True,
            "allowed_entrypoint": "cad_job_worker",
            "status": "queued_requires_worker_lock",
        })

    return {
        "schema": SCHEMA,
        "version": "v4.4",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "base": plan.get("base", ""),
        "drawing_path": str(drawing_path or ""),
        "run_dir": str(run_dir or ""),
        "source_plan_status": plan.get("status", ""),
        "requires_solidworks_lock": True,
        "ui_thread_may_execute": False,
        "allowed_entrypoint": "cad_job_worker",
        "direct_com_called": False,
        "acceptance_trace_requirements": plan.get("acceptance_trace_requirements") or {},
        "reference_extraction": plan.get("reference_extraction") or {},
        "reference_callouts": plan.get("reference_callouts") or [],
        "reference_layout_policy": plan.get("reference_layout_policy") or {},
        "view_plan": plan.get("view_plan") or [],
        "layout_plan": plan.get("layout_plan") or {},
        "ui_defect_repair_layout_targets": plan.get("ui_defect_repair_layout_targets") or {},
        "reference_dimension_lane_policy": plan.get("reference_dimension_lane_policy") or {},
        "operations": operations,
        "operation_count": len(operations),
        "status": "contract_ready_requires_cad_worker_lock",
        "failure_status_without_lock": "blocked_by_solidworks_lock",
    }


def write_execution_contract(contract: dict[str, Any], path: Path | str) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


__all__ = ["build_execution_contract", "write_execution_contract"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a CAD-worker execution contract from a reference-intent dimension plan.")
    parser.add_argument("--plan", required=True)
    parser.add_argument("--drawing", default="")
    parser.add_argument("--run-dir", default="")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    plan = json.loads(Path(args.plan).read_text(encoding="utf-8-sig"))
    contract = build_execution_contract(
        plan,
        drawing_path=args.drawing or None,
        run_dir=args.run_dir or None,
    )
    out = write_execution_contract(contract, args.out)
    print(json.dumps({"status": contract["status"], "operation_count": contract["operation_count"], "out": str(out)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
