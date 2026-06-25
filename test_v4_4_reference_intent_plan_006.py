from __future__ import annotations

import json
from pathlib import Path

from app.services.reference_intent_dimension_executor import build_execution_contract
from app.services.reference_intent_dimension_planner import (
    build_reference_intent_dimension_plan,
    load_reference_profile,
)


REQUIRED_DIM_FIELDS = {
    "source_reference",
    "target_view",
    "expected_type",
    "is_manufacturing_dimension",
    "fallback_policy",
    "source_reference_evidence",
    "reference_value",
    "reference_value_status",
}

REQUIRED_CALLOUT_FIELDS = {
    "source_reference",
    "target_view",
    "expected_type",
    "is_manufacturing_dimension",
    "fallback_policy",
    "source_reference_evidence",
    "reference_value",
}


def main() -> None:
    base = "LB26001-A-04-006"
    profile = load_reference_profile(base)
    plan = build_reference_intent_dimension_plan(base, reference_profile=profile)

    assert plan["schema"] == "sw_drawing_studio.reference_intent_dimension_plan.v4_4"
    assert plan["allow_note_substitution"] is False
    assert plan["ui_screenshot_acceptance_required"] is True
    assert plan["reference_extraction"]["status"] == "visual_reference_png_values_recorded"

    dims = plan.get("dimensions") or []
    assert len(dims) == 12
    for item in dims:
        missing = sorted(field for field in REQUIRED_DIM_FIELDS if field not in item)
        assert not missing, (item.get("key"), missing)
        assert item["is_manufacturing_dimension"] is True
        assert item["create_as"] == "SolidWorks DisplayDim"
        assert item["forbid_note_substitution"] is True
        assert item["generic_autodimension_acceptance_allowed"] is False

    by_key = {item["key"]: item for item in dims}
    assert by_key["overall_length"]["reference_value"] == 230
    assert by_key["overall_width"]["reference_value"] == 12
    assert by_key["overall_height"]["reference_value"] == 13
    assert by_key["left_end_offset"]["reference_value"] == 10
    assert by_key["right_end_offset"]["reference_value"] == 10
    assert by_key["hole_y_location"]["reference_value"] == 6
    assert by_key["hole_pitch"]["reference_value"] == [70, 70, 70]
    assert by_key["hole_diameter"]["reference_value"]["diameter_mm"] == 3.3
    assert by_key["hole_diameter"]["reference_value"]["thread"] == "M4-6H"

    callouts = {item["key"]: item for item in plan.get("reference_callouts") or []}
    for item in callouts.values():
        missing = sorted(field for field in REQUIRED_CALLOUT_FIELDS if field not in item)
        assert not missing, (item.get("key"), missing)
        assert item["source_reference_evidence"]

    assert callouts["thread_callout_m4_6h"]["reference_value"] == "M4-6H 完全贯穿"
    assert callouts["surface_finish_rest_3_2"]["reference_value"] == "3.2 其余"
    assert callouts["radius_callout"]["reference_value"] is None
    assert callouts["chamfer_callout"]["reference_value"] is None

    contract = build_execution_contract(
        plan,
        drawing_path=Path("drw_output/runs/<fresh_run_dir>/drawing/LB26001-A-04-006_v5.SLDDRW"),
        run_dir=Path("drw_output/runs/<fresh_run_dir>"),
    )
    assert contract["schema"] == "sw_drawing_studio.reference_intent_dimension_execution_contract.v4_4"
    assert contract["operation_count"] == 12
    assert all(op["is_manufacturing_dimension"] is True for op in contract["operations"])
    assert all(op["source_reference_evidence"] for op in contract["operations"])
    assert contract["requires_solidworks_lock"] is True
    assert contract["ui_thread_may_execute"] is False

    # Keep the committed artifact aligned with the generator contract.
    artifact = json.loads(Path("drw_output/reference_intent_dimension_plan_006.json").read_text(encoding="utf-8"))
    assert artifact["schema"] == plan["schema"]
    assert len(artifact.get("dimensions") or []) == 12
    assert all(item.get("is_manufacturing_dimension") is True for item in artifact.get("dimensions") or [])

    print("PASS test_v4_4_reference_intent_plan_006")


if __name__ == "__main__":
    main()
