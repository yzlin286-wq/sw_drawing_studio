"""v2.3 mock worker for validating QProcess/job UI plumbing.

This worker intentionally avoids SolidWorks, OCR, YOLO, and network calls. It emits
the same JSONL protocol as real workers so UI pages can prove that long-running
jobs do not freeze the main process before real CAD validation is attempted.
"""
from __future__ import annotations

import argparse
import json
import sys
import time

sys.stdout.reconfigure(line_buffering=True)


def _emit(event_type: str, job_id: str, data: dict | None = None, message: str = "") -> None:
    event = {
        "event_type": event_type,
        "type": event_type,
        "job_id": job_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "data": data or {},
        "message": message,
    }
    print(json.dumps(event, ensure_ascii=False), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Mock long-running job worker")
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--scenario", default="normal_pass",
                        choices=[
                            "pass",
                            "normal_pass",
                            "pass_with_warning",
                            "timeout",
                            "failed",
                            "recovered",
                            "stuck_then_recovered",
                        ])
    parser.add_argument("--duration-s", type=float, default=10.0)
    args = parser.parse_args()

    job_id = args.job_id
    scenario = args.scenario
    duration_s = max(0.0, float(args.duration_s))

    if scenario == "pass":
        scenario = "normal_pass"

    _emit("job_started", job_id,
          data={"job_type": "mock", "scenario": scenario, "duration_s": duration_s},
          message=f"Mock job started: {scenario}")

    steps = max(1, int(duration_s / 0.1))
    sleep_s = duration_s / steps if steps else 0
    for i in range(steps):
        if sleep_s:
            time.sleep(sleep_s)
        progress = round((i + 1) / steps, 3)
        _emit("progress", job_id,
              data={"progress": progress, "stage": f"mock_step_{i + 1}/{steps}"},
              message=f"Mock progress {progress:.0%}")
        if i % 10 == 0:
            _emit("heartbeat", job_id, data={"ts": time.time()}, message="mock alive")
        if scenario == "stuck_then_recovered" and i == max(0, steps // 3):
            _emit("warning", job_id,
                  data={
                      "key": "mock_stuck",
                      "reason": "simulated stuck worker period",
                      "recoverable": True,
                      "stage": "stuck",
                  },
                  message="Mock worker appears stuck; recovery will be attempted")
            time.sleep(min(1.0, max(0.2, duration_s / 5 if duration_s else 0.2)))
            _emit("recovered", job_id,
                  data={
                      "key": "mock_stuck_recovered",
                      "reason": "simulated recovery completed",
                      "stage": "recovered",
                  },
                  message="Mock worker recovered from simulated stuck period")

    if scenario == "pass_with_warning":
        _emit("warning", job_id,
              data={"warning": "mock warning for UI rendering"},
              message="Mock warning emitted")
    elif scenario == "recovered":
        _emit("warning", job_id,
              data={"action": "recover", "reason": "simulated transient failure"},
              message="Mock recovered from simulated transient failure")
        _emit("recovered", job_id,
              data={"action": "recover", "reason": "simulated transient failure", "stage": "recovered"},
              message="Mock recovery completed")
    elif scenario == "timeout":
        _emit("job_failed", job_id,
              data={"error": "mock timeout", "scenario": scenario},
              message="Mock job timed out")
        return 2
    elif scenario == "failed":
        _emit("job_failed", job_id,
              data={"error": "mock failure", "scenario": scenario},
              message="Mock job failed")
        return 1

    _emit("job_finished", job_id,
          data={"result": {"ok": True, "scenario": scenario, "duration_s": duration_s}},
          message="Mock job finished")
    return 0


if __name__ == "__main__":
    sys.exit(main())
