import json
from pathlib import Path
from tempfile import TemporaryDirectory

from app.services.dimension_planner import build_dimension_plan
from app.services.drawing_blueprint_builder import build_drawing_blueprint
from app.services.drawing_blueprint_model import DrawingBlueprint, blueprint_json_schema
from app.services.reference_style_profile_service import build_reference_profiles_v4
from tools.ui_robot.drawing_visual_review_suite import _find_generated_png


def _v3_profile() -> dict:
    return {
        "schema": "sw_drawing_studio.reference_style_profile.v1",
        "reference_samples": {
            "LB26001-A-04-006": {
                "success": True,
                "path": "LB26001-A-04-006.SLDDRW",
                "view_count": 4,
                "view_types": {"7": 2, "4": 2},
                "display_dim_count": 12,
                "sheet_size_m": {"width": 0.297, "height": 0.21},
                "view_layout": [
                    {"type": "7", "center_norm": [0.3704, 0.8074], "size_norm": [0.20, 0.10]},
                    {"type": "4", "center_norm": [0.7259, 0.8074], "size_norm": [0.14, 0.10]},
                    {"type": "4", "center_norm": [0.3704, 0.5948], "size_norm": [0.20, 0.08]},
                    {"type": "7", "center_norm": [0.8025, 0.4780], "size_norm": [0.12, 0.12]},
                ],
                "notes_raw_text": ["技术要求：", "未注粗糙度 Ra3.2。"],
            },
            "LB26001-A-04-022": {
                "success": True,
                "path": "LB26001-A-04-022.SLDDRW",
                "view_count": 4,
                "view_types": {"7": 2, "4": 2},
                "display_dim_count": 25,
                "sheet_size_m": {"width": 0.297, "height": 0.21},
                "view_layout": [
                    {"type": "7", "center_norm": [0.3704, 0.6895]},
                    {"type": "4", "center_norm": [0.7071, 0.6895]},
                    {"type": "4", "center_norm": [0.3704, 0.3495]},
                    {"type": "7", "center_norm": [0.8324, 0.4536]},
                ],
            },
        },
    }


def test_blueprint_schema_contains_required_v4_plans() -> None:
    schema = blueprint_json_schema()
    assert schema["properties"]["schema"]["const"] == "sw_drawing_studio.drawing_blueprint.v4"
    required = set(schema["required"])
    assert {"view_plan", "dimension_plan", "notes_plan", "validation_plan"} <= required
    assert "reference_storyboard" in schema["properties"]
    assert "view_roles" in schema["properties"]
    assert "notes_title_policy" in schema["properties"]
    assert "visual_acceptance_checklist" in schema["properties"]
    assert schema["$defs"]["DimensionPlan"]["properties"]["allow_note_substitution"]["const"] is False
    assert "dimension_intent_groups" in schema["$defs"]["DimensionPlan"]["properties"]
    assert "dimension_targets" in schema["$defs"]["DimensionPlan"]["properties"]
    assert "view_dimension_quotas" in schema["$defs"]["DimensionPlan"]["properties"]
    assert schema["$defs"]["ValidationPlan"]["properties"]["forbid_named_view_as_projected"]["const"] is True


def test_reference_profile_builds_blueprint_with_projection_and_displaydim_floor() -> None:
    with TemporaryDirectory() as tmp:
        profile_path = Path(tmp) / "v3_profile.json"
        out_path = Path(tmp) / "reference_profiles_v4.json"
        profile_path.write_text(json.dumps(_v3_profile(), ensure_ascii=False), encoding="utf-8")

        payload = build_reference_profiles_v4(source_profile=profile_path, out_path=out_path)
        reference_006 = payload["profiles"]["LB26001-A-04-006"]
        blueprint = build_drawing_blueprint(
            base="LB26001-A-04-006",
            part_class="machined_part",
            reference_profile=reference_006,
        )
        data = blueprint.to_dict()

        assert out_path.exists()
        assert data["dimension_plan"]["required_display_dim_count"] == 12
        assert data["dimension_plan"]["allow_note_substitution"] is False
        assert len(data["dimension_plan"]["dimension_targets"]) == 12
        assert all(item["create_as"] == "SolidWorks DisplayDim" for item in data["dimension_plan"]["dimension_targets"])
        assert data["reference_storyboard"]["narrative"] == "readable_manufacturing_drawing"
        assert data["reference_storyboard"]["primary_reading_order"] == ["front", "top", "right", "iso"]
        assert data["view_roles"]["top"]["role"] == "functional_feature_relationships"
        assert data["view_roles"]["iso"]["allow_dimension_targets"] is False
        assert data["notes_title_policy"]["strip_default_template_artifacts"] is True
        assert set(data["visual_acceptance_checklist"]) == {
            "reference_match",
            "view_layout",
            "display_dimensions",
            "dimension_readability",
            "title_block",
            "manufacturing_notes",
        }
        projected = [item for item in data["view_plan"] if item["sw_view_type"] == "4"]
        assert projected
        assert all(item["create_method"] == "projection_api" for item in projected)
        assert all(item["projected_from"] == "front" for item in projected)
        assert data["validation_plan"]["require_ui_visual_review"] is True
        sheet_policy = data["layout_plan"]["sheet_template_policy"]
        assert sheet_policy["policy"] == "strip_default_template_artifacts"
        assert sheet_policy["default_template_artifacts_allowed"] is False
        assert sheet_policy["skip_builtin_gb_frame_titleblock"] is True
        lane_policy = data["layout_plan"]["dimension_lane_policy"]
        assert lane_policy["fallback_when_unreadable"] == "rearrange_before_validation"
        assert len(lane_policy["lane_targets"]) == 12
        assert "reference_sheet_template_policy:strip_default_template_artifacts" in data["warnings"]
        assert data["notes_plan"]["raw_reference_notes"]

        roundtrip = DrawingBlueprint.from_dict(data)
        assert roundtrip.base == "LB26001-A-04-006"


