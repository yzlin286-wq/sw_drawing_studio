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


DEFAULT_UI_DEFECT_BUCKETS = REPO_ROOT / "drw_output" / "diagnostics" / "lb26001_006_ui_defect_buckets_v4_4.json"


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


def _bucket_checklist_value(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, dict):
        for key in ("pass", "visual_acceptance_pass", "closed", "confirmed", "ok"):
            if key in value:
                return bool(value.get(key))
    return None


def _manual_bucket_closure_checklist(item: dict[str, Any]) -> dict[str, bool | None]:
    raw = (
        item.get("ui_defect_bucket_closure_checklist")
        or item.get("defect_bucket_closure_checklist")
        or item.get("bucket_closure_checklist")
        or item.get("ui_defect_bucket_closure")
        or item.get("bucket_closure")
        or {}
    )
    result: dict[str, bool | None] = {}
    if isinstance(raw, dict):
        for key, value in raw.items():
            bucket = str(key or "").strip()
            if bucket:
                result[bucket] = _bucket_checklist_value(value)
    elif isinstance(raw, list):
        for item_raw in raw:
            if not isinstance(item_raw, dict):
                continue
            bucket = str(item_raw.get("bucket") or item_raw.get("key") or "").strip()
            if bucket:
                result[bucket] = _bucket_checklist_value(item_raw)
    return result


def _ui_defect_bucket_closure_gate(
    *,
    base: str,
    manual_review: dict[str, Any],
    ui_defect_buckets: dict[str, Any],
) -> dict[str, Any]:
    # ui_defect_bucket_closure_review_gate:
    # A future 006 PASS must close every Drawing Review screenshot defect bucket
    # by manual/application-UI visual judgement. API metrics, DisplayDim counts,
    # and reference JSON are supporting evidence only.
    required_base = str(ui_defect_buckets.get("base") or "").strip()
    required = [
        str(item or "").strip()
        for item in (
            ui_defect_buckets.get("required_next_screenshot_check_buckets")
            or ui_defect_buckets.get("required_bucket_keys")
            or []
        )
        if str(item or "").strip()
    ]
    if not ui_defect_buckets or not required or (required_base and required_base != base):
        return {
            "ui_defect_bucket_closure_required": False,
            "ui_defect_bucket_closure_pass": True,
            "required_ui_defect_bucket_keys": [],
            "passed_ui_defect_bucket_keys": [],
            "missing_ui_defect_bucket_keys": [],
            "failed_ui_defect_bucket_keys": [],
            "bucket_closure_contract_count": 0,
            "api_or_displaydim_metric_alone_can_close": False,
        }

    entries = _matching_manual_entries(manual_review, base)
    merged: dict[str, bool | None] = {}
    for entry in entries:
        merged.update(_manual_bucket_closure_checklist(entry))
    passed = sorted(key for key in required if merged.get(key) is True)
    failed = sorted(key for key in required if key in merged and merged.get(key) is not True)
    missing = sorted(key for key in required if key not in merged)
    pass_gate = bool(required and not failed and not missing)
    return {
        "ui_defect_bucket_closure_required": True,
        "ui_defect_bucket_closure_pass": pass_gate,
        "required_ui_defect_bucket_keys": required,
        "passed_ui_defect_bucket_keys": passed,
        "missing_ui_defect_bucket_keys": missing,
        "failed_ui_defect_bucket_keys": failed,
        "bucket_closure_contract_count": len([
            item for item in ui_defect_buckets.get("bucket_closure_contract") or []
            if isinstance(item, dict)
        ]),
        "api_or_displaydim_metric_alone_can_close": False,
    }


def _canonical_entry(entry: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "ui_report_entry_pass": bool(entry.get("ui_report_entry_pass")),
        "manual_review_entry_screenshot_pass": bool(entry.get("manual_review_entry_screenshot_pass")),
        "ui_defect_bucket_closure_pass": (
            not bool(entry.get("ui_defect_bucket_closure_required"))
            or bool(entry.get("ui_defect_bucket_closure_pass"))
        ),
        "vision_qc_v6_visual_acceptance_pass": bool(entry.get("vision_qc_v6_visual_acceptance_pass")),
        "reference_compare_v4_pass": bool(entry.get("reference_compare_v4_pass")),
        "generated_png_source_pass": (
            not bool(entry.get("generated_png_source_required"))
            or bool(entry.get("generated_png_source_pass"))
        ),
    }
    passed = all(checks.values())
    blocking_keys: list[str] = []
    if not checks["ui_report_entry_pass"]:
        blocking_keys.append("ui_report_entry_not_pass")
    if not checks["manual_review_entry_screenshot_pass"]:
        blocking_keys.append("manual_review_screenshot_not_bound")
    if not checks["ui_defect_bucket_closure_pass"]:
        blocking_keys.append("ui_defect_bucket_closure_not_proven")
    if not checks["vision_qc_v6_visual_acceptance_pass"]:
        blocking_keys.append("vision_qc_v6_with_ui_not_pass")
    if not checks["reference_compare_v4_pass"]:
        blocking_keys.append("reference_compare_v4_with_ui_not_pass")
    if not checks["generated_png_source_pass"]:
        blocking_keys.append("generated_png_source_not_current_run")
    return {
        "base": entry.get("base"),
        "status": "pass" if passed else "need_review",
        "pass": passed,
        "visual_acceptance_pass": passed,
        "run_dir": entry.get("run_dir"),
        "case_dir": entry.get("case_dir"),
        "generated_png": entry.get("generated_png"),
        "application_ui_screenshot": entry.get("ui_report_entry_screenshot"),
        "vision_qc_v6_with_ui_review": entry.get("vision_qc_v6_with_ui_review"),
        "reference_compare_v4_with_ui_review": entry.get("reference_compare_v4_with_ui_review"),
        "checks": checks,
        "ui_defect_bucket_closure": {
            "required": bool(entry.get("ui_defect_bucket_closure_required")),
            "pass": bool(entry.get("ui_defect_bucket_closure_pass")),
            "required_bucket_keys": list(entry.get("required_ui_defect_bucket_keys") or []),
            "passed_bucket_keys": list(entry.get("passed_ui_defect_bucket_keys") or []),
            "missing_bucket_keys": list(entry.get("missing_ui_defect_bucket_keys") or []),
            "failed_bucket_keys": list(entry.get("failed_ui_defect_bucket_keys") or []),
            "bucket_closure_contract_count": entry.get("bucket_closure_contract_count"),
            "api_or_displaydim_metric_alone_can_close": False,
        },
        "blocking_issue_keys": blocking_keys,
        "reasons": list(entry.get("reasons") or []),
    }


