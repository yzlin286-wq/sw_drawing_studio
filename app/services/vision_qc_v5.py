"""v2.3 Task 5: Vision QC v5

在 v4 基础上增加:
  - 证据融合 (evidence_fusion)
  - 误报过滤 (false_positive_filter)
  - 零件类别规则 (category-specific rules)
  - 040 的 1.7mm 标题栏边缘碰撞降级为 info

5 步流程:
  1. 运行 v4 获取基础结果
  2. 运行 evidence_fusion 融合多源结果
  3. 运行 false_positive_filter 过滤已知误报
  4. 应用零件类别规则
  5. 构建最终 issues 列表

输出: vision_qc_v5.json
每个 issue 必须有: key, severity, bbox, source, confidence, fix_suggestion, evidence
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class VisionIssue:
    """Vision QC 问题"""
    key: str
    severity: str  # critical / major / minor / info
    bbox: list[float]  # 4 个归一化值 [x, y, w, h]
    source: str  # geometry_qc / pdf_text / ocr / template / yolo_obb / llm_review
    confidence: float
    fix_suggestion: str
    evidence: list[dict] = field(default_factory=list)  # 支持证据列表
    human_review: str = ""  # pending / confirmed_false_positive / confirmed_issue
    description: str = ""


def run_vision_qc_v5(
    pdf_path: Optional[Path] = None,
    png_path: Optional[Path] = None,
    qc_json_path: Optional[Path] = None,
    run_dir: Optional[Path] = None,
    run_id: str = "",
    part_category: str = "",
) -> dict:
    """运行 Vision QC v5

    Args:
        pdf_path: PDF 文件路径
        png_path: PNG 预览图路径(可选)
        qc_json_path: QC JSON 路径(可选)
        run_dir: 运行目录
        run_id: 运行 ID
        part_category: 零件类别 (fastener/spring/purchased_part/...)

    Returns:
        Vision QC v5 结果字典
    """
    start = time.time()

    pdf_path = Path(pdf_path) if pdf_path else None

    result = {
        "version": "v5",
        "run_id": run_id,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "pdf_path": str(pdf_path) if pdf_path else "",
        "part_category": part_category,
        "success": False,
        "reason": "",
        "issues": [],
        "summary": {
            "total_issues": 0,
            "critical": 0,
            "major": 0,
            "minor": 0,
            "info": 0,
        },
        "steps": {},
        "fallback_used": False,
    }

    if pdf_path is None or not pdf_path.exists():
        result["reason"] = f"PDF 不存在: {pdf_path}"
        result["fallback_used"] = True
        _finalize_v5(result, run_dir, start)
        return result

    # ========== Step 1: 运行 v4 获取基础结果 ==========
    try:
        from app.services.vision_qc_v4 import run_vision_qc_v4
        v4_result = run_vision_qc_v4(
            pdf_path=pdf_path,
            png_path=png_path,
            qc_json_path=qc_json_path,
            run_dir=run_dir,
            run_id=run_id,
        )
        result["steps"]["v4_base"] = {
            "success": v4_result.get("success", False),
            "mode": v4_result.get("mode", ""),
            "issue_count": len(v4_result.get("issues", [])),
        }
        v4_issues = v4_result.get("issues", [])
        result["fallback_used"] = v4_result.get("fallback_used", False)
    except Exception as e:
        result["steps"]["v4_base"] = {"success": False, "error": str(e)}
        v4_issues = []
        result["fallback_used"] = True

    # ========== Step 2: 证据融合 ==========
    try:
        from app.services.vision_evidence_fusion import EvidenceFusion
        fusion = EvidenceFusion()

        # 按 source 分组 v4 issues
        issues_from_sources: dict[str, list[dict]] = {}
        for issue in v4_issues:
            src = issue.get("source", "unknown")
            if src not in issues_from_sources:
                issues_from_sources[src] = []
            issues_from_sources[src].append(issue)

        # 同时从 qc_json 提取 geometry_qc issues
        if qc_json_path and Path(qc_json_path).exists():
            try:
                qc_data = json.loads(Path(qc_json_path).read_text(encoding="utf-8"))
                geo_issues = _extract_geometry_qc_issues(qc_data)
                if geo_issues:
                    issues_from_sources["geometry_qc"] = geo_issues
            except Exception:
                pass

        fused_issues = fusion.fuse_issues(issues_from_sources)
        result["steps"]["evidence_fusion"] = {
            "source_count": len(issues_from_sources),
            "fused_count": len(fused_issues),
        }
    except Exception as e:
        result["steps"]["evidence_fusion"] = {"error": str(e)}
        fused_issues = v4_issues  # 融合失败则使用 v4 原始结果

    # ========== Step 3: 误报过滤 ==========
    try:
        from app.services.vision_false_positive_filter import VisionFalsePositiveFilter
        fp_filter = VisionFalsePositiveFilter()
        filtered_issues = fp_filter.filter_issues(fused_issues, part_category=part_category)
        result["steps"]["false_positive_filter"] = {
            "before_count": len(fused_issues),
            "after_count": len(filtered_issues),
            "filtered_count": len(fused_issues) - len(filtered_issues),
        }
    except Exception as e:
        result["steps"]["false_positive_filter"] = {"error": str(e)}
        filtered_issues = fused_issues

    # ========== Step 4: 零件类别规则 ==========
    filtered_issues = _apply_category_rules(filtered_issues, part_category)
    result["steps"]["category_rules"] = {
        "part_category": part_category,
        "applied": bool(part_category),
    }

    # ========== Step 5: 构建最终 issues 列表 ==========
    final_issues = []
    for issue in filtered_issues:
        # 确保每个 issue 都有所有必需字段
        vision_issue = {
            "key": issue.get("key", "unknown"),
            "severity": issue.get("severity", "info"),
            "bbox": issue.get("bbox", [0.0, 0.0, 0.0, 0.0]),
            "source": issue.get("source", "unknown"),
            "confidence": issue.get("confidence", 0.5),
            "fix_suggestion": issue.get("fix_suggestion", ""),
            "evidence": issue.get("evidence", []),
            "human_review": issue.get("human_review", "pending"),
            "description": issue.get("description", ""),
        }

        # 特殊规则: 040 的 1.7mm 标题栏边缘碰撞降级为 info
        if (vision_issue["key"] == "titlebar_collision"
                and _is_titlebar_edge_collision_040(vision_issue)):
            vision_issue["severity"] = "info"
            vision_issue["description"] = (
                vision_issue.get("description", "")
                + " [040: 1.7mm 标题栏边缘碰撞, 降级为 info]"
            )

        final_issues.append(vision_issue)

    result["issues"] = final_issues

    # 汇总
    _finalize_v5(result, run_dir, start)
    return result


def _extract_geometry_qc_issues(qc_data: dict) -> list[dict]:
    """从 qc.json 提取 geometry_qc 类型的 issues"""
    issues = []
    hard_fail = qc_data.get("hard_fail", [])
    warnings = qc_data.get("warnings", [])

    for hf in hard_fail:
        key = hf if isinstance(hf, str) else hf.get("key", "unknown")
        issues.append({
            "key": key,
            "severity": "critical",
            "source": "geometry_qc",
            "confidence": 0.95,
            "bbox": [0.0, 0.0, 0.0, 0.0],
            "description": f"QC hard_fail: {key}",
            "fix_suggestion": "",
            "evidence": [{"type": "hard_fail", "value": str(hf)}],
        })

    for w in warnings:
        key = w if isinstance(w, str) else w.get("key", "unknown")
        issues.append({
            "key": key,
            "severity": "minor",
            "source": "geometry_qc",
            "confidence": 0.8,
            "bbox": [0.0, 0.0, 0.0, 0.0],
            "description": f"QC warning: {key}",
            "fix_suggestion": "",
            "evidence": [{"type": "warning", "value": str(w)}],
        })

    return issues


def _apply_category_rules(issues: list[dict], part_category: str) -> list[dict]:
    """应用零件类别特定规则

    Args:
        issues: 问题列表
        part_category: 零件类别

    Returns:
        应用规则后的问题列表
    """
    if not part_category:
        return issues

    # 标准件/弹簧/外购件: 不需要 datum/ra
    no_datum_ra_categories = {"fastener", "spring", "purchased_part"}

    if part_category.lower() in no_datum_ra_categories:
        for issue in issues:
            key = issue.get("key", "")
            if key in ("missing_datum", "missing_ra"):
                issue["severity"] = "info"
                issue["description"] = (
                    issue.get("description", "")
                    + f" [{part_category} 类别不需要此检查, 降级为 info]"
                )

    return issues


def _is_titlebar_edge_collision_040(issue: dict) -> bool:
    """判断是否为 040 的 1.7mm 标题栏边缘碰撞

    通过 evidence 中的 overlap_x_mm 字段判断
    """
    evidence = issue.get("evidence", [])
    for ev in evidence:
        overlap = ev.get("overlap_x_mm", None)
        if overlap is not None and float(overlap) <= 2.0:
            return True
    # 也检查 issue 本身的字段
    overlap = issue.get("overlap_x_mm", None)
    if overlap is not None and float(overlap) <= 2.0:
        return True
    return False


def _finalize_v5(result: dict, run_dir: Optional[Path], start: float):
    """完成 v5 结果"""
    # 汇总 issues
    for issue in result["issues"]:
        sev = issue.get("severity", "info")
        result["summary"]["total_issues"] += 1
        if sev in result["summary"]:
            result["summary"][sev] += 1

    # 成功条件
    has_critical = result["summary"]["critical"] > 0
    result["success"] = not has_critical
    result["reason"] = "Vision QC v5 完成" if result["success"] else "Vision QC v5 存在 critical 问题"
    result["duration_ms"] = int((time.time() - start) * 1000)

    # 保存
    if run_dir:
        _write_v5_result(run_dir, result)


def _write_v5_result(run_dir: Path, result: dict):
    """写入 vision_qc_v5.json"""
    out_dir = Path(run_dir)
    qc_dir = out_dir / "qc"
    qc_dir.mkdir(parents=True, exist_ok=True)

    out_path = qc_dir / "vision_qc_v5.json"
    out_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return out_path
