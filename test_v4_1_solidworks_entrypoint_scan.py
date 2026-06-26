from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from app.services.solidworks_entrypoint_scanner import scan_solidworks_entrypoints
from tools.validation.scan_solidworks_entrypoints_v4_1 import write_report


def main() -> None:
    service_report = scan_solidworks_entrypoints()
    assert service_report["schema"] == "sw_drawing_studio.unguarded_solidworks_entrypoints.v4_4"
    assert "ui_thread_direct_risk_count" in service_report
    assert "ui_thread_subprocess_call_count" in service_report
    assert "ui_threadpool_worker_count" in service_report
    assert "service_direct_risk_count" in service_report
    assert "system_health_ui_thread_direct_probe_count" in service_report
    report = write_report()
    out = Path(report["report_path"])
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["entrypoint_count"] >= 1
    assert data["status"] == "pass"
    assert data["unguarded_or_unknown_count"] == 0
    assert any(
        entry["file"].endswith("cad_job_worker.py") and entry["guard_status"] == "worker_process"
        for entry in data["entries"]
    )
    assert data["system_health_ui_thread_direct_probe_count"] == 0
    assert data["ui_thread_direct_risk_count"] == 0
    assert data["ui_thread_subprocess_call_count"] == 0
    assert data["ui_threadpool_worker_count"] == 0
    assert data["service_direct_risk_count"] == 0
    assert data["external_addin_host_lock_contract_status"] == "pass"
    contract_checks = {
        item.get("key"): item
        for item in data["external_addin_host_lock_contract"]["checks"]
        if isinstance(item, dict)
    }
    assert contract_checks["refdoc_relink_strategies_require_current_job_lock"]["status"] == "pass"
    assert not any(
        entry["file"].startswith("app/ui/")
        and "System Health direct collect" in set(entry.get("patterns") or [])
        for entry in data["entries"]
    )
    for ui_path in ["app/ui/system_health_page.py", "app/ui/home_page.py"]:
        source = Path(ui_path).read_text(encoding="utf-8")
        assert "collect_system_health" not in source
    legacy_worker_source = Path("app/ui/_workers.py").read_text(encoding="utf-8")
    for token in ["QThreadPool", "QRunnable", "LLMWorker", "RunnerWorker"]:
        assert token not in legacy_worker_source
    assert not any(
        entry["file"].startswith("app/ui/")
        and "Qt ThreadPool worker" in set(entry.get("patterns") or [])
        for entry in data["entries"]
    )
    assert not any(
        entry["file"].startswith("app/ui/")
        and "subprocess.Popen" in set(entry.get("patterns") or [])
        for entry in data["entries"]
    )
    assert not any(
        entry["file"].startswith("app/ui/")
        and "os.startfile" in set(entry.get("patterns") or [])
        for entry in data["entries"]
    )
    for ui_path in [
        "app/ui/home_page.py",
        "app/ui/logs_diagnostics_page.py",
        "app/ui/job_queue_page.py",
        "app/ui/single_part_page.py",
        "app/ui/visual_audit_page.py",
    ]:
        source = Path(ui_path).read_text(encoding="utf-8")
        assert "subprocess.Popen" not in source
        assert "os.startfile" not in source
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        bad = root / "app" / "ui" / "bad_shell_open.py"
        bad.parent.mkdir(parents=True)
        bad.write_text(
            "import os\nimport subprocess\n"
            "def open_dir(path):\n"
            "    subprocess.Popen(['explorer', str(path)])\n"
            "    os.startfile(str(path))\n",
            encoding="utf-8",
        )
        synthetic = scan_solidworks_entrypoints(root)
        assert synthetic["status"] == "warning"
        assert synthetic["ui_thread_subprocess_call_count"] == 2
        assert synthetic["ui_thread_direct_risk_count"] == 2
        assert len(synthetic["ui_thread_subprocess_calls"]) == 2
    print("OK test_v4_1_solidworks_entrypoint_scan")


if __name__ == "__main__":
    main()
