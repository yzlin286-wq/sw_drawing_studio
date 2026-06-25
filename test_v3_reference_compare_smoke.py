from pathlib import Path
from tempfile import TemporaryDirectory

from tools.validation.reference_compare_smoke_v3 import (
    compare,
    _count_display_dim_annotation_items,
    _merge_annotation_display_dim_fallback,
    _normalize_view_metrics,
    _read_json,
    _resolve_reference_drawing,
    _score,
)


def test_empty_reference_metrics_cannot_pass() -> None:
    scoring = _score(
        {
            "success": True,
            "view_count": 0,
            "view_types": {},
            "display_dim_count": 0,
        },
        {
            "success": True,
            "view_count": 0,
            "view_types": {},
            "display_dim_count": 0,
        },
        {
            "display_dim_count": 44,
            "checks": {
                "view_overlap": {"real_view_count": 4},
                "all_13_keys_present": {"pass": True, "present_count": 13},
            },
            "warnings": [],
        },
    )

    assert scoring["status"] == "need_review"
    assert scoring["view_match_score"] == 0.0
    assert scoring["dimension_match_score"] == 0.0
    assert scoring["metric_quality"]["reference"]["usable"] is False
    assert "reference_view_metrics_empty" in scoring["metric_quality"]["reference"]["weak_reasons"]
    assert "reference_display_dim_metrics_empty" in scoring["metric_quality"]["reference"]["weak_reasons"]


def test_extra_generated_views_need_review() -> None:
    scoring = _score(
        {
            "success": True,
            "view_count": 2,
            "view_types": {"7": 1, "4": 1},
            "display_dim_count": 44,
        },
        {
            "success": True,
            "view_count": 4,
            "view_types": {"7": 4, "4": 1},
            "display_dim_count": 44,
        },
        {
            "display_dim_count": 44,
            "checks": {
                "view_overlap": {"pass": True, "real_view_count": 4},
                "view_in_frame": {"pass": True},
                "all_13_keys_present": {"pass": True, "present_count": 13},
            },
            "warnings": [],
        },
    )

    keys = [diff["key"] for diff in scoring["differences"]]
    assert scoring["status"] == "need_review"
    assert "view_count_higher_than_reference" in keys
    assert scoring["view_match_score"] == 0.7
    assert scoring["dimension_match_score"] == 1.0
    assert scoring["metric_quality"]["reference"]["usable"] is True


def test_extra_view_type_needs_review() -> None:
    scoring = _score(
        {
            "success": True,
            "view_count": 2,
            "view_types": {"7": 1, "4": 1},
            "display_dim_count": 8,
        },
        {
            "success": True,
            "view_count": 3,
            "view_types": {"7": 1, "4": 1, "3": 1},
            "display_dim_count": 8,
        },
        {
            "display_dim_count": 8,
            "checks": {
                "view_overlap": {"pass": True, "real_view_count": 3},
                "view_in_frame": {"pass": True},
                "all_13_keys_present": {"pass": True, "present_count": 13},
            },
            "warnings": [],
        },
    )

    keys = [diff["key"] for diff in scoring["differences"]]
    assert scoring["status"] == "need_review"
    assert "view_count_higher_than_reference" in keys
    assert "view_type_extra_than_reference" in keys


def test_long_thin_sidecar_dimensions_are_warning_not_need_review() -> None:
    scoring = _score(
        {
            "success": True,
            "view_count": 4,
            "view_types": {"7": 2, "4": 2},
            "display_dim_count": 8,
        },
        {
            "success": True,
            "view_count": 4,
            "view_types": {"7": 4},
            "display_dim_count": 0,
        },
        {
            "part_class": "long_thin",
            "display_dim_count": 0,
            "note_dim_count": 4,
            "checks": {
                "dimension_coverage": {"overall_length": 1.0, "overall_width": 0.1},
                "view_overlap": {"pass": True, "real_view_count": 4},
                "view_in_frame": {"pass": True},
                "all_13_keys_present": {"pass": True, "present_count": 13},
            },
            "warnings": ["dim_total_zero_with_sidecar_annotation"],
        },
    )

    assert scoring["status"] == "pass_with_warning"
    assert "generated_display_dim_metrics_empty" not in scoring["metric_quality"]["generated"]["weak_reasons"]
    assert "part_class_policy.sidecar_key_dimension_annotation" in scoring["metric_quality"]["generated"]["fallbacks"]
    assert scoring["dimension_match_score"] == 0.8


