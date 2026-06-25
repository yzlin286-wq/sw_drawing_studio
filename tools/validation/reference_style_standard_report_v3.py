"""Write a human-readable LB26001 drawing standard from learned reference metrics."""
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

from tools.validation.reference_style_profile_v3 import LAYOUT_CENTER_TOLERANCE_NORM, _slot_layout_points


DEFAULT_PROFILE = REPO_ROOT / "drw_output" / "reference_style_profile" / "lb26001_reference_style_profile.json"
DEFAULT_GAP = (
    REPO_ROOT
    / "drw_output"
    / "reference_style_profile"
    / "type_count_gate_recheck_20260622"
    / "lb26001_reference_style_gap_report.json"
)
DEFAULT_OUT_JSON = REPO_ROOT / "drw_output" / "reference_style_profile" / "lb26001_drawing_standard_v3_0.json"
DEFAULT_OUT_MD = REPO_ROOT / "drw_output" / "reference_style_profile" / "lb26001_drawing_standard_v3_0.md"

VIEW_TYPE_LABELS = {
    "4": "投影视图",
    "7": "标准/命名模型视图",
}


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


def _view_types_text(view_types: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in sorted(view_types, key=str):
        label = VIEW_TYPE_LABELS.get(str(key), f"类型{key}")
        parts.append(f"{key}({label})x{_int(view_types.get(key))}")
    return ", ".join(parts) or "-"


def _sheet_mm(sample: dict[str, Any]) -> dict[str, float]:
    sheet = sample.get("sheet_size_m") or {}
    try:
        return {
            "width": round(float(sheet.get("width") or 0) * 1000.0, 1),
            "height": round(float(sheet.get("height") or 0) * 1000.0, 1),
        }
    except Exception:
        return {"width": 0.0, "height": 0.0}


def _slot_payload(sample: dict[str, Any]) -> dict[str, list[float]]:
    slots = _slot_layout_points(sample)
    return {
        key: [round(point[0], 4), round(point[1], 4)]
        for key, point in sorted(slots.items())
    }


def _section_policy(sample: dict[str, Any]) -> dict[str, Any]:
    view_types = {str(key): _int(value) for key, value in (sample.get("view_types") or {}).items()}
    only_standard_projected = bool(view_types) and set(view_types).issubset({"4", "7"})
    return {
        "automatic_section_or_detail_allowed": not only_standard_projected,
        "reason": (
            "same-name reference uses only standard/named and projected views"
            if only_standard_projected
            else "reference includes or permits non-standard view families"
        ),
    }


def _sample_rule(sample: dict[str, Any]) -> dict[str, Any]:
    view_types = {str(key): _int(value) for key, value in (sample.get("view_types") or {}).items()}
    slots = _slot_payload(sample)
    return {
        "base": str(sample.get("base") or ""),
        "reference_drawing": str(sample.get("path") or ""),
        "sheet_size_mm": _sheet_mm(sample),
        "required_view_count": _int(sample.get("view_count")),
        "required_view_types": view_types,
        "required_projected_view_count": _int(view_types.get("4")),
        "display_dim_floor": _int(sample.get("display_dim_count")),
        "annotation_count_reference": _int(sample.get("annotation_count")),
        "layout_slots_center_norm": slots,
        "layout_tolerance_norm": LAYOUT_CENTER_TOLERANCE_NORM,
        "section_policy": _section_policy(sample),
        "must_not_count_as_display_dim": ["Note", "OCR text", "QC sidecar", "visual-only text"],
        "correction_checks": [
            "generated view_count must equal required_view_count",
            "generated view_types must equal required_view_types",
            "generated real DisplayDim count must be >= display_dim_floor",
            "generated semantic layout centers must stay within layout_tolerance_norm",
            "automatic section/detail views must remain disabled when section_policy forbids them",
        ],
    }


def _gap_summary(gap_report: dict[str, Any]) -> dict[str, Any]:
    if not gap_report:
        return {}
    cases = gap_report.get("cases") or []
    difference_counts: dict[str, int] = {}
    for case in cases:
        if not isinstance(case, dict):
            continue
        for diff in case.get("differences") or []:
            if isinstance(diff, dict):
                key = str(diff.get("key") or "")
                if key:
                    difference_counts[key] = difference_counts.get(key, 0) + 1
    return {
        "source_report": str(gap_report.get("source_profile") or ""),
        "stage_summary": str(gap_report.get("stage_summary") or ""),
        "status": str(gap_report.get("status") or ""),
        "pass": bool(gap_report.get("pass")),
        "sample_count": _int(gap_report.get("sample_count")),
        "pass_count": _int(gap_report.get("pass_count")),
        "need_review_count": _int(gap_report.get("need_review_count")),
        "fail_count": _int(gap_report.get("fail_count")),
        "difference_counts": dict(sorted(difference_counts.items())),
    }


def build_standard(profile: dict[str, Any], gap_report: dict[str, Any] | None = None) -> dict[str, Any]:
    samples = profile.get("reference_samples") or {}
    sample_rules = [
        _sample_rule(sample)
        for _, sample in sorted(samples.items())
        if isinstance(sample, dict) and sample.get("success")
    ]
    return {
        "schema": "sw_drawing_studio.lb26001_drawing_standard.v1",
        "generated_at": _now(),
        "status": "standard_ready" if sample_rules else "fail",
        "pass": bool(sample_rules),
        "source_profile_status": str(profile.get("status") or ""),
        "source_profile_generated_at": str(profile.get("generated_at") or ""),
        "sample_count": len(sample_rules),
        "reference_scope": [rule["base"] for rule in sample_rules],
        "global_rules": [
            {
                "key": "exact_same_name_view_family",
                "severity": "need_review",
                "rule": "已学习的 LB26001 同名样本必须匹配参考图纸的视图数量和视图类型计数。",
            },
            {
                "key": "projected_views_are_not_named_view_substitutes",
                "severity": "need_review",
                "rule": "参考图中的 type 4 投影视图必须用真实投影视图生成，不能用独立命名模型视图替代。",
            },
            {
                "key": "real_displaydim_floor",
                "severity": "fail",
                "rule": "生成图纸的真实 SolidWorks DisplayDim 数量不得低于同名参考图纸基线。",
            },
            {
                "key": "no_note_or_sidecar_displaydim_substitution",
                "severity": "fail",
                "rule": "Note、OCR 文本、视觉文本和 QC sidecar 数值只能辅助复核，不能计为真实 DisplayDim。",
            },
            {
                "key": "reference_layout_center_tolerance",
                "severity": "need_review",
                "rule": f"front/top/right/iso 语义视图中心必须保持在参考布局 {LAYOUT_CENTER_TOLERANCE_NORM:.2f} 归一化图幅单位内。",
            },
            {
                "key": "no_extra_section_or_detail_for_six_samples",
                "severity": "need_review",
                "rule": "六张已学习样本只使用 type 7 和 type 4，同名零件禁用自动新增剖视图/详图。",
            },
        ],
        "sample_rules": sample_rules,
        "current_gap_summary": _gap_summary(gap_report or {}),
        "next_cad_test_plan": [
            "先恢复可响应的 SolidWorks COM active-object 会话，再进行真实修正测试。",
            "通过 JobRuntimeFacade/start_cad_job 重跑 LB26001-A-04-006，并要求视图类型 7x2/4x2、DisplayDim >= 12、无额外视图族、布局通过。",
            "006 通过后，再按各自视图规则和 DisplayDim 下限重跑 007/008/009/015/022。",
            "六张样本全部通过 strict style gate 后，才允许重跑 LB26001_36。",
        ],
        "non_release_note": "本报告只是已学习制图规范和离线证据；只有 fresh SLDDRW/PDF/DXF/PNG 全部通过严格验证后，才能作为真实 CAD 通过证明。",
    }


def render_markdown(standard: dict[str, Any]) -> str:
    lines: list[str] = [
        "# LB26001 参考图纸制图规范 v3.0",
        "",
        f"- 生成时间: `{standard.get('generated_at')}`",
        f"- 状态: `{standard.get('status')}`",
        f"- 样本数量: `{standard.get('sample_count')}`",
        "- 判定: 这是规范学习报告，不是最终真实 CAD 通过证明。",
        "",
        "## 全局硬规则",
        "",
    ]
    for rule in standard.get("global_rules") or []:
        lines.append(f"- `{rule['key']}` [{rule['severity']}]: {rule['rule']}")

    lines.extend([
        "",
        "## 样本规则",
        "",
        "| 图号 | 视图数 | 视图类型 | DisplayDim 下限 | 图幅(mm) | 布局槽中心(norm) | 剖视/详图策略 |",
        "| --- | ---: | --- | ---: | --- | --- | --- |",
    ])
    for rule in standard.get("sample_rules") or []:
        sheet = rule.get("sheet_size_mm") or {}
        sheet_text = f"{sheet.get('width', 0)} x {sheet.get('height', 0)}"
        slots = rule.get("layout_slots_center_norm") or {}
        slot_text = "; ".join(
            f"{key}=({value[0]:.4f},{value[1]:.4f})"
            for key, value in sorted(slots.items())
        ) or "-"
        section = rule.get("section_policy") or {}
        section_text = "禁止自动新增剖视/详图" if not section.get("automatic_section_or_detail_allowed") else "允许按参考图复核"
        lines.append(
            "| {base} | {views} | {types} | {dims} | {sheet} | {slots} | {section} |".format(
                base=rule.get("base"),
                views=rule.get("required_view_count"),
                types=_view_types_text(rule.get("required_view_types") or {}),
                dims=rule.get("display_dim_floor"),
                sheet=sheet_text,
                slots=slot_text,
                section=section_text,
            )
        )

    gap = standard.get("current_gap_summary") or {}
    lines.extend(["", "## 当前历史差距", ""])
    if gap:
        lines.extend([
            f"- gap 状态: `{gap.get('status')}`, pass=`{gap.get('pass')}`",
            f"- 样本: `{gap.get('sample_count')}`, pass=`{gap.get('pass_count')}`, need_review=`{gap.get('need_review_count')}`, fail=`{gap.get('fail_count')}`",
            "- 差异计数:",
        ])
        for key, count in (gap.get("difference_counts") or {}).items():
            lines.append(f"  - `{key}`: {count}")
    else:
        lines.append("- 未提供历史 gap report。")

    lines.extend([
        "",
        "## 修正测试顺序",
        "",
    ])
    for index, item in enumerate(standard.get("next_cad_test_plan") or [], start=1):
        lines.append(f"{index}. {item}")
    lines.extend(["", f"> {standard.get('non_release_note')}", ""])
    return "\n".join(lines)


def write_standard_reports(standard: dict[str, Any], out_json: Path, out_md: Path) -> None:
    _write_json(out_json, standard)
    _write_text(out_md, render_markdown(standard))


def main() -> int:
    parser = argparse.ArgumentParser(description="Build LB26001 drawing standard report from reference style profile.")
    parser.add_argument("--profile", default=str(DEFAULT_PROFILE))
    parser.add_argument("--gap-report", default=str(DEFAULT_GAP))
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    parser.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    args = parser.parse_args()

    profile = _read_json(Path(args.profile))
    gap_report = _read_json(Path(args.gap_report)) if args.gap_report else {}
    standard = build_standard(profile, gap_report)
    out_json = Path(args.out_json)
    out_md = Path(args.out_md)
    if not out_json.is_absolute():
        out_json = (REPO_ROOT / out_json).resolve()
    if not out_md.is_absolute():
        out_md = (REPO_ROOT / out_md).resolve()
    write_standard_reports(standard, out_json, out_md)
    print(json.dumps({
        "pass": standard["pass"],
        "status": standard["status"],
        "sample_count": standard["sample_count"],
        "out_json": str(out_json),
        "out_md": str(out_md),
    }, ensure_ascii=False))
    return 0 if standard["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
