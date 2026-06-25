from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.validation.product_evidence_gate_v4_4 import BASE, DEPENDENT_BASES, build_product_evidence_gate


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _write_file(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"ok")
    return path


def _write_final_artifact(path: Path, key: str) -> Path:
    if key == "exe_ui_robot_result":
        return _write_json(path, {"mode": "windows_exe_ui_robot", "pass": True})
    if key == "stability_20min_mock":
        return _write_json(path, {"mode": "source_qt_mock_stability", "pass": True, "duration_observed_s": 1201.0})
    if key == "stability_2h_ui":
        return _write_json(path, {"mode": "windows_exe_navigation_stability", "pass": True, "duration_observed_s": 7201.0})
    return _write_file(path)


def _fixture(
    root: Path,
    *,
    readiness_ready: bool = True,
    regeneration_pass: bool = True,
    acceptance_pass: bool = True,
    requested_pass: bool = True,
    final_artifacts: bool = True,
    raw_issue_schema_pass: bool = True,
    normalized_issue_schema_pass: bool = True,
    visual_audit_schema_gap_pass: bool | None = None,
    rerun_packet_build_ready: bool = True,
    rerun_packet_real_cad_allowed_now: bool | None = None,
) -> dict[str, Path]:
    gap_pass = (
        bool(raw_issue_schema_pass and normalized_issue_schema_pass and final_artifacts)
        if visual_audit_schema_gap_pass is None
        else visual_audit_schema_gap_pass
    )
    packet_real_cad_allowed = (
        bool(rerun_packet_build_ready and readiness_ready)
        if rerun_packet_real_cad_allowed_now is None
        else rerun_packet_real_cad_allowed_now
    )
    packet_status = (
        "offline_prerequisites_missing"
        if not rerun_packet_build_ready
        else "ready_for_locked_006_rerun"
        if packet_real_cad_allowed
        else "blocked_by_solidworks_readiness"
    )
    paths = {
        "stability": _write_json(
            root / "stability.json",
            {
                "status": "pass",
                "pass": True,
                "warning_reasons": [],
                "entrypoint_summary": {
                    "unguarded_or_unknown_count": 0,
                    "ui_thread_direct_risk_count": 0,
                    "service_direct_risk_count": 0,
                    "system_health_ui_thread_direct_probe_count": 0,
                },
            },
        ),
        "readiness": _write_json(
            root / "readiness.json",
            {
                "status": "ready" if readiness_ready else "blocked",
                "ready_to_start_locked_006_cad": readiness_ready,
                "blocking_issue_keys": [] if readiness_ready else ["solidworks_not_running"],
            },
        ),
        "reference": _write_json(
            root / "reference.json",
            {
                "base": BASE,
                "pass": True,
                "status": "plan_proof_pass_requires_locked_cad_run",
                "report_is_drawing_acceptance_evidence": False,
                "api_only_acceptance_allowed": False,
                "dimension_summary": {"count": 12},
            },
        ),
        "rerun_packet": _write_json(
            root / "rerun_packet.json",
            {
                "schema": "sw_drawing_studio.lb26001_006_rerun_packet.v4_2",
                "base": BASE,
                "status": packet_status,
                "pass": False,
                "report_is_acceptance_evidence": False,
                "packet_build_ready": rerun_packet_build_ready,
                "real_cad_allowed_now": packet_real_cad_allowed,
                "readiness_ready": readiness_ready,
                "readiness_status": "ready" if readiness_ready else "blocked",
                "offline_prerequisite_missing_keys": []
                if rerun_packet_build_ready
                else ["generator_repair_signatures_present"],
                "api_only_acceptance_allowed": False,
                "application_ui_screenshot_is_final_gate": True,
                "source_signatures": {
                    "generator": {
                        "pass": rerun_packet_build_ready,
                        "missing_signatures": []
                        if rerun_packet_build_ready
                        else ["reference_callout_review_plan_required"],
                    },
                    "cad_job_worker": {"pass": True, "missing_signatures": []},
                },
            },
        ),
        "regeneration": _write_json(
            root / "regeneration.json",
            {
                "base": BASE,
                "pass": regeneration_pass,
                "status": "regeneration_evidence_pass_requires_application_ui_screenshot_review" if regeneration_pass else "blocked_by_missing_fresh_006_run",
                "run_id": "run006" if regeneration_pass else "",
                "run_dir": str(root / "runs" / "run006") if regeneration_pass else "",
                "report_is_drawing_acceptance_evidence": False,
                "blocking_issue_keys": [] if regeneration_pass else ["explicit_006_run_evidence_source"],
            },
        ),
        "acceptance": _write_json(
            root / "acceptance.json",
            {
                "base": BASE,
                "pass": acceptance_pass,
                "status": "pass" if acceptance_pass else "blocked_by_006",
                "application_ui_screenshot_is_final_gate": True,
                "blocking_issue_keys": [] if acceptance_pass else ["manual_visual_checklist_not_pass"],
                "ui_closure_evidence": {
                    "direct_ui_screenshot_recheck_method_ok": True,
                    "direct_ui_screenshot_recheck_pass": acceptance_pass,
                    "manual_visual_checklist_pass": acceptance_pass,
                    "manual_visual_checklist_failed_items": [] if acceptance_pass else ["display_dimensions"],
                },
            },
        ),
        "requested": _write_json(
            root / "requested.json",
            {
                "pass": requested_pass,
                "status": "pass" if requested_pass else "blocked_by_006",
                "pass_count": 6 if requested_pass else 0,
                "not_pass_count": 0 if requested_pass else 6,
                "primary_acceptance_proof_status": "pass" if requested_pass else "blocked_by_006",
                "per_drawing_ui_review_matrix": [
                    {"base": base, "pass": requested_pass}
                    for base in [BASE, *DEPENDENT_BASES]
                ],
            },
        ),
        "issue_schema": _write_json(
            root / "issue_schema_validation.json",
            {
                "status": "pass" if raw_issue_schema_pass else "fail",
                "pass": raw_issue_schema_pass,
                "issue_count": 10,
                "noncompliant_issue_count": 0 if raw_issue_schema_pass else 7,
                "failure_bucket": [] if raw_issue_schema_pass else ["vision_issue_schema_incomplete"],
            },
        ),
        "normalized_issue_schema": _write_json(
            root / "issue_schema_validation_normalized.json",
            {
                "status": "pass" if normalized_issue_schema_pass else "fail",
                "pass": normalized_issue_schema_pass,
                "issue_count": 10,
                "noncompliant_issue_count": 0 if normalized_issue_schema_pass else 1,
                "failure_bucket": [] if normalized_issue_schema_pass else ["normalized_issue_schema_incomplete"],
            },
        ),
        "visual_audit_schema_gap": _write_json(
            root / "visual_audit_schema_gap_v4_4.json",
            {
                "schema": "sw_drawing_studio.visual_audit_schema_gap.v4_4",
                "status": "pass" if gap_pass else "raw_issue_schema_noncompliant",
                "pass": gap_pass,
                "raw_noncompliant_issue_count": 0 if raw_issue_schema_pass else 7,
                "normalized_noncompliant_issue_count": 0 if normalized_issue_schema_pass else 1,
                "visual_audit_report_final_present": final_artifacts,
                "visual_audit_full_scope_allowed_now": gap_pass,
                "normalized_supporting_only": True,
                "normalized_cannot_replace_raw": True,
                "blocking_issue_keys": [] if gap_pass else ["raw_issue_schema_pass"],
            },
        ),
    }
    final = {
        "dist_exe": root / "dist" / "sw_drawing_studio.exe",
        "release_log": root / "release_log_v3_0.md",
        "validation_log": root / "validation_log_v3_0.md",
        "ui_acceptance_report": root / "ui_acceptance_report_v3_0.md",
        "exe_ui_robot_result": root / "exe_ui_robot_result_v3_0.json",
        "cad_smoke": root / "cad_smoke_v3_0.json",
        "dimension_validation_smoke": root / "dimension_validation_smoke.json",
        "reference_compare_smoke": root / "reference_compare_smoke.json",
        "reference_comparison_report": root / "drw_output" / "reference_comparison_report_v3_0.xlsx",
        "visual_audit_report": root / "drw_output" / "visual_audit_report_v3_0.xlsx",
        "visual_audit_index": root / "drw_output" / "visual_audit_index.json",
        "stability_20min_mock": root / "stability_20min_mock_v3_0.json",
        "stability_2h_ui": root / "stability_2h_ui_v3_0.json",
    }
    if final_artifacts:
        for key, path in final.items():
            _write_final_artifact(path, key)
    paths["final_artifacts"] = final  # type: ignore[assignment]
    return paths


