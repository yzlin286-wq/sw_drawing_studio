from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.ui.main_window import (
    NAV_ITEMS,
    PAGE_BATCH,
    PAGE_DRAWING_REVIEW,
    PAGE_HEALTH,
    PAGE_HOME,
    PAGE_JOBS,
    PAGE_LOG,
    PAGE_SETTINGS,
    PAGE_SINGLE,
    PAGE_VISUAL_AUDIT,
    MainWindow,
)


EXPECTED_NAV = [
    "仪表盘",
    "单件制图",
    "作业队列",
    "视觉审计",
    "图纸复核",
    "批量验证",
    "系统健康",
    "日志诊断",
    "设置",
]


def test_v3_main_navigation_contract() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    assert NAV_ITEMS == EXPECTED_NAV

    window = MainWindow()
    page_map = {
        PAGE_HOME: window.home_page,
        PAGE_SINGLE: window.single_page,
        PAGE_JOBS: window.job_queue_page,
        PAGE_VISUAL_AUDIT: window.visual_audit_page,
        PAGE_DRAWING_REVIEW: window.drawing_review_page,
        PAGE_BATCH: window.batch_page,
        PAGE_HEALTH: window.system_health_page,
        PAGE_LOG: window.logs_diagnostics_page,
        PAGE_SETTINGS: window.settings_page,
    }
    assert window.nav.count() == len(EXPECTED_NAV)
    for row, widget in page_map.items():
        window.nav.setCurrentRow(row)
        app.processEvents()
        assert window.stack.currentWidget() is widget
        assert window.nav.item(row).text() == EXPECTED_NAV[row]
    window.close()
    app.processEvents()


if __name__ == "__main__":
    test_v3_main_navigation_contract()
    print("v3 main navigation smoke PASS")
