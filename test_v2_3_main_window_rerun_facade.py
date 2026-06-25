"""Smoke tests for CAD rerun routing through JobRuntimeFacade.

These tests use a fake facade, so they never launch SolidWorks. They verify that
legacy rerun actions in MainWindow submit QProcess-backed CAD jobs and map worker
manifest-style results back into the Batch/QC UI surfaces.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

from app.ui.batch_page import COL_ERROR, COL_OUT
from app.ui.main_window import MainWindow


class FakeCadFacade(QObject):
    job_started = Signal(str, dict)
    job_progress = Signal(str, dict)
    job_finished = Signal(str, dict)
    job_failed = Signal(str, dict)
    event_logged = Signal(str, str, dict)

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[dict] = []
        self.cancelled: list[str] = []

    def start_cad_job(self, **kwargs) -> str:
        self.calls.append(kwargs)
        return f"fake_cad_job_{len(self.calls)}"

    def start_batch_job(self, **kwargs) -> str:
        raise AssertionError("rerun tests must not submit batch jobs")

    def start_qc_action(self, **kwargs) -> str:
        raise AssertionError("CAD rerun must not submit qc_action jobs")

    def cancel_job(self, job_id: str) -> bool:
        self.cancelled.append(job_id)
        return True


def _app() -> QApplication:
    return QApplication.instance() or QApplication(sys.argv)


def _fixture_dir() -> Path:
    root = Path("drw_output") / "_main_window_rerun_facade"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _write_file(path: Path, text: str = "fixture") -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return str(path)


def _connect_fake(window: MainWindow, fake: FakeCadFacade) -> None:
    window.job_facade = fake
    fake.job_progress.connect(window._on_cad_rerun_progress)
    fake.job_finished.connect(window._on_cad_rerun_finished)
    fake.job_failed.connect(window._on_cad_rerun_failed)


def test_main_window_source_no_legacy_cad_rerun_runner() -> None:
    text = Path("app/ui/main_window.py").read_text(encoding="utf-8")
    forbidden = ("SwRunner", "RunnerWorker", "run_single", "_start_runner_worker")
    for token in forbidden:
        assert token not in text, token


def test_batch_single_row_rerun_submits_cad_facade_and_renders_result() -> None:
    _app()
    window = MainWindow()
    fake = FakeCadFacade()
    _connect_fake(window, fake)
    root = _fixture_dir()
    part = _write_file(root / "BatchRerun.SLDPRT")
    window.batch_page.add_paths([part])

    window._on_request_rerun_one(part)

    assert len(fake.calls) == 1
    call = fake.calls[0]
    assert call["part_path"] == part
    assert call["output_dir"] == ""
    assert call["max_rounds"] == window._max_qc_rounds
    assert call["timeout_s"] == 900
    assert "fake_cad_job_1" in window._cad_rerun_jobs

    run_dir = root / "run_batch"
    out_drw = _write_file(run_dir / "drawing" / "BatchRerun_v5.SLDDRW")
    qc_json = _write_file(run_dir / "qc" / "BatchRerun_v5_qc.json", '{"pass": true, "score_pass_count": 5}')
    fake.job_finished.emit(
        "fake_cad_job_1",
        {
            "result": {
                "run_dir": str(run_dir),
                "drawing_usable": {"pass": True},
                "output_files": {"drawing": [out_drw], "qc": [qc_json]},
            }
        },
    )

    assert not window._cad_rerun_jobs
    assert window.batch_page.btn_run.isEnabled()
    row = window.batch_page._row_index_of(part)
    assert row >= 0
    assert window.batch_page.model.item(row, COL_OUT).text() == out_drw
    assert window.batch_page.model.item(row, COL_ERROR).text() == ""
    window.close()


def test_qc_rerun_submits_cad_facade_and_updates_selected_drawing() -> None:
    _app()
    window = MainWindow()
    fake = FakeCadFacade()
    _connect_fake(window, fake)
    root = _fixture_dir()
    source_drw = _write_file(root / "ReviewRerun_v5.SLDDRW")
    _write_file(root / "ReviewRerun.SLDPRT")

    window._on_request_rerun(source_drw)

    assert len(fake.calls) == 1
    assert fake.calls[0]["part_path"].endswith("ReviewRerun.SLDPRT")
    assert fake.calls[0]["output_dir"] == ""
    assert "fake_cad_job_1" in window._cad_rerun_jobs

    out_drw = _write_file(root / "run_qc" / "drawing" / "ReviewRerun_v5.SLDDRW")
    fake.job_finished.emit(
        "fake_cad_job_1",
        {
            "result": {
                "run_dir": str(root / "run_qc"),
                "drawing_usable": {"pass": True},
                "output_files": {"drawing": [out_drw]},
            }
        },
    )

    assert window.qc_page.slddrw_path() == out_drw
    assert not window._cad_rerun_jobs
    window.close()


if __name__ == "__main__":
    test_main_window_source_no_legacy_cad_rerun_runner()
    test_batch_single_row_rerun_submits_cad_facade_and_renders_result()
    test_qc_rerun_submits_cad_facade_and_updates_selected_drawing()
    print("v2.3 main window CAD rerun facade smoke PASS")