"""Smoke test for the source-level mock stability runner."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_mock_stability_runner_short_smoke() -> None:
    out_dir = Path("drw_output") / "ui_acceptance" / "mock_stability_unit"
    cmd = [
        sys.executable,
        "tools/ui_robot/mock_stability_runner.py",
        "--out-dir",
        str(out_dir),
        "--duration-s",
        "0.6",
        "--sample-interval-s",
        "0.2",
        "--screenshot-interval-s",
        "0.4",
        "--completion-grace-s",
        "8",
    ]
    proc = subprocess.run(
        cmd,
        cwd=Path(__file__).resolve().parent,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    report_path = out_dir / "mock_stability_report.json"
    assert report_path.exists()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["pass"] is True
    assert report["mode"] == "source_qt_mock_stability"
    assert report["checks"]["job_completed"] is True
    assert report["checks"]["event_log_exists"] is True
    assert report["checks"]["required_events_present"] is True
    assert Path(report["samples_jsonl"]).exists()
    assert Path(report["screenshots_dir"]).exists()


if __name__ == "__main__":
    test_mock_stability_runner_short_smoke()
    print("v3 mock stability runner smoke PASS")