def test_006_reference_compare_rejects_sidecar_only_dimension_policy() -> None:
    scoring = _score(
        {
            "success": True,
            "view_count": 4,
            "view_types": {"7": 2, "4": 2},
            "display_dim_count": 8,
        },
        {
            "success": True,
            "view_count": 4,
            "view_types": {"7": 4},
            "display_dim_count": 0,
        },
        {
            "part_class": "long_thin",
            "display_dim_count": 0,
            "note_dim_count": 4,
            "checks": {
                "dimension_coverage": {"overall_length": 1.0, "overall_width": 0.1},
                "view_overlap": {"pass": True, "real_view_count": 4},
                "view_in_frame": {"pass": True},
                "all_13_keys_present": {"pass": True, "present_count": 13},
            },
            "warnings": ["dim_total_zero_with_sidecar_annotation"],
        },
        base="LB26001-A-04-006",
    )

    assert scoring["status"] == "need_review"
    assert "generated_display_dim_metrics_empty" in scoring["metric_quality"]["generated"]["weak_reasons"]
    assert "part_class_policy.sidecar_key_dimension_annotation" not in scoring["metric_quality"]["generated"]["fallbacks"]
    assert scoring["metric_quality"]["generated"]["strict_reference_intent_case"] is True
    assert scoring["metric_quality"]["generated"]["sidecar_policy_allowed"] is False
    assert scoring["dimension_match_score"] == 0.0


def test_sidecar_json_with_utf8_bom_is_readable() -> None:
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "sidecar.json"
        path.write_text('\ufeff{"success": true, "view_count": 2}', encoding="utf-8")

        data = _read_json(path)

    assert data["success"] is True
    assert data["view_count"] == 2


def test_annotation_probe_supplies_display_dim_when_sidecar_reports_zero() -> None:
    merged = _merge_annotation_display_dim_fallback(
        {
            "success": True,
            "display_dim_count": 0,
            "warnings": [],
        },
        {
            "success": True,
            "display_dim_count": 0,
            "display_dim_annotation_count": 8,
            "source": "pywin32_annotation_probe",
        },
    )

    assert merged["display_dim_count_api"] == 0
    assert merged["display_dim_count"] == 8
    assert merged["display_dim_annotation_count"] == 8
    assert merged["display_dim_count_source"] == "annotation_type1"
    assert "display_dim_count_from_annotation_type1" in merged["warnings"]


def test_cosmetic_thread_annotations_do_not_count_as_display_dims() -> None:
    class FakeAnnotation:
        def __init__(self, name: str) -> None:
            self._name = name

        def GetType(self) -> int:
            return 1

        def GetName(self) -> str:
            return self._name

    assert _count_display_dim_annotation_items([
        FakeAnnotation("孔螺纹线1"),
        FakeAnnotation("孔螺蚊线2"),
        FakeAnnotation("RD1@工程图视图1"),
    ]) == 1


def test_qc_dimension_fallback_does_not_override_generated_metrics() -> None:
    scoring = _score(
        {
            "success": True,
            "view_count": 4,
            "view_types": {"7": 2, "4": 2},
            "display_dim_count": 12,
        },
        {
            "success": True,
            "view_count": 4,
            "view_types": {"7": 2, "4": 2},
            "display_dim_count": 8,
            "display_dim_count_source": "annotation_type1",
        },
        {
            "display_dim_count": 44,
            "checks": {
                "view_overlap": {"pass": True, "real_view_count": 4},
                "view_in_frame": {"pass": True},
                "all_13_keys_present": {"pass": True, "present_count": 13},
            },
            "warnings": [],
        },
    )

    keys = [diff["key"] for diff in scoring["differences"]]
    assert "display_dim_count_lower_than_reference" in keys
    assert scoring["dimension_match_score"] == 0.667
    assert "qc.display_dim_count" not in scoring["metric_quality"]["generated"]["fallbacks"]


