"""QProcess worker for System Health checks.

The UI must not probe SolidWorks COM, Document Manager, imports, or subprocesses
directly. This worker performs those checks in a child process and emits the same
JSONL event contract consumed by JobRunner.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
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


def main() -> int:
    parser = argparse.ArgumentParser(description="System Health worker")
    parser.add_argument("--job-id", required=True)
    parser.add_argument(
        "--real-opendoc6-probe",
        action="store_true",
        help="Run a real OpenDoc6 probe against --probe-doc-path. Intended for release validation, not routine UI refresh.",
    )
    parser.add_argument(
        "--ensure-solidworks",
        action="store_true",
        help="Allow Dispatch('SldWorks.Application') before collecting release-gate rows.",
    )
    parser.add_argument("--probe-doc-path", default="")
    args = parser.parse_args()

    job_id = args.job_id
    _emit(
        "job_started",
        job_id,
        data={"job_type": "system_health"},
        message="System Health check started",
    )
    try:
        _emit("progress", job_id, data={"progress": 0.1, "stage": "collecting"}, message="Collecting health rows")
        _emit("heartbeat", job_id, data={"ts": time.time()}, message="health worker alive")
        from app.services.system_health_service import collect_system_health, system_health_payload

        rows, summary = collect_system_health(
            ensure_solidworks=args.ensure_solidworks,
            real_opendoc6_probe=args.real_opendoc6_probe,
            probe_doc_path=args.probe_doc_path or None,
        )
        payload = system_health_payload(rows, summary)
        _emit("progress", job_id, data={"progress": 0.9, "stage": "render_ready"}, message="Health rows collected")
        _emit(
            "job_finished",
            job_id,
            data={"result": payload},
            message=f"System Health check finished ({summary.get('total', len(rows))} checks)",
        )
        return 0
    except Exception as exc:
        _emit(
            "job_failed",
            job_id,
            data={"error": str(exc), "reason": type(exc).__name__},
            message=f"System Health check failed: {exc}",
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
