from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parent
FIXTURE_DIR = ROOT / "drw_output" / "_qc_action_worker_test"


def _parse_events(stdout: str) -> list[dict]:
    events: list[dict] = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        events.append(json.loads(line))
    return events


def test_render_png_worker_smoke() -> None:
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    slddrw = FIXTURE_DIR / "fixture.SLDDRW"
    existing_png = FIXTURE_DIR / "fixture.PNG"
    out_png = FIXTURE_DIR / "fixture_rendered.PNG"
    slddrw.write_text("dummy drawing placeholder", encoding="utf-8")
    Image.new("RGB", (32, 24), "white").save(existing_png)
    if out_png.exists():
        out_png.unlink()
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "app" / "workers" / "qc_action_worker.py"),
            "--job-id",
            "qc_render_smoke",
            "--action",
            "render_png",
            "--slddrw-path",
            str(slddrw),
            "--png-path",
            str(out_png),
            "--run-dir",
            str(FIXTURE_DIR),
        ],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=env,
        timeout=20,
    )

    events = _parse_events(proc.stdout)
    event_types = {event.get("event_type") for event in events}
    assert proc.returncode == 0, proc.stderr
    assert {"job_started", "progress", "heartbeat", "job_finished"} <= event_types
    assert out_png.exists() and out_png.stat().st_size > 0


if __name__ == "__main__":
    test_render_png_worker_smoke()
    print("v2.3 qc action worker verification PASS")