def _build(paths: dict[str, Path]) -> dict:
    return build_product_evidence_gate(
        stability_gate_path=paths["stability"],
        readiness_path=paths["readiness"],
        reference_proof_path=paths["reference"],
        rerun_packet_path=paths["rerun_packet"],
        regeneration_gate_path=paths["regeneration"],
        acceptance_proof_path=paths["acceptance"],
        requested_status_path=paths["requested"],
        issue_schema_validation_path=paths["issue_schema"],
        normalized_issue_schema_validation_path=paths["normalized_issue_schema"],
        visual_audit_schema_gap_path=paths["visual_audit_schema_gap"],
        final_artifacts=paths["final_artifacts"],  # type: ignore[arg-type]
    )


def test_product_evidence_gate_can_pass_complete_fixture() -> None:
    with TemporaryDirectory() as tmp:
        result = _build(_fixture(Path(tmp)))

        assert result["pass"] is True
        assert result["status"] == "pass"
        assert result["release_ready"] is True
        assert result["allowed_actions"]["full_129_allowed"] is True
        assert not result["blocking_issue_keys"]


def test_product_evidence_gate_blocks_when_solidworks_readiness_is_blocked() -> None:
    with TemporaryDirectory() as tmp:
        result = _build(_fixture(Path(tmp), readiness_ready=False))

        assert result["pass"] is False
        assert result["status"] == "blocked_by_solidworks_readiness"
        assert result["allowed_actions"]["locked_006_cad_rerun_allowed_now"] is False
        assert result["allowed_actions"]["expand_007_008_009_015_022_allowed"] is False
        assert result["allowed_actions"]["lb26001_36_allowed"] is False
        assert result["allowed_actions"]["full_129_allowed"] is False
        assert "solidworks_readiness_for_006" in set(result["blocking_issue_keys"])
        assert "lb26001_006_rerun_packet_ready" not in set(result["blocking_issue_keys"])
        assert "lb26001_006_rerun_packet_readiness_state_current" not in set(result["blocking_issue_keys"])


