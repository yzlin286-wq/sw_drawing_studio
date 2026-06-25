"""Smoke test for the v2.3 Logs & Diagnostics page.

Uses a tiny run fixture and does not invoke SolidWorks.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import zipfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.services.diagnostics import DIAGNOSTICS_DIR, build_diagnostics_zip
from app.services.run_manager import RUNS_DIR
from app.ui.logs_diagnostics_page import LogsDiagnosticsPage, collect_run_files, discover_runs
from app.ui.main_window import NAV_ITEMS, PAGE_LOG, MainWindow


RUN_ID = "_logs_diag_test_run"


def _fixture() -> Path:
    run = RUNS_DIR / RUN_ID
    if run.exists():
        shutil.rmtree(run)
    (run / "logs").mkdir(parents=True, exist_ok=True)
    (run / "qc").mkdir(parents=True, exist_ok=True)
    (run / "drawing").mkdir(parents=True, exist_ok=True)
    manifest = {
        "run_id": RUN_ID,
        "started_at": "2026-06-21 10:00:00",
        "finished_at": "2026-06-21 10:01:00",
        "input_part_path_abs": r"C:\parts\sample.SLDPRT",
        "drawing_usable": {"pass": False},
        "qc_pass_count": 8,
        "vision_score": 71,
        "hard_fail": ["qc_pass_too_low"],
        "warnings": [{"code": "fixture_warning"}],
        "exception_summary": ["fixture exception"],
    }
    (run / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (run / "logs" / "run.log").write_text("run fixture log\n", encoding="utf-8")
    (run / "logs" / "sw.log").write_text("sw fixture log\n", encoding="utf-8")
    (run / "logs" / "worker_stdout.log").write_text('{"event_type":"progress"}\n', encoding="utf-8")
    (run / "job_event_log.jsonl").write_text('{"type":"job_started","job_id":"_logs_diag_test_run"}\n', encoding="utf-8")
    (run / "sw_session.json").write_text(
        json.dumps({"connected": False, "transaction_status": "fixture"}, ensure_ascii=False),
        encoding="utf-8",
    )
    (run / "screenshots").mkdir(parents=True, exist_ok=True)
    (run / "screenshots" / "01_dashboard.png").write_bytes(b"\x89PNG\r\n\x1a\nfixture")
    (run / "qc" / "vision_qc_v5.json").write_text(
        json.dumps({"version": "v5", "issues": [{"key": "fixture_issue"}]}, ensure_ascii=False),
        encoding="utf-8",
    )
    (run / "qc" / "final_quality.json").write_text(
        json.dumps({"overall_status": "fail"}, ensure_ascii=False),
        encoding="utf-8",
    )
    return run


def _cleanup() -> None:
    run = RUNS_DIR / RUN_ID
    if run.exists():
        shutil.rmtree(run)
    zip_path = DIAGNOSTICS_DIR / f"diagnostics_{RUN_ID}.zip"
    if zip_path.exists():
        zip_path.unlink()


def test_discover_and_collect_files() -> None:
    _fixture()
    runs = discover_runs()
    run = next((r for r in runs if r.run_id == RUN_ID), None)
    assert run is not None
    labels = [label for label, _ in collect_run_files(run)]
    assert "manifest.json" in labels
    assert "logs/run.log" in labels
    assert "qc/vision_qc_v5.json" in labels
    assert "qc/final_quality.json" in labels


def test_diagnostics_zip_contains_v23_evidence() -> None:
    run = _fixture()
    zip_path = build_diagnostics_zip(RUN_ID, screenshots_dir=run / "screenshots")
    assert zip_path.exists()
    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())
    assert "manifest.json" in names
    assert "sw_session.json" in names
    assert "logs/run.log" in names
    assert "logs/sw.log" in names
    assert "logs/worker_stdout.log" in names
    assert "job_event_log.jsonl" in names
    assert "qc/vision_qc_v5.json" in names
    assert "qc/final_quality.json" in names
    assert "screenshots/01_dashboard.png" in names
    assert "health_check.json" in names
    assert "version.txt" in names


def test_logs_diagnostics_page_loads_fixture() -> None:
    _fixture()
    app = QApplication.instance() or QApplication(sys.argv)
    page = LogsDiagnosticsPage()
    page.refresh()
    assert page.select_run_for_test(RUN_ID)
    text = page.detail_view.toPlainText()
    assert RUN_ID in page.summary_label.text()
    assert "sample.SLDPRT" in page.summary_label.text()
    assert "run fixture log" in text or "run_id" in text
    zip_path = page.build_selected_diagnostics()
    assert zip_path is not None and zip_path.exists()
    page.close()
    app.processEvents()


def test_main_window_nav() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    assert NAV_ITEMS[PAGE_LOG] == "日志诊断"
    window = MainWindow()
    assert hasattr(window, "logs_diagnostics_page")
    assert window.stack.indexOf(window.logs_diagnostics_page) == PAGE_LOG
    window._goto_page(PAGE_LOG)
    assert window.stack.currentIndex() == PAGE_LOG
    window.close()
    app.processEvents()


if __name__ == "__main__":
    app = QApplication.instance() or QApplication(sys.argv)
    try:
        test_discover_and_collect_files()
        test_diagnostics_zip_contains_v23_evidence()
        test_logs_diagnostics_page_loads_fixture()
        test_main_window_nav()
        print("v2.3 logs diagnostics page smoke PASS")
    finally:
        _cleanup()
