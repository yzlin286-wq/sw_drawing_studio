from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory

from app.services.reference_compare_v4 import compare_reference_v4


REQUIRED_ISSUE_FIELDS = {
    "key",
    "severity",
    "bbox",
    "source",
    "confidence",
    "evidence",
    "fix_suggestion",
    "auto_fix_available",
    "human_review_status",
}


def _reference_profile() -> dict:
    return {
        "schema": "sw_drawing_studio.reference_profile.v4",
        "base": "LB26001-A-04-006",
        "view_count": 4,
        "view_types": {"7": 2, "4": 2},
        "display_dim_count": 12,
        "normalized_notes": [{"text": "TECHNICAL REQUIREMENTS"}],
        "roughness_symbols": [{"bbox": [0.1, 0.1, 0.05, 0.05]}],
        "datum_symbols": [],
    }


def _blueprint() -> dict:
    return {
        "schema": "sw_drawing_studio.drawing_blueprint.v4",
        "base": "LB26001-A-04-006",
        "part_class": "machined_part",
        "drawing_purpose": "manufacturing",
        "view_plan": [
            {"slot": "front", "view_type": "named", "required": True, "sw_view_type": "7", "create_method": "named_view"},
            {"slot": "top", "view_type": "projected", "required": True, "sw_view_type": "4", "create_method": "projection_api", "projected_from": "front"},
            {"slot": "right", "view_type": "projected", "required": True, "sw_view_type": "4", "create_method": "projection_api", "projected_from": "front"},
            {"slot": "iso", "view_type": "iso", "required": True, "sw_view_type": "7", "create_method": "named_view"},
        ],
        "dimension_plan": {
            "required_display_dim_count": 12,
            "reference_display_dim_count": 12,
            "allow_note_substitution": False,
        },
        "annotation_plan": {"roughness_required": True},
        "titlebar_plan": {"required_fields": ["drawing_no", "name", "material"], "missing_fields": []},
        "notes_plan": {"required_notes": ["TECHNICAL REQUIREMENTS"], "raw_reference_notes": ["TECHNICAL REQUIREMENTS"]},
        "validation_plan": {
            "view_match_min": 0.9,
            "dimension_match_min": 0.8,
            "titlebar_match_min": 0.85,
            "notes_match_min": 0.85,
            "layout_match_min": 0.8,
            "forbid_note_as_display_dim": True,
            "forbid_named_view_as_projected": True,
            "require_ui_visual_review": True,
        },
    }


def _target_blueprint() -> dict:
    blueprint = deepcopy(_blueprint())
    blueprint["dimension_plan"]["dimension_targets"] = [
        {"key": "overall_length", "group": "overall", "view_slot": "front"},
        {"key": "hole_pitch", "group": "holes", "view_slot": "top"},
        {"key": "projection_view_height", "group": "projection", "view_slot": "right"},
    ]
    return blueprint


def _generator_warnings_coverage(*, missing: bool = False) -> dict:
    covered = ["overall_length", "hole_pitch"]
    missing_keys = ["projection_view_height"] if missing else []
    if not missing:
        covered.append("projection_view_height")
    snapshots = []
    if missing:
        snapshots.append(
            {
                "stage": "pre_saveas",
                "display_dim_count": 12,
                "target_count": 3,
                "covered_count": 3,
                "covered_target_keys": ["overall_length", "hole_pitch", "projection_view_height"],
                "missing_target_keys": [],
                "persisted_after_reopen": False,
            }
        )
    snapshots.append(
        {
            "stage": "post_layout_final",
            "display_dim_count": 12,
            "target_count": 3,
            "covered_count": len(covered),
            "covered_target_keys": covered,
            "missing_target_keys": missing_keys,
            "persisted_after_reopen": True,
        }
    )
    return {
        "reference_intent_target_coverage": snapshots,
        "reference_intent_target_coverage_delta": {
            "source": "reference_intent_target_coverage_stage_delta",
            "stage_order": [item["stage"] for item in snapshots],
            "lost_target_keys": ["projection_view_height"] if missing else [],
            "final_missing_target_keys": missing_keys,
        },
    }


