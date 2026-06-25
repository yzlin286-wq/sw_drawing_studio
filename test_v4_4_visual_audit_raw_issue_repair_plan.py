from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.validation.visual_audit_raw_issue_repair_plan_v4_4 import build_repair_plan


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _fixture(root: Path, *, missing_replacement: bool = False) -> dict[str, Path]:
    raw_file = root / "drw_output" / "runs" / "abc" / "qc" / "vision_qc.json"
    raw_path = _write_json(
        root / "issue_schema_validation.json",
        {
            "schema": "sw_drawing_studio.issue_schema_validation.v1",
            "status": "fail",
            "pass": False,
            "issue_count": 2,
            "noncompliant_issue_count": 1,
            "failures": [
                {
                    "file": str(raw_file),
                    "issue_path": "$.issues[0]",
                    "issue_key": "legacy_string_issue",
                    "missing_fields": ["key", "bbox", "evidence"],
                    "invalid_fields": ["issue_must_be_object"],
                }
            ],
        },
    )
    normalized_validation_path = _write_json(
        root / "issue_schema_validation_normalized.json",
        {
            "schema": "sw_drawing_studio.issue_schema_validation.v1",
            "status": "pass",
            "pass": True,
            "issue_count": 2,
            "noncompliant_issue_count": 0,
        },
    )
    normalized_issue_path = "$.issues[99]" if missing_replacement else "$.issues[0]"
    normalized_index_path = _write_json(
        root / "visual_audit" / "normalized_issue_index.json",
        {
            "schema": "sw_drawing_studio.normalized_issue_index.v1",
            "status": "pass",
            "pass": True,
            "issue_count": 2,
            "issues": [
                {
                    "key": "legacy_string_issue",
                    "severity": "major",
                    "bbox": [0.0, 0.0, 1.0, 1.0],
                    "source": "historical_visual_audit",
                    "confidence": 0.0,
                    "evidence": {"source_file": "drw_output/runs/abc/qc/vision_qc.json", "issue_path": normalized_issue_path},
                    "fix_suggestion": "Review raw issue.",
                    "auto_fix_available": False,
                    "human_review_status": "pending",
                    "normalization": {
                        "source_file": "drw_output/runs/abc/qc/vision_qc.json",
                        "issue_path": normalized_issue_path,
                        "warnings": [
                            "issue_was_not_object",
                            "bbox_missing_or_invalid_default_full_page",
                            "confidence_missing_or_invalid_default_zero",
                            "evidence_missing_synthesized_from_legacy_record",
                        ],
                    },
                },
                {
                    "key": "already_complete",
                    "severity": "minor",
                    "bbox": [0.1, 0.1, 0.2, 0.2],
                    "source": "vision_qc_v5",
                    "confidence": 0.8,
                    "evidence": {"source_file": "drw_output/runs/abc/qc/vision_qc.json", "issue_path": "$.issues[1]"},
                    "fix_suggestion": "None.",
                    "auto_fix_available": False,
                    "human_review_status": "pending",
                    "normalization": {
                        "source_file": "drw_output/runs/abc/qc/vision_qc.json",
                        "issue_path": "$.issues[1]",
                        "warnings": [],
                    },
                },
            ],
        },
    )
    return {
        "raw": raw_path,
        "normalized_validation": normalized_validation_path,
        "normalized_index": normalized_index_path,
    }


def test_raw_issue_repair_plan_tracks_complete_normalized_replacements() -> None:
    with TemporaryDirectory() as tmp:
        paths = _fixture(Path(tmp))

        result = build_repair_plan(
            raw_issue_schema_path=paths["raw"],
            normalized_issue_schema_path=paths["normalized_validation"],
            normalized_index_path=paths["normalized_index"],
        )

        assert result["status"] == "repair_overlay_ready_requires_raw_backfill"
        assert result["pass"] is True
        assert result["release_ready"] is False
        assert result["historical_artifacts_modified"] is False
        assert result["normalized_cannot_replace_raw"] is True
        assert result["normalized_records_for_all_raw_failures"] is True
        assert result["missing_replacement_count"] == 0
        assert result["lossy_normalized_issue_count"] == 1
        assert result["requires_human_review_for_lossy_records"] is True
        assert result["allowed_next_actions"]["use_as_release_pass"] is False
        assert result["allowed_next_actions"]["write_back_after_user_approval_and_backup"] is True


def test_raw_issue_repair_plan_blocks_when_replacement_trace_is_missing() -> None:
    with TemporaryDirectory() as tmp:
        paths = _fixture(Path(tmp), missing_replacement=True)

        result = build_repair_plan(
            raw_issue_schema_path=paths["raw"],
            normalized_issue_schema_path=paths["normalized_validation"],
            normalized_index_path=paths["normalized_index"],
        )

        assert result["status"] == "repair_overlay_incomplete"
        assert result["pass"] is False
        assert result["normalized_records_for_all_raw_failures"] is False
        assert result["missing_replacement_count"] == 1
        assert result["missing_replacements"][0]["issue_path"] == "$.issues[0]"


def test_raw_issue_repair_plan_tool_is_file_only() -> None:
    source = Path("tools/validation/visual_audit_raw_issue_repair_plan_v4_4.py").read_text(encoding="utf-8")
    forbidden = [
        "win32com",
        "pythoncom",
        "GetActiveObject",
        "Dispatch(",
        "OpenDoc6",
        "QProcess",
        "subprocess.run",
        "JobRuntimeFacade",
        "JobRunner",
        "start_cad_job",
    ]
    for token in forbidden:
        assert token not in source


if __name__ == "__main__":
    test_raw_issue_repair_plan_tracks_complete_normalized_replacements()
    test_raw_issue_repair_plan_blocks_when_replacement_trace_is_missing()
    test_raw_issue_repair_plan_tool_is_file_only()
    print("PASS test_v4_4_visual_audit_raw_issue_repair_plan")
