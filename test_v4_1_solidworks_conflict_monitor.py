from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from app.services.solidworks_conflict_monitor import ProcessInfo, build_conflict_report, write_conflict_report


def main() -> None:
    from app.services import solidworks_global_lock as lock_service

    with tempfile.TemporaryDirectory() as tmp:
        lock_path = Path(tmp) / "solidworks_global_lock.json"
        old_lock = os.environ.get(lock_service.LOCK_PATH_ENV)
        os.environ[lock_service.LOCK_PATH_ENV] = str(lock_path)
        try:
            lock_payload = {
                "lock_version": 1,
                "owner_project": "other_project",
                "owner_workspace": r"C:\other",
                "owner_codex_session": "",
                "owner_pid": os.getpid(),
                "owner_worker_pid": os.getpid(),
                "owner_job_id": "other_job",
                "owner_run_id": "run_x",
                "operation": "generate_drawing",
                "part_path": "part.SLDPRT",
                "sw_pid": 101,
                "created_at": "2026-06-23T00:00:00",
                "heartbeat_at": "2026-06-23T00:00:00",
                "ttl_sec": 180,
                "allow_restart_sw": False,
                "status": "active",
            }
            processes = [
                ProcessInfo(pid=101, name="SLDWORKS.exe", responding=False, main_window_title="SOLIDWORKS"),
                ProcessInfo(pid=201, name="python.exe", command_line="python app/workers/cad_job_worker.py --job-id a"),
                ProcessInfo(pid=202, name="python.exe", command_line="python app/workers/cad_job_worker.py --job-id b"),
                ProcessInfo(pid=203, name="python.exe", command_line="python app/services/sw_dialog_guard.py DialogGuard"),
            ]
            report = build_conflict_report(processes=processes, lock=lock_payload)
            assert report["level"] == "FAIL", report
            keys = {item["key"] for item in report["findings"]}
            assert "solidworks_not_responding" in keys
            assert "multiple_active_cad_workers" in keys

            ok_report = build_conflict_report(
                processes=[ProcessInfo(pid=101, name="SLDWORKS.exe", responding=True, main_window_title="SOLIDWORKS")],
                lock=lock_payload,
            )
            assert ok_report["level"] == "OK", ok_report

            out = Path("drw_output") / "diagnostics" / "conflict_report.json"
            written = write_conflict_report(out_path=out, processes=processes, lock=lock_payload)
            assert out.exists()
            assert written["level"] == "FAIL"
        finally:
            if old_lock is None:
                os.environ.pop(lock_service.LOCK_PATH_ENV, None)
            else:
                os.environ[lock_service.LOCK_PATH_ENV] = old_lock

    print("PASS test_v4_1_solidworks_conflict_monitor")


if __name__ == "__main__":
    main()
