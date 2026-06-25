from __future__ import annotations

import inspect
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.validation import real_cad_smoke_v3 as smoke


def test_lb26001_006_direct_smoke_blocks_before_facade_when_readiness_fails() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        part = root / "LB26001-A-04-006.SLDPRT"
        report = root / "cad_smoke.json"
        packet = root / "lb26001_006_rerun_packet_v4_2.json"
        part.write_text("dummy part", encoding="utf-8")

        guard = smoke._lb26001_006_direct_cad_guard(
            part,
            sw_state={
                "source": "unit_fixture",
                "process_present": False,
                "responding": None,
                "main_window_title": "",
            },
            packet_report_path=packet,
        )
        payload = smoke._write_lb26001_006_direct_guard_report(part, report, guard)
        written = json.loads(report.read_text(encoding="utf-8"))
        packet_written = json.loads(packet.read_text(encoding="utf-8"))

    assert guard["required"] is True
    assert guard["allowed"] is False
    assert guard["status"] == "blocked_by_lb26001_006_direct_guard"
    assert guard["ready_to_start_locked_006_cad"] is False
    assert guard["rerun_packet_report"] == str(packet)
    assert packet_written["schema"] == "sw_drawing_studio.lb26001_006_rerun_packet.v4_2"
    assert "solidworks_not_running" in guard["readiness_blocking_issue_keys"]
    assert guard["automatic_restart_allowed"] is False
    assert payload["pass"] is False
    assert written["status"]["status"] == "blocked_by_lb26001_006_direct_guard"
    assert written["run_dir"] == ""
    assert written["lb26001_006_rerun_packet_report"] == str(packet)
    assert written["event_types"] == []
    assert written["checks"][0]["name"] == "lb26001_006_no_com_readiness_and_rerun_packet_guard"


def test_non_006_direct_smoke_guard_is_not_applicable() -> None:
    guard = smoke._lb26001_006_direct_cad_guard(Path("LB26001-A-04-040.SLDPRT"))

    assert guard["required"] is False
    assert guard["allowed"] is True
    assert guard["status"] == "not_applicable"


def test_real_cad_smoke_main_calls_006_direct_guard_before_process_guard() -> None:
    source = inspect.getsource(smoke.main)
    guard_index = source.index("_lb26001_006_direct_cad_guard(")
    process_guard_index = source.index("run_smoke_with_process_guard(")

    assert guard_index < process_guard_index


def test_real_cad_smoke_sets_006_rerun_packet_env_for_worker() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        part = root / "LB26001-A-04-006.SLDPRT"
        packet = root / "packet.json"
        old_value = smoke.os.environ.get("SWDS_LB26001_006_RERUN_PACKET_PATH")
        try:
            result = smoke._set_006_rerun_packet_env(part, packet)
        finally:
            if old_value is None:
                smoke.os.environ.pop("SWDS_LB26001_006_RERUN_PACKET_PATH", None)
            else:
                smoke.os.environ["SWDS_LB26001_006_RERUN_PACKET_PATH"] = old_value

    assert result == str(packet)


if __name__ == "__main__":
    test_lb26001_006_direct_smoke_blocks_before_facade_when_readiness_fails()
    test_non_006_direct_smoke_guard_is_not_applicable()
    test_real_cad_smoke_main_calls_006_direct_guard_before_process_guard()
    test_real_cad_smoke_sets_006_rerun_packet_env_for_worker()
    print("PASS test_v4_2_real_cad_smoke_guard")
