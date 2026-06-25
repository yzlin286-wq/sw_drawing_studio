"""QProcess worker for diagnostics package actions.

Diagnostics ZIP generation can collect System Health rows and version details,
so the UI must submit it through JobRuntimeFacade instead of calling the
packager synchronously.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _emit(event_type: str, job_id: str, data: dict | None = None, message: str = "") -> None:
    event = {
        "event_type": event_type,
        "type": event_type,
        "job_id": job_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "data": data or {},
        "message": message,
    }
    print(json.dumps(event, ensure_ascii=False), flush=True)


def _describe_zip(path: Path) -> dict:
    with zipfile.ZipFile(path, "r") as zf:
        members = zf.namelist()
    return {
        "zip_path": str(path),
        "size_bytes": path.stat().st_size,
        "member_count": len(members),
        "members": members[:200],
        "members_truncated": len(members) > 200,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnostics action worker")
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--action", required=True, choices=["build_zip"])
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--screenshots-dir", default="")
    args = parser.parse_args()

    job_id = args.job_id
    _emit(
        "job_started",
        job_id,
        data={"job_type": "diagnostics_action", "action": args.action, "run_id": args.run_id},
        message="Diagnostics action started",
    )
    try:
        run_id = str(args.run_id or "").strip()
        if not run_id:
            raise ValueError("run_id is required")

        _emit("progress", job_id, data={"progress": 0.1, "stage": "validate_inputs"}, message="Validating inputs")
        _emit("heartbeat", job_id, data={"ts": time.time()}, message="diagnostics worker alive")

        from app.services.diagnostics import RUNS_DIR, build_diagnostics_zip

        run_dir = RUNS_DIR / run_id
        if not run_dir.exists():
            _emit(
                "warning",
                job_id,
                data={"run_id": run_id, "run_dir": str(run_dir), "reason": "run_dir_missing"},
                message=f"Run directory missing: {run_dir}",
            )

        screenshots_dir = Path(args.screenshots_dir) if args.screenshots_dir else None
        _emit("progress", job_id, data={"progress": 0.35, "stage": "building_zip"}, message="Building diagnostics ZIP")
        zip_path = build_diagnostics_zip(run_id, screenshots_dir=screenshots_dir)
        result = {
            "success": True,
            "action": args.action,
            "run_id": run_id,
            **_describe_zip(zip_path),
        }
        _emit("progress", job_id, data={"progress": 0.95, "stage": "complete"}, message="Diagnostics ZIP completed")
        _emit("job_finished", job_id, data={"result": result}, message=f"Diagnostics ZIP finished: {zip_path}")
        return 0
    except Exception as exc:
        _emit(
            "job_failed",
            job_id,
            data={
                "success": False,
                "action": args.action,
                "run_id": args.run_id,
                "error": str(exc),
                "reason": str(exc),
            },
            message=f"Diagnostics action failed: {exc}",
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
