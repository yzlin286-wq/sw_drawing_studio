from __future__ import annotations

import contextlib
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Iterator

LOCK_VERSION = 1
DEFAULT_TTL_SEC = 180
LOCK_PATH_ENV = "SW_DRAWING_STUDIO_LOCK_PATH"
CONFLICT_LOG_ENV = "SW_DRAWING_STUDIO_CONFLICT_LOG"
OWNER_PROJECT_ENV = "SW_DRAWING_STUDIO_OWNER_PROJECT"
LOCK_JOB_ID_ENV = "SW_DRAWING_STUDIO_LOCK_JOB_ID"


def default_lock_path() -> Path:
    override = os.environ.get(LOCK_PATH_ENV, "").strip()
    if override:
        return Path(override)
    root = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
    return root / "sw_drawing_studio" / "solidworks_global_lock.json"


def conflict_log_path() -> Path:
    override = os.environ.get(CONFLICT_LOG_ENV, "").strip()
    if override:
        return Path(override)
    return default_lock_path().with_name("solidworks_lock_conflicts.jsonl")


def read_lock() -> dict[str, Any] | None:
    path = default_lock_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception as exc:
        return {
            "lock_version": LOCK_VERSION,
            "status": "corrupt",
            "reason": str(exc),
            "lock_path": str(path),
        }


def acquire_lock(
    owner_project: str,
    owner_workspace: str,
    job_id: str,
    operation: str,
    part_path: str,
    timeout_sec: float,
    *,
    run_id: str = "",
    ttl_sec: int = DEFAULT_TTL_SEC,
    allow_restart_sw: bool = False,
    owner_worker_pid: int | None = None,
    sw_pid: int | None = None,
) -> dict[str, Any]:
    """Acquire the machine-wide SolidWorks lock without touching SolidWorks COM."""
    deadline = time.monotonic() + max(0.0, float(timeout_sec or 0.0))
    job_id = str(job_id or "").strip() or f"pid-{os.getpid()}"
    owner_worker_pid = int(owner_worker_pid or os.getpid())

    while True:
        with _file_mutex():
            existing = read_lock()
            if not existing or existing.get("status") in {"released", "corrupt"}:
                record = _new_record(
                    owner_project=owner_project,
                    owner_workspace=owner_workspace,
                    job_id=job_id,
                    operation=operation,
                    part_path=part_path,
                    run_id=run_id,
                    ttl_sec=ttl_sec,
                    allow_restart_sw=allow_restart_sw,
                    owner_worker_pid=owner_worker_pid,
                    sw_pid=sw_pid,
                )
                _write_lock(record)
                os.environ[LOCK_JOB_ID_ENV] = job_id
                _log_conflict("lock_acquired", record)
                return {"acquired": True, "status": "acquired", "lock": record}

            if _same_owner(existing, job_id):
                record = dict(existing)
                record["heartbeat_at"] = _now_iso()
                record["status"] = "active"
                record["operation"] = operation or record.get("operation", "")
                record["part_path"] = part_path or record.get("part_path", "")
                record["owner_worker_pid"] = owner_worker_pid
                if sw_pid is not None:
                    record["sw_pid"] = sw_pid
                _write_lock(record)
                os.environ[LOCK_JOB_ID_ENV] = job_id
                return {"acquired": True, "status": "already_owned", "lock": record}

            if is_lock_stale(existing):
                stale = dict(existing)
                _remove_lock()
                _log_conflict("stale_lock_released", stale, {"requested_by_job_id": job_id})
                continue

            conflict = explain_conflict(existing)
            payload = {
                "acquired": False,
                "status": "blocked_by_solidworks_lock",
                "owner": _owner_summary(existing),
                "reason": conflict.get("reason", ""),
                "fix_suggestion": conflict.get("fix_suggestion", ""),
                "lock": existing,
            }
            _log_conflict(
                "lock_conflict",
                existing,
                {
                    "requested_by_job_id": job_id,
                    "requested_operation": operation,
                    "requested_part_path": part_path,
                    "timeout_sec": timeout_sec,
                },
            )
            if time.monotonic() >= deadline:
                return payload

        time.sleep(0.25)


def release_lock(job_id: str, reason: str = "") -> dict[str, Any]:
    job_id = str(job_id or "").strip()
    with _file_mutex():
        existing = read_lock()
        if not existing:
            return {"released": True, "status": "no_lock", "reason": reason}
        if existing.get("status") == "corrupt":
            return {"released": False, "status": "corrupt_lock", "lock": existing}
        if not _same_owner(existing, job_id):
            conflict = explain_conflict(existing)
            result = {
                "released": False,
                "status": "blocked_by_solidworks_lock",
                "owner": _owner_summary(existing),
                "reason": conflict.get("reason", ""),
                "fix_suggestion": conflict.get("fix_suggestion", ""),
                "lock": existing,
            }
            _log_conflict("release_conflict", existing, {"requested_by_job_id": job_id, "reason": reason})
            return result
        _remove_lock()
        _log_conflict("lock_released", existing, {"reason": reason})
        if os.environ.get(LOCK_JOB_ID_ENV) == job_id:
            os.environ.pop(LOCK_JOB_ID_ENV, None)
        return {"released": True, "status": "released", "reason": reason, "lock": existing}


