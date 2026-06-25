"""v1.8 Task 2: Drawing Accuracy Score

计算图纸准确性综合分数（0-100），分项:
  - layout (20): 视图布局质量（view_overlap / view_in_frame / scale）
  - dimension (35): 尺寸完整性（dim_total / dimension_coverage / sidecar）
  - titlebar (10): 标题栏完整性（13 keys / gb_titlebar）
  - annotation (15): 标注完整性（tech_note / ra_note / datum_a / standard_annotation）
  - visual_clarity (20): 视觉清晰度（text_height / vision_score / png_missing）

输出到 qc.json 的 drawing_accuracy_score 字段，并同步到 manifest。
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any


def compute_drawing_accuracy_score(qc_data: dict) -> dict:
    """计算 drawing_accuracy_score

    Args:
        qc_data: qc.json 的完整 dict

    Returns:
        {
            "total": int,  # 0-100
            "layout": {"score": int, "max": 20, "details": {...}},
            "dimension": {"score": int, "max": 35, "details": {...}},
            "titlebar": {"score": int, "max": 10, "details": {...}},
            "annotation": {"score": int, "max": 15, "details": {...}},
            "visual_clarity": {"score": int, "max": 20, "details": {...}},
            "grade_label": str,  # A/B/C/D
            "reasons": [str],  # 扣分原因
        }
    """
    checks = qc_data.get("checks", {})
    reasons = []

    # === 1. Layout (20 分) ===
    layout_score = 0
    layout_details = {}

    # view_overlap (8 分)
    vo = checks.get("view_overlap", {})
    if vo.get("pass") is True:
        layout_score += 8
        layout_details["view_overlap"] = 8
    else:
        reasons.append("layout.view_overlap: 视图重叠")
        layout_details["view_overlap"] = 0

    # view_in_frame (7 分)
    vif = checks.get("view_in_frame", {})
    if vif.get("pass") is True:
        layout_score += 7
        layout_details["view_in_frame"] = 7
    else:
        reasons.append("layout.view_in_frame: 视图超出图框")
        layout_details["view_in_frame"] = 0

    # scale_in_set (5 分)
    sis = checks.get("scale_in_set", {})
    if sis.get("pass") is True:
        layout_score += 5
        layout_details["scale_in_set"] = 5
    else:
        reasons.append("layout.scale_in_set: 比例非标准")
        layout_details["scale_in_set"] = 0

    # === 2. Dimension (35 分) ===
    dim_score = 0
    dim_details = {}

    dim_total = checks.get("dim_count_sufficient", {}).get("dim_total", 0)
    dim_cov = checks.get("dimension_coverage", {})
    part_class = qc_data.get("part_class", "feature_part")
    has_sidecar = qc_data.get("has_valid_sidecar_annotation", False)
    std_anno = qc_data.get("standard_annotation_present", False)
    is_purchased = part_class in ("fastener", "spring", "purchased_part")

    # dim_total 评分 (20 分)
    if dim_total >= 5:
        dim_score += 20
        dim_details["dim_total"] = 20
    elif dim_total >= 3:
        dim_score += 12
        dim_details["dim_total"] = 12
        reasons.append(f"dimension.dim_total: {dim_total} < 5")
    elif dim_total > 0:
        dim_score += 6
        dim_details["dim_total"] = 6
        reasons.append(f"dimension.dim_total: {dim_total} < 3")
    else:
        # dim_total=0 但有 sidecar 标注
        if has_sidecar or std_anno:
            dim_score += 8
            dim_details["dim_total"] = 8
            reasons.append("dimension.dim_total=0 但有 sidecar/标准标注")
        else:
            dim_score += 0
            dim_details["dim_total"] = 0
            reasons.append("dimension.dim_total=0 无标注")

    # dimension_coverage associativity (8 分)
    assoc = dim_cov.get("associativity", "unknown")
    if assoc == "model":
        dim_score += 8
        dim_details["associativity"] = 8
    elif assoc in ("mixed", "non_model"):
        dim_score += 4
        dim_details["associativity"] = 4
        reasons.append(f"dimension.associativity: {assoc}")
    else:
        dim_score += 1
        dim_details["associativity"] = 1
        reasons.append(f"dimension.associativity: {assoc}")

    # overall dimensions (7 分)
    overall_count = sum(1 for k in ("overall_length", "overall_width", "overall_height")
                        if dim_cov.get(k) is not None)
    sidecar_overall = qc_data.get("sidecar_overall", {})
    sidecar_overall_count = sum(1 for k in ("overall_length", "overall_width", "overall_height")
                                if sidecar_overall.get(k) is not None)
    total_overall = max(overall_count, sidecar_overall_count)
    overall_score = min(7, total_overall * 3)
    dim_score += overall_score
    dim_details["overall"] = overall_score
    if total_overall < 3:
        reasons.append(f"dimension.overall: 仅 {total_overall}/3 向")

    # === 3. Titlebar (10 分) ===
    titlebar_score = 0
    titlebar_details = {}

    # all_13_keys_present (6 分)
    keys_check = checks.get("all_13_keys_present", {})
    if keys_check.get("pass") is True:
        titlebar_score += 6
        titlebar_details["keys"] = 6
    else:
        present = keys_check.get("present_count", 0)
        titlebar_score += min(4, present // 4)
        titlebar_details["keys"] = min(4, present // 4)
        reasons.append(f"titlebar.keys: {present}/13")

    # gb_titlebar_complete (4 分)
    gb_tb = checks.get("gb_titlebar_complete", {})
    if gb_tb.get("pass") is True:
        titlebar_score += 4
        titlebar_details["gb_titlebar"] = 4
    else:
        titlebar_details["gb_titlebar"] = 0
        reasons.append("titlebar.gb_titlebar: 不完整")

    # === 4. Annotation (15 分) ===
    anno_score = 0
    anno_details = {}

    # has_tech_note (4 分)
    if checks.get("has_tech_note", {}).get("pass") is True:
        anno_score += 4
        anno_details["tech_note"] = 4
    else:
        anno_details["tech_note"] = 0
        reasons.append("annotation.tech_note: 缺失")

    # has_ra_note (3 分)
    if checks.get("has_ra_note", {}).get("pass") is True:
        anno_score += 3
        anno_details["ra_note"] = 3
    else:
        anno_details["ra_note"] = 0

    # has_datum_a (3 分)
    if checks.get("has_datum_a", {}).get("pass") is True:
        anno_score += 3
        anno_details["datum_a"] = 3
    else:
        anno_details["datum_a"] = 0

    # standard_annotation_present (5 分) - 采购类专用
    if std_anno:
        anno_score += 5
        anno_details["standard_annotation"] = 5
    elif is_purchased:
        anno_details["standard_annotation"] = 0
        reasons.append("annotation.standard_annotation: 采购类缺失标准标注")
    else:
        # 非采购类给 2 分（不强制）
        anno_score += 2
        anno_details["standard_annotation"] = 2

    # === 5. Visual Clarity (20 分) ===
    visual_score = 0
    visual_details = {}

    # text_height_ge_3_5mm (5 分)
    th = checks.get("text_height_ge_3_5mm", {})
    if th.get("pass") is True:
        visual_score += 5
        visual_details["text_height"] = 5
    else:
        visual_details["text_height"] = 0
        reasons.append("visual.text_height: < 3.5mm")

    # png_missing (8 分) - 检查 hard_fail
    hard_fail = qc_data.get("hard_fail", [])
    if "png_missing" not in hard_fail:
        visual_score += 8
        visual_details["png"] = 8
    else:
        visual_details["png"] = 0
        reasons.append("visual.png: 缺失")

    # vision_score (7 分)
    vision = checks.get("vision_score", {}).get("score")
    if vision is not None:
        if vision >= 80:
            visual_score += 7
            visual_details["vision"] = 7
        elif vision >= 60:
            visual_score += 5
            visual_details["vision"] = 5
        elif vision >= 40:
            visual_score += 3
            visual_details["vision"] = 3
            reasons.append(f"visual.vision: {vision} < 60")
        else:
            visual_score += 1
            visual_details["vision"] = 1
            reasons.append(f"visual.vision: {vision} < 40")
    else:
        # 无 vision score，给中等分（不惩罚）
        visual_score += 4
        visual_details["vision"] = 4
        reasons.append("visual.vision: 未评估")

    # === 总分 ===
    total = layout_score + dim_score + titlebar_score + anno_score + visual_score

    # grade_label
    if total >= 85:
        grade_label = "A"
    elif total >= 70:
        grade_label = "B"
    elif total >= 50:
        grade_label = "C"
    else:
        grade_label = "D"

    return {
        "total": total,
        "layout": {"score": layout_score, "max": 20, "details": layout_details},
        "dimension": {"score": dim_score, "max": 35, "details": dim_details},
        "titlebar": {"score": titlebar_score, "max": 10, "details": titlebar_details},
        "annotation": {"score": anno_score, "max": 15, "details": anno_details},
        "visual_clarity": {"score": visual_score, "max": 20, "details": visual_details},
        "grade_label": grade_label,
        "reasons": reasons,
    }


def update_qc_with_accuracy_score(qc_json_path: Path) -> dict:
    """读取 qc.json，计算 accuracy score，写回

    Args:
        qc_json_path: qc.json 路径

    Returns:
        accuracy_score dict
    """
    qc_data = json.loads(qc_json_path.read_text(encoding="utf-8"))
    score = compute_drawing_accuracy_score(qc_data)
    qc_data["drawing_accuracy_score"] = score
    qc_json_path.write_text(json.dumps(qc_data, ensure_ascii=False, indent=2), encoding="utf-8")
    return score


def main():
    """CLI: python drawing_accuracy_score.py <qc.json>"""
    import sys
    if len(sys.argv) < 2:
        print("Usage: python drawing_accuracy_score.py <qc.json>")
        sys.exit(1)
    qc_path = Path(sys.argv[1])
    score = update_qc_with_accuracy_score(qc_path)
    print(json.dumps(score, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
