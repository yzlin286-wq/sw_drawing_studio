from __future__ import annotations

import os
import tempfile
from pathlib import Path


def main() -> None:
    from app.services import solidworks_global_lock as lock
    from app.services.solidworks_safe_restart import build_restart_preflight

    with tempfile.TemporaryDirectory() as tmp:
        old_lock = os.environ.get(lock.LOCK_PATH_ENV)
        old_log = os.environ.get(lock.CONFLICT_LOG_ENV)
        os.environ[lock.LOCK_PATH_ENV] = str(Path(tmp) / "solidworks_global_lock.json")
        os.environ[lock.CONFLICT_LOG_ENV] = str(Path(tmp) / "solidworks_lock_conflicts.jsonl")
        os.environ.pop(lock.LOCK_JOB_ID_ENV, None)
        try:
            no_lock = build_restart_preflight(job_id="restart_a", run_dir=Path(tmp))
            assert no_lock["status"] == "blocked_by_solidworks_lock", no_lock

            acquired = lock.acquire_lock(
                owner_project="unit",
                owner_workspace=str(Path.cwd()),
                job_id="restart_a",
                operation="unit_restart",
                part_path="",
                timeout_sec=0,
                run_id="restart_run",
                allow_restart_sw=False,
            )
            assert acquired["acquired"] is True, acquired
            blocked = build_restart_preflight(job_id="restart_a", run_dir=Path(tmp), user_confirmed=True)
            assert blocked["status"] == "blocked_restart_not_allowed_by_lock", blocked
            lock.release_lock("restart_a", "test")

            acquired = lock.acquire_lock(
                owner_project="unit",
                owner_workspace=str(Path.cwd()),
                job_id="restart_b",
                operation="unit_restart",
                part_path="",
                timeout_sec=0,
                run_id="restart_run",
                allow_restart_sw=True,
            )
            assert acquired["acquired"] is True, acquired
            waiting = build_restart_preflight(job_id="restart_b", run_dir=Path(tmp), user_confirmed=False)
            assert waiting["status"] == "waiting_for_user_confirmation", waiting
            report = Path(tmp) / "diagnostics" / "restart_report.json"
            assert report.exists()
            lock.release_lock("restart_b", "test")
        finally:
            os.environ.pop(lock.LOCK_JOB_ID_ENV, None)
            if old_lock is None:
                os.environ.pop(lock.LOCK_PATH_ENV, None)
            else:
                os.environ[lock.LOCK_PATH_ENV] = old_lock
            if old_log is None:
                os.environ.pop(lock.CONFLICT_LOG_ENV, None)
            else:
                os.environ[lock.CONFLICT_LOG_ENV] = old_log

    print("PASS test_v4_1_solidworks_safe_restart")


if __name__ == "__main__":
    main()
