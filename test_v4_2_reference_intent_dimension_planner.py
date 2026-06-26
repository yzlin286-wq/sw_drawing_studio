from pathlib import Path

from app.services.reference_intent_dimension_executor import build_execution_contract
from app.services.reference_intent_dimension_planner import (
    build_reference_intent_dimension_plan,
    load_reference_profile,
    write_reference_intent_dimension_plan,
)


def test_006_reference_intent_dimension_plan_has_required_contract_fields() -> None:
    profile = load_reference_profile("LB26001-A-04-006")
    plan = build_reference_intent_dimension_plan("LB26001-A-04-006", reference_profile=profile)

    assert plan["base"] == "LB26001-A-04-006"
    assert plan["required_display_dim_count"] >= 12
    assert plan["reference_display_dim_count"] == 12
    assert plan["allow_note_substitution"] is False
    assert plan["ui_screenshot_acceptance_required"] is True
    assert {"front", "top", "right", "iso"}.issubset(set(plan["reference_view_slots"]))
    assert len(plan["dimensions"]) >= 12
    callouts = {item["key"]: item for item in plan["reference_callouts"]}
    assert {"thread_callout_m4_6h", "surface_finish_rest_3_2"} <= set(callouts)
    assert callouts["thread_callout_m4_6h"]["create_as"] != "SolidWorks DisplayDim"
    assert callouts["thread_callout_m4_6h"]["forbid_note_substitution_for_displaydim"] is True
    assert callouts["surface_finish_rest_3_2"]["create_as"] == "manufacturing note/symbol; does not count as DisplayDim"
    layout_plan = plan["layout_plan"]
    assert layout_plan["sheet_template_policy"]["skip_builtin_gb_frame_titleblock"] is True
    assert layout_plan["sheet_template_policy"]["default_template_artifacts_allowed"] is False
    assert layout_plan["reference_titlebar_policy"]["suppress_default_titlebar_fields"] is True
    assert layout_plan["reference_titlebar_policy"]["render_reference_bottom_notice"] is True
    assert plan["reference_titlebar_policy"]["suppress_drawing_no_name_visible_note"] is True
    assert layout_plan["reference_view_outline_policy"]["view_outline_size_match_required"] is True
    assert layout_plan["reference_view_outline_policy"]["independent_view_scale_allowed"] is True
    assert layout_plan["reference_view_outline_policy"]["downscale_oversized_views_only"] is True
    assert plan["reference_view_outline_policy"]["target_outlines_required"] is True

    for dimension in plan["dimensions"]:
        assert dimension["source_reference"].endswith("LB26001-A-04-006.SLDDRW")
        assert dimension["target_view"]
        assert dimension["expected_type"]
        assert dimension["fallback_policy"] == "need_review_when_real_displaydim_unavailable"
        assert dimension["create_as"] == "SolidWorks DisplayDim"
        assert dimension["forbid_note_substitution"] is True
        assert dimension["functional_role"]
        assert dimension["reading_group"]
        assert dimension["placement_lane"]["readability_required"] is True
        assert dimension["allowed_witness_entity"]["must_be_visible_in_target_view"] is True
        assert dimension["prune_protection_policy"]["protected"] is True
        assert dimension["prune_protection_policy"]["delete_only_if_target_covered_elsewhere"] is True

    targets = {item["key"]: item for item in plan["dimensions"]}
    assert targets["hole_diameter"]["placement_lane"]["lane_family"] == "outside_top"
    assert plan["reference_dimension_lane_policy"]["top_view_right_callout_lane_allowed_for_displaydim"] is False
    assert plan["reference_dimension_lane_policy"]["right_side_hole_thread_text_uses_callout_checklist"] is True
    assert targets["hole_pitch"]["placement_lane"]["station"] == 0.70
    assert targets["projection_view_height"]["reading_group"] == "04_small_projected_view"


def test_006_execution_contract_requires_worker_lock_and_does_not_call_com() -> None:
    profile = load_reference_profile("LB26001-A-04-006")
    plan = build_reference_intent_dimension_plan("LB26001-A-04-006", reference_profile=profile)
    contract = build_execution_contract(plan, drawing_path=Path("drawing.SLDDRW"))

    assert contract["requires_solidworks_lock"] is True
    assert contract["ui_thread_may_execute"] is False
    assert contract["direct_com_called"] is False
    assert contract["allowed_entrypoint"] == "cad_job_worker"
    assert contract["failure_status_without_lock"] == "blocked_by_solidworks_lock"
    assert contract["operation_count"] == len(plan["dimensions"])
    assert all(item["requires_solidworks_lock"] for item in contract["operations"])
    assert all(item["allowed_entrypoint"] == "cad_job_worker" for item in contract["operations"])
    first = contract["operations"][0]
    assert first["functional_role"]
    assert first["placement_lane"]["readability_required"] is True
    assert first["prune_protection_policy"]["protected"] is True


def test_write_006_reference_intent_dimension_plan_artifact() -> None:
    profile = load_reference_profile("LB26001-A-04-006")
    plan = build_reference_intent_dimension_plan("LB26001-A-04-006", reference_profile=profile)
    out = write_reference_intent_dimension_plan(
        plan,
        Path("drw_output/reference_intent_dimension_plan_006.json"),
    )

    assert out.exists()
    assert "reference_intent_dimension_plan" in out.read_text(encoding="utf-8")


if __name__ == "__main__":
    test_006_reference_intent_dimension_plan_has_required_contract_fields()
    test_006_execution_contract_requires_worker_lock_and_does_not_call_com()
    test_write_006_reference_intent_dimension_plan_artifact()
    print("OK test_v4_2_reference_intent_dimension_planner")
