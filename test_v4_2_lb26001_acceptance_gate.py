import json
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image, ImageDraw

from tools.validation.lb26001_acceptance_gate_v4_2 import audit_lb26001_acceptance_gate


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _write_gate(path: Path, entries: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema": "sw_drawing_studio.ui_visual_review_gate.v4",
                "entries": entries,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def _entry(base: str, *, passed: bool, reasons: list[str] | None = None) -> dict:
    return {
        "base": base,
        "vision_qc_v6_visual_acceptance_pass": passed,
        "reference_compare_v4_pass": passed,
        "vision_qc_v6_with_ui_review": f"vision/{base}.json",
        "reference_compare_v4_with_ui_review": f"v4/{base}.json",
        "reasons": reasons or [],
    }


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


def _draw_plain_png(path: Path) -> Path:
    image = Image.new("RGB", (900, 600), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle([160, 180, 650, 280], outline="black", width=2)
    draw.line([120, 130, 720, 130], fill="black", width=1)
    image.save(path)
    return path


def _write_pass_artifacts(
    root: Path,
    base: str,
    *,
    include_screenshot: bool = True,
    generated_source_pass: bool = True,
    application_source_ok: bool = True,
    include_manual_checklist: bool = True,
    plain_screenshot: bool = False,
) -> dict:
    screenshot = root / "screenshots" / f"{base}.png"
    screenshot.parent.mkdir(parents=True, exist_ok=True)
    if include_screenshot:
        if plain_screenshot:
            _draw_plain_png(screenshot)
        else:
            _draw_application_ui_screenshot(screenshot)

    ui_report = root / "drawing_visual_review_report.json"
    ui_report.write_text(
        json.dumps(
            {
                "schema": (
                    "sw_drawing_studio.drawing_visual_review_ui.v1"
                    if application_source_ok
                    else "generic.visual_report"
                ),
                "mode": (
                    "source_qt_application_ui_screenshot"
                    if application_source_ok
                    else "api_metric_export"
                ),
                "entries": [
                    {
                        "base": base,
                        "ui_screenshot": {"path": str(screenshot)},
                        "generated_png_evidence": {
                            "strict_source_pass": generated_source_pass,
                            "under_run_dir": generated_source_pass,
                            "under_legacy_v5": not generated_source_pass,
                        },
                    }
                ]
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    v6 = root / "vision" / f"{base}.json"
    v6.parent.mkdir(parents=True, exist_ok=True)
    v6.write_text(
        json.dumps(
            {
                "visual_acceptance_pass": True,
                "status": "pass",
                "manual_review": str(root / "manual_visual_judgement.json"),
                "checks": {
                    "ui_screenshot_review": {
                        "pass": True,
                        "manual_review_method_ok": True,
                        "ui_screenshot_paths_existing": [str(screenshot)] if include_screenshot else [],
                        "source_ui_report": str(ui_report),
                        "source_ui_report_schema": (
                            "sw_drawing_studio.drawing_visual_review_ui.v1"
                            if application_source_ok
                            else "generic.visual_report"
                        ),
                        "source_ui_report_mode": (
                            "source_qt_application_ui_screenshot"
                            if application_source_ok
                            else "api_metric_export"
                        ),
                        "source_ui_report_application_ui_ok": application_source_ok,
                        "case_match": (
                            {
                                "pass": True,
                                "manual_case_status_pass": True,
                                "visual_checklist_required": True,
                                "visual_checklist_pass": True,
                                "missing_visual_checklist_items": [],
                                "failed_visual_checklist_items": [],
                                "not_passed_visual_checklist_items": [],
                            }
                            if include_manual_checklist
                            else {"pass": True}
                        ),
                        "generated_png_source_required": True,
                        "generated_png_source_pass": generated_source_pass,
                        "generated_png_source_evidence": {
                            "strict_source_pass": generated_source_pass,
                            "under_run_dir": generated_source_pass,
                            "under_legacy_v5": not generated_source_pass,
                        },
                    }
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    v4 = root / "v4" / f"{base}.json"
    v4.parent.mkdir(parents=True, exist_ok=True)
    v4.write_text('{"pass": true, "status": "pass"}', encoding="utf-8")
    return {
        "base": base,
        "vision_qc_v6_visual_acceptance_pass": True,
        "reference_compare_v4_pass": True,
        "vision_qc_v6_with_ui_review": str(v6),
        "reference_compare_v4_with_ui_review": str(v4),
        "reasons": [],
    }


def _write_staged_summary(root: Path, *, base: str = "LB26001-A-04-006", lifecycle_pass: bool = True, write_lifecycle: bool = True) -> Path:
    case_dir = root / "stage" / f"01_{base}"
    lifecycle_report = case_dir / "displaydim_lifecycle_audit.json"
    if write_lifecycle:
        _write_json(
            lifecycle_report,
            {
                "schema": "sw_drawing_studio.lb26001_006_displaydim_lifecycle_audit.v4_2",
                "base": base,
                "status": "pass" if lifecycle_pass else "fail",
                "pass": lifecycle_pass,
                "blocking_issue_keys": [] if lifecycle_pass else ["final_display_dim_below_reference_floor"],
            },
        )
    return _write_json(
        root / "stage" / "summary.json",
        {
            "stage": "LB26001_006",
            "status": "pass" if lifecycle_pass else "need_review",
            "pass": lifecycle_pass,
            "processed": 1,
            "total": 1,
            "cases": [
                {
                    "part_name": base,
                    "case_dir": str(case_dir),
                    "displaydim_lifecycle_required": True,
                    "displaydim_lifecycle_pass": lifecycle_pass,
                    "displaydim_lifecycle_report": str(lifecycle_report),
                    "displaydim_lifecycle_blocking_issue_keys": [] if lifecycle_pass else ["final_display_dim_below_reference_floor"],
                }
            ],
        },
    )


def test_lb26001_acceptance_gate_blocks_expansion_until_006_passes() -> None:
    with TemporaryDirectory() as tmp:
        gate = _write_gate(
            Path(tmp) / "gate.json",
            [
                _entry(
                    "LB26001-A-04-006",
                    passed=False,
                    reasons=[
                        "display_dim_lower_than_reference",
                        "ui_screenshot_visual_acceptance_not_passed",
                    ],
                )
            ],
        )
        result = audit_lb26001_acceptance_gate(
            gate_summaries=[gate],
            staged_summary_path=_write_staged_summary(root=Path(tmp), lifecycle_pass=False),
            requested_bases=["LB26001-A-04-006", "LB26001-A-04-007"],
        )

    keys = {item["key"] for item in result["issues"]}
    assert result["status"] == "blocked_by_006"
    assert result["pass"] is False
    assert "lb26001_006_required_before_expansion" in keys
    assert "reference_compare_v4_with_ui_review_not_pass" in keys


def test_lb26001_acceptance_gate_passes_single_006_when_ui_closure_passes() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        gate = _write_gate(root / "gate.json", [_write_pass_artifacts(root, "LB26001-A-04-006")])
        out = Path(tmp) / "audit.json"
        result = audit_lb26001_acceptance_gate(
            gate_summaries=[gate],
            staged_summary_path=_write_staged_summary(root),
            requested_bases=["LB26001-A-04-006"],
            out_path=out,
        )
        out_exists = out.exists()

    assert result["status"] == "pass"
    assert result["pass"] is True
    assert result["primary_pass"] is True
    assert result["base_results"][0]["ui_screenshot_file_count"] == 1
    assert result["base_results"][0]["ui_screenshot_content_check_pass"] is True
    assert result["base_results"][0]["generated_png_source_pass"] is True
    assert out_exists is True


def test_lb26001_acceptance_gate_infers_generated_png_source_from_legacy_ui_report_paths() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        base = "LB26001-A-04-006"
        run_dir = root / "runs" / "fresh"
        generated_png = run_dir / "drawing" / f"{base}_v5.PNG"
        generated_png.parent.mkdir(parents=True)
        generated_png.write_bytes(b"fresh-png")
        screenshot = root / "screenshots" / f"{base}.png"
        screenshot.parent.mkdir(parents=True)
        _draw_application_ui_screenshot(screenshot)
        ui_report = root / "drawing_visual_review_report.json"
        ui_report.write_text(
            json.dumps(
                {
                    "schema": "sw_drawing_studio.drawing_visual_review_ui.v1",
                    "mode": "source_qt_application_ui_screenshot",
                    "entries": [
                        {
                            "base": base,
                            "run_dir": str(run_dir),
                            "generated_png": str(generated_png),
                            "ui_screenshot": {"path": str(screenshot)},
                        }
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        manual = root / "manual_visual_judgement.json"
        manual.write_text('{"overall_status": "PASS"}', encoding="utf-8")
        v6 = root / "vision" / f"{base}.json"
        v6.parent.mkdir(parents=True)
        v6.write_text(
            json.dumps(
                {
                    "visual_acceptance_pass": True,
                    "status": "pass",
                    "manual_review": str(manual),
                    "checks": {
                        "ui_screenshot_review": {
                            "pass": True,
                            "manual_review_method_ok": True,
                            "ui_screenshot_paths_existing": [str(screenshot)],
                            "source_ui_report": str(ui_report),
                            "source_ui_report_schema": "sw_drawing_studio.drawing_visual_review_ui.v1",
                            "source_ui_report_mode": "source_qt_application_ui_screenshot",
                            "source_ui_report_application_ui_ok": True,
                            "case_match": {
                                "pass": True,
                                "manual_case_status_pass": True,
                                "visual_checklist_required": True,
                                "visual_checklist_pass": True,
                                "missing_visual_checklist_items": [],
                                "failed_visual_checklist_items": [],
                                "not_passed_visual_checklist_items": [],
                            },
                            "generated_png_source_required": True,
                            "generated_png_source_pass": False,
                            "generated_png_source_evidence": {},
                        }
                    },
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        v4 = root / "v4" / f"{base}.json"
        v4.parent.mkdir(parents=True)
        v4.write_text('{"pass": true, "status": "pass"}', encoding="utf-8")
        gate = _write_gate(
            root / "gate.json",
            [
                {
                    "base": base,
                    "vision_qc_v6_visual_acceptance_pass": True,
                    "reference_compare_v4_pass": True,
                    "vision_qc_v6_with_ui_review": str(v6),
                    "reference_compare_v4_with_ui_review": str(v4),
                    "reasons": [],
                }
            ],
        )

        result = audit_lb26001_acceptance_gate(
            gate_summaries=[gate],
            staged_summary_path=_write_staged_summary(root),
            requested_bases=[base],
            out_path=root / "acceptance.json",
        )

    first = result["base_results"][0]
    assert result["pass"] is True
    assert first["generated_png_source_pass"] is True
    assert first["generated_png_source_evidence"]["source"] == "drawing_visual_review_report_path_inference"
    assert first["generated_png_source_evidence"]["under_run_dir"] is True


def test_lb26001_acceptance_gate_rejects_ui_pass_without_lifecycle_report() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        gate = _write_gate(root / "gate.json", [_write_pass_artifacts(root, "LB26001-A-04-006")])
        result = audit_lb26001_acceptance_gate(
            gate_summaries=[gate],
            staged_summary_path=_write_staged_summary(root, write_lifecycle=False),
            requested_bases=["LB26001-A-04-006"],
        )

    keys = {item["key"] for item in result["issues"]}
    first = result["base_results"][0]
    assert result["status"] == "need_review"
    assert result["pass"] is False
    assert result["primary_pass"] is False
    assert first["displaydim_lifecycle_required"] is True
    assert first["displaydim_lifecycle_report_exists"] is False
    assert "displaydim_lifecycle_report_missing" in keys
    assert "displaydim_lifecycle_not_pass" in keys


def test_lb26001_acceptance_gate_requires_ui_closure_for_each_requested_base() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        gate = _write_gate(root / "gate.json", [_write_pass_artifacts(root, "LB26001-A-04-006")])
        result = audit_lb26001_acceptance_gate(
            gate_summaries=[gate],
            staged_summary_path=_write_staged_summary(root),
            requested_bases=["LB26001-A-04-006", "LB26001-A-04-007"],
        )

    keys = {item["key"] for item in result["issues"]}
    assert result["status"] == "need_review"
    assert result["pass"] is False
    assert "ui_visual_review_gate_missing" in keys


def test_lb26001_acceptance_gate_distinguishes_failed_visual_checklist_from_missing() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        base = "LB26001-A-04-006"
        screenshot = root / "screenshots" / f"{base}.png"
        screenshot.parent.mkdir(parents=True)
        _draw_application_ui_screenshot(screenshot)
        ui_report = root / "drawing_visual_review_report.json"
        ui_report.write_text(
            json.dumps(
                {
                    "schema": "sw_drawing_studio.drawing_visual_review_ui.v1",
                    "mode": "source_qt_application_ui_screenshot",
                    "entries": [{"base": base, "ui_screenshot": {"path": str(screenshot)}}],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        manual = root / "manual_visual_judgement.json"
        manual.write_text('{"overall_status": "FAIL"}', encoding="utf-8")
        v6 = root / "vision" / f"{base}.json"
        v6.parent.mkdir(parents=True)
        v6.write_text(
            json.dumps(
                {
                    "visual_acceptance_pass": False,
                    "status": "need_review",
                    "manual_review": str(manual),
                    "checks": {
                        "ui_screenshot_review": {
                            "pass": False,
                            "manual_review_method_ok": True,
                            "ui_screenshot_paths_existing": [str(screenshot)],
                            "source_ui_report": str(ui_report),
                            "source_ui_report_schema": "sw_drawing_studio.drawing_visual_review_ui.v1",
                            "source_ui_report_mode": "source_qt_application_ui_screenshot",
                            "source_ui_report_application_ui_ok": True,
                            "case_match": {
                                "pass": False,
                                "manual_case_status_pass": False,
                                "visual_checklist_required": True,
                                "visual_checklist_pass": False,
                                "missing_visual_checklist_items": [],
                                "failed_visual_checklist_items": ["title_block"],
                                "not_passed_visual_checklist_items": ["title_block"],
                            },
                            "generated_png_source_required": True,
                            "generated_png_source_pass": True,
                            "generated_png_source_evidence": {
                                "strict_source_pass": True,
                                "under_run_dir": True,
                                "under_legacy_v5": False,
                            },
                        }
                    },
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        v4 = root / "v4" / f"{base}.json"
        v4.parent.mkdir(parents=True)
        v4.write_text('{"pass": false, "status": "need_review"}', encoding="utf-8")
        gate = _write_gate(
            root / "gate.json",
            [
                {
                    "base": base,
                    "vision_qc_v6_visual_acceptance_pass": False,
                    "reference_compare_v4_pass": False,
                    "vision_qc_v6_with_ui_review": str(v6),
                    "reference_compare_v4_with_ui_review": str(v4),
                    "reasons": [],
                }
            ],
        )
        result = audit_lb26001_acceptance_gate(
            gate_summaries=[gate],
            requested_bases=[base],
        )

    keys = {item["key"] for item in result["issues"]}
    first = result["base_results"][0]
    assert "manual_visual_checklist_failed" in keys
    assert "manual_visual_checklist_missing_or_incomplete" not in keys
    assert first["manual_visual_checklist_missing_items"] == []
    assert first["manual_visual_checklist_failed_items"] == ["title_block"]


def test_lb26001_acceptance_gate_rejects_api_pass_without_screenshot_file() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        gate = _write_gate(root / "gate.json", [_write_pass_artifacts(root, "LB26001-A-04-006", include_screenshot=False)])
        result = audit_lb26001_acceptance_gate(
            gate_summaries=[gate],
            requested_bases=["LB26001-A-04-006"],
        )

    keys = {item["key"] for item in result["issues"]}
    assert result["status"] == "need_review"
    assert result["pass"] is False
    assert result["primary_pass"] is False
    assert "application_ui_screenshot_evidence_missing" in keys


def test_lb26001_acceptance_gate_rejects_plain_png_claimed_as_ui_screenshot() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        gate = _write_gate(
            root / "gate.json",
            [_write_pass_artifacts(root, "LB26001-A-04-006", plain_screenshot=True)],
        )
        result = audit_lb26001_acceptance_gate(
            gate_summaries=[gate],
            requested_bases=["LB26001-A-04-006"],
        )

    keys = {item["key"] for item in result["issues"]}
    first = result["base_results"][0]
    assert result["status"] == "need_review"
    assert result["pass"] is False
    assert result["primary_pass"] is False
    assert first["ui_screenshot_file_count"] == 1
    assert first["ui_screenshot_content_check_pass"] is False
    assert "application_ui_screenshot_content_invalid" in keys


def test_lb26001_acceptance_gate_rejects_ui_pass_with_stale_generated_png_source() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        gate = _write_gate(
            root / "gate.json",
            [_write_pass_artifacts(root, "LB26001-A-04-006", generated_source_pass=False)],
        )
        result = audit_lb26001_acceptance_gate(
            gate_summaries=[gate],
            requested_bases=["LB26001-A-04-006"],
        )

    keys = {item["key"] for item in result["issues"]}
    first = result["base_results"][0]
    assert result["status"] == "need_review"
    assert result["pass"] is False
    assert result["primary_pass"] is False
    assert first["generated_png_source_required"] is True
    assert first["generated_png_source_pass"] is False
    assert "generated_png_source_evidence_not_current_run" in keys


def test_lb26001_acceptance_gate_rejects_api_pass_without_application_ui_report_source() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        gate = _write_gate(
            root / "gate.json",
            [_write_pass_artifacts(root, "LB26001-A-04-006", application_source_ok=False)],
        )
        result = audit_lb26001_acceptance_gate(
            gate_summaries=[gate],
            requested_bases=["LB26001-A-04-006"],
        )

    keys = {item["key"] for item in result["issues"]}
    first = result["base_results"][0]
    assert result["status"] == "need_review"
    assert result["pass"] is False
    assert result["primary_pass"] is False
    assert first["source_ui_report_application_ui_ok"] is False
    assert "application_ui_screenshot_source_report_invalid" in keys


def test_lb26001_acceptance_gate_rejects_ui_pass_without_manual_checklist_details() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        gate = _write_gate(
            root / "gate.json",
            [_write_pass_artifacts(root, "LB26001-A-04-006", include_manual_checklist=False)],
        )
        result = audit_lb26001_acceptance_gate(
            gate_summaries=[gate],
            requested_bases=["LB26001-A-04-006"],
        )

    keys = {item["key"] for item in result["issues"]}
    first = result["base_results"][0]
    assert result["status"] == "need_review"
    assert result["pass"] is False
    assert result["primary_pass"] is False
    assert first["manual_case_status_pass"] is False
    assert first["manual_visual_checklist_required"] is False
    assert "manual_visual_case_not_pass" in keys
    assert "manual_visual_checklist_missing_or_incomplete" in keys


if __name__ == "__main__":
    test_lb26001_acceptance_gate_blocks_expansion_until_006_passes()
    test_lb26001_acceptance_gate_passes_single_006_when_ui_closure_passes()
    test_lb26001_acceptance_gate_infers_generated_png_source_from_legacy_ui_report_paths()
    test_lb26001_acceptance_gate_rejects_ui_pass_without_lifecycle_report()
    test_lb26001_acceptance_gate_requires_ui_closure_for_each_requested_base()
    test_lb26001_acceptance_gate_distinguishes_failed_visual_checklist_from_missing()
    test_lb26001_acceptance_gate_rejects_api_pass_without_screenshot_file()
    test_lb26001_acceptance_gate_rejects_plain_png_claimed_as_ui_screenshot()
    test_lb26001_acceptance_gate_rejects_ui_pass_with_stale_generated_png_source()
    test_lb26001_acceptance_gate_rejects_api_pass_without_application_ui_report_source()
    test_lb26001_acceptance_gate_rejects_ui_pass_without_manual_checklist_details()
    print("PASS test_v4_2_lb26001_acceptance_gate")
