from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.ui_robot.exe_click_acceptance import (  # noqa: E402
    DEFAULT_EXE,
    EventLogger,
    _is_selected,
    _save_window_image,
)


DEFAULT_OUT = REPO_ROOT / "drw_output" / "ui_acceptance" / "exe_job_queue_v3"
SCENARIOS = [
    "normal_pass",
    "pass_with_warning",
    "recovered",
    "stuck_then_recovered",
    "failed",
    "timeout",
]
HEADERS = {
    "job_id",
    "part",
    "stage",
    "progress",
    "status",
    "retry_count",
    "duration",
    "sw_pid",
    "last_event",
    "action",
}


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _button(window: Any, title: str) -> Any:
    btn = window.child_window(title=title, control_type="Button")
    btn.wait("exists ready", timeout=20)
    return btn


def _is_visible(control: Any) -> bool:
    try:
        return bool(control.is_visible())
    except Exception:
        return True


def _visible_descendants(window: Any, control_type: str) -> list[Any]:
    controls = []
    for ctrl in window.descendants(control_type=control_type):
        if _is_visible(ctrl):
            controls.append(ctrl)
    return controls


def _rect(control: Any) -> Any:
    return control.rectangle()


def _select_job_queue(window: Any) -> None:
    item = window.child_window(title="作业队列", control_type="ListItem")
    item.wait("exists ready", timeout=30)
    item.click_input()
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if _is_selected(item):
            return
        time.sleep(0.2)
    raise RuntimeError("作业队列导航项未被选中")


def _scenario_combo(window: Any) -> Any:
    combos = _visible_descendants(window, "ComboBox")
    if not combos:
        raise RuntimeError("No visible ComboBox controls found on Job Queue page")
    return sorted(combos, key=lambda c: (_rect(c).top, _rect(c).left))[-1]


def _duration_spinner(window: Any) -> Any:
    spinners = _visible_descendants(window, "Spinner")
    if not spinners:
        raise RuntimeError("No visible duration Spinner found on Job Queue page")
    return sorted(spinners, key=lambda c: (_rect(c).top, _rect(c).left))[-1]


def _set_scenario(window: Any, scenario: str) -> None:
    if scenario not in SCENARIOS:
        raise ValueError(f"Unknown mock scenario: {scenario}")
    combo = _scenario_combo(window)
    try:
        combo.select(scenario)
        return
    except Exception:
        pass
    from pywinauto import keyboard

    combo.click_input()
    time.sleep(0.2)
    keyboard.send_keys("{HOME}")
    for _ in range(SCENARIOS.index(scenario)):
        keyboard.send_keys("{DOWN}")
    keyboard.send_keys("{ENTER}")
    time.sleep(0.2)


def _set_duration(window: Any, duration_s: float) -> None:
    spinner = _duration_spinner(window)
    from pywinauto import keyboard

    spinner.click_input()
    time.sleep(0.1)
    keyboard.send_keys("^a")
    keyboard.send_keys(str(round(duration_s, 1)))
    keyboard.send_keys("{ENTER}")
    time.sleep(0.2)


def _table(window: Any) -> Any:
    tables = _visible_descendants(window, "Table")
    if not tables:
        raise RuntimeError("No visible job table found")
    return max(tables, key=lambda t: (_rect(t).width(), _rect(t).height()))


def _cell_text(cell: Any) -> str:
    try:
        return str(cell.window_text()).strip()
    except Exception:
        return ""


def _group_cells_by_row(cells: list[Any]) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for cell in sorted(cells, key=lambda c: (_rect(c).top, _rect(c).left)):
        top = _rect(cell).top
        for row in rows:
            if abs(_rect(row[0]).top - top) <= 6:
                row.append(cell)
                break
        else:
            rows.append([cell])
    return [sorted(row, key=lambda c: _rect(c).left) for row in rows]


def _table_rows(window: Any) -> list[dict[str, Any]]:
    table = _table(window)
    cells = [
        cell
        for cell in table.descendants(control_type="DataItem")
        if _is_visible(cell) and _cell_text(cell)
    ]
    rows: list[dict[str, Any]] = []
    for group in _group_cells_by_row(cells):
        values = [_cell_text(cell) for cell in group]
        if not values or {v.lower() for v in values[:10]} & HEADERS:
            continue
        if len(values) < 5:
            continue
        row = {
            "job_id": values[0],
            "part": values[1] if len(values) > 1 else "",
            "stage": values[2] if len(values) > 2 else "",
            "progress": values[3] if len(values) > 3 else "",
            "status": values[4] if len(values) > 4 else "",
            "retry_count": values[5] if len(values) > 5 else "0",
            "duration": values[6] if len(values) > 6 else "",
            "sw_pid": values[7] if len(values) > 7 else "",
            "last_event": values[8] if len(values) > 8 else "",
            "action": values[9] if len(values) > 9 else "",
            "values": values,
            "click_target": group[0],
        }
        if row["job_id"] and row["part"]:
            rows.append(row)
    return rows


