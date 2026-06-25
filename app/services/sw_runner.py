from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Signal

from app.services.resource_paths import (
    child_process_env,
    pipeline_command,
    pipeline_script_path,
    runtime_path,
)

RUNTIME_ROOT = runtime_path(".")
QC_LOG_MD = pipeline_script_path("drw_qc_loop_v5").with_name("qc_log.md")


class SwRunner(QObject):
    log_line = Signal(str)
    progress = Signal(int, int)
    finished = Signal(dict)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._proc: subprocess.Popen | None = None
        self._stop_flag = False

    def stop(self) -> None:
        self._stop_flag = True
        proc = self._proc
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
            except Exception:
                pass

    def run_single(
        self,
        sldprt_path: str,
        output_dir: str,
        max_rounds: int = 3,
    ) -> dict[str, Any]:
        sldprt = Path(sldprt_path)
        out_dir = Path(output_dir)
        base = sldprt.stem

        result: dict[str, Any] = {
            "ok": False,
            "sldprt": str(sldprt),
            "slddrw": "",
            "qc_json": "",
            "qc_log": str(QC_LOG_MD),
            "error": "",
        }

        if not sldprt.exists():
            result["error"] = f"SLDPRT not found: {sldprt}"
            self.log_line.emit(f"[runner] ERROR: {result['error']}")
            self.finished.emit(result)
            return result

        qc_loop_script: str
        v6_path = pipeline_script_path("drw_qc_loop_v6")
        v5_path = pipeline_script_path("drw_qc_loop_v5")
        use_v5 = os.environ.get("USE_V5", "") == "1"
        if v6_path.exists() and not use_v5:
            qc_script_key = "drw_qc_loop_v6"
            qc_loop_script = str(v6_path)
            self.log_line.emit("[runner] using v6")
        else:
            qc_script_key = "drw_qc_loop_v5"
            qc_loop_script = str(v5_path)
            if use_v5:
                self.log_line.emit("[runner] using v5 fallback")
            else:
                self.log_line.emit(f"[runner] using v5 (v6 missing at {v6_path})")

        if not Path(qc_loop_script).exists():
            result["error"] = f"qc loop script not found: {qc_loop_script}"
            self.log_line.emit(f"[runner] ERROR: {result['error']}")
            self.finished.emit(result)
            return result

        cmd = pipeline_command(qc_script_key, [str(sldprt)])
        self.log_line.emit(f"[runner] cwd = {RUNTIME_ROOT}")
        self.log_line.emit(f"[runner] cmd = {cmd}")
        self.log_line.emit(f"[runner] max_rounds = {max_rounds}")

        env = child_process_env()
        env["QC_LOOP_MAX_ROUNDS"] = str(int(max_rounds))

        try:
            self._proc = subprocess.Popen(
                cmd,
                cwd=str(RUNTIME_ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                env=env,
            )
        except Exception as exc:
            result["error"] = f"Popen failed: {exc}"
            self.log_line.emit(f"[runner] ERROR: {result['error']}")
            self.finished.emit(result)
            return result

        proc = self._proc
        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                if self._stop_flag:
                    break
                line = line.rstrip("\r\n")
                if line:
                    self.log_line.emit(line)
            proc.wait()
        except Exception as exc:
            self.log_line.emit(f"[runner] read stdout exception: {exc}")
        finally:
            rc = proc.returncode if proc else -1
            self.log_line.emit(f"[runner] subprocess returncode = {rc}")

        v5_dir = out_dir / "v5"
        slddrw = v5_dir / f"{base}_v5.SLDDRW"
        qc_json = v5_dir / f"{base}_v5_qc.json"

        if slddrw.exists():
            result["slddrw"] = str(slddrw)
        else:
            self.log_line.emit(f"[runner] WARN: slddrw not found: {slddrw}")

        if qc_json.exists():
            result["qc_json"] = str(qc_json)
            try:
                with qc_json.open("r", encoding="utf-8") as f:
                    qc_data = json.load(f)
                result["qc_pass"] = bool(qc_data.get("pass"))
                result["qc_pass_count"] = qc_data.get("score_pass_count")
            except Exception as exc:
                self.log_line.emit(f"[runner] WARN: read qc_json failed: {exc}")
        else:
            self.log_line.emit(f"[runner] WARN: qc_json not found: {qc_json}")

        result["ok"] = bool(result["slddrw"]) and (proc is not None and proc.returncode == 0)
        if not result["ok"] and not result["error"]:
            if proc is not None and proc.returncode != 0:
                result["error"] = f"subprocess returncode={proc.returncode}"
            elif not result["slddrw"]:
                result["error"] = "SLDDRW not generated"

        self.finished.emit(result)
        return result

    def run_batch(
        self,
        items: list[str],
        output_dir: str | None = None,
        max_rounds: int = 3,
    ) -> list[dict[str, Any]]:
        self._stop_flag = False
        results: list[dict[str, Any]] = []
        total = len(items)
        out_dir = output_dir or str(runtime_path("drw_output"))
        for idx, sldprt in enumerate(items, 1):
            if self._stop_flag:
                self.log_line.emit("[runner] batch stopped by user")
                break
            self.progress.emit(idx, total)
            self.log_line.emit(f"\n[runner] ===== batch {idx}/{total}: {sldprt} =====")
            res = self.run_single(sldprt, out_dir, max_rounds=max_rounds)
            results.append(res)
        self.progress.emit(total, total)
        return results
