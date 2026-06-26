from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.solidworks_conflict_monitor import write_conflict_report  # noqa: E402
from app.services.solidworks_entrypoint_scanner import write_entrypoint_report  # noqa: E402


DIAGNOSTICS_DIR = ROOT / "drw_output" / "diagnostics"
ENTRYPOINT_REPORT = DIAGNOSTICS_DIR / "unguarded_solidworks_entrypoints.json"
LOCK_TEST_REPORT = DIAGNOSTICS_DIR / "solidworks_lock_test_result.json"
CONFLICT_REPORT = DIAGNOSTICS_DIR / "conflict_report.json"
SUMMARY_REPORT = DIAGNOSTICS_DIR / "solidworks_stability_gate_v4_4.json"


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())


def _old_iso(seconds_ago: int = 3600) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(time.time() - seconds_ago))


def _record_check(checks: list[dict[str, Any]], key: str, status: str, details: dict[str, Any] | None = None) -> None:
    checks.append({"key": key, "status": status, "details": details or {}})


def run_lock_test(out_path: Path = LOCK_TEST_REPORT) -> dict[str, Any]:
    from app.services import solidworks_global_lock as lock

    checks: list[dict[str, Any]] = []
    status = "pass"
    failure: str | None = None

    with tempfile.TemporaryDirectory() as tmp:
        lock_path = Path(tmp) / "solidworks_global_lock.json"
        conflict_log = Path(tmp) / "solidworks_lock_conflicts.jsonl"
        old_lock_path = os.environ.get(lock.LOCK_PATH_ENV)
        old_log_path = os.environ.get(lock.CONFLICT_LOG_ENV)
        os.environ[lock.LOCK_PATH_ENV] = str(lock_path)
        os.environ[lock.CONFLICT_LOG_ENV] = str(conflict_log)
        try:
            first = lock.acquire_lock(
                owner_project="v4_4_lock_test",
                owner_workspace=str(ROOT),
                job_id="job_a",
                operation="unit.acquire",
                part_path="fixture.SLDPRT",
                timeout_sec=0,
                run_id="run_a",
                ttl_sec=1,
            )
            if first.get("acquired") is True and (lock.read_lock() or {}).get("owner_job_id") == "job_a":
                _record_check(checks, "first_job_acquires_lock", "pass", first)
            else:
                raise AssertionError(f"first lock acquire failed: {first}")

            second = lock.acquire_lock(
                owner_project="v4_4_lock_test",
                owner_workspace=str(ROOT),
                job_id="job_b",
                operation="unit.conflict",
                part_path="fixture_b.SLDPRT",
                timeout_sec=0,
                ttl_sec=1,
            )
            if second.get("acquired") is False and second.get("status") == "blocked_by_solidworks_lock":
                _record_check(checks, "second_job_blocked_by_owner", "pass", second)
            else:
                raise AssertionError(f"second lock should be blocked: {second}")

            hb = lock.heartbeat("job_a")
            released = lock.release_lock("job_a", "unit_release")
            if hb.get("updated") is True and released.get("released") is True and lock.read_lock() is None:
                _record_check(checks, "heartbeat_and_release", "pass", {"heartbeat": hb, "release": released})
            else:
                raise AssertionError(f"heartbeat/release failed: hb={hb} release={released}")

            alive_owner = {
                "lock_version": 1,
                "owner_project": "v4_4_lock_test",
                "owner_workspace": str(ROOT),
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
            steal = lock.acquire_lock(
                owner_project="v4_4_lock_test",
                owner_workspace=str(ROOT),
                job_id="job_c",
                operation="unit.no_steal",
                part_path="fixture.SLDPRT",
                timeout_sec=0,
                ttl_sec=1,
            )
            if steal.get("acquired") is False and (lock.read_lock() or {}).get("owner_job_id") == "alive_owner":
                _record_check(checks, "alive_owner_not_stolen", "pass", steal)
            else:
                raise AssertionError(f"alive owner was stolen: {steal}")

            dead_owner = dict(alive_owner)
            dead_owner["owner_pid"] = 99999999
            dead_owner["owner_worker_pid"] = 99999998
            dead_owner["owner_job_id"] = "dead_owner"
            lock_path.write_text(json.dumps(dead_owner, ensure_ascii=False), encoding="utf-8")
            stale_release = lock.force_release_stale_lock("unit_stale")
            if stale_release.get("released") is True and lock.read_lock() is None:
                _record_check(checks, "stale_owner_released", "pass", stale_release)
            else:
                raise AssertionError(f"stale owner was not released: {stale_release}")

            if conflict_log.exists():
                _record_check(checks, "conflict_log_written", "pass", {"path": str(conflict_log)})
            else:
                raise AssertionError("conflict log was not written")
        except Exception as exc:
            status = "fail"
            failure = str(exc)
            _record_check(checks, "lock_test_exception", "fail", {"error": str(exc), "type": type(exc).__name__})
        finally:
            if old_lock_path is None:
                os.environ.pop(lock.LOCK_PATH_ENV, None)
            else:
                os.environ[lock.LOCK_PATH_ENV] = old_lock_path
            if old_log_path is None:
                os.environ.pop(lock.CONFLICT_LOG_ENV, None)
            else:
                os.environ[lock.CONFLICT_LOG_ENV] = old_log_path

    report = {
        "schema": "sw_drawing_studio.solidworks_lock_test_result.v4_4",
        "generated_at": _now(),
        "status": status,
        "pass": status == "pass",
        "failure": failure or "",
        "checks": checks,
        "policy": {
            "second_owner_must_be_blocked": True,
            "alive_owner_lock_must_not_be_stolen": True,
            "stale_owner_lock_can_be_released_after_pid_and_ttl_checks": True,
        },
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report["report_path"] = str(out_path)
    return report


def run_gate() -> dict[str, Any]:
    DIAGNOSTICS_DIR.mkdir(parents=True, exist_ok=True)
    entrypoint = write_entrypoint_report(root=ROOT, out_path=ENTRYPOINT_REPORT)
    lock_test = run_lock_test(LOCK_TEST_REPORT)
    conflict = write_conflict_report(out_path=CONFLICT_REPORT)
    warning_reasons: list[str] = []
    if entrypoint.get("status") != "pass":
        warning_reasons.append("unguarded_or_review_required_solidworks_entrypoints")
    if lock_test.get("status") != "pass":
        warning_reasons.append("solidworks_global_lock_test_failed")
    if str(conflict.get("level") or "").upper() != "OK":
        warning_reasons.append("solidworks_conflict_monitor_warning_or_fail")
    status = "warning" if warning_reasons else "pass"
    summary = {
        "schema": "sw_drawing_studio.solidworks_stability_gate.v4_4",
        "generated_at": _now(),
        "status": status,
        "pass": status == "pass",
        "release_ready": False,
        "warning_reasons": warning_reasons,
        "reports": {
            "unguarded_solidworks_entrypoints": str(ENTRYPOINT_REPORT),
            "solidworks_lock_test_result": str(LOCK_TEST_REPORT),
            "conflict_report": str(CONFLICT_REPORT),
        },
        "entrypoint_summary": {
            "status": entrypoint.get("status"),
            "entrypoint_count": entrypoint.get("entrypoint_count"),
            "unguarded_or_unknown_count": entrypoint.get("unguarded_or_unknown_count"),
            "ui_thread_direct_risk_count": entrypoint.get("ui_thread_direct_risk_count"),
            "ui_thread_subprocess_call_count": entrypoint.get("ui_thread_subprocess_call_count"),
            "ui_threadpool_worker_count": entrypoint.get("ui_threadpool_worker_count"),
            "service_direct_risk_count": entrypoint.get("service_direct_risk_count"),
            "system_health_ui_thread_direct_probe_count": entrypoint.get("system_health_ui_thread_direct_probe_count"),
            "worker_backed_model_client_count": entrypoint.get("worker_backed_model_client_count"),
            "legacy_service_adapter_count": entrypoint.get("legacy_service_adapter_count"),
            "background_watchdog_probe_count": entrypoint.get("background_watchdog_probe_count"),
            "validation_tool_requires_manual_lock_count": entrypoint.get("validation_tool_requires_manual_lock_count"),
            "external_addin_needs_host_lock_count": entrypoint.get("external_addin_needs_host_lock_count"),
            "external_addin_host_lock_contract_status": entrypoint.get("external_addin_host_lock_contract_status"),
        },
        "lock_test_summary": {
            "status": lock_test.get("status"),
            "check_count": len(lock_test.get("checks") or []),
            "failure": lock_test.get("failure", ""),
        },
        "conflict_summary": {
            "level": conflict.get("level"),
            "counts": conflict.get("counts", {}),
            "fix_suggestion": conflict.get("fix_suggestion", ""),
        },
    }
    SUMMARY_REPORT.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main() -> int:
    summary = run_gate()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary.get("status") in {"pass", "warning"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
