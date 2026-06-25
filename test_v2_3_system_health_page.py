"""Smoke test for the v2.3 System Health page.

The test does not require SolidWorks to be running. A disconnected CAD session
must be shown as degraded drawing capability, not as a broken UI.
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from app.ui.main_window import NAV_ITEMS, PAGE_HEALTH, MainWindow
from app.services.system_health_service import collect_system_health, find_row
from app.ui.system_health_page import SystemHealthPage


REQUIRED_GROUPS = {"SolidWorks", "Vision", "Data", "License", "UI-Worker"}
REQUIRED_KEYS = {
    "sw_running",
    "addin_ping",
    "opendoc6_test",
    "dialog_guard",
    "fitz",
    "cv2",
    "ultralytics_import",
    "paddleocr",
    "yolo_weights",
    "document_manager_key",
    "mock_worker_smoke",
}


def test_collect_system_health_contract() -> None:
    rows, result = collect_system_health()
    groups = {row.group for row in rows}
    keys = {row.key for row in rows}

    assert REQUIRED_GROUPS.issubset(groups), groups
    assert REQUIRED_KEYS.issubset(keys), keys
    assert result["total"] == len(rows)
    assert result["pass"] + result["warning"] + result["fail"] == len(rows)

    sw_running = find_row(rows, "sw_running")
    assert sw_running is not None
    assert sw_running.status in {"pass", "warning"}


def test_system_health_page_refresh() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    page = SystemHealthPage()
    page.refresh()
    wait_until(lambda: page.model.rowCount() >= len(REQUIRED_KEYS), timeout_ms=10000)

    assert page.model.rowCount() >= len(REQUIRED_KEYS)
    text = page.detail_view.toPlainText()
    for group in REQUIRED_GROUPS:
        assert f"[{group}]" in text
    assert "mock_worker_smoke" in text
    page.close()
    app.processEvents()


def test_main_window_nav() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    assert NAV_ITEMS[PAGE_HEALTH] == "系统健康"
    window = MainWindow()
    assert hasattr(window, "system_health_page")
    assert window.stack.indexOf(window.system_health_page) == PAGE_HEALTH
    window.close()
    app.processEvents()


def wait_until(predicate, timeout_ms: int = 5000, step_ms: int = 50) -> bool:
    deadline = timeout_ms
    while deadline > 0:
        app = QApplication.instance()
        if app is not None:
            app.processEvents()
        if predicate():
            return True
        loop = QEventLoop()
        QTimer.singleShot(step_ms, loop.quit)
        loop.exec()
        deadline -= step_ms
    return bool(predicate())


if __name__ == "__main__":
    app = QApplication.instance() or QApplication(sys.argv)
    test_collect_system_health_contract()
    test_system_health_page_refresh()
    test_main_window_nav()
    print("v2.3 system health page smoke PASS")
