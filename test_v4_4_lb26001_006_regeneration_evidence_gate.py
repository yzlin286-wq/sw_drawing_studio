from __future__ import annotations

import json
import os
import time
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.validation.lb26001_006_regeneration_evidence_gate_v4_4 import (
    BASE,
    REPO_ROOT,
    build_regeneration_evidence_gate,
)


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _write_file(path: Path, data: bytes = b"x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _set_mtime(path: Path, value: float) -> None:
    os.utime(path, (value, value))


def _write_event_log(run_dir: Path, finished: bool = True) -> None:
    events = ["job_started", "heartbeat", "progress"]
    events.append("job_finished" if finished else "job_failed")
    lines = [
        json.dumps({"event_type": event, "type": event, "timestamp": "2026-06-25T00:00:00"}, ensure_ascii=False)
        for event in events
    ]
    _write_file(run_dir / "job_event_log.jsonl", ("\n".join(lines) + "\n").encode("utf-8"))


def _make_fresh_run(root: Path, *, started_at: float | None = None) -> Path:
    run_dir = root
    run_id = run_dir.name
    started = started_at if started_at is not None else time.time() - 30
    for ext in ["SLDDRW", "PDF", "DXF", "PNG"]:
        _write_file(run_dir / "drawing" / f"{BASE}_v5.{ext}", b"fresh")
    _write_json(run_dir / "qc" / f"{BASE}_v5_qc.json", {"pass": True})
    _write_json(run_dir / "qc" / f"{BASE}_v5_warnings.json", {"warnings": []})
    _write_json(run_dir / "qc" / "drawing_blueprint.json", {"base": BASE})
    _write_json(run_dir / "qc" / "vision_qc_v6.json", {"status": "pass"})
    _write_json(run_dir / "qc" / "final_quality.json", {"status": "pass_with_warning", "deliverable": True})
    _write_json(run_dir / "sw_session.json", {"status": "connected", "sw_pid": 1234})
    _write_event_log(run_dir)
    _write_json(
        run_dir / "manifest.json",
        {
            "schema": "sw_drawing_studio.worker_manifest.v1",
            "job_type": "cad",
            "part_base": BASE,
            "run_id": run_id,
            "run_dir": str(run_dir),
            "core_files_ok": True,
            "drawing_usable": {"pass": True},
            "hard_fail": [],
            "artifact_freshness": {"min_mtime": started, "stale_artifacts": []},
        },
    )
    for path in run_dir.rglob("*"):
        if path.is_file():
            _set_mtime(path, started + 10)
    return run_dir


def _write_staged_summary(summary_path: Path, run_dir: Path) -> Path:
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    started = manifest["artifact_freshness"]["min_mtime"]
    case_dir = summary_path.parent / "01_LB26001-A-04-006"
    dimension_report = _write_json(case_dir / "dimension_validation.json", {"status": "pass", "pass": True})
    reference_report = _write_json(case_dir / "reference_compare_v4.json", {"status": "pass", "pass": True})
    _write_json(
        summary_path,
        {
            "schema": "sw_drawing_studio.staged_cad_validation.v3",
            "cases": [
                {
                    "part_name": BASE,
                    "run_dir": str(run_dir),
                    "case_dir": str(case_dir),
                    "dimension_report": str(dimension_report),
                    "reference_compare_v4_report": str(reference_report),
                }
            ],
        },
    )
    for path in [dimension_report, reference_report, summary_path]:
        _set_mtime(path, started + 20)
    return summary_path


def test_006_regeneration_evidence_gate_passes_fresh_synthetic_run() -> None:
    runs_root = REPO_ROOT / "drw_output" / "runs"
    runs_root.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="test_006_regen_gate_", dir=runs_root) as tmp:
        run_dir = _make_fresh_run(Path(tmp))
        summary_path = _write_staged_summary(run_dir / "staged_summary.json", run_dir)

        result = build_regeneration_evidence_gate(run_dir=run_dir, summary_path=summary_path)

        assert result["pass"] is True
        assert result["status"] == "regeneration_evidence_pass_requires_application_ui_screenshot_review"
        assert result["release_ready"] is False
        assert result["report_is_drawing_acceptance_evidence"] is False
        assert result["api_only_acceptance_allowed"] is False
        assert result["ui_screenshot_acceptance_required"] is True
        assert result["staged_summary_required"] is True
        assert result["staged_validation_artifacts_required"] is True
        assert result["staged_validation_artifact_contract_pass"] is True
        assert set(result["required_staged_artifact_keys"]) == {"dimension_validation", "reference_compare_v4"}
        assert not result["blocking_issue_keys"]