def test_reference_drawing_falls_back_to_part_sibling() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        part = root / "3D转2D测试图纸" / "LB26001-A-04-001.SLDPRT"
        reference = part.with_suffix(".SLDDRW")
        broken_reference_dir = root / "3D?2D????"
        part.parent.mkdir(parents=True)
        part.write_text("part placeholder", encoding="utf-8")
        reference.write_text("reference placeholder", encoding="utf-8")

        resolved = _resolve_reference_drawing(part, broken_reference_dir, part.stem)

    assert resolved == reference.resolve()


def test_off_sheet_palette_views_are_not_reference_view_count() -> None:
    metrics = {
        "success": True,
        "sheet": {"properties": [6, 13, 1, 4, 1, 0.297, 0.21, 1]},
        "view_count": 14,
        "view_types": {"7": 12, "4": 2},
        "view_names": [
            "工程图视图1",
            "工程图视图2",
            "工程图视图3",
            "工程图视图4",
            "*前视",
            "*上视",
        ],
        "view_outlines": [
            {"name": "工程图视图1", "type": "7", "outline": [0.061, 0.165, 0.159, 0.177]},
            {"name": "工程图视图2", "type": "4", "outline": [0.204, 0.165, 0.216, 0.177]},
            {"name": "工程图视图3", "type": "4", "outline": [0.061, 0.105, 0.159, 0.117]},
            {"name": "工程图视图4", "type": "7", "outline": [0.221, 0.086, 0.262, 0.114]},
            {"name": "*前视", "type": "7", "outline": [-0.491, -0.005, -0.447, 0.005]},
            {"name": "*上视", "type": "7", "outline": [-0.611, -0.005, -0.567, 0.005]},
        ],
    }

    normalized = _normalize_view_metrics(metrics)

    assert normalized["view_count"] == 4
    assert normalized["view_types"] == {"7": 2, "4": 2}
    assert normalized["raw_view_count"] == 14
    assert normalized["view_filter"]["removed_count"] == 2
    assert "*前视" in normalized["view_filter"]["removed_names"]


def test_generic_annotation_warnings_need_reference_evidence() -> None:
    scoring = _score(
        {
            "success": True,
            "view_count": 4,
            "view_types": {"7": 2, "4": 2},
            "display_dim_count": 12,
        },
        {
            "success": True,
            "view_count": 4,
            "view_types": {"7": 2, "4": 2},
            "display_dim_count": 8,
        },
        {
            "display_dim_count": 8,
            "checks": {
                "view_overlap": {"pass": True, "real_view_count": 4},
                "view_in_frame": {"pass": True},
                "all_13_keys_present": {"pass": True, "present_count": 13},
            },
            "warnings": ["has_ra_note", "has_datum_a", "gb_has_section_view_or_skipped"],
        },
    )

    keys = [diff["key"] for diff in scoring["differences"]]
    assert "display_dim_count_lower_than_reference" in keys
    assert "has_ra_note" not in keys
    assert "has_datum_a" not in keys
    assert "gb_has_section_view_or_skipped" not in keys
    assert scoring["status"] == "pass_with_warning"
    assert set(scoring["metric_quality"]["reference"]["annotation_evidence_skipped"]) == {
        "has_ra_note",
        "has_datum_a",
        "gb_has_section_view_or_skipped",
    }


