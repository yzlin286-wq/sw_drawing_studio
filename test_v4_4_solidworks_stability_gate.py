from __future__ import annotations

import json
from pathlib import Path

from tools.validation.run_solidworks_stability_gate_v4_4 import (
    CONFLICT_REPORT,
    ENTRYPOINT_REPORT,
    LOCK_TEST_REPORT,
    SUMMARY_REPORT,
    run_gate,
)


ROOT = Path(__file__).resolve().parent


def main() -> None:
    summary = run_gate()
    assert summary["schema"] == "sw_drawing_studio.solidworks_stability_gate.v4_4"
    assert summary["status"] in {"pass", "warning"}
    assert summary["release_ready"] is False

    for path in [ENTRYPOINT_REPORT, LOCK_TEST_REPORT, CONFLICT_REPORT, SUMMARY_REPORT]:
        assert path.exists(), path
        data = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(data, dict), path

    entrypoint = json.loads(ENTRYPOINT_REPORT.read_text(encoding="utf-8"))
    assert entrypoint["schema"] == "sw_drawing_studio.unguarded_solidworks_entrypoints.v4_4"
    assert entrypoint["status"] == "pass"
    assert entrypoint["unguarded_or_unknown_count"] == 0
    assert entrypoint["system_health_ui_thread_direct_probe_count"] == 0
    assert entrypoint["ui_thread_direct_risk_count"] == 0
    assert entrypoint["service_direct_risk_count"] == 0
    assert entrypoint["bounded_probe_worker_launcher_count"] >= 1
    assert entrypoint["system_health_worker_probe_service_count"] >= 1
    assert entrypoint["external_addin_host_lock_contract_status"] == "pass"
    contract = entrypoint["external_addin_host_lock_contract"]
    assert contract["pass"] is True
    assert contract["failed_count"] == 0

    lock_result = json.loads(LOCK_TEST_REPORT.read_text(encoding="utf-8"))
    assert lock_result["schema"] == "sw_drawing_studio.solidworks_lock_test_result.v4_4"
    assert lock_result["status"] == "pass"

    batch_worker = (ROOT / "app" / "workers" / "batch_job_worker.py").read_text(encoding="utf-8")
    assert "SolidWorksResourceAudit" in batch_worker
    assert "_finalize_solidworks_resources" in batch_worker
    assert "DOC_REGISTRY_ENV" in batch_worker
    assert "RESOURCE_AUDIT_ENV" in batch_worker

    generator = (
        ROOT / ".trae" / "specs" / "build-v6-and-validate-exe-ui" / "drw_generate_v6.py"
    ).read_text(encoding="utf-8")
    for marker in [
        "initial_part_open",
        "new_drawing_created",
        "seed_work_part_open",
        "final_close_generated_drawing",
        "final_close_work_part",
    ]:
        assert marker in generator

    print("PASS test_v4_4_solidworks_stability_gate")


if __name__ == "__main__":
    main()
