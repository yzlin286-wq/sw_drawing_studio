"""Build and apply a v3.0 drawing-style profile from original SLDDRW files.

The profile is intentionally stricter than the smoke scorer. It treats the
named user reference drawings as engineering-standard samples, then checks
generated drawings against exact view count, projected-view usage, and real
DisplayDim baselines. QC sidecar/note evidence is recorded, but it is not
promoted to real CAD DisplayDim evidence.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

_THIS_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_THIS_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_THIS_REPO_ROOT))

from tools.validation.reference_compare_smoke_v3 import (
    REPO_ROOT,
    _normalize_view_metrics,
    _read_json,
    _run_reference_metrics_sidecar,
    _write_json,
)

DEFAULT_REFERENCE_DIR = REPO_ROOT / "3D转2D测试图纸"
DEFAULT_OUT_DIR = REPO_ROOT / "drw_output" / "reference_style_profile"
DEFAULT_REFERENCE_BASES = [
    "LB26001-A-04-006",
    "LB26001-A-04-007",
    "LB26001-A-04-008",
    "LB26001-A-04-009",
    "LB26001-A-04-015",
    "LB26001-A-04-022",
]
LAYOUT_CENTER_TOLERANCE_NORM = 0.08


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


def _view_types(metrics: dict[str, Any]) -> dict[str, int]:
    raw = metrics.get("view_types") or {}
    return {str(key): _int(value) for key, value in raw.items()}


def _sheet_size_m(metrics: dict[str, Any]) -> dict[str, float]:
    sheet = metrics.get("sheet") or {}
    props = sheet.get("properties") or []
    try:
        if len(props) >= 7:
            return {"width": round(float(props[5]), 6), "height": round(float(props[6]), 6)}
    except Exception:
        pass
    paper = sheet.get("paper_size") or []
    try:
        if len(paper) >= 2:
            return {"width": round(float(paper[0]), 6), "height": round(float(paper[1]), 6)}
    except Exception:
        pass
    return {}


def _view_layout(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    size = _sheet_size_m(metrics)
    width = float(size.get("width") or 0)
    height = float(size.get("height") or 0)
    layout: list[dict[str, Any]] = []
    for item in metrics.get("view_outlines") or []:
        if not isinstance(item, dict):
            continue
        outline = item.get("outline") or []
        if len(outline) < 4:
            continue
        try:
            x0, y0, x1, y1 = [float(v) for v in outline[:4]]
        except Exception:
            continue
        center_x = (x0 + x1) / 2.0
        center_y = (y0 + y1) / 2.0
        entry = {
            "name": str(item.get("name") or ""),
            "type": str(item.get("type") or ""),
            "outline_m": [round(x0, 6), round(y0, 6), round(x1, 6), round(y1, 6)],
            "center_m": [round(center_x, 6), round(center_y, 6)],
            "size_m": [round(abs(x1 - x0), 6), round(abs(y1 - y0), 6)],
        }
        if width > 0 and height > 0:
            entry["center_norm"] = [round(center_x / width, 4), round(center_y / height, 4)]
            entry["size_norm"] = [round(abs(x1 - x0) / width, 4), round(abs(y1 - y0) / height, 4)]
        layout.append(entry)
    return layout


def _sample(base: str, metrics: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_view_metrics(metrics)
    return {
        "base": base,
        "path": str(normalized.get("path") or ""),
        "success": bool(normalized.get("success")),
        "reason": str(normalized.get("reason") or ""),
        "view_count": _int(normalized.get("view_count")),
        "view_types": _view_types(normalized),
        "display_dim_count": _int(normalized.get("display_dim_count")),
        "annotation_count": _int(normalized.get("annotation_count")),
        "sheet_size_m": _sheet_size_m(normalized),
        "view_layout": _view_layout(normalized),
        "sidecar_report": normalized.get("sidecar_report"),
        "source": normalized.get("source", ""),
    }


def _layout_point(item: dict[str, Any], sheet_size: dict[str, Any]) -> tuple[float, float] | None:
    center_norm = item.get("center_norm") or []
    if len(center_norm) >= 2:
        try:
            return float(center_norm[0]), float(center_norm[1])
        except Exception:
            pass

    center_m = item.get("center_m") or []
    width = float(sheet_size.get("width") or 0)
    height = float(sheet_size.get("height") or 0)
    if len(center_m) >= 2 and width > 0 and height > 0:
        try:
            return float(center_m[0]) / width, float(center_m[1]) / height
        except Exception:
            pass
    return None


def _slot_layout_points(sample: dict[str, Any]) -> dict[str, tuple[float, float]]:
    sheet_size = sample.get("sheet_size_m") or {}
    items: list[dict[str, Any]] = []
    for index, item in enumerate(sample.get("view_layout") or []):
        if not isinstance(item, dict):
            continue
        point = _layout_point(item, sheet_size)
        if point is None:
            continue
        items.append({
            "index": index,
            "type": str(item.get("type") or ""),
            "point": point,
        })
    if not items:
        return {}

    base_items = [item for item in items if item["type"] != "4"]
    projected_items = [item for item in items if item["type"] == "4"]
    front = max(base_items or items, key=lambda item: (item["point"][1], -item["point"][0]))
    slots: dict[str, tuple[float, float]] = {"front": front["point"]}

    remaining_projected = list(projected_items)
    if remaining_projected:
        front_x, front_y = front["point"]
        lower_projected = [
            item for item in remaining_projected
            if item["point"][1] < front_y - 0.02
        ]
        top_pool = lower_projected or remaining_projected
        top = min(
            top_pool,
            key=lambda item: (
                abs(item["point"][0] - front_x),
                abs(item["point"][1] - front_y),
                item["index"],
            ),
        )
        slots["top"] = top["point"]
        remaining_projected = [item for item in remaining_projected if item is not top]

    if remaining_projected:
        front_x, front_y = front["point"]
        right_pool = [
            item for item in remaining_projected
            if item["point"][0] > front_x + 0.02
        ] or remaining_projected
        right = max(
            right_pool,
            key=lambda item: (
                item["point"][0],
                -abs(item["point"][1] - front_y),
                -item["index"],
            ),
        )
        slots["right"] = right["point"]

    remaining_base = [item for item in base_items if item is not front]
    if remaining_base:
        front_x, front_y = front["point"]
        iso_pool = [
            item for item in remaining_base
            if item["point"][0] > front_x + 0.02 or item["point"][1] < front_y - 0.02
        ] or remaining_base
        iso = max(
            iso_pool,
            key=lambda item: (
                item["point"][0],
                -abs(item["point"][1] - front_y),
                -item["index"],
            ),
        )
        slots["iso"] = iso["point"]

    return slots


def _point_payload(point: tuple[float, float]) -> list[float]:
    return [round(point[0], 4), round(point[1], 4)]


def _layout_score_and_differences(
    reference: dict[str, Any],
    generated: dict[str, Any],
    add_difference,
) -> float:
    ref_slots = _slot_layout_points(reference)
    if not ref_slots:
        return 1.0

    gen_slots = _slot_layout_points(generated)
    if not gen_slots:
        add_difference(
            "view_layout_metrics_unavailable",
            "need_review",
            sorted(ref_slots),
            [],
            "Extract generated drawing view outlines and compare sheet-normalized view centers with the reference drawing.",
        )
        return 0.0

    slot_scores: list[float] = []
    for key in sorted(ref_slots):
        ref_point = ref_slots[key]
        gen_point = gen_slots.get(key)
        if gen_point is None:
            add_difference(
                "view_layout_center_missing",
                "need_review",
                {"slot": key, "center_norm": _point_payload(ref_point)},
                {"available_slots": sorted(gen_slots)},
                "Create the same semantic view slot as the reference drawing before accepting this generated drawing.",
            )
            slot_scores.append(0.0)
            continue

        dx = gen_point[0] - ref_point[0]
        dy = gen_point[1] - ref_point[1]
        distance = (dx * dx + dy * dy) ** 0.5
        if distance > LAYOUT_CENTER_TOLERANCE_NORM:
            add_difference(
                "view_layout_center_shifted_from_reference",
                "need_review",
                {
                    "slot": key,
                    "center_norm": _point_payload(ref_point),
                    "tolerance_norm": LAYOUT_CENTER_TOLERANCE_NORM,
                },
                {
                    "slot": key,
                    "center_norm": _point_payload(gen_point),
                    "distance_norm": round(distance, 4),
                },
                "Place the generated view center within the learned reference layout tolerance for this LB26001 sample.",
            )
            slot_scores.append(max(0.0, 1.0 - (distance - LAYOUT_CENTER_TOLERANCE_NORM) / 0.32))
        else:
            slot_scores.append(1.0)

    return round(sum(slot_scores) / len(slot_scores), 3) if slot_scores else 1.0


def derive_profile(reference_metrics_by_base: dict[str, dict[str, Any]]) -> dict[str, Any]:
    samples: dict[str, dict[str, Any]] = {
        base: _sample(base, metrics)
        for base, metrics in reference_metrics_by_base.items()
    }
    usable = {base: item for base, item in samples.items() if item.get("success")}
    view_counts = sorted({_int(item.get("view_count")) for item in usable.values() if _int(item.get("view_count")) > 0})
    type_totals: Counter[str] = Counter()
    projected_samples = 0
    for item in usable.values():
        types = item.get("view_types") or {}
        type_totals.update({str(k): _int(v) for k, v in types.items()})
        if _int(types.get("4")) > 0:
            projected_samples += 1

    dim_values = [_int(item.get("display_dim_count")) for item in usable.values()]
    aggregate = {
        "allowed_view_counts": view_counts,
        "exact_view_count_by_sample": {base: _int(item.get("view_count")) for base, item in usable.items()},
        "view_type_totals": dict(type_totals),
        "projected_view_type": "4",
        "projected_view_required": bool(usable) and projected_samples >= max(1, len(usable) // 2),
        "projected_view_sample_count": projected_samples,
        "min_projected_view_count_by_sample": {
            base: _int((item.get("view_types") or {}).get("4"))
            for base, item in usable.items()
        },
        "min_display_dim_by_sample": {
            base: _int(item.get("display_dim_count"))
            for base, item in usable.items()
        },
        "display_dim_range": {
            "min": min(dim_values) if dim_values else 0,
            "max": max(dim_values) if dim_values else 0,
        },
        "sheet_sizes_m": sorted({
            json.dumps(item.get("sheet_size_m") or {}, sort_keys=True)
            for item in usable.values()
        }),
    }
    aggregate["sheet_sizes_m"] = [json.loads(item) for item in aggregate["sheet_sizes_m"]]

    return {
        "schema": "sw_drawing_studio.reference_style_profile.v1",
        "generated_at": _now(),
        "status": "profile_ready" if len(usable) == len(samples) and usable else "need_review",
        "sample_count": len(samples),
        "usable_sample_count": len(usable),
        "reference_samples": samples,
        "aggregate": aggregate,
        "rules": [
            {
                "key": "view_count_must_match_reference_for_known_sample",
                "severity": "need_review",
                "fix_suggestion": "Select the same 2/3/4-view layout family as the original reference drawing for this part.",
            },
            {
                "key": "projected_view_type_4_required_when_reference_uses_it",
                "severity": "need_review",
                "fix_suggestion": "Create top/right projected drawing views from the base view instead of independent named model views.",
            },
            {
                "key": "view_type_counts_must_match_reference",
                "severity": "need_review",
                "fix_suggestion": "Match the same-name reference drawing view type counts instead of adding or replacing view families.",
            },
            {
                "key": "generated_display_dim_must_not_be_lower_than_reference",
                "severity": "fail",
                "fix_suggestion": "Generate real SolidWorks DisplayDim annotations; do not count Notes, OCR text, or QC sidecar values as DisplayDim.",
            },
            {
                "key": "view_layout_centers_must_match_reference",
                "severity": "need_review",
                "fix_suggestion": "Compare front/top/right/iso sheet-normalized view centers against the same-name reference drawing.",
            },
        ],
    }


def evaluate_generated_against_reference(
    base: str,
    reference_metrics: dict[str, Any],
    generated_metrics: dict[str, Any],
    qc: dict[str, Any] | None = None,
) -> dict[str, Any]:
    reference = _sample(base, reference_metrics)
    generated = _sample(base, generated_metrics)
    qc = qc or {}
    differences: list[dict[str, Any]] = []

    def add(key: str, severity: str, reference_value: Any, generated_value: Any, fix: str) -> None:
        differences.append({
            "key": key,
            "severity": severity,
            "reference": reference_value,
            "generated": generated_value,
            "fix_suggestion": fix,
        })

    ref_views = _int(reference.get("view_count"))
    gen_views = _int(generated.get("view_count"))
    if ref_views > 0 and gen_views != ref_views:
        add(
            "view_count_not_equal_reference",
            "need_review",
            ref_views,
            gen_views,
            "Match the reference drawing view count for this known LB26001 sample.",
        )

    ref_types = reference.get("view_types") or {}
    gen_types = generated.get("view_types") or {}
    ref_projected = _int(ref_types.get("4"))
    gen_projected = _int(gen_types.get("4"))
    for view_type in sorted(set(ref_types) | set(gen_types), key=str):
        ref_count = _int(ref_types.get(view_type))
        gen_count = _int(gen_types.get(view_type))
        if ref_count > 0 and gen_count < ref_count:
            add(
                "view_type_count_lower_than_reference",
                "need_review",
                {"type": str(view_type), "count": ref_count},
                {"type": str(view_type), "count": gen_count},
                "Create the same number of reference view-family instances for this known LB26001 sample.",
            )
        elif ref_count > 0 and gen_count > ref_count:
            add(
                "view_type_count_higher_than_reference",
                "need_review",
                {"type": str(view_type), "count": ref_count},
                {"type": str(view_type), "count": gen_count},
                "Remove extra views from this view family or prove the same-name reference requires them.",
            )
        elif ref_count <= 0 and gen_count > 0:
            add(
                "view_type_extra_than_reference",
                "need_review",
                {"type": str(view_type), "count": 0},
                {"type": str(view_type), "count": gen_count},
                "Do not add section/detail/view families that are absent from the same-name reference drawing.",
            )
    if ref_projected > 0 and gen_projected < ref_projected:
        add(
            "projected_view_count_lower_than_reference",
            "need_review",
            ref_projected,
            gen_projected,
            "Use real projected views for the orthographic top/right views.",
        )
    if ref_projected > 0 and gen_views > 0 and _int(gen_types.get("7")) == gen_views:
        add(
            "generated_all_named_model_views",
            "need_review",
            "reference uses projected type 4 views",
            json.dumps(gen_types, ensure_ascii=False),
            "Do not build every orthographic view with CreateDrawViewFromModelView3 named views.",
        )

    ref_dims = _int(reference.get("display_dim_count"))
    gen_dims = _int(generated.get("display_dim_count"))
    dimension_validation = qc.get("dimension_validation") or {}
    dimension_sources = qc.get("dimension_sources") or {}
    qc_dims = _int(
        qc.get("display_dim_count")
        or dimension_validation.get("display_dim_count")
        or dimension_sources.get("display_dim_count")
    )
    if ref_dims > 0 and gen_dims <= 0:
        add(
            "generated_display_dim_zero_with_reference_baseline",
            "fail",
            ref_dims,
            gen_dims,
            "Generate real SolidWorks DisplayDim annotations before counting the drawing as deliverable.",
        )
    elif ref_dims > 0 and gen_dims < ref_dims:
        add(
            "display_dim_count_lower_than_reference",
            "fail",
            ref_dims,
            gen_dims,
            "Bring generated DisplayDim coverage up to the same-name reference drawing baseline.",
        )
    elif ref_dims > 0 and gen_dims > max(ref_dims + 2, int((ref_dims * 1.5) + 0.999)):
        add(
            "display_dim_count_higher_than_reference",
            "need_review",
            ref_dims,
            gen_dims,
            "Avoid over-dimensioning beyond the same-name reference drawing style; prefer the minimum manufacturable set.",
        )
    if qc_dims > gen_dims:
        add(
            "qc_dimension_fallback_not_displaydim",
            "warning",
            f"reference_display_dim={ref_dims}",
            f"generated_display_dim={gen_dims}; qc_display_dim={qc_dims}",
            "Keep QC-derived sidecar dimensions separate from real CAD DisplayDim counts.",
        )

    layout_score = _layout_score_and_differences(reference, generated, add)

    severities = {str(item.get("severity")) for item in differences}
    if "fail" in severities:
        status = "fail"
    elif "need_review" in severities:
        status = "need_review"
    elif "warning" in severities:
        status = "pass_with_warning"
    else:
        status = "pass"

    view_score = 1.0
    if ref_views > 0:
        count_score = 1.0 if gen_views == ref_views else max(0.0, 1.0 - abs(gen_views - ref_views) / max(ref_views, gen_views, 1))
        projected_score = 1.0 if ref_projected <= 0 else min(gen_projected / ref_projected, 1.0)
        type_scores: list[float] = []
        for view_type in sorted(set(ref_types) | set(gen_types), key=str):
            ref_count = _int(ref_types.get(view_type))
            gen_count = _int(gen_types.get(view_type))
            if ref_count <= 0:
                type_scores.append(0.0 if gen_count > 0 else 1.0)
            elif gen_count <= 0:
                type_scores.append(0.0)
            else:
                type_scores.append(min(gen_count / ref_count, ref_count / gen_count, 1.0))
        type_count_score = sum(type_scores) / len(type_scores) if type_scores else 1.0
        view_score = round((count_score * 0.30) + (projected_score * 0.35) + (type_count_score * 0.35), 3)
    if ref_dims <= 0:
        dimension_score = 1.0
    elif gen_dims <= 0:
        dimension_score = 0.0
    else:
        dimension_score = round(min(gen_dims / ref_dims, ref_dims / gen_dims, 1.0), 3)
    overall = round((view_score * 0.35) + (dimension_score * 0.45) + (layout_score * 0.20), 3)

    return {
        "base": base,
        "status": status,
        "pass": status in {"pass", "pass_with_warning"},
        "view_style_score": view_score,
        "dimension_style_score": dimension_score,
        "layout_style_score": layout_score,
        "overall_style_score": overall,
        "reference": reference,
        "generated": generated,
        "qc_display_dim_count": qc_dims,
        "differences": differences,
        "reasons": [
            str(item.get("key"))
            for item in differences
            if item.get("severity") in {"fail", "need_review", "warning"}
        ],
    }


def _case_by_base(summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    cases: dict[str, dict[str, Any]] = {}
    for case in summary.get("cases") or []:
        if not isinstance(case, dict):
            continue
        base = str(case.get("part_name") or Path(str(case.get("part") or "")).stem)
        if base:
            cases[base] = case
    return cases


def build_profile_and_gap_report(
    bases: list[str],
    reference_dir: Path,
    out_dir: Path,
    stage_summary_path: Path | None = None,
    *,
    no_sidecar: bool = False,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    out_dir.mkdir(parents=True, exist_ok=True)
    reference_metrics: dict[str, dict[str, Any]] = {}
    gap_cases: list[dict[str, Any]] = []
    summary = _read_json(stage_summary_path) if stage_summary_path else {}
    cases_by_base = _case_by_base(summary)

    for base in bases:
        report_path = Path(str((cases_by_base.get(base) or {}).get("reference_report") or ""))
        report = _read_json(report_path) if report_path.exists() else {}
        metrics = report.get("reference_metrics") if isinstance(report, dict) else None
        if not metrics:
            drawing = reference_dir / f"{base}.SLDDRW"
            if no_sidecar:
                metrics = {
                    "path": str(drawing),
                    "exists": drawing.exists(),
                    "success": False,
                    "reason": "sidecar_disabled_and_no_reference_compare_report",
                }
            else:
                metrics = _run_reference_metrics_sidecar(drawing, f"{base}_style_reference")
        metrics = _normalize_view_metrics(dict(metrics))
        reference_metrics[base] = metrics
        _write_json(out_dir / f"{base}_reference_metrics.json", metrics)

        if report.get("generated_metrics"):
            case = cases_by_base.get(base) or {}
            qc_path = Path(str((case.get("dimension_report") or "")))
            qc = _read_json(qc_path) if qc_path.exists() else {}
            gap_cases.append(
                evaluate_generated_against_reference(
                    base,
                    metrics,
                    report.get("generated_metrics") or {},
                    qc=qc,
                )
            )

    profile = derive_profile(reference_metrics)
    profile["source"] = {
        "reference_dir": str(reference_dir),
        "stage_summary": str(stage_summary_path or ""),
    }
    _write_json(out_dir / "lb26001_reference_style_profile.json", profile)
    _write_profile_markdown(out_dir / "lb26001_reference_style_profile.md", profile)

    gap_report = None
    if gap_cases:
        pass_count = sum(1 for item in gap_cases if item.get("status") == "pass")
        gap_report = {
            "schema": "sw_drawing_studio.reference_style_gap.v1",
            "generated_at": _now(),
            "source_profile": str(out_dir / "lb26001_reference_style_profile.json"),
            "stage_summary": str(stage_summary_path or ""),
            "sample_count": len(gap_cases),
            "pass_count": pass_count,
            "need_review_count": sum(1 for item in gap_cases if item.get("status") == "need_review"),
            "fail_count": sum(1 for item in gap_cases if item.get("status") == "fail"),
            "status": "pass" if pass_count == len(gap_cases) else "fail",
            "pass": pass_count == len(gap_cases),
            "cases": gap_cases,
        }
        _write_json(out_dir / "lb26001_reference_style_gap_report.json", gap_report)
        _write_gap_markdown(out_dir / "lb26001_reference_style_gap_report.md", gap_report)
    return profile, gap_report


def _write_profile_markdown(path: Path, profile: dict[str, Any]) -> None:
    aggregate = profile.get("aggregate") or {}
    lines = [
        "# LB26001 Reference Style Profile",
        "",
        f"- status: `{profile.get('status')}`",
        f"- samples: `{profile.get('usable_sample_count')}/{profile.get('sample_count')}`",
        f"- allowed view counts: `{aggregate.get('allowed_view_counts')}`",
        f"- projected view required: `{aggregate.get('projected_view_required')}`",
        f"- display dim range: `{aggregate.get('display_dim_range')}`",
        "",
        "## Samples",
    ]
    for base, sample in (profile.get("reference_samples") or {}).items():
        lines.append(
            f"- `{base}`: views={sample.get('view_count')}, "
            f"types={sample.get('view_types')}, DisplayDim={sample.get('display_dim_count')}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_gap_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# LB26001 Reference Style Gap Report",
        "",
        f"- status: `{report.get('status')}`",
        f"- pass: `{report.get('pass')}`",
        f"- samples: `{report.get('sample_count')}`",
        f"- pass/need_review/fail: `{report.get('pass_count')}/{report.get('need_review_count')}/{report.get('fail_count')}`",
        "",
        "## Cases",
    ]
    for case in report.get("cases") or []:
        lines.append(
            f"- `{case.get('base')}`: status={case.get('status')}, "
            f"score={case.get('overall_style_score')}, reasons={case.get('reasons')}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build LB26001 reference drawing style profile and gap report.")
    parser.add_argument("--bases", nargs="*", default=DEFAULT_REFERENCE_BASES)
    parser.add_argument("--reference-dir", default=str(DEFAULT_REFERENCE_DIR))
    parser.add_argument("--stage-summary", default="")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--no-sidecar", action="store_true")
    args = parser.parse_args()

    reference_dir = Path(args.reference_dir)
    if not reference_dir.is_absolute():
        reference_dir = (REPO_ROOT / reference_dir).resolve()
    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = (REPO_ROOT / out_dir).resolve()
    stage_summary = Path(args.stage_summary) if args.stage_summary else None
    if stage_summary is not None and not stage_summary.is_absolute():
        stage_summary = (REPO_ROOT / stage_summary).resolve()

    profile, gap_report = build_profile_and_gap_report(
        list(args.bases),
        reference_dir,
        out_dir,
        stage_summary,
        no_sidecar=args.no_sidecar,
    )
    result = {
        "profile": str(out_dir / "lb26001_reference_style_profile.json"),
        "profile_status": profile.get("status"),
        "gap_report": str(out_dir / "lb26001_reference_style_gap_report.json") if gap_report else "",
        "gap_status": (gap_report or {}).get("status", ""),
        "pass": bool(gap_report.get("pass")) if gap_report else profile.get("status") == "profile_ready",
    }
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
