import json
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image, ImageDraw

from app.services.notes_detector import detect_notes
from app.services.titlebar_detector import detect_titlebar
from app.services.vision_issue_schema import REQUIRED_ISSUE_FIELDS
from app.services.vision_qc_v6 import _compare_reference_png, run_vision_qc_v6


def _blueprint() -> dict:
    return {
        "schema": "sw_drawing_studio.drawing_blueprint.v4",
        "base": "LB26001-A-04-006",
        "part_class": "machined_part",
        "view_plan": [
            {"slot": "front", "required": True, "center_norm": [0.37, 0.81]},
            {"slot": "top", "required": True, "center_norm": [0.37, 0.59], "sw_view_type": "4"},
            {"slot": "right", "required": True, "center_norm": [0.72, 0.81], "sw_view_type": "4"},
            {"slot": "iso", "required": True, "center_norm": [0.80, 0.48]},
        ],
        "dimension_plan": {
            "required_display_dim_count": 12,
            "allow_note_substitution": False,
            "fallback_policy": "need_review_when_real_displaydim_unavailable",
        },
        "annotation_plan": {
            "centerlines_required": True,
            "center_marks_required": True,
        },
        "notes_plan": {
            "required_notes": ["技术要求", "未注粗糙度 Ra3.2"],
            "raw_reference_notes": ["TECHNICAL REQUIREMENTS"],
        },
        "layout_plan": {
            "titlebar_box_norm": [0.68, 0.0, 1.0, 0.18],
            "notes_box_norm": [0.58, 0.18, 0.98, 0.35],
            "sheet_size": {"width": 0.297, "height": 0.21},
        },
    }


def _reference_style_blueprint() -> dict:
    blueprint = json.loads(json.dumps(_blueprint(), ensure_ascii=False))
    blueprint["layout_plan"]["sheet_template_policy"] = {
        "source": "reference_profile",
        "policy": "strip_default_template_artifacts",
        "default_template_artifacts_allowed": False,
        "skip_builtin_gb_frame_titleblock": True,
        "visible_titlebar_mode": "compact_reference_fields",
        "reason": "same-name reference controls visible sheet/titleblock style",
    }
    return blueprint


