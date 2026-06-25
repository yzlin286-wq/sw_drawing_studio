from __future__ import annotations

import json
import shutil
from pathlib import Path

from app.services.final_quality import compute_final_quality
from app.services.vision_qc_v2 import run_vision_qc_v2


ROOT = Path(__file__).resolve().parent
FIXTURE_DIR = ROOT / "drw_output" / "_vision_qc_v2_policy_test"


class _Ctx:
    hard_fail: list[str] = []
    warnings: list[str] = ["dim_total_below_threshold"]
    drawing_usable = {"pass": True}
    dimension_grade = "B"
    usable_for = ["manufacturing", "assembly", "procurement"]
    drawing_accuracy_score = {"total": 72}


def _write_case(name: str, qc: dict) -> tuple[Path, Path, Path]:
    run_dir = FIXTURE_DIR / name
    if run_dir.exists():
        shutil.rmtree(run_dir)
    qc_dir = run_dir / "qc"
    drawing_dir = run_dir / "drawing"
    qc_dir.mkdir(parents=True)
    drawing_dir.mkdir(parents=True)
    qc_path = qc_dir / "fixture_qc.json"
    png_path = drawing_dir / "fixture.png"
    qc_path.write_text(json.dumps(qc, ensure_ascii=False, indent=2), encoding="utf-8")
    png_path.write_bytes(b"png placeholder")
    return run_dir, qc_path, png_path


def _base_qc() -> dict:
    return {
        "checks": {
            "dim_count_sufficient": {"dim_total": 4},
            "dimension_coverage": {"associativity": "model"},
            "text_height_ge_3_5mm": {"pass": True},
        },
        "hard_fail": [],
        "warnings": [],
        "display_dim_count": 4,
        "note_dim_count": 4,
    }


def _assert_issue_schema(result: dict) -> None:
    required = {
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
    assert result["issues"], "expected at least one issue"
    for issue in result["issues"]:
        missing = required - set(issue)
        assert not missing, f"missing fields {missing} in {issue}"


def test_tiny_part_sidecar_dimension_shortfall_is_warning() -> None:
    qc = _base_qc()
    qc.update(
        {
            "part_class": "tiny_part",
            "dimension_grade": "B",
            "has_valid_sidecar_annotation": True,
            "dimension_sources": {
                "sidecar_overall": {
                    "overall_length": 29.0,
                    "overall_width": 19.5,
                    "overall_height": 8.0,
                }
            },
        }
    )
    run_dir, qc_path, png_path = _write_case("tiny_part_sidecar", qc)

    result = run_vision_qc_v2(qc_path, png_path, run_dir)
    dim_issue = next(i for i in result["issues"] if i["key"] == "dimension_insufficient")

    assert dim_issue["severity"] == "minor"
    assert result["summary"]["major"] == 0
    assert dim_issue["evidence"]["policy"] == "tiny_or_long_thin_sidecar_dimension_warning"
    _assert_issue_schema(result)

    final_quality = compute_final_quality(_Ctx(), result, run_dir=run_dir)
    assert final_quality["status"] == "pass_with_warning"
    assert final_quality["deliverable"] is True


def test_feature_part_dimension_shortfall_remains_major() -> None:
    qc = _base_qc()
    qc.update(
        {
            "part_class": "feature_part",
            "dimension_grade": "D",
            "has_valid_sidecar_annotation": False,
        }
    )
    run_dir, qc_path, png_path = _write_case("feature_part_shortfall", qc)

    result = run_vision_qc_v2(qc_path, png_path, run_dir)
    dim_issue = next(i for i in result["issues"] if i["key"] == "dimension_insufficient")

    assert dim_issue["severity"] == "major"
    assert result["summary"]["major"] == 1
    assert dim_issue["evidence"]["policy"] == "manufacturing_display_dim_threshold"
    _assert_issue_schema(result)


if __name__ == "__main__":
    test_tiny_part_sidecar_dimension_shortfall_is_warning()
    test_feature_part_dimension_shortfall_remains_major()
    print("PASS test_v3_vision_qc_v2_policy")
