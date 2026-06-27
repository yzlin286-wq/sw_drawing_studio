from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from app.services.solidworks_global_lock import current_job_holds_lock, read_lock

RESOURCE_AUDIT_SCHEMA = "sw_drawing_studio.solidworks_resource_audit.v1"
DOCUMENT_REGISTRY_SCHEMA = "sw_drawing_studio.solidworks_document_registry.v1"
DOC_REGISTRY_ENV = "SWDS_SOLIDWORKS_DOC_REGISTRY"
RESOURCE_AUDIT_ENV = "SWDS_SOLIDWORKS_RESOURCE_AUDIT"


def document_registry_path(run_dir: str | Path) -> Path:
    return Path(run_dir) / "solidworks_document_registry.jsonl"


def document_registry_summary_path(run_dir: str | Path) -> Path:
    return Path(run_dir) / "solidworks_document_registry.json"


def append_document_registry_event(
    registry_path: str | Path,
    event_type: str,
    *,
    job_id: str = "",
    role: str = "",
    path: str = "",
    title: str = "",
    doc_type: str | int = "",
    stage: str = "",
    owned_by_job: bool = True,
    close_verified: bool | None = None,
    reason: str = "",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    registry = Path(registry_path)
    registry.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "schema": DOCUMENT_REGISTRY_SCHEMA,
        "event_type": str(event_type),
        "timestamp": _now(),
        "job_id": str(job_id or os.environ.get("JOB_ID") or ""),
        "role": str(role or ""),
        "path": str(path or ""),
        "title": str(title or ""),
        "doc_type": str(doc_type or ""),
        "stage": str(stage or ""),
        "owned_by_job": bool(owned_by_job),
        "close_verified": close_verified,
        "reason": str(reason or ""),
        "extra": extra or {},
    }
    with registry.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")
    return event


def load_document_registry_events(run_dir_or_path: str | Path) -> list[dict[str, Any]]:
    path = Path(run_dir_or_path)
    if path.is_dir():
        path = document_registry_path(path)
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def summarize_document_registry(run_dir_or_path: str | Path) -> dict[str, Any]:
    events = load_document_registry_events(run_dir_or_path)
    open_docs: dict[str, dict[str, Any]] = {}
    close_failures: list[dict[str, Any]] = []
    opened_count = 0
    closed_count = 0
    for event in events:
        event_type = str(event.get("event_type") or "")
        if not bool(event.get("owned_by_job", True)):
            continue
        key = _doc_key(event)
        if event_type == "solidworks_doc_opened":
            opened_count += 1
            open_docs[key] = dict(event)
        elif event_type == "solidworks_doc_closed":
            closed_count += 1
            if event.get("close_verified") is False:
                close_failures.append(dict(event))
            open_docs.pop(key, None)
        elif event_type == "solidworks_doc_close_failed":
            close_failures.append(dict(event))
    summary = {
        "schema": DOCUMENT_REGISTRY_SCHEMA,
        "generated_at": _now(),
        "event_count": len(events),
        "opened_count": opened_count,
        "closed_count": closed_count,
        "open_job_owned_documents": list(open_docs.values()),
        "open_job_owned_document_count": len(open_docs),
        "close_failures": close_failures,
        "close_failure_count": len(close_failures),
    }
    path = Path(run_dir_or_path)
    if path.is_dir():
        out = document_registry_summary_path(path)
        out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        summary["path"] = str(out)
    return summary


def collect_solidworks_processes() -> list[dict[str, Any]]:
    rows = _collect_processes_with_psutil()
    if rows:
        return rows
    return _collect_processes_with_powershell()


def collect_open_document_snapshot(job_id: str) -> dict[str, Any]:
    if not current_job_holds_lock(job_id):
        return {
            "collected": False,
            "open_doc_count": None,
            "documents": [],
            "reason": "solidworks_com_probe_skipped_without_current_job_lock",
        }
    com_context = _initialize_com_for_resource_audit()
    try:
        import win32com.client

        sw = win32com.client.GetActiveObject("SldWorks.Application")
        documents = _enumerate_sw_documents(sw)
        return {
            "collected": True,
            "open_doc_count": len(documents),
            "documents": documents,
            "reason": "",
        }
    except Exception as exc:
        return {
            "collected": False,
            "open_doc_count": None,
            "documents": [],
            "reason": str(exc),
        }
    finally:
        _uninitialize_com_for_resource_audit(com_context)


