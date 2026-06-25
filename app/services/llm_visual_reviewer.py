"""v2.0 Task 6: LLM Visual Reviewer

LLM 只做复核和解释，不做主检测
基于 PDF/PNG + OCR 文本 + 检测结果生成复核意见
"""
from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Any


def review_drawing(
    pdf_path: Path,
    png_path: Path = None,
    ocr_result: dict = None,
    symbol_result: dict = None,
    yolo_result: dict = None,
    qc_data: dict = None,
    run_dir: Path = None,
) -> dict:
    """LLM 复核工程图

    Args:
        pdf_path: PDF 文件路径
        png_path: PNG 预览图路径
        ocr_result: OCR 提取结果
        symbol_result: 符号检测结果
        yolo_result: YOLO 检测结果
        qc_data: QC 数据
        run_dir: run_dir 根目录

    Returns:
        {
            "success": bool,
            "review": dict,
            "reason": str,
        }
    """
    pdf_path = Path(pdf_path).resolve() if pdf_path else None

    result = {
        "success": False,
        "review": {},
        "reason": "",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    try:
        from app.services.llm_client import LLMClient

        client = LLMClient()

        # 构建复核 prompt
        prompt = _build_review_prompt(
            pdf_path, ocr_result, symbol_result, yolo_result, qc_data
        )

        # 调用 LLM
        llm_response = client.chat(prompt)

        # 解析 LLM 响应
        review = _parse_llm_response(llm_response)

        result["review"] = review
        result["success"] = True
        result["reason"] = "LLM 复核完成"

    except ImportError:
        # LLM 客户端不可用，使用规则复核
        result["review"] = _rule_based_review(
            ocr_result, symbol_result, yolo_result, qc_data
        )
        result["success"] = True
        result["reason"] = "LLM 客户端不可用，使用规则复核"
    except Exception as e:
        result["review"] = _rule_based_review(
            ocr_result, symbol_result, yolo_result, qc_data
        )
        result["success"] = True
        result["reason"] = f"LLM 调用失败，使用规则复核: {e}"

    return result


def _build_review_prompt(
    pdf_path: Path,
    ocr_result: dict,
    symbol_result: dict,
    yolo_result: dict,
    qc_data: dict,
) -> str:
    """构建 LLM 复核 prompt"""
    parts = []
    parts.append("你是工程图质检专家。请复核以下工程图质检结果，给出复核意见。")
    parts.append("\n## 质检数据\n")

    if qc_data:
        parts.append(f"- part_class: {qc_data.get('part_class', 'unknown')}")
        parts.append(f"- dim_total: {qc_data.get('checks', {}).get('dim_count_sufficient', {}).get('dim_total', 0)}")
        parts.append(f"- hard_fail: {qc_data.get('hard_fail', [])}")
        parts.append(f"- warnings: {len(qc_data.get('warnings', []))}")

    if ocr_result:
        titlebar = ocr_result.get("titlebar", {})
        parts.append(f"\n## 标题栏\n- {json.dumps(titlebar, ensure_ascii=False)}")

    if symbol_result:
        parts.append(f"\n## 符号检测\n- symbol_count: {symbol_result.get('symbol_count', 0)}")

    if yolo_result:
        parts.append(f"\n## 元素检测\n- method: {yolo_result.get('method', 'unknown')}")
        parts.append(f"- detection_count: {yolo_result.get('detection_count', 0)}")
        parts.append(f"- by_type: {json.dumps(yolo_result.get('by_type', {}), ensure_ascii=False)}")

    parts.append("\n## 请输出\n")
    parts.append("```json")
    parts.append('{')
    parts.append('  "overall_assessment": "pass/warning/fail",')
    parts.append('  "issues": [{"key": "...", "severity": "major/minor", "description": "...", "fix_suggestion": "..."}],')
    parts.append('  "summary": "总体评价"')
    parts.append('}')
    parts.append("```")

    return "\n".join(parts)


def _parse_llm_response(response: str) -> dict:
    """解析 LLM 响应"""
    try:
        # 尝试提取 JSON
        import re
        json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(1))

        # 尝试直接解析
        return json.loads(response)
    except Exception:
        return {
            "overall_assessment": "unknown",
            "issues": [],
            "summary": response[:500] if response else "",
        }


def _rule_based_review(
    ocr_result: dict,
    symbol_result: dict,
    yolo_result: dict,
    qc_data: dict,
) -> dict:
    """基于规则的复核（LLM 不可用时的 fallback）"""
    issues = []
    overall = "pass"

    if qc_data:
        hard_fail = qc_data.get("hard_fail", [])
        if hard_fail:
            overall = "fail"
            issues.append({
                "key": "hard_fail",
                "severity": "critical",
                "description": f"硬失败项: {hard_fail}",
                "fix_suggestion": "修复硬失败项",
            })

        dim_total = qc_data.get("checks", {}).get("dim_count_sufficient", {}).get("dim_total", 0)
        if dim_total == 0:
            issues.append({
                "key": "no_dimensions",
                "severity": "major",
                "description": "图纸中无尺寸标注",
                "fix_suggestion": "使用 Add-in Dimension Engine 生成尺寸",
            })
            if overall == "pass":
                overall = "warning"

    if ocr_result:
        titlebar = ocr_result.get("titlebar", {})
        if not titlebar.get("drawing_number"):
            issues.append({
                "key": "missing_drawing_number",
                "severity": "minor",
                "description": "标题栏缺少图号",
                "fix_suggestion": "补充图号",
            })

    if symbol_result and symbol_result.get("symbol_count", 0) == 0:
        issues.append({
            "key": "no_surface_finish",
            "severity": "minor",
            "description": "未检测到表面粗糙度符号",
            "fix_suggestion": "添加 Ra 符号",
        })

    return {
        "overall_assessment": overall,
        "issues": issues,
        "summary": f"规则复核: {len(issues)} 个问题",
        "method": "rule_based",
    }
