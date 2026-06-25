import json
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image, ImageDraw

from tools.validation.apply_ui_visual_review_v4 import apply_ui_visual_review


def _draw_review_png(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (900, 600), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle([100, 100, 360, 240], outline="black", width=2)
    draw.line([80, 80, 390, 80], fill="black", width=1)
    draw.line([80, 80, 80, 260], fill="black", width=1)
    for x in range(130, 330, 45):
        draw.line([x, 72, x + 20, 72], fill="black", width=1)
        draw.line([x, 75, x, 95], fill="black", width=1)
    for y in range(505, 590, 18):
        draw.line([615, y, 890, y], fill="black", width=1)
    for x in range(615, 891, 45):
        draw.line([x, 505, x, 590], fill="black", width=1)
    image.save(path)
    return path


def _draw_application_ui_screenshot(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (1600, 900), "white")
    draw = ImageDraw.Draw(image)

    # Application chrome, navigation, and log regions for the screenshot-content gate.
    draw.rectangle([0, 0, 1600, 72], fill=(225, 232, 240))
    draw.rectangle([0, 0, 180, 900], fill=(235, 239, 245))
    draw.rectangle([0, 730, 1600, 900], fill=(242, 244, 247))
    for y in range(105, 520, 54):
        draw.rectangle([22, y, 150, y + 24], fill=(200, 207, 216))
    for y in range(760, 875, 22):
        draw.line([210, y, 1500, y], fill=(175, 180, 188), width=2)

    # Side-by-side review panes in the regions checked by the validator.
    draw.rectangle([450, 180, 790, 640], outline=(70, 70, 70), width=3)
    draw.rectangle([860, 180, 1200, 640], outline=(70, 70, 70), width=3)
    draw.rectangle([805, 160, 845, 660], fill=(210, 215, 222))
    for x0 in (500, 910):
        draw.rectangle([x0, 260, x0 + 190, 390], outline="black", width=3)
        draw.line([x0 - 20, 245, x0 + 220, 245], fill="black", width=2)
        draw.line([x0 - 20, 245, x0 - 20, 420], fill="black", width=2)
        for x in range(x0 + 20, x0 + 170, 42):
            draw.line([x, 235, x + 24, 235], fill="black", width=2)
            draw.line([x, 238, x, 258], fill="black", width=2)
    image.save(path)
    return path


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def test_apply_ui_visual_review_writes_v6_and_v4_with_ui_artifacts() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        base = "LB26001-A-04-006"
        run_dir = root / "runs" / "case"
        case_dir = root / "stage" / f"01_{base}"
        ui_dir = root / "ui"
        png = _draw_review_png(run_dir / "drawing" / f"{base}_v5.PNG")
        reference_png = _draw_review_png(root / f"{base}.png")
        screenshot = _draw_application_ui_screenshot(ui_dir / "screenshots" / f"01_{base}_ui_visual_review.png")
        part = root / f"{base}.SLDPRT"
        part.write_text("fixture", encoding="utf-8")

        blueprint = {
            "schema": "sw_drawing_studio.drawing_blueprint.v4",
            "base": base,
            "part_class": "machined_part",
            "drawing_purpose": "manufacturing",
            "view_plan": [
                {
                    "slot": "front",
                    "view_type": "named",
                    "required": True,
                    "sw_view_type": "7",
                    "create_method": "named_view",
                }
            ],
            "dimension_plan": {
                "required_display_dim_count": 0,
                "reference_display_dim_count": 1,
                "allow_note_substitution": False,
            },
            "annotation_plan": {},
            "titlebar_plan": {"required_fields": ["drawing_no"], "missing_fields": []},
            "notes_plan": {},
            "validation_plan": {"require_ui_visual_review": True},
        }
        _write_json(run_dir / "qc" / "drawing_blueprint.json", blueprint)
        _write_json(run_dir / "qc" / f"{base}_v5_qc.json", {"pass": True, "display_dim_count": 1})
        _write_json(case_dir / "cad_smoke.json", {"pass": True, "run_dir": str(run_dir), "artifacts": {}})
        _write_json(
            case_dir / "dimension_validation.json",
            {"pass": True, "status": "pass", "dimension_validation": {"display_dim_count": 1, "note_dim_count": 0}},
        )
        _write_json(case_dir / "reference_compare.json", {"pass": True, "status": "pass"})
        _write_json(case_dir / "reference_style.json", {"pass": True, "status": "pass"})
        profiles = root / "reference_profiles_v4.json"
        _write_json(
            profiles,
            {
                "profiles": {
                    base: {
                        "base": base,
                        "view_count": 1,
                        "view_types": {"7": 1},
                        "display_dim_count": 1,
                        "normalized_notes": [],
                        "roughness_symbols": [],
                        "datum_symbols": [],
                    }
                }
            },
        )
        summary = _write_json(
            root / "stage" / "summary.json",
            {
                "cases": [
                    {
                        "part_name": base,
                        "part": str(part),
                        "run_dir": str(run_dir),
                        "case_dir": str(case_dir),
                    }
                ]
            },
        )
        ui_report = _write_json(
            ui_dir / "drawing_visual_review_report.json",
            {
                "schema": "sw_drawing_studio.drawing_visual_review_ui.v1",
                "mode": "source_qt_application_ui_screenshot",
                "entries": [
                    {
                        "base": base,
                        "generated_png": str(png),
                        "ui_screenshot": {"path": str(screenshot), "pass": True},
                        "generated_png_evidence": {
                            "strict_source_pass": True,
                            "under_run_dir": True,
                            "under_legacy_v5": False,
                        },
                    }
                ]
            },
        )
        manual = _write_json(
            ui_dir / "manual_visual_judgement.json",
            {
                "method": "application_drawing_review_ui_screenshot",
                "overall_status": "PASS",
                "visual_acceptance_pass": True,
                "cases": [
                    {
                        "base": base,
                        "verdict": "PASS",
                        "visual_acceptance_pass": True,
                        "ui_screenshot": str(screenshot),
                        "visual_checklist": {
                            "reference_match": True,
                            "view_layout": True,
                            "display_dimensions": True,
                            "dimension_readability": True,
                            "title_block": True,
                            "manufacturing_notes": True,
                        },
                    }
                ],
            },
        )
        out_dir = ui_dir / "closed_loop"

        result = apply_ui_visual_review(
            summary_path=summary,
            ui_report_path=ui_report,
            manual_review_path=manual,
            out_dir=out_dir,
            bases=[base],
            reference_profiles=profiles,
        )
        v6_payload = json.loads(
            (out_dir / "vision_qc_v6_with_ui_review" / f"{base}.json").read_text(encoding="utf-8")
        )
        generated_files_exist = {
            "v6_case": (out_dir / "vision_qc_v6_with_ui_review" / f"{base}.json").exists(),
            "v4_case": (out_dir / "reference_compare_v4_with_ui_review" / f"{base}.json").exists(),
            "v6_single": (out_dir / "vision_qc_v6_with_ui_review.json").exists(),
            "v4_single": (out_dir / "reference_compare_v4_with_ui_review.json").exists(),
            "effective_manual": (out_dir / "manual_visual_judgement_with_source.json").exists(),
            "summary": (out_dir / "ui_visual_review_gate_summary.json").exists(),
            "canonical_ui_visual_review": (out_dir / "ui_visual_review.json").exists(),
        }
        canonical = json.loads((out_dir / "ui_visual_review.json").read_text(encoding="utf-8"))

    assert result["pass"] is False
    assert result["status"] == "need_review"
    assert result["ui_visual_review"].endswith("ui_visual_review.json")
    assert result["source_ui_report_injected"] is True
    assert result["effective_manual_review"].endswith("manual_visual_judgement_with_source.json")
    assert result["entries"][0]["vision_qc_v6_visual_acceptance_pass"] is False
    assert result["entries"][0]["ui_screenshot_review_pass"] is True
    assert result["entries"][0]["generated_png_source_required"] is True
    assert result["entries"][0]["generated_png_source_pass"] is True
    assert result["entries"][0]["reference_compare_v4_pass"] is False
    assert "layout_match_score_below_v4_threshold" in result["entries"][0]["reasons"]
    ui_review = v6_payload["checks"]["ui_screenshot_review"]
    assert ui_review["source_ui_report"] == str(ui_report)
    assert ui_review["source_ui_report_exists"] is True
    assert ui_review["pass"] is True
    assert ui_review["ui_screenshot_content_check_pass"] is True
    assert generated_files_exist == {
        "v6_case": True,
        "v4_case": True,
        "v6_single": True,
        "v4_single": True,
        "effective_manual": True,
        "summary": True,
        "canonical_ui_visual_review": True,
    }
    assert canonical["schema"] == "sw_drawing_studio.ui_visual_review.v4_4"
    assert canonical["review_method"] == "application_drawing_review_ui_screenshot"
    assert canonical["application_ui_screenshot_is_final_gate"] is True
    assert canonical["api_only_acceptance_allowed"] is False
    assert canonical["pass"] is False
    assert canonical["entries"][0]["base"] == base
    assert canonical["entries"][0]["application_ui_screenshot"] == str(screenshot)
    assert "reference_compare_v4_with_ui_not_pass" in canonical["blocking_issue_keys"]
    assert result["ui_report_entries_all_pass"] is True
    assert result["manual_review_entries_all_pass"] is True
    assert result["vision_qc_v6_all_pass"] is False
    assert result["reference_compare_v4_all_pass"] is False
    assert result["entries"][0]["ui_report_entry_present"] is True
    assert result["entries"][0]["ui_report_entry_screenshot_exists"] is True
    assert result["entries"][0]["ui_report_entry_pass"] is True
    assert result["entries"][0]["manual_review_entry_present"] is True
    assert result["entries"][0]["manual_review_screenshot_matches_ui_report_entry"] is True
    assert result["entries"][0]["manual_review_entry_screenshot_pass"] is True


def test_apply_ui_visual_review_blocks_pass_without_matching_ui_report_entry() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        base = "SAMPLE-001"
        run_dir = root / "runs" / "case"
        case_dir = root / "stage" / f"01_{base}"
        ui_dir = root / "ui"
        png = _draw_review_png(run_dir / "drawing" / f"{base}_v5.PNG")
        screenshot = _draw_application_ui_screenshot(ui_dir / "screenshots" / f"01_{base}_ui_visual_review.png")
        part = root / f"{base}.SLDPRT"
        part.write_text("fixture", encoding="utf-8")
        _draw_review_png(root / f"{base}.png")

        _write_json(
            run_dir / "qc" / "drawing_blueprint.json",
            {
                "schema": "sw_drawing_studio.drawing_blueprint.v4",
                "base": base,
                "part_class": "machined_part",
                "drawing_purpose": "manufacturing",
                "view_plan": [
                    {
                        "slot": "front",
                        "view_type": "named",
                        "required": True,
                        "sw_view_type": "7",
                        "create_method": "named_view",
                    }
                ],
                "dimension_plan": {
                    "required_display_dim_count": 0,
                    "reference_display_dim_count": 0,
                    "allow_note_substitution": False,
                },
                "annotation_plan": {},
                "titlebar_plan": {"required_fields": [], "missing_fields": []},
                "notes_plan": {},
                "validation_plan": {"require_ui_visual_review": True},
            },
        )
        _write_json(run_dir / "qc" / f"{base}_v5_qc.json", {"pass": True, "display_dim_count": 0})
        _write_json(case_dir / "cad_smoke.json", {"pass": True, "run_dir": str(run_dir), "artifacts": {}})
        _write_json(
            case_dir / "dimension_validation.json",
            {"pass": True, "status": "pass", "dimension_validation": {"display_dim_count": 0, "note_dim_count": 0}},
        )
        _write_json(case_dir / "reference_compare.json", {"pass": True, "status": "pass"})
        _write_json(case_dir / "reference_style.json", {"pass": True, "status": "pass"})
        profiles = root / "reference_profiles_v4.json"
        _write_json(
            profiles,
            {
                "profiles": {
                    base: {
                        "base": base,
                        "view_count": 1,
                        "view_types": {"7": 1},
                        "display_dim_count": 0,
                        "normalized_notes": [],
                        "roughness_symbols": [],
                        "datum_symbols": [],
                    }
                }
            },
        )
        summary = _write_json(
            root / "stage" / "summary.json",
            {
                "cases": [
                    {
                        "part_name": base,
                        "part": str(part),
                        "run_dir": str(run_dir),
                        "case_dir": str(case_dir),
                    }
                ]
            },
        )
        ui_report = _write_json(
            ui_dir / "drawing_visual_review_report.json",
            {
                "schema": "sw_drawing_studio.drawing_visual_review_ui.v1",
                "mode": "source_qt_application_ui_screenshot",
                "entries": [],
            },
        )
        manual = _write_json(
            ui_dir / "manual_visual_judgement.json",
            {
                "method": "application_drawing_review_ui_screenshot",
                "overall_status": "PASS",
                "visual_acceptance_pass": True,
                "cases": [
                    {
                        "base": base,
                        "verdict": "PASS",
                        "visual_acceptance_pass": True,
                        "ui_screenshot": str(screenshot),
                        "visual_checklist": {
                            "reference_match": True,
                            "view_layout": True,
                            "display_dimensions": True,
                            "dimension_readability": True,
                            "title_block": True,
                            "manufacturing_notes": True,
                        },
                    }
                ],
            },
        )

        result = apply_ui_visual_review(
            summary_path=summary,
            ui_report_path=ui_report,
            manual_review_path=manual,
            out_dir=ui_dir / "closed_loop",
            bases=[base],
            reference_profiles=profiles,
        )

    assert result["pass"] is False
    assert result["status"] == "need_review"
    assert result["ui_report_entries_all_pass"] is False
    assert result["entries"][0]["ui_report_entry_present"] is False
    assert result["entries"][0]["ui_report_entry_screenshot_exists"] is False
    assert result["entries"][0]["ui_report_entry_pass"] is False
    assert result["entries"][0]["generated_png"] == str(png)


def test_apply_ui_visual_review_blocks_pass_when_manual_screenshot_differs_from_ui_report() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        base = "SAMPLE-002"
        run_dir = root / "runs" / "case"
        case_dir = root / "stage" / f"01_{base}"
        ui_dir = root / "ui"
        png = _draw_review_png(run_dir / "drawing" / f"{base}_v5.PNG")
        ui_screenshot = _draw_application_ui_screenshot(ui_dir / "screenshots" / f"01_{base}_ui_visual_review.png")
        other_screenshot = _draw_application_ui_screenshot(ui_dir / "screenshots" / f"other_{base}_ui_visual_review.png")
        part = root / f"{base}.SLDPRT"
        part.write_text("fixture", encoding="utf-8")
        _draw_review_png(root / f"{base}.png")

        _write_json(
            run_dir / "qc" / "drawing_blueprint.json",
            {
                "schema": "sw_drawing_studio.drawing_blueprint.v4",
                "base": base,
                "part_class": "machined_part",
                "drawing_purpose": "manufacturing",
                "view_plan": [
                    {
                        "slot": "front",
                        "view_type": "named",
                        "required": True,
                        "sw_view_type": "7",
                        "create_method": "named_view",
                    }
                ],
                "dimension_plan": {
                    "required_display_dim_count": 0,
                    "reference_display_dim_count": 0,
                    "allow_note_substitution": False,
                },
                "annotation_plan": {},
                "titlebar_plan": {"required_fields": [], "missing_fields": []},
                "notes_plan": {},
                "validation_plan": {"require_ui_visual_review": True},
            },
        )
        _write_json(run_dir / "qc" / f"{base}_v5_qc.json", {"pass": True, "display_dim_count": 0})
        _write_json(case_dir / "cad_smoke.json", {"pass": True, "run_dir": str(run_dir), "artifacts": {}})
        _write_json(
            case_dir / "dimension_validation.json",
            {"pass": True, "status": "pass", "dimension_validation": {"display_dim_count": 0, "note_dim_count": 0}},
        )
        _write_json(case_dir / "reference_compare.json", {"pass": True, "status": "pass"})
        _write_json(case_dir / "reference_style.json", {"pass": True, "status": "pass"})
        profiles = root / "reference_profiles_v4.json"
        _write_json(
            profiles,
            {
                "profiles": {
                    base: {
                        "base": base,
                        "view_count": 1,
                        "view_types": {"7": 1},
                        "display_dim_count": 0,
                        "normalized_notes": [],
                        "roughness_symbols": [],
                        "datum_symbols": [],
                    }
                }
            },
        )
        summary = _write_json(
            root / "stage" / "summary.json",
            {
                "cases": [
                    {
                        "part_name": base,
                        "part": str(part),
                        "run_dir": str(run_dir),
                        "case_dir": str(case_dir),
                    }
                ]
            },
        )
        ui_report = _write_json(
            ui_dir / "drawing_visual_review_report.json",
            {
                "schema": "sw_drawing_studio.drawing_visual_review_ui.v1",
                "mode": "source_qt_application_ui_screenshot",
                "entries": [
                    {
                        "base": base,
                        "generated_png": str(png),
                        "ui_screenshot": {"path": str(ui_screenshot), "pass": True},
                    }
                ],
            },
        )
        manual = _write_json(
            ui_dir / "manual_visual_judgement.json",
            {
                "method": "application_drawing_review_ui_screenshot",
                "overall_status": "PASS",
                "visual_acceptance_pass": True,
                "cases": [
                    {
                        "base": base,
                        "verdict": "PASS",
                        "visual_acceptance_pass": True,
                        "ui_screenshot": str(other_screenshot),
                        "visual_checklist": {
                            "reference_match": True,
                            "view_layout": True,
                            "display_dimensions": True,
                            "dimension_readability": True,
                            "title_block": True,
                            "manufacturing_notes": True,
                        },
                    }
                ],
            },
        )

        result = apply_ui_visual_review(
            summary_path=summary,
            ui_report_path=ui_report,
            manual_review_path=manual,
            out_dir=ui_dir / "closed_loop",
            bases=[base],
            reference_profiles=profiles,
        )

    assert result["pass"] is False
    assert result["status"] == "need_review"
    assert result["ui_report_entries_all_pass"] is True
    assert result["manual_review_entries_all_pass"] is False
    assert result["entries"][0]["ui_report_entry_pass"] is True
    assert result["entries"][0]["manual_review_entry_present"] is True
    assert result["entries"][0]["manual_review_screenshot_matches_ui_report_entry"] is False
    assert result["entries"][0]["manual_review_entry_screenshot_pass"] is False
    assert result["entries"][0]["manual_review_entry_screenshot_mismatch_paths"] == [str(other_screenshot)]


if __name__ == "__main__":
    test_apply_ui_visual_review_writes_v6_and_v4_with_ui_artifacts()
    test_apply_ui_visual_review_blocks_pass_without_matching_ui_report_entry()
    test_apply_ui_visual_review_blocks_pass_when_manual_screenshot_differs_from_ui_report()
    print("PASS test_v4_apply_ui_visual_review")
