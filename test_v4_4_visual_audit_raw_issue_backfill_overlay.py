from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.validation.visual_audit_raw_issue_backfill_overlay_v4_4 import build_overlay


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _fixture(root: Path, *, missing_replacement: bool = False) -> dict[str, Path]:
    raw_file = root / "drw_output" / "runs" / "abc" / "qc" / "vision_qc.json"
    raw = _write_json(
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
    replacement_path = "$.issues[99]" if missing_replacement else "$.issues[0]"
    normalized = _write_json(
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
                    "evidence": {
                        "source_file": "drw_output/runs/abc/qc/vision_qc.json",
                        "issue_path": replacement_path,
                    },
                    "fix_suggestion": "Review raw issue.",
                    "auto_fix_available": False,
                    "human_review_status": "pending",
                    "normalization": {
                        "source_file": "drw_output/runs/abc/qc/vision_qc.json",
                        "issue_path": replacement_path,
                        "warnings": [
                            "issue_was_not_object",
                            "bbox_missing_or_invalid_default_full_page",
                            "confidence_missing_or_invalid_default_zero",
                            "evidence_missing_synthesized_from_legacy_record",
                        ],
                    },
                }
            ],
        },
    )
    return {"raw": raw, "normalized": normalized}


def test_raw_issue_backfill_overlay_writes_traceable_jsonl() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        paths = _fixture(root)
        out_jsonl = root / "overlay.jsonl"
        out_summary = root / "summary.json"
        out_md = root / "summary.md"

        result = build_overlay(
            raw_issue_schema_path=paths["raw"],
            normalized_index_path=paths["normalized"],
            out_jsonl=out_jsonl,
            out_summary=out_summary,
            out_md=out_md,
        )

        assert result["status"] == "overlay_ready_requires_human_review"
        assert result["pass"] is True
        assert result["release_ready"] is False
        assert result["historical_artifacts_modified"] is False
        assert result["normalized_cannot_replace_raw"] is True
        assert result["raw_schema_replacement_allowed"] is False
        assert result["raw_failure_count"] == 1
        assert result["overlay_record_count"] == 1
        assert result["missing_replacement_count"] == 0
        assert result["lossy_overlay_record_count"] == 1
        assert result["output_jsonl"]["line_count"] == 1
        assert result["output_jsonl"]["sha256"]
        assert out_summary.exists()
        assert out_md.exists()
        line = json.loads(out_jsonl.read_text(encoding="utf-8").strip())
        assert line["schema"] == "sw_drawing_studio.visual_audit_raw_issue_backfill_overlay_record.v4_4"
        assert line["source_file"] == "drw_output/runs/abc/qc/vision_qc.json"
        assert line["issue_path"] == "$.issues[0]"
        assert line["requires_human_review"] is True
        assert line["normalized_issue"]["key"] == "legacy_string_issue"


def test_raw_issue_backfill_overlay_blocks_missing_replacement() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        paths = _fixture(root, missing_replacement=True)

        result = build_overlay(
            raw_issue_schema_path=paths["raw"],
            normalized_index_path=paths["normalized"],
        )

        assert result["status"] == "overlay_incomplete"
        assert result["pass"] is False
        assert result["overlay_record_count"] == 0
        assert result["missing_replacement_count"] == 1
        assert result["missing_replacements"][0]["issue_path"] == "$.issues[0]"


def test_raw_issue_backfill_overlay_tool_is_file_only() -> None:
    source = Path("tools/validation/visual_audit_raw_issue_backfill_overlay_v4_4.py").read_text(encoding="utf-8")
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
    test_raw_issue_backfill_overlay_writes_traceable_jsonl()
    test_raw_issue_backfill_overlay_blocks_missing_replacement()
    test_raw_issue_backfill_overlay_tool_is_file_only()
    print("PASS test_v4_4_visual_audit_raw_issue_backfill_overlay")