def heartbeat(job_id: str) -> dict[str, Any]:
    job_id = str(job_id or "").strip()
    with _file_mutex():
        existing = read_lock()
        if not existing:
            return {"updated": False, "status": "no_lock"}
        if not _same_owner(existing, job_id):
            return {
                "updated": False,
                "status": "blocked_by_solidworks_lock",
                "owner": _owner_summary(existing),
                "fix_suggestion": explain_conflict(existing).get("fix_suggestion", ""),
            }
        existing["heartbeat_at"] = _now_iso()
        existing["owner_worker_pid"] = os.getpid()
        existing["status"] = "active"
        _write_lock(existing)
        return {"updated": True, "status": "heartbeat", "lock": existing}


def wait_for_lock(timeout_sec: float = 30.0, poll_interval: float = 0.25) -> dict[str, Any]:
    deadline = time.monotonic() + max(0.0, float(timeout_sec or 0.0))
    while True:
        existing = read_lock()
        if not existing or existing.get("status") in {"released", "corrupt"} or is_lock_stale(existing):
            return {"available": True, "status": "available", "lock": existing}
        if time.monotonic() >= deadline:
            return {
                "available": False,
                "status": "blocked_by_solidworks_lock",
                "owner": _owner_summary(existing),
                "fix_suggestion": explain_conflict(existing).get("fix_suggestion", ""),
                "lock": existing,
            }
        time.sleep(max(0.05, float(poll_interval)))


def force_release_stale_lock(reason: str = "stale_lock") -> dict[str, Any]:
    with _file_mutex():
        existing = read_lock()
        if not existing:
            return {"released": False, "status": "no_lock"}
        if not is_lock_stale(existing):
            return {
                "released": False,
                "status": "lock_not_stale",
                "owner": _owner_summary(existing),
                "fix_suggestion": "等待当前 CAD job 完成，或确认 owner 进程不存在且 heartbeat 超时后再释放 stale lock",
                "lock": existing,
            }
        _remove_lock()
        _log_conflict("force_release_stale_lock", existing, {"reason": reason})
        return {"released": True, "status": "released_stale", "lock": existing, "reason": reason}


def is_lock_stale(lock: dict[str, Any] | None = None, *, now: float | None = None) -> bool:
    lock = lock if lock is not None else read_lock()
    if not lock or lock.get("status") in {"released", "corrupt"}:
        return False
    owner_pid = _int_or_none(lock.get("owner_pid"))
    owner_worker_pid = _int_or_none(lock.get("owner_worker_pid"))
    if _pid_alive(owner_pid) or _pid_alive(owner_worker_pid):
        return False
    ttl = _float_or_default(lock.get("ttl_sec"), DEFAULT_TTL_SEC)
    heartbeat_at = _parse_iso_epoch(str(lock.get("heartbeat_at") or lock.get("created_at") or ""))
    if heartbeat_at <= 0:
        return True
    return (now if now is not None else time.time()) - heartbeat_at > ttl


def explain_conflict(lock: dict[str, Any] | None = None) -> dict[str, Any]:
    lock = lock if lock is not None else read_lock()
    if not lock:
        return {"reason": "no_active_solidworks_lock", "fix_suggestion": ""}
    owner = _owner_summary(lock)
    if is_lock_stale(lock):
        return {
            "reason": "solidworks_lock_is_stale",
            "owner": owner,
            "fix_suggestion": "检测到锁已过期，可释放；释放前请确认 owner 进程不存在且无未保存文档",
        }
    return {
        "reason": "SolidWorks 正被另一个任务使用",
        "owner": owner,
        "fix_suggestion": "等待当前 CAD job 完成，或手动确认后释放 stale lock",
    }


def current_job_holds_lock(job_id: str | None = None) -> bool:
    job_id = str(job_id or os.environ.get(LOCK_JOB_ID_ENV) or os.environ.get("JOB_ID") or "").strip()
    if not job_id:
        return False
    lock = read_lock()
    return bool(lock and _same_owner(lock, job_id) and not is_lock_stale(lock))


def require_current_job_lock(operation: str = "") -> dict[str, Any]:
    job_id = os.environ.get(LOCK_JOB_ID_ENV) or os.environ.get("JOB_ID") or ""
    if current_job_holds_lock(job_id):
        return {"ok": True, "status": "lock_held", "job_id": job_id, "lock": read_lock()}
    lock = read_lock()
    conflict = explain_conflict(lock)
    return {
        "ok": False,
        "status": "blocked_by_solidworks_lock",
        "operation": operation,
        "job_id": job_id,
        "owner": conflict.get("owner") or _owner_summary(lock or {}),
        "reason": conflict.get("reason", "SolidWorks COM requires global lock"),
        "fix_suggestion": conflict.get("fix_suggestion", "通过 JobRuntimeFacade/CAD worker 持锁后再调用 SolidWorks COM"),
    }


