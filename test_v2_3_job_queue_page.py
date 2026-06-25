"""Smoke test for the v2.3 Job Queue page.

Uses the mock QProcess worker, so it does not require SolidWorks.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from app.ui.job_queue_page import JobQueuePage
from app.ui.main_window import NAV_ITEMS, PAGE_JOBS, MainWindow
from app.services.job_event_bus import JobEventBus
from app.services.job_queue import JobQueue, JobRecord
from app.services.job_runner import JobRunner


def test_main_window_nav() -> None:
    assert "作业队列" in NAV_ITEMS
    assert NAV_ITEMS[PAGE_JOBS] == "作业队列"
    window = MainWindow()
    assert hasattr(window, "job_queue_page")
    assert window.stack.indexOf(window.job_queue_page) == PAGE_JOBS
    window.close()


def test_job_queue_page_mock_job() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    page = JobQueuePage()
    page.duration.setValue(0.2)
    page.scenario.setCurrentText("normal_pass")
    page._start_mock()

    def check_done() -> None:
        jobs = page.facade.list_jobs()
        if any(j.get("status") == "completed" for j in jobs):
            app.quit()

    timer = QTimer()
    timer.setInterval(100)
    timer.timeout.connect(check_done)
    timer.start()
    QTimer.singleShot(5000, app.quit)
    app.exec()
    timer.stop()

    jobs = page.facade.list_jobs()
    assert any(j.get("status") == "completed" for j in jobs), jobs
    page.refresh()
    assert page.model.rowCount() >= 1
    assert "job_finished" in page.event_view.toPlainText()
    page.close()


def test_job_queue_page_cad_enqueue() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    page = JobQueuePage()
    sample = Path("3D转2D测试图纸") / "LB26001-A-04-001.SLDPRT"
    if not sample.exists():
        sample = next(Path("3D转2D测试图纸").glob("*.SLDPRT"))
    page.add_cad_paths_for_test([str(sample)])
    assert "待启动 CAD: 1" in page.pending_label.text()
    record = JobRecord(
        job_id="cad_args",
        part_name=sample.stem,
        part_path=str(sample),
        job_type="cad",
        timeout_s=600,
    )
    record.result["output_dir"] = "drw_output"
    record.result["max_rounds"] = 3
    args = JobRunner(JobEventBus(), JobQueue())._build_worker_args(record)
    assert args[args.index("--part-path") + 1] == str(sample)
    assert args[args.index("--output-dir") + 1] == "drw_output"
    assert args[args.index("--max-rounds") + 1] == "3"
    page.close()


if __name__ == "__main__":
    app = QApplication.instance() or QApplication(sys.argv)
    test_main_window_nav()
    test_job_queue_page_mock_job()
    test_job_queue_page_cad_enqueue()
    print("v2.3 job queue page smoke PASS")
