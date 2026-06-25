from __future__ import annotations

import json
import tempfile
from pathlib import Path

from app.workers.cad_job_worker import _classify_failure, _write_failure_manifest


def main() -> None:
    result_data = {
        "returncode": 1,
        "lines": 22,
        "hard_fail": ["subprocess_failed"],
        "warnings": [],
        "subprocess_tail": [
            "[sw_connect] active probe status=timeout reason=GetActiveObject probe timed out after 15s revision=",
            "solidworks_active_object_timeout: GetActiveObject probe timed out after 15s",
        ],
    }
    classified = _classify_failure("subprocess_exit_code_1", result_data)
    assert classified["failure_bucket"] == "solidworks_com_active_object_timeout"
    assert classified["recoverable"] is True
    assert "SolidWorks" in classified["fix_suggestion"]

    with tempfile.TemporaryDirectory() as tmp:
        manifest = _write_failure_manifest(
            r"C:\workspace\3D转2D测试图纸\LB26001-A-04-006.SLDPRT",
            tmp,
            result_data,
            classified["failure_reason"],
        )
        manifest_path = Path(manifest["run_dir"]) / "manifest.json"
        sw_session_path = Path(manifest["run_dir"]) / "sw_session.json"
        manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
        sw_session = json.loads(sw_session_path.read_text(encoding="utf-8"))

    assert manifest_data["failure_bucket"] == "solidworks_com_active_object_timeout"
    assert manifest_data["run_id"]
    assert "solidworks_com_active_object_timeout" in manifest_data["hard_fail"]
    assert manifest_data["drawing_usable"]["pass"] is False
    assert manifest_data["fix_suggestion"]
    assert sw_session["failure_bucket"] == "solidworks_com_active_object_timeout"
    assert sw_session["evidence"]
    print("PASS test_v3_cad_failure_manifest")


if __name__ == "__main__":
    main()
