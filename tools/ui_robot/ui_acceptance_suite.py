from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.services.visual_audit_reporter import VisualAuditReporter
from app.ui.main_window import MainWindow
from tools.ui_robot.human_simulator import (
    EventLogger,
    click_list_row,
    click_widget,
    make_app,
    process_events,
    select_job_row,
    ui_acceptance_root,
    wait_until,
)
from tools.ui_robot.report_ui_acceptance import write_markdown
from tools.ui_robot.screenshot_runner import (
    ScreenshotRunner,
    create_review_fixture,
    wait_for_job_status,
)


def run_suite(out_dir: Path | None = None, mock_duration_s: float = 0.4) -> dict[str, Any]:
    app = make_app()
    root = Path(out_dir) if out_dir else ui_acceptance_root()
    root.mkdir(parents=True, exist_ok=True)
    logger = EventLogger(root)
    runner = ScreenshotRunner(root, logger)

    logger.log("suite_started", "source-level Qt UI acceptance started", out_dir=str(root))

    window = MainWindow()
    window.resize(1600, 1000)
    window.show()
    process_events(1000)

    screenshots = []
    screenshots.extend(runner.capture_main_pages(window))

    job_ops = exercise_job_queue(window, logger, mock_duration_s)
    screenshots.append(runner.capture_widget(window, "03_作业队列.png", "作业队列", min_bytes=50_000))

    visual_artifacts = exercise_visual_audit(window, logger)
    click_list_row(window.nav, 3, logger)
    screenshots.append(runner.capture_widget(window, "04_视觉审计.png", "视觉审计", min_bytes=50_000))

    review_artifacts = exercise_drawing_review(root, window, runner, logger)

    diagnostics_artifacts = exercise_logs_diagnostics(window, logger)
    click_list_row(window.nav, 7, logger)
    screenshots.append(runner.capture_widget(window, "08_日志诊断.png", "日志诊断", min_bytes=50_000))

    settings_result = exercise_settings(window, runner, logger)
    screenshots.append(settings_result["screenshot"])

    window.close()
    QApplication.processEvents()

    artifacts = {
        "ui_events": str(logger.path),
        "screenshots_dir": str(runner.screenshots_dir),
        "visual_audit_index": str(REPO_ROOT / "drw_output" / "visual_audit_index.json"),
        "visual_audit_report": visual_artifacts.get("report", ""),
        "human_review": review_artifacts.get("human_review", ""),
        "diagnostics_zip": diagnostics_artifacts.get("zip", ""),
        "settings_result": settings_result.get("result", ""),
    }
    screenshot_pass = all(item.get("pass") for item in screenshots)
    report = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "source_qt_ui_robot",
        "pass": bool(screenshot_pass and job_ops.get("normal_pass_completed") and job_ops.get("timeout_failed")),
        "screenshots": screenshots,
        "job_operations": job_ops,
        "artifacts": artifacts,
        "remaining_gates": [
            "This is source-level Qt automation, not Windows-level EXE click automation.",
            "20-minute mock stability was not run by the quick suite.",
            "Real SolidWorks validation and historical visual audit coverage remain pending.",
        ],
    }
    report_path = root / "ui_acceptance_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path = write_markdown(report_path, root / "ui_acceptance_report_v3_0.md")
    artifacts["ui_acceptance_report_json"] = str(report_path)
    artifacts["ui_acceptance_report_md"] = str(md_path)
    report["artifacts"] = artifacts
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.log("suite_finished", "source-level Qt UI acceptance finished", passed=report["pass"])
    return report


def exercise_job_queue(window: MainWindow, logger: EventLogger, duration_s: float) -> dict[str, Any]:
    click_list_row(window.nav, 2, logger)
    page = window.job_queue_page
    page.duration.setValue(duration_s)

    page.scenario.setCurrentText("normal_pass")
    click_widget(page.btn_mock, logger, "start normal_pass mock")
    normal_job = _latest_job_id(page, "mock_normal_pass")
    normal_done = wait_for_job_status(page, normal_job, {"completed"}, timeout_ms=8000) if normal_job else False

    page.scenario.setCurrentText("timeout")
    click_widget(page.btn_mock, logger, "start timeout mock")
    timeout_job = _latest_job_id(page, "mock_timeout")
    timeout_failed = wait_for_job_status(page, timeout_job, {"failed"}, timeout_ms=8000) if timeout_job else False

    retry_changed = False
    if timeout_job and select_job_row(page, timeout_job):
        click_widget(page.btn_retry, logger, "retry timeout mock")
        retry_changed = wait_until(
            lambda: (page.facade.get_job_status(timeout_job) or {}).get("retry_count", 0) >= 1,
            timeout_ms=3000,
        )

    page.scenario.setCurrentText("normal_pass")
    page.duration.setValue(max(2.0, duration_s))
    click_widget(page.btn_mock, logger, "start cancellable mock")
    cancel_job = _latest_job_id(page, "mock_normal_pass")
    running = wait_for_job_status(page, cancel_job, {"running"}, timeout_ms=3000) if cancel_job else False
    cancelled = False
    if running and cancel_job and select_job_row(page, cancel_job):
        click_widget(page.btn_cancel, logger, "cancel current mock")
        cancelled = wait_for_job_status(page, cancel_job, {"cancelled", "failed"}, timeout_ms=5000)

    page.refresh()
    logger.log(
        "job_queue_operations",
        "mock job operations completed",
        normal_job=normal_job,
        timeout_job=timeout_job,
        cancel_job=cancel_job,
        normal_done=normal_done,
        timeout_failed=timeout_failed,
        retry_changed=retry_changed,
        cancelled=cancelled,
    )
    return {
        "normal_pass_completed": normal_done,
        "timeout_failed": timeout_failed,
        "retry_changed": retry_changed,
        "cancelled_or_failed_after_cancel": cancelled,
        "normal_job": normal_job,
        "timeout_job": timeout_job,
        "cancel_job": cancel_job,
    }


