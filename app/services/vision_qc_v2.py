"""v1.8 Task 4: 视觉质检 v2

基于 qc.json + PNG + sidecar 结果生成 vision_qc_v2.json
检查项: titlebar / layout / dimension / annotation / readability

每个 issue 包含:
  - key: issue 标识
  - severity: critical / major / minor / info
  - bbox: [x, y, w, h] 归一化坐标 (0-1)
  - description: 问题描述
  - fix_suggestion: 修复建议
  - auto_fix_available: 是否可自动修复
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any


SIDECAR_DIMENSION_CLASSES = {"long_thin", "tiny_part"}
PURCHASE_CLASSES = {"fastener", "spring", "purchased_part"}


def run_vision_qc_v2(
    qc_json_path: Path,
    png_path: Path,
    run_dir: Path,
) -> dict:
    """运行视觉质检 v2

    Args:
        qc_json_path: qc.json 路径
        png_path: PNG 预览图路径
        run_dir: run_dir 根目录

    Returns:
        vision_qc_v2 dict
    """
    result = {
        "version": "v1.8",
        "source_qc": str(qc_json_path),
        "source_png": str(png_path),
        "issues": [],
        "summary": {
            "total": 0,
            "critical": 0,
            "major": 0,
            "minor": 0,
            "info": 0,
        },
        "checks": {
            "titlebar": {"pass": True, "issues": []},
            "layout": {"pass": True, "issues": []},
            "dimension": {"pass": True, "issues": []},
            "annotation": {"pass": True, "issues": []},
            "readability": {"pass": True, "issues": []},
        },
    }

    # 读取 qc.json
    qc_data = {}
    try:
        qc_data = json.loads(qc_json_path.read_text(encoding="utf-8"))
    except Exception as e:
        result["issues"].append({
            "key": "qc_json_read_error",
            "severity": "critical",
            "bbox": [0, 0, 1, 1],
            "description": f"无法读取 qc.json: {e}",
            "fix_suggestion": "检查 qc.json 文件是否存在且格式正确",
            "auto_fix_available": False,
        })
        _finalize(result)
        _write_result(run_dir, result)
        return result

    checks = qc_data.get("checks", {})
    hard_fail = qc_data.get("hard_fail", [])
    warnings = qc_data.get("warnings", [])
    part_class = qc_data.get("part_class", "feature_part")
    dim_total = checks.get("dim_count_sufficient", {}).get("dim_total", 0)
    has_sidecar = qc_data.get("has_valid_sidecar_annotation", False)
    std_anno = qc_data.get("standard_annotation_present", False)
    dimension_grade = str(qc_data.get("dimension_grade") or "")
    dimension_sources = qc_data.get("dimension_sources", {})

    # === 1. Titlebar 检查 ===
    _check_titlebar(checks, warnings, result)

    # === 2. Layout 检查 ===
    _check_layout(checks, hard_fail, result)

    # === 3. Dimension 检查 ===
    _check_dimension(
        checks,
        dim_total,
        has_sidecar,
        std_anno,
        part_class,
        dimension_grade,
        dimension_sources,
        result,
    )

    # === 4. Annotation 检查 ===
    _check_annotation(checks, warnings, result)

    # === 5. Readability 检查 ===
    _check_readability(checks, png_path, result)

    _finalize(result)
    _write_result(run_dir, result)
    return result


def _check_titlebar(checks: dict, warnings: list, result: dict):
    """检查标题栏"""
    # all_13_keys_present
    keys_check = checks.get("all_13_keys_present", {})
    if keys_check.get("pass") is False:
        present = keys_check.get("present_count", 0)
        result["issues"].append({
            "key": "titlebar_keys_missing",
            "severity": "major",
            "bbox": [0.7, 0.85, 0.3, 0.15],
            "description": f"标题栏属性不完整，仅 {present}/13 项",
            "fix_suggestion": "检查标题栏模板，补全缺失属性（机型/品名/图号/材质等）",
            "auto_fix_available": True,
        })
        result["checks"]["titlebar"]["pass"] = False

    # gb_titlebar_complete
    if "gb_titlebar_complete" in warnings:
        result["issues"].append({
            "key": "titlebar_gb_incomplete",
            "severity": "minor",
            "bbox": [0.7, 0.85, 0.3, 0.15],
            "description": "标题栏不符合 GB 标准完整性要求",
            "fix_suggestion": "按 GB/T 10609.1 补全标题栏字段",
            "auto_fix_available": True,
        })


def _check_layout(checks: dict, hard_fail: list, result: dict):
    """检查布局"""
    # view_overlap
    if "view_overlap" in hard_fail:
        result["issues"].append({
            "key": "layout_view_overlap",
            "severity": "critical",
            "bbox": [0.1, 0.1, 0.8, 0.7],
            "description": "视图存在重叠",
            "fix_suggestion": "调整视图位置，确保视图间无重叠",
            "auto_fix_available": True,
        })
        result["checks"]["layout"]["pass"] = False

    # view_out_of_frame
    if "view_out_of_frame" in hard_fail:
        result["issues"].append({
            "key": "layout_view_out_of_frame",
            "severity": "critical",
            "bbox": [0, 0, 1, 1],
            "description": "视图超出图框边界",
            "fix_suggestion": "缩小视图比例或调整视图位置至图框内",
            "auto_fix_available": True,
        })
        result["checks"]["layout"]["pass"] = False

    # scale_in_set
    scale_check = checks.get("scale_in_set", {})
    if scale_check.get("pass") is False:
        scale = scale_check.get("scale", "?")
        result["issues"].append({
            "key": "layout_scale_nonstandard",
            "severity": "minor",
            "bbox": [0.4, 0.4, 0.2, 0.2],
            "description": f"比例 {scale} 非标准值",
            "fix_suggestion": "使用标准比例: 5:1/2:1/1:1/1:2/1:5/1:10 等",
            "auto_fix_available": True,
        })


def _has_overall_sidecar_evidence(dimension_sources: dict) -> bool:
    """Return True when sidecar provides usable overall L/W/H evidence."""
    if not isinstance(dimension_sources, dict):
        return False
    sidecar_overall = dimension_sources.get("sidecar_overall")
    if not isinstance(sidecar_overall, dict):
        return False
    required = ["overall_length", "overall_width", "overall_height"]
    return all(float(sidecar_overall.get(key) or 0) > 0 for key in required)


def _check_dimension(checks: dict, dim_total: int, has_sidecar: bool,
                     std_anno: bool, part_class: str, dimension_grade: str,
                     dimension_sources: dict, result: dict):
    """检查尺寸"""
    is_purchased = part_class in PURCHASE_CLASSES
    is_sidecar_class = part_class in SIDECAR_DIMENSION_CLASSES
    has_sidecar_evidence = bool(has_sidecar) or _has_overall_sidecar_evidence(dimension_sources)
    sidecar_grade_ok = dimension_grade in {"B", "C"}

    if dim_total == 0 and not has_sidecar and not std_anno:
        result["issues"].append({
            "key": "dimension_none",
            "severity": "critical",
            "bbox": [0.1, 0.1, 0.8, 0.7],
            "description": "图纸无任何尺寸标注",
            "fix_suggestion": "插入模型尺寸或使用 sidecar 补充总长/总宽/总高",
            "auto_fix_available": True,
        })
        result["checks"]["dimension"]["pass"] = False
    elif dim_total == 0 and has_sidecar:
        result["issues"].append({
            "key": "dimension_sidecar_only",
            "severity": "minor",
            "bbox": [0.1, 0.05, 0.3, 0.05],
            "description": "尺寸仅通过 sidecar Note 标注（非关联 DisplayDim）",
            "fix_suggestion": "考虑使用 InsertModelAnnotations3 插入关联尺寸",
            "auto_fix_available": False,
        })
    elif dim_total < 5 and not is_purchased:
        if is_sidecar_class and has_sidecar_evidence and sidecar_grade_ok:
            severity = "minor"
            description = (
                f"尺寸数量低于制造图阈值: DisplayDim={dim_total}/5；"
                f"{part_class} 已有 sidecar 三向尺寸证据，dimension_grade={dimension_grade}"
            )
            fix_suggestion = "保留为警告；如需制造级出图，补充真实 DisplayDim 或人工复核确认。"
            auto_fix_available = False
            evidence = {
                "part_class": part_class,
                "dimension_grade": dimension_grade,
                "display_dim_count": dim_total,
                "has_sidecar_evidence": True,
                "policy": "tiny_or_long_thin_sidecar_dimension_warning",
            }
        else:
            severity = "major"
            description = f"尺寸数量不足: {dim_total}/5"
            fix_suggestion = "补充关键尺寸标注（总长/总宽/总高/孔/槽）"
            auto_fix_available = True
            evidence = {
                "part_class": part_class,
                "dimension_grade": dimension_grade,
                "display_dim_count": dim_total,
                "has_sidecar_evidence": bool(has_sidecar_evidence),
                "policy": "manufacturing_display_dim_threshold",
            }
        result["issues"].append({
            "key": "dimension_insufficient",
            "severity": severity,
            "bbox": [0.1, 0.1, 0.8, 0.7],
            "description": description,
            "fix_suggestion": fix_suggestion,
            "auto_fix_available": auto_fix_available,
            "source": "geometry_qc",
            "confidence": 0.9,
            "evidence": evidence,
            "human_review_status": "pending",
        })

    # dimension_coverage associativity
    dim_cov = checks.get("dimension_coverage", {})
    assoc = dim_cov.get("associativity", "unknown")
    if assoc in ("none", "unknown"):
        result["issues"].append({
            "key": "dimension_no_associativity",
            "severity": "minor",
            "bbox": [0.1, 0.1, 0.8, 0.7],
            "description": f"尺寸关联性: {assoc}",
            "fix_suggestion": "使用模型关联尺寸而非手动标注",
            "auto_fix_available": False,
        })


def _check_annotation(checks: dict, warnings: list, result: dict):
    """检查标注"""
    # has_tech_note
    if checks.get("has_tech_note", {}).get("pass") is False:
        result["issues"].append({
            "key": "annotation_no_tech_note",
            "severity": "minor",
            "bbox": [0.1, 0.75, 0.5, 0.1],
            "description": "缺少技术要求注释",
            "fix_suggestion": "添加技术要求（如：未注公差按 GB/T 1804-m）",
            "auto_fix_available": True,
        })

    # has_ra_note
    if "has_ra_note" in warnings:
        result["issues"].append({
            "key": "annotation_no_ra",
            "severity": "minor",
            "bbox": [0.7, 0.05, 0.1, 0.05],
            "description": "缺少表面粗糙度 Ra 标注",
            "fix_suggestion": "在标题栏右上角标注 '其余 Ra=3.2'",
            "auto_fix_available": True,
        })

    # has_datum_a
    if "has_datum_a" in warnings:
        result["issues"].append({
            "key": "annotation_no_datum",
            "severity": "minor",
            "bbox": [0.1, 0.1, 0.8, 0.7],
            "description": "缺少基准 A 标注",
            "fix_suggestion": "添加基准代号 A（GB/T 1182-2008）",
            "auto_fix_available": False,
        })


def _check_readability(checks: dict, png_path: Path, result: dict):
    """检查可读性"""
    # text_height
    th_check = checks.get("text_height_ge_3_5mm", {})
    if th_check.get("pass") is False:
        h = th_check.get("text_height_m", 0)
        result["issues"].append({
            "key": "readability_text_too_small",
            "severity": "major",
            "bbox": [0.1, 0.1, 0.8, 0.7],
            "description": f"字高 {h*1000:.2f}mm < 3.5mm",
            "fix_suggestion": "设置字高 >= 3.5mm (GetUserPreferenceDoubleValue(89))",
            "auto_fix_available": True,
        })
        result["checks"]["readability"]["pass"] = False

    # PNG 存在性
    if not png_path.exists():
        result["issues"].append({
            "key": "readability_png_missing",
            "severity": "major",
            "bbox": [0, 0, 1, 1],
            "description": "PNG 预览图缺失",
            "fix_suggestion": "检查 PNG 导出逻辑（PDF→PyMuPDF 回退）",
            "auto_fix_available": True,
        })
        result["checks"]["readability"]["pass"] = False

    # vision_score
    vision = checks.get("vision_score", {}).get("score")
    if vision is not None and vision < 60:
        result["issues"].append({
            "key": "readability_vision_low",
            "severity": "major",
            "bbox": [0, 0, 1, 1],
            "description": f"视觉评分 {vision} < 60",
            "fix_suggestion": "改善图纸清晰度、布局、标注完整性",
            "auto_fix_available": False,
        })


def _finalize(result: dict):
    """汇总统计"""
    for issue in result["issues"]:
        _normalize_issue_schema(issue)
        sev = issue.get("severity", "info")
        result["summary"][sev] = result["summary"].get(sev, 0) + 1
        result["summary"]["total"] += 1
        # 归类到 checks
        key = issue.get("key", "")
        if key.startswith("titlebar"):
            result["checks"]["titlebar"]["issues"].append(issue["key"])
        elif key.startswith("layout"):
            result["checks"]["layout"]["issues"].append(issue["key"])
        elif key.startswith("dimension"):
            result["checks"]["dimension"]["issues"].append(issue["key"])
        elif key.startswith("annotation"):
            result["checks"]["annotation"]["issues"].append(issue["key"])
        elif key.startswith("readability"):
            result["checks"]["readability"]["issues"].append(issue["key"])


def _normalize_issue_schema(issue: dict) -> None:
    """Ensure every issue carries the v3 review fields."""
    issue.setdefault("bbox", [0, 0, 1, 1])
    issue.setdefault("source", "geometry_qc")
    issue.setdefault("confidence", 0.8)
    issue.setdefault("evidence", {"description": issue.get("description", "")})
    issue.setdefault("fix_suggestion", "人工复核并补充修复建议")
    issue.setdefault("auto_fix_available", False)
    issue.setdefault("human_review_status", "pending")


def _write_result(run_dir: Path, result: dict):
    """写入 vision_qc_v2.json"""
    qc_dir = run_dir / "qc"
    qc_dir.mkdir(parents=True, exist_ok=True)
    out_path = qc_dir / "vision_qc_v2.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    """CLI: python vision_qc_v2.py <qc.json> <png_path> <run_dir>"""
    import sys
    if len(sys.argv) < 4:
        print("Usage: python vision_qc_v2.py <qc.json> <png_path> <run_dir>")
        sys.exit(1)
    result = run_vision_qc_v2(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
