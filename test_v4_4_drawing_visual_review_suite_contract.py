from __future__ import annotations

import ast
from pathlib import Path


SOURCE = Path("tools/ui_robot/drawing_visual_review_suite.py")


def _source_text() -> str:
    return SOURCE.read_text(encoding="utf-8")


def test_drawing_visual_review_suite_uses_direct_review_workbench_host() -> None:
    tree = ast.parse(_source_text())
    imported_modules: list[str] = []
    called_names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported_modules.append(node.module or "")
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                called_names.append(func.id)

    assert "app.ui.main_window" not in imported_modules
    assert "MainWindow" not in called_names
    assert "DrawingReviewWorkbench" in called_names
    assert "QMainWindow" in called_names


def test_drawing_visual_review_suite_declares_no_solidworks_probe_during_screenshot_review() -> None:
    source = _source_text()

    assert '"application_ui_source_mode": "drawing_review_workbench_direct_host"' in source
    assert '"solidworks_probe_allowed_during_screenshot_review": False' in source
    assert "click_list_row(window.nav" not in source
    assert "PAGE_DRAWING_REVIEW" not in source


if __name__ == "__main__":
    test_drawing_visual_review_suite_uses_direct_review_workbench_host()
    test_drawing_visual_review_suite_declares_no_solidworks_probe_during_screenshot_review()
    print("PASS test_v4_4_drawing_visual_review_suite_contract")
