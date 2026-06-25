import json
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.validation.manual_visual_judgement_template_v4 import (
    REQUIRED_VISUAL_CHECKS,
    build_manual_visual_judgement_template,
    write_manual_visual_judgement_template,
)


def test_manual_visual_judgement_template_is_pending_and_checklist_complete() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        ui_report_path = root / "drawing_visual_review_report.json"
        screenshot = root / "screenshots" / "006.png"
        screenshot.parent.mkdir()
        screenshot.write_bytes(b"fake-png")
        report = {
            "schema": "sw_drawing_studio.drawing_visual_review_ui.v1",
            "mode": "source_qt_application_ui_screenshot",
            "entries": [
                {
                    "base": "LB26001-A-04-006",
                    "ui_screenshot": {"path": str(screenshot), "pass": True},
                    "reference_png": str(root / "reference.png"),
                    "generated_png": str(root / "generated.png"),
                    "comparison_png": {"path": str(root / "comparison.png")},
                }
            ],
        }

        payload = build_manual_visual_judgement_template(
            ui_report=report,
            ui_report_path=ui_report_path,
        )

    assert payload["schema"] == "sw_drawing_studio.manual_visual_judgement.v4_2.template"
    assert payload["overall_status"] == "PENDING_MANUAL_REVIEW"
    assert payload["visual_acceptance_pass"] is False
    assert payload["source_ui_report"] == str(ui_report_path)
    assert payload["api_only_acceptance_allowed"] is False
    assert payload["required_visual_checklist_items"] == list(REQUIRED_VISUAL_CHECKS)
    assert len(payload["entries"]) == 1
    entry = payload["entries"][0]
    assert entry["base"] == "LB26001-A-04-006"
    assert entry["manual_status"] == "PENDING"
    assert entry["visual_acceptance_pass"] is False
    assert entry["ui_screenshot"] == str(screenshot)
    assert entry["visual_checklist"] == {key: None for key in REQUIRED_VISUAL_CHECKS}
    assert entry["api_only_acceptance_allowed"] is False


def test_manual_visual_judgement_template_can_filter_bases_and_write_file() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        ui_report_path = root / "drawing_visual_review_report.json"
        out = root / "manual_visual_judgement_template.json"
        report = {
            "entries": [
                {"base": "LB26001-A-04-006", "ui_screenshot": {"path": "006.png"}},
                {"base": "LB26001-A-04-007", "ui_screenshot": {"path": "007.png"}},
            ]
        }

        payload = write_manual_visual_judgement_template(
            ui_report=report,
            ui_report_path=ui_report_path,
            out_path=out,
            bases=["LB26001-A-04-007"],
        )
        assert out.exists()
        written = json.loads(out.read_text(encoding="utf-8"))

    assert [item["base"] for item in payload["entries"]] == ["LB26001-A-04-007"]
    assert [item["base"] for item in written["entries"]] == ["LB26001-A-04-007"]
    assert written["entries"][0]["visual_checklist"] == {key: None for key in REQUIRED_VISUAL_CHECKS}


if __name__ == "__main__":
    test_manual_visual_judgement_template_is_pending_and_checklist_complete()
    test_manual_visual_judgement_template_can_filter_bases_and_write_file()
    print("PASS test_v4_2_manual_visual_judgement_template")
