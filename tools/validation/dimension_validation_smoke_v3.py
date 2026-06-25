"""v3.0 2D annotation validation smoke.

Reads the fresh Real CAD Smoke run and writes dimension_validation_smoke.json.
The validator reports source separation explicitly and does not count Note text
as SolidWorks DisplayDim evidence.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
DEFAULT_CAD_SMOKE = REPO_ROOT / "drw_output" / "cad_smoke_v3_0.json"
DEFAULT_OUT = REPO_ROOT / "drw_output" / "dimension_validation_smoke.json"
PURCHASE_CLASSES = {"fastener", "spring", "purchased_part"}
SIDECAR_ALLOWED_CLASSES = {"long_thin", "tiny_part"}
REAL_DISPLAY_DIM_COUNT_SOURCES = {"display_dimension_api", "annotation_type1"}
STRICT_REFERENCE_INTENT_BASES = {
    "LB26001-A-04-006",
    "LB26001-A-04-007",
    "LB26001-A-04-008",
    "LB26001-A-04-009",
    "LB26001-A-04-015",
    "LB26001-A-04-022",
}
MetricsRunner = Callable[[Path, str], dict[str, Any]]


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _find_first(run_dir: Path, patterns: list[str]) -> Path | None:
    for pattern in patterns:
        for path in sorted(run_dir.glob(pattern)):
            if path.is_file():
                return path
    return None


def _bool(value: Any) -> bool:
    return bool(value is True or (isinstance(value, (int, float)) and value > 0))


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


def _drawing_base_from_path(path: Path | None) -> str:
    if not path:
        return ""
    stem = path.stem
    return stem[:-3] if stem.endswith("_v5") else stem


def _is_strict_reference_intent_dimension_case(
    base: str,
    *,
    qc: dict[str, Any] | None = None,
    manifest: dict[str, Any] | None = None,
    run_dir: Path | None = None,
) -> bool:
    if base in STRICT_REFERENCE_INTENT_BASES:
        return True
    qc = qc or {}
    manifest = manifest or {}
    if bool(qc.get("ui_screenshot_review_is_final_gate") or manifest.get("ui_screenshot_review_is_final_gate")):
        return True
    blueprint = _read_json(run_dir / "qc" / "drawing_blueprint.json") if run_dir else {}
    targets = blueprint.get("dimension_targets") or []
    reasons = blueprint.get("reasons") or []
    return bool(targets or "ui_screenshot_is_final_visual_gate" in reasons)


def _default_metrics_runner(drawing_path: Path, label: str) -> dict[str, Any]:
    from tools.validation.reference_compare_smoke_v3 import _run_reference_metrics_sidecar

    return _run_reference_metrics_sidecar(drawing_path, label, timeout_s=180)


def _upgrade_display_dim_count_from_real_metrics(
    drawing_path: Path | None,
    current_count: int,
    *,
    metrics_runner: MetricsRunner | None = None,
) -> tuple[int, dict[str, Any]]:
    evidence: dict[str, Any] = {
        "attempted": False,
        "accepted": False,
        "reason": "",
    }
    if current_count > 0:
        evidence["reason"] = "display_dim_count_already_available"
        return current_count, evidence
    if not drawing_path:
        evidence["reason"] = "drawing_path_missing"
        return current_count, evidence

    runner = metrics_runner or _default_metrics_runner
    label = f"{drawing_path.stem}_dimension_validation"
    evidence.update({
        "attempted": True,
        "drawing": str(drawing_path),
        "label": label,
    })
    try:
        metrics = runner(drawing_path, label)
    except Exception as exc:
        evidence["reason"] = f"reference_metrics_sidecar_exception: {exc}"
        return current_count, evidence

    metrics_count = _safe_int(metrics.get("display_dim_count"))
    metrics_source = str(metrics.get("display_dim_count_source") or "")
    evidence.update({
        "success": bool(metrics.get("success")),
        "source": str(metrics.get("source") or ""),
        "display_dim_count": metrics_count,
        "display_dim_count_source": metrics_source,
        "sidecar_report": str(metrics.get("sidecar_report") or metrics.get("annotation_probe_report") or ""),
        "returncode": metrics.get("returncode"),
        "reason": str(metrics.get("reason") or ""),
    })
    if not metrics.get("success"):
        if not evidence["reason"]:
            evidence["reason"] = "reference_metrics_sidecar_not_successful"
        return current_count, evidence
    if metrics_count <= current_count:
        evidence["reason"] = f"reference_metrics_display_dim_not_higher:{metrics_count}/{current_count}"
        return current_count, evidence
    if metrics_source not in REAL_DISPLAY_DIM_COUNT_SOURCES:
        evidence["reason"] = f"unsupported_display_dim_count_source:{metrics_source or 'missing'}"
        return current_count, evidence

    evidence["accepted"] = True
    evidence["reason"] = "accepted_real_display_dim_metrics"
    return metrics_count, evidence


def _has_sidecar_dimension_evidence(
    part_class: str,
    display_dim_count: int,
    note_dim_count: int,
    standard_annotation_count: int,
    coverage: dict[str, Any],
    warnings: list[str],
    dim_sources: dict[str, Any],
    *,
    allow_sidecar_policy: bool = True,
) -> tuple[bool, str]:
    if display_dim_count > 0:
        return True, "display_dim"

    if part_class in PURCHASE_CLASSES:
        if note_dim_count > 0 and standard_annotation_count > 0:
            return True, "procurement_standard_annotation"
        return False, "purchased_part_missing_standard_annotation"

    if part_class in SIDECAR_ALLOWED_CLASSES:
        if not allow_sidecar_policy:
            return False, "strict_reference_intent_display_dim_required"
        has_sidecar_warning = "dim_total_zero_with_sidecar_annotation" in warnings
        source_summary = " ".join(str(item) for item in dim_sources.get("sources_summary") or [])
        has_sidecar_source = "sidecar" in source_summary.lower()
        has_overall = any(coverage.get(key) is not None for key in ["overall_length", "overall_width", "overall_height"])
        if note_dim_count > 0 and has_overall and (has_sidecar_warning or has_sidecar_source):
            return True, "sidecar_key_dimension_annotation"
        return False, "sidecar_key_dimension_missing"

    return False, "display_dim_required"


def validate(run_dir: Path, out_path: Path, *, metrics_runner: MetricsRunner | None = None) -> dict[str, Any]:
    manifest = _read_json(run_dir / "manifest.json")
    qc_path = _find_first(run_dir, ["qc/*_qc.json"])
    qc = _read_json(qc_path) if qc_path else {}
    final_quality = _read_json(run_dir / "qc" / "final_quality.json")
    drawing_path = _find_first(run_dir, ["drawing/*.SLDDRW"])
    png_path = _find_first(run_dir, ["drawing/*.PNG", "drawing/*.png"])
    drawing_base = str(manifest.get("part_base") or _drawing_base_from_path(drawing_path) or "")

    checks = qc.get("checks") or {}
    coverage = checks.get("dimension_coverage") or {}
    dim_count = checks.get("dim_count_sufficient") or {}
    text_height = checks.get("text_height_ge_3_5mm") or {}
    dim_sources = qc.get("dimension_sources") or manifest.get("dimension_sources") or {}
    warnings = list(qc.get("warnings") or manifest.get("warnings") or [])
    hard_fail = list(qc.get("hard_fail") or manifest.get("hard_fail") or [])
    part_class = str(qc.get("part_class") or manifest.get("part_class") or "")
    strict_reference_intent_case = _is_strict_reference_intent_dimension_case(
        drawing_base,
        qc=qc,
        manifest=manifest,
        run_dir=run_dir,
    )

    raw_display_dim_count = _safe_int(qc.get("display_dim_count") or dim_sources.get("display_dim_count") or coverage.get("dim_total") or 0)
    display_dim_count, display_dim_metrics = _upgrade_display_dim_count_from_real_metrics(
        drawing_path,
        raw_display_dim_count,
        metrics_runner=metrics_runner,
    )
    addin_created_dim_count = _safe_int(qc.get("addin_dimension_count") or 0)
    existing_display_dim_count = max(0, display_dim_count - addin_created_dim_count)
    note_dim_count = _safe_int(qc.get("note_dim_count") or dim_sources.get("note_dim_count") or 0)
    model_associative_dim_count = _safe_int(qc.get("model_associative_dim_count") or 0)
    standard_annotation_count = 1 if _bool(qc.get("standard_annotation_present")) else 0

    threshold = _safe_int(dim_count.get("threshold") or 5)
    blocking_reasons: list[str] = []
    validation_warnings: list[str] = []
    display_dim_count_source = "qc.display_dim_count / dimension_sources.display_dim_count"
    if display_dim_metrics.get("accepted"):
        display_dim_count_source = "reference_metrics_sidecar.display_dim_count"
        validation_warnings.append("display_dim_count_from_reference_metrics_sidecar")

    if not qc_path or not qc:
        blocking_reasons.append("qc_json_missing")
    if not drawing_path:
        blocking_reasons.append("slddrw_missing")
    has_dimension_evidence, dimension_evidence_policy = _has_sidecar_dimension_evidence(
        part_class=part_class,
        display_dim_count=display_dim_count,
        note_dim_count=note_dim_count,
        standard_annotation_count=standard_annotation_count,
        coverage=coverage,
        warnings=warnings,
        dim_sources=dim_sources,
        allow_sidecar_policy=not strict_reference_intent_case,
    )

    if display_dim_count <= 0 and not has_dimension_evidence:
        blocking_reasons.append("display_dim_count_zero")
    if display_dim_count <= 0 and has_dimension_evidence:
        validation_warnings.append(f"display_dim_zero_allowed_by_policy:{dimension_evidence_policy}")
    if strict_reference_intent_case and dimension_evidence_policy == "strict_reference_intent_display_dim_required":
        validation_warnings.append("strict_reference_intent_sidecar_policy_disabled")
    if part_class in {"feature_part", "machined_part", ""} and display_dim_count < threshold:
        blocking_reasons.append(f"display_dim_count_below_threshold:{display_dim_count}/{threshold}")
    if hard_fail:
        blocking_reasons.extend([f"hard_fail:{item}" for item in hard_fail])
    if final_quality and final_quality.get("deliverable") is False:
        blocking_reasons.append(f"final_quality_not_deliverable:{final_quality.get('status')}")
    if note_dim_count > 0:
        validation_warnings.append("note_dimensions_present_not_counted_as_display_dim")
    if model_associative_dim_count <= 0:
        validation_warnings.append("model_associative_dim_count_zero")
    if "non_model_associative_dimension" in warnings:
        validation_warnings.append("non_model_associative_dimension")
    if standard_annotation_count == 0:
        validation_warnings.append("standard_annotation_missing")
    for key in ["has_tech_note", "has_ra_note", "has_datum_a", "gb_titlebar_complete", "gb_has_section_view_or_skipped", "titlebar_complete"]:
        if key in warnings:
            validation_warnings.append(key)

    dimension_validation = {
        "display_dim_count": display_dim_count,
        "raw_display_dim_count": raw_display_dim_count,
        "display_dim_count_source": display_dim_count_source,
        "display_dim_metrics": display_dim_metrics,
        "addin_created_dim_count": addin_created_dim_count,
        "existing_display_dim_count": existing_display_dim_count,
        "model_associative_dim_count": model_associative_dim_count,
        "note_dim_count": note_dim_count,
        "standard_annotation_count": standard_annotation_count,
        "overall_length": coverage.get("overall_length") is not None,
        "overall_width": coverage.get("overall_width") is not None,
        "overall_height": coverage.get("overall_height") is not None,
        "hole_diameter": coverage.get("hole_diameter") is not None,
        "hole_location": coverage.get("hole_location") is not None,
        "dimension_text_readable": text_height.get("pass") is True,
        "dimension_overlap": False if checks.get("view_overlap", {}).get("pass") is True else None,
        "dimension_grade": str(qc.get("dimension_grade") or manifest.get("dimension_grade") or ""),
        "usable_for": list(qc.get("usable_for") or manifest.get("usable_for") or []),
        "part_class": part_class,
        "drawing_base": drawing_base,
        "strict_reference_intent_case": strict_reference_intent_case,
        "sidecar_policy_allowed": not strict_reference_intent_case,
        "dimension_evidence_policy": dimension_evidence_policy,
        "has_dimension_evidence": has_dimension_evidence,
        "blocking_reasons": blocking_reasons,
        "warnings": sorted(set(validation_warnings)),
    }

    if blocking_reasons:
        status = "fail"
    elif validation_warnings:
        status = "pass_with_warning"
    else:
        status = "pass"

    payload = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "dimension_validation_smoke_v3",
        "run_dir": str(run_dir),
        "drawing": str(drawing_path or ""),
        "png": str(png_path or ""),
        "qc_json": str(qc_path or ""),
        "final_quality_path": str(run_dir / "qc" / "final_quality.json"),
        "source_separation": {
            "display_dim_source": display_dim_count_source,
            "raw_display_dim_source": "qc.display_dim_count / dimension_sources.display_dim_count",
            "note_dim_source": "qc.note_dim_count / dimension_sources.note_dim_count",
            "notes_counted_as_display_dim": False,
            "model_associative_source": "qc.model_associative_dim_count",
            "source_summary": dim_sources.get("sources_summary") or [],
            "display_dim_metrics": display_dim_metrics,
            "strict_reference_intent_case": strict_reference_intent_case,
            "sidecar_policy_allowed": not strict_reference_intent_case,
        },
        "dimension_validation": dimension_validation,
        "final_quality_status": final_quality.get("status", ""),
        "final_quality_deliverable": final_quality.get("deliverable"),
        "status": status,
        "pass": status in {"pass", "pass_with_warning"},
    }
    payload["reasons"] = blocking_reasons
    payload["fix_suggestions"] = [
        "Run Add-in Dimension / associative dimension generation for model_associative_dim_count_zero."
        if item == "model_associative_dim_count_zero" else
        "Add standard annotations or document why they are not required for the part class."
        if item == "standard_annotation_missing" else
        "Review warning and either fix the drawing or record human_review.json."
        for item in dimension_validation["warnings"]
    ]
    _write_json(out_path, payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run v3.0 dimension validation smoke on a Real CAD Smoke run.")
    parser.add_argument("--run-dir", default="", help="Run directory. Defaults to drw_output/cad_smoke_v3_0.json run_dir.")
    parser.add_argument("--cad-smoke", default=str(DEFAULT_CAD_SMOKE))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    cad_smoke = Path(args.cad_smoke)
    if not cad_smoke.is_absolute():
        cad_smoke = (REPO_ROOT / cad_smoke).resolve()
    run_dir = Path(args.run_dir) if args.run_dir else Path(str(_read_json(cad_smoke).get("run_dir") or ""))
    if not run_dir.is_absolute():
        run_dir = (REPO_ROOT / run_dir).resolve()
    out = Path(args.out)
    if not out.is_absolute():
        out = (REPO_ROOT / out).resolve()

    if not run_dir.exists():
        payload = {
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "mode": "dimension_validation_smoke_v3",
            "run_dir": str(run_dir),
            "status": "fail",
            "pass": False,
            "reasons": [f"run_dir not found: {run_dir}"],
            "fix_suggestions": ["Run Real CAD Smoke first and pass its run_dir to this validator."],
        }
        _write_json(out, payload)
        print(json.dumps({"pass": False, "report": str(out), "reasons": payload["reasons"]}, ensure_ascii=False))
        return 1

    payload = validate(run_dir, out)
    print(json.dumps({
        "pass": payload["pass"],
        "status": payload["status"],
        "report": str(out),
        "run_dir": payload["run_dir"],
        "reasons": payload.get("reasons", []),
    }, ensure_ascii=False))
    return 0 if payload["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
