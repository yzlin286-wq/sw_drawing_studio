import json
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image, ImageDraw

import tools.validation.lb26001_requested_drawings_status_v4_2 as status_mod
from tools.validation.lb26001_requested_drawings_status_v4_2 import (
    DEFAULT_ACCEPTANCE_GATE,
    DEFAULT_ACCEPTANCE_PROOF,
    DEFAULT_DIRECT_UI_SCREENSHOT_RECHECK,
    build_requested_drawings_status,
)


def _draw_application_ui_screenshot(path: Path) -> Path:
    image = Image.new("RGB", (1600, 950), "#f0f0f0")
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, 0, 1600, 34], fill="#e5e5e5", outline="#c8c8c8")
    draw.rectangle([0, 34, 1600, 84], fill="#eeeeee", outline="#cccccc")
    draw.rectangle([0, 84, 112, 800], fill="#f6f6f6", outline="#cfcfcf")
    draw.rectangle([116, 86, 364, 635], fill="white", outline="#cfcfcf")
    draw.rectangle([368, 86, 1290, 800], fill="#ededed", outline="#cfcfcf")
    draw.rectangle([1294, 86, 1592, 800], fill="white", outline="#cfcfcf")
    draw.rectangle([0, 810, 1600, 948], fill="white", outline="#cfcfcf")
    draw.rectangle([119, 108, 360, 126], fill="#2a8bd6")
    draw.rectangle([470, 130, 820, 640], fill="white", outline="#d0d6dc", width=2)
    draw.rectangle([860, 130, 1210, 640], fill="white", outline="#d0d6dc", width=2)
    draw.line([840, 120, 840, 650], fill="#98abc0", width=2)
    for offset in [0, 390]:
        x0 = 520 + offset
        draw.rectangle([x0, 245, x0 + 210, 325], outline="black", width=2)
        draw.line([x0 - 25, 220, x0 + 250, 220], fill="black", width=1)
        draw.line([x0 + 12, 355, x0 + 200, 355], fill="black", width=1)
    for y in range(835, 930, 22):
        draw.line([20, y, 1580, y], fill="#333333", width=1)
    image.save(path)
    return path