def test_reference_section_evidence_still_penalizes_missing_section() -> None:
    scoring = _score(
        {
            "success": True,
            "view_count": 3,
            "view_types": {"7": 2, "3": 1},
            "view_names": ["工程图视图1", "剖视图 A-A", "工程图视图2"],
            "display_dim_count": 8,
        },
        {
            "success": True,
            "view_count": 3,
            "view_types": {"7": 3},
            "display_dim_count": 8,
        },
        {
            "display_dim_count": 8,
            "checks": {
                "view_overlap": {"pass": True, "real_view_count": 3},
                "view_in_frame": {"pass": True},
                "all_13_keys_present": {"pass": True, "present_count": 13},
            },
            "warnings": ["gb_has_section_view_or_skipped"],
        },
    )

    keys = [diff["key"] for diff in scoring["differences"]]
    assert "gb_has_section_view_or_skipped" in keys
    assert "gb_has_section_view_or_skipped" not in scoring["metric_quality"]["reference"]["annotation_evidence_skipped"]


def test_compare_fails_fast_when_solidworks_com_probe_times_out() -> None:
    from unittest.mock import patch

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_dir = root / "run"
        drawing_dir = run_dir / "drawing"
        qc_dir = run_dir / "qc"
        reference_dir = root / "refs"
        part = reference_dir / "LB26001-A-04-006.SLDPRT"
        reference = reference_dir / "LB26001-A-04-006.SLDDRW"
        generated = drawing_dir / "LB26001-A-04-006_v5.SLDDRW"
        out = root / "reference_compare.json"
        drawing_dir.mkdir(parents=True)
        qc_dir.mkdir(parents=True)
        reference_dir.mkdir(parents=True)
        part.write_text("part placeholder", encoding="utf-8")
        reference.write_text("reference placeholder", encoding="utf-8")
        generated.write_text("generated placeholder", encoding="utf-8")
        (qc_dir / "LB26001-A-04-006_v5_qc.json").write_text(
            """{
              "display_dim_count": 8,
              "checks": {
                "view_overlap": {"pass": true, "real_view_count": 4},
                "view_in_frame": {"pass": true},
                "all_13_keys_present": {"pass": true, "present_count": 13}
              },
              "warnings": []
            }""",
            encoding="utf-8",
        )

        from tools.validation import reference_compare_smoke_v3 as module

        def fail_sidecar(*_args, **_kwargs):
            raise AssertionError("sidecar should not run after COM probe timeout")

        with patch.object(
            module,
            "probe_solidworks_connection",
            lambda **_: {
                "status": "timeout",
                "reason": "get_active_object timed out after 0.1s",
                "method": "get_active_object",
            },
        ), patch.object(module, "_run_reference_metrics_sidecar", fail_sidecar):
            payload = compare(
                run_dir,
                reference_dir,
                out,
                part_path=part,
                metrics_mode="sidecar_only",
                sidecar_timeout_s=999,
                com_probe_timeout_s=0.1,
            )
        report_payload = _read_json(out)

        assert payload["pass"] is False
        assert payload["status"] == "fail"
        assert payload["failure_bucket"] == "solidworks_com_active_object_timeout"
        assert payload["connection_probe"]["status"] == "timeout"
        assert payload["reference_metrics"]["source"] == "solidworks_com_probe"
        assert payload["generated_metrics"]["source"] == "solidworks_com_probe"
        assert payload["reasons"][0] == "solidworks_com_active_object_timeout"
        assert report_payload["failure_bucket"] == "solidworks_com_active_object_timeout"


if __name__ == "__main__":
    test_empty_reference_metrics_cannot_pass()
    test_extra_generated_views_need_review()
    test_extra_view_type_needs_review()
    test_long_thin_sidecar_dimensions_are_warning_not_need_review()
    test_006_reference_compare_rejects_sidecar_only_dimension_policy()
    test_sidecar_json_with_utf8_bom_is_readable()
    test_annotation_probe_supplies_display_dim_when_sidecar_reports_zero()
    test_cosmetic_thread_annotations_do_not_count_as_display_dims()
    test_qc_dimension_fallback_does_not_override_generated_metrics()
    test_reference_drawing_falls_back_to_part_sibling()
    test_off_sheet_palette_views_are_not_reference_view_count()
    test_generic_annotation_warnings_need_reference_evidence()
    test_reference_section_evidence_still_penalizes_missing_section()
    test_compare_fails_fast_when_solidworks_com_probe_times_out()
    print("PASS test_v3_reference_compare_smoke")
