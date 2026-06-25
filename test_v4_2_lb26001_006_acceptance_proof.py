import json
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.validation.lb26001_006_acceptance_proof_v4_2 import (
    BASE,
    DEFAULT_DIRECT_UI_SCREENSHOT_RECHECK,
    build_acceptance_proof,
)


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _staged(path: Path, *, passed: bool, lifecycle_pass: bool | None = None, write_lifecycle_report: bool = True) -> Path:
    lifecycle_pass = passed if lifecycle_pass is None else lifecycle_pass
    case_dir = path.parent / "01_LB26001-A-04-006"
    lifecycle_report = case_dir / "displaydim_lifecycle_audit.json"
    if write_lifecycle_report:
        _write_json(
            lifecycle_report,
            {
                "schema": "sw_drawing_studio.lb26001_006_displaydim_lifecycle_audit.v4_2",
                "base": BASE,
                "status": "pass" if lifecycle_pass else "fail",
                "pass": lifecycle_pass,
                "blocking_issue_keys": [] if lifecycle_pass else ["final_display_dim_below_reference_floor"],
            },
        )
    return _write_json(
        path,
        {
            "stage": "LB26001_006",
            "status": "pass" if passed else "need_review",
            "pass": passed,
            "processed": 1,
            "total": 1,
            "cases": [
                {
                    "part_name": BASE,
                    "status": "pass" if passed else "need_review",
                    "case_dir": str(case_dir),
                    "run_dir": str(path.parent / "runs" / "fresh"),
                    "cad_pass": True,
                    "dimension_pass": True,
                    "reference_pass": True,
                    "reference_style_pass": passed,
                    "displaydim_lifecycle_required": True,
                    "displaydim_lifecycle_pass": lifecycle_pass,
                    "displaydim_lifecycle_report": str(lifecycle_report),
                    "displaydim_lifecycle_blocking_issue_keys": [] if lifecycle_pass else ["final_display_dim_below_reference_floor"],
                    "vision_qc_v6_pass": passed,
                    "reference_compare_v4_pass": passed,
                    "deliverable": passed and lifecycle_pass,
                }
            ],
        },
    )


def _ui_gate(path: Path, *, passed: bool, manual_binding_pass: bool = True) -> Path:
    return _write_json(
        path,
        {
            "schema": "sw_drawing_studio.ui_visual_review_gate.v4",
            "status": "pass" if passed else "need_review",
            "pass": passed,
            "ui_report_entries_all_pass": True,
            "manual_review_entries_all_pass": manual_binding_pass,
            "vision_qc_v6_all_pass": passed,
            "reference_compare_v4_all_pass": passed,
            "entries": [
                {
                    "base": BASE,
                    "ui_report_entry_pass": True,
                    "manual_review_entry_screenshot_pass": manual_binding_pass,
                    "manual_review_screenshot_matches_ui_report_entry": manual_binding_pass,
                    "vision_qc_v6_visual_acceptance_pass": passed,
                    "reference_compare_v4_pass": passed,
                    "generated_png_source_required": True,
                    "generated_png_source_pass": True,
                    "reasons": [] if passed else ["display_dim_lower_than_reference"],
                }
            ],
        },
    )


def _acceptance_gate(
    path: Path,
    *,
    passed: bool,
    generated_png_source_pass: bool = True,
    include_manual_checklist: bool = True,
) -> Path:
    return _write_json(
        path,
        {
            "schema": "sw_drawing_studio.lb26001_acceptance_gate.v4_2",
            "status": "pass" if passed else "blocked_by_006",
            "pass": passed,
            "primary_pass": passed,
            "base_results": [
                {
                    "base": BASE,
                    "pass": passed,
                    "vision_qc_v6_visual_acceptance_pass": passed,
                    "reference_compare_v4_pass": passed,
                    "source_ui_report_application_ui_ok": True,
                    "ui_screenshot_file_count": 1,
                    "ui_screenshot_files": [str(path.parent / "screenshots" / f"{BASE}.png")],
                    "manual_case_status_pass": passed,
                    "manual_visual_checklist_required": include_manual_checklist,
                    "manual_visual_checklist_pass": passed,
                    "manual_visual_checklist_missing_items": [] if include_manual_checklist else ["reference_match"],
                    "manual_visual_checklist_failed_items": [],
                    "manual_visual_checklist_not_passed_items": [] if include_manual_checklist else ["reference_match"],
                    "generated_png_source_required": True,
                    "generated_png_source_pass": generated_png_source_pass,
                    "generated_png_source_evidence": {
                        "strict_source_pass": generated_png_source_pass,
                        "under_run_dir": generated_png_source_pass,
                    },
                    "reasons": [] if passed else ["ui_screenshot_visual_acceptance_not_passed"],
                }
            ],
            "reasons": [] if passed else ["vision_qc_v6_with_ui_review_not_pass"],
            "issues": [],
        },
    )


