"""v3.0 EXE smoke validation for the frozen desktop app.

This smoke avoids real SolidWorks, OCR, YOLO, and long CAD work. It verifies
that the current frozen executable can start, dispatch v3 workers, locate
bundled pipeline scripts, and render the internal nine-page walkthrough with
screenshots. The heavier Windows click robot, two-hour stability run, real CAD
validation, and historical visual audit coverage remain separate gates.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_EXE = REPO_ROOT / "dist_v3_smoke" / "sw_drawing_studio.exe"
DEFAULT_OUT = REPO_ROOT / "drw_output" / "ui_acceptance" / "exe_v3_smoke"


def _decode(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


def _run(
    cmd: list[str],
    *,
    timeout_s: int = 60,
    env_extra: dict[str, str] | None = None,
) -> tuple[subprocess.CompletedProcess[bytes], str, str]:
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout_s, env=env)
    return proc, _decode(proc.stdout), _decode(proc.stderr)


def _jsonl_events(stdout: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            events.append(value)
    return events


def _event_types(events: list[dict[str, Any]]) -> set[str]:
    return {str(event.get("event_type") or event.get("type") or "") for event in events if event}


def _check_worker(
    exe_path: Path,
    label: str,
    args: list[str],
    *,
    required: set[str],
    timeout_s: int = 90,
    env_extra: dict[str, str] | None = None,
) -> dict[str, Any]:
    cmd = [str(exe_path), "--worker", *args]
    proc, stdout, stderr = _run(cmd, timeout_s=timeout_s, env_extra=env_extra)
    events = _jsonl_events(stdout)
    types = _event_types(events)
    missing = sorted(required - types)
    ok = proc.returncode == 0 and not missing
    return {
        "label": label,
        "cmd": cmd,
        "returncode": proc.returncode,
        "event_count": len(events),
        "event_types": sorted(types),
        "missing_events": missing,
        "pass": ok,
        "stdout_tail": stdout[-1200:],
        "stderr_tail": stderr[-1200:],
    }


def _write_qc_fixture(root: Path) -> dict[str, Path]:
    fixture = root / "qc_action_fixture"
    run_dir = fixture / "run"
    qc_dir = run_dir / "qc"
    drawing_dir = run_dir / "drawing"
    qc_dir.mkdir(parents=True, exist_ok=True)
    drawing_dir.mkdir(parents=True, exist_ok=True)

    qc_json = qc_dir / "fixture_qc.json"
    qc_json.write_text(
        json.dumps(
            {
                "pass": True,
                "checks": {
                    "all_13_keys_present": {"pass": True, "present_count": 13},
                    "dim_count_sufficient": {"dim_total": 6},
                    "has_tech_note": {"pass": True},
                    "text_height_ge_3_5mm": {"pass": True},
                    "vision_score": {"score": 95},
                },
                "hard_fail": [],
                "warnings": [],
                "part_class": "feature_part",
                "has_valid_sidecar_annotation": False,
                "standard_annotation_present": True,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    png_path = drawing_dir / "fixture.png"
    try:
        from PIL import Image, ImageDraw

        image = Image.new("RGB", (640, 360), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle((30, 30, 610, 330), outline="black", width=3)
        draw.text((60, 70), "sw_drawing_studio v3 EXE smoke fixture", fill="black")
        draw.line((60, 180, 580, 180), fill="black", width=2)
        image.save(png_path)
    except Exception:
        # Minimal valid 1x1 PNG fallback.
        png_path.write_bytes(
            bytes.fromhex(
                "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753"
                "de0000000c49444154789c6360f8ffff3f0005fe02fea73581e80000000049"
                "454e44ae426082"
            )
        )

    return {"run_dir": run_dir, "qc_json": qc_json, "png": png_path}


def check_pipeline_info(exe_path: Path) -> dict[str, Any]:
    cmd = [str(exe_path), "--pipeline-script-info", "drw_quality_check"]
    proc, stdout, stderr = _run(cmd, timeout_s=60)
    info: dict[str, Any] = {}
    try:
        info = json.loads(stdout.strip().splitlines()[-1])
    except Exception as exc:
        info = {"parse_error": str(exc)}
    ok = (
        proc.returncode == 0
        and info.get("script_key") == "drw_quality_check"
        and info.get("exists") is True
        and str(info.get("script_path", "")).endswith("drw_quality_check.py")
    )
    return {
        "label": "pipeline_script_info",
        "cmd": cmd,
        "returncode": proc.returncode,
        "info": info,
        "pass": ok,
        "stdout_tail": stdout[-1200:],
        "stderr_tail": stderr[-1200:],
    }


def check_gui_alive(exe_path: Path) -> dict[str, Any]:
    started_at = time.monotonic()
    proc = subprocess.Popen([str(exe_path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(5)
    alive = proc.poll() is None
    elapsed = round(time.monotonic() - started_at, 2)
    stdout = ""
    stderr = ""
    if alive:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=10)
    else:
        raw_out, raw_err = proc.communicate(timeout=10)
        stdout = _decode(raw_out)
        stderr = _decode(raw_err)
    return {
        "label": "gui_alive",
        "pid": proc.pid,
        "alive_after_5s": alive,
        "elapsed_s": elapsed,
        "pass": alive,
        "stdout_tail": stdout[-1200:],
        "stderr_tail": stderr[-1200:],
    }


def check_ui_walkthrough(exe_path: Path, root: Path) -> dict[str, Any]:
    out_dir = root / "internal_walkthrough"
    cmd = [str(exe_path), "--ui-walkthrough", str(out_dir)]
    proc, stdout, stderr = _run(
        cmd,
        timeout_s=180,
        env_extra={"QT_QPA_PLATFORM": "offscreen"},
    )
    report_path = out_dir / "ui_walkthrough_report.json"
    report: dict[str, Any] = {}
    if report_path.exists():
        report = json.loads(report_path.read_text(encoding="utf-8"))
    else:
        try:
            report = json.loads(stdout.strip().splitlines()[-1])
        except Exception as exc:
            report = {"parse_error": str(exc)}
    results = report.get("results") if isinstance(report.get("results"), list) else []
    screenshot_sizes = [int(item.get("screenshot_size_bytes") or 0) for item in results if isinstance(item, dict)]
    ok = (
        proc.returncode == 0
        and report.get("all_pages_pass") is True
        and report.get("page_count") == 9
        and len(screenshot_sizes) == 9
        and min(screenshot_sizes or [0]) >= 50_000
    )
    return {
        "label": "internal_ui_walkthrough",
        "cmd": cmd,
        "returncode": proc.returncode,
        "report": str(report_path),
        "page_count": report.get("page_count"),
        "all_pages_pass": report.get("all_pages_pass"),
        "screenshot_count": len(screenshot_sizes),
        "min_screenshot_size": min(screenshot_sizes or [0]),
        "pass": ok,
        "stdout_tail": stdout[-1200:],
        "stderr_tail": stderr[-1200:],
    }


def write_markdown(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# v3.0 EXE Smoke Report",
        "",
        f"Generated: {report.get('generated_at', '')}",
        f"EXE: `{report.get('exe', '')}`",
        f"Overall: {'PASS' if report.get('pass') else 'FAIL'}",
        "",
        "## Checks",
        "",
        "| Check | Result | Detail |",
        "| --- | --- | --- |",
    ]
    for check in report.get("checks", []):
        detail = ""
        if check.get("label", "").endswith("worker"):
            detail = "events=" + ",".join(check.get("event_types", []))
        elif check.get("label") == "internal_ui_walkthrough":
            detail = f"pages={check.get('page_count')} min_png={check.get('min_screenshot_size')}"
        elif check.get("label") == "gui_alive":
            detail = f"alive_after_5s={check.get('alive_after_5s')}"
        elif check.get("label") == "pipeline_script_info":
            detail = str(check.get("info", {}).get("script_path", ""))
        else:
            detail = f"returncode={check.get('returncode')}"
        lines.append(f"| {check.get('label')} | {'PASS' if check.get('pass') else 'FAIL'} | {detail} |")

    lines += [
        "",
        "## Remaining Gates",
        "",
        "- Windows-level EXE click automation remains pending.",
        "- Two-hour UI stability remains pending.",
        "- Real SolidWorks staged validation remains pending.",
        "- Historical visual audit 100 percent coverage remains pending.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_smoke(exe_path: Path, out_dir: Path) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    fixture_part = out_dir / "fixture_part.SLDPRT"
    fixture_part.write_bytes(b"v3 exe smoke fixture")
    qc = _write_qc_fixture(out_dir)

    checks: list[dict[str, Any]] = []
    checks.append(
        {
            "label": "exe_exists",
            "path": str(exe_path),
            "size_bytes": exe_path.stat().st_size if exe_path.exists() else 0,
            "pass": exe_path.exists() and exe_path.stat().st_size > 100_000_000,
        }
    )
    checks.append(
        _check_worker(
            exe_path,
            "mock_worker",
            ["mock", "--job-id", "smoke_mock", "--scenario", "normal_pass", "--duration-s", "0.2"],
            required={"job_started", "progress", "heartbeat", "job_finished"},
        )
    )
    checks.append(
        _check_worker(
            exe_path,
            "llm_pre_analyze_worker",
            [
                "llm_action",
                "--job-id",
                "smoke_llm_pre",
                "--action",
                "pre_analyze",
                "--part-path",
                str(fixture_part),
            ],
            required={"job_started", "progress", "heartbeat", "warning", "job_finished"},
            env_extra={"SW_DRAWING_STUDIO_LLM_MOCK_RESPONSE": '{"category":"feature_part","front_view":"front","scale":"1:1"}'},
        )
    )
    checks.append(
        _check_worker(
            exe_path,
            "llm_tech_text_worker",
            ["llm_action", "--job-id", "smoke_llm_text", "--action", "tech_text"],
            required={"job_started", "progress", "heartbeat", "warning", "job_finished"},
            env_extra={
                "SW_DRAWING_STUDIO_LLM_MOCK_RESPONSE": json.dumps(
                    ["Use GB/T 1804-m.", "Remove burrs.", "Mark surface roughness."]
                )
            },
        )
    )
    checks.append(
        _check_worker(
            exe_path,
            "qc_action_worker",
            [
                "qc_action",
                "--job-id",
                "smoke_qc",
                "--action",
                "vision_qc_v2",
                "--qc-json-path",
                str(qc["qc_json"]),
                "--png-path",
                str(qc["png"]),
                "--run-dir",
                str(qc["run_dir"]),
            ],
            required={"job_started", "progress", "heartbeat", "job_finished"},
        )
    )
    checks.append(
        _check_worker(
            exe_path,
            "system_health_worker",
            ["system_health", "--job-id", "smoke_health"],
            required={"job_started", "progress", "heartbeat", "job_finished"},
            timeout_s=180,
        )
    )
    checks.append(check_pipeline_info(exe_path))
    checks.append(check_gui_alive(exe_path))
    checks.append(check_ui_walkthrough(exe_path, out_dir))

    report = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "v3_exe_smoke",
        "exe": str(exe_path),
        "out_dir": str(out_dir),
        "pass": all(bool(check.get("pass")) for check in checks),
        "checks": checks,
        "artifacts": {
            "report_json": str(out_dir / "exe_smoke_report.json"),
            "report_md": str(out_dir / "exe_smoke_report.md"),
            "internal_walkthrough": str(out_dir / "internal_walkthrough"),
            "qc_fixture_run": str(qc["run_dir"]),
        },
        "remaining_gates": [
            "Windows-level EXE click automation remains pending.",
            "Two-hour UI stability remains pending.",
            "Real SolidWorks staged validation remains pending.",
            "Historical visual audit 100 percent coverage remains pending.",
        ],
    }
    report_path = out_dir / "exe_smoke_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(report, out_dir / "exe_smoke_report.md")
    return report


def main() -> int:
    exe_path = Path(sys.argv[1]) if len(sys.argv) >= 2 else DEFAULT_EXE
    out_dir = Path(sys.argv[2]) if len(sys.argv) >= 3 else DEFAULT_OUT
    report = run_smoke(exe_path, out_dir)
    print(json.dumps({"pass": report["pass"], "out_dir": str(out_dir)}, ensure_ascii=False))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
