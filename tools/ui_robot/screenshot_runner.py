from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen
from PySide6.QtWidgets import QWidget

from tools.ui_robot.human_simulator import (
    EventLogger,
    click_list_row,
    grab_widget,
    process_events,
    wait_until,
)


V3_SCREENSHOTS = [
    ("01_仪表盘.png", 0, "仪表盘"),
    ("02_单件制图.png", 1, "单件制图"),
    ("03_作业队列.png", 2, "作业队列"),
    ("04_视觉审计.png", 3, "视觉审计"),
    ("05_图纸复核.png", 4, "图纸复核"),
    ("06_批量验证.png", 5, "批量验证"),
    ("07_系统健康.png", 6, "系统健康"),
    ("08_日志诊断.png", 7, "日志诊断"),
    ("09_设置.png", 8, "设置"),
]


class ScreenshotRunner:
    def __init__(self, out_dir: Path, logger: EventLogger) -> None:
        self.out_dir = Path(out_dir)
        self.screenshots_dir = self.out_dir / "screenshots"
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logger
        self.results: list[dict[str, Any]] = []

    def capture_main_pages(self, window: Any) -> list[dict[str, Any]]:
        window.resize(1600, 1000)
        window.show()
        process_events(500)
        for filename, row, label in V3_SCREENSHOTS:
            click_list_row(window.nav, row, self.logger)
            process_events(700)
            if row == 6:
                wait_until(
                    lambda: not getattr(window.system_health_page, "_active_job_id", "")
                    and window.system_health_page.model.rowCount() > 0,
                    timeout_ms=12000,
                    step_ms=150,
                )
            result = grab_widget(window, self.screenshots_dir / filename, logger=self.logger)
            result.update({"label": label, "nav_row": row, "nav_text": window.nav.item(row).text()})
            self.results.append(result)
        return self.results

    def capture_widget(
        self,
        widget: QWidget,
        filename: str,
        label: str,
        min_bytes: int = 50_000,
        width: int = 1600,
        height: int = 1000,
    ) -> dict[str, Any]:
        widget.resize(width, height)
        widget.show()
        process_events(700)
        result = grab_widget(widget, self.screenshots_dir / filename, min_bytes=min_bytes, logger=self.logger)
        result.update({"label": label, "nav_row": None, "nav_text": label})
        self.results.append(result)
        return result


def wait_for_job_status(page: Any, job_id: str, statuses: set[str], timeout_ms: int = 8000) -> bool:
    def _predicate() -> bool:
        job = page.facade.get_job_status(job_id) or {}
        page.refresh()
        return str(job.get("status") or "") in statuses

    return wait_until(_predicate, timeout_ms=timeout_ms, step_ms=150)


def create_review_fixture(out_dir: Path) -> dict[str, Any]:
    run_dir = Path(out_dir) / "drawing_review_fixture"
    qc_dir = run_dir / "qc"
    drawing_dir = run_dir / "drawing"
    qc_dir.mkdir(parents=True, exist_ok=True)
    drawing_dir.mkdir(parents=True, exist_ok=True)

    png_path = _find_existing_png()
    if png_path is None:
        png_path = drawing_dir / "fixture_drawing.png"
        _create_fixture_png(png_path)

    manifest = {
        "run_id": "ui_acceptance_review",
        "drawing_usable": {"pass": True},
        "qc_pass_count": 10,
        "vision_score": 72,
        "hard_fail": [],
        "warnings": ["ui_acceptance_fixture"],
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    issues = [
        {
            "key": "titlebar_missing_fields",
            "severity": "major",
            "source": "ocr",
            "confidence": 0.86,
            "bbox": [0.68, 0.76, 0.24, 0.12],
            "description": "标题栏核心字段缺失",
            "evidence": {"missing": ["part_no", "material", "date"]},
            "fix_suggestion": "补齐标题栏 CustomProperty 并重新生成图纸。",
            "auto_fix_available": False,
            "human_review": "pending",
        },
        {
            "key": "datum_a_missing",
            "severity": "minor",
            "source": "geometry",
            "confidence": 0.78,
            "bbox": [0.18, 0.22, 0.18, 0.16],
            "description": "未检测到基准 A",
            "evidence": {"template_match": "none"},
            "fix_suggestion": "根据主定位面添加 Datum A 标识。",
            "auto_fix_available": True,
            "human_review": "pending",
        },
    ]
    (qc_dir / "vision_qc_v5.json").write_text(
        json.dumps({"version": "v5", "issues": issues}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {"run_dir": run_dir, "png_path": png_path, "issues": issues}


def _find_existing_png() -> Path | None:
    roots = [
        Path("drw_output/v23_validation"),
        Path("drw_output/runs"),
        Path("drw_output/v5"),
        Path(".trae/specs"),
    ]
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True):
            if path.stat().st_size > 20_000:
                return path
        for path in sorted(root.rglob("*.PNG"), key=lambda p: p.stat().st_mtime, reverse=True):
            if path.stat().st_size > 20_000:
                return path
    return None


def _create_fixture_png(path: Path) -> None:
    image = QImage(1600, 1100, QImage.Format.Format_RGB32)
    image.fill(QColor("#fbfbfb"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor("#1f2933"), 3))
    painter.drawRect(40, 40, 1520, 1020)
    painter.drawRect(1050, 810, 470, 210)
    painter.setPen(QPen(QColor("#4b5563"), 2))
    for x in range(180, 960, 120):
        painter.drawLine(x, 170, x, 660)
    for y in range(170, 660, 90):
        painter.drawLine(180, y, 940, y)
    painter.setPen(QPen(QColor("#0f766e"), 5))
    painter.drawEllipse(290, 240, 410, 300)
    painter.drawRect(820, 260, 250, 220)
    painter.setPen(QPen(QColor("#dc2626"), 5))
    painter.drawRect(1088, 860, 360, 82)
    painter.setPen(QPen(QColor("#111827"), 2))
    for y in range(840, 1010, 34):
        painter.drawLine(1050, y, 1520, y)
    painter.end()
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(str(path))