def _direct_recheck(path: Path, *, screenshot: Path, passed: bool) -> Path:
    return _write_json(
        path,
        {
            "schema": "sw_drawing_studio.codex_direct_ui_screenshot_recheck.v4_2",
            "overall_status": "PASS" if passed else "FAIL",
            "review_method": "direct_application_drawing_review_ui_screenshot_visual_check",
            "api_is_not_final_judgement": True,
            "ui_screenshot_review_is_final_gate": True,
            "cases": [
                {
                    "base": BASE,
                    "status": "PASS" if passed else "FAIL",
                    "screenshot": str(screenshot),
                    "visual_findings": [] if passed else ["Direct UI screenshot still differs from the reference."],
                }
            ],
        },
    )


def test_lb26001_006_acceptance_proof_passes_when_all_ui_backed_gates_pass() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        result = build_acceptance_proof(
            staged_summary_path=_staged(root / "summary.json", passed=True),
            ui_gate_path=_ui_gate(root / "ui_gate.json", passed=True),
            screenshot_binding_gate_path=_ui_gate(root / "binding_gate.json", passed=True),
            acceptance_gate_path=_acceptance_gate(root / "acceptance.json", passed=True),
            supplemental_checklist_gate_path=root / "missing_supplemental_checklist.json",
            out_json=root / "proof.json",
            out_md=root / "proof.md",
        )

    assert result["status"] == "pass"
    assert result["pass"] is True
    assert result["report_is_acceptance_evidence"] is True
    assert result["api_only_acceptance_allowed"] is False
    assert result["blocking_issue_keys"] == []


def test_lb26001_006_acceptance_proof_blocks_quality_fail_even_with_ui_screenshot() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        result = build_acceptance_proof(
            staged_summary_path=_staged(root / "summary.json", passed=False),
            ui_gate_path=_ui_gate(root / "ui_gate.json", passed=False),
            screenshot_binding_gate_path=_ui_gate(root / "binding_gate.json", passed=False, manual_binding_pass=True),
            acceptance_gate_path=_acceptance_gate(root / "acceptance.json", passed=False),
            supplemental_checklist_gate_path=root / "missing_supplemental_checklist.json",
        )

    keys = set(result["blocking_issue_keys"])
    assert result["status"] == "blocked_by_006"
    assert result["pass"] is False
    assert "staged_case_not_deliverable" in keys
    assert "v6_with_ui_not_pass" in keys
    assert "reference_compare_v4_with_ui_not_pass" in keys
    assert "acceptance_gate_not_pass" in keys
    assert "ui_report_entry_not_pass" not in keys
    assert "manual_review_screenshot_not_bound" not in keys


def test_lb26001_006_acceptance_proof_blocks_lifecycle_report_not_pass_even_with_ui_pass() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        result = build_acceptance_proof(
            staged_summary_path=_staged(root / "summary.json", passed=True, lifecycle_pass=False),
            ui_gate_path=_ui_gate(root / "ui_gate.json", passed=True),
            screenshot_binding_gate_path=_ui_gate(root / "binding_gate.json", passed=True),
            acceptance_gate_path=_acceptance_gate(root / "acceptance.json", passed=True),
            supplemental_checklist_gate_path=root / "missing_supplemental_checklist.json",
        )

    keys = set(result["blocking_issue_keys"])
    staged = result["staged_evidence"]
    assert result["pass"] is False
    assert staged["displaydim_lifecycle_required"] is True
    assert staged["displaydim_lifecycle_report_exists"] is True
    assert staged["displaydim_lifecycle_case_pass"] is False
    assert staged["displaydim_lifecycle_report_pass"] is False
    assert "displaydim_lifecycle_not_pass" in keys
    assert "final_display_dim_below_reference_floor" in staged["displaydim_lifecycle_blocking_issue_keys"]


