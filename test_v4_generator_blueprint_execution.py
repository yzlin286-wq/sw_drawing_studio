import importlib.util
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory


GENERATOR_PATH = Path(__file__).resolve().parent / ".trae" / "specs" / "build-v6-and-validate-exe-ui" / "drw_generate_v6.py"


def _load_generator():
    spec = importlib.util.spec_from_file_location("drw_generate_v6_v4_blueprint_test", GENERATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _reference_profiles_v4() -> dict:
    return {
        "schema": "sw_drawing_studio.reference_profiles.v4",
        "profiles": {
            "LB26001-A-04-006": {
                "schema": "sw_drawing_studio.reference_profile_sample.v4",
                "base": "LB26001-A-04-006",
                "source_reference": "LB26001-A-04-006.SLDDRW",
                "view_count": 4,
                "view_types": {"7": 2, "4": 2},
                "view_positions": [
                    {"type": "7", "center_norm": [0.3704, 0.8074], "size_norm": [0.20, 0.10]},
                    {"type": "4", "center_norm": [0.7259, 0.8074], "size_norm": [0.14, 0.10]},
                    {"type": "4", "center_norm": [0.3704, 0.5948], "size_norm": [0.20, 0.08]},
                    {"type": "7", "center_norm": [0.8025, 0.4780], "size_norm": [0.12, 0.12]},
                ],
                "sheet_size": {"width": 0.297, "height": 0.21},
                "display_dim_count": 12,
                "titlebar_fields": {"drawing_no": "LB26001-A-04-006"},
                "notes_raw_text": ["TECHNICAL REQUIREMENTS", "UNSPECIFIED ROUGHNESS RA3.2"],
            }
        },
    }


def _manual_blueprint() -> dict:
    return {
        "schema": "sw_drawing_studio.drawing_blueprint.v4",
        "version": "v4.0",
        "base": "LB26001-A-04-006",
        "part_class": "machined_part",
        "view_plan": [
            {
                "slot": "front",
                "view_type": "named",
                "required": True,
                "source": "manual_test",
                "center_norm": [0.25, 0.75],
                "create_method": "named_view",
            },
            {
                "slot": "top",
                "view_type": "projected",
                "required": True,
                "source": "manual_test",
                "center_norm": [0.25, 0.45],
                "sw_view_type": "4",
                "create_method": "projection_api",
                "projected_from": "front",
            },
        ],
        "dimension_plan": {
            "required_display_dim_count": 99,
            "reference_display_dim_count": 99,
            "fallback_policy": "need_review_when_real_displaydim_unavailable",
            "allow_note_substitution": False,
        },
        "annotation_plan": {},
        "titlebar_plan": {
            "fields": {
                "drawing_no": "LB26001-A-04-006",
                "name": "压块",
                "material": "45#",
                "date": "2026-06-22",
            }
        },
        "notes_plan": {
            "required_notes": ["UNSPECIFIED ROUGHNESS RA3.2"],
            "raw_reference_notes": ["DEBURR ALL SHARP EDGES"],
        },
        "validation_plan": {
            "required_artifacts": ["drawing_blueprint.json", "vision_qc.json"],
            "require_true_display_dim": True,
            "forbid_note_as_display_dim": True,
            "forbid_named_view_as_projected": True,
            "require_ui_visual_review": True,
        },
        "layout_plan": {
            "sheet_size": {"width": 0.297, "height": 0.21},
            "notes_box_norm": [0.58, 0.18, 0.98, 0.35],
            "titlebar_box_norm": [0.68, 0.0, 1.0, 0.18],
        },
    }


def _restore_env(snapshot: dict[str, str | None]) -> None:
    for key, value in snapshot.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def test_generator_builds_and_copies_v4_drawing_blueprint_from_reference_profile() -> None:
    module = _load_generator()
    env_snapshot = {
        "REFERENCE_PROFILES_V4": os.environ.get("REFERENCE_PROFILES_V4"),
        "DRAWING_BLUEPRINT_PATH": os.environ.get("DRAWING_BLUEPRINT_PATH"),
    }
    with TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        profile_path = tmp_path / "reference_profiles_v4.json"
        run_dir = tmp_path / "runs" / "one"
        out_dir = tmp_path / "drawing"
        profile_path.write_text(json.dumps(_reference_profiles_v4(), ensure_ascii=False), encoding="utf-8")
        os.environ["REFERENCE_PROFILES_V4"] = str(profile_path)
        os.environ.pop("DRAWING_BLUEPRINT_PATH", None)
        try:
            warnings_box = []
            blueprint, written, source = module._v4_build_or_load_drawing_blueprint(
                tmp_path / "LB26001-A-04-006.SLDPRT",
                run_dir=str(run_dir),
                out_dir=str(out_dir),
                bbox_m=(0.23, 0.013, 0.012),
                src_props={"图号": "LB26001-A-04-006"},
                warnings_box=warnings_box,
            )
        finally:
            _restore_env(env_snapshot)

        assert source == "generated_from_v4_builder"
        assert blueprint["schema"] == "sw_drawing_studio.drawing_blueprint.v4"
        assert module._v4_blueprint_view_keys(blueprint) == ["front", "top", "right", "iso"]
        sheet_policy = blueprint["layout_plan"]["sheet_template_policy"]
        assert sheet_policy["policy"] == "strip_default_template_artifacts"
        assert sheet_policy["default_template_artifacts_allowed"] is False
        assert module._v4_blueprint_default_titleblock_policy(blueprint) == (
            False,
            "DrawingBlueprint.layout_plan.sheet_template_policy",
        )
        assert module._v4_blueprint_dim_floor(blueprint) == 12
        assert len((blueprint["dimension_plan"]).get("dimension_targets") or []) == 12
        assert module._v4_dimension_view_quotas(blueprint) == {"front": 3, "top": 6, "right": 3}
        assert module._v4_dimension_autodim_slots(blueprint) == ["front", "top", "right"]
        assert blueprint["reference_storyboard"]["narrative"] == "readable_manufacturing_drawing"
        assert blueprint["view_roles"]["iso"]["allow_dimension_targets"] is False
        assert blueprint["notes_title_policy"]["strip_default_template_artifacts"] is True
        assert len(blueprint["layout_plan"]["dimension_lane_policy"]["lane_targets"]) == 12
        centers = module._v4_blueprint_layout_centers(blueprint)
        assert round(centers["front"][0], 4) == round(0.3704 * 0.297, 4)
        assert round(centers["front"][1], 4) == round(0.8074 * 0.21, 4)
        outlines = module._v4_blueprint_layout_outlines(blueprint)
        assert "front" in outlines
        assert round(outlines["front"][2] - outlines["front"][0], 4) == round(0.20 * 0.297, 4)
        assert run_dir.joinpath("qc", "drawing_blueprint.json").exists()
        assert out_dir.joinpath("LB26001-A-04-006_drawing_blueprint.json").exists()
        assert set(written) == {
            str(run_dir / "qc" / "drawing_blueprint.json"),
            str(out_dir / "LB26001-A-04-006_drawing_blueprint.json"),
        }
        assert any(item.get("code") == "drawing_blueprint_v4" for item in warnings_box)


def test_reference_outline_scale_hint_prefers_same_name_reference_size() -> None:
    module = _load_generator()
    blueprint = {
        "layout_plan": {"sheet_size": {"width": 0.297, "height": 0.21}},
        "view_plan": [
            {"slot": "front", "outline_norm": [0.1627, 0.7719, 0.5781, 0.8429]},
            {"slot": "top", "outline_norm": [0.1627, 0.5605, 0.5781, 0.6291]},
            {"slot": "right", "outline_norm": [0.7016, 0.7719, 0.7501, 0.8429]},
            {"slot": "iso", "outline_norm": [0.7164, 0.3929, 0.8886, 0.5631]},
        ],
    }

    outlines = module._v4_blueprint_layout_outlines(blueprint)
    assert round(outlines["front"][2] - outlines["front"][0], 4) == round(0.4154 * 0.297, 4)
    assert module._reference_outline_scale_hint(
        (0.23, 0.013, 0.012),
        outlines,
        ["front", "top", "right", "iso"],
    ) == (1, 2)


def test_generator_loads_explicit_drawing_blueprint_path_before_building_one() -> None:
    module = _load_generator()
    env_snapshot = {
        "REFERENCE_PROFILES_V4": os.environ.get("REFERENCE_PROFILES_V4"),
        "DRAWING_BLUEPRINT_PATH": os.environ.get("DRAWING_BLUEPRINT_PATH"),
    }
    with TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        blueprint_path = tmp_path / "manual_drawing_blueprint.json"
        run_dir = tmp_path / "runs" / "manual"
        out_dir = tmp_path / "drawing"
        blueprint_path.write_text(json.dumps(_manual_blueprint(), ensure_ascii=False), encoding="utf-8")
        os.environ["DRAWING_BLUEPRINT_PATH"] = str(blueprint_path)
        os.environ.pop("REFERENCE_PROFILES_V4", None)
        try:
            warnings_box = []
            blueprint, written, source = module._v4_build_or_load_drawing_blueprint(
                tmp_path / "LB26001-A-04-006.SLDPRT",
                run_dir=str(run_dir),
                out_dir=str(out_dir),
                bbox_m=(0.12, 0.04, 0.02),
                src_props={},
                warnings_box=warnings_box,
            )
        finally:
            _restore_env(env_snapshot)

        assert source == str(blueprint_path)
        assert module._v4_blueprint_view_keys(blueprint) == ["front", "top"]
        assert module._v4_blueprint_dim_floor(blueprint) == 99
        assert len(written) == 2
        copied = json.loads(run_dir.joinpath("qc", "drawing_blueprint.json").read_text(encoding="utf-8"))
        assert copied["dimension_plan"]["required_display_dim_count"] == 99
        assert any(
            item.get("code") == "drawing_blueprint_v4"
            and item.get("required_display_dim_count") == 99
            for item in warnings_box
        )


def test_generator_builds_blueprint_titlebar_notes_and_annotation_execution_plan() -> None:
    module = _load_generator()
    blueprint = _manual_blueprint()

    overrides = module._v4_titlebar_property_overrides(blueprint)
    assert overrides["图号"] == "LB26001-A-04-006"
    assert overrides["品名"] == "压块"
    assert overrides["材质"] == "45#"

    src_props = {"图号": "OLD", "品名": "", "材质": ""}
    warnings_box = [{"code": "prop_missing", "key": "品名"}]
    applied = module._v4_apply_titlebar_property_overrides(src_props, blueprint, warnings_box=warnings_box)
    assert applied["图号"] == "LB26001-A-04-006"
    assert src_props["图号"] == "LB26001-A-04-006"
    assert src_props["品名"] == "压块"
    assert not any(item.get("code") == "prop_missing" and item.get("key") == "品名" for item in warnings_box)

    flags = module._v4_blueprint_annotation_flags(blueprint)
    assert flags["roughness_required"] is True
    assert flags["datum_required"] is False
    assert flags["gtol_required"] is False

    note_plan = module._v4_blueprint_note_insertions(blueprint)
    assert len(note_plan) == 1
    assert "UNSPECIFIED ROUGHNESS RA3.2" in note_plan[0]["text"]
    assert "DEBURR ALL SHARP EDGES" in note_plan[0]["text"]
    assert note_plan[0]["position_m"][0] > 0.17
    assert note_plan[0]["position_m"][1] > 0.06

    titlebar_plan = module._v4_blueprint_titlebar_insertions(blueprint, src_props)
    assert len(titlebar_plan) == 1
    assert "图号: LB26001-A-04-006" in titlebar_plan[0]["text"]
    assert "品名: 压块" in titlebar_plan[0]["text"]
    assert titlebar_plan[0]["position_m"][0] > 0.20
    assert titlebar_plan[0]["position_m"][1] < 0.04


def test_generator_runs_dimension_arrange_before_visual_exports() -> None:
    source = GENERATOR_PATH.read_text(encoding="utf-8")

    assert "from app.services.dimension_arrange_service import arrange_dimensions" in source
    assert '_run_dimension_arrange_stage("pre_export")' in source
    assert '_run_dimension_arrange_stage("post_layout")' in source
    assert '"dimension_arrange_results": _dimension_arrange_results' in source
    assert "def _arrange_layout_with_blueprint_context" in source
    assert 'merged.setdefault("part_class"' in source
    assert "def _long_thin_candidates" in source
    assert 'part_class == "long_thin"' in source
    assert "right_callout" in source
    assert "callout_lane_count" in source
    assert "_apply_horizontal_dimension_text_policy" in source
    assert "swBrokenLeaderHorizontalText" in source
    assert "required_slots = _v4_dimension_autodim_slots" in source
    assert "reference_intent_autodimension_disabled" in source
    assert "post_layout_reference_intent_autodimension_disabled" in source
    assert "def _run_reference_intent_explicit_display_dims" in source
    assert "GetVisibleEntities2" in source
    assert "visible_entities2_select4_adddimension2" in source
    assert "nearest_layout_center" in source
    assert "AddDiameterDimension2" in source
    assert "reference_intent_floor_guard_no_delete" in source
    assert '"delete_plan": []' in source
    assert '"deleted_items": []' in source
    assert "target_match" in source
    assert "reference_intent_target_coverage" in source
    assert "persisted_after_reopen" in source
    assert "reference_intent_explicit_display_dims" in source
    assert '"explicit_display_dims": _explicit_dim_result' in source
    assert '"explicit_display_dims": _post_layout_explicit' in source
    assert "slot_quotas=slot_quotas" in source
    assert "_score_display_dim_for_reference_intent" in source
    assert "reference_intent_score_before" in source
    assert "dimension_plan=dimension_plan" in source
    assert "REFERENCE_INTENT_DIMENSION_PLAN_PATH" in source
    assert "dimension_targets" in source
    assert "placement_lane" in source
    assert "prune_protection_policy" in source
    assert "reference_intent_target_protected_no_delete" in source
    assert "persisted_real_outlines_recovered_view" in source
    assert "post_layout_reference_prune" in source
    assert "def _v4_blueprint_default_titleblock_policy" in source
    assert "DrawingBlueprint.layout_plan.sheet_template_policy" in source


if __name__ == "__main__":
    test_generator_builds_and_copies_v4_drawing_blueprint_from_reference_profile()
    test_generator_loads_explicit_drawing_blueprint_path_before_building_one()
    test_generator_builds_blueprint_titlebar_notes_and_annotation_execution_plan()
    test_generator_runs_dimension_arrange_before_visual_exports()
    print("PASS test_v4_generator_blueprint_execution")
