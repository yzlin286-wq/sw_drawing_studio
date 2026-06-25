from tools.validation.reference_style_profile_v3 import (
    derive_profile,
    evaluate_generated_against_reference,
)


SHEET_W = 0.297
SHEET_H = 0.21


def _view_outline(vtype: str, center_norm: tuple[float, float]) -> dict:
    center_x = center_norm[0] * SHEET_W
    center_y = center_norm[1] * SHEET_H
    width = SHEET_W * 0.06
    height = SHEET_H * 0.06
    return {
        "name": f"view_{vtype}_{center_norm[0]}_{center_norm[1]}",
        "type": vtype,
        "outline": [
            center_x - width / 2,
            center_y - height / 2,
            center_x + width / 2,
            center_y + height / 2,
        ],
    }


def _metrics(
    view_count: int,
    view_types: dict[str, int],
    display_dim_count: int,
    layout: list[tuple[str, tuple[float, float]]] | None = None,
) -> dict:
    return {
        "success": True,
        "view_count": view_count,
        "view_types": view_types,
        "display_dim_count": display_dim_count,
        "annotation_count": 0,
        "sheet": {"properties": [6, 13, 1, 2, 1, SHEET_W, SHEET_H, 1]},
        "view_outlines": [_view_outline(vtype, center) for vtype, center in (layout or [])],
    }


def _layout_006() -> list[tuple[str, tuple[float, float]]]:
    return [
        ("7", (0.3704, 0.8074)),
        ("4", (0.7259, 0.8074)),
        ("4", (0.3704, 0.5948)),
        ("7", (0.8025, 0.4780)),
    ]


def test_reference_style_profile_derives_lb26001_rules() -> None:
    profile = derive_profile(
        {
            "LB26001-A-04-006": _metrics(4, {"7": 2, "4": 2}, 12),
            "LB26001-A-04-007": _metrics(4, {"7": 2, "4": 2}, 8),
            "LB26001-A-04-008": _metrics(2, {"7": 1, "4": 1}, 2),
            "LB26001-A-04-009": _metrics(3, {"7": 1, "4": 2}, 4),
            "LB26001-A-04-015": _metrics(2, {"7": 1, "4": 1}, 14),
            "LB26001-A-04-022": _metrics(4, {"7": 2, "4": 2}, 25),
        }
    )

    aggregate = profile["aggregate"]
    assert profile["status"] == "profile_ready"
    assert aggregate["allowed_view_counts"] == [2, 3, 4]
    assert aggregate["projected_view_required"] is True
    assert aggregate["min_projected_view_count_by_sample"]["LB26001-A-04-022"] == 2
    assert aggregate["min_display_dim_by_sample"]["LB26001-A-04-015"] == 14
    assert aggregate["display_dim_range"] == {"min": 2, "max": 25}


def test_all_named_views_and_zero_display_dims_fail_style_gate() -> None:
    result = evaluate_generated_against_reference(
        "LB26001-A-04-006",
        _metrics(4, {"7": 2, "4": 2}, 12),
        _metrics(4, {"7": 4}, 0),
        qc={"display_dim_count": 12},
    )

    keys = [item["key"] for item in result["differences"]]
    assert result["status"] == "fail"
    assert result["pass"] is False
    assert "projected_view_count_lower_than_reference" in keys
    assert "generated_all_named_model_views" in keys
    assert "generated_display_dim_zero_with_reference_baseline" in keys
    assert "qc_dimension_fallback_not_displaydim" in keys


def test_reference_view_count_overproduction_needs_review() -> None:
    result = evaluate_generated_against_reference(
        "LB26001-A-04-008",
        _metrics(2, {"7": 1, "4": 1}, 2),
        _metrics(4, {"7": 2, "4": 2}, 2),
    )

    keys = [item["key"] for item in result["differences"]]
    assert result["status"] == "need_review"
    assert result["pass"] is False
    assert "view_count_not_equal_reference" in keys


def test_reference_view_type_distribution_must_match() -> None:
    result = evaluate_generated_against_reference(
        "LB26001-A-04-006",
        _metrics(4, {"7": 2, "4": 2}, 12),
        _metrics(4, {"7": 1, "4": 2, "3": 1}, 12),
    )

    keys = [item["key"] for item in result["differences"]]
    assert result["status"] == "need_review"
    assert result["pass"] is False
    assert "view_type_count_lower_than_reference" in keys
    assert "view_type_extra_than_reference" in keys
    assert result["view_style_score"] < 1.0


def test_reference_display_dim_overproduction_needs_review() -> None:
    result = evaluate_generated_against_reference(
        "LB26001-A-04-006",
        _metrics(4, {"7": 2, "4": 2}, 12),
        _metrics(4, {"7": 2, "4": 2}, 19),
    )

    keys = [item["key"] for item in result["differences"]]
    assert result["status"] == "need_review"
    assert result["pass"] is False
    assert "display_dim_count_higher_than_reference" in keys
    assert result["dimension_style_score"] < 1.0


def test_matching_reference_layout_passes_style_gate() -> None:
    result = evaluate_generated_against_reference(
        "LB26001-A-04-006",
        _metrics(4, {"7": 2, "4": 2}, 12, _layout_006()),
        _metrics(4, {"7": 2, "4": 2}, 12, _layout_006()),
    )

    assert result["status"] == "pass"
    assert result["pass"] is True
    assert result["layout_style_score"] == 1.0
    assert result["differences"] == []


def test_shifted_reference_layout_needs_review() -> None:
    shifted = [
        ("7", (0.3704, 0.8074)),
        ("4", (0.7259, 0.8074)),
        ("4", (0.5704, 0.5948)),
        ("7", (0.8025, 0.4780)),
    ]
    result = evaluate_generated_against_reference(
        "LB26001-A-04-006",
        _metrics(4, {"7": 2, "4": 2}, 12, _layout_006()),
        _metrics(4, {"7": 2, "4": 2}, 12, shifted),
    )

    keys = [item["key"] for item in result["differences"]]
    assert result["status"] == "need_review"
    assert result["pass"] is False
    assert result["layout_style_score"] < 1.0
    assert "view_layout_center_shifted_from_reference" in keys


def test_missing_generated_layout_metrics_needs_review() -> None:
    result = evaluate_generated_against_reference(
        "LB26001-A-04-006",
        _metrics(4, {"7": 2, "4": 2}, 12, _layout_006()),
        _metrics(4, {"7": 2, "4": 2}, 12),
    )

    keys = [item["key"] for item in result["differences"]]
    assert result["status"] == "need_review"
    assert result["pass"] is False
    assert result["layout_style_score"] == 0.0
    assert "view_layout_metrics_unavailable" in keys


if __name__ == "__main__":
    test_reference_style_profile_derives_lb26001_rules()
    test_all_named_views_and_zero_display_dims_fail_style_gate()
    test_reference_view_count_overproduction_needs_review()
    test_reference_view_type_distribution_must_match()
    test_reference_display_dim_overproduction_needs_review()
    test_matching_reference_layout_passes_style_gate()
    test_shifted_reference_layout_needs_review()
    test_missing_generated_layout_metrics_needs_review()
    print("PASS test_v3_reference_style_profile")
