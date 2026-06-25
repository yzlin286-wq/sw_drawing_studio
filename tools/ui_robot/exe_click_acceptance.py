from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EXE = REPO_ROOT / "dist_v3_smoke" / "sw_drawing_studio.exe"
DEFAULT_OUT = REPO_ROOT / "drw_output" / "ui_acceptance" / "exe_click_v3"

PAGES = [
    ("01_仪表盘.png", "仪表盘", 50_000),
    ("02_单件制图.png", "单件制图", 50_000),
    ("03_作业队列.png", "作业队列", 50_000),
    ("04_视觉审计.png", "视觉审计", 50_000),
    ("05_图纸复核.png", "图纸复核", 70_000),
    ("06_批量验证.png", "批量验证", 50_000),
    ("07_系统健康.png", "系统健康", 50_000),
    ("08_日志诊断.png", "日志诊断", 50_000),
    ("09_设置.png", "设置", 50_000),
]


class EventLogger:
    def __init__(self, out_dir: Path) -> None:
        self.path = out_dir / "ui_events.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, event_type: str, message: str = "", **data: Any) -> None:
        payload = {
            "type": event_type,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "message": message,
            "data": data,
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _image_stats(path: Path) -> dict[str, Any]:
    try:
        from PIL import Image

        with Image.open(path) as image:
            width, height = image.size
            colors: set[tuple[int, int, int]] = set()
            luma_total = 0
            samples = 0
            step_x = max(1, width // 32)
            step_y = max(1, height // 24)
            rgb = image.convert("RGB")
            for y in range(0, height, step_y):
                for x in range(0, width, step_x):
                    r, g, b = rgb.getpixel((x, y))
                    colors.add((r, g, b))
                    luma_total += int(0.2126 * r + 0.7152 * g + 0.0722 * b)
                    samples += 1
            return {
                "width": width,
                "height": height,
                "sample_unique_colors": len(colors),
                "avg_luma": round(luma_total / max(1, samples), 2),
            }
    except Exception as exc:
        return {"width": 0, "height": 0, "sample_unique_colors": 0, "avg_luma": 0, "error": str(exc)}


def _save_window_image(window: Any, path: Path) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = window.capture_as_image()
    image.save(path, "PNG", compress_level=0)
    size = path.stat().st_size if path.exists() else 0
    stats = _image_stats(path)
    return {
        "path": str(path),
        "size_bytes": size,
        **stats,
    }


def _is_selected(item: Any) -> bool:
    try:
        return bool(item.iface_selection_item.CurrentIsSelected)
    except Exception:
        return False


def _visible_texts(window: Any) -> list[str]:
    texts: list[str] = []
    try:
        for child in window.descendants(control_type="Text"):
            try:
                text = child.window_text()
            except Exception:
                continue
            if text:
                texts.append(text)
    except Exception:
        pass
    return texts


def _write_markdown(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# v3.0 EXE Click Acceptance",
        "",
        f"Generated: {report.get('generated_at', '')}",
        f"EXE: `{report.get('exe', '')}`",
        f"Overall: {'PASS' if report.get('pass') else 'FAIL'}",
        "",
        "## Pages",
        "",
        "| Page | Result | Screenshot | Size | Colors |",
        "| --- | --- | --- | ---: | ---: |",
    ]
    for page in report.get("pages", []):
        lines.append(
            "| {page} | {result} | `{shot}` | {size} | {colors} |".format(
                page=page.get("page"),
                result="PASS" if page.get("pass") else "FAIL",
                shot=page.get("screenshot"),
                size=page.get("size_bytes"),
                colors=page.get("sample_unique_colors"),
            )
        )
    lines += [
        "",
        "## Remaining Gates",
        "",
        "- This validates Windows-level EXE navigation clicks and screenshots only.",
        "- Two-hour UI stability remains pending.",
        "- Real SolidWorks staged validation remains pending.",
        "- Historical visual audit 100 percent coverage remains pending.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_acceptance(exe_path: Path, out_dir: Path, wait_s: float = 1.0) -> dict[str, Any]:
    try:
        from pywinauto import Application, Desktop
    except Exception as exc:
        raise RuntimeError(f"pywinauto is required for EXE click acceptance: {exc}") from exc

    out_dir.mkdir(parents=True, exist_ok=True)
    screenshots_dir = out_dir / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    logger = EventLogger(out_dir)
    logger.log("suite_started", "Windows-level EXE click acceptance started", exe=str(exe_path))

    app = Application(backend="uia").start(str(exe_path), work_dir=str(REPO_ROOT), wait_for_idle=False)
    window = None
    pages: list[dict[str, Any]] = []
    try:
        window = Desktop(backend="uia").window(title="SW Drawing Studio")
        window.wait("visible", timeout=90)
        window.set_focus()
        time.sleep(max(1.0, wait_s))
        try:
            window.move_window(x=80, y=60, width=1600, height=1000, repaint=True)
        except Exception:
            pass

        for filename, page_name, min_bytes in PAGES:
            item = window.child_window(title=page_name, control_type="ListItem")
            item.wait("exists ready", timeout=20)
            item.click_input()
            time.sleep(wait_s)
            selected = _is_selected(item)
            shot = screenshots_dir / filename
            image = _save_window_image(window, shot)
            texts = _visible_texts(window)
            dashboard_error = page_name == "仪表盘" and any(("仪表盘" in t or "Dashboard" in t) and "异常" in t for t in texts)
            page_result = {
                "page": page_name,
                "screenshot": str(shot),
                "selected": selected,
                "min_bytes": min_bytes,
                "dashboard_error_visible": dashboard_error,
                **image,
            }
            page_result["pass"] = bool(
                selected
                and image.get("size_bytes", 0) >= min_bytes
                and image.get("sample_unique_colors", 0) >= 8
                and not dashboard_error
            )
            pages.append(page_result)
            logger.log("page_clicked", page_name, **page_result)

        report = {
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "mode": "windows_exe_click_acceptance",
            "exe": str(exe_path),
            "out_dir": str(out_dir),
            "pass": all(page.get("pass") for page in pages) and len(pages) == len(PAGES),
            "pages": pages,
            "artifacts": {
                "ui_events": str(logger.path),
                "screenshots_dir": str(screenshots_dir),
                "report_json": str(out_dir / "exe_click_acceptance_report.json"),
                "report_md": str(out_dir / "exe_click_acceptance_report.md"),
            },
            "remaining_gates": [
                "Two-hour UI stability remains pending.",
                "Real SolidWorks staged validation remains pending.",
                "Historical visual audit 100 percent coverage remains pending.",
            ],
        }
        report_path = out_dir / "exe_click_acceptance_report.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        _write_markdown(report, out_dir / "exe_click_acceptance_report.md")
        logger.log("suite_finished", "Windows-level EXE click acceptance finished", passed=report["pass"])
        return report
    finally:
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Windows-level v3.0 EXE click acceptance")
    parser.add_argument("--exe", default=str(DEFAULT_EXE))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT))
    parser.add_argument("--wait-s", type=float, default=1.0)
    args = parser.parse_args(argv)

    report = run_acceptance(Path(args.exe), Path(args.out_dir), wait_s=args.wait_s)
    print(json.dumps({"pass": report["pass"], "out_dir": report["out_dir"]}, ensure_ascii=False))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
