import json
from pathlib import Path

from app.services.vision_issue_schema import REQUIRED_ISSUE_FIELDS, normalize_issue
from tools.validation.issue_schema_validation_v3 import validate_issue_schema


def test_normalize_legacy_string_issue_has_complete_schema(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    issue = normalize_issue(
        "标题栏缺少图号",
        source_file="drw_output/legacy/vision.json",
        issue_path="$.issues[0]",
    )

    for field in REQUIRED_ISSUE_FIELDS:
        assert field in issue
    assert issue["key"]
    assert issue["severity"] == "major"
    assert issue["bbox"] == [0.0, 0.0, 1.0, 1.0]
    assert issue["source"] == "legacy"
    assert issue["confidence"] == 0.0
    assert issue["auto_fix_available"] is False
    assert issue["human_review_status"] == "pending"
    assert issue["normalization"]["status"] == "normalized_with_warnings"
    assert "issue_was_not_object" in issue["normalization"]["warnings"]

    report = tmp_path / "normalized.json"
    report.write_text(
        '{"issues": [' + json.dumps(issue, ensure_ascii=False) + "]}",
        encoding="utf-8",
    )
    validation = validate_issue_schema([report])
    assert validation["pass"] is True


def test_normalize_partial_dict_preserves_valid_zero_confidence(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    issue = normalize_issue(
        {
            "key": "bad_bbox",
            "severity": "warning",
            "bbox": [10, 20, 30, 40],
            "confidence": 0,
            "fix": "重新检查视图布局。",
        },
        source_file="drw_output/legacy/vision.json",
        issue_path="$.checks.layout.issues[0]",
        default_source="template",
    )

    assert issue["severity"] == "minor"
    assert issue["bbox"] == [0.1, 0.2, 0.3, 0.4]
    assert issue["source"] == "template"
    assert issue["confidence"] == 0.0
    assert issue["fix_suggestion"] == "重新检查视图布局。"
    assert issue["auto_fix_available"] is False
    assert issue["human_review_status"] == "pending"
    assert "confidence_missing_or_invalid_default_zero" not in issue["normalization"]["warnings"]

    report = tmp_path / "normalized.json"
    report.write_text(
        '{"issues": [' + json.dumps(issue, ensure_ascii=False) + "]}",
        encoding="utf-8",
    )
    validation = validate_issue_schema([report])
    assert validation["pass"] is True


if __name__ == "__main__":
    test_normalize_legacy_string_issue_has_complete_schema(Path("drw_output/_issue_normalizer_test/string"))
    test_normalize_partial_dict_preserves_valid_zero_confidence(Path("drw_output/_issue_normalizer_test/dict"))
    print("PASS test_v3_vision_issue_schema_normalizer")
