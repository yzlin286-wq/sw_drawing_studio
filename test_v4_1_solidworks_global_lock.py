from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path


def _old_iso(seconds_ago: int = 3600) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(time.time() - seconds_ago))


def main() -> None:
    from app.services import solidworks_global_lock as lock

    results: dict[str, object] = {"checks": []}
    out_path = Path("drw_output") / "solidworks_lock_test_result.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        lock_path = Path(tmp) / "solidworks_global_lock.json"
        conflict_log = Path(tmp) / "solidworks_lock_conflicts.jsonl"
        old_lock_path = os.environ.get(lock.LOCK_PATH_ENV)
        old_log_path = os.environ.get(lock.CONFLICT_LOG_ENV)
        os.environ[lock.LOCK_PATH_ENV] = str(lock_path)
        os.environ[lock.CONFLICT_LOG_ENV] = str(conflict_log)
        try:
            first = lock.acquire_lock(
                owner_project="unit",
                owner_workspace=str(Path.cwd()),
                job_id="job_a",
                operation="unit.acquire",
                part_path="fixture.SLDPRT",
                timeout_sec=0,
                run_id="run_a",
                ttl_sec=1,
            )
            assert first["acquired"] is True, first
            assert lock.read_lock()["owner_job_id"] == "job_a"  # type: ignore[index]
            results["checks"].append("same_process_acquire")

            second = lock.acquire_lock(
                owner_project="unit",
                owner_workspace=str(Path.cwd()),
                job_id="job_b",
                operation="unit.conflict",
                part_path="fixture_b.SLDPRT",
                timeout_sec=0,
                ttl_sec=1,
            )
            assert second["acquired"] is False, second
            assert second["status"] == "blocked_by_solidworks_lock", second
            results["checks"].append("second_job_blocked")

            hb = lock.heartbeat("job_a")
            assert hb["updated"] is True, hb
            released = lock.release_lock("job_a", "unit_release")
            assert released["released"] is True, released
            assert lock.read_lock() is None
            results["checks"].append("heartbeat_and_release")

            alive_owner = {
                "lock_version": 1,
                "owner_project": "unit",
                "owner_workspace": str(Path.cwd()),
                "owner_codex_session": "",
                "owner_pid": os.getpid(),
                "owner_worker_pid": os.getpid(),
                "owner_job_id": "alive_owner",
                "owner_run_id": "alive_run",
                "operation": "unit.old_heartbeat",
                "part_path": "fixture.SLDPRT",
                "sw_pid": None,
                "created_at": _old_iso(),
                "heartbeat_at": _old_iso(),
                "ttl_sec": 1,
                "allow_restart_sw": False,
                "status": "active",
            }
            lock_path.write_text(json.dumps(alive_owner, ensure_ascii=False), encoding="utf-8")
            assert lock.is_lock_stale() is False
            steal = lock.acquire_lock(
                owner_project="unit",
                owner_workspace=str(Path.cwd()),
                job_id="job_c",
                operation="unit.no_steal",
                part_path="fixture.SLDPRT",
                timeout_sec=0,
                ttl_sec=1,
            )
            assert steal["acquired"] is False, steal
            assert lock.read_lock()["owner_job_id"] == "alive_owner"  # type: ignore[index]
            results["checks"].append("alive_owner_not_stolen")

            dead_owner = dict(alive_owner)
            dead_owner["owner_pid"] = 99999999
            dead_owner["owner_worker_pid"] = 99999998
            dead_owner["owner_job_id"] = "dead_owner"
            lock_path.write_text(json.dumps(dead_owner, ensure_ascii=False), encoding="utf-8")
            assert lock.is_lock_stale() is True
            stale_release = lock.force_release_stale_lock("unit_stale")
            assert stale_release["released"] is True, stale_release
            assert lock.read_lock() is None
            results["checks"].append("stale_owner_released")

            results["status"] = "pass"
            results["conflict_log_exists"] = conflict_log.exists()
        finally:
            if old_lock_path is None:
                os.environ.pop(lock.LOCK_PATH_ENV, None)
            else:
                os.environ[lock.LOCK_PATH_ENV] = old_lock_path
            if old_log_path is None:
                os.environ.pop(lock.CONFLICT_LOG_ENV, None)
            else:
                os.environ[lock.CONFLICT_LOG_ENV] = old_log_path

    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print("PASS test_v4_1_solidworks_global_lock")


if __name__ == "__main__":
    main()