def _acceptance_proof(root: Path, *, passed: bool = True) -> Path:
    proof = root / "acceptance_proof.json"
    proof.write_text(
        json.dumps(
            {
                "schema": "sw_drawing_studio.lb26001_006_acceptance_proof.v4_2",
                "status": "pass" if passed else "blocked_by_006",
                "pass": passed,
                "blocking_issue_keys": [] if passed else ["v6_with_ui_not_pass"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return proof


def test_requested_drawings_status_keeps_ui_fail_and_006_block() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        screenshot = root / "screenshots" / "006.png"
        screenshot_007 = root / "screenshots" / "007.png"
        comparison = root / "comparison" / "006_reference_vs_generated.png"
        screenshot.parent.mkdir()
        comparison.parent.mkdir()
        _draw_application_ui_screenshot(screenshot)
        _draw_application_ui_screenshot(screenshot_007)
        _draw_application_ui_screenshot(comparison)
        acceptance_gate = root / "acceptance_gate.json"
        acceptance_gate.write_text(
            json.dumps(
                {
                    "status": "blocked_by_006",
                    "pass": False,
                    "base_results": [
                        {
                            "base": "LB26001-A-04-006",
                            "pass": False,
                            "vision_qc_v6_visual_acceptance_pass": False,
                            "reference_compare_v4_pass": False,
                            "ui_screenshot_files": [str(screenshot)],
                            "source_ui_report_application_ui_ok": True,
                            "ui_screenshot_content_check_pass": True,
                            "manual_case_status_pass": False,
                            "manual_visual_checklist_required": True,
                            "manual_visual_checklist_pass": False,
                            "manual_visual_checklist_missing_items": [
                                "reference_match",
                                "view_layout",
                            ],
                            "reasons": ["ui_screenshot_visual_acceptance_not_passed"],
                        },
                        {
                            "base": "LB26001-A-04-007",
                            "pass": False,
                            "vision_qc_v6_visual_acceptance_pass": False,
                            "reference_compare_v4_pass": False,
                        },
                    ],
                    "issues": [
                        {
                            "base": "LB26001-A-04-006",
                            "key": "application_ui_screenshot_review_not_passed",
                        },
                        {
                            "base": "LB26001-A-04-007",
                            "key": "ui_visual_review_gate_missing",
                        },
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        readiness = root / "readiness.json"
        readiness.write_text(
            json.dumps(
                {
                    "status": "blocked",
                    "blocking_issue_keys": ["solidworks_not_responding"],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        manual = root / "manual_visual_judgement.json"
        manual.write_text(
            json.dumps(
                {
                    "overall_status": "FAIL",
                    "review_mode": "application_drawing_review_ui_screenshot",
                    "entries": [
                        {
                            "base": "LB26001-A-04-006",
                            "manual_status": "FAIL",
                            "visual_acceptance_pass": False,
                            "ui_screenshot": str(screenshot),
                            "comparison_png": str(comparison),
                            "visual_checklist": {
                                "reference_match": False,
                                "view_layout": False,
                                "display_dimensions": False,
                            },
                            "visual_checklist_notes": {
                                "reference_match": "Reference composition mismatch from UI screenshot.",
                                "view_layout": "View layout differs from reference.",
                            },
                            "findings": ["006 still does not match the reference"],
                            "required_correction": "Repair 006 from the application UI screenshot comparison.",
                        },
                        {
                            "base": "LB26001-A-04-007",
                            "manual_status": "FAIL",
                            "visual_acceptance_pass": False,
                            "ui_screenshot": str(screenshot_007),
                            "findings": ["007 screenshot review also failed"],
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        report = build_requested_drawings_status(
            acceptance_gate_path=acceptance_gate,
            acceptance_proof_path=_acceptance_proof(root, passed=False),
            readiness_path=readiness,
            manual_review_paths=[manual],
            out_path=root / "status.json",
        )

    by_base = {item["base"]: item for item in report["base_results"]}
    assert report["status"] == "blocked_by_006"
    assert report["pass"] is False
    assert report["all_generated_drawings_currently_unqualified"] is True
    assert report["per_drawing_application_ui_screenshot_required"] is True
    assert report["final_judgement_requires_application_ui_per_drawing"] is True
    assert report["per_drawing_ui_acceptance_pass_count"] == 0
    assert report["per_drawing_ui_review_incomplete_count"] == 6
    assert by_base["LB26001-A-04-006"]["status"] == "visual_fail"
    assert by_base["LB26001-A-04-006"]["ui_visual_review_status"] == "visual_fail"
    assert by_base["LB26001-A-04-006"]["ui_screenshot_file_count"] == 1
    assert by_base["LB26001-A-04-006"]["api_only_acceptance_allowed"] is False
    assert by_base["LB26001-A-04-006"]["source_ui_report_application_ui_ok"] is True
    assert by_base["LB26001-A-04-006"]["manual_visual_checklist_required"] is True
    assert by_base["LB26001-A-04-006"]["manual_visual_checklist_pass"] is False
    assert by_base["LB26001-A-04-006"]["manual_visual_checklist_missing_items"] == [
        "reference_match",
        "view_layout",
    ]
    assert by_base["LB26001-A-04-006"]["application_ui_screenshot_gate_pass"] is False
    assert "manual_visual_checklist" in by_base["LB26001-A-04-006"]["missing_ui_acceptance_requirements"]
    assert by_base["LB26001-A-04-007"]["status"] == "visual_fail"
    assert by_base["LB26001-A-04-007"]["acceptance_status"] == "blocked_by_006"
    assert by_base["LB26001-A-04-007"]["acceptance_blocked_by_006"] is True
    assert by_base["LB26001-A-04-007"]["ui_visual_review_status"] == "visual_fail"
    assert by_base["LB26001-A-04-007"]["ui_screenshot_file_count"] == 1
    assert by_base["LB26001-A-04-007"]["api_is_not_final_judgement"] is True
    assert by_base["LB26001-A-04-007"]["api_only_acceptance_allowed"] is False
    assert by_base["LB26001-A-04-007"]["application_ui_screenshot_gate_pass"] is False
    assert "ui_visual_review_gate" in by_base["LB26001-A-04-007"]["missing_ui_acceptance_requirements"]
    assert "application_ui_source_report" in by_base["LB26001-A-04-007"]["missing_ui_acceptance_requirements"]
    assert "manual_visual_checklist" in by_base["LB26001-A-04-007"]["missing_ui_acceptance_requirements"]
    matrix_by_base = {item["base"]: item for item in report["per_drawing_ui_review_matrix"]}
    assert matrix_by_base["LB26001-A-04-006"]["final_judgement_source"] == (
        "application_drawing_review_ui_screenshot_manual_visual_judgement"
    )
    assert matrix_by_base["LB26001-A-04-006"]["application_ui_screenshot_present"] is True
    assert matrix_by_base["LB26001-A-04-006"]["manual_visual_judgement_present"] is True
    assert matrix_by_base["LB26001-A-04-006"]["manual_visual_judgement_pass"] is False
    assert matrix_by_base["LB26001-A-04-006"]["comparison_image"] == str(comparison)
    assert matrix_by_base["LB26001-A-04-006"]["latest_manual_visual_checklist"]["reference_match"] is False
    assert matrix_by_base["LB26001-A-04-006"]["latest_manual_visual_checklist_notes"]["view_layout"] == (
        "View layout differs from reference."
    )
    assert matrix_by_base["LB26001-A-04-006"]["latest_manual_findings"] == [
        "006 still does not match the reference"
    ]
    assert matrix_by_base["LB26001-A-04-006"]["latest_manual_required_correction"] == (
        "Repair 006 from the application UI screenshot comparison."
    )
    assert matrix_by_base["LB26001-A-04-006"]["manual_visual_checklist_failed_items"] == [
        "reference_match",
        "view_layout",
        "display_dimensions",
    ]
    assert matrix_by_base["LB26001-A-04-007"]["api_only_acceptance_allowed"] is False
    assert "LB26001-A-04-006" in report["drawings_with_visual_failure"]
    assert "LB26001-A-04-007" in report["drawings_with_visual_failure"]


def test_requested_drawings_status_rejects_api_pass_without_ui_screenshot() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        acceptance_gate = root / "acceptance_gate.json"
        acceptance_gate.write_text(
            json.dumps(
                {
                    "status": "need_review",
                    "pass": False,
                    "base_results": [
                        {
                            "base": "LB26001-A-04-006",
                            "pass": True,
                            "vision_qc_v6_visual_acceptance_pass": True,
                            "reference_compare_v4_pass": True,
                            "ui_screenshot_files": [],
                            "generated_png_source_required": True,
                            "generated_png_source_pass": True,
                        },
                    ],
                    "issues": [],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        readiness = root / "readiness.json"
        readiness.write_text('{"status": "ready"}', encoding="utf-8")
        manual = root / "manual_visual_judgement.json"
        manual.write_text(
            json.dumps(
                {
                    "overall_status": "PASS",
                    "review_mode": "application_drawing_review_ui_screenshot",
                    "entries": [
                        {
                            "base": "LB26001-A-04-006",
                            "manual_status": "PASS",
                            "visual_acceptance_pass": True,
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        report = build_requested_drawings_status(
            acceptance_gate_path=acceptance_gate,
            acceptance_proof_path=_acceptance_proof(root, passed=True),
            readiness_path=readiness,
            manual_review_paths=[manual],
            out_path=root / "status.json",
        )

    first = report["base_results"][0]
    assert first["base"] == "LB26001-A-04-006"
    assert first["pass"] is False
    assert first["status"] == "ui_screenshot_missing"
    assert first["ui_visual_review_status"] == "ui_screenshot_missing"
    assert first["api_only_acceptance_allowed"] is False
    assert first["application_ui_screenshot_gate_pass"] is False
    assert "application_ui_screenshot_file" in first["missing_ui_acceptance_requirements"]
    matrix = report["per_drawing_ui_review_matrix"][0]
    assert matrix["application_ui_screenshot_required"] is True
    assert matrix["application_ui_screenshot_present"] is False
    assert matrix["manual_visual_judgement_present"] is True
    assert matrix["api_is_not_final_judgement"] is True
    assert matrix["api_only_acceptance_allowed"] is False
    assert "LB26001-A-04-006" in report["drawings_missing_application_ui_screenshot"]


def test_requested_drawings_status_marks_stale_generated_png_source_invalid() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        screenshot = root / "screenshots" / "006.png"
        screenshot.parent.mkdir()
        _draw_application_ui_screenshot(screenshot)
        acceptance_gate = root / "acceptance_gate.json"
        acceptance_gate.write_text(
            json.dumps(
                {
                    "status": "need_review",
                    "pass": False,
                    "base_results": [
                        {
                            "base": "LB26001-A-04-006",
                            "pass": False,
                            "vision_qc_v6_visual_acceptance_pass": True,
                            "reference_compare_v4_pass": True,
                            "ui_screenshot_files": [str(screenshot)],
                            "generated_png_source_required": True,
                            "generated_png_source_pass": False,
                            "generated_png_source_evidence": {"under_legacy_v5": True},
                        },
                    ],
                    "issues": [
                        {
                            "base": "LB26001-A-04-006",
                            "key": "generated_png_source_evidence_not_current_run",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        readiness = root / "readiness.json"
        readiness.write_text('{"status": "ready"}', encoding="utf-8")
        manual = root / "manual_visual_judgement.json"
        manual.write_text(
            json.dumps(
                {
                    "overall_status": "PASS",
                    "review_mode": "application_drawing_review_ui_screenshot",
                    "entries": [
                        {
                            "base": "LB26001-A-04-006",
                            "manual_status": "PASS",
                            "visual_acceptance_pass": True,
                            "ui_screenshot": str(screenshot),
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        report = build_requested_drawings_status(
            acceptance_gate_path=acceptance_gate,
            acceptance_proof_path=_acceptance_proof(root, passed=True),
            readiness_path=readiness,
            manual_review_paths=[manual],
            out_path=root / "status.json",
        )

    first = report["base_results"][0]
    assert first["pass"] is False
    assert first["status"] == "generated_png_source_invalid"
    assert first["ui_visual_review_status"] == "generated_png_source_invalid"
    assert first["generated_png_source_required"] is True
    assert first["generated_png_source_pass"] is False
    assert first["application_ui_screenshot_gate_pass"] is False
    assert "fresh_generated_png_source" in first["missing_ui_acceptance_requirements"]


def test_requested_drawings_status_surfaces_manual_visual_checklist_missing() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        screenshot = root / "screenshots" / "006.png"
        screenshot.parent.mkdir()
        _draw_application_ui_screenshot(screenshot)
        acceptance_gate = root / "acceptance_gate.json"
        acceptance_gate.write_text(
            json.dumps(
                {
                    "status": "need_review",
                    "pass": False,
                    "base_results": [
                        {
                            "base": "LB26001-A-04-006",
                            "pass": False,
                            "vision_qc_v6_visual_acceptance_pass": False,
                            "reference_compare_v4_pass": True,
                            "ui_screenshot_files": [str(screenshot)],
                            "source_ui_report_application_ui_ok": True,
                            "ui_screenshot_content_check_pass": True,
                            "manual_case_status_pass": True,
                            "manual_visual_checklist_required": True,
                            "manual_visual_checklist_pass": False,
                            "manual_visual_checklist_missing_items": ["display_dimensions"],
                            "generated_png_source_required": True,
                            "generated_png_source_pass": True,
                        },
                    ],
                    "issues": [
                        {
                            "base": "LB26001-A-04-006",
                            "key": "manual_visual_checklist_missing_or_incomplete",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        readiness = root / "readiness.json"
        readiness.write_text('{"status": "ready"}', encoding="utf-8")
        manual = root / "manual_visual_judgement.json"
        manual.write_text(
            json.dumps(
                {
                    "overall_status": "PASS",
                    "review_mode": "application_drawing_review_ui_screenshot",
                    "entries": [
                        {
                            "base": "LB26001-A-04-006",
                            "manual_status": "PASS",
                            "visual_acceptance_pass": True,
                            "ui_screenshot": str(screenshot),
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        report = build_requested_drawings_status(
            acceptance_gate_path=acceptance_gate,
            acceptance_proof_path=_acceptance_proof(root, passed=True),
            readiness_path=readiness,
            manual_review_paths=[manual],
            out_path=root / "status.json",
        )

    first = report["base_results"][0]
    assert first["pass"] is False
    assert first["status"] == "manual_visual_checklist_missing"
    assert first["ui_visual_review_status"] == "manual_visual_checklist_missing"
    assert first["manual_case_status_pass"] is True
    assert first["manual_visual_checklist_pass"] is False
    assert first["manual_visual_checklist_missing_items"] == ["display_dimensions"]
    assert first["application_ui_screenshot_gate_pass"] is False
    assert first["missing_ui_acceptance_requirements"] == [
        "manual_visual_checklist",
        "required_per_drawing_artifacts",
    ]


def test_requested_drawings_status_surfaces_manual_visual_checklist_failed() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        screenshot = root / "screenshots" / "006.png"
        screenshot.parent.mkdir()
        _draw_application_ui_screenshot(screenshot)
        acceptance_gate = root / "acceptance_gate.json"
        acceptance_gate.write_text(
            json.dumps(
                {
                    "status": "need_review",
                    "pass": False,
                    "base_results": [
                        {
                            "base": "LB26001-A-04-006",
                            "pass": False,
                            "vision_qc_v6_visual_acceptance_pass": False,
                            "reference_compare_v4_pass": True,
                            "ui_screenshot_files": [str(screenshot)],
                            "source_ui_report_application_ui_ok": True,
                            "ui_screenshot_content_check_pass": True,
                            "manual_case_status_pass": False,
                            "manual_visual_checklist_required": True,
                            "manual_visual_checklist_pass": False,
                            "manual_visual_checklist_missing_items": [],
                            "manual_visual_checklist_failed_items": ["title_block"],
                            "manual_visual_checklist_not_passed_items": ["title_block"],
                            "generated_png_source_required": True,
                            "generated_png_source_pass": True,
                        },
                    ],
                    "issues": [
                        {
                            "base": "LB26001-A-04-006",
                            "key": "manual_visual_checklist_failed",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        readiness = root / "readiness.json"
        readiness.write_text('{"status": "ready"}', encoding="utf-8")
        manual = root / "manual_visual_judgement.json"
        manual.write_text(
            json.dumps(
                {
                    "overall_status": "FAIL",
                    "review_mode": "application_drawing_review_ui_screenshot",
                    "entries": [
                        {
                            "base": "LB26001-A-04-006",
                            "manual_status": "FAIL",
                            "visual_acceptance_pass": False,
                            "ui_screenshot": str(screenshot),
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        report = build_requested_drawings_status(
            acceptance_gate_path=acceptance_gate,
            acceptance_proof_path=_acceptance_proof(root, passed=True),
            readiness_path=readiness,
            manual_review_paths=[manual],
            out_path=root / "status.json",
        )

    first = report["base_results"][0]
    assert first["pass"] is False
    assert first["status"] == "manual_visual_checklist_failed"
    assert first["ui_visual_review_status"] == "manual_visual_checklist_failed"
    assert first["manual_visual_checklist_missing_items"] == []
    assert first["manual_visual_checklist_failed_items"] == ["title_block"]
    assert first["manual_visual_checklist_not_passed_items"] == ["title_block"]
    assert first["missing_ui_acceptance_requirements"] == [
        "manual_case_pass",
        "required_per_drawing_artifacts",
    ]


def test_requested_drawings_status_surfaces_manual_checklist_notes_and_correction() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        screenshot = root / "screenshots" / "006.png"
        screenshot.parent.mkdir()
        _draw_application_ui_screenshot(screenshot)
        acceptance_gate = root / "acceptance_gate.json"
        acceptance_gate.write_text(
            json.dumps(
                {
                    "status": "need_review",
                    "pass": False,
                    "base_results": [
                        {
                            "base": "LB26001-A-04-006",
                            "pass": False,
                            "vision_qc_v6_visual_acceptance_pass": False,
                            "reference_compare_v4_pass": True,
                            "ui_screenshot_files": [str(screenshot)],
                            "source_ui_report_application_ui_ok": True,
                            "ui_screenshot_content_check_pass": True,
                            "manual_case_status_pass": False,
                            "manual_visual_checklist_required": True,
                            "manual_visual_checklist_pass": False,
                            "manual_visual_checklist_missing_items": [],
                            "manual_visual_checklist_failed_items": ["title_block"],
                            "manual_visual_checklist_not_passed_items": ["title_block"],
                            "generated_png_source_required": True,
                            "generated_png_source_pass": True,
                        },
                    ],
                    "issues": [{"base": "LB26001-A-04-006", "key": "manual_visual_checklist_failed"}],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        readiness = root / "readiness.json"
        readiness.write_text('{"status": "ready"}', encoding="utf-8")
        manual = root / "manual_visual_judgement_codex_20260624.json"
        manual.write_text(
            json.dumps(
                {
                    "overall_status": "FAIL",
                    "review_mode": "application_drawing_review_ui_screenshot",
                    "entries": [
                        {
                            "base": "LB26001-A-04-006",
                            "manual_status": "FAIL",
                            "visual_acceptance_pass": False,
                            "ui_screenshot": str(screenshot),
                            "visual_checklist": {
                                "reference_match": False,
                                "view_layout": False,
                                "display_dimensions": False,
                                "dimension_readability": False,
                                "title_block": False,
                                "manufacturing_notes": False,
                            },
                            "visual_checklist_notes": {
                                "title_block": "Generated titleblock does not match the reference.",
                            },
                            "findings": ["Generated drawing still uses the wrong titleblock."],
                            "required_correction": "Remove the default titleblock and match the reference layout.",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        report = build_requested_drawings_status(
            acceptance_gate_path=acceptance_gate,
            acceptance_proof_path=_acceptance_proof(root, passed=True),
            readiness_path=readiness,
            manual_review_paths=[manual],
            out_path=root / "status.json",
        )

    first = report["base_results"][0]
    assert first["latest_manual_review"].endswith("manual_visual_judgement_codex_20260624.json")
    assert first["latest_manual_visual_checklist"]["title_block"] is False
    assert first["latest_manual_visual_checklist_notes"]["title_block"] == "Generated titleblock does not match the reference."
    assert first["latest_manual_findings"] == ["Generated drawing still uses the wrong titleblock."]
    assert first["latest_manual_required_correction"] == "Remove the default titleblock and match the reference layout."


def test_requested_drawings_status_rejects_gate_pass_when_ui_source_or_checklist_missing() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        screenshot = root / "screenshots" / "006.png"
        screenshot.parent.mkdir()
        _draw_application_ui_screenshot(screenshot)
        acceptance_gate = root / "acceptance_gate.json"
        acceptance_gate.write_text(
            json.dumps(
                {
                    "status": "pass",
                    "pass": True,
                    "base_results": [
                        {
                            "base": "LB26001-A-04-006",
                            "pass": True,
                            "vision_qc_v6_visual_acceptance_pass": True,
                            "reference_compare_v4_pass": True,
                            "ui_screenshot_files": [str(screenshot)],
                            "source_ui_report_application_ui_ok": False,
                            "manual_case_status_pass": True,
                            "manual_visual_checklist_required": False,
                            "manual_visual_checklist_pass": True,
                            "generated_png_source_required": True,
                            "generated_png_source_pass": True,
                        },
                    ],
                    "issues": [],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        readiness = root / "readiness.json"
        readiness.write_text('{"status": "ready"}', encoding="utf-8")
        manual = root / "manual_visual_judgement.json"
        manual.write_text(
            json.dumps(
                {
                    "overall_status": "PASS",
                    "review_mode": "application_drawing_review_ui_screenshot",
                    "entries": [
                        {
                            "base": "LB26001-A-04-006",
                            "manual_status": "PASS",
                            "visual_acceptance_pass": True,
                            "ui_screenshot": str(screenshot),
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        report = build_requested_drawings_status(
            acceptance_gate_path=acceptance_gate,
            acceptance_proof_path=_acceptance_proof(root, passed=True),
            readiness_path=readiness,
            manual_review_paths=[manual],
            out_path=root / "status.json",
        )

    first = report["base_results"][0]
    assert first["pass"] is False
    assert first["status"] == "need_review"
    assert first["ui_visual_review_status"] == "pass"
    assert first["application_ui_screenshot_gate_pass"] is False
    assert "application_ui_source_report" in first["missing_ui_acceptance_requirements"]
    assert "manual_visual_checklist" in first["missing_ui_acceptance_requirements"]


def test_requested_drawings_status_rejects_nonexistent_ui_screenshot_path() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        missing_screenshot = root / "screenshots" / "missing_006.png"
        acceptance_gate = root / "acceptance_gate.json"
        acceptance_gate.write_text(
            json.dumps(
                {
                    "status": "pass",
                    "pass": True,
                    "base_results": [
                        {
                            "base": "LB26001-A-04-006",
                            "pass": True,
                            "vision_qc_v6_visual_acceptance_pass": True,
                            "reference_compare_v4_pass": True,
                            "ui_screenshot_files": [str(missing_screenshot)],
                            "source_ui_report_application_ui_ok": True,
                            "ui_screenshot_content_check_pass": True,
                            "manual_case_status_pass": True,
                            "manual_visual_checklist_required": True,
                            "manual_visual_checklist_pass": True,
                            "generated_png_source_required": True,
                            "generated_png_source_pass": True,
                        },
                    ],
                    "issues": [],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        readiness = root / "readiness.json"
        readiness.write_text('{"status": "ready"}', encoding="utf-8")
        manual = root / "manual_visual_judgement.json"
        manual.write_text(
            json.dumps(
                {
                    "overall_status": "PASS",
                    "review_mode": "application_drawing_review_ui_screenshot",
                    "entries": [
                        {
                            "base": "LB26001-A-04-006",
                            "manual_status": "PASS",
                            "visual_acceptance_pass": True,
                            "ui_screenshot": str(missing_screenshot),
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        report = build_requested_drawings_status(
            acceptance_gate_path=acceptance_gate,
            acceptance_proof_path=_acceptance_proof(root, passed=True),
            readiness_path=readiness,
            manual_review_paths=[manual],
            out_path=root / "status.json",
        )

    first = report["base_results"][0]
    assert first["pass"] is False
    assert first["status"] == "ui_screenshot_missing"
    assert first["ui_screenshot_file_count"] == 0
    assert first["invalid_or_missing_gate_ui_screenshot_files"] == [str(missing_screenshot)]
    assert "application_ui_screenshot_file" in first["missing_ui_acceptance_requirements"]


def test_requested_drawings_status_defaults_to_strict_final_006_evidence() -> None:
    assert "LB26001_006_explicit_displaydim_visible_entities_visual_review_20260623" in str(DEFAULT_ACCEPTANCE_GATE)
    assert "closed_loop_strict_final_20260624" in str(DEFAULT_ACCEPTANCE_GATE)
    assert str(DEFAULT_ACCEPTANCE_PROOF).endswith("lb26001_006_acceptance_proof_v4_2.json")
    assert str(DEFAULT_DIRECT_UI_SCREENSHOT_RECHECK).endswith("codex_direct_ui_screenshot_recheck_20260624.json")


def test_requested_drawings_status_discovers_new_ui_screenshot_manual_reviews() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        review_dir = root / "drw_output" / "ui_acceptance" / "LB26001_ref6_application_ui_screenshot_recheck_user_20260624"
        review_dir.mkdir(parents=True)
        review = review_dir / "manual_visual_judgement_codex_20260624.json"
        review.write_text('{"overall_status": "FAIL"}', encoding="utf-8")

        old_reviews = status_mod.DEFAULT_MANUAL_REVIEWS
        old_globs = status_mod.DEFAULT_MANUAL_REVIEW_GLOBS
        try:
            status_mod.DEFAULT_MANUAL_REVIEWS = []
            status_mod.DEFAULT_MANUAL_REVIEW_GLOBS = [
                root
                / "drw_output"
                / "ui_acceptance"
                / "LB26001_ref6_application_ui_screenshot_recheck*"
                / "manual_visual_judgement_codex_*.json"
            ]
            discovered = status_mod._default_manual_review_paths()
        finally:
            status_mod.DEFAULT_MANUAL_REVIEWS = old_reviews
            status_mod.DEFAULT_MANUAL_REVIEW_GLOBS = old_globs

    assert discovered == [review]


def test_requested_drawings_status_uses_006_proof_to_block_false_gate_pass() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        screenshot = root / "screenshots" / "006.png"
        screenshot.parent.mkdir()
        _draw_application_ui_screenshot(screenshot)
        acceptance_gate = root / "acceptance_gate.json"
        acceptance_gate.write_text(
            json.dumps(
                {
                    "status": "pass",
                    "pass": True,
                    "base_results": [
                        {
                            "base": "LB26001-A-04-006",
                            "pass": True,
                            "vision_qc_v6_visual_acceptance_pass": True,
                            "reference_compare_v4_pass": True,
                            "ui_screenshot_files": [str(screenshot)],
                            "source_ui_report_application_ui_ok": True,
                            "ui_screenshot_content_check_pass": True,
                            "manual_case_status_pass": True,
                            "manual_visual_checklist_required": True,
                            "manual_visual_checklist_pass": True,
                            "generated_png_source_required": True,
                            "generated_png_source_pass": True,
                        },
                        {
                            "base": "LB26001-A-04-007",
                            "pass": False,
                        },
                    ],
                    "issues": [],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        readiness = root / "readiness.json"
        readiness.write_text('{"status": "ready"}', encoding="utf-8")
        manual = root / "manual_visual_judgement.json"
        manual.write_text(
            json.dumps(
                {
                    "overall_status": "PASS",
                    "review_mode": "application_drawing_review_ui_screenshot",
                    "entries": [
                        {
                            "base": "LB26001-A-04-006",
                            "manual_status": "PASS",
                            "visual_acceptance_pass": True,
                            "ui_screenshot": str(screenshot),
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        report = build_requested_drawings_status(
            acceptance_gate_path=acceptance_gate,
            acceptance_proof_path=_acceptance_proof(root, passed=False),
            readiness_path=readiness,
            manual_review_paths=[manual],
            out_path=root / "status.json",
        )

    by_base = {item["base"]: item for item in report["base_results"]}
    assert report["status"] == "blocked_by_006"
    assert report["primary_acceptance_proof_pass"] is False
    assert report["primary_acceptance_proof_blocking_issue_keys"] == ["v6_with_ui_not_pass"]
    assert by_base["LB26001-A-04-006"]["primary_acceptance_proof_pass"] is False
    assert by_base["LB26001-A-04-007"]["acceptance_status"] == "blocked_by_006"
    assert by_base["LB26001-A-04-007"]["acceptance_blocked_by_006"] is True


def test_requested_drawings_status_blocks_when_006_proof_is_missing() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        acceptance_gate = root / "acceptance_gate.json"
        acceptance_gate.write_text(
            json.dumps(
                {
                    "status": "pass",
                    "pass": True,
                    "base_results": [
                        {
                            "base": base,
                            "pass": True,
                            "ui_screenshot_files": [str(root / "screenshots" / f"{base}.png")],
                            "source_ui_report_application_ui_ok": True,
                            "ui_screenshot_content_check_pass": True,
                            "manual_case_status_pass": True,
                            "manual_visual_checklist_required": True,
                            "manual_visual_checklist_pass": True,
                            "generated_png_source_required": True,
                            "generated_png_source_pass": True,
                        }
                        for base in [
                            "LB26001-A-04-006",
                            "LB26001-A-04-007",
                            "LB26001-A-04-008",
                            "LB26001-A-04-009",
                            "LB26001-A-04-015",
                            "LB26001-A-04-022",
                        ]
                    ],
                    "issues": [],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        screenshot_dir = root / "screenshots"
        screenshot_dir.mkdir()
        for base in [
            "LB26001-A-04-006",
            "LB26001-A-04-007",
            "LB26001-A-04-008",
            "LB26001-A-04-009",
            "LB26001-A-04-015",
            "LB26001-A-04-022",
        ]:
            _draw_application_ui_screenshot(screenshot_dir / f"{base}.png")
        readiness = root / "readiness.json"
        readiness.write_text('{"status": "ready"}', encoding="utf-8")
        manual = root / "manual_visual_judgement.json"
        manual.write_text(
            json.dumps(
                {
                    "overall_status": "PASS",
                    "review_mode": "application_drawing_review_ui_screenshot",
                    "entries": [
                        {
                            "base": base,
                            "manual_status": "PASS",
                            "visual_acceptance_pass": True,
                            "ui_screenshot": str(screenshot_dir / f"{base}.png"),
                        }
                        for base in [
                            "LB26001-A-04-006",
                            "LB26001-A-04-007",
                            "LB26001-A-04-008",
                            "LB26001-A-04-009",
                            "LB26001-A-04-015",
                            "LB26001-A-04-022",
                        ]
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        report = build_requested_drawings_status(
            acceptance_gate_path=acceptance_gate,
            acceptance_proof_path=root / "missing_proof.json",
            readiness_path=readiness,
            manual_review_paths=[manual],
            out_path=root / "status.json",
        )

    assert report["status"] == "blocked_by_006"
    assert report["primary_acceptance_proof_present"] is False
    assert report["primary_acceptance_proof_pass"] is False
    assert report["pass"] is False


def test_requested_drawings_status_uses_direct_ui_screenshot_recheck_as_manual_gate() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        screenshot = root / "screenshots" / "006.png"
        screenshot.parent.mkdir()
        _draw_application_ui_screenshot(screenshot)
        acceptance_gate = root / "acceptance_gate.json"
        acceptance_gate.write_text(
            json.dumps(
                {
                    "status": "pass",
                    "pass": True,
                    "base_results": [
                        {
                            "base": "LB26001-A-04-006",
                            "pass": True,
                            "vision_qc_v6_visual_acceptance_pass": True,
                            "reference_compare_v4_pass": True,
                            "ui_screenshot_files": [str(screenshot)],
                            "source_ui_report_application_ui_ok": True,
                            "ui_screenshot_content_check_pass": True,
                            "manual_case_status_pass": True,
                            "manual_visual_checklist_required": True,
                            "manual_visual_checklist_pass": True,
                            "generated_png_source_required": True,
                            "generated_png_source_pass": True,
                        }
                    ],
                    "issues": [],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        readiness = root / "readiness.json"
        readiness.write_text('{"status": "ready"}', encoding="utf-8")
        direct_recheck = root / "codex_direct_ui_screenshot_recheck_20260624.json"
        direct_recheck.write_text(
            json.dumps(
                {
                    "schema": "sw_drawing_studio.codex_direct_ui_screenshot_recheck.v4_2",
                    "overall_status": "FAIL",
                    "review_method": "direct_application_drawing_review_ui_screenshot_visual_check",
                    "api_is_not_final_judgement": True,
                    "ui_screenshot_review_is_final_gate": True,
                    "cases": [
                        {
                            "base": "LB26001-A-04-006",
                            "status": "FAIL",
                            "screenshot": str(screenshot),
                            "visual_findings": [
                                "Generated drawing still does not match the reference screenshot."
                            ],
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        report = build_requested_drawings_status(
            acceptance_gate_path=acceptance_gate,
            acceptance_proof_path=_acceptance_proof(root, passed=True),
            readiness_path=readiness,
            manual_review_paths=[direct_recheck],
            out_path=root / "status.json",
        )

    first = report["base_results"][0]
    assert first["base"] == "LB26001-A-04-006"
    assert first["acceptance_gate_pass"] is True
    assert first["primary_acceptance_proof_pass"] is True
    assert first["application_ui_screenshot_review_method_ok"] is True
    assert first["pass"] is False
    assert first["status"] == "visual_fail"
    assert first["ui_visual_review_status"] == "visual_fail"
    assert first["latest_manual_review"].endswith("codex_direct_ui_screenshot_recheck_20260624.json")
    assert first["latest_manual_findings"] == [
        "Generated drawing still does not match the reference screenshot."
    ]


def test_requested_drawings_status_carries_006_ui_bucket_closure_gate() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        screenshot = root / "screenshots" / "006.png"
        screenshot.parent.mkdir()
        _draw_application_ui_screenshot(screenshot)
        acceptance_gate = root / "acceptance_gate.json"
        acceptance_gate.write_text(
            json.dumps(
                {
                    "status": "pass",
                    "pass": True,
                    "base_results": [
                        {
                            "base": "LB26001-A-04-006",
                            "pass": True,
                            "vision_qc_v6_visual_acceptance_pass": True,
                            "reference_compare_v4_pass": True,
                            "ui_screenshot_files": [str(screenshot)],
                            "source_ui_report_application_ui_ok": True,
                            "ui_screenshot_content_check_pass": True,
                            "manual_case_status_pass": True,
                            "manual_visual_checklist_required": True,
                            "manual_visual_checklist_pass": True,
                            "generated_png_source_required": True,
                            "generated_png_source_pass": True,
                        }
                    ],
                    "issues": [],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        readiness = root / "readiness.json"
        readiness.write_text('{"status": "ready"}', encoding="utf-8")
        manual = root / "manual_visual_judgement.json"
        manual.write_text(
            json.dumps(
                {
                    "overall_status": "PASS",
                    "review_mode": "application_drawing_review_ui_screenshot",
                    "entries": [
                        {
                            "base": "LB26001-A-04-006",
                            "manual_status": "PASS",
                            "visual_acceptance_pass": True,
                            "ui_screenshot": str(screenshot),
                            "visual_checklist": {
                                "reference_match": True,
                                "view_layout": True,
                                "display_dimensions": True,
                            },
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        ui_review = root / "ui_visual_review.json"
        ui_review.write_text(
            json.dumps(
                {
                    "schema": "sw_drawing_studio.ui_visual_review.v4_4",
                    "status": "need_review",
                    "pass": False,
                    "review_method": "application_drawing_review_ui_screenshot",
                    "application_ui_screenshot_is_final_gate": True,
                    "api_only_acceptance_allowed": False,
                    "entries": [
                        {
                            "base": "LB26001-A-04-006",
                            "status": "need_review",
                            "pass": False,
                            "visual_acceptance_pass": False,
                            "application_ui_screenshot": str(screenshot),
                            "checks": {
                                "ui_report_entry_pass": True,
                                "manual_review_entry_screenshot_pass": True,
                                "ui_defect_bucket_closure_pass": False,
                                "vision_qc_v6_visual_acceptance_pass": True,
                                "reference_compare_v4_pass": True,
                            },
                            "ui_defect_bucket_closure": {
                                "required": True,
                                "pass": False,
                                "required_bucket_keys": [
                                    "dimension_visual_overdense",
                                    "callout_missing",
                                ],
                                "passed_bucket_keys": ["dimension_visual_overdense"],
                                "missing_bucket_keys": ["callout_missing"],
                                "failed_bucket_keys": [],
                                "bucket_closure_contract_count": 2,
                            },
                            "blocking_issue_keys": ["ui_defect_bucket_closure_not_proven"],
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        report = build_requested_drawings_status(
            acceptance_gate_path=acceptance_gate,
            acceptance_proof_path=_acceptance_proof(root, passed=True),
            readiness_path=readiness,
            ui_visual_review_path=ui_review,
            manual_review_paths=[manual],
            out_path=root / "status.json",
        )

    first = report["base_results"][0]
    assert first["base"] == "LB26001-A-04-006"
    assert first["pass"] is False
    assert first["ui_defect_bucket_closure_required"] is True
    assert first["ui_defect_bucket_closure_pass"] is False
    assert first["ui_defect_bucket_missing_keys"] == ["callout_missing"]
    assert "ui_defect_bucket_closure" in first["missing_ui_acceptance_requirements"]
    matrix = report["per_drawing_ui_review_matrix"][0]
    assert matrix["ui_defect_bucket_closure_required"] is True
    assert matrix["ui_defect_bucket_closure_pass"] is False
    assert matrix["ui_defect_bucket_required_keys"] == [
        "dimension_visual_overdense",
        "callout_missing",
    ]
    assert matrix["ui_defect_bucket_passed_keys"] == ["dimension_visual_overdense"]
    assert matrix["ui_defect_bucket_missing_keys"] == ["callout_missing"]
    assert matrix["ui_defect_bucket_closure_contract_count"] == 2
    assert matrix["ui_defect_bucket_api_or_displaydim_metric_alone_can_close"] is False


if __name__ == "__main__":
    test_requested_drawings_status_keeps_ui_fail_and_006_block()
    test_requested_drawings_status_rejects_api_pass_without_ui_screenshot()
    test_requested_drawings_status_marks_stale_generated_png_source_invalid()
    test_requested_drawings_status_surfaces_manual_visual_checklist_missing()
    test_requested_drawings_status_surfaces_manual_visual_checklist_failed()
    test_requested_drawings_status_surfaces_manual_checklist_notes_and_correction()
    test_requested_drawings_status_rejects_gate_pass_when_ui_source_or_checklist_missing()
    test_requested_drawings_status_rejects_nonexistent_ui_screenshot_path()
    test_requested_drawings_status_defaults_to_strict_final_006_evidence()
    test_requested_drawings_status_discovers_new_ui_screenshot_manual_reviews()
    test_requested_drawings_status_uses_006_proof_to_block_false_gate_pass()
    test_requested_drawings_status_blocks_when_006_proof_is_missing()
    test_requested_drawings_status_uses_direct_ui_screenshot_recheck_as_manual_gate()
    test_requested_drawings_status_carries_006_ui_bucket_closure_gate()
    print("PASS test_v4_2_lb26001_requested_drawings_status")


