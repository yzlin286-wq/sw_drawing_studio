"""v2.3 EXE smoke checks that do not launch SolidWorks.

This validates the frozen dispatch paths added for v2.3:
- ``--worker mock`` can run from the onefile EXE and emit JSONL events.
- ``--pipeline-script-info drw_quality_check`` can locate bundled scripts
  without executing COM-heavy pipeline code.
- The GUI process can start and stay alive briefly.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_EXE = REPO_ROOT / "dist_v23_smoke" / "sw_drawing_studio_v23_smoke.exe"


def _decode(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


def check_mock_worker(exe_path: Path) -> bool:
    print("\n--- v2.3 frozen mock worker ---")
    cmd = [
        str(exe_path),
        "--worker",
        "mock",
        "--job-id",
        "smoke",
        "--scenario",
        "normal_pass",
        "--duration-s",
        "0.1",
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    stdout = _decode(proc.stdout)
    stderr = _decode(proc.stderr)
    events = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            print(f"WARN: non-json stdout line: {line[:160]}")

    event_types = {event.get("event_type") for event in events}
    ok = (
        proc.returncode == 0
        and "job_started" in event_types
        and "progress" in event_types
        and "job_finished" in event_types
    )
    print(f"returncode={proc.returncode}")
    print(f"events={sorted(str(x) for x in event_types if x)}")
    if stderr.strip():
        print(f"stderr={stderr[:500]}")
    print(f"mock_worker={'PASS' if ok else 'FAIL'}")
    return ok


def check_pipeline_dispatch_info(exe_path: Path) -> bool:
    print("\n--- v2.3 frozen pipeline dispatch info ---")
    cmd = [
        str(exe_path),
        "--pipeline-script-info",
        "drw_quality_check",
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    stdout = _decode(proc.stdout)
    stderr = _decode(proc.stderr)
    info = {}
    try:
        info = json.loads(stdout.strip().splitlines()[-1])
    except Exception as exc:
        print(f"WARN: could not parse pipeline info JSON: {exc}")

    ok = (
        proc.returncode == 0
        and info.get("script_key") == "drw_quality_check"
        and info.get("exists") is True
        and str(info.get("script_path", "")).endswith("drw_quality_check.py")
    )
    print(f"returncode={proc.returncode}")
    print(f"info={info}")
    if stderr.strip():
        print(f"stderr={stderr[:500]}")
    print(f"pipeline_dispatch_info={'PASS' if ok else 'FAIL'}")
    return ok


def check_gui_alive(exe_path: Path) -> bool:
    print("\n--- v2.3 GUI alive smoke ---")
    proc = subprocess.Popen(
        [str(exe_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    print(f"pid={proc.pid}")
    time.sleep(5)
    alive = proc.poll() is None
    print(f"alive_after_5s={alive}")
    if alive:
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=8)
        return True

    stdout, stderr = proc.communicate(timeout=5)
    print(f"returncode={proc.returncode}")
    print(f"stdout={_decode(stdout)[:500]}")
    print(f"stderr={_decode(stderr)[:500]}")
    return False


def main() -> int:
    exe_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_EXE
    print("=" * 70)
    print("v2.3 EXE smoke")
    print("=" * 70)
    print(f"exe={exe_path}")

    if not exe_path.exists():
        print(f"FAIL: EXE 不存在: {exe_path}")
        return 1
    print(f"size_mb={exe_path.stat().st_size / 1024 / 1024:.1f}")

    checks = {
        "mock_worker": check_mock_worker(exe_path),
        "pipeline_dispatch_info": check_pipeline_dispatch_info(exe_path),
        "gui_alive": check_gui_alive(exe_path),
    }

    print("\n=== v2.3 EXE smoke summary ===")
    for name, ok in checks.items():
        print(f"{name}: {'PASS' if ok else 'FAIL'}")
    if all(checks.values()):
        print("PASS: v2.3 EXE smoke passed")
        return 0
    print("FAIL: v2.3 EXE smoke failed")
    return 1


if __name__ == "__main__":
    sys.exit(main())
