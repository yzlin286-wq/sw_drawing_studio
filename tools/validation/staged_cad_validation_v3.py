"""v3.0 staged real CAD validation.

This orchestrates real CAD jobs through the existing validator scripts. It does
not touch original CAD files and does not relax QC thresholds. Each case writes
its own CAD, dimension, and reference comparison reports, then the stage summary
records deliverability and failure buckets.
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.sw_connection_guard import check_sw_connection_guard, write_sw_connection_guard
from app.services.sw_safe_restart_workflow import build_safe_restart_workflow, write_safe_restart_workflow
from tools.validation.reference_style_profile_v3 import evaluate_generated_against_reference
from app.services.reference_compare_v4 import compare_reference_v4
from app.services.vision_qc_v6 import run_vision_qc_v6
from tools.validation.lb26001_006_displaydim_lifecycle_audit_v4_2 import (
    DEFAULT_REFERENCE_INTENT_PLAN as DEFAULT_LB26001_006_LIFECYCLE_REFERENCE_INTENT_PLAN,
    build_lifecycle_audit as build_lb26001_006_lifecycle_audit,
    render_markdown as render_lb26001_006_lifecycle_markdown,
)
from tools.validation.lb26001_006_regression_readiness_v4_2 import (
    build_readiness_report as build_lb26001_006_readiness_report,
    collect_solidworks_process_state,
    render_markdown as render_lb26001_006_readiness_markdown,
)
from tools.validation.lb26001_006_rerun_packet_v4_2 import (
    DEFAULT_CORRECTION_PLAN as DEFAULT_LB26001_006_CORRECTION_PLAN,
    DEFAULT_REFERENCE_COMPARE_SOURCE as DEFAULT_LB26001_006_REFERENCE_COMPARE_SOURCE,
    DEFAULT_REFERENCE_INTENT_CONTRACT as DEFAULT_LB26001_006_REFERENCE_INTENT_CONTRACT,
    DEFAULT_REFERENCE_INTENT_PLAN as DEFAULT_LB26001_006_REFERENCE_INTENT_PLAN,
    DEFAULT_REQUESTED_STATUS as DEFAULT_LB26001_006_REQUESTED_STATUS,
    build_rerun_packet as build_lb26001_006_rerun_packet,
)

DEFAULT_REFERENCE_DIR = REPO_ROOT / "3D转2D测试图纸"
DEFAULT_STAGE_PARTS = {
    "LB26001_006": [
        DEFAULT_REFERENCE_DIR / "LB26001-A-04-006.SLDPRT",
    ],
    "024_040": [
        DEFAULT_REFERENCE_DIR / "LB26001-A-04-024.SLDPRT",
        DEFAULT_REFERENCE_DIR / "LB26001-A-04-040.SLDPRT",
    ],
}
STAGE_SET_FILES = {
    "core_12": REPO_ROOT / "validation_sets" / "core_12.json",
    "LB26001_36": REPO_ROOT / "validation_sets" / "lb26001_36.json",
    "medium_30": REPO_ROOT / "validation_sets" / "medium_30.json",
}
DEFAULT_OUT_ROOT = REPO_ROOT / "drw_output" / "staged_validation"
DEFAULT_REFERENCE_PROFILES_V4 = REPO_ROOT / "drw_output" / "reference_style_profile" / "reference_profiles_v4.json"
STAGE_DELIVERABLE_TARGETS = {
    "LB26001_006": 1.0,
    "024_040": 1.0,
    "core_12": 1.0,
    "LB26001_36": 0.97,
    "medium_30": 0.97,
}
LB26001_006_BASE = "LB26001-A-04-006"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _run_command(cmd: list[str], cwd: Path, timeout_s: int) -> dict[str, Any]:
    started = time.time()
    try:
        completed = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
            check=False,
        )
        return {
            "cmd": cmd,
            "returncode": completed.returncode,
            "duration_s": round(time.time() - started, 1),
            "stdout": completed.stdout.strip(),
            "stderr": completed.stderr.strip(),
            "timeout": False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "cmd": cmd,
            "returncode": -1,
            "duration_s": round(time.time() - started, 1),
            "stdout": (exc.stdout or "").strip() if isinstance(exc.stdout, str) else "",
            "stderr": (exc.stderr or "").strip() if isinstance(exc.stderr, str) else "",
            "timeout": True,
        }


def _resolve_parts(stage: str, parts: list[str]) -> list[Path]:
    if parts:
        raw_parts = [Path(p) for p in parts]
    elif stage in DEFAULT_STAGE_PARTS:
        raw_parts = DEFAULT_STAGE_PARTS[stage]
    else:
        stage_file = STAGE_SET_FILES.get(stage)
        stage_data = _read_json(stage_file) if stage_file else {}
        raw_parts = [Path(str(item.get("part_path") or "")) for item in stage_data.get("items", [])]
    resolved: list[Path] = []
    for part in raw_parts:
        if not str(part):
            continue
        resolved.append(part if part.is_absolute() else (REPO_ROOT / part).resolve())
    return resolved


def _write_no_reference_report(part: Path, run_dir: Path, out_path: Path) -> dict[str, Any]:
    payload = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "reference_compare_smoke_v3",
        "part": str(part),
        "reference_drawing": str(part.with_suffix(".SLDDRW")),
        "generated_drawing": "",
        "run_dir": str(run_dir),
        "status": "no_reference",
        "pass": True,
        "reasons": ["no_same_name_reference_slddrw"],
        "fix_suggestions": ["Record this as an accepted no-reference case for the staged validation set."],
        "no_reference_reason": "Same-name original SLDDRW was not found in the reference test directory.",
    }
    _write_json(out_path, payload)
    return payload


def _write_reference_style_report(part: Path, reference_report: Path, dimension_report: Path, out_path: Path) -> dict[str, Any]:
    report = _read_json(reference_report)
    qc = _read_json(dimension_report)
    if not report:
        payload = {
            "schema": "sw_drawing_studio.reference_style_case.v1",
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "part": str(part),
            "status": "fail",
            "pass": False,
            "reasons": ["reference_compare_report_missing"],
            "fix_suggestions": ["Run reference_compare_smoke_v3 before style validation."],
        }
        _write_json(out_path, payload)
        return payload

    if report.get("status") == "no_reference":
        payload = {
            "schema": "sw_drawing_studio.reference_style_case.v1",
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "part": str(part),
            "status": "no_reference",
            "pass": True,
            "reasons": list(report.get("reasons") or ["no_same_name_reference_slddrw"]),
            "fix_suggestions": list(report.get("fix_suggestions") or []),
        }
        _write_json(out_path, payload)
        return payload

    reference_metrics = report.get("reference_metrics") or {}
    generated_metrics = report.get("generated_metrics") or {}
    if not reference_metrics or not generated_metrics:
        payload = {
            "schema": "sw_drawing_studio.reference_style_case.v1",
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "part": str(part),
            "status": "need_review",
            "pass": False,
            "reasons": ["reference_style_metrics_missing"],
            "fix_suggestions": [
                "Fix reference/generated SLDDRW metric extraction before accepting staged CAD validation."
            ],
            "reference_compare_report": str(reference_report),
        }
        _write_json(out_path, payload)
        return payload

    payload = evaluate_generated_against_reference(
        part.stem,
        reference_metrics,
        generated_metrics,
        qc=qc,
    )
    payload["schema"] = "sw_drawing_studio.reference_style_case.v1"
    payload["generated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    payload["part"] = str(part)
    payload["reference_compare_report"] = str(reference_report)
    payload["dimension_report"] = str(dimension_report)
    _write_json(out_path, payload)
    return payload


def _first_file(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.exists() and path.is_file():
            return path
    return None


def _find_generated_png(run_dir: Path, base: str) -> Path:
    direct = run_dir / "drawing" / f"{base}_v5.PNG"
    if direct.exists():
        return direct
    matches = sorted((run_dir / "drawing").glob("*.PNG")) + sorted((run_dir / "drawing").glob("*.png"))
    return matches[0] if matches else direct


def _find_qc_json(run_dir: Path, base: str) -> Path | None:
    return _first_file([
        run_dir / "qc" / f"{base}_v5_qc.json",
        *sorted((run_dir / "qc").glob("*_qc.json")),
    ])


def _find_blueprint(run_dir: Path, base: str) -> Path | None:
    return _first_file([
        run_dir / "qc" / "drawing_blueprint.json",
        run_dir / "drawing" / f"{base}_drawing_blueprint.json",
        *sorted((run_dir / "qc").glob("*drawing_blueprint*.json")),
    ])


def _find_reference_png(part: Path) -> Path | None:
    return _first_file([
        REPO_ROOT / "drw_output" / "case_library" / f"{part.stem}.png",
        REPO_ROOT / "drw_output" / "case_library" / f"{part.stem}.PNG",
        part.with_suffix(".png"),
        part.with_suffix(".PNG"),
    ])


def _find_manual_review(case_dir: Path) -> Path | None:
    return _first_file([
        case_dir / "manual_visual_judgement.json",
        case_dir / "manual_visual_review.json",
        case_dir / "manual_visual_recheck.json",
    ])


def _write_vision_qc_v6_report(part: Path, run_dir: Path, case_dir: Path, out_path: Path) -> dict[str, Any]:
    try:
        result = run_vision_qc_v6(
            png_path=_find_generated_png(run_dir, part.stem),
            run_dir=run_dir,
            blueprint_path=_find_blueprint(run_dir, part.stem),
            qc_json_path=_find_qc_json(run_dir, part.stem),
            reference_png_path=_find_reference_png(part),
            manual_review_path=_find_manual_review(case_dir),
            out_path=out_path,
        )
        return result
    except Exception as exc:
        payload = {
            "schema": "sw_drawing_studio.vision_qc_v6",
            "version": "v6",
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "part": str(part),
            "run_dir": str(run_dir),
            "status": "fail",
            "success": False,
            "visual_acceptance_pass": False,
            "pass": False,
            "issues": [{
                "key": "vision_qc_v6_exception",
                "severity": "critical",
                "bbox": [0.0, 0.0, 1.0, 1.0],
                "source": "staged_cad_validation_v3",
                "confidence": 1.0,
                "evidence": {"exception": str(exc)},
                "fix_suggestion": "Fix vision_qc_v6 execution before accepting staged CAD validation.",
                "auto_fix_available": False,
                "human_review_status": "pending",
                "description": "vision_qc_v6 raised during staged validation.",
            }],
        }
        _write_json(out_path, payload)
        return payload


def _write_reference_compare_v4_report(
    part: Path,
    run_dir: Path,
    case_dir: Path,
    cad_report: Path,
    dimension_report: Path,
    vision_report: Path,
    reference_report: Path,
    reference_style_report: Path,
    out_path: Path,
) -> dict[str, Any]:
    try:
        result = compare_reference_v4(
            base=part.stem,
            blueprint=_find_blueprint(run_dir, part.stem),
            reference_profiles=DEFAULT_REFERENCE_PROFILES_V4,
            dimension_validation=dimension_report,
            vision_qc=vision_report,
            generator_warnings=_generator_warnings_from_cad_report(cad_report, run_dir, part.stem),
            legacy_reference_compare=reference_report,
            legacy_reference_style=reference_style_report,
            out_path=out_path,
        )
        return result
    except Exception as exc:
        payload = {
            "schema": "sw_drawing_studio.reference_compare.v4",
            "version": "v4.0",
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "base": part.stem,
            "part": str(part),
            "run_dir": str(run_dir),
            "status": "fail",
            "pass": False,
            "reasons": ["reference_compare_v4_exception"],
            "failure_bucket": ["reference_compare_v4_exception"],
            "fix_suggestions": ["Fix reference_compare_v4 execution before accepting staged CAD validation."],
            "differences": [{
                "key": "reference_compare_v4_exception",
                "severity": "critical",
                "bbox": [0.0, 0.0, 1.0, 1.0],
                "source": "staged_cad_validation_v3",
                "confidence": 1.0,
                "evidence": {"exception": str(exc)},
                "fix_suggestion": "Fix reference_compare_v4 execution before accepting staged CAD validation.",
                "auto_fix_available": False,
                "human_review_status": "pending",
            }],
        }
        _write_json(out_path, payload)
        return payload


def _generator_warnings_from_cad_report(cad_report: Path, run_dir: Path, base: str) -> Path | None:
    try:
        cad = _read_json(cad_report)
    except Exception:
        cad = {}
    path_text = str((((cad.get("artifacts") or {}).get("warnings_json") or {}).get("path") or ""))
    if path_text:
        candidate = Path(path_text)
        if candidate.exists():
            return candidate
    candidates = [
        run_dir / "qc" / f"{base}_v5_warnings.json",
        run_dir / "drawing" / f"{base}_v5_warnings.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    try:
        matches = sorted((run_dir / "qc").glob("*_warnings.json"))
    except Exception:
        matches = []
    return matches[0] if matches else None


def _is_lb26001_006_part(part: Path) -> bool:
    return part.stem == LB26001_006_BASE


def _write_lifecycle_markdown(out_md: Path, payload: dict[str, Any]) -> None:
    out_md.parent.mkdir(parents=True, exist_ok=True)
    try:
        text = render_lb26001_006_lifecycle_markdown(payload)
    except Exception:
        text = "\n".join([
            "# LB26001-A-04-006 DisplayDim Lifecycle Audit",
            "",
            f"- Status: `{payload.get('status')}`",
            f"- PASS: `{str(payload.get('pass')).lower()}`",
            "",
            "## Blocking Issues",
            "",
            *[f"- `{key}`" for key in payload.get("blocking_issue_keys") or []],
            "",
        ])
    out_md.write_text(text, encoding="utf-8")


def _lifecycle_failure_payload(
    *,
    part: Path,
    run_dir: Path,
    cad_report: Path,
    dimension_report: Path,
    warnings_path: Path | None,
    blocking_issue_keys: list[str],
    exception: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema": "sw_drawing_studio.lb26001_006_displaydim_lifecycle_audit.v4_2",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "base": LB26001_006_BASE,
        "part": str(part),
        "run_dir": str(run_dir),
        "status": "fail",
        "pass": False,
        "applicable": True,
        "warnings_path": str(warnings_path or ""),
        "cad_smoke_path": str(cad_report),
        "dimension_validation_path": str(dimension_report),
        "reference_intent_plan_path": str(DEFAULT_LB26001_006_LIFECYCLE_REFERENCE_INTENT_PLAN),
        "required_display_dim_floor": 12,
        "stage_counts": [],
        "loss_events": [],
        "coverage_summary": {},
        "prune_log_summary": {},
        "sidecar_policy_summary": {},
        "post_prune_guard_summary": {},
        "post_layout_repair_summary": {},
        "target_stage_matrix": {},
        "blocking_issue_keys": sorted(set(blocking_issue_keys)),
        "api_is_not_final_judgement": True,
        "ui_screenshot_review_is_final_gate": True,
        "next_actions": [
            "Regenerate LB26001-A-04-006 through the locked CAD path, then rerun lifecycle, v4/v6, and Drawing Review UI screenshot validation.",
        ],
    }
    if exception:
        payload["exception"] = exception
    return payload


def _write_displaydim_lifecycle_audit_report(
    part: Path,
    run_dir: Path,
    cad_report: Path,
    dimension_report: Path,
    out_json: Path,
    out_md: Path,
) -> dict[str, Any]:
    if not _is_lb26001_006_part(part):
        payload = {
            "schema": "sw_drawing_studio.lb26001_006_displaydim_lifecycle_audit.v4_2",
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "base": part.stem,
            "part": str(part),
            "status": "not_applicable",
            "pass": True,
            "applicable": False,
            "reason": "displaydim lifecycle audit is strict only for LB26001-A-04-006.",
            "api_is_not_final_judgement": True,
            "ui_screenshot_review_is_final_gate": True,
        }
        _write_json(out_json, payload)
        _write_lifecycle_markdown(out_md, payload)
        return payload

    warnings_path = _generator_warnings_from_cad_report(cad_report, run_dir, part.stem)
    blockers: list[str] = []
    if not run_dir.exists():
        blockers.append("displaydim_lifecycle_run_dir_missing")
    if warnings_path is None or not warnings_path.exists():
        blockers.append("displaydim_lifecycle_warnings_missing")
    if not cad_report.exists():
        blockers.append("displaydim_lifecycle_cad_smoke_missing")
    if not dimension_report.exists():
        blockers.append("displaydim_lifecycle_dimension_validation_missing")
    if blockers:
        payload = _lifecycle_failure_payload(
            part=part,
            run_dir=run_dir,
            cad_report=cad_report,
            dimension_report=dimension_report,
            warnings_path=warnings_path,
            blocking_issue_keys=blockers,
        )
        _write_json(out_json, payload)
        _write_lifecycle_markdown(out_md, payload)
        return payload

    try:
        payload = build_lb26001_006_lifecycle_audit(
            warnings_path=warnings_path,
            cad_smoke_path=cad_report,
            dimension_validation_path=dimension_report,
            reference_intent_plan_path=DEFAULT_LB26001_006_LIFECYCLE_REFERENCE_INTENT_PLAN,
        )
        payload["part"] = str(part)
        payload["run_dir"] = str(run_dir)
        payload["applicable"] = True
        _write_json(out_json, payload)
        _write_lifecycle_markdown(out_md, payload)
        return payload
    except Exception as exc:
        payload = _lifecycle_failure_payload(
            part=part,
            run_dir=run_dir,
            cad_report=cad_report,
            dimension_report=dimension_report,
            warnings_path=warnings_path,
            blocking_issue_keys=["displaydim_lifecycle_audit_exception"],
            exception=str(exc),
        )
        _write_json(out_json, payload)
        _write_lifecycle_markdown(out_md, payload)
        return payload


def _missing_artifact_reasons(report: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    artifacts = report.get("artifacts") or {}
    for key in ["slddrw", "pdf", "dxf", "png", "qc_json", "vision_qc", "final_quality", "manifest", "job_event_log"]:
        info = artifacts.get(key) or {}
        if not (info.get("exists") and int(info.get("size_bytes") or 0) > 0):
            reasons.append(f"missing_artifact:{key}")
    return reasons


def _failure_bucket(
    part: Path,
    cad: dict[str, Any],
    dim: dict[str, Any],
    ref: dict[str, Any],
    style: dict[str, Any],
    lifecycle: dict[str, Any],
    vision: dict[str, Any],
    reference_v4: dict[str, Any] | None,
    commands: dict[str, Any],
) -> list[str]:
    buckets: list[str] = []
    if commands.get("cad", {}).get("timeout"):
        buckets.append("cad_validator_timeout")
    if commands.get("cad", {}).get("returncode", 0) != 0:
        buckets.append("cad_validator_nonzero")
    if cad and not cad.get("pass"):
        buckets.append("cad_smoke_not_pass")
    if not cad:
        buckets.append("cad_smoke_report_missing")
    if cad:
        buckets.extend(_missing_artifact_reasons(cad))
        final_status = str((cad.get("final_quality") or {}).get("status") or "")
        if final_status and final_status not in {"pass", "pass_with_warning"}:
            buckets.append(f"final_quality:{final_status}")
    if commands.get("dimension", {}).get("timeout"):
        buckets.append("dimension_validator_timeout")
    if dim and not dim.get("pass"):
        buckets.append("dimension_validation_not_pass")
    if commands.get("reference", {}).get("timeout"):
        buckets.append("reference_validator_timeout")
    if ref and not ref.get("pass"):
        buckets.append("reference_compare_not_pass")
    if not ref:
        buckets.append("reference_compare_report_missing")
    if style and not style.get("pass"):
        buckets.append("reference_style_not_pass")
    if not style:
        buckets.append("reference_style_report_missing")
    lifecycle_required = _is_lb26001_006_part(part)
    if lifecycle_required and lifecycle and not lifecycle.get("pass"):
        buckets.append("displaydim_lifecycle_not_pass")
    if lifecycle_required and not lifecycle:
        buckets.append("displaydim_lifecycle_report_missing")
    if commands.get("vision_qc_v6", {}).get("timeout"):
        buckets.append("vision_qc_v6_timeout")
    if vision and not vision.get("visual_acceptance_pass"):
        buckets.append("vision_qc_v6_not_pass")
    if not vision:
        buckets.append("vision_qc_v6_report_missing")
    if reference_v4 is not None and reference_v4 and not reference_v4.get("pass"):
        buckets.append("reference_compare_v4_not_pass")
    if reference_v4 is not None and not reference_v4:
        buckets.append("reference_compare_v4_report_missing")
    return sorted(set(buckets))


def _case_summary(
    part: Path,
    case_dir: Path,
    cad: dict[str, Any],
    dim: dict[str, Any],
    ref: dict[str, Any],
    commands: dict[str, Any],
    style: dict[str, Any] | None = None,
    lifecycle: dict[str, Any] | None = None,
    vision: dict[str, Any] | None = None,
    reference_v4: dict[str, Any] | None = None,
) -> dict[str, Any]:
    style = style or {}
    lifecycle = lifecycle or {}
    vision = vision or {}
    buckets = _failure_bucket(part, cad, dim, ref, style, lifecycle, vision, reference_v4, commands)
    cad_pass = bool(cad.get("pass"))
    dim_pass = bool(dim.get("pass"))
    ref_pass = bool(ref.get("pass"))
    style_pass = bool(style.get("pass"))
    lifecycle_required = _is_lb26001_006_part(part)
    lifecycle_pass = True if not lifecycle_required else bool(lifecycle.get("pass"))
    vision_pass = bool(vision.get("visual_acceptance_pass"))
    reference_v4_pass = True if reference_v4 is None else bool(reference_v4.get("pass"))
    deliverable = (
        cad_pass
        and dim_pass
        and ref_pass
        and style_pass
        and lifecycle_pass
        and vision_pass
        and reference_v4_pass
    )
    evidence_complete = (
        bool(cad)
        and bool(dim)
        and bool(ref)
        and bool(style)
        and (not lifecycle_required or bool(lifecycle))
        and bool(vision)
        and (reference_v4 is None or bool(reference_v4))
        and (deliverable or bool(buckets))
    )
    status = "pass" if deliverable else ("need_review" if evidence_complete else "fail")
    return {
        "part": str(part),
        "part_name": part.stem,
        "case_dir": str(case_dir),
        "run_dir": cad.get("run_dir", ""),
        "cad_report": str(case_dir / "cad_smoke.json"),
        "dimension_report": str(case_dir / "dimension_validation.json"),
        "reference_report": str(case_dir / "reference_compare.json"),
        "reference_style_report": str(case_dir / "reference_style.json"),
        "displaydim_lifecycle_report": str(case_dir / "displaydim_lifecycle_audit.json"),
        "vision_qc_v6_report": str(case_dir / "vision_qc_v6.json"),
        "reference_compare_v4_report": str(case_dir / "reference_compare_v4.json"),
        "cad_pass": cad_pass,
        "dimension_pass": dim_pass,
        "reference_pass": ref_pass,
        "reference_style_pass": style_pass,
        "displaydim_lifecycle_required": lifecycle_required,
        "displaydim_lifecycle_pass": lifecycle_pass,
        "vision_qc_v6_pass": vision_pass,
        "reference_compare_v4_pass": reference_v4_pass,
        "deliverable": deliverable,
        "status": status,
        "failure_bucket": buckets,
        "reasons": (
            list(cad.get("reasons") or [])
            + list(dim.get("reasons") or [])
            + list(ref.get("reasons") or [])
            + list(style.get("reasons") or [])
            + list(lifecycle.get("reasons") or [])
            + list(lifecycle.get("blocking_issue_keys") or [])
            + list(vision.get("reasons") or [])
            + list((reference_v4 or {}).get("reasons") or [])
        ),
        "final_quality_status": str((cad.get("final_quality") or {}).get("status") or ""),
        "dimension_status": str(dim.get("status") or ""),
        "reference_status": str(ref.get("status") or ""),
        "reference_style_status": str(style.get("status") or ""),
        "displaydim_lifecycle_status": str(lifecycle.get("status") or ("not_required" if not lifecycle_required else "")),
        "displaydim_lifecycle_blocking_issue_keys": list(lifecycle.get("blocking_issue_keys") or []),
        "vision_qc_v6_status": str(vision.get("status") or ""),
        "vision_qc_v6_visual_acceptance_pass": vision.get("visual_acceptance_pass"),
        "reference_compare_v4_status": str((reference_v4 or {}).get("status") or ""),
        "commands": commands,
    }


def _remaining_gates(stage: str) -> list[str]:
    remaining_gates = [
        "core_12",
        "LB26001_36",
        "medium_30",
        "historical_visual_audit_100_percent",
        "full_129",
        "final_exe_rebuild_and_release_log",
    ]
    return [gate for gate in remaining_gates if gate != stage]


def _write_sw_preflight_reports(
    out_dir: Path,
    *,
    timeout_s: float,
    sw_guard: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], Path, dict[str, Any], Path]:
    guard = sw_guard if sw_guard is not None else check_sw_connection_guard(timeout_s=timeout_s)
    guard_report = out_dir / "sw_connection_guard.json"
    write_sw_connection_guard(guard, guard_report)
    workflow = build_safe_restart_workflow(connection_guard=guard, user_confirmed=False)
    workflow_report = out_dir / "sw_safe_restart_workflow.json"
    write_safe_restart_workflow(workflow, workflow_report)
    return guard, guard_report, workflow, workflow_report


def _write_lb26001_006_readiness_preflight_report(
    out_dir: Path,
    *,
    readiness: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], Path, Path]:
    if readiness and "ready_to_start_locked_006_cad" in readiness:
        report = dict(readiness)
    else:
        sw_state = readiness if readiness is not None else collect_solidworks_process_state()
        report = build_lb26001_006_readiness_report(sw_state=sw_state)
    report_path = out_dir / "lb26001_006_regression_readiness_v4_2.json"
    _write_json(report_path, report)
    report_md = out_dir / "lb26001_006_regression_readiness_v4_2.md"
    report_md.write_text(render_lb26001_006_readiness_markdown(report), encoding="utf-8")
    return report, report_path, report_md


def _write_lb26001_006_rerun_packet_preflight_report(
    out_dir: Path,
    *,
    readiness: dict[str, Any],
    rerun_packet: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], Path]:
    if rerun_packet and "real_cad_allowed_now" in rerun_packet:
        packet = dict(rerun_packet)
    else:
        packet = build_lb26001_006_rerun_packet(
            readiness=readiness,
            requested_status=_read_json(DEFAULT_LB26001_006_REQUESTED_STATUS),
            correction_plan=_read_json(DEFAULT_LB26001_006_CORRECTION_PLAN),
            reference_intent_plan_path=DEFAULT_LB26001_006_REFERENCE_INTENT_PLAN,
            reference_intent_contract_path=DEFAULT_LB26001_006_REFERENCE_INTENT_CONTRACT,
            reference_compare_source_path=DEFAULT_LB26001_006_REFERENCE_COMPARE_SOURCE,
        )
    packet_path = out_dir / "lb26001_006_rerun_packet_v4_2.json"
    _write_json(packet_path, packet)
    return packet, packet_path


def _stage_preflight_failure_summary(
    *,
    stage: str,
    out_dir: Path,
    started: float,
    total: int,
    guard: dict[str, Any],
    guard_report: Path,
    workflow_report: Path,
) -> dict[str, Any]:
    bucket = str(guard.get("failure_bucket") or "sw_connection_guard_not_pass")
    return {
        "schema": "sw_drawing_studio.staged_cad_validation.v1",
        "stage": stage,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "out_dir": str(out_dir),
        "duration_s": round(time.time() - started, 1),
        "total": total,
        "processed": 0,
        "deliverable_count": 0,
        "deliverable_target_ratio": float(STAGE_DELIVERABLE_TARGETS.get(stage, 1.0)),
        "required_deliverable_count": math.ceil(total * float(STAGE_DELIVERABLE_TARGETS.get(stage, 1.0))) if total > 0 else 0,
        "execution_completed": False,
        "acceptance_pass": False,
        "need_review_count": 0,
        "failed_count": 0,
        "status": "fail",
        "pass": False,
        "preflight_pass": False,
        "sw_connection_guard_pass": False,
        "sw_connection_guard_report": str(guard_report),
        "sw_safe_restart_workflow_report": str(workflow_report),
        "failure_bucket": sorted(set(["sw_connection_guard_not_pass", bucket])),
        "reasons": [str(guard.get("reason") or bucket)],
        "fix_suggestions": [str(guard.get("user_action_required") or "Resolve SolidWorks connection before staged CAD validation.")],
        "cases": [],
        "remaining_gates": _remaining_gates(stage),
    }


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def _stage_006_readiness_failure_summary(
    *,
    stage: str,
    out_dir: Path,
    started: float,
    total: int,
    readiness: dict[str, Any],
    readiness_report: Path,
    readiness_report_md: Path | None = None,
    rerun_packet: dict[str, Any] | None = None,
    rerun_packet_report: Path | None = None,
) -> dict[str, Any]:
    blocking_keys = [str(item) for item in readiness.get("blocking_issue_keys") or [] if str(item)]
    packet = rerun_packet or {}
    offline_missing = [
        str(item)
        for item in packet.get("offline_prerequisite_missing_keys") or []
        if str(item)
    ]
    issue_map = {
        str(item.get("key")): item
        for item in readiness.get("issues") or []
        if isinstance(item, dict) and item.get("key")
    }
    prerequisite_map = {
        str(item.get("key")): item
        for item in packet.get("offline_prerequisites") or []
        if isinstance(item, dict) and item.get("key")
    }
    fix_suggestions = _unique([
        str(issue_map.get(key, {}).get("fix_suggestion") or "")
        for key in blocking_keys
    ] + [
        str(prerequisite_map.get(key, {}).get("fix_suggestion") or "")
        for key in offline_missing
    ])
    packet_status = str(packet.get("status") or "")
    packet_build_ready = bool(packet.get("packet_build_ready"))
    packet_blocked_only_by_readiness = bool(
        packet
        and packet_status == "blocked_by_solidworks_readiness"
        and packet_build_ready
        and not offline_missing
    )
    if packet and packet_blocked_only_by_readiness:
        packet_bucket = ["lb26001_006_rerun_packet_blocked_by_readiness"]
    elif packet and not packet.get("real_cad_allowed_now"):
        packet_bucket = ["lb26001_006_rerun_packet_not_ready"]
    else:
        packet_bucket = []
    readiness_bucket = ["lb26001_006_readiness_not_ready"] if not readiness.get("ready_to_start_locked_006_cad") else []
    safe_recovery = readiness.get("safe_recovery_guidance") or {}
    source_signatures = packet.get("source_signatures") or {}
    source_signature_summary = {
        str(key): bool(value.get("pass"))
        for key, value in source_signatures.items()
        if isinstance(value, dict)
    }
    offline_prerequisite_summary = {
        str(key): bool(value.get("pass"))
        for key, value in prerequisite_map.items()
    }
    current_006_verdict = packet.get("current_006_ui_verdict") or {}
    failed_visual_checks = [
        str(item)
        for item in current_006_verdict.get("failed_visual_checklist_items") or []
        if str(item)
    ]
    correction_actions = [
        item for item in current_006_verdict.get("correction_actions") or []
        if isinstance(item, dict)
    ]
    latest_manual_findings = [
        str(item)
        for item in current_006_verdict.get("latest_manual_findings") or []
        if str(item).strip()
    ]
    latest_manual_checklist = current_006_verdict.get("latest_manual_visual_checklist")
    if not isinstance(latest_manual_checklist, dict):
        latest_manual_checklist = {}
    latest_manual_checklist_notes = current_006_verdict.get("latest_manual_visual_checklist_notes")
    if not isinstance(latest_manual_checklist_notes, dict):
        latest_manual_checklist_notes = {}
    ui_screenshot_files = [
        str(item)
        for item in current_006_verdict.get("ui_screenshot_files") or []
        if str(item).strip()
    ]
    existing_application_ui_screenshots = [
        str(item)
        for item in current_006_verdict.get("application_ui_screenshot_paths_existing_application_ui") or []
        if str(item).strip()
    ]
    ui_evidence = {
        "latest_manual_review": str(current_006_verdict.get("latest_manual_review") or ""),
        "comparison_image": str(current_006_verdict.get("comparison_image") or ""),
        "latest_manual_findings": latest_manual_findings,
        "latest_manual_visual_checklist": latest_manual_checklist,
        "latest_manual_visual_checklist_notes": latest_manual_checklist_notes,
        "latest_manual_required_correction": str(current_006_verdict.get("latest_manual_required_correction") or ""),
        "ui_screenshot_files": ui_screenshot_files,
        "application_ui_screenshot_paths_existing_application_ui": existing_application_ui_screenshots,
        "generated_png": str(current_006_verdict.get("generated_png") or ""),
        "reference_png": str(current_006_verdict.get("reference_png") or ""),
    }
    return {
        "schema": "sw_drawing_studio.staged_cad_validation.v1",
        "stage": stage,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "out_dir": str(out_dir),
        "duration_s": round(time.time() - started, 1),
        "total": total,
        "processed": 0,
        "deliverable_count": 0,
        "deliverable_target_ratio": float(STAGE_DELIVERABLE_TARGETS.get(stage, 1.0)),
        "required_deliverable_count": math.ceil(total * float(STAGE_DELIVERABLE_TARGETS.get(stage, 1.0))) if total > 0 else 0,
        "execution_completed": False,
        "acceptance_pass": False,
        "need_review_count": 0,
        "failed_count": 0,
        "status": "fail",
        "pass": False,
        "preflight_pass": False,
        "readiness_preflight_pass": bool(readiness.get("ready_to_start_locked_006_cad")),
        "rerun_packet_preflight_pass": bool(packet.get("real_cad_allowed_now")),
        "sw_connection_guard_skipped_due_to_readiness": not bool(readiness.get("ready_to_start_locked_006_cad")),
        "sw_connection_guard_skipped_due_to_006_preflight": True,
        "lb26001_006_readiness_report": str(readiness_report),
        "lb26001_006_readiness_report_md": str(readiness_report_md or ""),
        "lb26001_006_rerun_packet_report": str(rerun_packet_report or ""),
        "lb26001_006_rerun_packet_status": packet_status,
        "lb26001_006_rerun_packet_build_ready": packet_build_ready,
        "lb26001_006_rerun_packet_blocked_only_by_readiness": packet_blocked_only_by_readiness,
        "lb26001_006_real_cad_allowed_now": bool(packet.get("real_cad_allowed_now")),
        "lb26001_006_readiness_status": str(readiness.get("status") or ""),
        "lb26001_006_ui_visual_review_gate": str(readiness.get("ui_visual_review_gate") or ""),
        "lb26001_006_expansion_gate": str(readiness.get("lb26001_expansion_gate") or ""),
        "lb26001_006_safe_recovery_guidance": safe_recovery,
        "lb26001_006_manual_recovery_required": bool(safe_recovery.get("manual_recovery_required")),
        "lb26001_006_automatic_restart_allowed": bool(safe_recovery.get("automatic_restart_allowed")),
        "lb26001_006_solidworks_lock_present": bool(readiness.get("solidworks_lock_present")),
        "lb26001_006_solidworks_lock_stale": bool(readiness.get("solidworks_lock_stale")),
        "lb26001_006_solidworks_lock_conflict": readiness.get("solidworks_lock_conflict") or {},
        "lb26001_006_solidworks_lock_owner": readiness.get("solidworks_lock_owner") or {},
        "lb26001_006_solidworks_lock_fix_suggestion": str(readiness.get("solidworks_lock_fix_suggestion") or ""),
        "lb26001_006_source_signature_summary": source_signature_summary,
        "lb26001_006_offline_prerequisite_summary": offline_prerequisite_summary,
        "lb26001_006_correction_plan_freshness_pass": bool(
            offline_prerequisite_summary.get("correction_plan_matches_current_006_status")
        ),
        "lb26001_006_effective_ui_corrections_present": bool(
            offline_prerequisite_summary.get("006_effective_ui_corrections_present")
        ),
        "lb26001_006_correction_plan_source_signature_pass": bool(
            offline_prerequisite_summary.get("correction_plan_source_signatures_present")
        ),
        "lb26001_006_failed_visual_checks": failed_visual_checks,
        "lb26001_006_correction_action_count": len(correction_actions),
        "lb26001_006_ui_evidence": ui_evidence,
        "lb26001_006_comparison_image": ui_evidence["comparison_image"],
        "lb26001_006_latest_manual_findings": latest_manual_findings,
        "lb26001_006_latest_manual_required_correction": ui_evidence["latest_manual_required_correction"],
        "failure_bucket": sorted(set([
            *readiness_bucket,
            *packet_bucket,
            *blocking_keys,
            *offline_missing,
        ])),
        "reasons": blocking_keys or offline_missing or [packet_status or str(readiness.get("status") or "lb26001_006_readiness_not_ready")],
        "fix_suggestions": fix_suggestions or [
            "Resolve LB26001-A-04-006 readiness blockers before starting locked real CAD validation."
        ],
        "cases": [],
        "remaining_gates": _remaining_gates(stage),
    }


def run_stage(
    stage: str,
    parts: list[Path],
    out_dir: Path,
    timeout_s: int,
    max_rounds: int,
    *,
    sw_guard_timeout_s: float = 3.0,
    sw_guard: dict[str, Any] | None = None,
    lb26001_readiness: dict[str, Any] | None = None,
    lb26001_rerun_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    cases: list[dict[str, Any]] = []
    started = time.time()
    lb26001_006_rerun_packet_report: Path | None = None
    if stage == "LB26001_006":
        readiness, readiness_report, readiness_report_md = _write_lb26001_006_readiness_preflight_report(
            out_dir,
            readiness=lb26001_readiness,
        )
        rerun_packet, lb26001_006_rerun_packet_report = _write_lb26001_006_rerun_packet_preflight_report(
            out_dir,
            readiness=readiness,
            rerun_packet=lb26001_rerun_packet,
        )
        if not rerun_packet.get("real_cad_allowed_now"):
            summary = _stage_006_readiness_failure_summary(
                stage=stage,
                out_dir=out_dir,
                started=started,
                total=len(parts),
                readiness=readiness,
                readiness_report=readiness_report,
                readiness_report_md=readiness_report_md,
                rerun_packet=rerun_packet,
                rerun_packet_report=lb26001_006_rerun_packet_report,
            )
            _write_json(out_dir / "summary.json", summary)
            return summary

    guard, guard_report, _workflow, workflow_report = _write_sw_preflight_reports(
        out_dir,
        timeout_s=sw_guard_timeout_s,
        sw_guard=sw_guard,
    )
    if guard.get("do_not_continue_batch") or not guard.get("safe_to_start_cad_job"):
        summary = _stage_preflight_failure_summary(
            stage=stage,
            out_dir=out_dir,
            started=started,
            total=len(parts),
            guard=guard,
            guard_report=guard_report,
            workflow_report=workflow_report,
        )
        _write_json(out_dir / "summary.json", summary)
        return summary

    for index, part in enumerate(parts, 1):
        case_dir = out_dir / f"{index:02d}_{part.stem}"
        case_dir.mkdir(parents=True, exist_ok=True)
        cad_report = case_dir / "cad_smoke.json"
        dimension_report = case_dir / "dimension_validation.json"
        reference_report = case_dir / "reference_compare.json"
        reference_style_report = case_dir / "reference_style.json"
        displaydim_lifecycle_report = case_dir / "displaydim_lifecycle_audit.json"
        displaydim_lifecycle_report_md = case_dir / "displaydim_lifecycle_audit.md"
        vision_qc_v6_report = case_dir / "vision_qc_v6.json"
        reference_compare_v4_report = case_dir / "reference_compare_v4.json"

        commands: dict[str, Any] = {}
        cad_command = [
            sys.executable,
            "tools/validation/real_cad_smoke_v3.py",
            "--part",
            str(part),
            "--timeout-s",
            str(timeout_s),
            "--max-rounds",
            str(max_rounds),
            "--out",
            str(cad_report),
        ]
        if _is_lb26001_006_part(part) and lb26001_006_rerun_packet_report is not None:
            cad_command.extend([
                "--lb26001-006-rerun-packet",
                str(lb26001_006_rerun_packet_report),
            ])
        commands["cad"] = _run_command(
            cad_command,
            REPO_ROOT,
            timeout_s + 420,
        )
        cad = _read_json(cad_report)
        run_dir = Path(str(cad.get("run_dir") or ""))

        if run_dir.exists():
            commands["dimension"] = _run_command(
                [
                    sys.executable,
                    "tools/validation/dimension_validation_smoke_v3.py",
                    "--run-dir",
                    str(run_dir),
                    "--cad-smoke",
                    str(cad_report),
                    "--out",
                    str(dimension_report),
                ],
                REPO_ROOT,
                180,
            )
            if part.with_suffix(".SLDDRW").exists():
                commands["reference"] = _run_command(
                    [
                        sys.executable,
                        "tools/validation/reference_compare_smoke_v3.py",
                        "--run-dir",
                        str(run_dir),
                        "--part",
                        str(part),
                        "--cad-smoke",
                        str(cad_report),
                        "--out",
                        str(reference_report),
                    ],
                    REPO_ROOT,
                    240,
                )
            else:
                _write_no_reference_report(part, run_dir, reference_report)
                commands["reference"] = {
                    "returncode": 0,
                    "timeout": False,
                    "stdout": "no same-name reference SLDDRW; wrote no_reference report",
                    "stderr": "",
                }
        else:
            commands["dimension"] = {
                "returncode": 1,
                "timeout": False,
                "stdout": "",
                "stderr": "run_dir missing; dimension validation skipped",
            }
            commands["reference"] = {
                "returncode": 1,
                "timeout": False,
                "stdout": "",
                "stderr": "run_dir missing; reference comparison skipped",
            }

        dim = _read_json(dimension_report)
        ref = _read_json(reference_report)
        style: dict[str, Any] = {}
        if reference_report.exists():
            style = _write_reference_style_report(part, reference_report, dimension_report, reference_style_report)
            commands["reference_style"] = {
                "returncode": 0 if style else 1,
                "timeout": False,
                "stdout": f"wrote {reference_style_report}",
                "stderr": "",
            }
        else:
            commands["reference_style"] = {
                "returncode": 1,
                "timeout": False,
                "stdout": "",
                "stderr": "reference_compare missing; reference style validation skipped",
            }
        lifecycle: dict[str, Any] = {}
        if run_dir.exists() or _is_lb26001_006_part(part):
            lifecycle = _write_displaydim_lifecycle_audit_report(
                part,
                run_dir,
                cad_report,
                dimension_report,
                displaydim_lifecycle_report,
                displaydim_lifecycle_report_md,
            )
            commands["displaydim_lifecycle_audit"] = {
                "returncode": 0 if lifecycle.get("pass") else 1,
                "timeout": False,
                "stdout": f"wrote {displaydim_lifecycle_report}",
                "stderr": "",
            }
        else:
            commands["displaydim_lifecycle_audit"] = {
                "returncode": 0,
                "timeout": False,
                "stdout": "displaydim lifecycle audit not required for this part",
                "stderr": "",
            }
        vision: dict[str, Any] = {}
        if run_dir.exists():
            vision = _write_vision_qc_v6_report(part, run_dir, case_dir, vision_qc_v6_report)
            commands["vision_qc_v6"] = {
                "returncode": 0 if vision else 1,
                "timeout": False,
                "stdout": f"wrote {vision_qc_v6_report}",
                "stderr": "",
            }
        else:
            commands["vision_qc_v6"] = {
                "returncode": 1,
                "timeout": False,
                "stdout": "",
                "stderr": "run_dir missing; vision_qc_v6 skipped",
            }
        reference_v4: dict[str, Any] = {}
        if run_dir.exists():
            reference_v4 = _write_reference_compare_v4_report(
                part,
                run_dir,
                case_dir,
                cad_report,
                dimension_report,
                vision_qc_v6_report,
                reference_report,
                reference_style_report,
                reference_compare_v4_report,
            )
            commands["reference_compare_v4"] = {
                "returncode": 0 if reference_v4.get("pass") else 1,
                "timeout": False,
                "stdout": f"wrote {reference_compare_v4_report}",
                "stderr": "",
            }
        else:
            commands["reference_compare_v4"] = {
                "returncode": 1,
                "timeout": False,
                "stdout": "",
                "stderr": "run_dir missing; reference_compare_v4 skipped",
            }
        cases.append(
            _case_summary(
                part,
                case_dir,
                cad,
                dim,
                ref,
                commands,
                style=style,
                lifecycle=lifecycle,
                vision=vision,
                reference_v4=reference_v4,
            )
        )

        interim = _stage_summary(stage, out_dir, started, cases, total=len(parts), final=False, sw_guard=guard)
        _write_json(out_dir / "summary.json", interim)

    summary = _stage_summary(stage, out_dir, started, cases, total=len(parts), final=True, sw_guard=guard)
    _write_json(out_dir / "summary.json", summary)
    return summary


def _stage_summary(
    stage: str,
    out_dir: Path,
    started: float,
    cases: list[dict[str, Any]],
    total: int,
    final: bool,
    sw_guard: dict[str, Any] | None = None,
) -> dict[str, Any]:
    deliverable_count = sum(1 for c in cases if c.get("deliverable"))
    completed_with_buckets = all(
        c.get("deliverable") or (c.get("status") == "need_review" and bool(c.get("failure_bucket")))
        for c in cases
    )
    processed_all = len(cases) == total
    target_ratio = float(STAGE_DELIVERABLE_TARGETS.get(stage, 1.0))
    required_deliverable_count = math.ceil(total * target_ratio) if total > 0 else 0
    acceptance_pass = processed_all and deliverable_count >= required_deliverable_count
    execution_completed = processed_all and completed_with_buckets
    if processed_all and deliverable_count == total:
        status = "pass"
    elif acceptance_pass and completed_with_buckets:
        status = "pass_with_warning"
    elif processed_all:
        status = "need_review" if completed_with_buckets else "fail"
    else:
        status = "running" if not final else "fail"
    payload = {
        "schema": "sw_drawing_studio.staged_cad_validation.v1",
        "stage": stage,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "out_dir": str(out_dir),
        "duration_s": round(time.time() - started, 1),
        "total": total,
        "processed": len(cases),
        "deliverable_count": deliverable_count,
        "deliverable_target_ratio": target_ratio,
        "required_deliverable_count": required_deliverable_count,
        "execution_completed": execution_completed,
        "acceptance_pass": acceptance_pass,
        "need_review_count": sum(1 for c in cases if c.get("status") == "need_review"),
        "failed_count": sum(1 for c in cases if c.get("status") == "fail"),
        "status": status,
        "pass": acceptance_pass and status in {"pass", "pass_with_warning"},
        "cases": cases,
        "remaining_gates": _remaining_gates(stage),
    }
    if sw_guard is not None:
        payload["preflight_pass"] = bool(sw_guard.get("safe_to_start_cad_job"))
        payload["sw_connection_guard_pass"] = bool(sw_guard.get("connected"))
        payload["sw_connection_guard_report"] = str(out_dir / "sw_connection_guard.json")
        payload["sw_safe_restart_workflow_report"] = str(out_dir / "sw_safe_restart_workflow.json")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run v3.0 staged real CAD validation.")
    parser.add_argument("--stage", default="024_040", choices=sorted(set(DEFAULT_STAGE_PARTS) | set(STAGE_SET_FILES)))
    parser.add_argument("--part", action="append", default=[], help="Override stage part list; repeat for multiple parts.")
    parser.add_argument("--out-dir", default="", help="Output directory. Defaults to drw_output/staged_validation/<stage>/<timestamp>.")
    parser.add_argument("--timeout-s", type=int, default=900)
    parser.add_argument("--max-rounds", type=int, default=1)
    parser.add_argument("--sw-guard-timeout-s", type=float, default=3.0,
                        help="Bounded SolidWorks COM preflight timeout before any CAD case starts.")
    args = parser.parse_args()

    parts = _resolve_parts(args.stage, args.part)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.out_dir) if args.out_dir else DEFAULT_OUT_ROOT / args.stage / timestamp
    if not out_dir.is_absolute():
        out_dir = (REPO_ROOT / out_dir).resolve()

    missing = [str(p) for p in parts if not p.exists()]
    if missing:
        payload = {
            "schema": "sw_drawing_studio.staged_cad_validation.v1",
            "stage": args.stage,
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "out_dir": str(out_dir),
            "status": "fail",
            "pass": False,
            "reasons": [f"missing_part:{p}" for p in missing],
            "fix_suggestions": ["Use real SLDPRT/SLDASM files from the reference test directory."],
        }
        _write_json(out_dir / "summary.json", payload)
        print(json.dumps({"pass": False, "status": "fail", "report": str(out_dir / "summary.json"), "reasons": payload["reasons"]}, ensure_ascii=False))
        return 1

    payload = run_stage(
        args.stage,
        parts,
        out_dir,
        timeout_s=args.timeout_s,
        max_rounds=args.max_rounds,
        sw_guard_timeout_s=args.sw_guard_timeout_s,
    )
    print(json.dumps({
        "pass": payload["pass"],
        "status": payload["status"],
        "report": str(out_dir / "summary.json"),
        "deliverable_count": payload["deliverable_count"],
        "total": payload["total"],
    }, ensure_ascii=False))
    return 0 if payload["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
