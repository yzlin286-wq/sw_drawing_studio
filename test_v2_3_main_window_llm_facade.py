"""Smoke tests for routing MainWindow LLM actions through JobRuntimeFacade."""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

from app.ui.batch_page import COL_CATEGORY, COL_FRONT_VIEW, COL_SCALE
from app.ui.main_window import MainWindow


class FakeLlmFacade(QObject):
    job_started = Signal(str, dict)
    job_progress = Signal(str, dict)
    job_finished = Signal(str, dict)
    job_failed = Signal(str, dict)
    event_logged = Signal(str, str, dict)

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[dict] = []
        self.cancelled: list[str] = []

    def start_llm_action(self, **kwargs) -> str:
        self.calls.append(kwargs)
        return f"fake_llm_job_{len(self.calls)}"

    def cancel_job(self, job_id: str) -> bool:
        self.cancelled.append(job_id)
        return True


def _app() -> QApplication:
    return QApplication.instance() or QApplication(sys.argv)


def _connect_fake(window: MainWindow, fake: FakeLlmFacade) -> None:
    window.job_facade = fake
    fake.job_progress.connect(window._on_llm_action_progress)
    fake.job_finished.connect(window._on_llm_action_finished)
    fake.job_failed.connect(window._on_llm_action_failed)


def test_main_window_source_no_ui_process_llm_worker() -> None:
    text = Path("app/ui/main_window.py").read_text(encoding="utf-8")
    forbidden = ("QThreadPool", "LLMWorker", "_start_worker", "self.llm.chat", "_llm_gen_tech_text")
    for token in forbidden:
        assert token not in text, token


def test_pre_analyze_uses_llm_facade_and_renders_result() -> None:
    _app()
    window = MainWindow()
    fake = FakeLlmFacade()
    _connect_fake(window, fake)
    window.llm = object()
    fixture = Path("drw_output") / "_main_window_llm_facade" / "pre.SLDPRT"
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_text("fake part", encoding="utf-8")
    part = str(fixture)
    window.batch_page.add_paths([part])

    window._on_request_pre_analyze([part])

    assert len(fake.calls) == 1
    assert fake.calls[0]["action"] == "pre_analyze"
    assert fake.calls[0]["part_path"] == part
    assert fake.calls[0]["timeout_s"] == 120
    assert "fake_llm_job_1" in window._llm_action_jobs

    fake.job_finished.emit(
        "fake_llm_job_1",
        {
            "result": {
                "action": "pre_analyze",
                "part_path": part,
                "pre_analysis": {"category": "shaft", "front_view": "Front", "scale": "1:1"},
            }
        },
    )

    row = window.batch_page._row_index_of(part)
    assert window.batch_page.model.item(row, COL_CATEGORY).text() == "shaft"
    assert window.batch_page.model.item(row, COL_FRONT_VIEW).text() == "Front"
    assert window.batch_page.model.item(row, COL_SCALE).text() == "1:1"
    assert not window._llm_action_jobs
    window.close()


def test_tech_text_uses_llm_facade_and_updates_report() -> None:
    _app()
    window = MainWindow()
    fake = FakeLlmFacade()
    _connect_fake(window, fake)
    window.llm = object()

    window._on_request_tech_text()

    assert len(fake.calls) == 1
    assert fake.calls[0]["action"] == "tech_text"
    assert fake.calls[0]["context"]
    assert fake.calls[0]["timeout_s"] == 120
    assert "fake_llm_job_1" in window._llm_action_jobs

    fake.job_finished.emit(
        "fake_llm_job_1",
        {
            "result": {
                "action": "tech_text",
                "items": ["Deburr all sharp edges.", "Apply GB/T 1804-m tolerance.", "Protect finished surfaces."],
            }
        },
    )

    text = window.qc_page.report.toPlainText()
    assert "Deburr all sharp edges." in text
    assert "Apply GB/T 1804-m tolerance." in text
    assert not window._llm_action_jobs
    window.close()


if __name__ == "__main__":
    test_main_window_source_no_ui_process_llm_worker()
    test_pre_analyze_uses_llm_facade_and_renders_result()
    test_tech_text_uses_llm_facade_and_updates_report()
    print("v2.3 main window LLM facade smoke PASS")