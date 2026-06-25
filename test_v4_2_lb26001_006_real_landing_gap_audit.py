from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

import tools.validation.lb26001_006_real_landing_gap_audit_v4_2 as gap_mod
from tools.validation.lb26001_006_real_landing_gap_audit_v4_2 import (
    PRIMARY_BASE,
    REQUESTED_BASES,
    build_gap_audit,
)


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _source_fixtures(root: Path) -> dict[str, Path]:
    root.mkdir(parents=True, exist_ok=True)
    staged = root / "staged_cad_validation_v3.py"
    smoke = root / "real_cad_smoke_v3.py"
    runner = root / "job_runner.py"
    facade = root / "job_runtime_facade.py"
    cad_worker = root / "cad_job_worker.py"
    lock_source = root / "solidworks_global_lock.py"
    lock_test = root / "test_v4_2_cad_worker_lock_conflict.py"
    staged.write_text('"tools/validation/real_cad_smoke_v3.py"\n', encoding="utf-8")
    smoke.write_text("JobRuntimeFacade\nfacade.start_cad_job(\n", encoding="utf-8")
    runner.write_text("QProcess\nproc.start(program, args)\n", encoding="utf-8")
    facade.write_text('CAD_WORKER = "cad_job_worker.py"\n', encoding="utf-8")
    cad_worker.write_text(
        "blocked_by_solidworks_lock\nsolidworks_lock_conflict\nfailure_bucket\nfix_suggestion\n",
        encoding="utf-8",
    )
    lock_source.write_text("owner\nblocked_by_solidworks_lock\n", encoding="utf-8")
    lock_test.write_text("blocked_by_solidworks_lock\nsolidworks_lock_conflict\nfix_suggestion\n", encoding="utf-8")
    return {
        "staged_validation_source_path": staged,
        "real_cad_smoke_source_path": smoke,
        "job_runner_source_path": runner,
        "facade_source_path": facade,
        "cad_worker_source_path": cad_worker,
        "global_lock_source_path": lock_source,
        "lock_conflict_test_source_path": lock_test,
    }


def _base_fixture(root: Path, *, api_pass_count: int = 0, include_direct_guard: bool = True) -> dict[str, Path]:
    readiness = _write_json(
        root / "readiness.json",
        {
            "status": "blocked",
            "ready_to_start_locked_006_cad": False,
            "blocking_issue_keys": ["solidworks_not_running"],
            "safe_recovery_guidance": {
                "manual_recovery_required": True,
                "automatic_restart_allowed": False,
            },
        },
    )
    packet = _write_json(
        root / "rerun_packet.json",
        {
            "status": "blocked_by_solidworks_readiness",
            "packet_build_ready": True,
            "real_cad_allowed_now": False,
            "readiness_ready": False,
            "offline_prerequisite_missing_keys": [],
        },
    )
    matrix = [
        {
            "base": base,
            "pass": False,
            "application_ui_screenshot_required": True,
            "application_ui_screenshot_present": False,
            "application_ui_screenshot_file_count": 0,
            "application_ui_screenshot_content_check_pass": False,
            "manual_visual_judgement_present": False,
            "manual_visual_judgement_pass": False,
            "manual_visual_checklist_pass": False,
            "source_ui_report_application_ui_ok": False,
            "ui_visual_review_status": "ui_screenshot_missing",
            "missing_ui_acceptance_requirements": ["application_ui_screenshot_file"],
        }
        for base in REQUESTED_BASES
    ]
    matrix[0].update(
        {
            "application_ui_screenshot_present": True,
            "application_ui_screenshot_file_count": 1,
            "manual_visual_judgement_present": True,
            "manual_visual_checklist_failed_items": ["reference_match", "display_dimensions"],
            "latest_manual_visual_checklist": {
                "reference_match": False,
                "display_dimensions": False,
            },
            "latest_manual_visual_checklist_notes": {
                "reference_match": "Generated drawing differs from the UI screenshot reference comparison.",
            },
            "latest_manual_findings": ["006 still fails the Drawing Review UI screenshot comparison."],
            "latest_manual_required_correction": "Regenerate 006 and rerun application UI screenshot review.",
            "ui_screenshot_files": ["006_ui.png"],
            "comparison_image": "006_reference_vs_generated.png",
        }
    )
    requested = _write_json(
        root / "requested_status.json",
        {
            "status": "blocked_by_006",
            "requested_bases": list(REQUESTED_BASES),
            "pass_count": api_pass_count,
            "not_pass_count": len(REQUESTED_BASES) - api_pass_count,
            "api_is_not_final_judgement": True,
            "final_judgement_requires_application_ui_per_drawing": True,
            "per_drawing_ui_review_incomplete_count": len(REQUESTED_BASES),
            "per_drawing_ui_review_matrix": matrix,
        },
    )
    direct = root / "direct_guard.json"
    if include_direct_guard:
        _write_json(
            direct,
            {
                "pass": False,
                "run_dir": "",
                "reasons": ["solidworks_not_running"],
                "lb26001_006_direct_guard": {
                    "required": True,
                    "allowed": False,
                    "status": "blocked_by_lb26001_006_direct_guard",
                    "real_cad_allowed_now": False,
                    "automatic_restart_allowed": False,
                    "manual_recovery_required": True,
                },
            },
        )
    proof = _write_json(
        root / "acceptance_proof.json",
        {
            "base": PRIMARY_BASE,
            "status": "blocked_by_006",
            "pass": False,
            "blocking_issue_keys": ["ui_gate_not_pass"],
            "run_dir": None,
        },
    )
    lifecycle = _write_json(
        root / "lifecycle.json",
        {
            "status": "fail",
            "pass": False,
            "blocking_issue_keys": ["final_display_dim_below_reference_floor"],
        },
    )
    preflight = _write_json(
        root / "preflight_summary.json",
        {
            "status": "fail",
            "processed": 0,
            "deliverable_count": 0,
            "readiness_preflight_pass": False,
            "rerun_packet_preflight_pass": False,
            "lb26001_006_real_cad_allowed_now": False,
            "lb26001_006_rerun_packet_build_ready": True,
            "lb26001_006_rerun_packet_blocked_only_by_readiness": True,
            "sw_connection_guard_skipped_due_to_readiness": True,
            "failure_bucket": [
                "lb26001_006_readiness_not_ready",
                "lb26001_006_rerun_packet_blocked_by_readiness",
            ],
            "lb26001_006_ui_evidence": {
                "comparison_image": "006_reference_vs_generated.png",
                "latest_manual_findings": [
                    "006 still fails the staged Drawing Review UI screenshot comparison."
                ],
                "latest_manual_visual_checklist": {
                    "reference_match": False,
                    "view_layout": False,
                },
                "latest_manual_visual_checklist_notes": {
                    "view_layout": "View layout differs from the reference.",
                },
                "latest_manual_required_correction": "Repair 006 before the next locked CAD rerun.",
            },
        },
    )
    return {
        "readiness_path": readiness,
        "rerun_packet_path": packet,
        "requested_status_path": requested,
        "direct_guard_path": direct,
        "acceptance_proof_path": proof,
        "lifecycle_audit_path": lifecycle,
        "staged_preflight_summary_path": preflight,
    }