def conflict_log_tail(limit: int = 20) -> list[dict[str, Any]]:
    path = conflict_log_path()
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-max(1, int(limit)) :]
    except Exception:
        return []
    rows: list[dict[str, Any]] = []
    for line in lines:
        try:
            item = json.loads(line)
            if isinstance(item, dict):
                rows.append(item)
        except Exception:
            continue
    return rows


def _new_record(
    *,
    owner_project: str,
    owner_workspace: str,
    job_id: str,
    operation: str,
    part_path: str,
    run_id: str,
    ttl_sec: int,
    allow_restart_sw: bool,
    owner_worker_pid: int,
    sw_pid: int | None,
) -> dict[str, Any]:
    return {
        "lock_version": LOCK_VERSION,
        "owner_project": owner_project or os.environ.get(OWNER_PROJECT_ENV, "sw_drawing_studio"),
        "owner_workspace": owner_workspace,
        "owner_codex_session": _codex_session(),
        "owner_pid": os.getpid(),
        "owner_worker_pid": owner_worker_pid,
        "owner_job_id": job_id,
        "owner_run_id": run_id,
        "operation": operation,
        "part_path": part_path,
        "sw_pid": sw_pid,
        "created_at": _now_iso(),
        "heartbeat_at": _now_iso(),
        "ttl_sec": int(ttl_sec or DEFAULT_TTL_SEC),
        "allow_restart_sw": bool(allow_restart_sw),
        "status": "active",
    }


def _same_owner(lock: dict[str, Any], job_id: str) -> bool:
    if not job_id:
        return False
    return str(lock.get("owner_job_id") or "") == str(job_id)


def _owner_summary(lock: dict[str, Any]) -> dict[str, Any]:
    if not lock:
        return {}
    heartbeat_at = str(lock.get("heartbeat_at") or "")
    return {
        "owner_project": lock.get("owner_project", ""),
        "owner_workspace": lock.get("owner_workspace", ""),
        "owner_job_id": lock.get("owner_job_id", ""),
        "owner_run_id": lock.get("owner_run_id", ""),
        "owner_pid": lock.get("owner_pid"),
        "owner_worker_pid": lock.get("owner_worker_pid"),
        "operation": lock.get("operation", ""),
        "part_path": lock.get("part_path", ""),
        "sw_pid": lock.get("sw_pid"),
        "heartbeat_at": heartbeat_at,
        "heartbeat_age_s": _heartbeat_age_s(heartbeat_at),
        "stale_lock": is_lock_stale(lock),
    }


def _write_lock(record: dict[str, Any]) -> None:
    path = default_lock_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name, suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(record, fh, ensure_ascii=False, indent=2)
        os.replace(tmp_name, path)
    finally:
        try:
            Path(tmp_name).unlink(missing_ok=True)
        except Exception:
            pass


def _remove_lock() -> None:
    try:
        default_lock_path().unlink(missing_ok=True)
    except Exception:
        pass


@contextlib.contextmanager
def _file_mutex() -> Iterator[None]:
    path = default_lock_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    mutex_path = path.with_suffix(path.suffix + ".mutex")
    with mutex_path.open("a+b") as fh:
        try:
            if fh.seek(0, os.SEEK_END) == 0:
                fh.write(b"\0")
                fh.flush()
            fh.seek(0)
        except Exception:
            pass
        try:
            import msvcrt

            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_LOCK, 1)
            yield
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        except ImportError:
            yield
        except Exception:
            with contextlib.suppress(Exception):
                import msvcrt

                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
            raise


def _log_conflict(event_type: str, lock: dict[str, Any], extra: dict[str, Any] | None = None) -> None:
    payload = {
        "timestamp": _now_iso(),
        "event_type": event_type,
        "lock_path": str(default_lock_path()),
        "lock": _owner_summary(lock),
        "extra": extra or {},
    }
    path = conflict_log_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _pid_alive(pid: int | None) -> bool:
    if not pid or pid <= 0:
        return False
    if pid == os.getpid():
        return True
    if os.name == "nt":
        return _pid_alive_windows(pid)
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except Exception:
        return False


def _pid_alive_windows(pid: int) -> bool:
    try:
        import ctypes
        from ctypes import wintypes
    except Exception:
        return False

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    STILL_ACTIVE = 259
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
    if not handle:
        return False
    try:
        exit_code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return False
        return int(exit_code.value) == STILL_ACTIVE
    finally:
        kernel32.CloseHandle(handle)


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())


def _parse_iso_epoch(value: str) -> float:
    if not value:
        return 0.0
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return time.mktime(time.strptime(value[:19], fmt))
        except Exception:
            continue
    return 0.0


def _heartbeat_age_s(value: str) -> float | None:
    epoch = _parse_iso_epoch(value)
    if epoch <= 0:
        return None
    return round(max(0.0, time.time() - epoch), 3)


def _codex_session() -> str:
    for key in ("CODEX_SESSION_ID", "CODEX_THREAD_ID", "SESSIONNAME"):
        value = os.environ.get(key, "").strip()
        if value:
            return value
    return ""


def _int_or_none(value: Any) -> int | None:
    try:
        parsed = int(value)
        return parsed if parsed > 0 else None
    except Exception:
        return None


def _float_or_default(value: Any, default: float) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)
