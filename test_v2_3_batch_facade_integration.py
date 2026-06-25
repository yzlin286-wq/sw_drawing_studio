"""Smoke test for routing the main Batch page through JobRuntimeFacade.

This uses a fake facade, so it does not launch SolidWorks. It verifies that the
main batch Run action submits a QProcess-backed batch job contract and renders
facade progress/results back into the batch table.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

from app.ui.batch_page import COL_ERROR, COL_OUT, COL_QC, COL_STATUS
from app.ui.main_window import MainWindow


class FakeBatchFacade(QObject):
    job_started = Signal(str, dict)
    job_progress = Signal(str, dict)
    job_finished = Signal(str, dict)
    job_failed = Signal(str, dict)
    event_logged = Signal(str, str, dict)

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[dict] = []
        self.cancelled: list[str] = []

    def start_batch_job(self, **kwargs) -> str:
        self.calls.append(kwargs)
        return "fake_batch_job"

    def cancel_job(self, job_id: str) -> bool:
        self.cancelled.append(job_id)
        return True


def _sample_parts() -> list[str]:
    fixture_dir = Path("drw_output") / "_batch_facade_test"
    fixture_dir.mkdir(parents=True, exist_ok=True)
    out: list[str] = []
    for name in ("sample_a.SLDPRT", "sample_b.SLDPRT"):
        p = fixture_dir / name
        p.write_text("fake solidworks part placeholder", encoding="utf-8")
        out.append(str(p))
    return out


def _connect_fake(window: MainWindow, fake: FakeBatchFacade) -> None:
    window.job_facade = fake
    fake.job_progress.connect(window._on_batch_job_progress)
    fake.job_finished.connect(window._on_batch_job_finished)
    fake.job_failed.connect(window._on_batch_job_failed)
    fake.event_logged.connect(window._on_batch_job_event)


def test_batch_page_uses_facade_and_renders_results() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    fake = FakeBatchFacade()
    _connect_fake(window, fake)
    parts = _sample_parts()
    window.batch_page.add_paths(parts)

    window._on_request_run(parts)

    assert window._active_batch_job_id == "fake_batch_job"
    assert len(fake.calls) == 1
    call = fake.calls[0]
    assert call["part_paths"] == parts
    assert call["output_dir"] == window._output_dir
    assert call["max_rounds"] == window._max_qc_rounds
    assert call["timeout_s"] == 900
    for row in range(window.batch_page.model.rowCount()):
        assert window.batch_page.model.item(row, COL_STATUS).text() == "排队中"

    fake.job_progress.emit("fake_batch_job", {"progress": 0.5, "stage": "批量 1/2", "current_part": parts[0]})
    assert window.batch_page.progress.value() == 1
    assert window.batch_page.model.item(0, COL_STATUS).text() == "运行中"

    out_drw = str(Path("drw_output") / "_batch_facade_test" / "sample_a_v5.SLDDRW")
    fake.job_finished.emit(
        "fake_batch_job",
        {
            "result": {
                "total": 2,
                "ok": 1,
                "failed": 1,
                "results": [
                    {"ok": True, "part": parts[0], "slddrw": out_drw, "error": ""},
                    {"ok": False, "part": parts[1], "error": "timeout"},
                ],
            }
        },
    )

    assert window._active_batch_job_id == ""
    assert window.batch_page.btn_run.isEnabled()
    assert window.batch_page.model.item(0, COL_STATUS).text() == "完成"
    assert window.batch_page.model.item(0, COL_OUT).text() == out_drw
    assert window.batch_page.model.item(1, COL_STATUS).text() == "失败"
    assert window.batch_page.model.item(1, COL_ERROR).text() == "timeout"
    assert window.batch_page.model.item(0, COL_QC).text() in {"", "pass", "fail"}  # optional existing fixture
    window.close()


def test_batch_cancel_uses_facade() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    fake = FakeBatchFacade()
    _connect_fake(window, fake)
    parts = _sample_parts()
    window.batch_page.add_paths(parts)
    window._on_request_run(parts)

    window._on_request_stop()

    assert fake.cancelled == ["fake_batch_job"]
    assert window._active_batch_job_id == ""
    assert window.batch_page.btn_run.isEnabled()
    window.close()


if __name__ == "__main__":
    test_batch_page_uses_facade_and_renders_results()
    test_batch_cancel_uses_facade()
    print("v2.3 batch facade integration smoke PASS")
