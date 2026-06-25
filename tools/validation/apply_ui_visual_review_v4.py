"""Apply Drawing Review UI judgement to v6/v4 validation artifacts.

This tool consumes existing staged CAD artifacts, application UI screenshot
reports, and a manual visual judgement JSON. It never calls SolidWorks.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.reference_compare_v4 import compare_reference_v4
from app.services.vision_qc_v6 import run_vision_qc_v6
from tools.validation.staged_cad_validation_v3 import (
    DEFAULT_REFERENCE_PROFILES_V4,
    _find_blueprint,
    _find_qc_json,
    _find_reference_png,
    _generator_warnings_from_cad_report,
)


def _read_json(path: Path | None) -> dict[str, Any]:
    if not path:
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _manual_review_with_source_report(
    *,
    manual_review: dict[str, Any],
    manual_review_path: Path,
    ui_report_path: Path,
    out_dir: Path,
) -> Path:
    source = str(manual_review.get("source_ui_report") or manual_review.get("drawing_visual_review_report") or "").strip()
    if source:
        return manual_review_path

    derived = dict(manual_review)
    derived["source_ui_report"] = str(ui_report_path)
    derived["drawing_visual_review_report"] = str(ui_report_path)
    derived["source_manual_review"] = str(manual_review_path)
    derived["source_injected_by"] = "apply_ui_visual_review_v4"
    derived["source_injected_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    effective_path = out_dir / "manual_visual_judgement_with_source.json"
    _write_json(effective_path, derived)
    return effective_path


def _repo_path(value: str | Path | None, *, base_dir: Path | None = None) -> Path | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    path = Path(text)
    if path.is_absolute():
        return path
    if base_dir is not None:
        local = base_dir / path
        if local.exists():
            return local
    return (REPO_ROOT / path).resolve()


def _case_map(summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in summary.get("cases") or []:
        if not isinstance(item, dict):
            continue
        base = str(item.get("part_name") or Path(str(item.get("part") or "")).stem or "").strip()
        if not base:
            continue
        result[base] = item
    return result


def _ui_entry_map(ui_report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in ui_report.get("entries") or []:
        if not isinstance(item, dict):
            continue
        base = str(item.get("base") or "").strip()
        if base:
            result[base] = item
    return result


def _manual_bases(manual_review: dict[str, Any]) -> list[str]:
    bases: list[str] = []
    for key in ["cases", "entries"]:
        for item in manual_review.get(key) or []:
            if isinstance(item, dict):
                base = str(item.get("base") or "").strip()
                if base and base not in bases:
                    bases.append(base)
    return bases


def _resolve_bases(
    requested: list[str],
    summary_cases: dict[str, dict[str, Any]],
    ui_entries: dict[str, dict[str, Any]],
    manual_review: dict[str, Any],
) -> list[str]:
    if requested:
        return requested
    manual = _manual_bases(manual_review)
    if manual:
        return manual
    if ui_entries:
        return list(ui_entries)
    return list(summary_cases)


def _case_dir(case: dict[str, Any], summary_path: Path) -> Path:
    case_dir = _repo_path(case.get("case_dir"), base_dir=summary_path.parent)
    if case_dir is not None:
        return case_dir
    base = str(case.get("part_name") or "")
    return next(iter(sorted(summary_path.parent.glob(f"*_{base}"))), summary_path.parent / base)


def _run_dir(case: dict[str, Any]) -> Path:
    run_dir = _repo_path(case.get("run_dir"))
    return run_dir if run_dir is not None else Path("")


def _part_path(case: dict[str, Any], base: str) -> Path:
    part = _repo_path(case.get("part"))
    return part if part is not None else Path(f"{base}.SLDPRT")


def _entry_png(base: str, entry: dict[str, Any], run_dir: Path, ui_report_path: Path) -> Path:
    for key in ["generated_png", "generated_image", "source_png"]:
        path = _repo_path(entry.get(key), base_dir=ui_report_path.parent)
        if path is not None and path.exists():
            return path
    direct = run_dir / "drawing" / f"{base}_v5.PNG"
    if direct.exists():
        return direct
    hits = sorted((run_dir / "drawing").glob(f"{base}*.PNG")) + sorted((run_dir / "drawing").glob(f"{base}*.png"))
    return hits[0] if hits else direct


def _source_ui_report_application_ui_ok(ui_report: dict[str, Any]) -> bool:
    schema = str(ui_report.get("schema") or "").lower()
    mode = str(ui_report.get("mode") or "").lower()
    return (
        "drawing_visual_review_ui" in schema
        and "application" in mode
        and "screenshot" in mode
    )


def _entry_ui_screenshot_gate(
    *,
    entry: dict[str, Any],
    ui_report: dict[str, Any],
    ui_report_path: Path,
) -> dict[str, Any]:
    raw = entry.get("ui_screenshot") or entry.get("application_ui_screenshot") or entry.get("screenshot")
    explicit_capture_pass: Any = None
    if isinstance(raw, dict):
        screenshot_text = str(raw.get("path") or raw.get("file") or "")
        explicit_capture_pass = raw.get("pass")
    else:
        screenshot_text = str(raw or "")
    screenshot_path = _repo_path(screenshot_text, base_dir=ui_report_path.parent)
    screenshot_exists = bool(
        screenshot_path is not None
        and screenshot_path.exists()
        and screenshot_path.is_file()
        and screenshot_path.stat().st_size > 0
    )
    capture_pass = screenshot_exists and explicit_capture_pass is not False
    source_ok = _source_ui_report_application_ui_ok(ui_report)
    return {
        "ui_report_entry_present": bool(entry),
        "ui_report_application_ui_ok": source_ok,
        "ui_report_entry_screenshot": str(screenshot_path or screenshot_text),
        "ui_report_entry_screenshot_exists": screenshot_exists,
        "ui_report_entry_screenshot_capture_pass": capture_pass,
        "ui_report_entry_pass": bool(entry and source_ok and capture_pass),
    }


def _matching_manual_entries(manual_review: dict[str, Any], base: str) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for container_key in ["cases", "entries"]:
        for item in manual_review.get(container_key) or []:
            if isinstance(item, dict) and str(item.get("base") or "") == base:
                matches.append(item)
    return matches


def _manual_entry_screenshot_text(item: dict[str, Any]) -> str:
    for key in ["ui_screenshot", "application_ui_screenshot", "screenshot"]:
        value = item.get(key)
        if isinstance(value, dict):
            text = str(value.get("path") or value.get("file") or "")
        else:
            text = str(value or "")
        if text:
            return text
    return ""


def _resolved_key(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.resolve()).lower()
    except Exception:
        return str(path).lower()


def _manual_entry_screenshot_gate(
    *,
    base: str,
    manual_review: dict[str, Any],
    manual_review_path: Path,
    ui_entry_gate: dict[str, Any],
) -> dict[str, Any]:
    matches = _matching_manual_entries(manual_review, base)
    ui_screenshot = _repo_path(ui_entry_gate.get("ui_report_entry_screenshot"))
    ui_key = _resolved_key(ui_screenshot)
    manual_paths: list[str] = []
    manual_existing: list[str] = []
    mismatch_paths: list[str] = []
    missing_paths: list[str] = []
    for item in matches:
        text = _manual_entry_screenshot_text(item)
        if not text:
            missing_paths.append("")
            continue
        path = _repo_path(text, base_dir=manual_review_path.parent)
        manual_paths.append(str(path or text))
        exists = bool(path is not None and path.exists() and path.is_file() and path.stat().st_size > 0)
        if exists:
            manual_existing.append(str(path))
        else:
            missing_paths.append(str(path or text))
        if ui_key and _resolved_key(path) != ui_key:
            mismatch_paths.append(str(path or text))
    pass_gate = bool(
        matches
        and manual_paths
        and not missing_paths
        and not mismatch_paths
        and ui_entry_gate.get("ui_report_entry_pass")
    )
    return {
        "manual_review_entry_present": bool(matches),
        "manual_review_entry_count": len(matches),
        "manual_review_entry_screenshot_paths": manual_paths,
        "manual_review_entry_screenshot_paths_existing": manual_existing,
        "manual_review_entry_screenshot_missing_paths": missing_paths,
        "manual_review_entry_screenshot_mismatch_paths": mismatch_paths,
        "manual_review_screenshot_matches_ui_report_entry": bool(manual_paths and not mismatch_paths),
        "manual_review_entry_screenshot_pass": pass_gate,
    }


def apply_ui_visual_review(
    *,
    summary_path: Path,
    ui_report_path: Path,
    manual_review_path: Path,
    out_dir: Path,
    bases: list[str] | None = None,
    reference_profiles: Path = DEFAULT_REFERENCE_PROFILES_V4,
) -> dict[str, Any]:
    summary = _read_json(summary_path)
    ui_report = _read_json(ui_report_path)
    manual_review = _read_json(manual_review_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    effective_manual_review_path = _manual_review_with_source_report(
        manual_review=manual_review,
        manual_review_path=manual_review_path,
        ui_report_path=ui_report_path,
        out_dir=out_dir,
    )
    effective_manual_review = (
        manual_review
        if effective_manual_review_path == manual_review_path
        else _read_json(effective_manual_review_path)
    )
    cases = _case_map(summary)
    ui_entries = _ui_entry_map(ui_report)
    selected_bases = _resolve_bases(bases or [], cases, ui_entries, effective_manual_review)

    v6_dir = out_dir / "vision_qc_v6_with_ui_review"
    v4_dir = out_dir / "reference_compare_v4_with_ui_review"
    entries: list[dict[str, Any]] = []

    for base in selected_bases:
        case = cases.get(base) or {}
        entry = ui_entries.get(base) or {}
        ui_entry_gate = _entry_ui_screenshot_gate(
            entry=entry,
            ui_report=ui_report,
            ui_report_path=ui_report_path,
        )
        manual_entry_gate = _manual_entry_screenshot_gate(
            base=base,
            manual_review=effective_manual_review,
            manual_review_path=effective_manual_review_path,
            ui_entry_gate=ui_entry_gate,
        )
        case_dir = _case_dir(case, summary_path)
        run_dir = _run_dir(case)
        part = _part_path(case, base)
        cad_report = case_dir / "cad_smoke.json"
        dimension_report = case_dir / "dimension_validation.json"
        reference_report = case_dir / "reference_compare.json"
        reference_style_report = case_dir / "reference_style.json"
        generated_png = _entry_png(base, entry, run_dir, ui_report_path)

        v6_path = v6_dir / f"{base}.json"
        v6 = run_vision_qc_v6(
            png_path=generated_png,
            run_dir=run_dir,
            blueprint_path=_find_blueprint(run_dir, base),
            qc_json_path=_find_qc_json(run_dir, base),
            reference_png_path=_find_reference_png(part),
            manual_review_path=effective_manual_review_path,
            out_path=v6_path,
        )

        v4_path = v4_dir / f"{base}.json"
        v4 = compare_reference_v4(
            base=base,
            blueprint=_find_blueprint(run_dir, base),
            reference_profiles=reference_profiles,
            dimension_validation=dimension_report,
            vision_qc=v6_path,
            generator_warnings=_generator_warnings_from_cad_report(cad_report, run_dir, base),
            legacy_reference_compare=reference_report,
            legacy_reference_style=reference_style_report,
            out_path=v4_path,
        )

        if len(selected_bases) == 1:
            _write_json(out_dir / "vision_qc_v6_with_ui_review.json", v6)
            _write_json(out_dir / "reference_compare_v4_with_ui_review.json", v4)

        ui_review = (v6.get("checks") or {}).get("ui_screenshot_review") or {}
        entries.append({
            "base": base,
            "case_dir": str(case_dir),
            "run_dir": str(run_dir),
            "generated_png": str(generated_png),
            **ui_entry_gate,
            **manual_entry_gate,
            "vision_qc_v6_with_ui_review": str(v6_path),
            "vision_qc_v6_status": v6.get("status"),
            "vision_qc_v6_visual_acceptance_pass": bool(v6.get("visual_acceptance_pass")),
            "ui_screenshot_review_pass": bool(ui_review.get("pass")),
            "generated_png_source_required": bool(ui_review.get("generated_png_source_required")),
            "generated_png_source_pass": bool(ui_review.get("generated_png_source_pass")),
            "generated_png_source_evidence": ui_review.get("generated_png_source_evidence") or {},
            "reference_compare_v4_with_ui_review": str(v4_path),
            "reference_compare_v4_status": v4.get("status"),
            "reference_compare_v4_pass": bool(v4.get("pass")),
            "reasons": list(v6.get("reasons") or []) + list(v4.get("reasons") or []),
        })

    all_v6_pass = all(bool(item.get("vision_qc_v6_visual_acceptance_pass")) for item in entries)
    all_v4_pass = all(bool(item.get("reference_compare_v4_pass")) for item in entries)
    all_ui_entries_pass = all(bool(item.get("ui_report_entry_pass")) for item in entries)
    all_manual_entries_pass = all(bool(item.get("manual_review_entry_screenshot_pass")) for item in entries)
    payload = {
        "schema": "sw_drawing_studio.ui_visual_review_gate.v4",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "summary": str(summary_path),
        "ui_report": str(ui_report_path),
        "manual_review": str(manual_review_path),
        "effective_manual_review": str(effective_manual_review_path),
        "source_ui_report_injected": effective_manual_review_path != manual_review_path,
        "out_dir": str(out_dir),
        "total": len(entries),
        "ui_report_entries_all_pass": all_ui_entries_pass,
        "manual_review_entries_all_pass": all_manual_entries_pass,
        "vision_qc_v6_all_pass": all_v6_pass,
        "reference_compare_v4_all_pass": all_v4_pass,
        "pass": bool(entries and all_ui_entries_pass and all_manual_entries_pass and all_v6_pass and all_v4_pass),
        "status": "pass" if entries and all_ui_entries_pass and all_manual_entries_pass and all_v6_pass and all_v4_pass else "need_review",
        "api_is_not_final_judgement": True,
        "entries": entries,
    }
    _write_json(out_dir / "ui_visual_review_gate_summary.json", payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply Drawing Review UI judgement to v6/v4 artifacts.")
    parser.add_argument("--summary", required=True)
    parser.add_argument("--ui-report", required=True)
    parser.add_argument("--manual-review", required=True)
    parser.add_argument("--out-dir", default="")
    parser.add_argument("--base", action="append", default=[], help="Limit to a drawing base. Repeat for multiple bases.")
    parser.add_argument("--reference-profiles", default=str(DEFAULT_REFERENCE_PROFILES_V4))
    args = parser.parse_args()

    ui_report = Path(args.ui_report)
    out_dir = Path(args.out_dir) if args.out_dir else ui_report.parent
    payload = apply_ui_visual_review(
        summary_path=Path(args.summary),
        ui_report_path=ui_report,
        manual_review_path=Path(args.manual_review),
        out_dir=out_dir,
        bases=list(args.base or []),
        reference_profiles=Path(args.reference_profiles),
    )
    print(json.dumps({
        "pass": payload.get("pass"),
        "status": payload.get("status"),
        "total": payload.get("total"),
        "report": str(out_dir / "ui_visual_review_gate_summary.json"),
    }, ensure_ascii=False))
    return 0 if payload.get("pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
