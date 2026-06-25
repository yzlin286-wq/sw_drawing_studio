"""Smoke test for the v2.3 Single Part page.

Uses a fake facade and avoids launching SolidWorks. The goal is to verify the UI
contract that submits CAD jobs through JobRuntimeFacade with strategy and
titlebar overrides, then renders the finished run result.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

from app.ui.single_part_page import SinglePartPage


class FakeFacade(QObject):
    job_started = Signal(str, dict)
    job_progress = Signal(str, dict)
    job_finished = Signal(str, dict)
    job_failed = Signal(str, dict)
    event_logged = Signal(str, str, dict)

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[dict] = []

    def start_cad_job(self, **kwargs) -> str:
        self.calls.append(kwargs)
        return "fake_single_job"


def _sample_part() -> Path:
    fixture_dir = Path("drw_output") / "_single_part_test"
    fixture_dir.mkdir(parents=True, exist_ok=True)
    sample = fixture_dir / "sample.SLDPRT"
    sample.write_text("fake solidworks part placeholder", encoding="utf-8")
    return sample


def test_single_part_page_submits_to_facade_and_renders_result() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    page = SinglePartPage()
    fake = FakeFacade()
    page.facade = fake
    fake.job_started.connect(page._on_job_started)
    fake.job_progress.connect(page._on_job_progress)
    fake.job_finished.connect(page._on_job_finished)
    fake.job_failed.connect(page._on_job_failed)
    fake.event_logged.connect(page._on_job_event)
    page._collect_titlebar_overrides = lambda _path: {"designer": "tester"}  # type: ignore[method-assign]

    sample = _sample_part()
    page.le_path.setText(str(sample))
    page.cb_strategy.setCurrentIndex(page.cb_strategy.findData("v5_compat"))

    page._on_run()

    assert page._active_job_id == "fake_single_job"
    assert len(fake.calls) == 1
    call = fake.calls[0]
    assert call["part_path"] == str(sample)
    assert call["output_dir"] == ""
    assert call["max_rounds"] == 3
    assert call["timeout_s"] == 900
    assert call["titlebar_overrides"] == {"designer": "tester"}
    assert call["strategy"] == "v5_compat"
    assert os.environ.get("USE_V5") == "1"

    fake.job_progress.emit("fake_single_job", {"progress": 0.5, "stage": "running qc"})
    assert page.progress.value() == 50
    assert page.lbl_step.text() == "running qc"

    run_dir = Path("drw_output") / "_single_part_test" / "run_pkg"
    run_dir.mkdir(parents=True, exist_ok=True)
    fake.job_finished.emit(
        "fake_single_job",
        {
            "result": {
                "run_id": "run_pkg",
                "run_dir": str(run_dir),
                "drawing_usable": {"pass": True},
                "hard_fail": [],
                "warnings": [],
                "qc_pass_count": 12,
                "vision_score": 96,
                "output_files": {"drawing": [str(run_dir / "sample.PDF")]},
                "fallback_used": False,
                "bom_status": "ok",
                "process_status": "ok",
                "quote_status": "ok",
            }
        },
    )

    assert page._active_job_id == ""
    assert page.btn_run.isEnabled()
    assert page.btn_open_pkg.isEnabled()
    assert page._current_run_dir == run_dir
    text = page.report.toPlainText()
    assert "run_id      : run_pkg" in text
    assert "qc_pass     : 12/12" in text
    assert "vision      : 96/100" in text
    page.close()


if __name__ == "__main__":
    test_single_part_page_submits_to_facade_and_renders_result()
    print("v2.3 single part page smoke PASS")