def test_lb26001_006_acceptance_proof_blocks_missing_lifecycle_report_even_with_summary_pass() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        result = build_acceptance_proof(
            staged_summary_path=_staged(root / "summary.json", passed=True, write_lifecycle_report=False),
            ui_gate_path=_ui_gate(root / "ui_gate.json", passed=True),
            screenshot_binding_gate_path=_ui_gate(root / "binding_gate.json", passed=True),
            acceptance_gate_path=_acceptance_gate(root / "acceptance.json", passed=True),
            supplemental_checklist_gate_path=root / "missing_supplemental_checklist.json",
        )

    keys = set(result["blocking_issue_keys"])
    staged = result["staged_evidence"]
    assert result["pass"] is False
    assert staged["displaydim_lifecycle_required"] is True
    assert staged["displaydim_lifecycle_report_exists"] is False
    assert "displaydim_lifecycle_report_missing" in keys
    assert "displaydim_lifecycle_not_pass" in keys


def test_lb26001_006_acceptance_proof_uses_supplemental_checklist_without_overriding_fail() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        stale_acceptance = _write_json(
            root / "stale_acceptance.json",
            {
                "schema": "sw_drawing_studio.lb26001_acceptance_gate.v4_2",
                "status": "blocked_by_006",
                "pass": False,
                "primary_pass": False,
                "base_results": [
                    {
                        "base": BASE,
                        "pass": False,
                        "vision_qc_v6_visual_acceptance_pass": False,
                        "reference_compare_v4_pass": False,
                        "source_ui_report_application_ui_ok": False,
                        "ui_screenshot_file_count": 1,
                        "ui_screenshot_files": [str(root / "screenshots" / f"{BASE}.png")],
                        "manual_case_status_pass": False,
                        "manual_visual_checklist_required": False,
                        "manual_visual_checklist_pass": False,
                        "generated_png_source_required": True,
                        "generated_png_source_pass": False,
                        "reasons": ["ui_screenshot_visual_acceptance_not_passed"],
                    }
                ],
                "reasons": ["vision_qc_v6_with_ui_review_not_pass"],
                "issues": [],
            },
        )
        supplemental = _write_json(
            root / "supplemental_checklist.json",
            {
                "schema": "sw_drawing_studio.lb26001_acceptance_gate.v4_2",
                "status": "blocked_by_006",
                "pass": False,
                "primary_pass": False,
                "base_results": [
                    {
                        "base": BASE,
                        "pass": False,
                        "vision_qc_v6_visual_acceptance_pass": False,
                        "reference_compare_v4_pass": False,
                        "source_ui_report": str(root / "drawing_visual_review_report.json"),
                        "source_ui_report_application_ui_ok": True,
                        "ui_screenshot_file_count": 1,
                        "ui_screenshot_files": [str(root / "screenshots" / f"{BASE}.png")],
                        "manual_case_status_pass": False,
                        "manual_visual_checklist_required": True,
                        "manual_visual_checklist_pass": False,
                        "manual_visual_checklist_missing_items": [],
                        "manual_visual_checklist_failed_items": ["reference_match"],
                        "manual_visual_checklist_not_passed_items": ["reference_match"],
                        "generated_png_source_required": True,
                        "generated_png_source_pass": True,
                        "generated_png_source_evidence": {"strict_source_pass": True, "under_run_dir": True},
                        "reasons": ["ui_screenshot_visual_acceptance_not_passed"],
                    }
                ],
                "reasons": ["manual_visual_checklist_failed"],
                "issues": [],
            },
        )

        result = build_acceptance_proof(
            staged_summary_path=_staged(root / "summary.json", passed=False),
            ui_gate_path=_ui_gate(root / "ui_gate.json", passed=False),
            screenshot_binding_gate_path=_ui_gate(root / "binding_gate.json", passed=False, manual_binding_pass=True),
            acceptance_gate_path=stale_acceptance,
            supplemental_checklist_gate_path=supplemental,
        )

    keys = set(result["blocking_issue_keys"])
    ui = result["ui_closure_evidence"]
    assert result["pass"] is False
    assert ui["source_ui_report_application_ui_ok"] is True
    assert ui["generated_png_source_pass"] is True
    assert ui["manual_visual_checklist_required"] is True
    assert ui["manual_visual_checklist_failed_items"] == ["reference_match"]
    assert "application_ui_source_report_invalid" not in keys
    assert "generated_png_source_not_current_run" not in keys
    assert "manual_visual_checklist_not_pass" in keys
    assert "acceptance_gate_not_pass" in keys


