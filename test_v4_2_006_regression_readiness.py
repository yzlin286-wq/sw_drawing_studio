import json
import os
import time
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.validation.lb26001_006_regression_readiness_v4_2 import (
    DEFAULT_EXPANSION_GATE,
    DEFAULT_UI_GATE,
    build_readiness_report,
    render_markdown,
)


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _ui_gate(path: Path, *, passed: bool = False) -> Path:
    return _write_json(
        path,
        {
            "status": "pass" if passed else "need_review",
            "entries": [
                {
                    "base": "LB26001-A-04-006",
                    "vision_qc_v6_visual_acceptance_pass": passed,
                    "reference_compare_v4_pass": passed,
                    "reasons": [] if passed else ["ui_screenshot_visual_acceptance_not_passed"],
                }
            ],
        },
    )


def _expansion_gate(path: Path, *, passed: bool = False) -> Path:
    return _write_json(
        path,
        {
            "status": "pass" if passed else "blocked_by_006",
            "pass": passed,
            "reasons": [] if passed else ["lb26001_006_required_before_expansion"],
        },
    )


def test_006_regression_readiness_blocks_unresponsive_unsaved_solidworks() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        report = build_readiness_report(
            sw_state={
                "process_present": True,
                "responding": False,
                "main_window_title": "SOLIDWORKS Premium 2025 SP5.0 - [草图1 ← 零件38 *]",
            },
            ui_gate_path=_ui_gate(root / "ui_gate.json"),
            expansion_gate_path=_expansion_gate(root / "expansion_gate.json"),
            lock_file=root / "missing_lock.json",
        )

    keys = set(report["blocking_issue_keys"])
    assert report["ready_to_start_locked_006_cad"] is False
    assert report["status"] == "blocked"
    assert "solidworks_not_responding" in keys
    assert "solidworks_unsaved_document_visible" in keys
    guidance = report["safe_recovery_guidance"]
    assert guidance["manual_recovery_required"] is True
    assert guidance["automatic_restart_allowed"] is False
    assert "unsaved document" in " ".join(guidance["steps"]).lower()
    assert "Do not kill or restart SLDWORKS.exe" in guidance["do_not"][0]


def test_006_regression_readiness_blocks_missing_ui_gate() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        report = build_readiness_report(
            sw_state={
                "process_present": True,
                "responding": True,
                "main_window_title": "SOLIDWORKS Premium 2025 SP5.0",
            },
            ui_gate_path=root / "missing_ui_gate.json",
            expansion_gate_path=_expansion_gate(root / "expansion_gate.json"),
            lock_file=root / "missing_lock.json",
        )

    assert report["ready_to_start_locked_006_cad"] is False
    assert "ui_visual_review_gate_missing" in report["blocking_issue_keys"]


def test_006_regression_readiness_allows_next_rerun_when_solidworks_is_safe() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        report = build_readiness_report(
            sw_state={
                "process_present": True,
                "responding": True,
                "main_window_title": "SOLIDWORKS Premium 2025 SP5.0",
            },
            ui_gate_path=_ui_gate(root / "ui_gate.json", passed=False),
            expansion_gate_path=_expansion_gate(root / "expansion_gate.json", passed=False),
            lock_file=root / "missing_lock.json",
        )

    info_keys = {item["key"] for item in report["issues"] if item["severity"] == "info"}
    assert report["ready_to_start_locked_006_cad"] is True
    assert report["status"] == "ready"
    assert "previous_006_v6_ui_gate_not_pass" in info_keys
    assert "lb26001_expansion_currently_blocked" in info_keys


def test_006_regression_readiness_blocks_existing_solidworks_lock() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        lock = _write_json(
            root / "solidworks_global_lock.json",
            {
                "owner_job_id": "other-job",
                "owner_pid": os.getpid(),
                "owner_worker_pid": os.getpid(),
                "heartbeat_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
                "ttl_sec": 180,
                "status": "active",
            },
        )
        report = build_readiness_report(
            sw_state={
                "process_present": True,
                "responding": True,
                "main_window_title": "SOLIDWORKS Premium 2025 SP5.0",
            },
            ui_gate_path=_ui_gate(root / "ui_gate.json", passed=False),
            expansion_gate_path=_expansion_gate(root / "expansion_gate.json", passed=False),
            lock_file=lock,
        )

    assert report["ready_to_start_locked_006_cad"] is False
    assert "solidworks_global_lock_present" in report["blocking_issue_keys"]


