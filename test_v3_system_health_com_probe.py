from __future__ import annotations

import app.services.system_health_service as health


def test_system_health_skips_addin_when_com_probe_times_out() -> None:
    original_probe = health.probe_solidworks_connection
    original_addin = health._probe_addin_ping

    def fake_probe(*, timeout_s=3.0, allow_dispatch=False, allow_dispatch_ex=False):
        return {
            "schema": "sw_drawing_studio.solidworks_com_probe.v1",
            "method": "get_active_object",
            "connection_method": "get_active_object",
            "status": "timeout",
            "reason": "get_active_object timed out after 3.0s",
            "elapsed_ms": 3000,
        }

    def fail_addin():
        raise AssertionError("Add-in Ping must not run when SolidWorks COM is unavailable")

    health.probe_solidworks_connection = fake_probe
    health._probe_addin_ping = fail_addin
    try:
        rows, summary = health.collect_system_health()
    finally:
        health.probe_solidworks_connection = original_probe
        health._probe_addin_ping = original_addin

    solidworks = health.find_row(rows, "solidworks")
    addin = health.find_row(rows, "addin_ping")
    assert solidworks is not None
    assert addin is not None
    assert solidworks.status == "warning"
    assert solidworks.details
    assert solidworks.details.get("failure_bucket") == "solidworks_com_active_object_timeout"
    assert "COM" in solidworks.message
    assert addin.status == "warning"
    assert "已跳过" in addin.message
    assert summary["total"] == len(rows)
    print("PASS test_v3_system_health_com_probe")


if __name__ == "__main__":
    test_system_health_skips_addin_when_com_probe_times_out()