def test_lb26001_006_acceptance_proof_blocks_manual_screenshot_mismatch() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        result = build_acceptance_proof(
            staged_summary_path=_staged(root / "summary.json", passed=True),
            ui_gate_path=_ui_gate(root / "ui_gate.json", passed=True),
            screenshot_binding_gate_path=_ui_gate(root / "binding_gate.json", passed=True, manual_binding_pass=False),
            acceptance_gate_path=_acceptance_gate(root / "acceptance.json", passed=True),
            supplemental_checklist_gate_path=root / "missing_supplemental_checklist.json",
        )

    keys = set(result["blocking_issue_keys"])
    assert result["status"] == "need_review"
    assert result["pass"] is False
    assert "manual_review_screenshot_not_bound" in keys
    assert "v6_with_ui_not_pass" not in keys
    assert "reference_compare_v4_with_ui_not_pass" not in keys


def test_lb26001_006_acceptance_proof_blocks_missing_manual_visual_checklist() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        result = build_acceptance_proof(
            staged_summary_path=_staged(root / "summary.json", passed=True),
            ui_gate_path=_ui_gate(root / "ui_gate.json", passed=True),
            screenshot_binding_gate_path=_ui_gate(root / "binding_gate.json", passed=True),
            acceptance_gate_path=_acceptance_gate(
                root / "acceptance.json",
                passed=True,
                include_manual_checklist=False,
            ),
            supplemental_checklist_gate_path=root / "missing_supplemental_checklist.json",
        )

    keys = set(result["blocking_issue_keys"])
    assert result["status"] == "need_review"
    assert result["pass"] is False
    assert "manual_visual_checklist_missing" in keys
    assert "acceptance_gate_not_pass" not in keys


def test_lb26001_006_acceptance_proof_blocks_matching_direct_ui_screenshot_fail() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        screenshot = root / "screenshots" / f"{BASE}.png"
        screenshot.parent.mkdir()
        screenshot.write_bytes(b"fake-png")
        result = build_acceptance_proof(
            staged_summary_path=_staged(root / "summary.json", passed=True),
            ui_gate_path=_ui_gate(root / "ui_gate.json", passed=True),
            screenshot_binding_gate_path=_ui_gate(root / "binding_gate.json", passed=True),
            acceptance_gate_path=_acceptance_gate(root / "acceptance.json", passed=True),
            supplemental_checklist_gate_path=root / "missing_supplemental_checklist.json",
            direct_ui_screenshot_recheck_path=_direct_recheck(root / "direct_recheck.json", screenshot=screenshot, passed=False),
        )

    keys = set(result["blocking_issue_keys"])
    ui = result["ui_closure_evidence"]
    assert result["status"] == "need_review"
    assert result["pass"] is False
    assert "direct_ui_screenshot_recheck_not_pass" in keys
    assert ui["direct_ui_screenshot_recheck_current"] is True
    assert ui["direct_ui_screenshot_recheck_pass"] is False
    assert ui["direct_ui_screenshot_recheck_findings"] == [
        "Direct UI screenshot still differs from the reference."
    ]