def _audit(root: Path, **overrides):
    paths = _base_fixture(root, **overrides)
    sources = _source_fixtures(root / "sources")
    return build_gap_audit(**paths, **sources)


def _requirement(payload: dict, key: str) -> dict:
    for item in payload["requirements"]:
        if item["key"] == key:
            return item
    raise AssertionError(f"missing requirement {key}")


def test_readiness_blocked_and_ui_matrix_incomplete_blocks_real_landing() -> None:
    with TemporaryDirectory() as tmp:
        payload = _audit(Path(tmp))

    assert payload["status"] == "blocked_by_solidworks_readiness"
    assert payload["ready_to_start_locked_006_cad"] is False
    assert payload["real_cad_allowed_now"] is False
    assert payload["manual_solidworks_recovery_required"] is True
    assert payload["automatic_restart_allowed"] is False
    assert payload["staged_preflight_no_cad_started"] is True
    assert payload["staged_preflight_packet_build_ready"] is True
    assert payload["staged_preflight_packet_blocked_only_by_readiness"] is True
    assert "lb26001_006_rerun_packet_blocked_by_readiness" in payload["staged_preflight_failure_bucket"]
    assert payload["staged_preflight_comparison_image"] == "006_reference_vs_generated.png"
    assert payload["staged_preflight_latest_manual_findings"] == [
        "006 still fails the staged Drawing Review UI screenshot comparison."
    ]
    assert payload["staged_preflight_ui_evidence"]["latest_manual_visual_checklist"]["reference_match"] is False
    assert payload["staged_preflight_ui_evidence"]["latest_manual_visual_checklist_notes"]["view_layout"] == (
        "View layout differs from the reference."
    )
    assert payload["staged_preflight_latest_manual_required_correction"] == (
        "Repair 006 before the next locked CAD rerun."
    )
    assert payload["six_requested_drawings_accepted"] is False
    assert payload["six_requested_drawings_all_currently_unqualified"] is True
    assert _requirement(payload, "direct_006_real_cad_smoke_guard_blocks_when_not_ready")["pass"] is True
    preflight_req = _requirement(payload, "staged_preflight_skips_sw_connection_when_readiness_blocked")
    assert preflight_req["pass"] is True
    assert preflight_req["evidence"]["no_cad_started"] is True
    assert _requirement(payload, "six_drawing_application_ui_review_complete")["pass"] is False
    assert PRIMARY_BASE in _requirement(payload, "six_drawing_application_ui_review_complete")["evidence"]["incomplete_bases"]
    primary_ui = next(item for item in payload["per_drawing_ui_review_matrix"] if item["base"] == PRIMARY_BASE)
    assert primary_ui["comparison_image"] == "006_reference_vs_generated.png"
    assert primary_ui["manual_visual_checklist_failed_items"] == ["reference_match", "display_dimensions"]
    assert primary_ui["latest_manual_visual_checklist"]["reference_match"] is False
    assert primary_ui["latest_manual_findings"] == [
        "006 still fails the Drawing Review UI screenshot comparison."
    ]


