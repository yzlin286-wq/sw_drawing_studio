from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.validation.visual_audit_schema_gap_v4_4 import build_visual_audit_schema_gap


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _write_file(path: Path, data: bytes = b"ok") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _fixture(
    root: Path,
    *,
    raw_pass: bool = True,
    normalized_pass: bool = True,
    final_report: bool = True,
    visual_audit_index: bool = True,
    full_scope_allowed: bool = True,
) -> dict[str, Path]:
    paths = {
        "raw": root / "issue_schema_validation.json",
        "normalized": root / "issue_schema_validation_normalized.json",
        "product_gate": root / "product_evidence_gate_v4_4.json",
        "index": root / "visual_audit_index.json",
        "report": root / "visual_audit_report_v3_0.xlsx",
    }
    _write_json(
        paths["raw"],
        {
            "schema": "sw_drawing_studio.issue_schema_validation.v1",
            "status": "pass" if raw_pass else "fail",
            "pass": raw_pass,
            "issue_count": 10,
            "noncompliant_issue_count": 0 if raw_pass else 7,
            "failure_bucket": [] if raw_pass else ["vision_issue_schema_incomplete"],
            "missing_field_counts": {} if raw_pass else {"human_review_status": 7, "evidence": 6},
            "invalid_field_counts": {} if raw_pass else {"issue_must_be_object": 3},
            "top_failure_files": [] if raw_pass else [{"file": "legacy.json", "failure_count": 7}],
        },
    )
    _write_json(
        paths["normalized"],
        {
            "schema": "sw_drawing_studio.issue_schema_validation.v1",
            "status": "pass" if normalized_pass else "fail",
            "pass": normalized_pass,
            "issue_count": 10,
            "noncompliant_issue_count": 0 if normalized_pass else 1,
            "failure_bucket": [] if normalized_pass else ["normalized_issue_schema_incomplete"],
        },
    )
    _write_json(
        paths["product_gate"],
        {
            "schema": "sw_drawing_studio.product_evidence_gate.v4_4",
            "status": "pass" if full_scope_allowed else "blocked_by_solidworks_readiness",
            "pass": full_scope_allowed,
            "allowed_actions": {"visual_audit_full_scope_allowed": full_scope_allowed},
            "blocking_issue_keys": [] if full_scope_allowed else ["solidworks_readiness_for_006"],
        },
    )
    if visual_audit_index:
        _write_json(paths["index"], {"generated_at": "2026-06-26", "total_files": 3, "total_bases": 2})
    if final_report:
        _write_file(paths["report"])
    return paths


def _build(paths: dict[str, Path]) -> dict:
    return build_visual_audit_schema_gap(
        raw_issue_schema_path=paths["raw"],
        normalized_issue_schema_path=paths["normalized"],
        product_gate_path=paths["product_gate"],
        visual_audit_index_path=paths["index"],
        visual_audit_report_path=paths["report"],
    )


def test_visual_audit_schema_gap_can_pass_complete_fixture() -> None:
    with TemporaryDirectory() as tmp:
        result = _build(_fixture(Path(tmp)))

        assert result["pass"] is True
        assert result["status"] == "pass"
        assert result["release_ready"] is False
        assert result["visual_audit_schema_evidence_pass"] is True
        assert result["normalized_supporting_only"] is True
        assert result["normalized_cannot_replace_raw"] is True
        assert not result["blocking_issue_keys"]


def test_visual_audit_schema_gap_blocks_raw_failure_even_when_normalized_passes() -> None:
    with TemporaryDirectory() as tmp:
        result = _build(
            _fixture(
                Path(tmp),
                raw_pass=False,
                normalized_pass=True,
                final_report=False,
                full_scope_allowed=False,
            )
        )

        assert result["pass"] is False
        assert result["status"] == "raw_issue_schema_noncompliant"
        assert result["raw_noncompliant_issue_count"] == 7
        assert result["normalized_issue_schema_pass"] is True
        assert result["normalized_supporting_only"] is True
        assert result["normalized_cannot_replace_raw"] is True
        assert "raw_issue_schema_pass" in set(result["blocking_issue_keys"])
        assert "final_visual_audit_report_present" in set(result["blocking_issue_keys"])
        assert "visual_audit_full_scope_allowed" in set(result["blocking_issue_keys"])
        assert result["raw_issue_schema_summary"]["missing_field_counts_top"]["human_review_status"] == 7


def test_visual_audit_schema_gap_blocks_missing_final_report() -> None:
    with TemporaryDirectory() as tmp:
        result = _build(_fixture(Path(tmp), final_report=False))

        assert result["pass"] is False
        assert result["status"] == "blocked_by_missing_final_visual_audit_report"
        assert result["visual_audit_report_final_present"] is False
        assert "final_visual_audit_report_present" in set(result["blocking_issue_keys"])