def _select_row(row: dict[str, Any]) -> None:
    target = row.get("click_target")
    if target is None:
        raise RuntimeError(f"Row has no click target: {row}")
    target.click_input()
    time.sleep(0.2)


def _wait_for_row(
    window: Any,
    predicate: Callable[[dict[str, Any]], bool],
    timeout_s: float,
    label: str,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_s
    last_rows: list[dict[str, Any]] = []
    while time.monotonic() < deadline:
        last_rows = _table_rows(window)
        for row in last_rows:
            if predicate(row):
                return row
        time.sleep(0.5)
    slim_rows = [
        {k: v for k, v in row.items() if k not in {"click_target"}}
        for row in last_rows[:8]
    ]
    raise TimeoutError(f"Timed out waiting for {label}; recent rows={slim_rows}")


def _retry_count(row: dict[str, Any]) -> int:
    text = str(row.get("retry_count") or "0")
    match = re.search(r"\d+", text)
    return int(match.group(0)) if match else 0


def _start_mock_job(
    window: Any,
    scenario: str,
    duration_s: float,
    timeout_s: float = 20.0,
) -> dict[str, Any]:
    before_ids = {row["job_id"] for row in _table_rows(window)}
    _set_scenario(window, scenario)
    _set_duration(window, duration_s)
    _button(window, "启动 Mock").click_input()
    part_name = f"mock_{scenario}"
    return _wait_for_row(
        window,
        lambda row: row.get("part") == part_name and row.get("job_id") not in before_ids,
        timeout_s=timeout_s,
        label=f"new {part_name} row",
    )


def _wait_job_status(
    window: Any,
    job_id: str,
    statuses: set[str],
    timeout_s: float,
    label: str,
) -> dict[str, Any]:
    return _wait_for_row(
        window,
        lambda row: row.get("job_id") == job_id and str(row.get("status")) in statuses,
        timeout_s=timeout_s,
        label=label,
    )


def _copy_row(row: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in row.items() if k != "click_target"}


def _capture(window: Any, screenshots_dir: Path, name: str, logger: EventLogger) -> dict[str, Any]:
    image = _save_window_image(window, screenshots_dir / name)
    image["pass"] = bool(image.get("size_bytes", 0) >= 50_000 and image.get("sample_unique_colors", 0) >= 8)
    logger.log("job_queue_screenshot", name, **image)
    return image


def _run_roots(exe_path: Path) -> list[Path]:
    roots = [
        REPO_ROOT / "drw_output" / "runs",
        Path(exe_path).resolve().parent / "drw_output" / "runs",
    ]
    unique: list[Path] = []
    for root in roots:
        if root not in unique:
            unique.append(root)
    return unique


def _locate_run_dir(job_id: str, run_roots: list[Path]) -> str:
    matches: list[Path] = []
    for runs_dir in run_roots:
        if runs_dir.exists():
            matches.extend(runs_dir.glob(f"mock_*_{job_id}"))
    matches = sorted(matches, key=lambda p: p.stat().st_mtime, reverse=True)
    return str(matches[0]) if matches else ""


def _job_log_has_action(job_id: str, action: str, run_roots: list[Path]) -> bool:
    run_dir = _locate_run_dir(job_id, run_roots)
    if not run_dir:
        return False
    log_path = Path(run_dir) / "job_event_log.jsonl"
    if not log_path.exists():
        return False
    for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("data", {}).get("action") == action:
            return True
    return False


def _close_opened_folder(folder_name: str) -> None:
    try:
        from pywinauto import Desktop

        for win in Desktop(backend="uia").windows():
            try:
                title = win.window_text()
            except Exception:
                continue
            if folder_name and folder_name in title:
                win.close()
    except Exception:
        return


def _write_markdown(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# v3.0 EXE Job Queue Acceptance",
        "",
        f"Generated: {report.get('generated_at', '')}",
        f"EXE: `{report.get('exe', '')}`",
        f"Overall: {'PASS' if report.get('pass') else 'FAIL'}",
        "",
        "## Checks",
        "",
    ]
    for key, value in (report.get("checks") or {}).items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Jobs", ""])
    for key, value in (report.get("jobs") or {}).items():
        lines.append(f"- {key}: `{json.dumps(value, ensure_ascii=False)}`")
    lines.extend(["", "## Screenshots", ""])
    for shot in report.get("screenshots") or []:
        lines.append(f"- `{shot.get('path', '')}` size={shot.get('size_bytes', 0)} pass={shot.get('pass')}")
    lines.extend(["", "## Remaining Gates", ""])
    for item in report.get("remaining_gates") or []:
        lines.append(f"- {item}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_acceptance(
    exe_path: Path,
    out_dir: Path,
    mock_duration_s: float = 0.8,
    cancel_duration_s: float = 8.0,
    skip_duration_s: float = 8.0,
    exercise_open_dir: bool = True,
) -> dict[str, Any]:
    try:
        from pywinauto import Application, Desktop
    except Exception as exc:
        raise RuntimeError(f"pywinauto is required for EXE Job Queue acceptance: {exc}") from exc

    out_dir.mkdir(parents=True, exist_ok=True)
    screenshots_dir = out_dir / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    logger = EventLogger(out_dir)
    logger.log("suite_started", "Windows-level EXE Job Queue acceptance started", exe=str(exe_path))
    run_roots = _run_roots(exe_path)

    app = Application(backend="uia").start(str(exe_path), work_dir=str(REPO_ROOT), wait_for_idle=False)
    window = None
    jobs: dict[str, Any] = {}
    screenshots: list[dict[str, Any]] = []
    failures: list[str] = []
    try:
        window = Desktop(backend="uia").window(title="SW Drawing Studio")
        window.wait("visible", timeout=90)
        window.set_focus()
        try:
            window.move_window(x=80, y=60, width=1600, height=1000, repaint=True)
        except Exception:
            pass
        time.sleep(1.0)
        _select_job_queue(window)
        screenshots.append(_capture(window, screenshots_dir, "01_job_queue_loaded.png", logger))

        normal = _start_mock_job(window, "normal_pass", mock_duration_s)
        normal_done = _wait_job_status(
            window,
            normal["job_id"],
            {"completed"},
            timeout_s=max(20.0, mock_duration_s + 12.0),
            label="normal_pass completed",
        )
        jobs["normal_pass"] = _copy_row(normal_done)
        screenshots.append(_capture(window, screenshots_dir, "02_normal_pass_completed.png", logger))

        if exercise_open_dir:
            _select_row(normal_done)
            _button(window, "打开目录").click_input()
            time.sleep(1.0)
            run_dir = _locate_run_dir(normal_done["job_id"], run_roots)
            jobs["normal_pass"]["run_dir"] = run_dir
            _close_opened_folder(Path(run_dir).name)
            window.set_focus()

        timeout_job = _start_mock_job(window, "timeout", mock_duration_s)
        timeout_failed = _wait_job_status(
            window,
            timeout_job["job_id"],
            {"failed"},
            timeout_s=max(25.0, mock_duration_s + 15.0),
            label="timeout failed",
        )
        jobs["timeout"] = _copy_row(timeout_failed)
        _button(window, "刷新").click_input()
        time.sleep(0.5)
        screenshots.append(_capture(window, screenshots_dir, "03_timeout_failed_ui_responsive.png", logger))

        _select_row(timeout_failed)
        _button(window, "重试选中").click_input()
        retry_started = _wait_for_row(
            window,
            lambda row: row.get("job_id") == timeout_job["job_id"] and _retry_count(row) >= 1,
            timeout_s=15.0,
            label="timeout retry_count >= 1",
        )
        retry_final = _wait_job_status(
            window,
            timeout_job["job_id"],
            {"failed"},
            timeout_s=max(25.0, mock_duration_s + 15.0),
            label="timeout retry failed with clear status",
        )
        jobs["retry_timeout"] = {
            "started": _copy_row(retry_started),
            "final": _copy_row(retry_final),
        }
        screenshots.append(_capture(window, screenshots_dir, "04_timeout_retry_failed.png", logger))

        cancel_job = _start_mock_job(window, "normal_pass", cancel_duration_s)
        cancel_running = _wait_job_status(
            window,
            cancel_job["job_id"],
            {"running"},
            timeout_s=12.0,
            label="cancel job running",
        )
        _select_row(cancel_running)
        _button(window, "取消当前").click_input()
        cancel_final = _wait_job_status(
            window,
            cancel_job["job_id"],
            {"cancelled"},
            timeout_s=15.0,
            label="cancel job cancelled",
        )
        jobs["cancel"] = _copy_row(cancel_final)
        screenshots.append(_capture(window, screenshots_dir, "05_cancelled.png", logger))

        skip_job = _start_mock_job(window, "normal_pass", skip_duration_s)
        skip_running = _wait_job_status(
            window,
            skip_job["job_id"],
            {"running"},
            timeout_s=12.0,
            label="skip job running",
        )
        _select_row(skip_running)
        _button(window, "跳过选中").click_input()
        skip_final = _wait_job_status(
            window,
            skip_job["job_id"],
            {"completed"},
            timeout_s=15.0,
            label="skip job completed",
        )
        jobs["skip"] = _copy_row(skip_final)
        jobs["skip"]["run_dir"] = _locate_run_dir(skip_job["job_id"], run_roots)
        jobs["skip"]["event_log_has_skipped"] = _job_log_has_action(skip_job["job_id"], "skipped", run_roots)
        screenshots.append(_capture(window, screenshots_dir, "06_skipped.png", logger))

        screenshots.append(_capture(window, screenshots_dir, "07_final.png", logger))
    except Exception as exc:
        failures.append(f"{type(exc).__name__}: {exc}")
        logger.log("suite_failure", str(exc), error_type=type(exc).__name__)
        if window is not None:
            try:
                screenshots.append(_capture(window, screenshots_dir, "failure.png", logger))
            except Exception:
                pass
    finally:
        process_alive = False
        try:
            process_alive = bool(app.is_process_running())
        except Exception:
            process_alive = False
        checks = {
            "normal_pass_completed": jobs.get("normal_pass", {}).get("status") == "completed",
            "timeout_failed": jobs.get("timeout", {}).get("status") == "failed",
            "retry_count_changed": _retry_count((jobs.get("retry_timeout") or {}).get("final") or {}) >= 1,
            "retry_final_failed": ((jobs.get("retry_timeout") or {}).get("final") or {}).get("status") == "failed",
            "cancelled": jobs.get("cancel", {}).get("status") == "cancelled",
            "skip_completed": jobs.get("skip", {}).get("status") == "completed",
            "skip_event_logged": bool(jobs.get("skip", {}).get("event_log_has_skipped")),
            "open_run_dir_exercised": bool(not exercise_open_dir or jobs.get("normal_pass", {}).get("run_dir")),
            "screenshots_pass": bool(screenshots) and all(s.get("pass") for s in screenshots),
            "process_alive_before_cleanup": process_alive,
            "failure_count": len(failures),
        }
        passed = all(value is True for key, value in checks.items() if key != "failure_count") and len(failures) == 0
        report = {
            "generated_at": _now(),
            "mode": "windows_exe_job_queue_acceptance",
            "exe": str(exe_path),
            "out_dir": str(out_dir),
            "pass": passed,
            "checks": checks,
            "failures": failures,
            "jobs": jobs,
            "screenshots": screenshots,
            "run_roots_checked": [str(root) for root in run_roots],
            "artifacts": {
                "ui_events": str(out_dir / "ui_events.jsonl"),
                "screenshots_dir": str(screenshots_dir),
                "report_json": str(out_dir / "exe_job_queue_acceptance_report.json"),
                "report_md": str(out_dir / "exe_job_queue_acceptance_report.md"),
            },
            "remaining_gates": [
                "Historical visual audit 100 percent coverage remains pending.",
                "v3.0 staged real CAD validation remains pending.",
                "Final dist/sw_drawing_studio.exe remains pending.",
                "Final release_log_v3_0.md remains pending.",
            ],
        }
        (out_dir / "exe_job_queue_acceptance_report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        _write_markdown(report, out_dir / "exe_job_queue_acceptance_report.md")
        logger.log("suite_finished", "Windows-level EXE Job Queue acceptance finished", passed=passed)
        if window is not None:
            try:
                window.close()
                time.sleep(1)
            except Exception:
                pass
        try:
            app.kill()
        except Exception:
            pass
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Windows-level v3.0 EXE Job Queue acceptance")
    parser.add_argument("--exe", default=str(DEFAULT_EXE))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT))
    parser.add_argument("--mock-duration-s", type=float, default=0.8)
    parser.add_argument("--cancel-duration-s", type=float, default=8.0)
    parser.add_argument("--skip-duration-s", type=float, default=8.0)
    parser.add_argument("--no-open-dir", action="store_true")
    args = parser.parse_args(argv)

    report = run_acceptance(
        Path(args.exe),
        Path(args.out_dir),
        mock_duration_s=args.mock_duration_s,
        cancel_duration_s=args.cancel_duration_s,
        skip_duration_s=args.skip_duration_s,
        exercise_open_dir=not args.no_open_dir,
    )
    print(json.dumps({"pass": report["pass"], "out_dir": report["out_dir"]}, ensure_ascii=False))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