class SolidWorksResourceAudit:
    def __init__(self, run_dir: str | Path, job_id: str, run_id: str = "") -> None:
        self.run_dir = Path(run_dir)
        self.job_id = str(job_id or "")
        self.run_id = str(run_id or self.run_dir.name)
        self.path = self.run_dir / "solidworks_resource_audit.json"
        self.run_dir.mkdir(parents=True, exist_ok=True)

    def capture(
        self,
        phase: str,
        *,
        lock_result: dict[str, Any] | None = None,
        registry_summary: dict[str, Any] | None = None,
        include_com_documents: bool = True,
    ) -> dict[str, Any]:
        snapshot = build_resource_snapshot(
            self.job_id,
            phase,
            lock_result=lock_result,
            registry_summary=registry_summary,
            include_com_documents=include_com_documents,
        )
        payload = self._load()
        payload.setdefault("snapshots", []).append(snapshot)
        blockers = _aggregate_blockers(payload.get("snapshots") or [])
        payload.update({
            "schema": RESOURCE_AUDIT_SCHEMA,
            "generated_at": _now(),
            "job_id": self.job_id,
            "run_id": self.run_id,
            "run_dir": str(self.run_dir),
            "status": "blocked_by_solidworks_resource_pressure" if blockers else "pass",
            "pass": not bool(blockers),
            "resource_blockers": blockers,
            "latest_phase": phase,
        })
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        snapshot["audit_path"] = str(self.path)
        return snapshot

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {
                "schema": RESOURCE_AUDIT_SCHEMA,
                "snapshots": [],
            }
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {"schema": RESOURCE_AUDIT_SCHEMA, "snapshots": []}
        except Exception:
            return {"schema": RESOURCE_AUDIT_SCHEMA, "snapshots": []}


def build_resource_snapshot(
    job_id: str,
    phase: str,
    *,
    lock_result: dict[str, Any] | None = None,
    registry_summary: dict[str, Any] | None = None,
    include_com_documents: bool = True,
) -> dict[str, Any]:
    processes = collect_solidworks_processes()
    lock = read_lock()
    holds_lock = current_job_holds_lock(job_id)
    open_documents = (
        collect_open_document_snapshot(job_id)
        if include_com_documents and holds_lock
        else {
            "collected": False,
            "open_doc_count": None,
            "documents": [],
            "reason": "not_current_lock_owner" if not holds_lock else "disabled",
        }
    )
    snapshot = {
        "phase": str(phase),
        "timestamp": _now(),
        "job_id": str(job_id or ""),
        "lock_state": {
            "current_job_holds_lock": bool(holds_lock),
            "lock": lock or {},
            "lock_result_status": (lock_result or {}).get("status", ""),
            "lock_acquired": bool((lock_result or {}).get("acquired")),
        },
        "solidworks_processes": processes,
        "solidworks_process_count": len(processes),
        "memory_working_set_mb": round(sum(float(p.get("working_set_mb") or 0.0) for p in processes), 3),
        "private_memory_mb": round(sum(float(p.get("private_memory_mb") or 0.0) for p in processes), 3),
        "handle_count": sum(int(p.get("handle_count") or 0) for p in processes),
        "open_documents": open_documents,
        "open_doc_count": open_documents.get("open_doc_count"),
        "document_registry": registry_summary or {},
    }
    snapshot["resource_blockers"] = resource_blockers(snapshot)
    snapshot["pass"] = not bool(snapshot["resource_blockers"])
    snapshot["status"] = "blocked_by_solidworks_resource_pressure" if snapshot["resource_blockers"] else "pass"
    return snapshot