def _write_blueprint(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_blueprint(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _write_reference_style_blueprint(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_reference_style_blueprint(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _draw_visual_png(path: Path) -> Path:
    image = Image.new("RGB", (900, 600), "white")
    draw = ImageDraw.Draw(image)
    # View-like geometry.
    draw.rectangle([120, 120, 390, 230], outline="black", width=2)
    draw.rectangle([120, 300, 390, 360], outline="black", width=2)
    draw.rectangle([500, 120, 650, 230], outline="black", width=2)
    draw.line([90, 90, 430, 90], fill="black", width=1)
    draw.line([90, 90, 90, 245], fill="black", width=1)
    for x in range(140, 370, 35):
        draw.line([x, 105, x + 20, 105], fill="black", width=1)
        draw.line([x, 108, x, 120], fill="black", width=1)
    # Notes area: blueprint y is bottom-origin, so this is lower-right in image space.
    for index in range(7):
        y = 405 + index * 12
        draw.line([530, y, 820, y], fill="black", width=1)
    # Titlebar area: bottom-right in image space.
    for y in range(505, 590, 18):
        draw.line([615, y, 890, y], fill="black", width=1)
    for x in range(615, 891, 45):
        draw.line([x, 505, x, 590], fill="black", width=1)
    image.save(path)
    return path


def _draw_clustered_dimension_png(path: Path) -> Path:
    image = Image.new("RGB", (900, 600), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle([120, 120, 390, 230], outline="black", width=2)
    draw.rectangle([120, 300, 390, 360], outline="black", width=2)
    for row in range(3):
        for col in range(3):
            x = 300 + col * 10
            y = 155 + row * 8
            draw.rectangle([x, y, x + 5, y + 4], fill="black")
    image.save(path)
    return path


def _draw_same_bbox_different_grid_pair(generated_path: Path, reference_path: Path) -> tuple[Path, Path]:
    def draw_base(path: Path, view_offset: int) -> Path:
        image = Image.new("RGB", (900, 600), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle([100, 80, 800, 520], outline="black", width=2)
        for x in range(120, 780, 80):
            draw.line([x, 92, x + 45, 92], fill="black", width=2)
        for index in range(3):
            left = view_offset + index * 32
            top = 150 + index * 70
            draw.rectangle([left, top, left + 145, top + 42], outline="black", width=3)
            draw.line([left + 10, top + 14, left + 135, top + 14], fill="black", width=2)
            draw.line([left + 12, top + 56, left + 120, top + 56], fill="black", width=2)
        image.save(path)
        return path

    reference = draw_base(reference_path, 145)
    generated = draw_base(generated_path, 555)
    return generated, reference


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
    for x in [128, 232, 336, 448, 524]:
        draw.rectangle([x, 46, x + 84, 68], fill="#f8f8f8", outline="#bdbdbd")
    for y in range(100, 210, 18):
        draw.line([12, y, 100, y], fill="#333333", width=1)
    draw.rectangle([119, 108, 360, 126], fill="#2a8bd6")
    draw.rectangle([470, 130, 820, 640], fill="white", outline="#d0d6dc", width=2)
    draw.rectangle([860, 130, 1210, 640], fill="white", outline="#d0d6dc", width=2)
    draw.line([840, 120, 840, 650], fill="#98abc0", width=2)
    for offset in [0, 390]:
        x0 = 520 + offset
        draw.rectangle([x0, 245, x0 + 210, 325], outline="black", width=2)
        draw.line([x0 - 25, 220, x0 + 250, 220], fill="black", width=1)
        draw.line([x0 + 12, 355, x0 + 200, 355], fill="black", width=1)
        for index in range(7):
            draw.line([x0 + 250, 420 + index * 14, x0 + 330, 420 + index * 14], fill="#333333", width=1)
    for y in range(112, 250, 24):
        draw.line([1308, y, 1568, y], fill="#222222", width=1)
    for y in range(835, 930, 22):
        draw.line([20, y, 1580, y], fill="#333333", width=1)
    image.save(path)
    return path


def _visual_checklist() -> dict:
    return {
        "reference_match": True,
        "view_layout": True,
        "display_dimensions": True,
        "dimension_readability": True,
        "title_block": True,
        "manufacturing_notes": True,
    }


def test_vision_qc_v6_flags_blank_png_and_keeps_required_issue_fields() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_dir = root / "run"
        png = root / "blank.png"
        Image.new("RGB", (500, 350), "white").save(png)
        blueprint = _write_blueprint(run_dir / "qc" / "drawing_blueprint.json")

        result = run_vision_qc_v6(png_path=png, run_dir=run_dir, blueprint_path=blueprint)

        assert result["status"] == "need_review"
        assert result["visual_acceptance_pass"] is False
        assert (run_dir / "qc" / "vision_qc_v6.json").exists()
        keys = {issue["key"] for issue in result["issues"]}
        assert "png_visual_blank" in keys
        for issue in result["issues"]:
            assert set(REQUIRED_ISSUE_FIELDS) <= set(issue)


def test_titlebar_and_notes_detectors_use_sheet_to_image_coordinate_conversion() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        png = _draw_visual_png(root / "drawing.png")
        blueprint = _blueprint()

        titlebar = detect_titlebar(png, blueprint=blueprint)
        notes = detect_notes(png, blueprint=blueprint)

        assert titlebar["detected"] is True
        assert notes["detected"] is True
        assert notes["technical_requirements_detected"] is True


def test_vision_qc_v6_rejects_default_titleblock_artifacts_when_reference_policy_strips_template() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_dir = root / "run"
        png = _draw_visual_png(root / "drawing_with_default_titleblock.png")
        blueprint = _write_reference_style_blueprint(run_dir / "qc" / "drawing_blueprint.json")

        result = run_vision_qc_v6(
            png_path=png,
            run_dir=run_dir,
            blueprint_path=blueprint,
        )
        artifact_check = result["checks"]["reference_sheet_template_artifacts"]
        keys = {issue["key"] for issue in result["issues"]}

        assert artifact_check["default_template_artifacts_forbidden"] is True
        assert artifact_check["default_template_artifacts_present"] is True
        assert "reference_titleblock_artifacts_present" in keys
        assert "titlebar_missing_or_empty" not in keys
        assert result["visual_acceptance_pass"] is False


def test_vision_qc_v6_rejects_clustered_reference_dimensions_as_unreadable() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_dir = root / "run"
        png = _draw_clustered_dimension_png(root / "clustered_dimensions.png")
        blueprint = _write_reference_style_blueprint(run_dir / "qc" / "drawing_blueprint.json")

        result = run_vision_qc_v6(
            png_path=png,
            run_dir=run_dir,
            blueprint_path=blueprint,
        )
        dimension_check = result["checks"]["dimension_visuals"]
        keys = {issue["key"] for issue in result["issues"]}

        assert dimension_check["reference_style_dimension_readability_required"] is True
        assert dimension_check["max_local_dimension_text_cluster_count"] >= 7
        assert dimension_check["visual_dimension_cluster_pass"] is False
        assert "dimension_visual_clustered_unreadable" in keys
        assert result["visual_acceptance_pass"] is False


def test_vision_qc_v6_rejects_reference_grid_mismatch_even_when_bbox_matches() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_dir = root / "run"
        generated_png, reference_png = _draw_same_bbox_different_grid_pair(
            root / "generated.png",
            root / "reference.png",
        )
        blueprint = _write_blueprint(run_dir / "qc" / "drawing_blueprint.json")

        reference_compare = _compare_reference_png(generated_png, reference_png)
        result = run_vision_qc_v6(
            png_path=generated_png,
            run_dir=run_dir,
            blueprint_path=blueprint,
            reference_png_path=reference_png,
        )
        keys = {issue["key"] for issue in result["issues"]}

        assert reference_compare["success"] is True
        assert reference_compare["bbox_layout_match"] is True
        assert reference_compare["grid_layout_match"] is False
        assert reference_compare["coarse_layout_match"] is False
        assert "reference_visual_layout_mismatch" in keys
        assert result["checks"]["reference_visual_compare"]["grid_layout_match"] is False


def test_vision_qc_v6_records_blueprint_and_supporting_api_as_non_final_evidence() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_dir = root / "run"
        png = _draw_visual_png(root / "drawing.png")
        blueprint = _write_blueprint(run_dir / "qc" / "drawing_blueprint.json")
        qc_json = run_dir / "qc" / "LB26001-A-04-006_v5_qc.json"
        qc_json.write_text(
            json.dumps({"pass": True, "display_dim_count": 14, "dimension_grade": "A"}, ensure_ascii=False),
            encoding="utf-8",
        )

        result = run_vision_qc_v6(
            png_path=png,
            run_dir=run_dir,
            blueprint_path=blueprint,
            qc_json_path=qc_json,
        )

        assert result["drawing_blueprint"].endswith("drawing_blueprint.json")
        assert result["checks"]["geometry_qc_supporting"]["api_is_not_final_judgement"] is True
        assert "titlebar" in result["checks"]
        assert "notes" in result["checks"]
        assert "dimension_visuals" in result["checks"]


def test_vision_qc_v6_rejects_manual_pass_without_application_screenshot_evidence() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_dir = root / "run"
        png = _draw_visual_png(root / "drawing.png")
        blueprint = _write_blueprint(run_dir / "qc" / "drawing_blueprint.json")
        manual_review = root / "manual_visual_judgement.json"
        manual_review.write_text(
            json.dumps(
                {
                    "overall_status": "PASS",
                    "visual_acceptance_pass": True,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = run_vision_qc_v6(
            png_path=png,
            run_dir=run_dir,
            blueprint_path=blueprint,
            manual_review_path=manual_review,
        )
        ui_review = result["checks"]["ui_screenshot_review"]
        keys = {issue["key"] for issue in result["issues"]}

        assert ui_review["pass"] is False
        assert ui_review["manual_review_method_ok"] is False
        assert ui_review["ui_screenshot_evidence_present"] is False
        assert "manual_ui_screenshot_review_required" in keys


def test_vision_qc_v6_accepts_manual_pass_with_application_screenshot_evidence() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_dir = root / "run"
        png = _draw_visual_png(root / "drawing.png")
        blueprint = _write_blueprint(run_dir / "qc" / "drawing_blueprint.json")
        screenshot = root / "01_LB26001-A-04-006_ui_visual_review.png"
        _draw_application_ui_screenshot(screenshot)
        ui_report = root / "drawing_visual_review_report.json"
        ui_report.write_text(
            json.dumps(
                {
                    "schema": "sw_drawing_studio.drawing_visual_review_ui.v1",
                    "mode": "source_qt_application_ui_screenshot",
                    "entries": [
                        {
                            "base": "LB26001-A-04-006",
                            "ui_screenshot": {"path": str(screenshot), "pass": True},
                            "generated_png_evidence": {
                                "strict_source_pass": True,
                                "under_run_dir": True,
                                "under_legacy_v5": False,
                            },
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        manual_review = root / "manual_visual_judgement.json"
        manual_review.write_text(
            json.dumps(
                {
                    "method": "application_drawing_review_ui_screenshot",
                    "overall_status": "PASS",
                    "visual_acceptance_pass": True,
                    "source_ui_report": str(ui_report),
                    "cases": [
                        {
                            "base": "LB26001-A-04-006",
                            "verdict": "PASS",
                            "visual_acceptance_pass": True,
                            "ui_screenshot": screenshot.name,
                            "visual_checklist": _visual_checklist(),
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = run_vision_qc_v6(
            png_path=png,
            run_dir=run_dir,
            blueprint_path=blueprint,
            manual_review_path=manual_review,
        )
        ui_review = result["checks"]["ui_screenshot_review"]
        keys = {issue["key"] for issue in result["issues"]}

        assert ui_review["pass"] is True
        assert ui_review["manual_review_method_ok"] is True
        assert ui_review["ui_screenshot_evidence_present"] is True
        assert ui_review["ui_screenshot_content_check_pass"] is True
        assert ui_review["ui_screenshot_paths_existing_application_ui"]
        assert ui_review["source_ui_report_application_ui_ok"] is True
        assert ui_review["source_ui_report_mode"] == "source_qt_application_ui_screenshot"
        assert ui_review["case_match"]["pass"] is True
        assert ui_review["case_match"]["visual_checklist_pass"] is True
        assert ui_review["generated_png_source_required"] is True
        assert ui_review["generated_png_source_pass"] is True
        assert "manual_ui_screenshot_review_required" not in keys


def test_vision_qc_v6_rejects_plain_png_claimed_as_application_screenshot() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_dir = root / "run"
        png = _draw_visual_png(root / "drawing.png")
        blueprint = _write_blueprint(run_dir / "qc" / "drawing_blueprint.json")
        screenshot = root / "01_LB26001-A-04-006_ui_visual_review.png"
        _draw_visual_png(screenshot)
        ui_report = root / "drawing_visual_review_report.json"
        ui_report.write_text(
            json.dumps(
                {
                    "schema": "sw_drawing_studio.drawing_visual_review_ui.v1",
                    "mode": "source_qt_application_ui_screenshot",
                    "entries": [
                        {
                            "base": "LB26001-A-04-006",
                            "ui_screenshot": {"path": str(screenshot), "pass": True},
                            "generated_png_evidence": {
                                "strict_source_pass": True,
                                "under_run_dir": True,
                                "under_legacy_v5": False,
                            },
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        manual_review = root / "manual_visual_judgement.json"
        manual_review.write_text(
            json.dumps(
                {
                    "method": "application_drawing_review_ui_screenshot",
                    "overall_status": "PASS",
                    "visual_acceptance_pass": True,
                    "source_ui_report": str(ui_report),
                    "cases": [
                        {
                            "base": "LB26001-A-04-006",
                            "verdict": "PASS",
                            "visual_acceptance_pass": True,
                            "ui_screenshot": screenshot.name,
                            "visual_checklist": _visual_checklist(),
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = run_vision_qc_v6(
            png_path=png,
            run_dir=run_dir,
            blueprint_path=blueprint,
            manual_review_path=manual_review,
        )
        ui_review = result["checks"]["ui_screenshot_review"]
        keys = {issue["key"] for issue in result["issues"]}

        assert ui_review["pass"] is False
        assert ui_review["ui_screenshot_evidence_present"] is True
        assert ui_review["ui_screenshot_content_check_pass"] is False
        assert "manual_ui_screenshot_review_required" in keys


def test_vision_qc_v6_infers_generated_png_source_from_legacy_ui_report_paths() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_dir = root / "run"
        png = run_dir / "drawing" / "LB26001-A-04-006_v5.PNG"
        png.parent.mkdir(parents=True)
        _draw_visual_png(png)
        blueprint = _write_blueprint(run_dir / "qc" / "drawing_blueprint.json")
        screenshot = root / "01_LB26001-A-04-006_ui_visual_review.png"
        _draw_application_ui_screenshot(screenshot)
        ui_report = root / "drawing_visual_review_report.json"
        ui_report.write_text(
            json.dumps(
                {
                    "schema": "sw_drawing_studio.drawing_visual_review_ui.v1",
                    "mode": "source_qt_application_ui_screenshot",
                    "entries": [
                        {
                            "base": "LB26001-A-04-006",
                            "run_dir": str(run_dir),
                            "generated_png": str(png),
                            "ui_screenshot": {"path": str(screenshot), "pass": True},
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        manual_review = root / "manual_visual_judgement.json"
        manual_review.write_text(
            json.dumps(
                {
                    "method": "application_drawing_review_ui_screenshot",
                    "overall_status": "PASS",
                    "visual_acceptance_pass": True,
                    "source_ui_report": str(ui_report),
                    "cases": [
                        {
                            "base": "LB26001-A-04-006",
                            "verdict": "PASS",
                            "visual_acceptance_pass": True,
                            "ui_screenshot": str(screenshot),
                            "visual_checklist": _visual_checklist(),
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = run_vision_qc_v6(
            png_path=png,
            run_dir=run_dir,
            blueprint_path=blueprint,
            manual_review_path=manual_review,
        )
        ui_review = result["checks"]["ui_screenshot_review"]

        assert ui_review["pass"] is True
        assert ui_review["generated_png_source_required"] is True
        assert ui_review["generated_png_source_pass"] is True
        assert ui_review["generated_png_source_evidence"]["source"] == "drawing_visual_review_report_path_inference"
        assert ui_review["generated_png_source_evidence"]["under_run_dir"] is True
        assert ui_review["generated_png_source_evidence"]["under_legacy_v5"] is False


def test_vision_qc_v6_rejects_manual_pass_without_per_drawing_visual_checklist() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_dir = root / "run"
        png = _draw_visual_png(root / "drawing.png")
        blueprint = _write_blueprint(run_dir / "qc" / "drawing_blueprint.json")
        screenshot = root / "01_LB26001-A-04-006_ui_visual_review.png"
        _draw_application_ui_screenshot(screenshot)
        ui_report = root / "drawing_visual_review_report.json"
        ui_report.write_text(
            json.dumps(
                {
                    "schema": "sw_drawing_studio.drawing_visual_review_ui.v1",
                    "mode": "source_qt_application_ui_screenshot",
                    "entries": [
                        {
                            "base": "LB26001-A-04-006",
                            "ui_screenshot": {"path": str(screenshot), "pass": True},
                            "generated_png_evidence": {
                                "strict_source_pass": True,
                                "under_run_dir": True,
                                "under_legacy_v5": False,
                            },
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        manual_review = root / "manual_visual_judgement.json"
        manual_review.write_text(
            json.dumps(
                {
                    "method": "application_drawing_review_ui_screenshot",
                    "overall_status": "PASS",
                    "visual_acceptance_pass": True,
                    "source_ui_report": str(ui_report),
                    "cases": [
                        {
                            "base": "LB26001-A-04-006",
                            "verdict": "PASS",
                            "visual_acceptance_pass": True,
                            "ui_screenshot": screenshot.name,
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = run_vision_qc_v6(
            png_path=png,
            run_dir=run_dir,
            blueprint_path=blueprint,
            manual_review_path=manual_review,
        )
        ui_review = result["checks"]["ui_screenshot_review"]
        keys = {issue["key"] for issue in result["issues"]}

        assert result["visual_acceptance_pass"] is False
        assert ui_review["pass"] is False
        assert ui_review["case_match"]["manual_case_status_pass"] is True
        assert ui_review["case_match"]["visual_checklist_pass"] is False
        assert set(ui_review["case_match"]["missing_visual_checklist_items"]) == set(_visual_checklist())
        assert "manual_ui_screenshot_review_required" in keys


def test_vision_qc_v6_infers_base_for_ui_case_match_without_blueprint() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_dir = root / "run"
        png = _draw_visual_png(root / "LB26001-A-04-006_v5.PNG")
        screenshot = root / "01_LB26001-A-04-006_ui_visual_review.png"
        _draw_application_ui_screenshot(screenshot)
        ui_report = root / "drawing_visual_review_report.json"
        ui_report.write_text(
            json.dumps(
                {
                    "schema": "sw_drawing_studio.drawing_visual_review_ui.v1",
                    "mode": "source_qt_application_ui_screenshot",
                    "entries": [
                        {
                            "base": "LB26001-A-04-006",
                            "ui_screenshot": {"path": str(screenshot), "pass": True},
                            "generated_png_evidence": {
                                "strict_source_pass": True,
                                "under_run_dir": True,
                                "under_legacy_v5": False,
                            },
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        manual_review = root / "manual_visual_judgement.json"
        manual_review.write_text(
            json.dumps(
                {
                    "method": "application_drawing_review_ui_screenshot",
                    "overall_status": "FAIL",
                    "visual_acceptance_pass": False,
                    "source_ui_report": str(ui_report),
                    "entries": [
                        {
                            "base": "LB26001-A-04-006",
                            "manual_status": "FAIL",
                            "visual_acceptance_pass": False,
                            "ui_screenshot": str(screenshot),
                            "visual_checklist": {key: False for key in _visual_checklist()},
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = run_vision_qc_v6(
            png_path=png,
            run_dir=run_dir,
            blueprint_path=None,
            manual_review_path=manual_review,
        )
        ui_review = result["checks"]["ui_screenshot_review"]
        keys = {issue["key"] for issue in result["issues"]}

        assert result["base"] == "LB26001-A-04-006"
        assert result["visual_acceptance_pass"] is False
        assert "drawing_blueprint_missing" in keys
        assert ui_review["pass"] is False
        assert ui_review["case_match"]["pass"] is False
        assert ui_review["case_match"]["manual_case_status_pass"] is False
        assert ui_review["case_match"]["visual_checklist_pass"] is False
        assert ui_review["case_match"]["missing_visual_checklist_items"] == []
        assert set(ui_review["case_match"]["failed_visual_checklist_items"]) == set(_visual_checklist())
        assert set(ui_review["case_match"]["not_passed_visual_checklist_items"]) == set(_visual_checklist())
        assert ui_review["generated_png_source_required"] is True


def test_vision_qc_v6_rejects_manual_pass_without_drawing_review_ui_report_source() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_dir = root / "run"
        png = _draw_visual_png(root / "drawing.png")
        blueprint = _write_blueprint(run_dir / "qc" / "drawing_blueprint.json")
        screenshot = root / "01_LB26001-A-04-006_ui_visual_review.png"
        _draw_application_ui_screenshot(screenshot)
        ui_report = root / "drawing_visual_review_report.json"
        ui_report.write_text(
            json.dumps(
                {
                    "schema": "generic.visual_report",
                    "mode": "api_metric_export",
                    "entries": [
                        {
                            "base": "LB26001-A-04-006",
                            "ui_screenshot": {"path": str(screenshot), "pass": True},
                            "generated_png_evidence": {
                                "strict_source_pass": True,
                                "under_run_dir": True,
                                "under_legacy_v5": False,
                            },
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        manual_review = root / "manual_visual_judgement.json"
        manual_review.write_text(
            json.dumps(
                {
                    "method": "application_drawing_review_ui_screenshot",
                    "overall_status": "PASS",
                    "visual_acceptance_pass": True,
                    "source_ui_report": str(ui_report),
                    "cases": [
                        {
                            "base": "LB26001-A-04-006",
                            "verdict": "PASS",
                            "visual_acceptance_pass": True,
                            "ui_screenshot": screenshot.name,
                            "visual_checklist": _visual_checklist(),
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = run_vision_qc_v6(
            png_path=png,
            run_dir=run_dir,
            blueprint_path=blueprint,
            manual_review_path=manual_review,
        )
        ui_review = result["checks"]["ui_screenshot_review"]
        keys = {issue["key"] for issue in result["issues"]}

        assert result["visual_acceptance_pass"] is False
        assert ui_review["pass"] is False
        assert ui_review["ui_screenshot_evidence_present"] is True
        assert ui_review["source_ui_report_exists"] is True
        assert ui_review["source_ui_report_application_ui_ok"] is False
        assert "manual_ui_screenshot_review_required" in keys


def test_vision_qc_v6_rejects_manual_pass_with_stale_generated_png_source() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_dir = root / "run"
        png = _draw_visual_png(root / "drawing.png")
        blueprint = _write_blueprint(run_dir / "qc" / "drawing_blueprint.json")
        screenshot = root / "01_LB26001-A-04-006_ui_visual_review.png"
        _draw_application_ui_screenshot(screenshot)
        ui_report = root / "drawing_visual_review_report.json"
        ui_report.write_text(
            json.dumps(
                {
                    "schema": "sw_drawing_studio.drawing_visual_review_ui.v1",
                    "mode": "source_qt_application_ui_screenshot",
                    "entries": [
                        {
                            "base": "LB26001-A-04-006",
                            "ui_screenshot": {"path": str(screenshot), "pass": True},
                            "generated_png_evidence": {
                                "strict_source_pass": False,
                                "under_run_dir": False,
                                "under_legacy_v5": True,
                                "reasons": ["legacy_drw_output_v5_png_not_allowed_for_lb26001_ui_acceptance"],
                            },
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        manual_review = root / "manual_visual_judgement.json"
        manual_review.write_text(
            json.dumps(
                {
                    "method": "application_drawing_review_ui_screenshot",
                    "overall_status": "PASS",
                    "visual_acceptance_pass": True,
                    "source_ui_report": str(ui_report),
                    "cases": [
                        {
                            "base": "LB26001-A-04-006",
                            "verdict": "PASS",
                            "visual_acceptance_pass": True,
                            "ui_screenshot": str(screenshot),
                            "visual_checklist": _visual_checklist(),
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = run_vision_qc_v6(
            png_path=png,
            run_dir=run_dir,
            blueprint_path=blueprint,
            manual_review_path=manual_review,
        )
        ui_review = result["checks"]["ui_screenshot_review"]
        keys = {issue["key"] for issue in result["issues"]}

        assert result["visual_acceptance_pass"] is False
        assert ui_review["pass"] is False
        assert ui_review["generated_png_source_required"] is True
        assert ui_review["generated_png_source_pass"] is False
        assert ui_review["generated_png_source_evidence"]["under_legacy_v5"] is True
        assert "manual_ui_screenshot_review_required" in keys


def test_cad_worker_invokes_vision_qc_v6() -> None:
    source = Path("app/workers/cad_job_worker.py").read_text(encoding="utf-8")

    assert "run_vision_qc_v6" in source
    assert "vision_qc_v6.json" in source
    assert "vision_qc_v6_visual_acceptance_pass" in source


if __name__ == "__main__":
    test_vision_qc_v6_flags_blank_png_and_keeps_required_issue_fields()
    test_titlebar_and_notes_detectors_use_sheet_to_image_coordinate_conversion()
    test_vision_qc_v6_rejects_default_titleblock_artifacts_when_reference_policy_strips_template()
    test_vision_qc_v6_rejects_clustered_reference_dimensions_as_unreadable()
    test_vision_qc_v6_rejects_reference_grid_mismatch_even_when_bbox_matches()
    test_vision_qc_v6_records_blueprint_and_supporting_api_as_non_final_evidence()
    test_vision_qc_v6_rejects_manual_pass_without_application_screenshot_evidence()
    test_vision_qc_v6_accepts_manual_pass_with_application_screenshot_evidence()
    test_vision_qc_v6_rejects_plain_png_claimed_as_application_screenshot()
    test_vision_qc_v6_infers_generated_png_source_from_legacy_ui_report_paths()
    test_vision_qc_v6_rejects_manual_pass_without_per_drawing_visual_checklist()
    test_vision_qc_v6_infers_base_for_ui_case_match_without_blueprint()
    test_vision_qc_v6_rejects_manual_pass_without_drawing_review_ui_report_source()
    test_vision_qc_v6_rejects_manual_pass_with_stale_generated_png_source()
    test_cad_worker_invokes_vision_qc_v6()
    print("PASS test_v4_vision_qc_v6")