def _generator_warnings_without_final_stage() -> dict:
    return {
        "reference_intent_target_coverage": [
            {
                "stage": "pre_export_final",
                "display_dim_count": 12,
                "target_count": 3,
                "covered_count": 3,
                "covered_target_keys": ["overall_length", "hole_pitch", "projection_view_height"],
                "missing_target_keys": [],
                "persisted_after_reopen": True,
            }
        ],
        "reference_intent_target_coverage_delta": {
            "source": "reference_intent_target_coverage_stage_delta",
            "stage_order": ["pre_export_final"],
            "lost_target_keys": [],
            "final_missing_target_keys": [],
        },
    }


def _generator_warnings_final_blocked() -> dict:
    payload = _generator_warnings_coverage(missing=False)
    payload["post_layout_dim_repair"] = {
        "final_acceptance_blockers": [
            {
                "key": "display_dim_floor_gap",
                "display_dim_count": 11,
                "reference_display_dim_floor": 12,
                "gap": 1,
            }
        ]
    }
    payload["warnings"] = [
        {
            "code": "post_layout_reference_intent_final_blocked",
            "display_dim_count": 11,
            "reference_display_dim_floor": 12,
            "blockers": payload["post_layout_dim_repair"]["final_acceptance_blockers"],
        }
    ]
    return payload


def _dimension(display_dims: int = 12, note_dims: int = 0) -> dict:
    return {
        "pass": display_dims >= 12,
        "status": "pass" if display_dims >= 12 else "need_review",
        "dimension_validation": {
            "display_dim_count": display_dims,
            "note_dim_count": note_dims,
            "dimension_evidence_policy": "display_dim",
        },
    }


def _sidecar_policy_dimension(display_dims: int = 12) -> dict:
    payload = _dimension(display_dims)
    payload["dimension_validation"]["dimension_evidence_policy"] = "sidecar_key_dimension_annotation"
    payload["dimension_validation"]["strict_reference_intent_case"] = True
    payload["dimension_validation"]["sidecar_policy_allowed"] = False
    return payload


def _vision(pass_visual: bool = True) -> dict:
    return {
        "schema": "sw_drawing_studio.vision_qc_v6",
        "status": "pass" if pass_visual else "need_review",
        "visual_acceptance_pass": pass_visual,
        "issues": [] if pass_visual else [
            {
                "key": "manual_ui_screenshot_review_required",
                "severity": "major",
                "bbox": [0, 0, 1, 1],
                "source": "ui_screenshot_review",
                "confidence": 1,
                "evidence": {},
                "fix_suggestion": "Capture and approve the application UI screenshot.",
                "auto_fix_available": False,
                "human_review_status": "pending",
            }
        ],
        "checks": {
            "ui_screenshot_review": {"required": True, "pass": pass_visual},
            "titlebar": {"detected": True},
            "notes": {"detected": True, "technical_requirements_detected": True},
            "reference_visual_compare": {"coarse_layout_match": True},
            "symbols": {"missing": []},
        },
    }


def test_reference_compare_v4_passes_when_blueprint_dims_and_ui_review_match_reference() -> None:
    result = compare_reference_v4(
        blueprint=_blueprint(),
        reference_profile=_reference_profile(),
        dimension_validation=_dimension(12),
        vision_qc=_vision(True),
    )

    assert result["status"] == "pass"
    assert result["pass"] is True
    assert result["scores"]["view_match"] == 1.0
    assert result["scores"]["dimension_match"] == 1.0
    assert result["generated"]["projected_view_methods"][0]["create_method"] == "projection_api"


