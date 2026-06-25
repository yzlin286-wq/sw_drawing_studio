"""v1.8 Task 5 / v2.1 Task 6: 几何 QC + 视觉 QC 融合

融合 hard_fail / drawing_usable / dimension_grade / vision_qc_v2
输出 final_quality.json

status:
  - pass: 几何 + 视觉全通过
  - pass_with_warning: 有 warning 但无 hard_fail
  - pass_with_manual_review: v2.1 新增，有 human_review.json 标记 manual_confirmed
  - need_review: 几何与视觉冲突
  - fail: 有 hard_fail
"""
from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Any


def _load_human_review(run_dir) -> dict | None:
    """v2.1: 加载 human_review.json

    Returns:
        dict if exists and status=manual_confirmed, else None
    """
    if not run_dir:
        return None
    try:
        review_path = Path(run_dir) / "qc" / "human_review.json"
        if not review_path.exists():
            return None
        review = json.loads(review_path.read_text(encoding="utf-8"))
        if isinstance(review, dict) and review.get("status") == "manual_confirmed":
            return review
    except Exception:
        pass
    return None


def _load_vision_qc_v3_warnings(run_dir) -> list:
    """v2.1: 从 vision_qc_v3.json 加载 fallback_used 作为 warnings"""
    if not run_dir:
        return []
    try:
        vqc_path = Path(run_dir) / "qc" / "vision_qc_v3.json"
        if not vqc_path.exists():
            return []
        vqc = json.loads(vqc_path.read_text(encoding="utf-8"))
        fu = vqc.get("fallback_used", [])
        return [f"vision_qc_v3 fallback: {item}" for item in fu]
    except Exception:
        return []


def compute_final_quality(ctx, vision_qc_v2: dict, run_dir=None) -> dict:
    """计算 final_quality

    Args:
        ctx: RunContext
        vision_qc_v2: vision_qc_v2.json dict
        run_dir: v2.1 新增，run_dir 根目录（用于读取 human_review.json 和 vision_qc_v3.json）

    Returns:
        final_quality dict
    """
    hard_fail = list(ctx.hard_fail or [])
    warnings = list(ctx.warnings or [])
    drawing_usable_pass = False
    if isinstance(ctx.drawing_usable, dict):
        drawing_usable_pass = bool(ctx.drawing_usable.get("pass"))

    dimension_grade = ctx.dimension_grade or "D"
    usable_for = list(ctx.usable_for or [])

    # v2.1: 加载 vision_qc_v3 fallback_used 作为 warnings
    vqc3_warnings = _load_vision_qc_v3_warnings(run_dir)
    warnings.extend(vqc3_warnings)

    # v2.1: 加载 human_review.json
    human_review = _load_human_review(run_dir)
    has_manual_review = human_review is not None

    # vision_qc_v2 summary
    vqc_summary = vision_qc_v2.get("summary", {})
    vqc_critical = vqc_summary.get("critical", 0)
    vqc_major = vqc_summary.get("major", 0)
    vqc_minor = vqc_summary.get("minor", 0)
    vqc_total = vqc_summary.get("total", 0)

    # 几何 QC 状态
    geo_pass = len(hard_fail) == 0 and drawing_usable_pass
    geo_has_warning = len(warnings) > 0

    # 视觉 QC 状态
    vision_pass = vqc_critical == 0 and vqc_major == 0
    vision_has_warning = vqc_minor > 0

    # 融合判定
    if not geo_pass:
        # 几何 hard_fail
        status = "fail"
        reason = f"几何 QC hard_fail: {hard_fail}"
    elif geo_pass and vision_pass and not geo_has_warning and not vision_has_warning:
        status = "pass"
        reason = "几何 + 视觉全通过"
    elif geo_pass and vision_pass:
        # v2.1: 如果有 manual_review，升级为 pass_with_manual_review
        if has_manual_review:
            status = "pass_with_manual_review"
            reason = f"通过但有 warning (geo={len(warnings)}, vision={vqc_minor})，已人工确认"
        else:
            status = "pass_with_warning"
            reason = f"通过但有 warning (geo={len(warnings)}, vision={vqc_minor})"
    elif geo_pass and not vision_pass:
        # 几何通过但视觉有 critical/major → need_review
        # v2.1: 如果有 manual_review，升级为 pass_with_manual_review
        if has_manual_review:
            status = "pass_with_manual_review"
            reason = f"几何通过但视觉有 critical={vqc_critical} major={vqc_major}，已人工确认"
        else:
            status = "need_review"
            reason = f"几何通过但视觉有 critical={vqc_critical} major={vqc_major}"
    else:
        status = "fail"
        reason = f"未知状态 geo_pass={geo_pass} vision_pass={vision_pass}"

    # 冲突检测：几何通过但视觉 critical
    conflict = False
    conflict_reason = ""
    if geo_pass and vqc_critical > 0:
        conflict = True
        conflict_reason = f"几何 QC 通过但视觉 QC 有 {vqc_critical} 个 critical issue"
        if status in ("pass", "pass_with_warning"):
            # v2.1: 如果有 manual_review，保留 pass_with_manual_review
            if has_manual_review:
                status = "pass_with_manual_review"
                reason = conflict_reason + "，已人工确认"
            else:
                status = "need_review"
                reason = conflict_reason

    # v2.1: 可交付性判定（drawing_usable + 无 hard_fail + (pass/pass_with_warning/pass_with_manual_review)）
    deliverable = (
        len(hard_fail) == 0
        and drawing_usable_pass
        and status in ("pass", "pass_with_warning", "pass_with_manual_review")
    )

    return {
        "version": "v2.1",
        "status": status,
        "reason": reason,
        "conflict": conflict,
        "conflict_reason": conflict_reason,
        "deliverable": deliverable,
        "has_manual_review": has_manual_review,
        "manual_review": human_review or {},
        "geo_qc": {
            "pass": geo_pass,
            "hard_fail": hard_fail,
            "warnings_count": len(warnings),
            "drawing_usable_pass": drawing_usable_pass,
            "dimension_grade": dimension_grade,
            "usable_for": usable_for,
        },
        "vision_qc": {
            "pass": vision_pass,
            "critical": vqc_critical,
            "major": vqc_major,
            "minor": vqc_minor,
            "total_issues": vqc_total,
        },
        "drawing_accuracy_score": ctx.drawing_accuracy_score.get("total", 0) if isinstance(ctx.drawing_accuracy_score, dict) else 0,
        "recommendation": _get_recommendation(status, dimension_grade, vqc_critical, vqc_major, has_manual_review),
    }


def _get_recommendation(status: str, grade: str, vqc_critical: int, vqc_major: int, has_manual_review: bool = False) -> str:
    """生成建议"""
    if status == "pass":
        return "图纸质量良好，可交付"
    elif status == "pass_with_warning":
        if grade in ("A", "B"):
            return "图纸可用，建议复核 warning 项后交付"
        else:
            return "图纸达 C 级，仅限采购/装配使用"
    elif status == "pass_with_manual_review":
        return f"图纸已人工确认通过（grade={grade}），可按人工确认结果交付"
    elif status == "need_review":
        return f"几何与视觉冲突，需人工复核（视觉 critical={vqc_critical}），或通过 Workbench 标记人工确认"
    else:
        return "图纸不可交付，需修复 hard_fail 项后重新生成"
