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
) -> dict[str, Path]:
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
    }
    final = {
        "release_log": root / "release_log_v3_0.md",
        "visual_audit_report": root / "visual_audit_report_v3_0.xlsx",
        "exe_ui_robot_result": root / "exe_ui_robot_result_v3_0.json",
        "stability_20min_mock": root / "stability_20min_mock_v3_0.json",
        "stability_2h_ui": root / "stability_2h_ui_v3_0.json",
    }
    if final_artifacts:
        for path in final.values():
            _write_file(path)
    paths["final_artifacts"] = final  # type: ignore[assignment]
    return paths


def _build(paths: dict[str, Path]) -> dict:
    return build_product_evidence_gate(
        stability_gate_path=paths["stability"],
        readiness_path=paths["readiness"],
        reference_proof_path=paths["reference"],
        regeneration_gate_path=paths["regeneration"],
        acceptance_proof_path=paths["acceptance"],
        requested_status_path=paths["requested"],
        issue_schema_validation_path=paths["issue_schema"],
        normalized_issue_schema_validation_path=paths["normalized_issue_schema"],
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
    test_product_evidence_gate_blocks_expansion_when_006_ui_acceptance_fails()
    test_product_evidence_gate_allows_ref6_expansion_only_after_006_passes()
    test_product_evidence_gate_blocks_release_when_final_artifacts_are_missing()
    test_product_evidence_gate_blocks_release_when_raw_issue_schema_fails()
    test_product_evidence_gate_tool_is_file_only()
    print("PASS test_v4_4_product_evidence_gate")
