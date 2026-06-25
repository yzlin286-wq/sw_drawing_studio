from __future__ import annotations

from pathlib import Path


SPEC_TEXT = Path("build_exe.spec").read_text(encoding="utf-8")


REQUIRED_DATAS = [
    "app/workers/cad_job_worker.py",
    "app/workers/batch_job_worker.py",
    "app/workers/drawing_review_worker.py",
    "app/workers/qc_action_worker.py",
    "app/workers/diagnostics_action_worker.py",
    "app/workers/llm_action_worker.py",
    "app/workers/health_check_worker.py",
    "app/workers/solidworks_com_probe_worker.py",
    "app/workers/vision_audit_worker.py",
    "app/workers/mock_long_job_worker.py",
    ".trae/specs/build-v6-and-validate-exe-ui/drw_qc_loop_v6.py",
    ".trae/specs/build-v6-and-validate-exe-ui/drw_generate_v6.py",
    ".trae/specs/enforce-drawing-quality/drw_qc_loop.py",
    ".trae/specs/enforce-drawing-quality/drw_generate_v5.py",
    ".trae/specs/enforce-drawing-quality/drw_quality_check.py",
    ".trae/specs/enforce-drawing-quality/gb_drawing_rules.md",
    ".trae/specs/enforce-drawing-quality/sw_api_drawing_rules.md",
    ".trae/specs/repair-section-and-recompare/section_helper.py",
    "templates/macros/auto_annotate.bas",
    "templates/macros/build_swp.py",
    "templates/macros/precompile_swp.py",
    "templates/build_drwdot.py",
    "templates/probe_drwdot.py",
]


REQUIRED_HIDDENIMPORTS = [
    "app.services.job_event_bus",
    "app.services.job_queue",
    "app.services.job_runner",
    "app.services.job_runtime_facade",
    "app.services.resource_paths",
    "app.services.system_health_service",
    "app.services.generated_output_scanner",
    "app.services.visual_audit_service",
    "app.services.visual_audit_reporter",
    "app.services.vision_qc_v4",
    "app.services.vision_qc_v5",
    "app.services.vision_evidence_fusion",
    "app.services.vision_false_positive_filter",
    "app.services.vision_issue_tracker",
    "app.services.sw_watchdog",
    "app.services.sw_recovery_policy",
    "app.services.sw_session_supervisor",
    "app.services.sw_dialog_guard",
    "app.services.dialog_guard",
    "app.services.dimension_arrange_service",
    "app.services.layout_solver_v2",
    "app.ui.job_queue_page",
    "app.ui.system_health_page",
    "app.ui.visual_audit_page",
    "app.ui.logs_diagnostics_page",
    "app.ui.titlebar_dialog",
    "app.workers.cad_job_worker",
    "app.workers.batch_job_worker",
    "app.workers.drawing_review_worker",
    "app.workers.qc_action_worker",
    "app.workers.diagnostics_action_worker",
    "app.workers.llm_action_worker",
    "app.workers.health_check_worker",
    "app.workers.solidworks_com_probe_worker",
    "app.workers.vision_audit_worker",
    "app.workers.mock_long_job_worker",
]


def test_build_spec_includes_v23_datas() -> None:
    missing = [item for item in REQUIRED_DATAS if item not in SPEC_TEXT]
    assert not missing, missing


def test_build_spec_includes_v23_hiddenimports() -> None:
    missing = [item for item in REQUIRED_HIDDENIMPORTS if item not in SPEC_TEXT]
    assert not missing, missing


if __name__ == "__main__":
    test_build_spec_includes_v23_datas()
    test_build_spec_includes_v23_hiddenimports()
    print("v2.3 build spec verification PASS")
