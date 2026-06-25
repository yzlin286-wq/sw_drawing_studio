import json
import tempfile
from pathlib import Path

from tools.validation.dimension_validation_smoke_v3 import _has_sidecar_dimension_evidence, validate


def test_purchased_part_zero_display_dim_can_use_standard_annotation() -> None:
    ok, policy = _has_sidecar_dimension_evidence(
        part_class="purchased_part",
        display_dim_count=0,
        note_dim_count=3,
        standard_annotation_count=1,
        coverage={},
        warnings=["dim_total_zero_purchased_with_std_anno"],
        dim_sources={},
    )

    assert ok is True
    assert policy == "procurement_standard_annotation"


def test_long_thin_zero_display_dim_can_use_sidecar_key_dimensions() -> None:
    ok, policy = _has_sidecar_dimension_evidence(
        part_class="long_thin",
        display_dim_count=0,
        note_dim_count=4,
        standard_annotation_count=0,
        coverage={"overall_length": 1.0, "overall_width": 0.1},
        warnings=["dim_total_zero_with_sidecar_annotation"],
        dim_sources={},
    )

    assert ok is True
    assert policy == "sidecar_key_dimension_annotation"


def test_006_strict_reference_intent_rejects_sidecar_only_dimensions() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = Path(tmp) / "run"
        drawing_dir = run_dir / "drawing"
        qc_dir = run_dir / "qc"
        drawing_dir.mkdir(parents=True)
        qc_dir.mkdir(parents=True)

        (drawing_dir / "LB26001-A-04-006_v5.SLDDRW").write_text("placeholder", encoding="utf-8")
        (qc_dir / "final_quality.json").write_text(
            json.dumps({"status": "pass_with_warning", "deliverable": True}, ensure_ascii=False),
            encoding="utf-8",
        )
        (qc_dir / "LB26001-A-04-006_v5_qc.json").write_text(
            json.dumps(
                {
                    "part_class": "long_thin",
                    "display_dim_count": 0,
                    "note_dim_count": 4,
                    "dimension_grade": "B",
                    "warnings": ["dim_total_zero_with_sidecar_annotation"],
                    "dimension_sources": {
                        "display_dim_count": 0,
                        "note_dim_count": 4,
                        "sources_summary": ["sidecar_note=4"],
                    },
                    "checks": {
                        "dimension_coverage": {
                            "overall_length": 1.0,
                            "overall_width": 1.0,
                        },
                        "dim_count_sufficient": {"threshold": 5},
                        "text_height_ge_3_5mm": {"pass": True},
                        "view_overlap": {"pass": True},
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        payload = validate(
            run_dir,
            Path(tmp) / "dimension_validation.json",
            metrics_runner=lambda *_args, **_kwargs: {"success": False, "reason": "not_used"},
        )

    dimension_validation = payload["dimension_validation"]
    assert payload["pass"] is False
    assert "display_dim_count_zero" in payload["reasons"]
    assert dimension_validation["drawing_base"] == "LB26001-A-04-006"
    assert dimension_validation["strict_reference_intent_case"] is True
    assert dimension_validation["sidecar_policy_allowed"] is False
    assert dimension_validation["dimension_evidence_policy"] == "strict_reference_intent_display_dim_required"
    assert "strict_reference_intent_sidecar_policy_disabled" in dimension_validation["warnings"]


def test_feature_part_still_requires_display_dim() -> None:
    ok, policy = _has_sidecar_dimension_evidence(
        part_class="feature_part",
        display_dim_count=0,
        note_dim_count=4,
        standard_annotation_count=1,
        coverage={"overall_length": 1.0},
        warnings=["dim_total_zero_with_sidecar_annotation"],
        dim_sources={},
    )

    assert ok is False
    assert policy == "display_dim_required"


def test_feature_part_can_use_real_display_dim_metrics_when_qc_count_is_stale() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = Path(tmp) / "run"
        drawing_dir = run_dir / "drawing"
        qc_dir = run_dir / "qc"
        drawing_dir.mkdir(parents=True)
        qc_dir.mkdir(parents=True)

        drawing_path = drawing_dir / "LB26001-A-04-031_v5.SLDDRW"
        drawing_path.write_text("placeholder", encoding="utf-8")
        (qc_dir / "final_quality.json").write_text(
            json.dumps({"status": "pass_with_warning", "deliverable": True}, ensure_ascii=False),
            encoding="utf-8",
        )
        (qc_dir / "LB26001-A-04-031_v5_qc.json").write_text(
            json.dumps(
                {
                    "part_class": "feature_part",
                    "display_dim_count": 0,
                    "note_dim_count": 3,
                    "model_associative_dim_count": 0,
                    "dimension_grade": "B",
                    "usable_for": ["manufacturing", "assembly"],
                    "warnings": ["has_ra_note", "titlebar_complete"],
                    "dimension_sources": {
                        "display_dim_count": 0,
                        "note_dim_count": 3,
                        "sources_summary": ["sidecar_note=3"],
                    },
                    "checks": {
                        "dimension_coverage": {
                            "overall_length": 1.0,
                            "overall_width": 1.0,
                            "overall_height": 1.0,
                        },
                        "dim_count_sufficient": {"threshold": 5},
                        "text_height_ge_3_5mm": {"pass": True},
                        "view_overlap": {"pass": True},
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        def fake_metrics_runner(path: Path, label: str) -> dict[str, object]:
            assert path == drawing_path
            assert label == "LB26001-A-04-031_v5_dimension_validation"
            return {
                "success": True,
                "source": "csharp_sidecar",
                "display_dim_count": 16,
                "display_dim_count_source": "display_dimension_api",
                "sidecar_report": str(Path(tmp) / "sidecar.json"),
            }

        payload = validate(
            run_dir,
            Path(tmp) / "dimension_validation.json",
            metrics_runner=fake_metrics_runner,
        )

    dimension_validation = payload["dimension_validation"]
    assert payload["pass"] is True
    assert "display_dim_count_zero" not in payload["reasons"]
    assert dimension_validation["raw_display_dim_count"] == 0
    assert dimension_validation["display_dim_count"] == 16
    assert dimension_validation["display_dim_count_source"] == "reference_metrics_sidecar.display_dim_count"
    assert dimension_validation["display_dim_metrics"]["accepted"] is True
    assert "note_dimensions_present_not_counted_as_display_dim" in dimension_validation["warnings"]
    assert payload["source_separation"]["notes_counted_as_display_dim"] is False


if __name__ == "__main__":
    test_purchased_part_zero_display_dim_can_use_standard_annotation()
    test_long_thin_zero_display_dim_can_use_sidecar_key_dimensions()
    test_006_strict_reference_intent_rejects_sidecar_only_dimensions()
    test_feature_part_still_requires_display_dim()
    test_feature_part_can_use_real_display_dim_metrics_when_qc_count_is_stale()
    print("PASS test_v3_dimension_validation")
