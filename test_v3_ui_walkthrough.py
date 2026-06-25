from __future__ import annotations

from app.main import V3_WALKTHROUGH_PAGES
from app.ui.main_window import NAV_ITEMS


EXPECTED_FILES = [
    "01_仪表盘.png",
    "02_单件制图.png",
    "03_作业队列.png",
    "04_视觉审计.png",
    "05_图纸复核.png",
    "06_批量验证.png",
    "07_系统健康.png",
    "08_日志诊断.png",
    "09_设置.png",
]


def test_v3_walkthrough_page_contract() -> None:
    filenames = [item[0] for item in V3_WALKTHROUGH_PAGES]
    rows = [item[1] for item in V3_WALKTHROUGH_PAGES]
    labels = [item[2] for item in V3_WALKTHROUGH_PAGES]
    thresholds = {item[2]: item[3] for item in V3_WALKTHROUGH_PAGES}

    assert filenames == EXPECTED_FILES
    assert rows == list(range(9))
    assert labels == NAV_ITEMS
    assert thresholds["图纸复核"] == 70_000
    assert all(thresholds[label] == 50_000 for label in labels if label != "图纸复核")


if __name__ == "__main__":
    test_v3_walkthrough_page_contract()
    print("v3 UI walkthrough contract PASS")
