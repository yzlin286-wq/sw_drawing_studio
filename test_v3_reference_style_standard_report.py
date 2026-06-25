import json
from pathlib import Path

from tools.validation.reference_style_standard_report_v3 import (
    build_standard,
    render_markdown,
    write_standard_reports,
)


SHEET_W = 0.297
SHEET_H = 0.21


def _view(vtype: str, center_norm: tuple[float, float]) -> dict:
    cx = center_norm[0] * SHEET_W
    cy = center_norm[1] * SHEET_H
    return {
        "name": f"view_{vtype}",
        "type": vtype,
        "outline_m": [cx - 0.01, cy - 0.01, cx + 0.01, cy + 0.01],
        "center_m": [cx, cy],
        "center_norm": [center_norm[0], center_norm[1]],
    }


def _sample(base: str, views: int, types: dict[str, int], dims: int) -> dict:
    layout = [
        _view("7", (0.37, 0.80)),
        _view("4", (0.72, 0.80)),
        _view("4", (0.37, 0.58)),
        _view("7", (0.80, 0.48)),
    ][:views]
    return {
        "base": base,
        "path": f"C:/ref/{base}.SLDDRW",
        "success": True,
        "view_count": views,
        "view_types": types,
        "display_dim_count": dims,
        "annotation_count": 0,
        "sheet_size_m": {"width": SHEET_W, "height": SHEET_H},
        "view_layout": layout,
    }


def test_standard_report_builds_machine_rules_and_markdown(tmp_path: Path) -> None:
    profile = {
        "status": "profile_ready",
        "generated_at": "2026-06-22 07:06:31",
        "reference_samples": {
            "LB26001-A-04-006": _sample("LB26001-A-04-006", 4, {"7": 2, "4": 2}, 12),
            "LB26001-A-04-008": _sample("LB26001-A-04-008", 2, {"7": 1, "4": 1}, 2),
        },
    }
    gap = {
        "status": "fail",
        "pass": False,
        "sample_count": 2,
        "pass_count": 0,
        "need_review_count": 0,
        "fail_count": 2,
        "cases": [
            {"differences": [{"key": "view_type_count_lower_than_reference"}]},
            {"differences": [{"key": "display_dim_count_lower_than_reference"}]},
        ],
    }

    standard = build_standard(profile, gap)
    markdown = render_markdown(standard)

    assert standard["status"] == "standard_ready"
    assert standard["sample_count"] == 2
    sample_006 = standard["sample_rules"][0]
    assert sample_006["required_view_count"] == 4
    assert sample_006["required_view_types"] == {"7": 2, "4": 2}
    assert sample_006["display_dim_floor"] == 12
    assert sample_006["section_policy"]["automatic_section_or_detail_allowed"] is False
    assert "LB26001 参考图纸制图规范" in markdown
    assert "禁止自动新增剖视/详图" in markdown
    assert "view_type_count_lower_than_reference" in markdown

    out_json = tmp_path / "standard.json"
    out_md = tmp_path / "standard.md"
    write_standard_reports(standard, out_json, out_md)
    assert json.loads(out_json.read_text(encoding="utf-8"))["sample_count"] == 2
    assert "DisplayDim 下限" in out_md.read_text(encoding="utf-8")


if __name__ == "__main__":
    test_standard_report_builds_machine_rules_and_markdown(Path("drw_output/_reference_standard_report_test"))
    print("PASS test_v3_reference_style_standard_report")
