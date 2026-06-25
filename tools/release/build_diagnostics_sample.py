from __future__ import annotations

import argparse
import json
import sys
import time
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.diagnostics import build_diagnostics_zip


RUN_ID = "diagnostics_sample_v3_0"


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_sample_run(run_dir: Path) -> None:
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    manifest = {
        "run_id": RUN_ID,
        "started_at": now,
        "finished_at": now,
        "input_part_path_abs": r"C:\diagnostics_sample\sample.SLDPRT",
        "drawing_usable": {"pass": False, "reason": "diagnostics sample run"},
        "qc_pass_count": 0,
        "vision_score": 0,
        "hard_fail": ["diagnostics_sample"],
        "warnings": [{"code": "sample_only", "message": "Release diagnostics sample fixture"}],
        "exception_summary": [],
        "artifacts": {
            "manifest": "manifest.json",
            "vision_qc": "qc/vision_qc_v5.json",
            "final_quality": "qc/final_quality.json",
            "sw_session": "sw_session.json",
            "job_events": "job_event_log.jsonl",
        },
        "diagnostics_sample": True,
    }
    _write_json(run_dir / "manifest.json", manifest)

    issue = {
        "key": "diagnostics_sample_issue",
        "severity": "info",
        "bbox": [0.1, 0.1, 0.4, 0.3],
        "source": "sample_fixture",
        "confidence": 0.99,
        "evidence": "Synthetic issue used only to prove diagnostics packaging.",
        "fix_suggestion": "Replace the sample run with a real failed run when debugging a user case.",
        "auto_fix_available": False,
        "human_review_status": "unreviewed",
    }
    _write_json(
        run_dir / "qc" / "vision_qc_v5.json",
        {
            "version": "v5",
            "status": "need_review",
            "issues": [issue],
            "summary": {"total": 1, "info": 1},
        },
    )
    _write_json(run_dir / "qc" / "qc.json", {"pass": False, "checks": ["diagnostics_sample"]})
    _write_json(run_dir / "qc" / "vision.json", {"score": 0, "source": "diagnostics_sample"})
    _write_json(
        run_dir / "qc" / "final_quality.json",
        {
            "overall_status": "need_review",
            "issues": [issue],
            "diagnostics_sample": True,
        },
    )
    _write_json(
        run_dir / "sw_session.json",
        {
            "connected": False,
            "sw_pid": None,
            "revision": None,
            "active_doc": None,
            "transaction_status": "not_started",
            "diagnostics_sample": True,
        },
    )

    _write_text(run_dir / "logs" / "run.log", "diagnostics sample run log\n")
    _write_text(run_dir / "logs" / "sw.log", "SolidWorks not connected for diagnostics sample\n")
    _write_text(run_dir / "logs" / "worker_stdout.log", '{"type":"job_started","job_id":"diagnostics_sample_v3_0"}\n')
    _write_text(run_dir / "logs" / "worker_stderr.log", "")
    _write_text(
        run_dir / "job_event_log.jsonl",
        "\n".join(
            [
                json.dumps({"type": "job_started", "job_id": RUN_ID, "stage": "diagnostics_sample"}),
                json.dumps({"type": "progress", "job_id": RUN_ID, "percent": 100}),
                json.dumps({"type": "job_finished", "job_id": RUN_ID, "status": "sample"}),
            ]
        )
        + "\n",
    )


def _validate_zip(zip_path: Path) -> dict:
    required = {
        "manifest.json",
        "qc.json",
        "vision.json",
        "qc/vision_qc_v5.json",
        "qc/final_quality.json",
        "sw_session.json",
        "logs/run.log",
        "logs/sw.log",
        "logs/worker_stdout.log",
        "job_event_log.jsonl",
        "health_check.json",
        "version.txt",
        "screenshots/01_dashboard.png",
        "screenshots/08_logs_diagnostics.png",
    }
    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())
        sizes = {name: zf.getinfo(name).file_size for name in zf.namelist()}
    missing = sorted(required - names)
    return {
        "pass": not missing,
        "zip_path": str(zip_path),
        "size_bytes": zip_path.stat().st_size,
        "entry_count": len(names),
        "missing_required": missing,
        "entries": sorted(names),
        "sizes": sizes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v3.0 diagnostics sample zip.")
    parser.add_argument(
        "--screenshots-dir",
        default=str(REPO_ROOT / "drw_output" / "ui_acceptance" / "exe_click_v3" / "screenshots"),
        help="Directory containing v3 UI acceptance screenshots.",
    )
    parser.add_argument(
        "--report",
        default=str(REPO_ROOT / "drw_output" / "diagnostics" / "diagnostics_sample_v3_0_report.json"),
    )
    args = parser.parse_args()

    run_dir = REPO_ROOT / "drw_output" / "runs" / RUN_ID
    screenshots_dir = Path(args.screenshots_dir)
    _build_sample_run(run_dir)
    zip_path = build_diagnostics_zip(RUN_ID, screenshots_dir=screenshots_dir)
    report = _validate_zip(zip_path)
    report["run_dir"] = str(run_dir)
    report["screenshots_dir"] = str(screenshots_dir)
    report_path = Path(args.report)
    _write_json(report_path, report)
    print(json.dumps({"pass": report["pass"], "zip_path": str(zip_path), "report": str(report_path)}, ensure_ascii=False))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
