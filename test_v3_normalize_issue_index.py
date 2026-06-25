import json
from pathlib import Path

from tools.validation.issue_schema_validation_v3 import validate_issue_schema
from tools.validation.normalize_issue_index_v3 import build_normalized_issue_index


def test_normalized_issue_index_converts_legacy_sources(tmp_path: Path) -> None:
    root = tmp_path / "source"
    root.mkdir(parents=True, exist_ok=True)
    source = root / "vision_qc_legacy.json"
    source.write_text(
        json.dumps(
            {
                "issues": [
                    "legacy_titlebar_missing",
                    {
                        "key": "dimension_overlap",
                        "bbox": [0.2, 0.3, 0, 0.1],
                        "score": 82,
                    },
                ],
                "nested": {
                    "issues": [
                        {
                            "description": "视图越框",
                            "severity": "critical",
                            "bbox": [0.7, 0.1, 0.2, 0.2],
                            "source": "geometry_qc",
                            "confidence": 0.95,
                            "evidence": {"check": "frame_bounds"},
                            "fix_suggestion": "调整比例或视图位置。",
                            "auto_fix_available": True,
                            "human_review_status": "pending",
                        }
                    ]
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    out = tmp_path / "normalized_issue_index.json"
    payload = build_normalized_issue_index([root], out)
    validation = validate_issue_schema([out])

    assert payload["pass"] is True
    assert payload["issue_count"] == 3
    assert payload["files_with_issues"] == 1
    assert payload["normalization_warning_count"] > 0
    assert validation["pass"] is True
    assert validation["issue_count"] == 3
    assert validation["noncompliant_issue_count"] == 0


if __name__ == "__main__":
    test_normalized_issue_index_converts_legacy_sources(Path("drw_output/_issue_index_test"))
    print("PASS test_v3_normalize_issue_index")
