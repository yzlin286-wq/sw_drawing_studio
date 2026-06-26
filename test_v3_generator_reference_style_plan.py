import importlib.util
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory


GENERATOR_PATH = Path(__file__).resolve().parent / ".trae" / "specs" / "build-v6-and-validate-exe-ui" / "drw_generate_v6.py"


def _load_generator():
    spec = importlib.util.spec_from_file_location("drw_generate_v6_under_test", GENERATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _layout(points: list[tuple[str, tuple[float, float]]]) -> list[dict]:
    return [
        {"type": vtype, "center_norm": [point[0], point[1]]}
        for vtype, point in points
    ]


def _profile() -> dict:
    return {
        "schema": "sw_drawing_studio.reference_style_profile.v1",
        "status": "profile_ready",
        "reference_samples": {
            "LB26001-A-04-006": {
                "view_count": 4,
                "view_types": {"7": 2, "4": 2},
                "display_dim_count": 12,
                "sheet_size_m": {"width": 0.297, "height": 0.21},
                "view_layout": _layout([
                    ("7", (0.3704, 0.8074)),
                    ("4", (0.7259, 0.8074)),
                    ("4", (0.3704, 0.5948)),
                    ("7", (0.8025, 0.4780)),
                ]),
            },
            "LB26001-A-04-007": {
                "view_count": 4,
                "view_types": {"7": 2, "4": 2},
                "display_dim_count": 8,
                "sheet_size_m": {"width": 0.297, "height": 0.21},
                "view_layout": _layout([
                    ("7", (0.3196, 0.7326)),
                    ("4", (0.4992, 0.7326)),
                    ("4", (0.3196, 0.3947)),
                    ("7", (0.6444, 0.4988)),
                ]),
            },
            "LB26001-A-04-008": {
                "view_count": 2,
                "view_types": {"7": 1, "4": 1},
                "display_dim_count": 2,
                "sheet_size_m": {"width": 0.297, "height": 0.21},
                "view_layout": _layout([
                    ("7", (0.3037, 0.7061)),
                    ("4", (0.3037, 0.4240)),
                ]),
            },
            "LB26001-A-04-009": {
                "view_count": 3,
                "view_types": {"7": 1, "4": 2},
                "display_dim_count": 4,
                "sheet_size_m": {"width": 0.297, "height": 0.21},
                "view_layout": _layout([
                    ("7", (0.3514, 0.6819)),
                    ("4", (0.3514, 0.4114)),
                    ("4", (0.8329, 0.5644)),
                ]),
            },
            "LB26001-A-04-015": {
                "view_count": 2,
                "view_types": {"7": 1, "4": 1},
                "display_dim_count": 14,
                "sheet_size_m": {"width": 0.297, "height": 0.21},
                "view_layout": _layout([
                    ("7", (0.3535, 0.7419)),
                    ("4", (0.3535, 0.3734)),
                ]),
            },
            "LB26001-A-04-022": {
                "view_count": 4,
                "view_types": {"7": 2, "4": 2},
                "display_dim_count": 25,
                "sheet_size_m": {"width": 0.297, "height": 0.21},
                "view_layout": _layout([
                    ("7", (0.3704, 0.6895)),
                    ("4", (0.7071, 0.6895)),
                    ("4", (0.3704, 0.3495)),
                    ("7", (0.8324, 0.4536)),
                ]),
            },
            "LB26001-A-04-002": {
                "view_count": 4,
                "view_types": {"7": 2, "4": 2},
                "display_dim_count": 12,
                "sheet_size_m": {"width": 0.297, "height": 0.21},
                "view_layout": _layout([
                    ("7", (0.321, 0.72)),
                    ("4", (0.321, 0.39)),
                    ("4", (0.61, 0.72)),
                    ("7", (0.78, 0.50)),
                ]),
            },
            "LB26001-A-04-025": {
                "view_count": 3,
                "view_types": {"7": 1, "4": 2},
                "display_dim_count": 18,
                "sheet_size_m": {"width": 0.297, "height": 0.21},
                "view_layout": _layout([
                    ("7", (0.33, 0.70)),
                    ("4", (0.33, 0.42)),
                    ("4", (0.72, 0.58)),
                ]),
            },
            "LB26001-A-04-031": {
                "view_count": 3,
                "view_types": {"7": 2, "4": 1},
                "display_dim_count": 11,
                "sheet_size_m": {"width": 0.297, "height": 0.21},
                "view_layout": _layout([
                    ("7", (0.3402, 0.7311)),
                    ("4", (0.3402, 0.4176)),
                    ("7", (0.7631, 0.4826)),
                ]),
            },
            "LB26001-A-04-035": {
                "view_count": 4,
                "view_types": {"7": 1, "4": 3},
                "display_dim_count": 11,
                "sheet_size_m": {"width": 0.297, "height": 0.21},
                "view_layout": _layout([
                    ("7", (0.2699, 0.7110)),
                    ("4", (0.2699, 0.3439)),
                    ("4", (0.5424, 0.7110)),
                    ("4", (0.7384, 0.4620)),
                ]),
            },
            "LB26001-A-04-050": {
                "view_count": 3,
                "view_types": {"7": 1, "4": 2},
                "display_dim_count": 21,
                "sheet_size_m": {"width": 0.297, "height": 0.21},
                "view_layout": _layout([
                    ("7", (0.35, 0.70)),
                    ("4", (0.35, 0.42)),
                    ("4", (0.78, 0.55)),
                ]),
            },
        },
        "aggregate": {
            "min_display_dim_by_sample": {
                "LB26001-A-04-006": 12,
                "LB26001-A-04-007": 8,
                "LB26001-A-04-008": 2,
                "LB26001-A-04-009": 4,
                "LB26001-A-04-015": 14,
                "LB26001-A-04-022": 25,
                "LB26001-A-04-002": 12,
                "LB26001-A-04-025": 18,
                "LB26001-A-04-031": 11,
                "LB26001-A-04-035": 11,
                "LB26001-A-04-050": 21,
            }
        },
    }


def test_generator_prefers_lb26001_36_reference_profile_before_legacy_six() -> None:
    module = _load_generator()
    old_profile = os.environ.get("REFERENCE_STYLE_PROFILE")
    os.environ.pop("REFERENCE_STYLE_PROFILE", None)
    try:
        candidates = module._reference_style_profile_candidates()
    finally:
        if old_profile is not None:
            os.environ["REFERENCE_STYLE_PROFILE"] = old_profile

    names = [Path(candidate).name for candidate in candidates]
    assert names[:2] == [
        "lb26001_36_reference_style_profile.json",
        "lb26001_reference_style_profile.json",
    ]


def test_generator_uses_all_six_lb26001_reference_style_plans() -> None:
    module = _load_generator()
    expected = {
        "LB26001-A-04-006": (["front", "top", "right", "iso"], 12),
        "LB26001-A-04-007": (["front", "top", "right", "iso"], 8),
        "LB26001-A-04-008": (["front", "top"], 2),
        "LB26001-A-04-009": (["front", "top", "right"], 4),
        "LB26001-A-04-015": (["front", "top"], 14),
        "LB26001-A-04-022": (["front", "top", "right", "iso"], 25),
    }
    old_profile = os.environ.get("REFERENCE_STYLE_PROFILE")
    with TemporaryDirectory() as tmp:
        profile_path = Path(tmp) / "lb26001_reference_style_profile.json"
        profile_path.write_text(json.dumps(_profile(), ensure_ascii=False), encoding="utf-8")
        os.environ["REFERENCE_STYLE_PROFILE"] = str(profile_path)
        try:
            for base, (view_keys, dim_floor) in expected.items():
                part = Path(tmp) / f"{base}.SLDPRT"
                assert module._reference_style_view_plan(part)[0] == view_keys
                assert module._reference_style_dim_floor(part)[0] == dim_floor
                section_allowed, section_source = module._reference_style_allows_section_view(part)
                assert section_allowed is False
                assert section_source.endswith("lb26001_reference_style_profile.json")
        finally:
            if old_profile is None:
                os.environ.pop("REFERENCE_STYLE_PROFILE", None)
            else:
                os.environ["REFERENCE_STYLE_PROFILE"] = old_profile


def test_generator_uses_lb26001_36_reference_view_families() -> None:
    module = _load_generator()
    expected = {
        "LB26001-A-04-002": (["front", "top", "right", "iso"], 12, {"front", "top", "right", "iso"}),
        "LB26001-A-04-025": (["front", "top", "right"], 18, {"front", "top", "right"}),
        "LB26001-A-04-031": (["front", "top", "iso"], 11, {"front", "top", "iso"}),
        "LB26001-A-04-035": (["front", "top", "right", "bottom"], 11, {"front", "top", "right", "bottom"}),
        "LB26001-A-04-050": (["front", "top", "right"], 21, {"front", "top", "right"}),
    }
    old_profile = os.environ.get("REFERENCE_STYLE_PROFILE")
    with TemporaryDirectory() as tmp:
        profile_path = Path(tmp) / "lb26001_reference_style_profile.json"
        profile_path.write_text(json.dumps(_profile(), ensure_ascii=False), encoding="utf-8")
        os.environ["REFERENCE_STYLE_PROFILE"] = str(profile_path)
        try:
            for base, (view_keys, dim_floor, center_keys) in expected.items():
                part = Path(tmp) / f"{base}.SLDPRT"
                assert module._reference_style_view_plan(part)[0] == view_keys
                assert module._reference_style_dim_floor(part)[0] == dim_floor
                centers, source = module._reference_style_layout_centers(part, view_keys)
                assert set(centers) == center_keys
                assert source.endswith("lb26001_reference_style_profile.json")
                section_allowed, section_source = module._reference_style_allows_section_view(part)
                assert section_allowed is False
                assert section_source.endswith("lb26001_reference_style_profile.json")
        finally:
            if old_profile is None:
                os.environ.pop("REFERENCE_STYLE_PROFILE", None)
            else:
                os.environ["REFERENCE_STYLE_PROFILE"] = old_profile


def test_generator_uses_first_angle_when_top_and_right_projected_slots_are_required() -> None:
    module = _load_generator()

    assert module._reference_style_should_use_first_angle(["front", "top", "right"]) is True
    assert module._reference_style_should_use_first_angle(["front", "top", "right", "iso"]) is False
    assert module._reference_style_should_use_first_angle(["front", "top", "iso"]) is False
    assert module._reference_style_should_use_first_angle(["front", "top", "right", "bottom"]) is False


def test_persisted_layout_centers_follow_created_view_order() -> None:
    module = _load_generator()
    centers = {
        "front": (0.080164, 0.14931),
        "top": (0.080164, 0.072211),
        "right": (0.161103, 0.14931),
        "iso": (0.230, 0.180),
        "bottom": (0.219297, 0.097024),
    }

    result = module._created_view_centers_for_persisted_layout(
        ["front", "top", "right", "bottom"],
        centers,
    )

    assert list(result) == ["front", "top", "right", "bottom"]
    assert result["bottom"] == centers["bottom"]
    assert "iso" not in result


def test_generator_allows_section_for_unknown_or_reference_section_samples() -> None:
    module = _load_generator()
    profile = _profile()
    profile["reference_samples"]["LB26001-A-04-099"] = {
        "view_count": 3,
        "view_types": {"7": 1, "4": 1, "3": 1},
        "display_dim_count": 5,
        "sheet_size_m": {"width": 0.297, "height": 0.21},
        "view_layout": _layout([
            ("7", (0.30, 0.70)),
            ("4", (0.30, 0.40)),
            ("3", (0.70, 0.40)),
        ]),
    }

    old_profile = os.environ.get("REFERENCE_STYLE_PROFILE")
    with TemporaryDirectory() as tmp:
        profile_path = Path(tmp) / "lb26001_reference_style_profile.json"
        profile_path.write_text(json.dumps(profile, ensure_ascii=False), encoding="utf-8")
        os.environ["REFERENCE_STYLE_PROFILE"] = str(profile_path)
        try:
            assert module._reference_style_allows_section_view(Path(tmp) / "UNKNOWN.SLDPRT") == (True, "")
            allowed, source = module._reference_style_allows_section_view(Path(tmp) / "LB26001-A-04-099.SLDPRT")
            assert allowed is True
            assert source.endswith("lb26001_reference_style_profile.json")
        finally:
            if old_profile is None:
                os.environ.pop("REFERENCE_STYLE_PROFILE", None)
            else:
                os.environ["REFERENCE_STYLE_PROFILE"] = old_profile


def test_generator_skips_builtin_titleblock_for_same_name_reference_samples() -> None:
    module = _load_generator()
    old_profile = os.environ.get("REFERENCE_STYLE_PROFILE")
    old_force = os.environ.get("FORCE_DEFAULT_TITLEBLOCK")
    with TemporaryDirectory() as tmp:
        profile_path = Path(tmp) / "lb26001_reference_style_profile.json"
        profile_path.write_text(json.dumps(_profile(), ensure_ascii=False), encoding="utf-8")
        os.environ["REFERENCE_STYLE_PROFILE"] = str(profile_path)
        os.environ.pop("FORCE_DEFAULT_TITLEBLOCK", None)
        try:
            should_draw, source = module._reference_style_should_draw_default_titleblock(
                Path(tmp) / "LB26001-A-04-006.SLDPRT",
                ["front", "top", "right", "iso"],
            )
            assert should_draw is False
            assert source.endswith("lb26001_reference_style_profile.json")

            should_draw_unknown, source_unknown = module._reference_style_should_draw_default_titleblock(
                Path(tmp) / "UNKNOWN.SLDPRT",
                [],
            )
            assert should_draw_unknown is True
            assert source_unknown == ""

            os.environ["FORCE_DEFAULT_TITLEBLOCK"] = "1"
            forced_draw, forced_source = module._reference_style_should_draw_default_titleblock(
                Path(tmp) / "LB26001-A-04-006.SLDPRT",
                ["front", "top", "right", "iso"],
            )
            assert forced_draw is True
            assert forced_source == "forced_by_env"
        finally:
            if old_profile is None:
                os.environ.pop("REFERENCE_STYLE_PROFILE", None)
            else:
                os.environ["REFERENCE_STYLE_PROFILE"] = old_profile
            if old_force is None:
                os.environ.pop("FORCE_DEFAULT_TITLEBLOCK", None)
            else:
                os.environ["FORCE_DEFAULT_TITLEBLOCK"] = old_force


def test_generator_records_reference_sheet_artifact_cleanup_policy() -> None:
    source = GENERATOR_PATH.read_text(encoding="utf-8")

    assert "reference_sheet_template_policy" in source
    assert "strip_default_template_artifacts" in source
    assert "reference style -> create from DRWDOT, then strip default sheet artifacts" in source
    assert "reference_sheet_artifact_cleanup" in source


def test_generator_maps_reference_layout_centers_to_view_slots() -> None:
    module = _load_generator()
    old_profile = os.environ.get("REFERENCE_STYLE_PROFILE")
    with TemporaryDirectory() as tmp:
        profile_path = Path(tmp) / "lb26001_reference_style_profile.json"
        profile_path.write_text(json.dumps(_profile(), ensure_ascii=False), encoding="utf-8")
        os.environ["REFERENCE_STYLE_PROFILE"] = str(profile_path)
        try:
            centers_006, source_006 = module._reference_style_layout_centers(Path(tmp) / "LB26001-A-04-006.SLDPRT")
            centers_009, _ = module._reference_style_layout_centers(Path(tmp) / "LB26001-A-04-009.SLDPRT")
            centers_015, _ = module._reference_style_layout_centers(Path(tmp) / "LB26001-A-04-015.SLDPRT")
        finally:
            if old_profile is None:
                os.environ.pop("REFERENCE_STYLE_PROFILE", None)
            else:
                os.environ["REFERENCE_STYLE_PROFILE"] = old_profile

    assert source_006.endswith("lb26001_reference_style_profile.json")
    assert set(centers_006) == {"front", "top", "right", "iso"}
    assert centers_006["top"][1] < centers_006["front"][1]
    assert centers_006["right"][0] > centers_006["front"][0]
    assert centers_006["iso"][0] > centers_006["front"][0]
    assert set(centers_009) == {"front", "top", "right"}
    assert centers_009["top"][1] < centers_009["front"][1]
    assert centers_009["right"][0] > centers_009["front"][0]
    assert set(centers_015) == {"front", "top"}
    assert centers_015["top"][1] < centers_015["front"][1]


def test_generator_dimension_insert_plan_scales_to_reference_floor() -> None:
    module = _load_generator()
    outline = (0.04, 0.12, 0.18, 0.17)

    assert module._dimension_attempt_target(8, 12) >= 6
    assert module._dimension_attempt_target(0, 25) >= 25
    assert module._dimension_attempt_target(25, 25) == 0
    assert module._effective_dimension_floor(0) == 5
    assert module._effective_dimension_floor(2) == 2
    assert module._reference_dimension_attempt_target(0, 0) >= 5
    assert module._reference_dimension_attempt_target(0, 2) == 2
    assert module._reference_dimension_attempt_target(0, 4) == 4
    assert module._reference_dimension_attempt_target(0, 12) >= 12
    assert module._reference_dimension_attempt_target(8, 12) >= 6
    assert module._needs_dimension_sidecar(True, 12, 12) is False
    assert module._needs_dimension_sidecar(True, 11, 12) is True
    assert module._needs_dimension_sidecar(False, 12, 12) is True
    assert module._dimension_sidecar_mode_for_reference_intent(True, False) == {
        "run_sidecar": True,
        "diagnostic_only": False,
        "reason": "generic_dimension_recovery_allowed",
    }
    assert module._dimension_sidecar_mode_for_reference_intent(True, True) == {
        "run_sidecar": False,
        "diagnostic_only": True,
        "reason": "reference_intent_sidecar_not_allowed_for_acceptance",
    }
    assert module._dimension_sidecar_mode_for_reference_intent(False, True)["reason"] == "display_dim_floor_satisfied"
    assert module._reference_dim_floor_gap(12, 12) is None
    assert module._reference_dim_floor_gap(14, 12) is None
    assert module._reference_dim_floor_gap(8, 12) == {
        "gap": 4,
        "reference_display_dim_floor": 12,
        "generated_display_dim_count": 8,
    }

    plan_006 = module._dimension_insert_plan_for_outline(
        outline,
        module._reference_dimension_attempt_target(0, 12),
    )
    plan_008 = module._dimension_insert_plan_for_outline(
        outline,
        module._reference_dimension_attempt_target(0, 2),
    )
    plan_009 = module._dimension_insert_plan_for_outline(
        outline,
        module._reference_dimension_attempt_target(0, 4),
    )
    plan_015 = module._dimension_insert_plan_for_outline(
        outline,
        module._reference_dimension_attempt_target(0, 14),
    )
    plan_022 = module._dimension_insert_plan_for_outline(
        outline,
        module._reference_dimension_attempt_target(0, 25),
    )

    assert len(plan_006) >= 12
    assert len(plan_008) == 2
    assert len(plan_009) == 4
    assert len(plan_015) >= 14
    assert len(plan_022) >= 25
    assert {item[0] for item in plan_022} == {"horizontal", "vertical", "diagonal"}
    assert all(len(item) == 3 for item in plan_022)


def test_generator_force_dimension_plan_only_chases_floor_gap() -> None:
    module = _load_generator()
    outline = (0.04, 0.12, 0.18, 0.17)

    plan_006_gap = module._force_dimension_insert_plan(outline, 8, 12)
    plan_006_reference_intent_gap = module._force_dimension_insert_plan(
        outline,
        8,
        12,
        allow_diagonal=False,
    )
    plan_006_done = module._force_dimension_insert_plan(outline, 12, 12)
    plan_008_gap = module._force_dimension_insert_plan(outline, 0, 2)

    assert len(plan_006_gap) >= 4
    assert {item[0] for item in plan_006_gap} <= {"horizontal", "vertical", "diagonal"}
    assert len(plan_006_reference_intent_gap) >= 4
    assert {item[0] for item in plan_006_reference_intent_gap} <= {"horizontal", "vertical"}
    assert plan_006_done == []
    assert len(plan_008_gap) == 2


def test_generator_skips_bulk_model_dimensions_for_006_reference_intent_contract() -> None:
    module = _load_generator()
    blueprint = {
        "base": "LB26001-A-04-006",
        "dimension_plan": {
            "source": "reference_intent_dimension_plan_v4_2",
            "required_display_dim_count": 12,
            "dimension_targets": [
                {
                    "key": f"target_{idx}",
                    "avoid_generic_model_annotation": True,
                }
                for idx in range(12)
            ],
            "view_dimension_quotas": {"front": 3, "top": 6, "right": 3},
            "reasons": [
                "reference_intent_dimension_plan_path_attached",
                "explicit_dimension_targets_replace_generic_autodimension_acceptance",
            ],
        },
    }
    generic_blueprint = {
        "base": "LB26001-A-04-010",
        "dimension_plan": {
            "source": "reference_dimension_profile",
            "required_display_dim_count": 12,
            "dimension_targets": [
                {
                    "key": "overall_length",
                    "avoid_generic_model_annotation": False,
                }
            ],
        },
    }

    assert module._v4_should_skip_generic_model_dimension_import(blueprint, 12) is True
    assert module._v4_should_disable_reference_autodimension(blueprint, 12) is True
    assert module._v4_should_skip_generic_model_dimension_import(generic_blueprint, 12) is False
    assert module._v4_should_disable_reference_autodimension(generic_blueprint, 12) is False


def test_generator_preserves_reference_intent_view_names_and_add_methods() -> None:
    module = _load_generator()
    with TemporaryDirectory() as tmp:
        plan_path = Path(tmp) / "reference_intent_dimension_plan_006.json"
        ui_correction_path = Path(tmp) / "lb26001_006_ui_correction_evidence.json"
        plan_path.write_text(
            json.dumps(
                {
                    "base": "LB26001-A-04-006",
                    "required_display_dim_count": 12,
                    "reference_view_slots": {
                        "front": {"reference_view_name": "工程图视图1"},
                        "right": {"reference_view_name": "工程图视图2"},
                        "top": {"reference_view_name": "工程图视图3"},
                    },
                    "dimensions": [
                        {
                            "key": "hole_diameter",
                            "group": "hole_locations",
                            "target_view": "top",
                            "expected_type": "diameter",
                            "expected_add_method": "AddDiameterDimension2",
                            "priority": 30,
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        ui_correction_path.write_text(
            json.dumps(
                {
                    "schema": "sw_drawing_studio.lb26001_006_ui_correction_evidence.v4_2",
                    "base": "LB26001-A-04-006",
                    "comparison_image": "006_reference_vs_generated.png",
                    "failed_visual_checklist_items": ["view_layout", "display_dimensions"],
                    "latest_manual_findings": ["006 still fails UI screenshot comparison."],
                    "latest_manual_required_correction": "Repair 006 from UI screenshot evidence.",
                    "application_ui_screenshot_is_final_gate": True,
                    "api_is_not_final_judgement": True,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        old_plan = os.environ.get("REFERENCE_INTENT_DIMENSION_PLAN_PATH")
        old_ui_correction = os.environ.get("LB26001_006_UI_CORRECTION_EVIDENCE_PATH")
        try:
            os.environ["REFERENCE_INTENT_DIMENSION_PLAN_PATH"] = str(plan_path)
            os.environ["LB26001_006_UI_CORRECTION_EVIDENCE_PATH"] = str(ui_correction_path)
            warnings = []
            blueprint = module._v4_apply_reference_intent_plan_path(
                {"base": "LB26001-A-04-006"},
                warnings_box=warnings,
            )
        finally:
            if old_plan is None:
                os.environ.pop("REFERENCE_INTENT_DIMENSION_PLAN_PATH", None)
            else:
                os.environ["REFERENCE_INTENT_DIMENSION_PLAN_PATH"] = old_plan
            if old_ui_correction is None:
                os.environ.pop("LB26001_006_UI_CORRECTION_EVIDENCE_PATH", None)
            else:
                os.environ["LB26001_006_UI_CORRECTION_EVIDENCE_PATH"] = old_ui_correction

    dimension_plan = blueprint["dimension_plan"]
    assert dimension_plan["reference_view_slots"]["top"]["reference_view_name"] == "工程图视图3"
    assert dimension_plan["dimension_targets"][0]["expected_add_method"] == "AddDiameterDimension2"
    assert dimension_plan["ui_correction_evidence"]["comparison_image"] == "006_reference_vs_generated.png"
    assert dimension_plan["ui_correction_evidence"]["failed_visual_checklist_items"] == [
        "view_layout",
        "display_dimensions",
    ]
    assert "lb26001_006_ui_correction_evidence_attached" in dimension_plan["reasons"]
    assert blueprint["source_inputs"]["lb26001_006_ui_correction_evidence_path"] == str(ui_correction_path)
    assert any(item.get("code") == "lb26001_006_ui_correction_evidence_attached" for item in warnings)
    assert module._reference_intent_view_name_candidates("top", dimension_plan)[0] == "工程图视图3"
    assert "Drawing View 3" in module._reference_intent_view_name_candidates("top", dimension_plan)


def test_generator_attaches_reference_callout_review_plan_for_006_ui_closure() -> None:
    module = _load_generator()
    with TemporaryDirectory() as tmp:
        plan_path = Path(tmp) / "reference_intent_dimension_plan_006.json"
        ui_defect_path = Path(tmp) / "lb26001_006_ui_defect_buckets_v4_4.json"
        plan_path.write_text(
            json.dumps(
                {
                    "base": "LB26001-A-04-006",
                    "required_display_dim_count": 12,
                    "dimensions": [
                        {
                            "key": "hole_diameter",
                            "target_view": "top",
                            "expected_type": "diameter",
                            "reference_value": {"hole_count": 4, "diameter_mm": 3.3, "thread": "M4-6H"},
                            "source_reference_evidence": {
                                "source_text": "4-⌀3.3 完全贯穿; M4-6H 完全贯穿",
                            },
                            "expected_add_method": "AddDiameterDimension2",
                        }
                    ],
                    "reference_callouts": [
                        {
                            "key": "thread_callout_m4_6h",
                            "target_view": "top",
                            "expected_type": "thread_callout",
                            "reference_value": "M4-6H 完全贯穿",
                            "is_manufacturing_dimension": True,
                        },
                        {
                            "key": "surface_finish_rest_3_2",
                            "target_view": "sheet_notes",
                            "expected_type": "surface_finish_callout",
                            "reference_value": "3.2 其余",
                            "is_manufacturing_dimension": True,
                        },
                        {
                            "key": "radius_callout",
                            "target_view": "front/top/right",
                            "expected_type": "radius_callout",
                            "reference_value": None,
                        },
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        ui_defect_path.write_text(
            json.dumps(
                {
                    "base": "LB26001-A-04-006",
                    "status": "blocked_by_solidworks_readiness",
                    "pass": False,
                    "api_only_acceptance_allowed": False,
                    "application_ui_screenshot_is_final_gate": True,
                    "expansion_allowed_now": False,
                    "active_buckets": ["callout_missing", "dimension_visual_overdense"],
                    "screenshot_visual_observations": [
                        {
                            "bucket": "dimension_visual_overdense",
                            "observation_key": "dimension_visual_overdense_application_ui_screenshot_observation",
                            "source": "application_drawing_review_ui_screenshot",
                            "source_paths": ["006_ui_visual_review.png"],
                            "visual_check": "display_dimensions",
                            "visual_check_pass": False,
                            "manual_note": "Generated sheet remains visually over-dense.",
                            "visual_fact": "The generated sheet visibly keeps too many DisplayDims.",
                            "reference_expectation": "The reference drawing uses a sparse 12-target dimension set.",
                            "generated_failure": "Extra generic dimensions make the output AutoDimension-like.",
                            "repair_signal": "Keep only reference-intent manufacturing targets.",
                            "supports_active_bucket": True,
                            "next_screenshot_check_required": True,
                            "api_or_displaydim_metric_alone_can_close": False,
                        },
                        {
                            "bucket": "callout_missing",
                            "observation_key": "callout_missing_application_ui_screenshot_observation",
                            "source": "application_drawing_review_ui_screenshot",
                            "source_paths": ["006_ui_visual_review.png"],
                            "visual_check": "reference_match",
                            "visual_check_pass": None,
                            "manual_note": "Callout bucket must be checked in the next screenshot.",
                            "visual_fact": "The screenshot does not close callout review.",
                            "reference_expectation": "Callouts must be checked visually.",
                            "generated_failure": "API metrics cannot close callout presence.",
                            "repair_signal": "Require a reference_callout_checklist.",
                            "supports_active_bucket": False,
                            "next_screenshot_check_required": True,
                            "api_or_displaydim_metric_alone_can_close": False,
                        },
                    ],
                    "bucket_closure_contract": [
                        {
                            "bucket": "dimension_visual_overdense",
                            "source_failure_evidence": ["application_drawing_review_ui_screenshot"],
                            "repair_inputs": ["lb26001_006_ui_defect_buckets_v4_4"],
                            "implementation_guard_keys": ["generator.physical_displaydim_dedupe"],
                            "post_rerun_required_evidence": [
                                "application_drawing_review_ui_screenshot",
                                "manual_visual_judgement",
                            ],
                            "ui_review_pass_condition": "DisplayDim set must match reference intent.",
                            "api_or_displaydim_metric_alone_can_close": False,
                        },
                        {
                            "bucket": "callout_missing",
                            "source_failure_evidence": ["application_drawing_review_ui_screenshot"],
                            "repair_inputs": ["reference_intent_dimension_plan_006"],
                            "implementation_guard_keys": ["generator.reference_callout_review_plan"],
                            "post_rerun_required_evidence": [
                                "application_drawing_review_ui_screenshot",
                                "manual_visual_judgement",
                                "reference_callout_checklist",
                            ],
                            "ui_review_pass_condition": "Callout checklist must prove required callouts.",
                            "api_or_displaydim_metric_alone_can_close": False,
                            "required_callout_keys": ["thread_callout_m4_6h", "surface_finish_rest_3_2"],
                            "absence_check_keys": ["radius_callout"],
                            "reference_callout_checklist_required": True,
                        },
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        old_plan = os.environ.get("REFERENCE_INTENT_DIMENSION_PLAN_PATH")
        old_ui_defects = os.environ.get("LB26001_006_UI_DEFECT_BUCKETS_PATH")
        try:
            os.environ["REFERENCE_INTENT_DIMENSION_PLAN_PATH"] = str(plan_path)
            os.environ["LB26001_006_UI_DEFECT_BUCKETS_PATH"] = str(ui_defect_path)
            blueprint = module._v4_apply_reference_intent_plan_path({"base": "LB26001-A-04-006"})
        finally:
            if old_plan is None:
                os.environ.pop("REFERENCE_INTENT_DIMENSION_PLAN_PATH", None)
            else:
                os.environ["REFERENCE_INTENT_DIMENSION_PLAN_PATH"] = old_plan
            if old_ui_defects is None:
                os.environ.pop("LB26001_006_UI_DEFECT_BUCKETS_PATH", None)
            else:
                os.environ["LB26001_006_UI_DEFECT_BUCKETS_PATH"] = old_ui_defects

    callout_plan = blueprint["dimension_plan"]["reference_callout_review_plan"]
    constraints = blueprint["dimension_plan"]["visual_defect_constraints"]
    closure_contract = blueprint["dimension_plan"]["ui_defect_bucket_closure_contract"]
    screenshot_observations = blueprint["dimension_plan"]["ui_defect_screenshot_visual_observations"]
    assert callout_plan["schema"] == "sw_drawing_studio.reference_callout_review_plan.v4_4"
    assert callout_plan["notes_do_not_count_as_display_dim"] is True
    assert callout_plan["application_ui_screenshot_required"] is True
    assert set(callout_plan["required_keys"]) == {
        "hole_diameter",
        "thread_callout_m4_6h",
        "surface_finish_rest_3_2",
    }
    assert callout_plan["absence_check_keys"] == ["radius_callout"]
    assert constraints["callout_presence_recheck_required"] is True
    assert constraints["reference_callout_review_required_keys"] == callout_plan["required_keys"]
    assert constraints["reference_callout_absence_check_keys"] == ["radius_callout"]
    assert [item["bucket"] for item in closure_contract] == [
        "dimension_visual_overdense",
        "callout_missing",
    ]
    assert constraints["bucket_closure_contract_buckets"] == [
        "dimension_visual_overdense",
        "callout_missing",
    ]
    assert constraints["ui_review_bucket_pass_conditions"]["dimension_visual_overdense"] == (
        "DisplayDim set must match reference intent."
    )
    assert constraints["ui_review_bucket_pass_conditions"]["callout_missing"] == (
        "Callout checklist must prove required callouts."
    )
    assert constraints["api_or_displaydim_metric_alone_can_close"] is False
    assert [item["bucket"] for item in screenshot_observations] == [
        "dimension_visual_overdense",
        "callout_missing",
    ]
    assert screenshot_observations[0]["source"] == "application_drawing_review_ui_screenshot"
    assert screenshot_observations[0]["visual_check_pass"] is False
    assert screenshot_observations[0]["api_or_displaydim_metric_alone_can_close"] is False
    assert constraints["screenshot_visual_observation_buckets"] == [
        "dimension_visual_overdense",
        "callout_missing",
    ]
    assert constraints["screenshot_visual_observations"][0]["generated_failure"] == (
        "Extra generic dimensions make the output AutoDimension-like."
    )
    assert closure_contract[1]["reference_callout_checklist_required"] is True
    assert closure_contract[1]["required_callout_keys"] == [
        "thread_callout_m4_6h",
        "surface_finish_rest_3_2",
    ]
    assert "ui_defect_bucket_reference_callout_review_plan" in blueprint["dimension_plan"]["reasons"]
    assert "ui_defect_bucket_closure_contract" in blueprint["dimension_plan"]["reasons"]
    assert "ui_defect_screenshot_visual_observations" in blueprint["dimension_plan"]["reasons"]


def test_generator_reference_autodim_and_prune_policy_is_bounded() -> None:
    module = _load_generator()

    assert module._reference_display_dim_cap(0) == 0
    assert module._reference_display_dim_cap(2) == 4
    assert module._reference_display_dim_cap(4) == 6
    assert module._reference_display_dim_cap(14) == 21
    assert module._reference_display_dim_cap(25) == 38
    assert module._reference_display_dim_cap(12, part_class="long_thin") == 14
    assert module._reference_display_dim_cap(25, part_class="long_thin") == 27
    assert module._reference_autodim_call_budget(2) == 1
    assert module._reference_autodim_call_budget(4) == 2
    assert module._reference_autodim_call_budget(8) == 2
    assert module._reference_autodim_call_budget(25) == 2
    assert module._reference_autodim_call_budget(12, part_class="long_thin") == 3


def test_generator_source_blocks_reference_intent_autodim_after_ui_failure() -> None:
    source = GENERATOR_PATH.read_text(encoding="utf-8")

    assert "def _v4_should_disable_reference_autodimension" in source
    assert "_disable_reference_autodimension" in source
    assert "def _run_reference_intent_explicit_display_dims" in source
    assert "reference_intent_explicit_display_dims" in source
    assert "GetVisibleEntities2" in source
    assert "visible_entities2_select4_adddimension2" in source
    assert "nearest_layout_center" in source
    assert "AddDiameterDimension2" in source
    assert "expected_add_method" in source
    assert "reference_view_name_candidate_select" in source
    assert "_drawing_doc_getviews_candidates" in source
    assert "live_getviews_scan" in source
    assert "reference_intent_created_views_refreshed" in source
    assert "post_layout_reopen_getviews_refresh" in source
    assert "post_layout_current_drawing_doc_refreshed" in source
    assert "post_layout_reopen_view_materialization_probe" in source
    assert "post_layout_reopen_view_materialization_fallback_open_options" in source
    assert '"to_open_options": 1' in source
    assert "post_layout_reopen_view_materialization_before_rebind" in source
    assert "post_layout_live_view_recovery_failed" in source
    assert "post_layout_reopen_force_rebuild_wait" in source
    assert "refresh_actions" in source
    assert '"record_count": len(records_)' in source
    assert "current_doc_view_count" in source
    assert "getviews_count" in source
    assert "current_sheet_getviews_count" in source
    assert "def _reference_intent_slot_rebind_summary" in source
    assert "slot_rebind_summary" in source
    assert "nearest_candidates" in source
    assert "unbound_slots" in source
    assert "reference_intent_floor_guard_no_delete" in source
    assert '"delete_plan": []' in source
    assert '"deleted_items": []' in source
    assert "target_match" in source
    assert "reference_intent_target_coverage" in source
    assert "persisted_after_reopen" in source
    assert "reference_intent_autodimension_disabled" in source
    assert "post_layout_reference_intent_autodimension_disabled" in source
    assert "reference_intent_dimension_sidecar_diagnostic_only" in source
    assert "reference_intent_sidecar_not_allowed_for_acceptance" in source
    assert "dimension_sidecar_mode" in source
    assert "post_saveas_reopen_prune_guard" in source
    assert "post_prune_dim_guard" in source
    assert "target_coverage_after_guard" in source
    assert "post_prune_reference_intent_guard_still_blocked" in source
    assert "post_layout_after_prune" in source
    assert "post_layout_prune_guard" in source
    assert "post_layout_prune_guard_explicit_display_dims" in source
    assert "post_layout_prune_guard_after_arrange" in source
    assert "post_layout_prune_guard_arrange_guard_explicit_display_dims" in source
    assert "post_layout_prune_guard_after_arrange_still_blocked" in source
    assert "post_layout_final_exact_prune" in source
    assert "post_layout_final_exact_prune_failed" in source
    assert "_v4_blueprint_layout_outlines" in source
    assert "_reference_outline_scale_hint" in source
    assert "target_outlines=_layout_outlines_for_solver" in source
    assert "target_outline_tolerance=0.28" in source
    assert "start_scale=chosen" in source
    assert "post_layout_prune_guard_still_blocked" in source
    assert "application_ui_screenshot_visual_acceptance_failed_generic_autodimension" in source
    assert "reference_intent_target_coverage_stage_delta" in source
    assert "_reference_intent_target_covered" in source
    assert "placement_lane" in source
    assert "prune_protection_policy" in source
    assert "reference_intent_target_protected_no_delete" in source
    assert "reference_intent_best_target_displaydim_protected" in source
    assert "reference_intent_exact_target_cap" in source
    assert "generator_top_view_local_reference_lanes" in source
    assert "physical_displaydim_dedupe" in source
    assert "persisted_real_outlines_recovered_view" in source
    assert "created_but_target_not_covered" in source
    assert "expected_add_method" in source
    assert "add_method_matches_expected" in source
    assert '"target_key": target_key' in source
    assert '"view_slot": slot' in source
    assert '"selected_entity": entity_identity' in source
    assert '"display_dim_count_before": before_one' in source
    assert '"display_dim_count_after": after_one' in source
    assert "target_covered_after_attempt" in source
    assert "_reference_intent_entity_rank" in source
    assert '"entity_rank": list(_reference_intent_entity_rank' in source
    assert "post_layout_reference_intent_final_blocked" in source


def test_generator_scores_long_thin_display_dims_by_reference_intent() -> None:
    module = _load_generator()
    dimension_plan = {
        "dimension_intent_groups": [
            {"key": "overall_envelope", "slots": ["front", "top"]},
            {"key": "hole_positions", "slots": ["top"]},
            {"key": "projected_view_size", "slots": ["right"]},
        ],
        "view_dimension_quotas": {"front": 4, "top": 6, "right": 2},
        "dimension_targets": [
            {
                "key": "left_end_offset",
                "group": "end_offsets",
                "target_view": "front",
                "expected_type": "vertical",
                "preferred_side": "left",
                "priority": 4,
            },
            {
                "key": "hole_pitch",
                "group": "hole_locations",
                "target_view": "top",
                "expected_type": "horizontal",
                "preferred_side": "above",
                "priority": 9,
            },
            {
                "key": "projection_view_height",
                "group": "projected_view_size",
                "target_view": "right",
                "expected_type": "vertical",
                "preferred_side": "right",
                "priority": 11,
            },
        ],
    }
    layout_plan = {
        "sheet_size": {"width": 0.297, "height": 0.21},
        "views": [
            {"slot": "front", "box_norm": [0.16, 0.77, 0.58, 0.84]},
            {"slot": "top", "box_norm": [0.16, 0.56, 0.58, 0.63]},
            {"slot": "right", "box_norm": [0.70, 0.77, 0.75, 0.84]},
            {"slot": "iso", "box_norm": [0.71, 0.39, 0.89, 0.56]},
        ],
    }
    top_outline = (0.0483, 0.1177, 0.1717, 0.1321)
    front_outline = (0.0483, 0.1621, 0.1717, 0.1770)

    top_hole_lane = module._score_display_dim_for_reference_intent(
        {
            "slot": "top",
            "_slot": "top",
            "view_outline": top_outline,
            "position": [0.1100, 0.1450],
        },
        layout_plan=layout_plan,
        dimension_plan=dimension_plan,
    )
    top_inside = module._score_display_dim_for_reference_intent(
        {
            "slot": "top",
            "_slot": "top",
            "view_outline": top_outline,
            "position": [0.1100, 0.1240],
        },
        layout_plan=layout_plan,
        dimension_plan=dimension_plan,
    )
    front_end = module._score_display_dim_for_reference_intent(
        {
            "slot": "front",
            "_slot": "front",
            "view_outline": front_outline,
            "position": [0.0410, 0.1690],
        },
        layout_plan=layout_plan,
        dimension_plan=dimension_plan,
    )
    iso_dim = module._score_display_dim_for_reference_intent(
        {
            "slot": "iso",
            "_slot": "iso",
            "view_outline": (0.2130, 0.0830, 0.2640, 0.1180),
            "position": [0.2750, 0.1100],
        },
        layout_plan=layout_plan,
        dimension_plan=dimension_plan,
    )

    assert top_hole_lane["score"] > top_inside["score"]
    assert front_end["score"] > top_inside["score"]
    assert top_hole_lane["score"] > iso_dim["score"]
    assert "hole_position_lane" in top_hole_lane["reason"]
    assert top_hole_lane["target_match"]["target_key"] == "hole_pitch"
    assert top_hole_lane["target_match"]["target_group"] == "hole_locations"
    assert front_end["target_match"]["target_key"] == "left_end_offset"


def test_generator_reports_reference_intent_target_coverage_from_display_dims() -> None:
    module = _load_generator()
    dimension_plan = {
        "dimension_intent_groups": [
            {"key": "end_offsets", "slots": ["front"]},
            {"key": "hole_locations", "slots": ["top"]},
            {"key": "projected_view_size", "slots": ["right"]},
        ],
        "view_dimension_quotas": {"front": 3, "top": 6, "right": 3},
        "dimension_targets": [
            {
                "key": "left_end_offset",
                "group": "end_offsets",
                "target_view": "front",
                "expected_type": "vertical",
                "preferred_side": "left",
                "priority": 4,
            },
            {
                "key": "hole_pitch",
                "group": "hole_locations",
                "target_view": "top",
                "expected_type": "horizontal",
                "preferred_side": "above",
                "priority": 9,
            },
            {
                "key": "projection_view_height",
                "group": "projected_view_size",
                "target_view": "right",
                "expected_type": "vertical",
                "preferred_side": "right",
                "priority": 11,
            },
        ],
    }
    items = [
        {
            "slot": "top",
            "_slot": "top",
            "view_outline": (0.0483, 0.1177, 0.1717, 0.1321),
            "position": [0.1340, 0.1450],
            "view": "top_view",
            "source": "unit",
        },
        {
            "slot": "front",
            "_slot": "front",
            "view_outline": (0.0483, 0.1621, 0.1717, 0.1770),
            "position": [0.0410, 0.1690],
            "view": "front_view",
            "source": "unit",
        },
    ]

    coverage = module._reference_intent_target_coverage_from_items(
        items,
        dimension_plan=dimension_plan,
    )

    assert coverage["target_count"] == 3
    assert coverage["covered_count"] == 2
    assert set(coverage["covered_target_keys"]) == {"hole_pitch", "left_end_offset"}
    assert coverage["missing_target_keys"] == ["projection_view_height"]
    target_map = {item["target_key"]: item for item in coverage["target_results"]}
    assert target_map["hole_pitch"]["matched_count"] == 1
    assert target_map["hole_pitch"]["persisted_after_reopen"] is True
    assert target_map["projection_view_height"]["persisted_after_reopen"] is False


def test_generator_strict_ui_defect_target_match_rejects_weak_autodim_survivors() -> None:
    module = _load_generator()
    dimension_plan = {
        "visual_defect_constraints": {
            "reject_generic_autodim_survivors": True,
            "compact_local_lanes_required": True,
            "callout_presence_recheck_required": True,
        },
        "dimension_targets": [
            {
                "key": "hole_pitch",
                "group": "hole_locations",
                "target_view": "top",
                "expected_type": "linear_horizontal",
                "preferred_side": "above",
                "priority": 9,
                "placement_lane": {"station": 0.70},
            },
            {
                "key": "hole_y_location",
                "group": "hole_locations",
                "target_view": "top",
                "expected_type": "linear_vertical",
                "preferred_side": "callout_right",
                "priority": 32,
                "placement_lane": {"station": 0.46},
            },
        ],
    }
    outline = (0.0, 0.0, 10.0, 1.0)
    weak_items = [
        {
            "_slot": "top",
            "slot": "top",
            "view_outline": outline,
            "position": [7.0, -0.30],
            "view": "top_view",
            "source": "wrong_side_bottom",
        },
        {
            "_slot": "top",
            "slot": "top",
            "view_outline": outline,
            "position": [1.0, 1.30],
            "view": "top_view",
            "source": "far_station_top",
        },
        {
            "_slot": "top",
            "slot": "top",
            "view_outline": outline,
            "position": [10.25, 0.46],
            "view": "top_view",
            "source": "right_vertical_callout",
        },
    ]

    weak_coverage = module._reference_intent_target_coverage_from_items(
        weak_items,
        dimension_plan=dimension_plan,
    )

    assert weak_coverage["covered_target_keys"] == ["hole_y_location"]
    assert weak_coverage["missing_target_keys"] == ["hole_pitch"]
    assert weak_coverage["matched_items"][0]["target_key"] == "hole_y_location"

    repaired_coverage = module._reference_intent_target_coverage_from_items(
        weak_items
        + [
            {
                "_slot": "top",
                "slot": "top",
                "view_outline": outline,
                "position": [7.0, 1.30],
                "view": "top_view",
                "source": "correct_top_pitch",
            }
        ],
        dimension_plan=dimension_plan,
    )

    assert set(repaired_coverage["covered_target_keys"]) == {"hole_pitch", "hole_y_location"}
    pitch_result = {
        item["target_key"]: item for item in repaired_coverage["target_results"]
    }["hole_pitch"]
    assert pitch_result["best_display_dim"]["target_match"]["strict_ui_defect_match"] is True
    assert pitch_result["best_display_dim"]["target_match"]["side_matches_preferred"] is True


def test_generator_deduplicates_physical_displaydims_from_multiple_enumerators() -> None:
    module = _load_generator()
    items = [
        {
            "view": "工程图视图2",
            "annotation_name": "D1@工程图视图2",
            "position": [0.12, 0.15],
            "view_outline": [0.04, 0.11, 0.17, 0.13],
            "source": "GetDisplayDimensions",
            "display_dim": object(),
        },
        {
            "view": "工程图视图2",
            "annotation_name": "D1@工程图视图2",
            "position": [0.12, 0.15],
            "view_outline": [0.04, 0.11, 0.17, 0.13],
            "source": "GetFirstDisplayDimension",
            "display_dim": object(),
        },
        {
            "view": "工程图视图2",
            "annotation_name": "",
            "position": [0.130001, 0.150001],
            "view_outline": [0.04, 0.11, 0.17, 0.13],
            "source": "GetDisplayDimensions",
        },
    ]

    deduped = module._dedupe_display_dim_annotations(items)

    assert len(deduped) == 2
    assert deduped[0]["source"] == "GetDisplayDimensions+GetFirstDisplayDimension"
    assert deduped[0]["duplicate_sources"][0]["source"] == "GetFirstDisplayDimension"


def test_generator_prune_dedupes_reference_intent_equivalent_wrappers_before_delete() -> None:
    module = _load_generator()

    class FakeDoc:
        def ClearSelection2(self, *_args):
            return True

        def ForceRebuild3(self, *_args):
            return True

    duplicate_a = object()
    duplicate_b = object()
    pitch_ann = object()
    live_items = [
        {
            "annotation": duplicate_a,
            "slot": "front",
            "_slot": "front",
            "view": "front",
            "source": "GetDisplayDimensions",
            "view_outline": [0.0, 0.0, 1.0, 1.0],
            "position": [0.50, 1.012],
        },
        {
            "annotation": duplicate_b,
            "slot": "front",
            "_slot": "front",
            "view": "front",
            "source": "GetFirstDisplayDimension",
            "view_outline": [0.0, 0.0, 1.0, 1.0],
            "position": [0.50, 1.012],
        },
        {
            "annotation": pitch_ann,
            "slot": "top",
            "_slot": "top",
            "view": "top",
            "source": "GetDisplayDimensions",
            "view_outline": [0.0, 0.0, 1.0, 1.0],
            "position": [0.70, 1.012],
        },
    ]
    dimension_plan = {
        "dimension_intent_groups": [{"key": "overall"}, {"key": "hole_locations"}],
        "visual_defect_constraints": {
            "reject_generic_autodim_survivors": True,
            "compact_local_lanes_required": True,
        },
        "dimension_targets": [
            {
                "key": "overall_length",
                "target_view": "front",
                "expected_type": "linear_horizontal",
                "preferred_side": "above",
                "priority": 1,
            },
            {
                "key": "hole_pitch",
                "target_view": "top",
                "expected_type": "linear_horizontal",
                "preferred_side": "above",
                "priority": 9,
            },
        ],
    }
    delete_calls = {"count": 0}
    original_collect = module._display_dim_annotations_in_doc
    original_delete = module._delete_selected_annotation
    try:
        module._display_dim_annotations_in_doc = lambda _doc: list(live_items)

        def fake_delete(_doc):
            delete_calls["count"] += 1
            return True, "unit.Delete"

        module._delete_selected_annotation = fake_delete
        result = module._prune_display_dims_to_cap(
            FakeDoc(),
            2,
            dimension_plan=dimension_plan,
            reference_dim_floor=2,
            strict_reference_intent=True,
        )
    finally:
        module._display_dim_annotations_in_doc = original_collect
        module._delete_selected_annotation = original_delete

    assert result["enumerated_before"] == 3
    assert result["before"] == 2
    assert result["deleted"] == 0
    assert delete_calls["count"] == 0
    assert result["reference_intent_delete_equivalence_dedupe"]["merged_count"] == 1
    assert result["skip_reason"] == "reference_intent_effective_cap_guard_no_delete"
    assert result["success"] is True


def test_generator_prioritizes_missing_reference_intent_targets_for_repair() -> None:
    module = _load_generator()
    targets = [
        {"key": "overall_length", "priority": 1},
        {"key": "hole_pitch", "priority": 9},
        {"key": "projection_view_height", "priority": 11},
    ]
    coverage = {"missing_target_keys": ["projection_view_height", "hole_pitch"]}

    ordered = module._reference_intent_targets_for_repair(targets, coverage)

    assert [item["key"] for item in ordered] == [
        "hole_pitch",
        "projection_view_height",
        "overall_length",
    ]
    assert module._reference_intent_missing_target_keys(coverage) == {"hole_pitch", "projection_view_height"}


def test_generator_checks_reference_intent_target_coverage_truthfully() -> None:
    module = _load_generator()

    assert module._reference_intent_target_covered(
        {"covered_target_keys": ["hole_pitch"], "missing_target_keys": []},
        "hole_pitch",
    ) is True
    assert module._reference_intent_target_covered(
        {"covered_target_keys": ["hole_pitch"], "missing_target_keys": ["hole_pitch"]},
        "hole_pitch",
    ) is False
    assert module._reference_intent_target_covered(
        {"target_results": [{"target_key": "projection_view_height", "matched_count": 1}]},
        "projection_view_height",
    ) is True
    assert module._reference_intent_target_covered(
        {"target_results": [{"target_key": "projection_view_height", "matched_count": 0}]},
        "projection_view_height",
    ) is False


def test_generator_ranks_reference_intent_entities_by_target_type() -> None:
    module = _load_generator()

    assert module._reference_intent_entity_rank("diameter", 2) < module._reference_intent_entity_rank("diameter", 1)
    assert module._reference_intent_entity_rank("linear_horizontal", 1) < module._reference_intent_entity_rank("linear_horizontal", 2)
    assert module._reference_intent_entity_rank("linear_vertical", -1)[1] == 999


def test_generator_uses_reference_intent_placement_lane_station() -> None:
    module = _load_generator()

    assert module._reference_intent_target_fraction({
        "key": "hole_pitch",
        "placement_lane": {"station": 0.73},
    }) == 0.73
    assert module._reference_intent_target_fraction({
        "key": "hole_pitch",
        "placement_lane": {"station": 1.7},
    }) == 1.0
    assert module._reference_intent_target_fraction({"key": "hole_pitch"}) == 0.70


def test_generator_post_layout_repair_triggers_on_missing_targets_even_when_floor_met() -> None:
    module = _load_generator()

    assert module._reference_intent_post_layout_repair_reason(
        12,
        12,
        {"covered_target_keys": ["overall_length"], "missing_target_keys": ["hole_pitch"]},
    ) == "reference_intent_targets_missing"
    assert module._reference_intent_post_layout_repair_reason(
        11,
        12,
        {"covered_target_keys": ["overall_length"], "missing_target_keys": []},
    ) == "display_dim_floor_gap"
    assert module._reference_intent_post_layout_repair_reason(
        12,
        12,
        {"covered_target_keys": ["overall_length", "hole_pitch"], "missing_target_keys": []},
    ) == ""


def test_generator_reports_final_reference_intent_acceptance_blockers() -> None:
    module = _load_generator()

    blockers = module._reference_intent_final_acceptance_blockers(
        11,
        12,
        {"covered_target_keys": ["overall_length"], "missing_target_keys": ["hole_pitch"]},
    )

    by_key = {item["key"]: item for item in blockers}
    assert set(by_key) == {"display_dim_floor_gap", "reference_intent_targets_missing"}
    assert by_key["display_dim_floor_gap"]["gap"] == 1
    assert by_key["reference_intent_targets_missing"]["missing_target_keys"] == ["hole_pitch"]
    assert module._reference_intent_final_acceptance_blockers(
        12,
        12,
        {"covered_target_keys": ["overall_length", "hole_pitch"], "missing_target_keys": []},
    ) == []


def test_generator_reports_reference_intent_target_coverage_stage_delta() -> None:
    module = _load_generator()
    snapshots = [
        {
            "stage": "pre_saveas",
            "covered_target_keys": ["overall_length", "hole_pitch"],
            "missing_target_keys": ["projection_view_height"],
        },
        {
            "stage": "post_saveas_reopen_prune",
            "covered_target_keys": ["overall_length"],
            "missing_target_keys": ["hole_pitch", "projection_view_height"],
        },
        {
            "stage": "post_layout_final",
            "covered_target_keys": ["overall_length", "projection_view_height"],
            "missing_target_keys": ["hole_pitch"],
        },
    ]

    delta = module._reference_intent_target_coverage_stage_delta(snapshots)
    by_key = {item["target_key"]: item for item in delta["per_target"]}

    assert delta["stage_order"] == ["pre_saveas", "post_saveas_reopen_prune", "post_layout_final"]
    assert delta["lost_target_keys"] == ["hole_pitch"]
    assert delta["recovered_target_keys"] == []
    assert delta["never_covered_target_keys"] == []
    assert delta["final_missing_target_keys"] == ["hole_pitch"]
    assert by_key["hole_pitch"]["first_covered_stage"] == "pre_saveas"
    assert by_key["hole_pitch"]["first_missing_after_covered_stage"] == "post_saveas_reopen_prune"
    assert by_key["hole_pitch"]["lost_after_coverage"] is True
    assert by_key["projection_view_height"]["first_covered_stage"] == "post_layout_final"


def test_generator_explicit_dims_continue_when_floor_met_but_targets_missing() -> None:
    source = GENERATOR_PATH.read_text(encoding="utf-8")

    assert "missing_target_keys_before" in source
    assert "target_coverage_after" in source
    assert "if current_count >= _dim_floor and not missing_now:" in source
    assert "if current_count >= _dim_floor and missing_now and target_key not in missing_now:" in source
    assert '"repair_reason": "missing_target_key" if target_key in missing_now else "display_dim_floor_gap"' in source


def test_generator_prune_preserves_unique_reference_intent_target_coverage() -> None:
    module = _load_generator()

    class FakeDoc:
        def ClearSelection2(self, *_args):
            return True

        def ForceRebuild3(self, *_args):
            return True

    ann_a = object()
    ann_b = object()
    ann_c = object()
    live_items = [
        {
            "annotation": ann_a,
            "slot": "front",
            "_slot": "front",
            "view": "front_a",
            "source": "unit",
            "view_outline": [0.0, 0.0, 1.0, 1.0],
            "position": [0.50, 1.012],
        },
        {
            "annotation": ann_b,
            "slot": "front",
            "_slot": "front",
            "view": "front_b",
            "source": "unit",
            "view_outline": [0.0, 0.0, 1.0, 1.0],
            "position": [0.55, 1.012],
        },
        {
            "annotation": ann_c,
            "slot": "top",
            "_slot": "top",
            "view": "top_hole",
            "source": "unit",
            "view_outline": [0.0, 0.0, 1.0, 1.0],
            "position": [0.70, 1.012],
        },
    ]
    dimension_plan = {
        "dimension_intent_groups": [{"key": "end_offsets"}, {"key": "hole_locations"}],
        "view_dimension_quotas": {"front": 1, "top": 1},
        "dimension_targets": [
            {"key": "overall_length", "target_view": "front", "preferred_side": "above", "priority": 1},
            {"key": "hole_pitch", "target_view": "top", "preferred_side": "above", "priority": 9},
        ],
    }
    selected = {"annotation": None}
    original_collect = module._display_dim_annotations_in_doc
    original_select = module._select_annotation_for_delete
    original_delete = module._delete_selected_annotation

    def fake_collect(_doc):
        return list(live_items)

    def fake_select(_doc, annotation, display_dim=None):
        selected["annotation"] = annotation
        return True, "unit.Select"

    def fake_delete(_doc):
        annotation = selected.get("annotation")
        for index, item in enumerate(list(live_items)):
            if item.get("annotation") is annotation:
                del live_items[index]
                return True, "unit.Delete"
        return False, "unit.DeleteMissing"

    try:
        module._display_dim_annotations_in_doc = fake_collect
        module._select_annotation_for_delete = fake_select
        module._delete_selected_annotation = fake_delete
        result = module._prune_display_dims_to_cap(
            FakeDoc(),
            2,
            dimension_plan=dimension_plan,
            reference_dim_floor=2,
            strict_reference_intent=True,
        )
    finally:
        module._display_dim_annotations_in_doc = original_collect
        module._select_annotation_for_delete = original_select
        module._delete_selected_annotation = original_delete

    deleted_keys = [item["target_key"] for item in result["deleted_items"]]
    remaining_annotations = {item["annotation"] for item in live_items}
    assert result["deleted"] == 1
    assert deleted_keys == ["overall_length"]
    assert result["deleted_items"][0]["slot"] == "front"
    assert result["deleted_items"][0]["reason"] == "over_quota_or_low_reference_intent_score"
    assert ann_c in remaining_annotations
    assert any(item["target_key"] == "hole_pitch" for item in result["protected_target_items"])
    assert result["success"] is True


def test_generator_prune_refuses_to_break_unique_target_coverage_for_cap() -> None:
    module = _load_generator()

    class FakeDoc:
        def ClearSelection2(self, *_args):
            return True

        def ForceRebuild3(self, *_args):
            return True

    live_items = [
        {
            "annotation": object(),
            "slot": "front",
            "_slot": "front",
            "view": "front",
            "source": "unit",
            "view_outline": [0.0, 0.0, 1.0, 1.0],
            "position": [0.50, 1.012],
        },
        {
            "annotation": object(),
            "slot": "top",
            "_slot": "top",
            "view": "top",
            "source": "unit",
            "view_outline": [0.0, 0.0, 1.0, 1.0],
            "position": [0.70, 1.012],
        },
    ]
    dimension_plan = {
        "dimension_intent_groups": [{"key": "end_offsets"}, {"key": "hole_locations"}],
        "dimension_targets": [
            {"key": "overall_length", "target_view": "front", "preferred_side": "above", "priority": 1},
            {"key": "hole_pitch", "target_view": "top", "preferred_side": "above", "priority": 9},
        ],
    }
    original_collect = module._display_dim_annotations_in_doc
    try:
        module._display_dim_annotations_in_doc = lambda _doc: list(live_items)
        result = module._prune_display_dims_to_cap(
            FakeDoc(),
            1,
            dimension_plan=dimension_plan,
            reference_dim_floor=1,
            strict_reference_intent=True,
        )
    finally:
        module._display_dim_annotations_in_doc = original_collect

    assert result["deleted"] == 0
    assert result["after"] == 2
    assert result["effective_cap"] == 2
    assert result["skip_reason"] == "reference_intent_effective_cap_guard_no_delete"
    assert result["protected_target_items"] == []
    assert result["success"] is True


def test_persisted_reference_prune_does_not_save_failed_prune() -> None:
    module = _load_generator()

    calls = {"save": 0, "restore": 0}
    fake_reopened = object()
    fake_restored = object()
    original_reopen = module._reopen_saved_drawing
    original_prune = module._prune_display_dims_to_cap
    original_save = module._save_drawing_doc
    original_restore = module._discard_unsaved_and_reopen_drawing

    def fake_reopen(*_args, **_kwargs):
        return fake_reopened, {"success": True}

    def fake_prune(*_args, **_kwargs):
        return {
            "deleted": 2,
            "success": False,
            "reasons": ["reference_intent_target_coverage_missing_after_prune:hole_pitch"],
        }

    def fake_save(*_args, **_kwargs):
        calls["save"] += 1
        return {"success": True}

    def fake_restore(*_args, **_kwargs):
        calls["restore"] += 1
        return fake_restored, {"success": True}

    try:
        module._reopen_saved_drawing = fake_reopen
        module._prune_display_dims_to_cap = fake_prune
        module._save_drawing_doc = fake_save
        module._discard_unsaved_and_reopen_drawing = fake_restore
        restored_doc, result = module._prune_persisted_reference_display_dims(
            object(),
            object(),
            "drawing.SLDDRW",
            12,
            part_class="long_thin",
            dimension_plan={
                "dimension_targets": [{"key": "hole_pitch"}],
                "view_dimension_quotas": {"top": 1},
            },
            layout_plan={},
        )
    finally:
        module._reopen_saved_drawing = original_reopen
        module._prune_display_dims_to_cap = original_prune
        module._save_drawing_doc = original_save
        module._discard_unsaved_and_reopen_drawing = original_restore

    assert restored_doc is fake_restored
    assert calls["save"] == 0
    assert calls["restore"] == 1
    assert result["success"] is False
    assert result["save"]["skipped_reason"] == "prune_failed_no_save"
    assert result["restore_after_failed_prune"]["success"] is True


def test_persisted_reference_prune_uses_exact_target_cap_for_strict_006() -> None:
    module = _load_generator()

    captured = {}
    fake_reopened = object()
    original_reopen = module._reopen_saved_drawing
    original_prune = module._prune_display_dims_to_cap

    def fake_reopen(*_args, **_kwargs):
        return fake_reopened, {"success": True}

    def fake_prune(_doc, cap, **kwargs):
        captured["cap"] = cap
        captured["strict_reference_intent"] = kwargs.get("strict_reference_intent")
        captured["reference_dim_floor"] = kwargs.get("reference_dim_floor")
        return {"deleted": 0, "success": True}

    targets = [
        {
            "key": f"target_{index}",
            "target_view": "top",
            "preferred_side": "above",
            "avoid_generic_model_annotation": True,
        }
        for index in range(12)
    ]
    try:
        module._reopen_saved_drawing = fake_reopen
        module._prune_display_dims_to_cap = fake_prune
        _doc, result = module._prune_persisted_reference_display_dims(
            object(),
            object(),
            "drawing.SLDDRW",
            12,
            part_class="long_thin",
            dimension_plan={
                "source": "reference_intent_dimension_plan_v4_2",
                "reasons": ["explicit_dimension_targets_replace_generic_autodimension_acceptance"],
                "required_display_dim_count": 12,
                "dimension_targets": targets,
                "view_dimension_quotas": {"front": 3, "top": 6, "right": 3},
            },
            layout_plan={},
        )
    finally:
        module._reopen_saved_drawing = original_reopen
        module._prune_display_dims_to_cap = original_prune

    assert captured["cap"] == 12
    assert captured["strict_reference_intent"] is True
    assert captured["reference_dim_floor"] == 12
    assert result["original_cap"] == 14
    assert result["cap"] == 12
    assert result["effective_cap_reason"] == "reference_intent_exact_target_cap"
    assert result["reference_intent_target_count"] == 12


def test_generator_rebinds_reference_intent_slots_from_persisted_outlines() -> None:
    module = _load_generator()
    layout_centers = {
        "front": (0.100, 0.160),
        "top": (0.100, 0.110),
        "right": (0.200, 0.160),
    }
    view_records = [
        {
            "name": "Drawing View 1",
            "type": "7",
            "outline": [0.128, 0.145, 0.154, 0.175],
            "view": object(),
        },
        {
            "name": "Drawing View 2",
            "type": "4",
            "outline": [0.088, 0.098, 0.112, 0.122],
            "view": object(),
        },
        {
            "name": "Drawing View 3",
            "type": "4",
            "outline": [0.188, 0.145, 0.212, 0.175],
            "view": object(),
        },
    ]

    matched = module._match_reference_intent_slot_views(
        view_records,
        layout_centers,
        {"front", "top", "right"},
        max_distance=0.035,
    )

    assert set(matched) == {"front", "top", "right"}
    assert matched["front"]["source"].startswith("nearest_layout_center_relaxed")
    assert matched["top"]["source"].startswith("nearest_layout_center")
    assert matched["right"]["distance"] <= 0.035


def test_generator_rebinds_reference_intent_slot_by_name_without_centers() -> None:
    module = _load_generator()
    view = object()
    matched = module._match_reference_intent_slot_views(
        [{"name": "Front View", "type": "7", "outline": [0.01, 0.02, 0.08, 0.06], "view": view}],
        {},
        {"front"},
    )

    assert matched["front"]["source"] == "view_name_hint"
    assert matched["front"]["view"] is view


def test_generator_rebinds_reference_intent_slots_by_view_family_when_centers_are_missing() -> None:
    module = _load_generator()
    front = object()
    top = object()
    right = object()
    iso = object()
    matched = module._match_reference_intent_slot_views(
        [
            {"name": "Drawing View 1", "type": "7", "outline": [0.070, 0.145, 0.170, 0.175], "view": front},
            {"name": "Drawing View 2", "type": "4", "outline": [0.075, 0.092, 0.165, 0.118], "view": top},
            {"name": "Drawing View 3", "type": "4", "outline": [0.195, 0.145, 0.225, 0.175], "view": right},
            {"name": "Drawing View 4", "type": "7", "outline": [0.225, 0.085, 0.275, 0.125], "view": iso},
        ],
        {},
        {"front", "top", "right", "iso"},
    )

    assert matched["front"]["source"] == "view_family_heuristic:type7_front"
    assert matched["top"]["source"] == "view_family_heuristic:type4_top"
    assert matched["right"]["source"] == "view_family_heuristic:type4_right"
    assert matched["iso"]["source"] == "view_family_heuristic:type7_iso"
    assert matched["front"]["view"] is front
    assert matched["top"]["view"] is top
    assert matched["right"]["view"] is right
    assert matched["iso"]["view"] is iso


def test_generator_prefers_current_doc_views_before_created_views_for_reference_intent_rebind() -> None:
    source = GENERATOR_PATH.read_text(encoding="utf-8")
    current_append = 'for view in _created_views_for_autodimension():\n                _append(view, "current_doc_views")'
    created_append = 'for slot, view in (created_views or {}).items():\n                _append(view, f"created_views:{slot}")'
    matched_call = "matched = _match_reference_intent_slot_views("
    fallback_accept = 'for slot, view in (created_views or {}).items():\n            _accept(slot, view, "created_views_fallback")'

    assert source.index(current_append) < source.index(created_append)
    assert source.index(matched_call) < source.index(fallback_accept)
    assert "created_views_fallback" in source


def test_generator_rebinds_reference_intent_slots_from_persisted_real_outline_names() -> None:
    module = _load_generator()
    layout_centers = {
        "front": (0.1100088, 0.169554),
        "top": (0.1100088, 0.124908),
        "right": (0.2155923, 0.169554),
    }
    front = object()
    top = object()
    right = object()
    matched = module._match_reference_intent_slot_views(
        [
            {
                "name": "工程图视图1",
                "type": "",
                "outline": [0.0828088, 0.164054, 0.1372088, 0.175054],
                "view": front,
            },
            {
                "name": "工程图视图2",
                "type": "",
                "outline": [0.0828088, 0.119508, 0.1372088, 0.130308],
                "view": top,
            },
            {
                "name": "工程图视图3",
                "type": "",
                "outline": [0.2101923, 0.164054, 0.2209923, 0.175054],
                "view": right,
            },
        ],
        layout_centers,
        {"front", "top", "right"},
        max_distance=0.020,
    )

    assert set(matched) == {"front", "top", "right"}
    assert matched["front"]["view_name"] == "工程图视图1"
    assert matched["top"]["view_name"] == "工程图视图2"
    assert matched["right"]["view_name"] == "工程图视图3"
    assert matched["front"]["view"] is front
    assert matched["top"]["view"] is top
    assert matched["right"]["view"] is right


def test_generator_post_layout_rebind_has_persisted_name_selection_fallback() -> None:
    source = GENERATOR_PATH.read_text(encoding="utf-8")

    assert "def _drawing_view_by_name_or_point" in source
    assert "SelectionManager" in source
    assert "GetSelectedObject6" in source
    assert "persisted_real_outlines" in source
    assert "select_by_persisted_name" in source
    assert "direct_accept_failed_select_by_persisted_name" in source
    assert '"direct_accept_failed": bool(direct_accept_failed)' in source
    assert "slot_rebind_diagnostics" in source
    assert "slot_rebind_summary" in source
    assert "nearest_candidates" in source


def test_reference_intent_slot_rebind_summary_reports_unbound_slot_causes() -> None:
    module = _load_generator()
    records = [
        {
            "name": "Drawing View1",
            "type": "7",
            "outline": [0.090, 0.140, 0.110, 0.160],
            "source": "current_doc_views",
            "view": object(),
        }
    ]
    layout_centers = {"front": (0.100, 0.150), "top": (0.100, 0.090)}
    matched = module._match_reference_intent_slot_views(
        records,
        layout_centers,
        {"front", "top"},
        max_distance=0.010,
    )

    summary = module._reference_intent_slot_rebind_summary(
        records,
        [],
        layout_centers,
        {"front", "top"},
        matched,
        [{"slot": "front", "accepted": True, "source": "nearest_layout_center:0.00000"}],
        {"reference_view_slots": {"top": {"reference_view_name": "TopRef"}}},
    )

    assert summary["bound_slots"] == ["front"]
    assert summary["unbound_slots"] == ["top"]
    assert summary["slot_results"]["front"]["reason"] == "bound"
    assert summary["slot_results"]["top"]["reason"] == "slot_match_not_attempted"
    assert summary["slot_results"]["top"]["name_candidates"][0] == "TopRef"
    assert summary["slot_results"]["top"]["nearest_candidates"][0]["view_name"] == "Drawing View1"

    empty_summary = module._reference_intent_slot_rebind_summary(
        [],
        [],
        layout_centers,
        {"front", "top"},
        {},
        [],
        {},
    )
    assert empty_summary["current_view_record_count"] == 0
    assert empty_summary["slot_results"]["front"]["reason"] == "no_view_records"
    assert empty_summary["slot_results"]["top"]["reason"] == "no_view_records"


def test_generator_ignores_cosmetic_thread_annotations_as_display_dims() -> None:
    module = _load_generator()

    class FakeAnnotation:
        def __init__(self, name: str) -> None:
            self._name = name

        def GetName(self) -> str:
            return self._name

    assert module._is_cosmetic_thread_annotation(FakeAnnotation("孔螺纹线1")) is True
    assert module._is_cosmetic_thread_annotation(FakeAnnotation("孔螺蚊线2")) is True
    assert module._is_cosmetic_thread_annotation(FakeAnnotation("RD1@工程图视图1")) is False


def test_generator_final_front_position_preserves_reference_center() -> None:
    module = _load_generator()

    assert module._final_front_position({"front": (0.11, 0.16955)}) == (0.11, 0.16955)
    assert module._final_front_position({"top": (0.11, 0.1249)}) == (0.080, 0.140)


def test_generator_reference_centers_drive_scale_downgrade() -> None:
    module = _load_generator()
    bbox_m = (0.08, 0.04, 0.04)
    centers = {
        "front": (0.10, 0.15),
        "top": (0.10, 0.13),
    }

    ok_1x, pairs_1x, _, out_1x = module.check_layout_no_overlap_for_centers(
        bbox_m,
        (1, 1),
        centers,
        view_keys=["front", "top"],
    )
    scale, outlines, pairs, util, out_of_workarea = module.pick_scale_with_reference_centers(
        bbox_m,
        centers,
        view_keys=["front", "top"],
        start_scale=(1, 1),
    )

    assert ok_1x is False
    assert ("front", "top") in pairs_1x or ("top", "front") in pairs_1x
    assert out_1x == []
    assert scale != (1, 1)
    assert pairs == []
    assert out_of_workarea == []
    assert outlines
    assert util > 0


if __name__ == "__main__":
    test_generator_prefers_lb26001_36_reference_profile_before_legacy_six()
    test_generator_uses_all_six_lb26001_reference_style_plans()
    test_generator_uses_lb26001_36_reference_view_families()
    test_generator_uses_first_angle_when_top_and_right_projected_slots_are_required()
    test_persisted_layout_centers_follow_created_view_order()
    test_generator_allows_section_for_unknown_or_reference_section_samples()
    test_generator_skips_builtin_titleblock_for_same_name_reference_samples()
    test_generator_records_reference_sheet_artifact_cleanup_policy()
    test_generator_maps_reference_layout_centers_to_view_slots()
    test_generator_dimension_insert_plan_scales_to_reference_floor()
    test_generator_force_dimension_plan_only_chases_floor_gap()
    test_generator_skips_bulk_model_dimensions_for_006_reference_intent_contract()
    test_generator_preserves_reference_intent_view_names_and_add_methods()
    test_generator_attaches_reference_callout_review_plan_for_006_ui_closure()
    test_generator_reference_autodim_and_prune_policy_is_bounded()
    test_generator_source_blocks_reference_intent_autodim_after_ui_failure()
    test_generator_scores_long_thin_display_dims_by_reference_intent()
    test_generator_reports_reference_intent_target_coverage_from_display_dims()
    test_generator_strict_ui_defect_target_match_rejects_weak_autodim_survivors()
    test_generator_prune_dedupes_reference_intent_equivalent_wrappers_before_delete()
    test_generator_prioritizes_missing_reference_intent_targets_for_repair()
    test_generator_checks_reference_intent_target_coverage_truthfully()
    test_generator_ranks_reference_intent_entities_by_target_type()
    test_generator_uses_reference_intent_placement_lane_station()
    test_generator_post_layout_repair_triggers_on_missing_targets_even_when_floor_met()
    test_generator_reports_final_reference_intent_acceptance_blockers()
    test_generator_reports_reference_intent_target_coverage_stage_delta()
    test_generator_explicit_dims_continue_when_floor_met_but_targets_missing()
    test_generator_prune_preserves_unique_reference_intent_target_coverage()
    test_generator_prune_refuses_to_break_unique_target_coverage_for_cap()
    test_persisted_reference_prune_does_not_save_failed_prune()
    test_persisted_reference_prune_uses_exact_target_cap_for_strict_006()
    test_generator_rebinds_reference_intent_slots_from_persisted_outlines()
    test_generator_rebinds_reference_intent_slot_by_name_without_centers()
    test_generator_rebinds_reference_intent_slots_by_view_family_when_centers_are_missing()
    test_generator_prefers_current_doc_views_before_created_views_for_reference_intent_rebind()
    test_generator_rebinds_reference_intent_slots_from_persisted_real_outline_names()
    test_generator_post_layout_rebind_has_persisted_name_selection_fallback()
    test_reference_intent_slot_rebind_summary_reports_unbound_slot_causes()
    test_generator_ignores_cosmetic_thread_annotations_as_display_dims()
    test_generator_final_front_position_preserves_reference_center()
    test_generator_reference_centers_drive_scale_downgrade()
    print("PASS test_v3_generator_reference_style_plan")
