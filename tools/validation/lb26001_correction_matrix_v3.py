"""Build the LB26001 strict correction-test matrix from the learned standard."""
from __future__ import annotations

import argparse
from collections import Counter
import json
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


DEFAULT_STANDARD = REPO_ROOT / "drw_output" / "reference_style_profile" / "lb26001_drawing_standard_v3_0.json"
DEFAULT_GAP = (
    REPO_ROOT
    / "drw_output"
    / "reference_style_profile"
    / "type_count_gate_recheck_20260622"
    / "lb26001_reference_style_gap_report.json"
)
DEFAULT_REFERENCE_DIR = REPO_ROOT / "3D转2D测试图纸"
DEFAULT_OUT_JSON = REPO_ROOT / "drw_output" / "reference_style_profile" / "lb26001_correction_test_matrix_v3_0.json"
DEFAULT_OUT_MD = REPO_ROOT / "drw_output" / "reference_style_profile" / "lb26001_correction_test_matrix_v3_0.md"


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


def _relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except Exception:
        return str(path)


def _gap_cases(gap_report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    cases: dict[str, dict[str, Any]] = {}
    for case in gap_report.get("cases") or []:
        if isinstance(case, dict) and case.get("base"):
            cases[str(case["base"])] = case
    return cases


def _difference_keys(case: dict[str, Any]) -> list[str]:
    keys: list[str] = []
    for diff in case.get("differences") or []:
        if isinstance(diff, dict) and diff.get("key"):
            keys.append(str(diff["key"]))
    return sorted(dict.fromkeys(keys))


def _score_payload(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": str(case.get("status") or "missing"),
        "pass": bool(case.get("pass")),
        "view_style_score": case.get("view_style_score"),
        "dimension_style_score": case.get("dimension_style_score"),
        "layout_style_score": case.get("layout_style_score"),
        "overall_style_score": case.get("overall_style_score"),
        "generated_drawing": str(((case.get("generated") or {}).get("path")) or ""),
    }


def _short(base: str) -> str:
    return base.rsplit("-", 1)[-1].lower()


def _command_templates(base: str, part_rel: str) -> dict[str, str]:
    short = _short(base)
    cad_out = f"drw_output\\cad_smoke_stylefix_{short}.json"
    dim_out = f"drw_output\\dimension_validation_stylefix_{short}.json"
    ref_out = f"drw_output\\reference_compare_stylefix_{short}.json"
    return {
        "real_cad_smoke": (
            f'python tools\\validation\\real_cad_smoke_v3.py --part "{part_rel}" '
            f"--timeout-s 900 --max-rounds 1 --out {cad_out}"
        ),
        "dimension_validation": (
            f"python tools\\validation\\dimension_validation_smoke_v3.py "
            f"--run-dir <fresh_run_dir> --cad-smoke {cad_out} --out {dim_out}"
        ),
        "reference_compare": (
            f'python tools\\validation\\reference_compare_smoke_v3.py --run-dir <fresh_run_dir> '
            f'--part "{part_rel}" --reference-dir "3D转2D测试图纸" --cad-smoke {cad_out} '
            f"--out {ref_out} --metrics-mode sidecar_first --sidecar-timeout-s 120"
        ),
    }


def _acceptance_criteria(rule: dict[str, Any]) -> list[dict[str, Any]]:
    required_types = {
        str(key): _int(value)
        for key, value in (rule.get("required_view_types") or {}).items()
    }
    return [
        {
            "key": "fresh_cad_artifacts",
            "severity": "fail",
            "required": "fresh run_dir with manifest, sw_session, job_event_log, SLDDRW, PDF, DXF, PNG, qc, vision_qc, final_quality",
        },
        {
            "key": "worker_events",
            "severity": "fail",
            "required": "job_started/progress/heartbeat/job_finished or job_failed with reason",
        },
        {
            "key": "view_count_exact",
            "severity": "need_review",
            "required": _int(rule.get("required_view_count")),
        },
        {
            "key": "view_type_counts_exact",
            "severity": "need_review",
            "required": required_types,
        },
        {
            "key": "real_displaydim_floor",
            "severity": "fail",
            "required": f"DisplayDim >= {_int(rule.get('display_dim_floor'))}",
        },
        {
            "key": "layout_center_tolerance",
            "severity": "need_review",
            "required": {
                "slots": rule.get("layout_slots_center_norm") or {},
                "tolerance_norm": rule.get("layout_tolerance_norm"),
            },
        },
        {
            "key": "no_extra_section_or_detail",
            "severity": "need_review",
            "required": not bool((rule.get("section_policy") or {}).get("automatic_section_or_detail_allowed")),
        },
        {
            "key": "no_displaydim_substitution",
            "severity": "fail",
            "required": "Do not count Note/OCR/QC sidecar/visual-only text as real DisplayDim.",
        },
    ]


def build_matrix(
    standard: dict[str, Any],
    gap_report: dict[str, Any],
    *,
    reference_dir: Path = DEFAULT_REFERENCE_DIR,
) -> dict[str, Any]:
    cases = _gap_cases(gap_report)
    entries: list[dict[str, Any]] = []
    difference_counter: Counter[str] = Counter()
    missing_parts: list[str] = []

    for index, rule in enumerate(standard.get("sample_rules") or [], start=1):
        if not isinstance(rule, dict):
            continue
        base = str(rule.get("base") or "")
        if not base:
            continue
        part_path = reference_dir / f"{base}.SLDPRT"
        if not part_path.exists():
            missing_parts.append(str(part_path))
        part_rel = _relative(part_path)
        gap_case = cases.get(base, {})
        diff_keys = _difference_keys(gap_case)
        difference_counter.update(diff_keys)
        entries.append(
            {
                "sequence": index,
                "base": base,
                "part_path": str(part_path),
                "part_exists": part_path.exists(),
                "reference_drawing": str(rule.get("reference_drawing") or ""),
                "must_not_modify_original_part": True,
                "required_view_count": _int(rule.get("required_view_count")),
                "required_view_types": {
                    str(key): _int(value)
                    for key, value in (rule.get("required_view_types") or {}).items()
                },
                "display_dim_floor": _int(rule.get("display_dim_floor")),
                "layout_slots_center_norm": rule.get("layout_slots_center_norm") or {},
                "layout_tolerance_norm": rule.get("layout_tolerance_norm"),
                "section_policy": rule.get("section_policy") or {},
                "current_gap": _score_payload(gap_case),
                "current_difference_keys": diff_keys,
                "command_templates": _command_templates(base, part_rel),
                "acceptance_criteria": _acceptance_criteria(rule),
            }
        )

    return {
        "schema": "sw_drawing_studio.lb26001_correction_test_matrix.v1",
        "generated_at": _now(),
        "status": "ready_for_real_cad_when_solidworks_responds" if entries and not missing_parts else "need_review",
        "pass": bool(entries) and not missing_parts,
        "source_standard_status": str(standard.get("status") or ""),
        "source_gap_status": str(gap_report.get("status") or ""),
        "source_gap_pass": bool(gap_report.get("pass")),
        "sample_count": len(entries),
        "missing_part_paths": missing_parts,
        "preconditions": [
            "SolidWorks 进程必须可响应，且 COM active-object probe 成功。",
            "重启或重跑修正测试前，必须先保存所有打开的 SolidWorks 工作。",
            "必须通过 JobRuntimeFacade/QProcess worker 执行；UI 线程不得直接调用 SolidWorks COM。",
            "必须把 SLDPRT/SLDASM 复制到 run_dir/input_work；不得修改原始测试 CAD 文件。",
            "不得降低 QC 阈值，也不得把 Note/OCR/QC sidecar 数值计为真实 DisplayDim。",
        ],
        "pilot_case": "LB26001-A-04-006",
        "entries": entries,
        "current_gap_difference_counts": dict(difference_counter.most_common()),
        "after_all_six_pass_command": (
            "python tools\\validation\\staged_cad_validation_v3.py "
            "--set-name LB26001_36 --out-root drw_output\\staged_validation"
        ),
        "non_release_note": (
            "本矩阵只是修正测试计划和离线验收清单；只有 fresh CAD 输出通过上述门槛后，才能作为可交付图纸证明。"
        ),
    }


def render_markdown(matrix: dict[str, Any]) -> str:
    lines: list[str] = [
        "# LB26001 修正测试矩阵 v3.0",
        "",
        f"- 生成时间: `{matrix.get('generated_at')}`",
        f"- 状态: `{matrix.get('status')}`",
        f"- 样本数量: `{matrix.get('sample_count')}`",
        f"- pilot: `{matrix.get('pilot_case')}`",
        "- 判定: 这是修正测试计划，不是最终真实 CAD 通过证明。",
        "",
        "## 前置条件",
        "",
    ]
    for item in matrix.get("preconditions") or []:
        lines.append(f"- {item}")

    lines.extend([
        "",
        "## 样本矩阵",
        "",
        "| 顺序 | 图号 | SLDPRT | 视图规则 | DisplayDim 下限 | 当前状态 | 当前主要差异 | 首个重跑命令 |",
        "| ---: | --- | --- | --- | ---: | --- | --- | --- |",
    ])
    for entry in matrix.get("entries") or []:
        types = ", ".join(
            f"{key}x{value}"
            for key, value in sorted((entry.get("required_view_types") or {}).items())
        )
        diffs = ", ".join(entry.get("current_difference_keys") or []) or "-"
        command = (entry.get("command_templates") or {}).get("real_cad_smoke", "")
        part_label = "存在" if entry.get("part_exists") else "缺失"
        current = (entry.get("current_gap") or {}).get("status", "")
        lines.append(
            f"| {entry.get('sequence')} | {entry.get('base')} | {part_label} | "
            f"{entry.get('required_view_count')} 视图; {types} | {entry.get('display_dim_floor')} | "
            f"{current} | {diffs} | `{command}` |"
        )

    lines.extend(["", "## 当前差异计数", ""])
    for key, count in (matrix.get("current_gap_difference_counts") or {}).items():
        lines.append(f"- `{key}`: {count}")
    if not matrix.get("current_gap_difference_counts"):
        lines.append("- 无历史差异输入。")

    lines.extend([
        "",
        "## 六件样本全部通过后的下一步",
        "",
        f"`{matrix.get('after_all_six_pass_command')}`",
        "",
        f"> {matrix.get('non_release_note')}",
        "",
    ])
    return "\n".join(lines)


def write_matrix_reports(matrix: dict[str, Any], out_json: Path, out_md: Path) -> None:
    _write_json(out_json, matrix)
    _write_text(out_md, render_markdown(matrix))


def main() -> int:
    parser = argparse.ArgumentParser(description="Build LB26001 strict correction-test matrix.")
    parser.add_argument("--standard", default=str(DEFAULT_STANDARD))
    parser.add_argument("--gap-report", default=str(DEFAULT_GAP))
    parser.add_argument("--reference-dir", default=str(DEFAULT_REFERENCE_DIR))
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    parser.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    args = parser.parse_args()

    standard = _read_json(Path(args.standard))
    gap_report = _read_json(Path(args.gap_report))
    reference_dir = Path(args.reference_dir)
    if not reference_dir.is_absolute():
        reference_dir = (REPO_ROOT / reference_dir).resolve()
    out_json = Path(args.out_json)
    out_md = Path(args.out_md)
    if not out_json.is_absolute():
        out_json = (REPO_ROOT / out_json).resolve()
    if not out_md.is_absolute():
        out_md = (REPO_ROOT / out_md).resolve()

    matrix = build_matrix(standard, gap_report, reference_dir=reference_dir)
    write_matrix_reports(matrix, out_json, out_md)
    print(json.dumps({
        "pass": matrix["pass"],
        "status": matrix["status"],
        "sample_count": matrix["sample_count"],
        "out_json": str(out_json),
        "out_md": str(out_md),
    }, ensure_ascii=False))
    return 0 if matrix["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
