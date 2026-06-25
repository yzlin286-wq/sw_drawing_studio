"""Smoke test for the v2.3 Drawing Review Workbench upgrades.

Uses a generated PNG and tiny run fixture; does not invoke SolidWorks.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from app.ui.drawing_review_workbench import DrawingReviewWorkbench


FIXTURE_ROOT = Path("drw_output") / "_review_workbench_test"


def _fixture() -> tuple[Path, Path]:
    if FIXTURE_ROOT.exists():
        shutil.rmtree(FIXTURE_ROOT)
    run = FIXTURE_ROOT / "run_001"
    qc = run / "qc"
    drawing = run / "drawing"
    qc.mkdir(parents=True, exist_ok=True)
    drawing.mkdir(parents=True, exist_ok=True)
    (run / "manifest.json").write_text(
        json.dumps({"run_id": "run_001", "qc_files": {}}, ensure_ascii=False),
        encoding="utf-8",
    )
    png = drawing / "part_v5.PNG"
    img = QImage(200, 120, QImage.Format.Format_RGB32)
    img.fill(QColor("#ffffff"))
    assert img.save(str(png))
    return run, png


def _issues() -> list[dict]:
    return [
        {
            "key": "ocr_title_missing",
            "severity": "major",
            "source": "ocr",
            "confidence": 0.8,
            "bbox": [0.70, 0.70, 0.20, 0.20],
            "description": "标题栏字段缺失",
            "fix_suggestion": "补齐标题栏",
            "evidence": [{"text": "fixture"}],
            "human_review": "pending",
        },
        {
            "key": "yolo_dim_overlap",
            "severity": "minor",
            "source": "yolo_obb",
            "confidence": 0.7,
            "bbox": [0.10, 0.10, 0.20, 0.20],
            "description": "尺寸文字可能重叠",
            "fix_suggestion": "调整尺寸轨道",
            "evidence": [],
            "human_review": "pending",
        },
        {
            "key": "geometry_view_overlap",
            "severity": "critical",
            "source": "geometry_qc",
            "confidence": 1.0,
            "bbox": [0.35, 0.35, 0.20, 0.20],
            "description": "视图重叠",
            "fix_suggestion": "重新布局",
            "evidence": [],
            "human_review": "pending",
        },
    ]


def _cleanup() -> None:
    if FIXTURE_ROOT.exists():
        shutil.rmtree(FIXTURE_ROOT)


def test_filters_layers_zoom_and_review_writeback() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    run, png = _fixture()
    page = DrawingReviewWorkbench()
    page.set_context(
        png_path=str(png),
        pdf_path=str(png.with_suffix(".PDF")),
        run_dir=str(run),
        run_id="run_001",
    )
    page.set_issues(_issues())
    assert page.issue_list.count() == 3
    assert page.preview.pixmap() is not None

    page.filter_severity.setCurrentText("major")
    assert page.issue_list.count() == 1
    assert "ocr_title_missing" in page.issue_list.item(0).text()
    assert len(page._bbox_overlays) == 1

    page.filter_severity.setCurrentText("全部 Severity")
    page.layer_yolo.setChecked(False)
    assert all("yolo" not in str(item.get("source", "")).lower() for item in page._bbox_overlays)

    old_width = page.preview.pixmap().width()
    page.set_zoom(2.0)
    assert page.preview.pixmap().width() > old_width

    page.issue_list.setCurrentRow(0)
    page._on_issue_clicked(page.issue_list.item(0))
    page._on_mark_false_positive()

    tracker_path = run / "qc" / "vision_issue_tracker.json"
    review_path = run / "qc" / "human_review.json"
    manifest_path = run / "manifest.json"
    assert tracker_path.exists()
    assert review_path.exists()
    assert manifest_path.exists()
    tracker = json.loads(tracker_path.read_text(encoding="utf-8"))
    assert any(
        d.get("human_review") == "confirmed_false_positive"
        for d in tracker.get("decisions", {}).values()
    )
    review = json.loads(review_path.read_text(encoding="utf-8"))
    assert review["decision"] == "confirmed_false_positive"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["has_manual_review"] is True

    page.close()
    app.processEvents()


class _FakeFacade:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def start_drawing_review_action(self, **kwargs) -> str:
        self.calls.append(kwargs)
        return f"fake_{len(self.calls)}"

    class _Signal:
        def connect(self, *_args, **_kwargs) -> None:
            return None

    job_progress = _Signal()
    job_finished = _Signal()
    job_failed = _Signal()
    event_logged = _Signal()


def test_service_buttons_submit_job_runtime_actions() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    run, png = _fixture()
    slddrw = run / "drawing" / "part_v5.SLDDRW"
    sldprt = run / "input_work" / "part.SLDPRT"
    pdf = run / "drawing" / "part_v5.PDF"
    slddrw.write_text("fixture", encoding="utf-8")
    sldprt.parent.mkdir(parents=True, exist_ok=True)
    sldprt.write_text("fixture", encoding="utf-8")
    pdf.write_text("fixture", encoding="utf-8")

    page = DrawingReviewWorkbench()
    fake = _FakeFacade()
    page._job_facade = fake
    page.set_context(
        slddrw_path=str(slddrw),
        sldprt_path=str(sldprt),
        pdf_path=str(pdf),
        png_path=str(png),
        run_dir=str(run),
        run_id="run_001",
    )

    page._on_addin_dimension()
    assert fake.calls[-1]["action"] == "addin_dimension"
    assert fake.calls[-1]["slddrw_path"] == str(slddrw)
    assert fake.calls[-1]["sldprt_path"] == str(sldprt)
    page._active_action_job_id = ""

    page._on_docmgr_relink()
    assert fake.calls[-1]["action"] == "docmgr_relink"
    page._active_action_job_id = ""

    page._on_vision_qc_v3()
    assert fake.calls[-1]["action"] == "vision_qc_v3"
    assert fake.calls[-1]["pdf_path"] == str(pdf)

    page.close()
    app.processEvents()


if __name__ == "__main__":
    try:
        test_filters_layers_zoom_and_review_writeback()
        test_service_buttons_submit_job_runtime_actions()
        print("v2.3 drawing review workbench smoke PASS")
    finally:
        _cleanup()