def exercise_visual_audit(window: MainWindow, logger: EventLogger) -> dict[str, str]:
    click_list_row(window.nav, 3, logger)
    page = window.visual_audit_page
    page.scan()
    process_events(500)
    report_path = REPO_ROOT / "drw_output" / "visual_audit_report_ui_acceptance.xlsx"
    try:
        results = [page._result_from_file(f) for f in page._filtered_files()]
        VisualAuditReporter(results).export_xlsx(report_path)
        logger.log("visual_audit_export", "visual audit report exported", path=str(report_path), rows=len(results))
    except Exception as exc:
        logger.log("visual_audit_export_failed", str(exc), path=str(report_path))
    return {"report": str(report_path) if report_path.exists() else ""}


def exercise_drawing_review(root: Path, window: MainWindow, runner: ScreenshotRunner, logger: EventLogger) -> dict[str, Any]:
    fixture = create_review_fixture(root)
    click_list_row(window.nav, 4, logger)
    page = window.drawing_review_page
    page.set_context(
        png_path=str(fixture["png_path"]),
        run_dir=str(fixture["run_dir"]),
        run_id="ui_acceptance_review",
    )
    page.set_preview_image(str(fixture["png_path"]))
    page.set_issues(fixture["issues"])
    process_events(500)
    if page.issue_list.count() > 0:
        page.issue_list.setCurrentRow(0)
        item = page.issue_list.item(0)
        if item is not None:
            page._on_issue_clicked(item)
            logger.log("drawing_review_issue_clicked", "selected first issue")
    page.layer_ocr.setChecked(False)
    page.layer_ocr.setChecked(True)
    page._on_mark_false_positive()
    page._on_mark_confirmed_issue()
    process_events(300)
    screenshot = runner.capture_widget(window, "05_图纸复核.png", "图纸复核", min_bytes=70_000)
    human_review = Path(fixture["run_dir"]) / "qc" / "human_review.json"
    logger.log("drawing_review_operations", "human review operations completed", human_review=str(human_review))
    return {"screenshot": screenshot, "human_review": str(human_review) if human_review.exists() else ""}


def exercise_logs_diagnostics(window: MainWindow, logger: EventLogger) -> dict[str, str]:
    click_list_row(window.nav, 7, logger)
    page = window.logs_diagnostics_page
    page.refresh()
    process_events(300)
    run = page._runs[0] if page._runs else None
    if run is None:
        logger.log("diagnostics_skipped", "no run available")
        return {"zip": ""}
    try:
        from app.services.diagnostics import build_diagnostics_zip

        zip_path = build_diagnostics_zip(run.run_id)
        logger.log("diagnostics_zip", "diagnostics zip generated", run_id=run.run_id, path=str(zip_path))
        return {"zip": str(zip_path)}
    except Exception as exc:
        logger.log("diagnostics_failed", str(exc), run_id=run.run_id)
        return {"zip": ""}


def exercise_settings(window: MainWindow, runner: ScreenshotRunner, logger: EventLogger) -> dict[str, Any]:
    click_list_row(window.nav, 8, logger)
    page = window.settings_page
    page.refresh()
    process_events(200)
    page.test_connection()
    process_events(300)
    status_text = page.status.text()
    if any(key in status_text for key in ["缺失", "跳过"]) or "missing" in status_text.lower() or "skipped" in status_text.lower():
        result = "warning_no_api_key_or_model"
        logger.log("settings_test_connection_skipped", "settings page produced warning", status=status_text)
    else:
        result = "warning_network_test_deferred"
        logger.log("settings_test_connection_deferred", "settings page avoided network call", status=status_text)
    screenshot = runner.capture_widget(window, "09_设置.png", "设置", min_bytes=50_000)
    return {"screenshot": screenshot, "result": result}


def _latest_job_id(page: Any, part_name: str) -> str:
    for job in page.facade.list_jobs():
        if job.get("part_name") == part_name:
            return str(job.get("job_id") or "")
    return ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run source-level v3.0 UI acceptance suite")
    parser.add_argument("--out-dir", default="", help="Output directory under drw_output/ui_acceptance")
    parser.add_argument("--mock-duration-s", type=float, default=0.4)
    args = parser.parse_args(argv)
    out_dir = Path(args.out_dir) if args.out_dir else None
    report = run_suite(out_dir=out_dir, mock_duration_s=args.mock_duration_s)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