def test_missing_direct_guard_report_is_not_proven() -> None:
    with TemporaryDirectory() as tmp:
        payload = _audit(Path(tmp), include_direct_guard=False)

    req = _requirement(payload, "direct_006_real_cad_smoke_guard_blocks_when_not_ready")
    assert req["pass"] is False
    assert req["status"] == "missing"
    assert "direct_006_real_cad_smoke_guard_blocks_when_not_ready" in payload["critical_failure_keys"]


def test_api_only_pass_count_cannot_accept_without_per_drawing_ui_screenshots() -> None:
    with TemporaryDirectory() as tmp:
        payload = _audit(Path(tmp), api_pass_count=len(REQUESTED_BASES))

    assert payload["six_requested_drawings_accepted"] is False
    assert payload["api_only_acceptance_allowed"] is False
    api_req = _requirement(payload, "api_only_success_cannot_accept_requested_drawings")
    ui_req = _requirement(payload, "six_drawing_application_ui_review_complete")
    assert api_req["pass"] is False
    assert api_req["evidence"]["api_only_pass_claim_detected"] is True
    assert ui_req["pass"] is False


def test_latest_staged_preflight_summary_discovers_packet_ready_readiness_bucket() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        paths = _base_fixture(root)
        paths.pop("staged_preflight_summary_path")
        sources = _source_fixtures(root / "sources")
        stale = _write_json(
            root / "drw_output" / "staged_validation" / "LB26001_006_readiness_preflight_old" / "summary.json",
            {
                "status": "fail",
                "processed": 0,
                "deliverable_count": 0,
                "readiness_preflight_pass": False,
                "rerun_packet_preflight_pass": False,
                "lb26001_006_real_cad_allowed_now": False,
                "lb26001_006_rerun_packet_build_ready": False,
                "lb26001_006_rerun_packet_blocked_only_by_readiness": False,
                "sw_connection_guard_skipped_due_to_readiness": True,
                "failure_bucket": ["stale"],
            },
        )
        latest = _write_json(
            root
            / "drw_output"
            / "staged_validation"
            / "LB26001_006_packet_ready_readiness_bucket_20260624"
            / "summary.json",
            {
                "status": "fail",
                "processed": 0,
                "deliverable_count": 0,
                "readiness_preflight_pass": False,
                "rerun_packet_preflight_pass": False,
                "lb26001_006_real_cad_allowed_now": False,
                "lb26001_006_rerun_packet_build_ready": True,
                "lb26001_006_rerun_packet_blocked_only_by_readiness": True,
                "sw_connection_guard_skipped_due_to_readiness": True,
                "failure_bucket": ["lb26001_006_rerun_packet_blocked_by_readiness"],
            },
        )
        os.utime(stale, (1, 1))
        os.utime(latest, (2, 2))
        old_repo_root = gap_mod.REPO_ROOT
        try:
            gap_mod.REPO_ROOT = root
            payload = build_gap_audit(**paths, **sources)
        finally:
            gap_mod.REPO_ROOT = old_repo_root

    assert payload["staged_preflight_summary_path"].endswith(
        "LB26001_006_packet_ready_readiness_bucket_20260624\\summary.json"
    ) or payload["staged_preflight_summary_path"].endswith(
        "LB26001_006_packet_ready_readiness_bucket_20260624/summary.json"
    )
    assert payload["staged_preflight_no_cad_started"] is True
    assert payload["staged_preflight_packet_build_ready"] is True
    assert payload["staged_preflight_packet_blocked_only_by_readiness"] is True


if __name__ == "__main__":
    test_readiness_blocked_and_ui_matrix_incomplete_blocks_real_landing()
    test_missing_direct_guard_report_is_not_proven()
    test_api_only_pass_count_cannot_accept_without_per_drawing_ui_screenshots()
    test_latest_staged_preflight_summary_discovers_packet_ready_readiness_bucket()
    print("PASS test_v4_2_lb26001_006_real_landing_gap_audit")
