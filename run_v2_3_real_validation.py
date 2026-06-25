"""v2.3 real CAD validation harness.

This intentionally launches the CAD worker, which can drive SolidWorks. It is
kept separate from smoke tests so release evidence clearly distinguishes:
- no-SolidWorks smoke validation
- deliberate real-world CAD validation

Default scope is one historically fast/deliverable part. Broader gates such as
024/040, core_12, LB26001_36, medium_30, visual audit, and 129 full should be
run after this smoke passes.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_PART = REPO_ROOT / "3D转2D测试图纸" / "LB26001-A-04-040.SLDPRT"
VALIDATION_DIR = REPO_ROOT / "drw_output" / "v23_validation"
RESULT_JSON = VALIDATION_DIR / "real_validation_smoke.json"


def _emit_print(line: str) -> None:
    print(line, flush=True)


def _parse_jsonl_line(line: str) -> dict[str, Any] | None:
    line = line.strip()
    if not line:
        return None
    try:
        obj = json.loads(line)
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _find_output_files(part_path: Path, run_dir: Path | None) -> dict[str, dict[str, Any]]:
    base = part_path.stem
    candidates: dict[str, list[Path]] = {
        "slddrw": [],
        "pdf": [],
        "dxf": [],
        "png": [],
        "qc_json": [],
        "manifest": [],
    }
    if run_dir:
        candidates["manifest"].append(run_dir / "manifest.json")
        candidates["qc_json"].append(run_dir / "qc" / f"{base}_v5_qc.json")
        for ext, key in [("SLDDRW", "slddrw"), ("PDF", "pdf"), ("DXF", "dxf"), ("PNG", "png")]:
            candidates[key].append(run_dir / "drawing" / f"{base}_v5.{ext}")
    v5 = REPO_ROOT / "drw_output" / "v5"
    candidates["qc_json"].append(v5 / f"{base}_v5_qc.json")
    for ext, key in [("SLDDRW", "slddrw"), ("PDF", "pdf"), ("DXF", "dxf"), ("PNG", "png")]:
        candidates[key].append(v5 / f"{base}_v5.{ext}")

    out: dict[str, dict[str, Any]] = {}
    for key, paths in candidates.items():
        found = next((p for p in paths if p.exists()), None)
        out[key] = {
            "exists": bool(found),
            "path": str(found) if found else "",
            "size_bytes": found.stat().st_size if found else 0,
            "modified_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(found.stat().st_mtime)) if found else "",
        }
    return out


def run_one(part_path: Path, timeout_s: int, max_rounds: int) -> dict[str, Any]:
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    if not part_path.exists():
        return {
            "part": str(part_path),
            "status": "error",
            "error": "part not found",
            "deliverable": False,
        }

    run_dir = VALIDATION_DIR / f"{part_path.stem}_{time.strftime('%Y%m%d_%H%M%S')}"
    run_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "-X",
        "utf8",
        "-u",
        str(REPO_ROOT / "app" / "workers" / "cad_job_worker.py"),
        "--job-id",
        "v23_real_smoke",
        "--part-path",
        str(part_path),
        "--output-dir",
        str(run_dir),
        "--max-rounds",
        str(max_rounds),
        "--timeout-s",
        str(timeout_s),
    ]
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    env["RUN_DIR"] = str(run_dir)
    env["RUN_ID"] = f"v23smoke_{part_path.stem}"

    events: list[dict[str, Any]] = []
    raw_tail: list[str] = []
    start = time.time()
    rc = -1
    timeout_hit = False

    _emit_print(f"[v2.3 real] part={part_path}")
    _emit_print(f"[v2.3 real] run_dir={run_dir}")
    _emit_print(f"[v2.3 real] timeout_s={timeout_s} max_rounds={max_rounds}")

    proc = subprocess.Popen(
        cmd,
        cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        env=env,
    )

    assert proc.stdout is not None
    try:
        while True:
            line = proc.stdout.readline()
            if line:
                line = line.rstrip("\r\n")
                raw_tail.append(line)
                raw_tail = raw_tail[-80:]
                event = _parse_jsonl_line(line)
                if event:
                    events.append(event)
                    et = event.get("event_type")
                    msg = event.get("message") or ""
                    if et in {"job_started", "progress", "job_finished", "job_failed", "heartbeat"}:
                        _emit_print(f"[event] {et}: {msg[:180]}")
                else:
                    _emit_print(f"[raw] {line[:240]}")
            if proc.poll() is not None:
                break
            if time.time() - start > timeout_s + 180:
                timeout_hit = True
                proc.kill()
                break
        rc = proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        timeout_hit = True
        proc.kill()
        rc = proc.wait(timeout=30)

    elapsed_s = round(time.time() - start, 1)
    manifest = _read_json(run_dir / "manifest.json")
    output_files = _find_output_files(part_path, run_dir)
    qc_path = Path(output_files["qc_json"]["path"]) if output_files["qc_json"]["path"] else Path()
    qc = _read_json(qc_path) if qc_path.exists() else {}
    finished = [e for e in events if e.get("event_type") == "job_finished"]
    failed = [e for e in events if e.get("event_type") == "job_failed"]

    core_files_ok = all(output_files[k]["exists"] for k in ["slddrw", "pdf", "dxf", "png"])
    manifest_usable = (manifest.get("drawing_usable") or {}).get("pass")
    qc_usable = (qc.get("drawing_usable") or {}).get("pass")
    deliverable = bool(core_files_ok and (manifest_usable is not False) and (qc_usable is not False))

    result = {
        "part": str(part_path),
        "base": part_path.stem,
        "status": "pass" if deliverable and rc == 0 and not timeout_hit else "fail",
        "returncode": rc,
        "elapsed_s": elapsed_s,
        "timeout_hit": timeout_hit,
        "run_dir": str(run_dir),
        "events_total": len(events),
        "event_counts": {
            "job_started": sum(1 for e in events if e.get("event_type") == "job_started"),
            "progress": sum(1 for e in events if e.get("event_type") == "progress"),
            "heartbeat": sum(1 for e in events if e.get("event_type") == "heartbeat"),
            "job_finished": len(finished),
            "job_failed": len(failed),
        },
        "output_files": output_files,
        "core_files_ok": core_files_ok,
        "deliverable": deliverable,
        "manifest": str(run_dir / "manifest.json") if (run_dir / "manifest.json").exists() else "",
        "manifest_drawing_usable": manifest.get("drawing_usable", {}),
        "manifest_hard_fail": manifest.get("hard_fail", []),
        "qc_json": str(qc_path) if qc_path.exists() else "",
        "qc_pass": qc.get("pass"),
        "qc_score_pass_count": qc.get("score_pass_count"),
        "qc_hard_fail": qc.get("hard_fail", []),
        "raw_tail": raw_tail[-30:],
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Run v2.3 real CAD validation smoke")
    parser.add_argument("--part", default=str(DEFAULT_PART), help="SLDPRT path")
    parser.add_argument("--timeout-s", type=int, default=900)
    parser.add_argument("--max-rounds", type=int, default=1)
    args = parser.parse_args()

    part_path = Path(args.part)
    if not part_path.is_absolute():
        part_path = (REPO_ROOT / part_path).resolve()

    result = run_one(part_path, timeout_s=args.timeout_s, max_rounds=args.max_rounds)
    payload = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "scope": "single_part_real_smoke",
        "solidworks_expected": True,
        "results": [result],
        "pass": bool(result.get("deliverable") and result.get("returncode") == 0 and not result.get("timeout_hit")),
    }
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    RESULT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _emit_print(f"[v2.3 real] saved={RESULT_JSON}")
    _emit_print(f"[v2.3 real] pass={payload['pass']} deliverable={result.get('deliverable')} rc={result.get('returncode')}")
    return 0 if payload["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
