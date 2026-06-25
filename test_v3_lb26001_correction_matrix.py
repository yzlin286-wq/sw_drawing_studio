import json
from pathlib import Path

from tools.validation.lb26001_correction_matrix_v3 import (
    build_matrix,
    render_markdown,
    write_matrix_reports,
)


def _standard() -> dict:
    return {
        "status": "standard_ready",
        "sample_rules": [
            {
                "base": "LB26001-A-04-006",
                "reference_drawing": "C:/ref/LB26001-A-04-006.SLDDRW",
                "required_view_count": 4,
                "required_view_types": {"7": 2, "4": 2},
                "display_dim_floor": 12,
                "layout_slots_center_norm": {"front": [0.37, 0.80], "top": [0.37, 0.59]},
                "layout_tolerance_norm": 0.08,
                "section_policy": {"automatic_section_or_detail_allowed": False},
            },
            {
                "base": "LB26001-A-04-008",
                "reference_drawing": "C:/ref/LB26001-A-04-008.SLDDRW",
                "required_view_count": 2,
                "required_view_types": {"7": 1, "4": 1},
                "display_dim_floor": 2,
                "layout_slots_center_norm": {"front": [0.30, 0.70], "top": [0.30, 0.42]},
                "layout_tolerance_norm": 0.08,
                "section_policy": {"automatic_section_or_detail_allowed": False},
            },
        ],
    }


def _gap() -> dict:
    return {
        "status": "fail",
        "pass": False,
        "cases": [
            {
                "base": "LB26001-A-04-006",
                "status": "fail",
                "pass": False,
                "view_style_score": 0.4,
                "dimension_style_score": 0.0,
                "layout_style_score": 0.2,
                "overall_style_score": 0.2,
                "generated": {"path": "C:/generated/LB26001-A-04-006_v5.SLDDRW"},
                "differences": [
                    {"key": "generated_all_named_model_views"},
                    {"key": "display_dim_count_lower_than_reference"},
                    {"key": "generated_all_named_model_views"},
                ],
            },
            {
                "base": "LB26001-A-04-008",
                "status": "need_review",
                "pass": False,
                "differences": [{"key": "view_count_not_equal_reference"}],
            },
        ],
    }


def test_correction_matrix_contains_commands_and_gap_reasons(tmp_path: Path) -> None:
    ref_dir = tmp_path / "3D转2D测试图纸"
    ref_dir.mkdir(parents=True, exist_ok=True)
    for base in ["LB26001-A-04-006", "LB26001-A-04-008"]:
        (ref_dir / f"{base}.SLDPRT").write_text("fixture", encoding="utf-8")

    matrix = build_matrix(_standard(), _gap(), reference_dir=ref_dir)
    markdown = render_markdown(matrix)

    assert matrix["status"] == "ready_for_real_cad_when_solidworks_responds"
    assert matrix["pass"] is True
    assert matrix["sample_count"] == 2
    assert matrix["pilot_case"] == "LB26001-A-04-006"
    first = matrix["entries"][0]
    assert first["base"] == "LB26001-A-04-006"
    assert first["part_exists"] is True
    assert first["required_view_types"] == {"7": 2, "4": 2}
    assert first["display_dim_floor"] == 12
    assert "real_cad_smoke_v3.py" in first["command_templates"]["real_cad_smoke"]
    assert "generated_all_named_model_views" in first["current_difference_keys"]
    assert matrix["current_gap_difference_counts"]["generated_all_named_model_views"] == 1
    assert "LB26001 修正测试矩阵" in markdown
    assert "DisplayDim 下限" in markdown

    out_json = tmp_path / "matrix.json"
    out_md = tmp_path / "matrix.md"
    write_matrix_reports(matrix, out_json, out_md)
    assert json.loads(out_json.read_text(encoding="utf-8"))["sample_count"] == 2
    assert "六件样本全部通过后的下一步" in out_md.read_text(encoding="utf-8")


def test_correction_matrix_flags_missing_part(tmp_path: Path) -> None:
    matrix = build_matrix(_standard(), _gap(), reference_dir=tmp_path)

    assert matrix["status"] == "need_review"
    assert matrix["pass"] is False
    assert len(matrix["missing_part_paths"]) == 2


if __name__ == "__main__":
    test_correction_matrix_contains_commands_and_gap_reasons(Path("drw_output/_lb26001_matrix_test/ok"))
    test_correction_matrix_flags_missing_part(Path("drw_output/_lb26001_matrix_test/missing"))
    print("PASS test_v3_lb26001_correction_matrix")
