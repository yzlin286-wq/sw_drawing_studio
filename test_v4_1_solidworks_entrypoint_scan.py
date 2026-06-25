from __future__ import annotations

import json
from pathlib import Path

from app.services.solidworks_entrypoint_scanner import scan_solidworks_entrypoints
from tools.validation.scan_solidworks_entrypoints_v4_1 import write_report


def main() -> None:
    service_report = scan_solidworks_entrypoints()
    assert service_report["schema"] == "sw_drawing_studio.unguarded_solidworks_entrypoints.v4_2"
    report = write_report()
    out = Path(report["report_path"])
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["entrypoint_count"] >= 1
    assert data["status"] in {"pass", "warning"}
    assert any(
        entry["file"].endswith("cad_job_worker.py") and entry["guard_status"] == "guarded"
        for entry in data["entries"]
    )
    print("OK test_v4_1_solidworks_entrypoint_scan")


if __name__ == "__main__":
    main()