def resource_blockers(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    process_count = int(snapshot.get("solidworks_process_count") or 0)
    lock_state = snapshot.get("lock_state") if isinstance(snapshot.get("lock_state"), dict) else {}
    if process_count and not bool(lock_state.get("current_job_holds_lock")):
        blockers.append({
            "key": "solidworks_running_without_current_job_lock",
            "status": "blocked_by_solidworks_lock",
            "reason": "SolidWorks is running but this job does not own the global lock.",
            "fix_suggestion": "Run real CAD only through the lock-owning CAD worker, or wait for the current lock owner.",
        })
    lock = lock_state.get("lock") if isinstance(lock_state.get("lock"), dict) else {}
    operation = str(lock.get("operation") or "")
    owner_job = str(lock.get("owner_job_id") or "")
    if operation.startswith("system_health.") and owner_job != str(snapshot.get("job_id") or ""):
        blockers.append({
            "key": "system_health_probe_owns_solidworks_lock",
            "status": "blocked_by_solidworks_lock",
            "reason": "A System Health probe owns the SolidWorks lock.",
            "fix_suggestion": "Wait for the bounded System Health probe to finish before starting CAD.",
        })

    max_open_docs = _env_int("SWDS_SOLIDWORKS_MAX_OPEN_DOCS", 20)
    open_doc_count = snapshot.get("open_doc_count")
    if isinstance(open_doc_count, int) and max_open_docs > 0 and open_doc_count > max_open_docs:
        blockers.append({
            "key": "solidworks_open_doc_count_too_high",
            "status": "blocked_by_solidworks_resource_pressure",
            "open_doc_count": open_doc_count,
            "threshold": max_open_docs,
            "reason": "Too many SolidWorks documents are open before or after the CAD job.",
            "fix_suggestion": "Close unrelated SolidWorks documents and retry through the CAD worker.",
        })

    max_working_set_mb = _env_float("SWDS_SOLIDWORKS_MAX_WORKING_SET_MB", 8192.0)
    working_set_mb = float(snapshot.get("memory_working_set_mb") or 0.0)
    if max_working_set_mb > 0 and working_set_mb > max_working_set_mb:
        blockers.append({
            "key": "solidworks_memory_too_high",
            "status": "blocked_by_solidworks_resource_pressure",
            "working_set_mb": round(working_set_mb, 3),
            "threshold_mb": max_working_set_mb,
            "reason": "SolidWorks memory pressure is above the configured limit.",
            "fix_suggestion": "Save user work, close unrelated documents, and retry without auto-restarting SolidWorks.",
        })

    max_handles = _env_int("SWDS_SOLIDWORKS_MAX_HANDLES", 50000)
    handle_count = int(snapshot.get("handle_count") or 0)
    if max_handles > 0 and handle_count > max_handles:
        blockers.append({
            "key": "solidworks_handle_count_too_high",
            "status": "blocked_by_solidworks_resource_pressure",
            "handle_count": handle_count,
            "threshold": max_handles,
            "reason": "SolidWorks handle count is above the configured limit.",
            "fix_suggestion": "Close unrelated documents and retry after resource pressure drops.",
        })

    registry = snapshot.get("document_registry") if isinstance(snapshot.get("document_registry"), dict) else {}
    if int(registry.get("close_failure_count") or 0) > 0:
        blockers.append({
            "key": "job_owned_document_close_failed",
            "status": "blocked_by_solidworks_resource_pressure",
            "close_failure_count": int(registry.get("close_failure_count") or 0),
            "reason": "One or more job-owned SolidWorks documents could not be verified closed.",
            "fix_suggestion": "Inspect solidworks_document_registry.json and avoid another CAD rerun until cleanup is clean.",
        })
    return blockers


def cleanup_job_owned_documents(run_dir: str | Path, job_id: str) -> dict[str, Any]:
    run_dir_path = Path(run_dir)
    registry_path = document_registry_path(run_dir_path)
    before = summarize_document_registry(run_dir_path)
    open_docs = list(before.get("open_job_owned_documents") or [])
    cleanup_records: list[dict[str, Any]] = []
    if not open_docs:
        return {
            "status": "pass",
            "pass": True,
            "cleanup_records": cleanup_records,
            "registry_summary": before,
        }
    if not current_job_holds_lock(job_id):
        append_document_registry_event(
            registry_path,
            "solidworks_doc_close_failed",
            job_id=job_id,
            role="cleanup",
            stage="cleanup_job_owned_documents",
            reason="current_job_does_not_hold_lock",
        )
        after = summarize_document_registry(run_dir_path)
        return {
            "status": "blocked_by_solidworks_lock",
            "pass": False,
            "cleanup_records": cleanup_records,
            "registry_summary": after,
            "reason": "current_job_does_not_hold_lock",
        }
    com_context = _initialize_com_for_resource_audit()
    try:
        import win32com.client

        sw = win32com.client.GetActiveObject("SldWorks.Application")
    except Exception as exc:
        append_document_registry_event(
            registry_path,
            "solidworks_doc_close_failed",
            job_id=job_id,
            role="cleanup",
            stage="cleanup_job_owned_documents",
            reason=f"connect_failed: {exc}",
        )
        after = summarize_document_registry(run_dir_path)
        return {
            "status": "blocked_by_solidworks_resource_pressure",
            "pass": False,
            "cleanup_records": cleanup_records,
            "registry_summary": after,
            "reason": str(exc),
        }
    finally:
        if "sw" not in locals():
            _uninitialize_com_for_resource_audit(com_context)

    try:
        for doc in open_docs:
            role = str(doc.get("role") or "")
            path = str(doc.get("path") or "")
            title = str(doc.get("title") or "")
            stage = str(doc.get("stage") or "cleanup")
            record = {"role": role, "path": path, "title": title, "stage": stage}
            try:
                model = _get_open_document(sw, path, title)
                if model is None:
                    append_document_registry_event(
                        registry_path,
                        "solidworks_doc_closed",
                        job_id=job_id,
                        role=role,
                        path=path,
                        title=title,
                        stage="cleanup_not_open",
                        close_verified=True,
                        reason="document_not_open",
                    )
                    record["close_verified"] = True
                    record["reason"] = "document_not_open"
                    cleanup_records.append(record)
                    continue
                actual_title = _read_com_value(model, "GetTitle") or title
                sw.CloseDoc(actual_title)
                still_open = _get_open_document(sw, path, actual_title) is not None
                append_document_registry_event(
                    registry_path,
                    "solidworks_doc_closed" if not still_open else "solidworks_doc_close_failed",
                    job_id=job_id,
                    role=role,
                    path=path,
                    title=str(actual_title or title),
                    stage="cleanup_job_owned_documents",
                    close_verified=not still_open,
                    reason="" if not still_open else "document_still_open_after_CloseDoc",
                )
                record["close_verified"] = not still_open
                record["reason"] = "" if not still_open else "document_still_open_after_CloseDoc"
            except Exception as exc:
                append_document_registry_event(
                    registry_path,
                    "solidworks_doc_close_failed",
                    job_id=job_id,
                    role=role,
                    path=path,
                    title=title,
                    stage="cleanup_job_owned_documents",
                    close_verified=False,
                    reason=str(exc),
                )
                record["close_verified"] = False
                record["reason"] = str(exc)
            cleanup_records.append(record)
    finally:
        _uninitialize_com_for_resource_audit(com_context)
    after = summarize_document_registry(run_dir_path)
    ok = int(after.get("open_job_owned_document_count") or 0) == 0 and int(after.get("close_failure_count") or 0) == 0
    return {
        "status": "pass" if ok else "blocked_by_solidworks_resource_pressure",
        "pass": ok,
        "cleanup_records": cleanup_records,
        "registry_summary": after,
    }


def _initialize_com_for_resource_audit() -> Any:
    try:
        import pythoncom

        pythoncom.CoInitialize()
        return pythoncom
    except Exception:
        return None


def _uninitialize_com_for_resource_audit(com_context: Any) -> None:
    if com_context is None:
        return
    try:
        com_context.CoUninitialize()
    except Exception:
        pass


def _collect_processes_with_psutil() -> list[dict[str, Any]]:
    try:
        import psutil
    except Exception:
        return []
    rows: list[dict[str, Any]] = []
    try:
        for proc in psutil.process_iter(["pid", "name", "memory_info"]):
            name = str(proc.info.get("name") or "")
            if name.lower() != "sldworks.exe":
                continue
            mem = proc.info.get("memory_info")
            try:
                handle_count = proc.num_handles() if hasattr(proc, "num_handles") else None
            except Exception:
                handle_count = None
            rows.append({
                "pid": int(proc.info.get("pid") or 0),
                "name": name,
                "working_set_mb": _bytes_to_mb(getattr(mem, "rss", 0)),
                "private_memory_mb": _bytes_to_mb(getattr(mem, "private", 0) or getattr(mem, "vms", 0)),
                "handle_count": handle_count,
            })
    except Exception:
        return []
    return rows


def _collect_processes_with_powershell() -> list[dict[str, Any]]:
    if not sys.platform.startswith("win"):
        return []
    try:
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        proc = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue | "
                "Select-Object Id,ProcessName,WorkingSet64,PrivateMemorySize64,HandleCount | "
                "ConvertTo-Json -Compress",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            check=False,
            creationflags=creationflags,
        )
    except Exception:
        return []
    text = (proc.stdout or "").strip()
    if not text:
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    items = data if isinstance(data, list) else [data]
    rows: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        rows.append({
            "pid": _int(item.get("Id")),
            "name": str(item.get("ProcessName") or "SLDWORKS") + ".exe",
            "working_set_mb": _bytes_to_mb(item.get("WorkingSet64")),
            "private_memory_mb": _bytes_to_mb(item.get("PrivateMemorySize64")),
            "handle_count": _int(item.get("HandleCount")),
        })
    return rows


