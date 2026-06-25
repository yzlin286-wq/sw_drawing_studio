"""Smoke test for the v2.3 Visual Audit page.

Uses tiny generated fixtures and does not invoke SolidWorks.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.services.generated_output_scanner import GeneratedOutputScanner
from app.services.job_event_bus import JobEventBus
from app.services.job_queue import JobQueue, JobRecord
from app.services.job_runner import JobRunner
from app.ui.main_window import NAV_ITEMS, PAGE_VISUAL_AUDIT, MainWindow
from app.ui.visual_audit_page import VisualAuditPage


def _fixture(tmp_root: Path) -> Path:
    run = tmp_root / "run_001"
    drawing = run / "drawing"
    qc = run / "qc"
    drawing.mkdir(parents=True, exist_ok=True)
    qc.mkdir(parents=True, exist_ok=True)
    (run / "manifest.json").write_text("{}", encoding="utf-8")
    (drawing / "part_a_v5.PDF").write_bytes(b"%PDF-1.4\n% fixture\n")
    (drawing / "part_a_v5.PNG").write_bytes(b"\x89PNG\r\n\x1a\n")
    (qc / "vision_qc_v5.json").write_text(
        json.dumps(
            {
                "version": "v5",
                "success": True,
                "issues": [
                    {
                        "key": "missing_ra",
                        "severity": "minor",
                        "source": "template",
                        "confidence": 0.7,
                        "bbox": [0, 0, 0, 0],
                        "fix_suggestion": "补充粗糙度符号",
                        "evidence": [],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return run


def test_scanner_recognizes_run_qc(tmp_path: Path | None = None) -> None:
    root = Path("drw_output") / "_visual_audit_test_fixture"
    if root.exists():
        import shutil

        shutil.rmtree(root)
    run = _fixture(root)
    scanner = GeneratedOutputScanner([str(root)])
    files = scanner.scan()
    assert len(files) == 2
    assert all(f.has_vision_qc for f in files), files
    assert all(f.vision_qc_version == "v5" for f in files), files
    assert all(Path(f.run_dir) == run / "drawing" for f in files)


def test_visual_audit_page_scan() -> None:
    root = Path("drw_output") / "_visual_audit_test_fixture"
    _fixture(root)
    app = QApplication.instance() or QApplication(sys.argv)
    page = VisualAuditPage()
    page.scanner = GeneratedOutputScanner([str(root)])
    page.service = page.service.__class__(page.scanner)
    page.scan()
    assert page.model.rowCount() == 2
    text = page.summary_label.text()
    assert "audited=2" in text
    page.bucket_filter.setCurrentText("minor")
    assert page.model.rowCount() == 2
    page.close()
    app.processEvents()


def test_main_window_nav() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    assert NAV_ITEMS[PAGE_VISUAL_AUDIT] == "视觉审计"
    window = MainWindow()
    assert hasattr(window, "visual_audit_page")
    assert window.stack.indexOf(window.visual_audit_page) == PAGE_VISUAL_AUDIT
    window.close()
    app.processEvents()


def test_vision_audit_worker_args_contract() -> None:
    record = JobRecord(
        job_id="va_args",
        part_name="part_a_v5",
        part_path="drw_output/_visual_audit_test_fixture/run_001/drawing/part_a_v5.PDF",
        job_type="vision_audit",
    )
    record.result["png_path"] = "drw_output/_visual_audit_test_fixture/run_001/drawing/part_a_v5.PNG"
    record.result["run_dir"] = "drw_output/_visual_audit_test_fixture/run_001"
    args = JobRunner(JobEventBus(), JobQueue())._build_worker_args(record)
    assert args[args.index("--pdf-path") + 1].endswith("part_a_v5.PDF")
    assert args[args.index("--png-path") + 1].endswith("part_a_v5.PNG")
    assert args[args.index("--run-dir") + 1].endswith("run_001")


if __name__ == "__main__":
    app = QApplication.instance() or QApplication(sys.argv)
    test_scanner_recognizes_run_qc()
    test_visual_audit_page_scan()
    test_main_window_nav()
    test_vision_audit_worker_args_contract()
    print("v2.3 visual audit page smoke PASS")