def test_reference_compare_v4_blocks_display_dim_below_reference_without_counting_notes() -> None:
    result = compare_reference_v4(
        blueprint=_blueprint(),
        reference_profile=_reference_profile(),
        dimension_validation=_dimension(8, note_dims=4),
        vision_qc=_vision(True),
    )
    keys = {item["key"] for item in result["differences"]}

    assert result["status"] == "fail"
    assert result["pass"] is False
    assert result["generated"]["display_dim_count"] == 8
    assert "display_dim_lower_than_reference" in keys
    assert "note_dimensions_not_counted_as_display_dim" in keys
    assert result["generated"]["note_dim_count"] == 4
    for issue in result["differences"]:
        assert REQUIRED_ISSUE_FIELDS <= set(issue)


def test_reference_compare_v4_blocks_named_view_used_as_projected_view() -> None:
    blueprint = _blueprint()
    blueprint["view_plan"][1]["create_method"] = "named_view"

    result = compare_reference_v4(
        blueprint=blueprint,
        reference_profile=_reference_profile(),
        dimension_validation=_dimension(12),
        vision_qc=_vision(True),
    )
    keys = {item["key"] for item in result["differences"]}

    assert result["status"] == "fail"
    assert "projected_view_not_projection_api" in keys


def test_reference_compare_v4_blocks_missing_application_ui_screenshot_acceptance() -> None:
    result = compare_reference_v4(
        blueprint=_blueprint(),
        reference_profile=_reference_profile(),
        dimension_validation=_dimension(12),
        vision_qc=_vision(False),
    )
    keys = {item["key"] for item in result["differences"]}

    assert result["status"] == "need_review"
    assert result["pass"] is False
    assert "ui_screenshot_visual_acceptance_not_passed" in keys


def test_reference_compare_v4_blocks_missing_reference_intent_target_coverage() -> None:
    result = compare_reference_v4(
        blueprint=_target_blueprint(),
        reference_profile=_reference_profile(),
        dimension_validation=_dimension(12),
        vision_qc=_vision(True),
    )
    keys = {item["key"] for item in result["differences"]}

    assert result["status"] == "need_review"
    assert result["pass"] is False
    assert "reference_intent_target_coverage_missing" in keys
    assert result["generated"]["reference_intent_target_coverage"]["required"] is True
    assert result["generated"]["reference_intent_target_coverage"]["coverage_present"] is False


def test_reference_compare_v4_blocks_missing_reference_intent_targets_after_persistence() -> None:
    result = compare_reference_v4(
        blueprint=_target_blueprint(),
        reference_profile=_reference_profile(),
        dimension_validation=_dimension(12),
        vision_qc=_vision(True),
        generator_warnings=_generator_warnings_coverage(missing=True),
    )
    keys = {item["key"] for item in result["differences"]}
    coverage = result["generated"]["reference_intent_target_coverage"]

    assert result["status"] == "fail"
    assert result["pass"] is False
    assert "reference_intent_targets_missing_after_persistence" in keys
    assert coverage["latest_stage"] == "post_layout_final"
    assert coverage["missing_target_keys"] == ["projection_view_height"]
    assert coverage["lost_target_keys"] == ["projection_view_height"]
    issue = next(item for item in result["differences"] if item["key"] == "reference_intent_targets_missing_after_persistence")
    assert issue["evidence"]["lost_target_keys"] == ["projection_view_height"]


def test_reference_compare_v4_requires_post_layout_final_target_coverage() -> None:
    result = compare_reference_v4(
        blueprint=_target_blueprint(),
        reference_profile=_reference_profile(),
        dimension_validation=_dimension(12),
        vision_qc=_vision(True),
        generator_warnings=_generator_warnings_without_final_stage(),
    )
    keys = {item["key"] for item in result["differences"]}
    coverage = result["generated"]["reference_intent_target_coverage"]

    assert result["status"] == "fail"
    assert result["pass"] is False
    assert "reference_intent_post_layout_final_coverage_missing" in keys
    assert coverage["final_stage_required"] is True
    assert coverage["final_stage_present"] is False
    assert coverage["latest_stage"] == "pre_export_final"


