import sys
import time
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtGui import QFont, QFontDatabase, QImage, QImageWriter
from PySide6.QtWidgets import QApplication

from app.ui.main_window import MainWindow, NAV_ITEMS
from app.services.resource_paths import bundle_root, pipeline_script_path


def resource_path(relative: str) -> Path:
    return bundle_root() / relative


_FONT_CONFIGURED = False


def configure_chinese_font(app: QApplication) -> None:
    """Prefer a Windows CJK font so Chinese UI screenshots do not render tofu."""
    global _FONT_CONFIGURED
    if _FONT_CONFIGURED:
        return

    font_paths = [
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/msyhbd.ttc"),
        Path("C:/Windows/Fonts/Deng.ttf"),
        Path("C:/Windows/Fonts/simsun.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/NotoSansSC-VF.ttf"),
    ]
    loaded_families: list[str] = []
    for font_path in font_paths:
        if not font_path.exists():
            continue
        font_id = QFontDatabase.addApplicationFont(str(font_path))
        if font_id >= 0:
            loaded_families.extend(QFontDatabase.applicationFontFamilies(font_id))

    preferred = ["Microsoft YaHei", "微软雅黑", "DengXian", "SimSun", "SimHei", "Noto Sans SC"]
    available = set(QFontDatabase.families()) | set(loaded_families)
    family = next((name for name in preferred if name in available), "")
    if not family and loaded_families:
        family = loaded_families[0]
    if family:
        app.setFont(QFont(family, 10))
    _FONT_CONFIGURED = True


def _run_worker(argv: list[str]) -> int:
    if not argv:
        print("[main] missing worker type", file=sys.stderr)
        return 2
    worker_type = argv[0]
    worker_modules = {
        "cad": "app.workers.cad_job_worker",
        "batch": "app.workers.batch_job_worker",
        "drawing_review": "app.workers.drawing_review_worker",
        "qc_action": "app.workers.qc_action_worker",
        "llm_action": "app.workers.llm_action_worker",
        "system_health": "app.workers.health_check_worker",
        "solidworks_com_probe": "app.workers.solidworks_com_probe_worker",
        "vision_audit": "app.workers.vision_audit_worker",
        "mock": "app.workers.mock_long_job_worker",
    }
    module_name = worker_modules.get(worker_type)
    if not module_name:
        print(f"[main] unknown worker type: {worker_type}", file=sys.stderr)
        return 2
    sys.argv = [f"{module_name}.py", *argv[1:]]
    module = __import__(module_name, fromlist=["main"])
    return int(module.main())


def _run_pipeline_script(argv: list[str]) -> int:
    if not argv:
        print("[main] missing pipeline script key", file=sys.stderr)
        return 2
    script_key = argv[0]
    script_path = pipeline_script_path(script_key)
    if not script_path.exists():
        print(f"[main] pipeline script missing: {script_path}", file=sys.stderr)
        return 2
    import runpy

    sys.argv = [str(script_path), *argv[1:]]
    runpy.run_path(str(script_path), run_name="__main__")
    return 0


def _print_pipeline_script_info(argv: list[str]) -> int:
    if not argv:
        print("[main] missing pipeline script key", file=sys.stderr)
        return 2
    script_key = argv[0]
    script_path = pipeline_script_path(script_key)
    info = {
        "script_key": script_key,
        "script_path": str(script_path),
        "exists": script_path.exists(),
    }
    import json

    print(json.dumps(info, ensure_ascii=False), flush=True)
    return 0 if script_path.exists() else 2


V3_WALKTHROUGH_PAGES = [
    ("01_仪表盘.png", 0, "仪表盘", 50_000),
    ("02_单件制图.png", 1, "单件制图", 50_000),
    ("03_作业队列.png", 2, "作业队列", 50_000),
    ("04_视觉审计.png", 3, "视觉审计", 50_000),
    ("05_图纸复核.png", 4, "图纸复核", 70_000),
    ("06_批量验证.png", 5, "批量验证", 50_000),
    ("07_系统健康.png", 6, "系统健康", 50_000),
    ("08_日志诊断.png", 7, "日志诊断", 50_000),
    ("09_设置.png", 8, "设置", 50_000),
]


