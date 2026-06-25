from pathlib import Path

from tools.validation.issue_schema_validation_v3 import validate_issue_schema


def test_issue_schema_accepts_complete_issue(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    report = tmp_path / "vision_qc_v2.json"
    report.write_text(
        """
{
  "issues": [
    {
      "key": "titlebar_missing",
      "severity": "minor",
      "bbox": [0.7, 0.85, 0.2, 0.1],
      "source": "geometry_qc",
      "confidence": 0.82,
      "evidence": {"field": "图号"},
      "fix_suggestion": "补齐标题栏图号。",
      "auto_fix_available": true,
      "human_review_status": "pending"
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )

    result = validate_issue_schema([report])

    assert result["pass"] is True
    assert result["status"] == "pass"
    assert result["issue_count"] == 1
    assert result["noncompliant_issue_count"] == 0


def test_issue_schema_rejects_legacy_or_incomplete_issue(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    report = tmp_path / "vision_qc_v2.json"
    report.write_text(
        """
{
  "issues": [
    "legacy_string_issue",
    {
      "key": "bad_bbox",
      "severity": "major",
      "bbox": [0.1, 0.2, 0, 0.2],
      "source": "template",
      "confidence": 1.2,
      "fix_suggestion": "",
      "auto_fix_available": "yes"
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )

    result = validate_issue_schema([report])

    assert result["pass"] is False
    assert result["status"] == "fail"
    assert result["issue_count"] == 2
    assert result["noncompliant_issue_count"] == 2
    assert result["failure_bucket"] == ["vision_issue_schema_incomplete"]
    all_missing = {field for item in result["failures"] for field in item["missing_fields"]}
    all_invalid = {field for item in result["failures"] for field in item["invalid_fields"]}
    assert "human_review_status" in all_missing
    assert "issue_must_be_object" in all_invalid
    assert "bbox_width_height_must_be_positive" in all_invalid
    assert "confidence_must_be_0_to_1" in all_invalid
    assert "auto_fix_available_must_be_boolean" in all_invalid
    assert result["missing_field_counts"]["human_review_status"] == 2
    assert result["invalid_field_counts"]["issue_must_be_object"] == 1
    assert result["top_failure_files"][0]["failure_count"] == 2


if __name__ == "__main__":
    test_issue_schema_accepts_complete_issue(Path("drw_output/_issue_schema_test/pass"))
    test_issue_schema_rejects_legacy_or_incomplete_issue(Path("drw_output/_issue_schema_test/fail"))
    print("PASS test_v3_issue_schema_validation")
