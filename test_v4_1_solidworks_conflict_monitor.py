from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from app.services.solidworks_conflict_monitor import (
    ProcessInfo,
    _apply_solidworks_window_state,
    build_conflict_report,
    write_conflict_report,
)


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
            assert report["status"] == "fail"
            assert report["pass"] is False
            assert report["fail_count"] >= 1
            keys = {item["key"] for item in report["findings"]}
            assert "solidworks_not_responding" in keys
            assert "multiple_active_cad_workers" in keys

            ok_report = build_conflict_report(
                processes=[ProcessInfo(pid=101, name="SLDWORKS.exe", responding=True, main_window_title="SOLIDWORKS")],
                lock=lock_payload,
            )
            assert ok_report["level"] == "OK", ok_report
            assert ok_report["status"] == "pass", ok_report
            assert ok_report["pass"] is True, ok_report
            assert ok_report["fail_count"] == 0, ok_report
            assert ok_report["warning_count"] == 0, ok_report

            unsaved_report = build_conflict_report(
                processes=[
                    ProcessInfo(
                        pid=101,
                        name="SLDWORKS.exe",
                        responding=True,
                        main_window_title="SOLIDWORKS Premium 2025 SP5.0 - [fixture.SLDASM *]",
                    )
                ],
                lock=lock_payload,
            )
            assert unsaved_report["level"] == "FAIL", unsaved_report
            assert unsaved_report["status"] == "fail", unsaved_report
            assert unsaved_report["pass"] is False, unsaved_report
            assert unsaved_report["fail_count"] >= 1, unsaved_report
            unsaved_keys = {item["key"] for item in unsaved_report["findings"]}
            assert "solidworks_unsaved_document_visible" in unsaved_keys
            assert "solidworks_running_without_lock" not in unsaved_keys
            assert "保存或关闭未保存文档" in unsaved_report["fix_suggestion"]

            merged = _apply_solidworks_window_state(
                [ProcessInfo(pid=101, name="SLDWORKS.exe", responding=None, main_window_title="")],
                {
                    101: {
                        "responding": True,
                        "main_window_title": "SOLIDWORKS Premium 2025 SP5.0 - [fixture.SLDASM *]",
                    }
                },
            )
            assert merged[0].responding is True
            assert merged[0].main_window_title.endswith("*]")

            out = Path(tmp) / "conflict_report.json"
            written = write_conflict_report(out_path=out, processes=processes, lock=lock_payload)
            assert out.exists()
            assert written["level"] == "FAIL"
            assert written["pass"] is False
        finally:
            if old_lock is None:
                os.environ.pop(lock_service.LOCK_PATH_ENV, None)
            else:
                os.environ[lock_service.LOCK_PATH_ENV] = old_lock

    print("PASS test_v4_1_solidworks_conflict_monitor")


if __name__ == "__main__":
    main()
