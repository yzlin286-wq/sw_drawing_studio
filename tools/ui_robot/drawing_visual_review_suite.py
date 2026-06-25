from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen
from PySide6.QtWidgets import QApplication, QSplitter

from app.ui.main_window import MainWindow, PAGE_DRAWING_REVIEW
from app.services.generated_png_source_evidence import generated_png_source_evidence
from tools.ui_robot.human_simulator import (
    EventLogger,
    click_list_row,
    grab_widget,
    make_app,
    process_events,
)
from tools.validation.manual_visual_judgement_template_v4 import write_manual_visual_judgement_template


PRIMARY_BASE = "LB26001-A-04-006"
DEPENDENT_BASES = [
    "LB26001-A-04-007",
    "LB26001-A-04-008",
    "LB26001-A-04-009",
    "LB26001-A-04-015",
    "LB26001-A-04-022",
]
REFERENCE_SAMPLE_BASES = [PRIMARY_BASE, *DEPENDENT_BASES]
DEFAULT_BASES = [PRIMARY_BASE]


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _case_dirs(summary_path: Path) -> dict[str, dict[str, Any]]:
    summary = _load_json(summary_path)
    result: dict[str, dict[str, Any]] = {}
    for case in summary.get("cases") or []:
        base = str(case.get("part_name") or "").strip()
        if not base:
            continue
        run_name = Path(str(case.get("run_dir") or "")).name
        if not run_name:
            continue
        stage_root = summary_path.parent
        case_dir = next(iter(sorted(stage_root.glob(f"*_{base}"))), Path(str(case.get("case_dir") or "")))
        result[base] = {
            "run_dir": REPO_ROOT / "drw_output" / "runs" / run_name,
            "case_dir": case_dir if case_dir.is_absolute() else (REPO_ROOT / case_dir),
            "summary_case": case,
        }
    return result


