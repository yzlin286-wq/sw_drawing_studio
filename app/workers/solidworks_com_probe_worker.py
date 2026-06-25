"""Bounded SolidWorks COM probe worker.

This worker is intentionally tiny: it performs one COM connection attempt and
prints a single JSON object. Callers own the timeout and may kill this process
without affecting the UI thread.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _read_com_value(obj, name: str):
    try:
        value = getattr(obj, name)
        return value() if callable(value) else value
    except Exception:
        return None


def _probe(method: str) -> dict:
    started = time.monotonic()
    result = {
        "schema": "sw_drawing_studio.solidworks_com_probe.v1",
        "method": method,
        "status": "unknown",
        "reason": "",
        "sw_revision": "",
        "sw_pid": None,
        "visible": None,
        "elapsed_ms": 0,
    }
    try:
        import pythoncom
        import win32com.client as wc
    except Exception as exc:
        result.update({"status": "failed", "reason": f"pywin32_unavailable: {exc}"})
        return result

    pythoncom.CoInitialize()
    try:
        if method == "get_active_object":
            sw = wc.GetActiveObject("SldWorks.Application")
        elif method == "dispatch":
            sw = wc.Dispatch("SldWorks.Application")
        elif method == "dispatch_ex":
            sw = wc.DispatchEx("SldWorks.Application")
        else:
            result.update({"status": "failed", "reason": f"unknown_method: {method}"})
            return result

        result["status"] = "connected"
        revision = _read_com_value(sw, "RevisionNumber")
        if revision is not None:
            result["sw_revision"] = str(revision or "")
        pid = _read_com_value(sw, "GetProcessID")
        if pid is None:
            pid = _read_com_value(sw, "GetProcessId")
        try:
            result["sw_pid"] = int(pid) if pid else None
        except Exception:
            result["sw_pid"] = None
        visible = _read_com_value(sw, "Visible")
        if visible is not None:
            result["visible"] = bool(visible)
    except Exception as exc:
        result.update({"status": "failed", "reason": str(exc)})
    finally:
        result["elapsed_ms"] = int((time.monotonic() - started) * 1000)
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe SolidWorks COM connection once")
    parser.add_argument(
        "--method",
        choices=["get_active_object", "dispatch", "dispatch_ex"],
        default="get_active_object",
    )
    parser.add_argument("--lock-timeout-s", type=float, default=0.5)
    args = parser.parse_args()
    job_id = os.environ.get("JOB_ID") or f"solidworks_probe_{os.getpid()}"
    lock_result = None
    try:
        from app.services.solidworks_global_lock import acquire_lock, release_lock

        lock_result = acquire_lock(
            owner_project=os.environ.get("SW_DRAWING_STUDIO_OWNER_PROJECT", "sw_drawing_studio"),
            owner_workspace=str(REPO_ROOT),
            job_id=job_id,
            operation=f"solidworks_com_probe:{args.method}",
            part_path="",
            timeout_sec=args.lock_timeout_s,
            run_id=os.environ.get("RUN_ID", ""),
            ttl_sec=5,
        )
    except Exception as exc:
        lock_result = {"acquired": False, "status": "lock_error", "reason": str(exc)}

    if not lock_result or not lock_result.get("acquired"):
        payload = {
            "schema": "sw_drawing_studio.solidworks_com_probe.v1",
            "method": args.method,
            "status": "blocked_by_solidworks_lock",
            "reason": (lock_result or {}).get("reason", "blocked_by_solidworks_lock"),
            "fix_suggestion": (lock_result or {}).get("fix_suggestion", "等待当前 CAD job 完成，或手动确认后释放 stale lock"),
            "owner": (lock_result or {}).get("owner", {}),
            "elapsed_ms": 0,
        }
        print(json.dumps(payload, ensure_ascii=False), flush=True)
        return 2

    try:
        payload = _probe(args.method)
        payload["solidworks_lock"] = {"status": lock_result.get("status"), "owner_job_id": job_id}
    finally:
        try:
            release_lock(job_id, "solidworks_com_probe_finished")
        except Exception:
            pass
    print(json.dumps(payload, ensure_ascii=False), flush=True)
    return 0 if payload.get("status") == "connected" else 1


if __name__ == "__main__":
    sys.exit(main())