def test_long_thin_blueprint_adds_reference_intent_dimension_quotas() -> None:
    with TemporaryDirectory() as tmp:
        profile_path = Path(tmp) / "v3_profile.json"
        out_path = Path(tmp) / "reference_profiles_v4.json"
        profile_path.write_text(json.dumps(_v3_profile(), ensure_ascii=False), encoding="utf-8")

        payload = build_reference_profiles_v4(source_profile=profile_path, out_path=out_path)
        reference_006 = payload["profiles"]["LB26001-A-04-006"]
        blueprint = build_drawing_blueprint(
            base="LB26001-A-04-006",
            part_class="long_thin",
            reference_profile=reference_006,
        )
        plan = blueprint.to_dict()["dimension_plan"]

        assert plan["required_display_dim_count"] == 12
        assert plan["view_dimension_quotas"] == {"front": 3, "top": 6, "right": 3}
        assert len(plan["dimension_targets"]) == 12
        assert {item["key"] for item in plan["dimension_targets"]} >= {"hole_diameter", "hole_x_location", "projection_view_height"}
        targets = {item["key"]: item for item in plan["dimension_targets"]}
        assert targets["hole_diameter"]["functional_role"] == "hole_size_for_drilling_and_inspection"
        assert targets["hole_pitch"]["placement_lane"]["station"] == 0.70
        assert targets["overall_length"]["prune_protection_policy"]["protected"] is True
        intent_keys = [item["key"] for item in plan["dimension_intent_groups"]]
        assert {"overall_envelope", "end_offsets", "hole_locations", "small_projected_view"} <= set(intent_keys)
        assert "view_dimension_quotas_control_autodim_prune" in plan["reasons"]


def test_dimension_planner_preserves_022_reference_floor() -> None:
    plan = build_dimension_plan(
        part_class="machined_part",
        reference_dimension_profile={"display_dim_count": 25},
    )
    assert plan.required_display_dim_count == 25
    assert plan.reference_display_dim_count == 25
    assert plan.fallback_policy == "need_review_when_real_displaydim_unavailable"


def test_dimension_planner_does_not_apply_universal_dim_total_5_gate_when_reference_is_lower() -> None:
    plan = build_dimension_plan(
        part_class="machined_part",
        reference_dimension_profile={"display_dim_count": 4},
    )
    assert plan.required_display_dim_count == 4
    assert "required_display_dim_count=4" in plan.reasons


def test_reference_notes_profile_detects_uppercase_ra_roughness_requirement() -> None:
    blueprint = build_drawing_blueprint(
        base="LB26001-A-04-006",
        part_class="machined_part",
        reference_profile={
            "base": "LB26001-A-04-006",
            "display_dim_count": 12,
            "notes_raw_text": ["UNSPECIFIED ROUGHNESS RA3.2"],
        },
    )
    data = blueprint.to_dict()

    assert data["annotation_plan"]["roughness_required"] is True
    assert any("roughness" in item.lower() for item in data["notes_plan"]["warning_notes"])


def test_default_notes_plan_propagates_roughness_into_annotation_plan() -> None:
    blueprint = build_drawing_blueprint(
        base="NO-REFERENCE",
        part_class="machined_part",
        reference_profile={},
    )
    data = blueprint.to_dict()

    assert any("Ra" in item or "粗糙度" in item for item in data["notes_plan"]["required_notes"])
    assert data["annotation_plan"]["roughness_required"] is True


def test_ui_visual_review_does_not_fallback_to_historical_v5_png() -> None:
    with TemporaryDirectory() as tmp:
        run_dir = Path(tmp) / "runs" / "fresh"
        historical = Path(tmp) / "drw_output" / "v5" / "LB26001-A-04-006_v5.PNG"
        historical.parent.mkdir(parents=True)
        historical.write_bytes(b"old")

        result = _find_generated_png("LB26001-A-04-006", run_dir)
        assert result == run_dir / "drawing" / "LB26001-A-04-006_v5.PNG"
        assert not result.exists()


if __name__ == "__main__":
    test_blueprint_schema_contains_required_v4_plans()
    test_reference_profile_builds_blueprint_with_projection_and_displaydim_floor()
    test_long_thin_blueprint_adds_reference_intent_dimension_quotas()
    test_dimension_planner_preserves_022_reference_floor()
    test_dimension_planner_does_not_apply_universal_dim_total_5_gate_when_reference_is_lower()
    test_reference_notes_profile_detects_uppercase_ra_roughness_requirement()
    test_default_notes_plan_propagates_roughness_into_annotation_plan()
    test_ui_visual_review_does_not_fallback_to_historical_v5_png()
    print("PASS test_v4_drawing_blueprint_core")