def _canonical_ui_visual_review_payload(
    *,
    gate_payload: dict[str, Any],
    out_dir: Path,
) -> dict[str, Any]:
    entries = [_canonical_entry(entry) for entry in gate_payload.get("entries") or []]
    failed = [entry for entry in entries if not entry.get("pass")]
    blocking_keys: list[str] = []
    for entry in failed:
        for key in entry.get("blocking_issue_keys") or []:
            if key not in blocking_keys:
                blocking_keys.append(key)
    return {
        "schema": "sw_drawing_studio.ui_visual_review.v4_4",
        "generated_at": gate_payload.get("generated_at"),
        "review_method": "application_drawing_review_ui_screenshot",
        "status": "pass" if entries and not failed else "need_review",
        "pass": bool(entries and not failed),
        "visual_acceptance_pass": bool(entries and not failed),
        "api_is_not_final_judgement": True,
        "api_only_acceptance_allowed": False,
        "application_ui_screenshot_is_final_gate": True,
        "summary": gate_payload.get("summary"),
        "ui_report": gate_payload.get("ui_report"),
        "manual_review": gate_payload.get("manual_review"),
        "effective_manual_review": gate_payload.get("effective_manual_review"),
        "source_ui_report_injected": bool(gate_payload.get("source_ui_report_injected")),
        "gate_summary": str(out_dir / "ui_visual_review_gate_summary.json"),
        "total": len(entries),
        "pass_count": len(entries) - len(failed),
        "fail_count": len(failed),
        "blocking_issue_keys": blocking_keys,
        "entries": entries,
        "next_required_action": (
            "Fix the generated drawing and rerun the application Drawing Review UI screenshot review."
            if failed
            else "Use this UI visual review packet as screenshot-backed acceptance evidence."
        ),
    }


def apply_ui_visual_review(
    *,
    summary_path: Path,
    ui_report_path: Path,
    manual_review_path: Path,
    out_dir: Path,
    bases: list[str] | None = None,
    reference_profiles: Path = DEFAULT_REFERENCE_PROFILES_V4,
    ui_defect_buckets: Path | None = None,
) -> dict[str, Any]:
    summary = _read_json(summary_path)
    ui_report = _read_json(ui_report_path)
    manual_review = _read_json(manual_review_path)
    ui_defects = _read_json(ui_defect_buckets)
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
        bucket_closure_gate = _ui_defect_bucket_closure_gate(
            base=base,
            manual_review=effective_manual_review,
            ui_defect_buckets=ui_defects,
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
            **bucket_closure_gate,
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
    all_bucket_closure_pass = all(
        (not bool(item.get("ui_defect_bucket_closure_required")))
        or bool(item.get("ui_defect_bucket_closure_pass"))
        for item in entries
    )
    pass_gate = bool(
        entries
        and all_ui_entries_pass
        and all_manual_entries_pass
        and all_bucket_closure_pass
        and all_v6_pass
        and all_v4_pass
    )
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
        "ui_defect_bucket_closure_all_pass": all_bucket_closure_pass,
        "ui_defect_bucket_source": str(ui_defect_buckets) if ui_defect_buckets else "",
        "vision_qc_v6_all_pass": all_v6_pass,
        "reference_compare_v4_all_pass": all_v4_pass,
        "pass": pass_gate,
        "status": "pass" if pass_gate else "need_review",
        "api_is_not_final_judgement": True,
        "entries": entries,
    }
    _write_json(out_dir / "ui_visual_review_gate_summary.json", payload)
    canonical = _canonical_ui_visual_review_payload(gate_payload=payload, out_dir=out_dir)
    _write_json(out_dir / "ui_visual_review.json", canonical)
    payload["ui_visual_review"] = str(out_dir / "ui_visual_review.json")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply Drawing Review UI judgement to v6/v4 artifacts.")
    parser.add_argument("--summary", required=True)
    parser.add_argument("--ui-report", required=True)
    parser.add_argument("--manual-review", required=True)
    parser.add_argument("--out-dir", default="")
    parser.add_argument("--base", action="append", default=[], help="Limit to a drawing base. Repeat for multiple bases.")
    parser.add_argument("--reference-profiles", default=str(DEFAULT_REFERENCE_PROFILES_V4))
    parser.add_argument("--ui-defect-buckets", default=str(DEFAULT_UI_DEFECT_BUCKETS))
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
        ui_defect_buckets=Path(args.ui_defect_buckets) if args.ui_defect_buckets else None,
    )
    print(json.dumps({
        "pass": payload.get("pass"),
        "status": payload.get("status"),
        "total": payload.get("total"),
        "report": str(out_dir / "ui_visual_review_gate_summary.json"),
        "ui_visual_review": str(out_dir / "ui_visual_review.json"),
    }, ensure_ascii=False))
    return 0 if payload.get("pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
