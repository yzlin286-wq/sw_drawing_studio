from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QFont, QFontDatabase, QImage, QImageWriter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QListWidget, QWidget

_FONT_CONFIGURED = False


def make_app() -> QApplication:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    _configure_app_font(app)
    return app


def _configure_app_font(app: QApplication) -> None:
    """Load a CJK-capable font for Qt offscreen screenshots."""
    global _FONT_CONFIGURED
    if _FONT_CONFIGURED:
        return

    preferred_paths = [
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/msyhbd.ttc"),
        Path("C:/Windows/Fonts/Deng.ttf"),
        Path("C:/Windows/Fonts/simsun.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/NotoSansSC-VF.ttf"),
    ]
    loaded_families: list[str] = []
    for font_path in preferred_paths:
        if not font_path.exists():
            continue
        font_id = QFontDatabase.addApplicationFont(str(font_path))
        if font_id >= 0:
            loaded_families.extend(QFontDatabase.applicationFontFamilies(font_id))

    preferred_names = [
        "Microsoft YaHei",
        "微软雅黑",
        "DengXian",
        "SimSun",
        "SimHei",
        "Noto Sans SC",
    ]
    available = set(QFontDatabase.families()) | set(loaded_families)
    family = next((name for name in preferred_names if name in available), "")
    if not family and loaded_families:
        family = loaded_families[0]
    if family:
        app.setFont(QFont(family, 10))

    _FONT_CONFIGURED = True


def ui_acceptance_root() -> Path:
    return REPO_ROOT / "drw_output" / "ui_acceptance" / time.strftime("%Y%m%d_%H%M%S")


class EventLogger:
    def __init__(self, out_dir: Path) -> None:
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.out_dir / "ui_events.jsonl"

    def log(self, event_type: str, message: str = "", **data: Any) -> None:
        payload = {
            "type": event_type,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "message": message,
            "data": data,
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def process_events(ms: int = 100) -> None:
    app = make_app()
    app.processEvents()
    if ms > 0:
        QTest.qWait(ms)
        app.processEvents()


def wait_until(
    predicate: Callable[[], bool],
    timeout_ms: int = 5000,
    step_ms: int = 100,
) -> bool:
    deadline = time.monotonic() + timeout_ms / 1000.0
    while time.monotonic() < deadline:
        process_events(step_ms)
        try:
            if predicate():
                return True
        except Exception:
            return False
    return False


def click_list_row(nav: QListWidget, row: int, logger: EventLogger | None = None) -> bool:
    if row < 0 or row >= nav.count():
        if logger:
            logger.log("click_failed", "list row out of range", row=row, count=nav.count())
        return False
    item = nav.item(row)
    rect = nav.visualItemRect(item)
    if rect.isValid():
        QTest.mouseClick(
            nav.viewport(),
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            rect.center(),
        )
        process_events(150)
        if logger:
            logger.log("click", "clicked nav row", row=row, text=item.text())
        return True
    nav.setCurrentRow(row)
    process_events(150)
    if logger:
        logger.log("click_fallback", "nav visual rect invalid; setCurrentRow used", row=row, text=item.text())
    return True


def click_widget(widget: QWidget, logger: EventLogger | None = None, label: str = "") -> bool:
    if not widget.isEnabled() or not widget.isVisible():
        if logger:
            logger.log("click_failed", "widget not enabled or visible", label=label)
        return False
    QTest.mouseClick(
        widget,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(widget.width() // 2, widget.height() // 2),
    )
    process_events(150)
    if logger:
        logger.log("click", "clicked widget", label=label or widget.objectName() or widget.__class__.__name__)
    return True


def grab_widget(
    widget: QWidget,
    path: Path,
    min_bytes: int = 50_000,
    logger: EventLogger | None = None,
) -> dict[str, Any]:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    process_events(250)
    pixmap = widget.grab()
    saved = _save_png_for_acceptance(pixmap.toImage(), path)
    size = path.stat().st_size if path.exists() else 0
    stats = image_stats(path)
    result = {
        "path": str(path),
        "saved": bool(saved),
        "size_bytes": size,
        "width": stats.get("width", 0),
        "height": stats.get("height", 0),
        "sample_unique_colors": stats.get("sample_unique_colors", 0),
        "avg_luma": stats.get("avg_luma", 0),
        "min_bytes": min_bytes,
        "pass": bool(saved) and size >= min_bytes and stats.get("sample_unique_colors", 0) >= 8,
    }
    if logger:
        logger.log("screenshot", path.name, **result)
    return result


def _save_png_for_acceptance(image: QImage, path: Path) -> bool:
    writer = QImageWriter(str(path), b"png")
    writer.setCompression(0)
    writer.setQuality(100)
    if writer.write(image):
        return True
    return image.save(str(path), "PNG", 100)


def image_stats(path: Path) -> dict[str, Any]:
    image = QImage(str(path))
    if image.isNull():
        return {"width": 0, "height": 0, "sample_unique_colors": 0, "avg_luma": 0}
    width = image.width()
    height = image.height()
    colors: set[int] = set()
    luma_total = 0
    samples = 0
    step_x = max(1, width // 32)
    step_y = max(1, height // 24)
    for y in range(0, height, step_y):
        for x in range(0, width, step_x):
            color = image.pixelColor(x, y)
            rgb = (color.red() << 16) | (color.green() << 8) | color.blue()
            colors.add(rgb)
            luma_total += int(0.2126 * color.red() + 0.7152 * color.green() + 0.0722 * color.blue())
            samples += 1
    avg_luma = round(luma_total / max(1, samples), 2)
    return {
        "width": width,
        "height": height,
        "sample_unique_colors": len(colors),
        "avg_luma": avg_luma,
    }


def selected_job_id(page: Any, status: str | None = None) -> str:
    jobs = page.facade.list_jobs()
    for job in jobs:
        if status is None or job.get("status") == status:
            return str(job.get("job_id") or "")
    return ""


def select_job_row(page: Any, job_id: str) -> bool:
    for row in range(page.model.rowCount()):
        item = page.model.item(row, 0)
        if item and item.text() == job_id:
            page.table.selectRow(row)
            process_events(100)
            return True
    return False
