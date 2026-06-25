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

from PySide6.QtWidgets import QApplication

from app.ui.main_window import MainWindow
from tools.ui_robot.human_simulator import (
    EventLogger,
    click_list_row,
    click_widget,
    grab_widget,
    process_events,
    ui_acceptance_root,
)


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _latest_mock_job(page: Any, scenario: str) -> str:
    expected = f"mock_{scenario}"
    for job in page.facade.list_jobs():
        if job.get("part_name") == expected:
            return str(job.get("job_id") or "")
    return ""


def _read_event_types(run_dir: str) -> tuple[list[str], int]:
    path = Path(run_dir) / "job_event_log.jsonl" if run_dir else Path()
    if not path.exists():
        return [], 0
    events: list[str] = []
    count = 0
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                count += 1
                try:
                    payload = json.loads(line)
                    events.append(str(payload.get("type") or payload.get("event_type") or ""))
                except Exception:
                    events.append("unparseable")
    except Exception:
        return events, count
    return events, count


def _write_markdown(report: dict[str, Any], path: Path) -> None:
    screenshots = report.get("screenshots") or []
    lines = [
        "# Mock Stability Report",
        "",
        f"Generated: {report.get('generated_at', '')}",
        f"Mode: {report.get('mode', '')}",
        f"PASS: {report.get('pass')}",
        f"Duration requested: {report.get('duration_requested_s')} s",
        f"Duration observed: {report.get('duration_observed_s')} s",
        f"Job ID: {report.get('job_id', '')}",
        f"Run dir: `{report.get('run_dir', '')}`",
        "",
        "## Checks",
    ]
    checks = report.get("checks") or {}
    for key, value in checks.items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Screenshots"])
    for item in screenshots:
        lines.append(f"- `{item.get('path', '')}` size={item.get('size_bytes', 0)} pass={item.get('pass')}")
    lines.extend(["", "## Remaining Gates"])
    for item in report.get("remaining_gates") or []:
        lines.append(f"- {item}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_stability(
    out_dir: Path | None = None,
    duration_s: float = 1200.0,
    scenario: str = "normal_pass",
    sample_interval_s: float = 10.0,
    screenshot_interval_s: float = 300.0,
    completion_grace_s: float = 45.0,
) -> dict[str, Any]:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    root = Path(out_dir) if out_dir else ui_acceptance_root()
    root.mkdir(parents=True, exist_ok=True)
    screenshots_dir = root / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    samples_path = root / "stability_samples.jsonl"
    logger = EventLogger(root)

    logger.log(
        "mock_stability_started",
        "source-level mock stability run started",
        duration_s=duration_s,
        scenario=scenario,
        sample_interval_s=sample_interval_s,
        screenshot_interval_s=screenshot_interval_s,
    )

    window = MainWindow()
    window.resize(1600, 1000)
    window.show()
    process_events(1000)

    click_list_row(window.nav, 2, logger)
    page = window.job_queue_page
    page.scenario.setCurrentText(scenario)
    page.duration.setValue(float(duration_s))
    click_widget(page.btn_mock, logger, f"start {scenario} stability mock")
    process_events(500)
    job_id = _latest_mock_job(page, scenario)

    screenshots: list[dict[str, Any]] = []
    samples: list[dict[str, Any]] = []
    failures: list[str] = []
    start = time.monotonic()
    next_sample = start
    next_screenshot = start
    final_deadline = start + duration_s + completion_grace_s
    last_status = ""
    run_dir = ""

    def capture(label: str) -> None:
        filename = f"{len(screenshots) + 1:02d}_{label}.png"
        screenshots.append(grab_widget(window, screenshots_dir / filename, min_bytes=50_000, logger=logger))

    if not job_id:
        failures.append("mock job id was not found after start")
    capture("start")

    while time.monotonic() < final_deadline:
        process_events(200)
        now = time.monotonic()
        try:
            page.refresh()
        except Exception as exc:
            failures.append(f"page refresh failed: {exc}")
            break
        status = page.facade.get_job_status(job_id) if job_id else None
        if status:
            last_status = str(status.get("status") or "")
            run_dir = str(status.get("run_dir") or run_dir or "")
        if now >= next_sample:
            sample = {
                "timestamp": _iso(),
                "elapsed_s": round(now - start, 2),
                "job_id": job_id,
                "status": last_status,
                "progress": status.get("progress") if isinstance(status, dict) else None,
                "stage": status.get("stage") if isinstance(status, dict) else "",
                "last_event": status.get("last_event") if isinstance(status, dict) else "",
                "current_page": window.stack.currentIndex(),
                "nav_row": window.nav.currentRow(),
                "window_visible": window.isVisible(),
            }
            samples.append(sample)
            with samples_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(sample, ensure_ascii=False) + "\n")
            logger.log("mock_stability_sample", "sampled source UI state", **sample)
            next_sample = now + max(1.0, sample_interval_s)
        if now >= next_screenshot:
            capture(f"elapsed_{int(now - start)}s")
            next_screenshot = now + max(5.0, screenshot_interval_s)
        if last_status in {"completed", "failed", "cancelled", "timeout"}:
            break

    process_events(500)
    status = page.facade.get_job_status(job_id) if job_id else None
    if status:
        last_status = str(status.get("status") or "")
        run_dir = str(status.get("run_dir") or run_dir or "")
    capture("final")
    observed_s = round(time.monotonic() - start, 2)
    event_types, event_count = _read_event_types(run_dir)
    required_events = {"job_started", "progress", "heartbeat", "job_finished"}
    missing_events = sorted(required_events - set(event_types))
    checks = {
        "job_started": bool(job_id),
        "job_completed": last_status == "completed",
        "duration_met": observed_s >= max(0.0, duration_s - 1.0),
        "sample_count": len(samples),
        "samples_written": samples_path.exists() and samples_path.stat().st_size > 0,
        "screenshots_pass": bool(screenshots) and all(item.get("pass") for item in screenshots),
        "event_log_exists": bool(run_dir) and (Path(run_dir) / "job_event_log.jsonl").exists(),
        "event_log_count": event_count,
        "required_events_present": not missing_events,
        "missing_events": missing_events,
        "window_visible_final": window.isVisible(),
        "job_queue_page_final": window.stack.currentIndex() == 2,
        "failures": failures,
    }
    passed = bool(
        checks["job_started"]
        and checks["job_completed"]
        and checks["duration_met"]
        and checks["samples_written"]
        and checks["screenshots_pass"]
        and checks["event_log_exists"]
        and checks["required_events_present"]
        and checks["window_visible_final"]
        and not failures
    )
    report = {
        "generated_at": _now(),
        "mode": "source_qt_mock_stability",
        "pass": passed,
        "scenario": scenario,
        "duration_requested_s": duration_s,
        "duration_observed_s": observed_s,
        "sample_interval_s": sample_interval_s,
        "screenshot_interval_s": screenshot_interval_s,
        "job_id": job_id,
        "final_status": last_status,
        "run_dir": run_dir,
        "job_event_log": str(Path(run_dir) / "job_event_log.jsonl") if run_dir else "",
        "samples_jsonl": str(samples_path),
        "screenshots_dir": str(screenshots_dir),
        "screenshots": screenshots,
        "checks": checks,
        "remaining_gates": [
            "This is source-level Qt stability evidence, not Windows-level EXE click automation.",
            "The separate 2-hour UI stability gate remains pending.",
            "Real SolidWorks validation and historical visual audit coverage remain pending.",
        ],
    }
    report_path = root / "mock_stability_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_markdown(report, root / "mock_stability_report.md")
    logger.log("mock_stability_finished", "source-level mock stability run finished", passed=passed, job_id=job_id)
    window.close()
    QApplication.processEvents()
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run source-level mock UI stability validation")
    parser.add_argument("--out-dir", default="")
    parser.add_argument("--duration-s", type=float, default=1200.0)
    parser.add_argument("--scenario", default="normal_pass", choices=["normal_pass", "pass_with_warning", "recovered", "stuck_then_recovered"])
    parser.add_argument("--sample-interval-s", type=float, default=10.0)
    parser.add_argument("--screenshot-interval-s", type=float, default=300.0)
    parser.add_argument("--completion-grace-s", type=float, default=45.0)
    args = parser.parse_args(argv)
    out_dir = Path(args.out_dir) if args.out_dir else None
    report = run_stability(
        out_dir=out_dir,
        duration_s=args.duration_s,
        scenario=args.scenario,
        sample_interval_s=args.sample_interval_s,
        screenshot_interval_s=args.screenshot_interval_s,
        completion_grace_s=args.completion_grace_s,
    )
    print(json.dumps(report, ensure_ascii=False), flush=True)
    return 0 if report.get("pass") else 1


if __name__ == "__main__":
    sys.exit(main())