def test_reference_compare_v4_rejects_sidecar_only_dimension_policy_for_006() -> None:
    result = compare_reference_v4(
        blueprint=_target_blueprint(),
        reference_profile=_reference_profile(),
        dimension_validation=_sidecar_policy_dimension(12),
        vision_qc=_vision(True),
        generator_warnings=_generator_warnings_coverage(missing=False),
    )
    keys = {item["key"] for item in result["differences"]}

    assert result["status"] == "fail"
    assert result["pass"] is False
    assert "strict_reference_intent_display_dim_source_not_real" in keys
    assert result["generated"]["display_dim_count"] == 12


def test_reference_compare_v4_blocks_generator_final_post_layout_warning() -> None:
    result = compare_reference_v4(
        blueprint=_target_blueprint(),
        reference_profile=_reference_profile(),
        dimension_validation=_dimension(12),
        vision_qc=_vision(True),
        generator_warnings=_generator_warnings_final_blocked(),
    )
    keys = {item["key"] for item in result["differences"]}

    assert result["status"] == "fail"
    assert result["pass"] is False
    assert "post_layout_reference_intent_final_blocked" in keys
    issue = next(item for item in result["differences"] if item["key"] == "post_layout_reference_intent_final_blocked")
    assert issue["evidence"]["blockers"][0]["key"] == "display_dim_floor_gap"
    assert issue["evidence"]["blockers"][0]["gap"] == 1


def test_reference_compare_v4_passes_when_reference_intent_targets_survive() -> None:
    result = compare_reference_v4(
        blueprint=_target_blueprint(),
        reference_profile=_reference_profile(),
        dimension_validation=_dimension(12),
        vision_qc=_vision(True),
        generator_warnings=_generator_warnings_coverage(missing=False),
    )

    assert result["status"] == "pass"
    assert result["pass"] is True
    assert result["generated"]["reference_intent_target_coverage"]["missing_target_keys"] == []


def test_reference_compare_v4_cli_writes_report() -> None:
    import json
    import subprocess
    import sys

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        blueprint = root / "drawing_blueprint.json"
        dimension = root / "dimension_validation.json"
        vision = root / "vision_qc_v6.json"
        profiles = root / "reference_profiles_v4.json"
        out = root / "reference_compare_v4.json"
        blueprint.write_text(json.dumps(_blueprint(), ensure_ascii=False), encoding="utf-8")
        dimension.write_text(json.dumps(_dimension(12), ensure_ascii=False), encoding="utf-8")
        vision.write_text(json.dumps(_vision(True), ensure_ascii=False), encoding="utf-8")
        profiles.write_text(
            json.dumps({"profiles": {"LB26001-A-04-006": _reference_profile()}}, ensure_ascii=False),
            encoding="utf-8",
        )

        completed = subprocess.run(
            [
                sys.executable,
                "tools/validation/reference_compare_v4.py",
                "--base",
                "LB26001-A-04-006",
                "--blueprint",
                str(blueprint),
                "--dimension-validation",
                str(dimension),
                "--vision-qc",
                str(vision),
                "--reference-profiles",
                str(profiles),
                "--out",
                str(out),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )

        assert completed.returncode == 0
        assert out.exists()


if __name__ == "__main__":
    test_reference_compare_v4_passes_when_blueprint_dims_and_ui_review_match_reference()
    test_reference_compare_v4_blocks_display_dim_below_reference_without_counting_notes()
    test_reference_compare_v4_blocks_named_view_used_as_projected_view()
    test_reference_compare_v4_blocks_missing_application_ui_screenshot_acceptance()
    test_reference_compare_v4_blocks_missing_reference_intent_target_coverage()
    test_reference_compare_v4_blocks_missing_reference_intent_targets_after_persistence()
    test_reference_compare_v4_requires_post_layout_final_target_coverage()
    test_reference_compare_v4_rejects_sidecar_only_dimension_policy_for_006()
    test_reference_compare_v4_blocks_generator_final_post_layout_warning()
    test_reference_compare_v4_passes_when_reference_intent_targets_survive()
    test_reference_compare_v4_cli_writes_report()
    print("PASS test_v4_reference_compare")
