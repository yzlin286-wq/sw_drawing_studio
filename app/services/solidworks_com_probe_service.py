from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from app.services.resource_paths import child_process_env, worker_command


WORKER_PATH = Path(__file__).resolve().parent.parent / "workers" / "solidworks_com_probe_worker.py"


def probe_solidworks_connection(
    *,
    timeout_s: float = 3.0,
    allow_dispatch: bool = False,
    allow_dispatch_ex: bool = False,
) -> dict[str, Any]:
    methods = ["get_active_object"]
    if allow_dispatch:
        methods.append("dispatch")
    if allow_dispatch_ex:
        methods.append("dispatch_ex")

    attempts: list[dict[str, Any]] = []
    for method in methods:
        attempt = _probe_method(method, timeout_s=timeout_s)
        attempts.append(attempt)
        if attempt.get("status") == "connected":
            result = dict(attempt)
            result["attempts"] = attempts
            result["connection_method"] = method
            return result
        if attempt.get("status") == "timeout":
            break

    last = attempts[-1] if attempts else {"status": "failed", "reason": "no_probe_attempts"}
    result = dict(last)
    result["attempts"] = attempts
    result["connection_method"] = str(last.get("method") or "")
    return result


def _probe_method(method: str, *, timeout_s: float) -> dict[str, Any]:
    started = time.monotonic()
    program, args = worker_command("solidworks_com_probe", WORKER_PATH, ["--method", method])
    cmd = [program, *args]
    proc: subprocess.Popen[str] | None = None
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(Path(__file__).resolve().parent.parent.parent),
            env=child_process_env(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        stdout, stderr = proc.communicate(timeout=max(0.5, float(timeout_s)))
    except subprocess.TimeoutExpired:
        _kill_process_tree(proc)
        stdout, stderr = _communicate_after_kill(proc)
        return {
            "schema": "sw_drawing_studio.solidworks_com_probe.v1",
            "method": method,
            "status": "timeout",
            "reason": f"{method} timed out after {float(timeout_s):.1f}s",
            "elapsed_ms": int((time.monotonic() - started) * 1000),
            "stdout_tail": _tail(stdout),
            "stderr_tail": _tail(stderr),
            "worker_pid": proc.pid if proc else None,
            "worker_killed": True,
        }
    except Exception as exc:
        return {
            "schema": "sw_drawing_studio.solidworks_com_probe.v1",
            "method": method,
            "status": "failed",
            "reason": str(exc),
            "elapsed_ms": int((time.monotonic() - started) * 1000),
        }

    stdout = (stdout or "").strip()
    stderr = (stderr or "").strip()
    payload = stdout.splitlines()[-1] if stdout else "{}"
    try:
        result = json.loads(payload)
        if not isinstance(result, dict):
            result = {"status": "failed", "reason": "probe_output_not_object"}
    except Exception as exc:
        result = {"status": "failed", "reason": f"invalid_probe_json: {exc}"}
    result.setdefault("schema", "sw_drawing_studio.solidworks_com_probe.v1")
    result.setdefault("method", method)
    result["returncode"] = proc.returncode if proc else None
    result["elapsed_ms"] = int((time.monotonic() - started) * 1000)
    if stderr:
        result["stderr_tail"] = _tail(stderr)
    if result.get("status") != "connected" and not result.get("reason"):
        result["reason"] = f"probe_returncode_{proc.returncode if proc else 'unknown'}"
    return result


def _kill_process_tree(proc: subprocess.Popen[str] | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    if sys.platform.startswith("win"):
        try:
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
                check=False,
            )
        except Exception:
            pass
        try:
            proc.wait(timeout=5)
            return
        except Exception:
            pass
    try:
        proc.kill()
    except Exception:
        pass
    try:
        proc.wait(timeout=3)
    except Exception:
        pass


def _communicate_after_kill(proc: subprocess.Popen[str] | None) -> tuple[str, str]:
    if proc is None:
        return "", ""
    try:
        stdout, stderr = proc.communicate(timeout=2)
        return stdout or "", stderr or ""
    except Exception:
        _kill_process_tree(proc)
        return "", ""


def _tail(text: str | bytes | None, limit: int = 1000) -> str:
    if not text:
        return ""
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="replace")
    return str(text)[-limit:]
