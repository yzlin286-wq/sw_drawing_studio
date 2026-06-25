from tools.ui_robot.drawing_visual_review_suite import (
    DEFAULT_BASES,
    DEPENDENT_BASES,
    PRIMARY_BASE,
    REFERENCE_SAMPLE_BASES,
    REPO_ROOT,
    _expansion_gate_summary,
    _generated_png_source_evidence,
    _resolve_cli_bases,
)
from pathlib import Path
from tempfile import TemporaryDirectory


def test_drawing_visual_review_defaults_to_006_only() -> None:
    assert PRIMARY_BASE == "LB26001-A-04-006"
    assert DEFAULT_BASES == [PRIMARY_BASE]
    assert _resolve_cli_bases(None) == [PRIMARY_BASE]
    assert _resolve_cli_bases([]) == [PRIMARY_BASE]
    assert set(DEPENDENT_BASES) == {
        "LB26001-A-04-007",
        "LB26001-A-04-008",
        "LB26001-A-04-009",
        "LB26001-A-04-015",
        "LB26001-A-04-022",
    }
    assert REFERENCE_SAMPLE_BASES == [PRIMARY_BASE, *DEPENDENT_BASES]


def test_drawing_visual_review_marks_dependent_bases_as_learning_until_006_passes() -> None:
    summary = _expansion_gate_summary([PRIMARY_BASE, "LB26001-A-04-007"])

    assert summary["expansion_requested"] is True
    assert summary["dependent_bases_requested"] == ["LB26001-A-04-007"]
    assert summary["status"] == "learning_or_evidence_only_until_006_passes"
    assert "006 must pass" in summary["acceptance_rule"]


def test_drawing_visual_review_rejects_legacy_v5_png_for_lb26001_acceptance() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_dir = root / "drw_output" / "runs" / "fresh_run"
        fresh_png = run_dir / "drawing" / f"{PRIMARY_BASE}_v5.PNG"
        fresh_png.parent.mkdir(parents=True)
        fresh_png.write_bytes(b"fresh-png")

        legacy_png = REPO_ROOT / "drw_output" / "v5" / f"{PRIMARY_BASE}_v5.PNG"

        fresh = _generated_png_source_evidence(
            base=PRIMARY_BASE,
            run_dir=run_dir,
            generated_png=fresh_png,
            source="run_dir",
        )
        legacy = _generated_png_source_evidence(
            base=PRIMARY_BASE,
            run_dir=run_dir,
            generated_png=legacy_png,
            source="explicit_override",
        )

    assert fresh["strict_source_pass"] is True
    assert fresh["under_run_dir"] is True
    assert legacy["strict_source_pass"] is False
    assert legacy["under_legacy_v5"] is True
    assert "legacy_drw_output_v5_png_not_allowed_for_lb26001_ui_acceptance" in legacy["reasons"]


def test_drawing_visual_review_report_declares_application_ui_screenshot_final_gate() -> None:
    source = (REPO_ROOT / "tools" / "ui_robot" / "drawing_visual_review_suite.py").read_text(encoding="utf-8")

    assert '"per_drawing_application_ui_screenshot_required": True' in source
    assert '"ui_screenshot_review_is_final_gate": True' in source
    assert '"api_only_acceptance_allowed": False' in source
    assert '"application_ui_screenshot_source": "Drawing Review page"' in source
    assert 'manual_visual_judgement_template.json' in source
    assert 'write_manual_visual_judgement_template' in source


if __name__ == "__main__":
    test_drawing_visual_review_defaults_to_006_only()
    test_drawing_visual_review_marks_dependent_bases_as_learning_until_006_passes()
    test_drawing_visual_review_rejects_legacy_v5_png_for_lb26001_acceptance()
    test_drawing_visual_review_report_declares_application_ui_screenshot_final_gate()
    print("PASS test_v4_2_drawing_visual_review_suite")