def test_006_regression_readiness_does_not_block_on_stale_solidworks_lock() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        lock = _write_json(
            root / "solidworks_global_lock.json",
            {
                "owner_job_id": "old-job",
                "owner_run_id": "old-run",
                "operation": "solidworks_com_probe:get_active_object",
                "owner_pid": 0,
                "owner_worker_pid": 0,
                "heartbeat_at": "2000-01-01T00:00:00",
                "ttl_sec": 1,
                "status": "active",
            },
        )
        report = build_readiness_report(
            sw_state={
                "process_present": True,
                "responding": True,
                "main_window_title": "SOLIDWORKS Premium 2025 SP5.0",
            },
            ui_gate_path=_ui_gate(root / "ui_gate.json", passed=False),
            expansion_gate_path=_expansion_gate(root / "expansion_gate.json", passed=False),
            lock_file=lock,
        )

    info_keys = {item["key"] for item in report["issues"] if item["severity"] == "info"}
    assert report["ready_to_start_locked_006_cad"] is True
    assert report["solidworks_lock_stale"] is True
    assert report["solidworks_lock_conflict"]["reason"] == "solidworks_lock_is_stale"
    assert report["solidworks_lock_owner"]["owner_job_id"] == "old-job"
    assert report["solidworks_lock_owner"]["owner_run_id"] == "old-run"
    assert report["solidworks_lock_owner"]["operation"] == "solidworks_com_probe:get_active_object"
    assert "solidworks_global_lock_stale" in info_keys
    assert "solidworks_global_lock_present" not in report["blocking_issue_keys"]
    markdown = render_markdown(report)
    assert "SolidWorks Lock Details" in markdown
    assert "old-job" in markdown
    assert "solidworks_lock_is_stale" in markdown


def test_006_regression_readiness_defaults_to_latest_canonical_ui_gate() -> None:
    assert "LB26001_006_locked_real_rerun_20260625_041353_visual_review" in str(DEFAULT_UI_GATE)
    assert "closed_loop" in str(DEFAULT_UI_GATE)
    assert "LB26001_006_locked_real_rerun_20260625_041353_visual_review" in str(DEFAULT_EXPANSION_GATE)
    assert "closed_loop" in str(DEFAULT_EXPANSION_GATE)


def test_006_regression_readiness_markdown_explains_manual_recovery_without_cad_start() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        report = build_readiness_report(
            sw_state={
                "process_present": False,
                "responding": None,
                "main_window_title": "",
            },
            ui_gate_path=_ui_gate(root / "ui_gate.json"),
            expansion_gate_path=_expansion_gate(root / "expansion_gate.json"),
            lock_file=root / "missing_lock.json",
        )
        markdown = render_markdown(report)

    assert "Manual Recovery Steps" in markdown
    assert "ready_to_start_locked_006_cad: `False`" in markdown
    assert "Automatic restart allowed: `False`" in markdown
    assert "Do not kill or restart SLDWORKS.exe" in markdown
    assert "Recovery Verification Command" in markdown
    assert "lb26001_006_regression_readiness_v4_2.py --out" in markdown
    assert "staged_cad_validation_v3.py --stage LB26001_006" in markdown
    assert "007/008/009/015/022" in markdown


if __name__ == "__main__":
    test_006_regression_readiness_blocks_unresponsive_unsaved_solidworks()
    test_006_regression_readiness_blocks_missing_ui_gate()
    test_006_regression_readiness_allows_next_rerun_when_solidworks_is_safe()
    test_006_regression_readiness_blocks_existing_solidworks_lock()
    test_006_regression_readiness_does_not_block_on_stale_solidworks_lock()
    test_006_regression_readiness_defaults_to_latest_canonical_ui_gate()
    test_006_regression_readiness_markdown_explains_manual_recovery_without_cad_start()
    print("PASS test_v4_2_006_regression_readiness")