def test_product_evidence_gate_blocks_locked_006_when_rerun_packet_offline_missing() -> None:
    with TemporaryDirectory() as tmp:
        result = _build(_fixture(Path(tmp), rerun_packet_build_ready=False))

        assert result["pass"] is False
        assert result["status"] == "blocked_by_006_rerun_packet"
        assert result["allowed_actions"]["locked_006_cad_rerun_allowed_now"] is False
        assert result["allowed_actions"]["full_129_allowed"] is False
        assert "lb26001_006_rerun_packet_ready" in set(result["blocking_issue_keys"])
        check = next(item for item in result["checks"] if item["key"] == "lb26001_006_rerun_packet_ready")
        assert check["details"]["offline_prerequisite_missing_keys"] == ["generator_repair_signatures_present"]
        assert check["details"]["source_signature_summary"]["generator"]["pass"] is False


def test_product_evidence_gate_blocks_locked_006_when_rerun_packet_state_is_stale() -> None:
    with TemporaryDirectory() as tmp:
        result = _build(_fixture(Path(tmp), readiness_ready=True, rerun_packet_real_cad_allowed_now=False))

        assert result["pass"] is False
        assert result["status"] == "blocked_by_006_rerun_packet"
        assert result["allowed_actions"]["locked_006_cad_rerun_allowed_now"] is False
        assert result["allowed_actions"]["full_129_allowed"] is False
        assert "lb26001_006_rerun_packet_readiness_state_current" in set(result["blocking_issue_keys"])
        check = next(
            item for item in result["checks"] if item["key"] == "lb26001_006_rerun_packet_readiness_state_current"
        )
        assert check["details"]["readiness_ok"] is True
        assert check["details"]["expected_packet_status"] == "ready_for_locked_006_rerun"


def test_product_evidence_gate_blocks_expansion_when_006_ui_acceptance_fails() -> None:
    with TemporaryDirectory() as tmp:
        result = _build(_fixture(Path(tmp), acceptance_pass=False, requested_pass=False))

        assert result["pass"] is False
        assert result["status"] == "blocked_by_006_application_ui_review"
        assert result["do_not_expand_007_008_009_015_022"] is True
        assert result["allowed_actions"]["expand_007_008_009_015_022_allowed"] is False
        assert "application_ui_006_acceptance_pass" in set(result["blocking_issue_keys"])


def test_product_evidence_gate_allows_ref6_expansion_only_after_006_passes() -> None:
    with TemporaryDirectory() as tmp:
        result = _build(_fixture(Path(tmp), acceptance_pass=True, requested_pass=False))

        assert result["pass"] is False
        assert result["status"] == "blocked_by_requested_ref6_ui_review"
        assert result["allowed_actions"]["expand_007_008_009_015_022_allowed"] is True
        assert result["allowed_actions"]["requested_ref6_complete"] is False
        assert result["allowed_actions"]["lb26001_36_allowed"] is False
        assert result["allowed_actions"]["full_129_allowed"] is False