def _find_generated_png(base: str, run_dir: Path) -> Path:
    candidates = [
        run_dir / "drawing" / f"{base}_v5.PNG",
        run_dir / "drawing" / f"{base}_v5.png",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    hits = sorted((run_dir / "drawing").glob(f"{base}*.PNG")) + sorted((run_dir / "drawing").glob(f"{base}*.png"))
    return hits[0] if hits else candidates[0]


def _generated_png_source_evidence(
    *,
    base: str,
    run_dir: Path,
    generated_png: Path,
    source: str,
) -> dict[str, Any]:
    return generated_png_source_evidence(
        base=base,
        run_dir=run_dir,
        generated_png=generated_png,
        source=source,
        repo_root=REPO_ROOT,
    )


def _find_reference_png(base: str) -> Path:
    candidates = [
        REPO_ROOT / "drw_output" / "case_library" / f"{base}.png",
        REPO_ROOT / "drw_output" / "case_library" / f"{base}.PNG",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def _scaled_rect(image: QImage, target: QRect) -> QRect:
    if image.isNull():
        return target
    scale = min(target.width() / max(1, image.width()), target.height() / max(1, image.height()))
    width = max(1, int(image.width() * scale))
    height = max(1, int(image.height() * scale))
    x = target.x() + (target.width() - width) // 2
    y = target.y() + (target.height() - height) // 2
    return QRect(x, y, width, height)


def _draw_fit_image(painter: QPainter, image: QImage, target: QRect, missing_label: str) -> None:
    painter.setPen(QPen(QColor("#d1d5db"), 2))
    painter.setBrush(QColor("#ffffff"))
    painter.drawRect(target)
    if image.isNull():
        painter.setPen(QColor("#991b1b"))
        painter.drawText(target, Qt.AlignmentFlag.AlignCenter, missing_label)
        return
    dest = _scaled_rect(image, target.adjusted(8, 8, -8, -8))
    painter.drawImage(dest, image)


def _compose_comparison_image(
    base: str,
    reference_png: Path,
    generated_png: Path,
    out_path: Path,
    support: dict[str, Any],
) -> dict[str, Any]:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    reference = QImage(str(reference_png))
    generated = QImage(str(generated_png))

    width = 1800
    height = 1200
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(QColor("#f8fafc"))

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    font = QFont("Microsoft YaHei", 18)
    font.setBold(True)
    painter.setFont(font)
    painter.setPen(QColor("#111827"))
    painter.drawText(QRect(30, 20, width - 60, 48), Qt.AlignmentFlag.AlignLeft, f"{base} visual drawing review")

    small = QFont("Microsoft YaHei", 10)
    painter.setFont(small)
    painter.setPen(QColor("#4b5563"))
    painter.drawText(
        QRect(30, 70, width - 60, 52),
        Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap,
        "Left: same-name reference drawing screenshot. Right: generated drawing screenshot. "
        "API metrics are supporting evidence only; final judgement must be made from this visual UI evidence.",
    )

    ref_title = QRect(35, 132, 820, 32)
    gen_title = QRect(945, 132, 820, 32)
    painter.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
    painter.setPen(QColor("#0f172a"))
    painter.drawText(ref_title, Qt.AlignmentFlag.AlignCenter, "Reference drawing")
    painter.drawText(gen_title, Qt.AlignmentFlag.AlignCenter, "Generated drawing")

    ref_rect = QRect(35, 170, 820, 820)
    gen_rect = QRect(945, 170, 820, 820)
    _draw_fit_image(painter, reference, ref_rect, f"Missing reference PNG:\n{reference_png}")
    _draw_fit_image(painter, generated, gen_rect, f"Missing generated PNG:\n{generated_png}")

    painter.setPen(QPen(QColor("#94a3b8"), 2))
    painter.drawLine(900, 145, 900, 1010)

    status = {
        "cad": support.get("cad_status", ""),
        "dimension": support.get("dimension_status", ""),
        "reference": support.get("reference_status", ""),
        "style": support.get("reference_style_status", ""),
    }
    status_text = " | ".join(f"{key}: {value or '-'}" for key, value in status.items())
    checks = [
        "Visual checklist: view count/type/layout, dimension placement/readability, title block, notes, border fit.",
        f"Supporting structured status: {status_text}",
        "Manual UI verdict is intentionally separated from API pass/fail.",
    ]
    painter.setFont(QFont("Microsoft YaHei", 11))
    painter.setPen(QColor("#111827"))
    y = 1025
    for line in checks:
        painter.drawText(QRect(40, y, width - 80, 32), Qt.AlignmentFlag.AlignLeft, line)
        y += 36

    painter.end()
    saved = image.save(str(out_path), "PNG", 100)
    return {
        "path": str(out_path),
        "saved": bool(saved),
        "width": image.width(),
        "height": image.height(),
        "reference_loaded": not reference.isNull(),
        "generated_loaded": not generated.isNull(),
    }


def _supporting_status(case_dir: Path, summary_case: dict[str, Any]) -> dict[str, Any]:
    dimension = _load_json(case_dir / "dimension_validation.json")
    reference = _load_json(case_dir / "reference_compare.json")
    style = _load_json(case_dir / "reference_style.json")
    return {
        "cad_status": summary_case.get("final_quality_status") or summary_case.get("status") or "",
        "dimension_status": dimension.get("status") or summary_case.get("dimension_status") or "",
        "reference_status": reference.get("status") or summary_case.get("reference_status") or "",
        "reference_style_status": style.get("status") or summary_case.get("reference_style_status") or "",
        "dimension_reasons": dimension.get("reasons") or [],
        "reference_reasons": reference.get("reasons") or [],
        "reference_style_reasons": style.get("reasons") or style.get("differences") or [],
    }


def _issues_for_case(base: str, support: dict[str, Any]) -> list[dict[str, Any]]:
    evidence = {
        "visual_scope": [
            "same-name reference screenshot vs generated screenshot",
            "view layout and drawing density",
            "dimension and note readability",
            "title block and border fit",
        ],
        "supporting_status": support,
        "api_is_not_final_judgement": True,
    }
    return [
        {
            "key": f"{base}_manual_visual_review_required",
            "severity": "major",
            "source": "ui_screenshot_visual_review",
            "confidence": 1.0,
            "description": "Review the UI screenshot side-by-side before accepting this drawing.",
            "evidence": evidence,
            "fix_suggestion": "If visual differences remain, fix generator layout/dimension rules and rerun a fresh drawing.",
            "auto_fix_available": False,
            "human_review": "pending_visual_judgement",
        }
    ]


def _parse_generated_png_overrides(values: list[str] | None) -> dict[str, Path]:
    overrides: dict[str, Path] = {}
    for value in values or []:
        if "=" not in value:
            continue
        base, path = value.split("=", 1)
        base = base.strip()
        path = path.strip()
        if base and path:
            overrides[base] = Path(path)
    return overrides


def _resolve_cli_bases(values: list[str] | None) -> list[str]:
    return list(values or DEFAULT_BASES)


def _expansion_gate_summary(bases: list[str]) -> dict[str, Any]:
    dependent_requested = [base for base in bases if base in DEPENDENT_BASES]
    return {
        "primary_base": PRIMARY_BASE,
        "default_scope": list(DEFAULT_BASES),
        "reference_sample_bases": list(REFERENCE_SAMPLE_BASES),
        "dependent_bases_requested": dependent_requested,
        "expansion_requested": bool(dependent_requested),
        "status": "learning_or_evidence_only_until_006_passes" if dependent_requested else "primary_006_only",
        "acceptance_rule": (
            "LB26001-A-04-006 must pass real CAD, strict v4 comparison, v6 visual QC, "
            "and application Drawing Review UI judgement before 007/008/009/015/022 enter acceptance."
        ),
    }


def run_visual_review(
    summary: Path,
    out_dir: Path,
    bases: list[str],
    generated_png_overrides: dict[str, Path] | None = None,
) -> dict[str, Any]:
    app = make_app()
    out_dir.mkdir(parents=True, exist_ok=True)
    logger = EventLogger(out_dir)
    screenshots_dir = out_dir / "screenshots"
    comparisons_dir = out_dir / "comparison_images"
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    comparisons_dir.mkdir(parents=True, exist_ok=True)

    cases = _case_dirs(summary)
    window = MainWindow()
    window.resize(2600, 1400)
    window.show()
    process_events(800)
    click_list_row(window.nav, PAGE_DRAWING_REVIEW, logger)
    page = window.drawing_review_page
    for splitter in page.findChildren(QSplitter):
        splitter.setSizes([320, 1580, 520])
    process_events(300)

    entries: list[dict[str, Any]] = []
    generated_png_overrides = generated_png_overrides or {}
    for index, base in enumerate(bases, start=1):
        case = cases.get(base, {})
        run_dir = Path(case.get("run_dir") or "")
        case_dir = Path(case.get("case_dir") or "")
        summary_case = dict(case.get("summary_case") or {})
        reference_png = _find_reference_png(base)
        generated_png_source = "run_dir"
        generated_png = _find_generated_png(base, run_dir)
        if base in generated_png_overrides:
            generated_png = generated_png_overrides[base]
            generated_png_source = "explicit_override"
        generated_png_evidence = _generated_png_source_evidence(
            base=base,
            run_dir=run_dir,
            generated_png=generated_png,
            source=generated_png_source,
        )
        support = _supporting_status(case_dir, summary_case)
        comparison_png = comparisons_dir / f"{index:02d}_{base}_reference_vs_generated.png"
        comparison_result = _compose_comparison_image(
            base,
            reference_png,
            generated_png,
            comparison_png,
            support,
        )

        page.set_context(
            png_path=str(comparison_png),
            run_dir=str(run_dir),
            run_id=run_dir.name,
        )
        page.set_preview_image(str(comparison_png))
        page.set_issues(_issues_for_case(base, support))
        page.issue_list.setCurrentRow(0)
        item = page.issue_list.item(0)
        if item is not None:
            page._on_issue_clicked(item)
        page.set_zoom(0.70)
        process_events(500)

        screenshot = grab_widget(
            window,
            screenshots_dir / f"{index:02d}_{base}_ui_visual_review.png",
            min_bytes=90_000,
            logger=logger,
        )
        entries.append(
            {
                "base": base,
                "run_dir": str(run_dir),
                "reference_png": str(reference_png),
                "generated_png": str(generated_png),
                "generated_png_source": generated_png_source,
                "generated_png_evidence": generated_png_evidence,
                "comparison_png": comparison_result,
                "ui_screenshot": screenshot,
                "application_ui_screenshot_review_required": True,
                "application_ui_screenshot_source": "Drawing Review page",
                "ui_screenshot_source": "source_qt_application_ui_screenshot",
                "ui_screenshot_is_final_gate": True,
                "api_only_acceptance_allowed": False,
                "supporting_status": support,
                "visual_verdict": "pending_manual_visual_judgement",
                "notes": [
                    "Screenshot captured from the application Drawing Review page.",
                    "Do not treat API pass/fail as the final drawing correctness decision.",
                ],
            }
        )
        logger.log(
            "drawing_visual_review_case",
            base,
            base=base,
            run_dir=str(run_dir),
            screenshot=screenshot.get("path"),
            screenshot_pass=screenshot.get("pass"),
        )

    window.close()
    QApplication.processEvents()

    screenshot_pass = all(bool(entry["ui_screenshot"].get("pass")) for entry in entries)
    image_inputs_loaded = all(
        bool(entry["comparison_png"].get("reference_loaded"))
        and bool(entry["comparison_png"].get("generated_loaded"))
        and bool(entry["generated_png_evidence"].get("strict_source_pass"))
        for entry in entries
    )
    evidence_capture_pass = bool(screenshot_pass and image_inputs_loaded)
    report = {
        "schema": "sw_drawing_studio.drawing_visual_review_ui.v1",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "source_qt_application_ui_screenshot",
        "summary": str(summary),
        "out_dir": str(out_dir),
        "generated_png_overrides": {base: str(path) for base, path in generated_png_overrides.items()},
        "total": len(entries),
        "screenshot_pass": screenshot_pass,
        "image_inputs_loaded": image_inputs_loaded,
        "evidence_capture_pass": evidence_capture_pass,
        "visual_acceptance_status": "pending_manual_visual_judgement",
        "visual_acceptance_pass": False,
        "pass": False,
        "per_drawing_application_ui_screenshot_required": True,
        "ui_screenshot_review_is_final_gate": True,
        "api_only_acceptance_allowed": False,
        "expansion_gate": _expansion_gate_summary(bases),
        "entries": entries,
        "remaining_gates": [
            "Manual visual judgement still must mark each drawing PASS/WARNING/FAIL.",
            "This is source-level application UI evidence, not EXE-level Windows robot evidence.",
            "LB26001-A-04-006 must pass before dependent LB26001 drawings enter acceptance.",
        ],
    }
    report_path = out_dir / "drawing_visual_review_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    manual_template_path = out_dir / "manual_visual_judgement_template.json"
    write_manual_visual_judgement_template(
        ui_report=report,
        ui_report_path=report_path,
        out_path=manual_template_path,
        bases=bases,
    )
    _write_markdown(report, out_dir / "drawing_visual_review_report_v3_0.md")
    logger.log(
        "drawing_visual_review_finished",
        "visual review screenshots captured",
        evidence_capture_pass=evidence_capture_pass,
        visual_acceptance_pass=False,
    )
    return report


def _write_markdown(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# Drawing Visual Review UI Evidence",
        "",
        f"- Generated at: {report.get('generated_at')}",
        f"- Mode: {report.get('mode')}",
        f"- Screenshot pass: {report.get('screenshot_pass')}",
        f"- Image inputs loaded: {report.get('image_inputs_loaded')}",
        f"- Evidence capture pass: {report.get('evidence_capture_pass')}",
        f"- Visual acceptance pass: {report.get('visual_acceptance_pass')}",
        "",
        "| Base | UI screenshot | Generated PNG | Generated source OK | Reference PNG | Visual verdict |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for entry in report.get("entries") or []:
        lines.append(
            "| {base} | {shot} | {gen} | {source_ok} | {ref} | {verdict} |".format(
                base=entry.get("base", ""),
                shot=entry.get("ui_screenshot", {}).get("path", ""),
                gen=entry.get("generated_png", ""),
                source_ok=entry.get("generated_png_evidence", {}).get("strict_source_pass", False),
                ref=entry.get("reference_png", ""),
                verdict=entry.get("visual_verdict", ""),
            )
        )
    lines.extend(
        [
            "",
            "## Remaining Gates",
            "",
        ]
    )
    for item in report.get("remaining_gates") or []:
        lines.append(f"- {item}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture Drawing Review UI screenshots for real generated drawings.")
    parser.add_argument(
        "--summary",
        default=str(REPO_ROOT / "drw_output" / "staged_validation" / "LB26001_ref6_current_20260622" / "summary.json"),
    )
    parser.add_argument(
        "--out-dir",
        default=str(REPO_ROOT / "drw_output" / "ui_acceptance" / f"LB26001_ref6_visual_review_{time.strftime('%Y%m%d_%H%M%S')}"),
    )
    parser.add_argument(
        "--base",
        action="append",
        dest="bases",
        help="Drawing base name. Repeat to override the 006-only default; dependent bases remain learning/evidence-only until 006 passes.",
    )
    parser.add_argument(
        "--generated-png",
        action="append",
        dest="generated_png",
        help="Explicit generated PNG override as BASE=PATH. Repeat per drawing.",
    )
    args = parser.parse_args()
    bases = _resolve_cli_bases(args.bases)
    generated_png_overrides = _parse_generated_png_overrides(args.generated_png)
    report = run_visual_review(Path(args.summary), Path(args.out_dir), bases, generated_png_overrides)
    print(
        json.dumps(
            {
                "evidence_capture_pass": report["evidence_capture_pass"],
                "visual_acceptance_pass": report["visual_acceptance_pass"],
                "report": str(Path(args.out_dir) / "drawing_visual_review_report.json"),
                "manual_visual_judgement_template": str(Path(args.out_dir) / "manual_visual_judgement_template.json"),
            },
            ensure_ascii=False,
        )
    )
    return 0 if report["evidence_capture_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