def test_visual_audit_schema_gap_blocks_validation_sequence() -> None:
    with TemporaryDirectory() as tmp:
        result = _build(_fixture(Path(tmp), full_scope_allowed=False))

        assert result["pass"] is False
        assert result["status"] == "blocked_by_validation_sequence"
    assert result["visual_audit_full_scope_allowed_now"] is False
    assert "visual_audit_full_scope_allowed" in set(result["blocking_issue_keys"])


def test_visual_audit_schema_gap_includes_repair_plan_as_supporting_only() -> None:
    with TemporaryDirectory() as tmp:
        paths = _fixture(
            Path(tmp),
            raw_pass=False,
            normalized_pass=True,
            final_report=False,
            full_scope_allowed=False,
        )
        repair_plan = _write_json(
            Path(tmp) / "visual_audit_raw_issue_repair_plan_v4_4.json",
            {
                "schema": "sw_drawing_studio.visual_audit_raw_issue_repair_plan.v4_4",
                "status": "repair_overlay_ready_requires_raw_backfill",
                "pass": True,
                "release_ready": False,
                "raw_noncompliant_issue_count": 7,
                "missing_replacement_count": 0,
                "lossy_normalized_issue_count": 5,
                "normalized_cannot_replace_raw": True,
                "historical_artifacts_modified": False,
            },
        )

        result = build_visual_audit_schema_gap(
            raw_issue_schema_path=paths["raw"],
            normalized_issue_schema_path=paths["normalized"],
            product_gate_path=paths["product_gate"],
            visual_audit_index_path=paths["index"],
            visual_audit_report_path=paths["report"],
            raw_issue_repair_plan_path=repair_plan,
        )

        assert result["pass"] is False
        assert result["status"] == "raw_issue_schema_noncompliant"
        assert "raw_issue_schema_pass" in set(result["blocking_issue_keys"])
        assert result["raw_issue_repair_plan_present"] is True
        assert result["raw_issue_repair_plan_ready"] is True
        assert result["raw_issue_repair_plan_cannot_replace_raw"] is True
        assert result["raw_issue_repair_plan_summary"]["lossy_normalized_issue_count"] == 5


def test_visual_audit_schema_gap_includes_backfill_overlay_as_supporting_only() -> None:
    with TemporaryDirectory() as tmp:
        paths = _fixture(
            Path(tmp),
            raw_pass=False,
            normalized_pass=True,
            final_report=False,
            full_scope_allowed=False,
        )
        overlay = _write_json(
            Path(tmp) / "visual_audit_raw_issue_backfill_overlay_v4_4.json",
            {
                "schema": "sw_drawing_studio.visual_audit_raw_issue_backfill_overlay.v4_4",
                "status": "overlay_ready_requires_human_review",
                "pass": True,
                "release_ready": False,
                "raw_failure_count": 7,
                "overlay_record_count": 7,
                "missing_replacement_count": 0,
                "lossy_overlay_record_count": 5,
                "normalized_cannot_replace_raw": True,
                "historical_artifacts_modified": False,
                "output_jsonl": {"line_count": 7, "sha256": "abc123"},
            },
        )

        result = build_visual_audit_schema_gap(
            raw_issue_schema_path=paths["raw"],
            normalized_issue_schema_path=paths["normalized"],
            product_gate_path=paths["product_gate"],
            visual_audit_index_path=paths["index"],
            visual_audit_report_path=paths["report"],
            raw_issue_backfill_overlay_path=overlay,
        )

        assert result["pass"] is False
        assert result["status"] == "raw_issue_schema_noncompliant"
        assert "raw_issue_schema_pass" in set(result["blocking_issue_keys"])
        assert result["raw_issue_backfill_overlay_present"] is True
        assert result["raw_issue_backfill_overlay_ready"] is True
        assert result["raw_issue_backfill_overlay_cannot_replace_raw"] is True
        assert result["raw_issue_backfill_overlay_summary"]["overlay_record_count"] == 7
        assert result["raw_issue_backfill_overlay_summary"]["jsonl_sha256"] == "abc123"


def test_visual_audit_schema_gap_tool_is_file_only() -> None:
    source = Path("tools/validation/visual_audit_schema_gap_v4_4.py").read_text(encoding="utf-8")
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
    test_visual_audit_schema_gap_can_pass_complete_fixture()
    test_visual_audit_schema_gap_blocks_raw_failure_even_when_normalized_passes()
    test_visual_audit_schema_gap_blocks_missing_final_report()
    test_visual_audit_schema_gap_blocks_validation_sequence()
    test_visual_audit_schema_gap_includes_repair_plan_as_supporting_only()
    test_visual_audit_schema_gap_includes_backfill_overlay_as_supporting_only()
    test_visual_audit_schema_gap_tool_is_file_only()
    print("PASS test_v4_4_visual_audit_schema_gap")