def test_006_regeneration_evidence_gate_blocks_run_dir_without_staged_summary() -> None:
    runs_root = REPO_ROOT / "drw_output" / "runs"
    runs_root.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="test_006_regen_gate_", dir=runs_root) as tmp:
        run_dir = _make_fresh_run(Path(tmp))

        result = build_regeneration_evidence_gate(run_dir=run_dir)

        keys = set(result["blocking_issue_keys"])
        assert result["pass"] is False
        assert result["status"] == "blocked_by_regeneration_evidence"
        assert result["staged_validation_artifact_contract_pass"] is False
        assert "staged_summary_provided" in keys
        assert "summary_case_is_006" in keys
        assert "staged_artifact_dimension_validation" in keys
        assert "staged_artifact_reference_compare_v4" in keys


def test_006_regeneration_evidence_gate_blocks_missing_reference_compare_v4() -> None:
    runs_root = REPO_ROOT / "drw_output" / "runs"
    runs_root.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="test_006_regen_gate_", dir=runs_root) as tmp:
        run_dir = _make_fresh_run(Path(tmp))
        summary_path = _write_staged_summary(run_dir / "staged_summary.json", run_dir)
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
        reference_path = Path(payload["cases"][0]["reference_compare_v4_report"])
        reference_path.unlink()

        result = build_regeneration_evidence_gate(run_dir=run_dir, summary_path=summary_path)

        keys = set(result["blocking_issue_keys"])
        assert result["pass"] is False
        assert result["status"] == "blocked_by_regeneration_evidence"
        assert result["staged_validation_artifact_contract_pass"] is False
        assert "staged_artifact_reference_compare_v4" in keys
        assert "fresh_staged_validation_artifacts" in keys


def test_006_regeneration_evidence_gate_blocks_stale_drawing_artifact() -> None:
    runs_root = REPO_ROOT / "drw_output" / "runs"
    runs_root.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="test_006_regen_gate_", dir=runs_root) as tmp:
        run_dir = _make_fresh_run(Path(tmp))
        started = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))["artifact_freshness"]["min_mtime"]
        _set_mtime(run_dir / "drawing" / f"{BASE}_v5.PNG", started - 60)

        result = build_regeneration_evidence_gate(run_dir=run_dir)

        assert result["pass"] is False
        assert result["status"] == "blocked_by_regeneration_evidence"
        assert "fresh_required_artifacts" in set(result["blocking_issue_keys"])


def test_006_regeneration_evidence_gate_blocks_missing_job_started_at() -> None:
    runs_root = REPO_ROOT / "drw_output" / "runs"
    runs_root.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="test_006_regen_gate_", dir=runs_root) as tmp:
        run_dir = _make_fresh_run(Path(tmp))
        manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        manifest["artifact_freshness"] = {"stale_artifacts": []}
        _write_json(run_dir / "manifest.json", manifest)

        result = build_regeneration_evidence_gate(run_dir=run_dir)

        assert result["pass"] is False
        assert "job_started_at_present" in set(result["blocking_issue_keys"])
        assert "fresh_required_artifacts" in set(result["blocking_issue_keys"])


def test_006_regeneration_evidence_gate_blocks_missing_sw_session() -> None:
    runs_root = REPO_ROOT / "drw_output" / "runs"
    runs_root.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="test_006_regen_gate_", dir=runs_root) as tmp:
        run_dir = _make_fresh_run(Path(tmp))
        (run_dir / "sw_session.json").unlink()

        result = build_regeneration_evidence_gate(run_dir=run_dir)

        keys = set(result["blocking_issue_keys"])
        assert result["pass"] is False
        assert "artifact_sw_session" in keys
        assert "sw_session_connected" in keys


def test_006_regeneration_evidence_gate_blocks_missing_explicit_run() -> None:
    result = build_regeneration_evidence_gate()

    assert result["pass"] is False
    assert result["status"] == "blocked_by_missing_fresh_006_run"
    assert result["blocking_issue_keys"] == ["explicit_006_run_evidence_source"]


def test_006_regeneration_evidence_gate_tool_is_file_only() -> None:
    source = Path("tools/validation/lb26001_006_regeneration_evidence_gate_v4_4.py").read_text(encoding="utf-8")
    forbidden = [
        "win32com",
        "pythoncom",
        "GetActiveObject",
        "Dispatch(",
        "OpenDoc6",
        "subprocess.run",
        "QProcess",
    ]
    for token in forbidden:
        assert token not in source


if __name__ == "__main__":
    test_006_regeneration_evidence_gate_passes_fresh_synthetic_run()
    test_006_regeneration_evidence_gate_blocks_run_dir_without_staged_summary()
    test_006_regeneration_evidence_gate_blocks_missing_reference_compare_v4()
    test_006_regeneration_evidence_gate_blocks_stale_drawing_artifact()
    test_006_regeneration_evidence_gate_blocks_missing_job_started_at()
    test_006_regeneration_evidence_gate_blocks_missing_sw_session()
    test_006_regeneration_evidence_gate_blocks_missing_explicit_run()
    test_006_regeneration_evidence_gate_tool_is_file_only()
    print("PASS test_v4_4_lb26001_006_regeneration_evidence_gate")