def test_product_evidence_gate_blocks_release_when_final_artifacts_are_missing() -> None:
    with TemporaryDirectory() as tmp:
        result = _build(_fixture(Path(tmp), final_artifacts=False))

        assert result["pass"] is False
        assert result["status"] == "warning_not_release_ready"
        assert result["release_ready"] is False
        assert result["allowed_actions"]["full_129_allowed"] is False
        assert "final_release_artifacts_present" in set(result["blocking_issue_keys"])


def test_product_evidence_gate_blocks_release_when_raw_issue_schema_fails() -> None:
    with TemporaryDirectory() as tmp:
        result = _build(_fixture(Path(tmp), raw_issue_schema_pass=False, normalized_issue_schema_pass=True))

        assert result["pass"] is False
        assert result["status"] == "warning_not_release_ready"
        assert result["release_ready"] is False
        assert result["allowed_actions"]["full_129_allowed"] is False
        assert "visual_audit_schema_proof_pass" in set(result["blocking_issue_keys"])
        check = next(item for item in result["checks"] if item["key"] == "visual_audit_schema_proof_pass")
        assert check["details"]["normalized_proof_is_supporting_only"] is True
        assert check["details"]["visual_audit_schema_gap"]["pass"] is False
        assert check["details"]["visual_audit_schema_gap"]["normalized_supporting_only"] is True


def test_product_evidence_gate_blocks_release_when_visual_audit_schema_gap_is_missing() -> None:
    with TemporaryDirectory() as tmp:
        paths = _fixture(Path(tmp))
        paths["visual_audit_schema_gap"].unlink()

        result = _build(paths)

        assert result["pass"] is False
        assert result["status"] == "warning_not_release_ready"
        assert result["release_ready"] is False
        assert result["allowed_actions"]["full_129_allowed"] is False
        assert "visual_audit_schema_proof_pass" in set(result["blocking_issue_keys"])
        check = next(item for item in result["checks"] if item["key"] == "visual_audit_schema_proof_pass")
        assert check["details"]["visual_audit_schema_gap"]["pass"] is None


def test_product_evidence_gate_blocks_release_when_exe_stability_is_not_proven() -> None:
    with TemporaryDirectory() as tmp:
        paths = _fixture(Path(tmp))
        _write_json(paths["final_artifacts"]["stability_2h_ui"], {"mode": "windows_exe_navigation_stability", "pass": True, "duration_observed_s": 7100.0})  # type: ignore[index]

        result = _build(paths)

        assert result["pass"] is False
        assert result["status"] == "warning_not_release_ready"
        assert result["release_ready"] is False
        assert result["allowed_actions"]["full_129_allowed"] is False
        assert "exe_ui_and_stability_proof_pass" in set(result["blocking_issue_keys"])


def test_product_evidence_gate_rejects_source_ui_robot_as_exe_evidence() -> None:
    with TemporaryDirectory() as tmp:
        paths = _fixture(Path(tmp))
        _write_json(paths["final_artifacts"]["exe_ui_robot_result"], {"mode": "source_qt_ui_robot", "pass": True})  # type: ignore[index]

        result = _build(paths)

        assert result["pass"] is False
        assert result["status"] == "warning_not_release_ready"
        assert result["allowed_actions"]["full_129_allowed"] is False
        assert "exe_ui_and_stability_proof_pass" in set(result["blocking_issue_keys"])


def test_product_evidence_gate_tool_is_file_only() -> None:
    source = Path("tools/validation/product_evidence_gate_v4_4.py").read_text(encoding="utf-8")
    forbidden = [
        "win32com",
        "pythoncom",
        "GetActiveObject",
        "Dispatch(",
        "OpenDoc6",
        "subprocess.run",
        "QProcess",
    ]
    for token in forbidden:
        assert token not in source


if __name__ == "__main__":
    test_product_evidence_gate_can_pass_complete_fixture()
    test_product_evidence_gate_blocks_when_solidworks_readiness_is_blocked()
    test_product_evidence_gate_blocks_locked_006_when_rerun_packet_offline_missing()
    test_product_evidence_gate_blocks_locked_006_when_rerun_packet_state_is_stale()
    test_product_evidence_gate_blocks_expansion_when_006_ui_acceptance_fails()
    test_product_evidence_gate_allows_ref6_expansion_only_after_006_passes()
    test_product_evidence_gate_blocks_release_when_final_artifacts_are_missing()
    test_product_evidence_gate_blocks_release_when_raw_issue_schema_fails()
    test_product_evidence_gate_blocks_release_when_visual_audit_schema_gap_is_missing()
    test_product_evidence_gate_blocks_release_when_exe_stability_is_not_proven()
    test_product_evidence_gate_rejects_source_ui_robot_as_exe_evidence()
    test_product_evidence_gate_tool_is_file_only()
    print("PASS test_v4_4_product_evidence_gate")
