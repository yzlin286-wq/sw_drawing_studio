from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.validation.staged_batch_sequence_gate_v4_4 import (
    REQUIRED_SEQUENCE,
    build_staged_batch_sequence_gate,
)


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _cad_report(path: Path) -> Path:
    return _write_json(
        path,
        {
            "status": "pass",
            "pass": True,
            "checks": [
                {"key": "facade_submitted", "pass": True},
                {"key": "worker_jsonl_events", "pass": True},
                {"key": "artifact_manifest", "pass": True},
                {"key": "artifact_job_event_log", "pass": True},
            ],
            "artifacts": {
                "manifest": {"exists": True},
                "job_event_log": {"exists": True},
            },
        },
    )


def _summary(
    root: Path,
    stage: str,
    *,
    strict_contract: bool = True,
    pass_stage: bool = True,
    generated_at: str = "2026-06-26 10:00:00",
) -> Path:
    case_dir = root / stage / "case01"
    cad_report = _cad_report(case_dir / "cad_smoke.json")
    total = 1
    deliverable = 1 if pass_stage else 0
    payload = {
        "schema": "sw_drawing_studio.staged_cad_validation.v1",
        "stage": stage,
        "generated_at": generated_at,
        "total": total,
        "processed": total,
        "deliverable_count": deliverable,
        "required_deliverable_count": total,
        "execution_completed": True,
        "acceptance_pass": pass_stage,
        "status": "pass" if pass_stage else "need_review",
        "pass": pass_stage,
        "solidworks_lock_owned": strict_contract,
        "used_job_runtime_facade": strict_contract,
        "used_qprocess": strict_contract,
        "application_ui_screenshot_evidence": strict_contract,
        "api_only_acceptance_allowed": False,
        "artifact_contract_pass": strict_contract,
        "cases": [
            {
                "part_name": f"{stage}_fixture",
                "case_dir": str(case_dir),
                "run_id": f"{stage}_run",
                "run_dir": str(root / "runs" / f"{stage}_run"),
                "cad_report": str(cad_report),
                "deliverable": bool(pass_stage),
                "status": "pass" if pass_stage else "need_review",
                "api_only_acceptance_allowed": False,
            }
        ],
    }
    return _write_json(root / stage / "summary.json", payload)


def _build(root: Path, summaries: dict[str, Path]) -> dict:
    return build_staged_batch_sequence_gate(
        stage_summaries=summaries,
        stage_root=root,
        out_json=root / "staged_batch_sequence_gate_v4_4.json",
        out_md=root / "staged_batch_sequence_gate_v4_4.md",
    )


def test_staged_batch_sequence_gate_can_pass_complete_contract() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        summaries = {stage: _summary(root, stage) for stage in REQUIRED_SEQUENCE}

        result = _build(root, summaries)

        assert result["pass"] is True
        assert result["status"] == "pass"
        assert result["visual_audit_allowed_after_medium_30"] is True
        assert result["full_129_allowed_after_visual_audit"] is True
        assert result["stage_generated_at_sequence_order_pass"] is True
        assert not result["blocking_issue_keys"]


def test_staged_batch_sequence_gate_rejects_legacy_summary_without_ui_contract() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        summaries = {
            stage: _summary(root, stage, strict_contract=(stage != "LB26001_36"))
            for stage in REQUIRED_SEQUENCE
        }

        result = _build(root, summaries)

        assert result["pass"] is False
        assert result["status"] == "pending"
        assert result["visual_audit_allowed_after_medium_30"] is False
        assert "LB26001_36_application_ui_screenshot_evidence" in result["blocking_issue_keys"]
        stage = next(item for item in result["stages"] if item["stage"] == "LB26001_36")
        assert stage["pass"] is False
        assert "application_ui_screenshot_evidence" in stage["mismatch_keys"]


def test_staged_batch_sequence_gate_rejects_missing_medium30() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        summaries = {stage: _summary(root, stage) for stage in REQUIRED_SEQUENCE if stage != "medium_30"}

        result = _build(root, summaries)

        assert result["pass"] is False
        assert result["status"] == "pending"
        assert "required_sequence_missing_or_out_of_order" in result["blocking_issue_keys"]
        assert "medium_30_summary_missing" in result["blocking_issue_keys"]


def test_staged_batch_sequence_gate_rejects_timestamp_order_inversion() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        generated_at_by_stage = {
            "024_040": "2026-06-26 10:10:00",
            "core_12": "2026-06-26 10:05:00",
            "LB26001_36": "2026-06-26 10:20:00",
            "medium_30": "2026-06-26 10:30:00",
        }
        summaries = {
            stage: _summary(root, stage, generated_at=generated_at_by_stage[stage])
            for stage in REQUIRED_SEQUENCE
        }

        result = _build(root, summaries)

        assert result["pass"] is False
        assert result["status"] == "pending"
        assert result["stage_generated_at_sequence_order_pass"] is False
        assert "stage_generated_at_sequence_order" in result["blocking_issue_keys"]
        assert result["visual_audit_allowed_after_medium_30"] is False
        assert result["full_129_allowed_after_visual_audit"] is False
        assert result["stage_generated_at_sequence_order"]["order_violations"] == [
            {
                "previous_stage": "024_040",
                "previous_generated_at": "2026-06-26 10:10:00",
                "stage": "core_12",
                "generated_at": "2026-06-26 10:05:00",
            }
        ]


def test_staged_batch_sequence_gate_tool_is_file_only() -> None:
    source = Path("tools/validation/staged_batch_sequence_gate_v4_4.py").read_text(encoding="utf-8")
    forbidden = [
        "win32com",
        "pythoncom",
        "GetActiveObject",
        "Dispatch(",
        "OpenDoc6",
        "subprocess.run",
    ]
    for token in forbidden:
        assert token not in source


if __name__ == "__main__":
    test_staged_batch_sequence_gate_can_pass_complete_contract()
    test_staged_batch_sequence_gate_rejects_legacy_summary_without_ui_contract()
    test_staged_batch_sequence_gate_rejects_missing_medium30()
    test_staged_batch_sequence_gate_rejects_timestamp_order_inversion()
    test_staged_batch_sequence_gate_tool_is_file_only()
    print("PASS test_v4_4_staged_batch_sequence_gate")