def _process_events_for(app: QApplication, ms: int) -> None:
    app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents)
    loop = QEventLoop()
    QTimer.singleShot(max(0, ms), loop.quit)
    loop.exec(QEventLoop.ProcessEventsFlag.AllEvents)
    app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents)


def _wait_for_page_ready(app: QApplication, window: MainWindow, idx: int, timeout_ms: int = 12_000) -> None:
    if idx != 6:
        _process_events_for(app, 350)
        return
    deadline = time.monotonic() + (timeout_ms / 1000.0)
    page = getattr(window, "system_health_page", None)
    while time.monotonic() < deadline:
        _process_events_for(app, 150)
        try:
            active_job = str(getattr(page, "_active_job_id", "") or "")
            row_count = int(page.model.rowCount()) if page is not None else 0
        except Exception:
            break
        if not active_job and row_count > 0:
            return


def _save_png_for_acceptance(image: QImage, path: Path) -> bool:
    writer = QImageWriter(str(path), b"png")
    writer.setCompression(0)
    writer.setQuality(100)
    if writer.write(image):
        return True
    return image.save(str(path), "PNG", 100)


def _run_ui_walkthrough(argv: list[str]) -> int:
    out_dir = Path(argv[0]) if argv else Path("drw_output") / "ui_acceptance" / "v3_internal_walkthrough"
    screenshots_dir = out_dir / "screenshots"
    out_dir.mkdir(parents=True, exist_ok=True)
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    configure_chinese_font(app)
    window = MainWindow()
    window.resize(1600, 1000)
    window.show()
    app.processEvents()

    results = []
    for filename, idx, label, min_bytes in V3_WALKTHROUGH_PAGES:
        window.nav.setCurrentRow(idx)
        _wait_for_page_ready(app, window, idx)
        screenshot_path = screenshots_dir / filename
        pixmap = window.grab()
        saved = _save_png_for_acceptance(pixmap.toImage(), screenshot_path)
        current = window.stack.currentIndex()
        size_bytes = screenshot_path.stat().st_size if screenshot_path.exists() else 0
        nav_text = window.nav.currentItem().text() if window.nav.currentItem() else ""
        results.append({
            "page_index": idx,
            "page_name": label,
            "current_index": current,
            "nav_text": nav_text,
            "screenshot": str(screenshot_path),
            "saved": saved,
            "screenshot_size_bytes": size_bytes,
            "min_bytes": min_bytes,
            "pass": saved and current == idx and nav_text == label and screenshot_path.exists() and size_bytes >= min_bytes,
        })

    report = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "exe_internal_ui_walkthrough",
        "window_title": window.windowTitle(),
        "expected_nav": NAV_ITEMS,
        "page_count": len(results),
        "screenshots_dir": str(screenshots_dir),
        "all_pages_pass": all(item["pass"] for item in results),
        "results": results,
        "remaining_gates": [
            "该 walkthrough 仅证明当前应用的 v3 中文页面渲染。",
            "Windows 级 EXE 点击自动化与 2 小时 UI 稳定性仍是独立门槛。",
        ],
    }
    report_path = out_dir / "ui_walkthrough_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False), flush=True)
    window.close()
    app.quit()
    return 0 if report["all_pages_pass"] and report["page_count"] == 9 else 1


def main() -> int:
    if len(sys.argv) >= 2 and sys.argv[1] == "--worker":
        return _run_worker(sys.argv[2:])
    if len(sys.argv) >= 2 and sys.argv[1] == "--pipeline-script-info":
        return _print_pipeline_script_info(sys.argv[2:])
    if len(sys.argv) >= 2 and sys.argv[1] == "--pipeline-script":
        return _run_pipeline_script(sys.argv[2:])
    if len(sys.argv) >= 2 and sys.argv[1] == "--ui-walkthrough":
        return _run_ui_walkthrough(sys.argv[2:])

    app = QApplication(sys.argv)

    try:
        from qt_material import apply_stylesheet  # type: ignore

        apply_stylesheet(app, theme="light_blue.xml")
    except Exception as exc:
        print(f"[main] qt_material 加载失败，使用默认主题: {exc}")
    configure_chinese_font(app)

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