def test_lb26001_006_acceptance_proof_ignores_stale_direct_recheck_screenshot() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        current_screenshot = root / "screenshots" / f"{BASE}.png"
        stale_screenshot = root / "screenshots" / "stale.png"
        current_screenshot.parent.mkdir()
        current_screenshot.write_bytes(b"fake-png")
        stale_screenshot.write_bytes(b"old-fake-png")
        result = build_acceptance_proof(
            staged_summary_path=_staged(root / "summary.json", passed=True),
            ui_gate_path=_ui_gate(root / "ui_gate.json", passed=True),
            screenshot_binding_gate_path=_ui_gate(root / "binding_gate.json", passed=True),
            acceptance_gate_path=_acceptance_gate(root / "acceptance.json", passed=True),
            supplemental_checklist_gate_path=root / "missing_supplemental_checklist.json",
            direct_ui_screenshot_recheck_path=_direct_recheck(root / "direct_recheck.json", screenshot=stale_screenshot, passed=False),
        )

    ui = result["ui_closure_evidence"]
    assert result["status"] == "pass"
    assert result["pass"] is True
    assert "direct_ui_screenshot_recheck_not_pass" not in result["blocking_issue_keys"]
    assert ui["direct_ui_screenshot_recheck_current"] is False
    assert ui["direct_ui_screenshot_recheck_pass"] is None


def test_lb26001_006_acceptance_proof_default_direct_recheck_path_is_current_artifact() -> None:
    assert str(DEFAULT_DIRECT_UI_SCREENSHOT_RECHECK).endswith("codex_direct_ui_screenshot_recheck_20260624.json")


def test_lb26001_006_acceptance_proof_discovers_latest_matching_manual_ui_recheck() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        screenshot = root / "screenshots" / f"{BASE}.png"
        screenshot.parent.mkdir()
        screenshot.write_bytes(b"fake-png")
        manual = _write_json(
            root / "manual_visual_judgement_codex_20260624.json",
            {
                "schema": "sw_drawing_studio.manual_visual_judgement.v4_2",
                "overall_status": "FAIL",
                "review_mode": "application_drawing_review_ui_screenshot",
                "api_is_not_final_judgement": True,
                "ui_screenshot_review_is_final_gate": True,
                "entries": [
                    {
                        "base": BASE,
                        "manual_status": "FAIL",
                        "visual_acceptance_pass": False,
                        "ui_screenshot": str(screenshot),
                        "findings": ["Latest application UI screenshot still fails."],
                    }
                ],
            },
        )
        result = build_acceptance_proof(
            staged_summary_path=_staged(root / "summary.json", passed=True),
            ui_gate_path=_ui_gate(root / "ui_gate.json", passed=True),
            screenshot_binding_gate_path=_ui_gate(root / "binding_gate.json", passed=True),
            acceptance_gate_path=_acceptance_gate(root / "acceptance.json", passed=True),
            supplemental_checklist_gate_path=root / "missing_supplemental_checklist.json",
        )

    ui = result["ui_closure_evidence"]
    assert result["status"] == "need_review"
    assert result["pass"] is False
    assert ui["direct_ui_screenshot_recheck"] == str(manual)
    assert ui["direct_ui_screenshot_recheck_current"] is True
    assert ui["direct_ui_screenshot_recheck_pass"] is False
    assert ui["direct_ui_screenshot_recheck_findings"] == [
        "Latest application UI screenshot still fails."
    ]
    assert "direct_ui_screenshot_recheck_not_pass" in result["blocking_issue_keys"]


if __name__ == "__main__":
    test_lb26001_006_acceptance_proof_passes_when_all_ui_backed_gates_pass()
    test_lb26001_006_acceptance_proof_blocks_quality_fail_even_with_ui_screenshot()
    test_lb26001_006_acceptance_proof_blocks_lifecycle_report_not_pass_even_with_ui_pass()
    test_lb26001_006_acceptance_proof_blocks_missing_lifecycle_report_even_with_summary_pass()
    test_lb26001_006_acceptance_proof_uses_supplemental_checklist_without_overriding_fail()
    test_lb26001_006_acceptance_proof_blocks_manual_screenshot_mismatch()
    test_lb26001_006_acceptance_proof_blocks_missing_manual_visual_checklist()
    test_lb26001_006_acceptance_proof_blocks_matching_direct_ui_screenshot_fail()
    test_lb26001_006_acceptance_proof_ignores_stale_direct_recheck_screenshot()
    test_lb26001_006_acceptance_proof_default_direct_recheck_path_is_current_artifact()
    test_lb26001_006_acceptance_proof_discovers_latest_matching_manual_ui_recheck()
    print("PASS test_v4_2_lb26001_006_acceptance_proof")
