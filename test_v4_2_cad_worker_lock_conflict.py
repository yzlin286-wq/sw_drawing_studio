from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory


REPO_ROOT = Path(__file__).resolve().parent


def _jsonl_events(text: str) -> list[dict]:
    events: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if isinstance(payload, dict):
            events.append(payload)
    return events


def test_cad_worker_lock_conflict_reports_owner_bucket_and_fix() -> None:
    from app.services import solidworks_global_lock as lock

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        lock_path = root / "solidworks_global_lock.json"
        conflict_log = root / "solidworks_lock_conflicts.jsonl"
        part = root / "LB26001-A-04-006.SLDPRT"
        part.write_text("dummy part fixture", encoding="utf-8")
        out_dir = root / "cad_worker_lock_conflict_run"

        old_lock_path = os.environ.get(lock.LOCK_PATH_ENV)
        old_conflict_log = os.environ.get(lock.CONFLICT_LOG_ENV)
        os.environ[lock.LOCK_PATH_ENV] = str(lock_path)
        os.environ[lock.CONFLICT_LOG_ENV] = str(conflict_log)
        try:
            owner = lock.acquire_lock(
                owner_project="unit_owner",
                owner_workspace=str(REPO_ROOT),
                job_id="owner-job",
                operation="unit.holds_solidworks",
                part_path=str(part),
                timeout_sec=0,
                run_id="owner-run",
                ttl_sec=180,
            )
            assert owner["acquired"] is True, owner

            env = os.environ.copy()
            env.update(
                {
                    lock.LOCK_PATH_ENV: str(lock_path),
                    lock.CONFLICT_LOG_ENV: str(conflict_log),
                    "SW_GLOBAL_LOCK_TIMEOUT_S": "0",
                    "PYTHONIOENCODING": "utf-8",
                    "PYTHONPATH": str(REPO_ROOT)
                    + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""),
                    "RUN_ID": "worker-lock-conflict",
                }
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    "app/workers/cad_job_worker.py",
                    "--job-id",
                    "blocked-worker",
                    "--part-path",
                    str(part),
                    "--output-dir",
                    str(out_dir),
                    "--max-rounds",
                    "1",
                    "--timeout-s",
                    "5",
                ],
                cwd=str(REPO_ROOT),
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
                check=False,
            )
        finally:
            try:
                lock.release_lock("owner-job", "unit_cleanup")
            finally:
                if old_lock_path is None:
                    os.environ.pop(lock.LOCK_PATH_ENV, None)
                else:
                    os.environ[lock.LOCK_PATH_ENV] = old_lock_path
                if old_conflict_log is None:
                    os.environ.pop(lock.CONFLICT_LOG_ENV, None)
                else:
                    os.environ[lock.CONFLICT_LOG_ENV] = old_conflict_log

        events = _jsonl_events(completed.stdout)
        failed = [event for event in events if event.get("event_type") == "job_failed"]
        assert completed.returncode == 4, completed.stdout + completed.stderr
        assert failed, completed.stdout
        data = failed[-1].get("data") or {}
        assert data["status"] == "blocked_by_solidworks_lock"
        assert data["error"] == "blocked_by_solidworks_lock"
        assert data["failure_bucket"] == "solidworks_lock_conflict"
        assert data["owner"]["owner_job_id"] == "owner-job"
        assert data["owner"]["owner_project"] == "unit_owner"
        assert data["fix_suggestion"]
        assert data["recoverable"] is True

        manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["failure_bucket"] == "solidworks_lock_conflict"
        assert manifest["drawing_usable"]["pass"] is False
        assert "solidworks_lock_conflict" in manifest["hard_fail"]
        assert manifest["fix_suggestion"]


if __name__ == "__main__":
    test_cad_worker_lock_conflict_reports_owner_bucket_and_fix()
    print("PASS test_v4_2_cad_worker_lock_conflict")
