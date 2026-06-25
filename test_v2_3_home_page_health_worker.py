"""Smoke coverage for Dashboard/Home health check worker isolation."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

import app.ui.home_page as home_page_module
from app.services.system_health_service import HealthRow, system_health_payload
from app.ui.home_page import HomePage


class _Signal:
    def __init__(self) -> None:
        self.callbacks = []

    def connect(self, callback) -> None:
        self.callbacks.append(callback)


class _FakeFacade:
    def __init__(self) -> None:
        self.job_finished = _Signal()
        self.job_failed = _Signal()
        self.started = []

    def start_system_health_check(self, timeout_s: float = 30) -> str:
        self.started.append(timeout_s)
        return "home_health_job"


def test_home_page_does_not_import_legacy_health_check() -> None:
    source = Path("app/ui/home_page.py").read_text(encoding="utf-8")
    assert "run_health_check" not in source
    assert "start_system_health_check" in source


def test_home_page_health_uses_facade_worker(monkeypatch=None) -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    fake = _FakeFacade()
    original = home_page_module.get_job_runtime_facade
    home_page_module.get_job_runtime_facade = lambda: fake
    try:
        page = HomePage()
        assert fake.started == [30]
        assert page._active_health_job_id == "home_health_job"

        rows = [
            HealthRow("UI-Worker", "mock_worker_smoke", "pass", "mock ok", ""),
            HealthRow("SolidWorks", "sw_running", "warning", "history usable", "start SolidWorks for CAD"),
        ]
        payload = system_health_payload(rows, {"pass": 1, "warning": 1, "fail": 0, "total": 2})
        page._on_health_job_finished("home_health_job", {"result": payload})

        assert page._active_health_job_id == ""
        assert page.btn_refresh_health.isEnabled()
        assert page._health_grid.count() >= 8
        assert "pass 1" in page.lbl_health_summary.text()
        page.close()
        app.processEvents()
    finally:
        home_page_module.get_job_runtime_facade = original


def test_home_page_missing_runs_dir_is_empty_state() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    fake = _FakeFacade()
    original_facade = home_page_module.get_job_runtime_facade
    original_runs_dir = home_page_module.RUNS_DIR
    with TemporaryDirectory() as td:
        missing_runs = Path(td) / "missing_runs"
        home_page_module.get_job_runtime_facade = lambda: fake
        home_page_module.RUNS_DIR = missing_runs
        try:
            page = HomePage()
            page._refresh_dashboard()
            page._refresh_sw_session()

            assert "Dashboard" not in page.lbl_today_runs.text()
            assert "0" in page.lbl_today_runs.text()
            assert "session" in page.lbl_sw_state.text()
            page.close()
            app.processEvents()
        finally:
            home_page_module.RUNS_DIR = original_runs_dir
            home_page_module.get_job_runtime_facade = original_facade


if __name__ == "__main__":
    test_home_page_does_not_import_legacy_health_check()
    test_home_page_health_uses_facade_worker()
    test_home_page_missing_runs_dir_is_empty_state()
    print("v2.3 home page health worker smoke PASS")