def _aggregate_blockers(snapshots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[str, dict[str, Any]] = {}
    for snapshot in snapshots:
        for blocker in snapshot.get("resource_blockers") or []:
            if isinstance(blocker, dict):
                by_key[str(blocker.get("key") or len(by_key))] = blocker
    return list(by_key.values())


def _enumerate_sw_documents(sw: Any) -> list[dict[str, Any]]:
    docs = []
    seen: set[str] = set()
    raw_docs = _read_com_value(sw, "GetDocuments")
    if raw_docs:
        try:
            for doc in list(raw_docs):
                _append_doc(docs, seen, doc)
        except Exception:
            pass
    if not docs:
        first = _read_com_value(sw, "GetFirstDocument")
        current = first
        for _ in range(200):
            if current is None:
                break
            _append_doc(docs, seen, current)
            current = _read_com_value(current, "GetNext")
    return docs


def _append_doc(docs: list[dict[str, Any]], seen: set[str], doc: Any) -> None:
    title = str(_read_com_value(doc, "GetTitle") or "")
    path = str(_read_com_value(doc, "GetPathName") or "")
    doc_type = _read_com_value(doc, "GetType")
    key = _normalize_path(path) or title
    if not key or key in seen:
        return
    seen.add(key)
    docs.append({"title": title, "path": path, "doc_type": str(doc_type or "")})


def _get_open_document(sw: Any, path: str, title: str) -> Any | None:
    getter = getattr(sw, "GetOpenDocumentByName", None)
    for key in (path, title, Path(path).name if path else ""):
        if not key or not callable(getter):
            continue
        try:
            doc = getter(str(key))
            if doc is not None:
                return doc
        except Exception:
            continue
    for doc in _enumerate_sw_documents(sw):
        if path and _normalize_path(doc.get("path")) == _normalize_path(path):
            return _get_open_document_by_title(sw, doc.get("title") or title)
        if title and str(doc.get("title") or "") == title:
            return _get_open_document_by_title(sw, title)
    return None


def _get_open_document_by_title(sw: Any, title: str) -> Any | None:
    getter = getattr(sw, "GetOpenDocumentByName", None)
    if not callable(getter) or not title:
        return None
    try:
        return getter(str(title))
    except Exception:
        return None


def _read_com_value(obj: Any, name: str) -> Any:
    try:
        value = getattr(obj, name)
        return value() if callable(value) else value
    except Exception:
        return None


def _doc_key(event: dict[str, Any]) -> str:
    return _normalize_path(event.get("path")) or str(event.get("title") or "") or str(id(event))


def _normalize_path(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        return os.path.normcase(os.path.abspath(text))
    except Exception:
        return text.lower()


def _bytes_to_mb(value: Any) -> float:
    try:
        return round(float(value or 0) / (1024.0 * 1024.0), 3)
    except Exception:
        return 0.0


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.environ.get(key, "") or default)
    except Exception:
        return default


def _env_float(key: str, default: float) -> float:
    try:
        return float(os.environ.get(key, "") or default)
    except Exception:
        return default


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())
