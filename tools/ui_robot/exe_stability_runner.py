from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.ui_robot.exe_click_acceptance import (
    DEFAULT_EXE,
    EventLogger,
    PAGES,
    _is_selected,
    _save_window_image,
    _visible_texts,
)


DEFAULT_OUT = REPO_ROOT / "drw_output" / "ui_acceptance" / "exe_stability_2h_v3"


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _write_markdown(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# v3.0 EXE Stability Report",
        "",
        f"Generated: {report.get('generated_at', '')}",
        f"EXE: `{report.get('exe', '')}`",
        f"Overall: {'PASS' if report.get('pass') else 'FAIL'}",
        f"Duration requested: {report.get('duration_requested_s')} s",
        f"Duration observed: {report.get('duration_observed_s')} s",
        f"Samples: {report.get('sample_count')}",
        f"Screenshots: {report.get('screenshot_count')}",
        "",
        "## Checks",
    ]
    for key, value in (report.get("checks") or {}).items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Failures"])
    failures = report.get("failures") or []
    if failures:
        for failure in failures:
            lines.append(f"- {failure}")
    else:
        lines.append("- none")
    lines.extend(["", "## Screenshots"])
    for shot in report.get("screenshots") or []:
        lines.append(f"- `{shot.get('path', '')}` page={shot.get('page', '')} size={shot.get('size_bytes', 0)} pass={shot.get('pass')}")
    lines.extend(["", "## Remaining Gates"])
    for item in report.get("remaining_gates") or []:
        lines.append(f"- {item}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _click_and_wait_selected(item: Any, timeout_s: float = 5.0) -> tuple[bool, int]:
    deadline = time.monotonic() + timeout_s
    attempts = 0
    while time.monotonic() < deadline:
        attempts += 1
        item.click_input()
        time.sleep(0.2)
        if _is_selected(item):
            return True, attempts
        time.sleep(0.3)
    return _is_selected(item), attempts


def run_stability(
    exe_path: Path,
    out_dir: Path,
    duration_s: float = 7200.0,
    sample_interval_s: float = 30.0,
    screenshot_interval_s: float = 600.0,
    page_wait_s: float = 0.5,
) -> dict[str, Any]:
    try:
        from pywinauto import Application, Desktop
    except Exception as exc:
        raise RuntimeError(f"pywinauto is required for EXE stability validation: {exc}") from exc

    out_dir.mkdir(parents=True, exist_ok=True)
    screenshots_dir = out_dir / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    samples_path = out_dir / "stability_samples.jsonl"
    logger = EventLogger(out_dir)
    logger.log(
        "exe_stability_started",
        "Windows-level EXE stability run started",
        exe=str(exe_path),
        duration_s=duration_s,
        sample_interval_s=sample_interval_s,
        screenshot_interval_s=screenshot_interval_s,
    )

    app = Application(backend="uia").start(str(exe_path), work_dir=str(REPO_ROOT), wait_for_idle=False)
    window = None
    screenshots: list[dict[str, Any]] = []
    samples: list[dict[str, Any]] = []
    failures: list[str] = []
    page_counts: dict[str, int] = {page_name: 0 for _, page_name, _ in PAGES}
    launch_start = time.monotonic()
    active_start: float | None = None
    next_sample = launch_start
    next_screenshot = launch_start

    def capture(page_name: str, label: str) -> None:
        filename = f"{len(screenshots) + 1:03d}_{label}.png"
        image = _save_window_image(window, screenshots_dir / filename)
        min_bytes = 70_000 if page_name == "图纸复核" else 50_000
        image["page"] = page_name
        image["min_bytes"] = min_bytes
        image["pass"] = bool(image.get("size_bytes", 0) >= min_bytes and image.get("sample_unique_colors", 0) >= 8)
        screenshots.append(image)
        logger.log("exe_stability_screenshot", page_name, **image)

    try:
        window = Desktop(backend="uia").window(title="SW Drawing Studio")
        window.wait("visible", timeout=90)
        window.set_focus()
        try:
            window.move_window(x=80, y=60, width=1600, height=1000, repaint=True)
        except Exception:
            pass
        time.sleep(max(1.0, page_wait_s))

        active_start = time.monotonic()
        next_sample = active_start
        next_screenshot = active_start
        deadline = active_start + duration_s
        page_index = 0
        while time.monotonic() < deadline:
            filename, page_name, min_bytes = PAGES[page_index % len(PAGES)]
            page_index += 1
            try:
                item = window.child_window(title=page_name, control_type="ListItem")
                item.wait("exists ready", timeout=20)
                selected, attempts = _click_and_wait_selected(item, timeout_s=max(5.0, page_wait_s + 2.0))
                time.sleep(max(0.1, page_wait_s))
                if not selected:
                    reason = f"{page_name}: navigation item was not selected after {attempts} attempts"
                    failures.append(reason)
                    logger.log("exe_stability_failure", reason, page=page_name, attempts=attempts)
                page_counts[page_name] += 1
                texts = _visible_texts(window)
                if page_name == "仪表盘" and any(("仪表盘" in t or "Dashboard" in t) and "异常" in t for t in texts):
                    reason = "仪表盘异常文本可见"
                    failures.append(reason)
                    logger.log("exe_stability_failure", reason, page=page_name)
            except Exception as exc:
                reason = f"{page_name}: click/sample failed: {type(exc).__name__}: {exc}"
                failures.append(reason)
                logger.log("exe_stability_failure", reason, page=page_name)
                break

            now = time.monotonic()
            if now >= next_sample:
                sample = {
                    "timestamp": _iso(),
                    "elapsed_s": round(now - active_start, 2),
                    "page": page_name,
                    "selected": selected,
                    "process": getattr(app, "process", None),
                    "window_visible": True,
                    "failure_count": len(failures),
                }
                samples.append(sample)
                with samples_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(sample, ensure_ascii=False) + "\n")
                logger.log("exe_stability_sample", page_name, **sample)
                next_sample = now + max(1.0, sample_interval_s)

            if now >= next_screenshot:
                capture(page_name, f"elapsed_{int(now - active_start)}s_{Path(filename).stem}")
                next_screenshot = now + max(5.0, screenshot_interval_s)

        final_page = PAGES[(page_index - 1) % len(PAGES)][1] if page_index else "仪表盘"
        capture(final_page, "final")
    except Exception as exc:
        failures.append(f"stability runner failed: {type(exc).__name__}: {exc}")
    finally:
        observed_s = round(time.monotonic() - (active_start or launch_start), 2)
        process_alive = False
        try:
            process_alive = bool(app.is_process_running())
        except Exception:
            try:
                process_alive = bool(window and window.exists(timeout=1))
            except Exception:
                process_alive = False

        full_cycle_required = duration_s >= len(PAGES) * max(4.0, page_wait_s + 0.5)
        checks = {
            "duration_met": observed_s >= max(0.0, duration_s - 1.0),
            "process_alive_final": process_alive,
            "samples_written": samples_path.exists() and samples_path.stat().st_size > 0,
            "sample_count": len(samples),
            "screenshots_pass": bool(screenshots) and all(shot.get("pass") for shot in screenshots),
            "full_cycle_required": full_cycle_required,
            "all_pages_visited": all(count > 0 for count in page_counts.values()) if full_cycle_required else True,
            "page_counts": page_counts,
            "failure_count": len(failures),
        }
        passed = bool(
            checks["duration_met"]
            and checks["process_alive_final"]
            and checks["samples_written"]
            and checks["screenshots_pass"]
            and checks["all_pages_visited"]
            and not failures
        )
        report = {
            "generated_at": _now(),
            "mode": "windows_exe_navigation_stability",
            "exe": str(exe_path),
            "out_dir": str(out_dir),
            "pass": passed,
            "duration_requested_s": duration_s,
            "duration_observed_s": observed_s,
            "sample_interval_s": sample_interval_s,
            "screenshot_interval_s": screenshot_interval_s,
            "page_wait_s": page_wait_s,
            "sample_count": len(samples),
            "screenshot_count": len(screenshots),
            "samples_jsonl": str(samples_path),
            "screenshots_dir": str(screenshots_dir),
            "screenshots": screenshots,
            "checks": checks,
            "failures": failures,
            "artifacts": {
                "ui_events": str(logger.path),
                "samples_jsonl": str(samples_path),
                "report_json": str(out_dir / "exe_stability_report.json"),
                "report_md": str(out_dir / "exe_stability_report.md"),
                "screenshots_dir": str(screenshots_dir),
            },
            "remaining_gates": [
                "This validates EXE navigation stability; staged real CAD validation remains separate.",
                "Historical visual audit 100 percent coverage remains pending.",
            ],
        }
        (out_dir / "exe_stability_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        _write_markdown(report, out_dir / "exe_stability_report.md")
        logger.log("exe_stability_finished", "Windows-level EXE stability run finished", passed=passed, failures=len(failures))
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
    parser = argparse.ArgumentParser(description="Run Windows-level v3.0 EXE navigation stability validation")
    parser.add_argument("--exe", default=str(DEFAULT_EXE))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT))
    parser.add_argument("--duration-s", type=float, default=7200.0)
    parser.add_argument("--sample-interval-s", type=float, default=30.0)
    parser.add_argument("--screenshot-interval-s", type=float, default=600.0)
    parser.add_argument("--page-wait-s", type=float, default=0.5)
    args = parser.parse_args(argv)
    report = run_stability(
        Path(args.exe),
        Path(args.out_dir),
        duration_s=args.duration_s,
        sample_interval_s=args.sample_interval_s,
        screenshot_interval_s=args.screenshot_interval_s,
        page_wait_s=args.page_wait_s,
    )
    print(json.dumps({"pass": report["pass"], "out_dir": report["out_dir"], "duration_observed_s": report["duration_observed_s"]}, ensure_ascii=False))
    return 0 if report.get("pass") else 1


if __name__ == "__main__":
    sys.exit(main())
