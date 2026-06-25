"""v2.0 Task 6: OCR QC Service

OCR 标题栏 / 技术要求文本提取
使用 PyMuPDF 内置文本提取（无需 Tesseract）
"""
from __future__ import annotations
import json
import re
import time
from pathlib import Path
from typing import Any


def extract_text_from_pdf(pdf_path: Path) -> dict:
    """从 PDF 提取文本

    Returns:
        {
            "success": bool,
            "pdf_path": str,
            "pages": list,  # [{page: int, text: str, blocks: list}]
            "total_text": str,
            "reason": str,
        }
    """
    pdf_path = Path(pdf_path).resolve()

    result = {
        "success": False,
        "pdf_path": str(pdf_path),
        "pages": [],
        "total_text": "",
        "reason": "",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    if not pdf_path.exists():
        result["reason"] = f"PDF 不存在: {pdf_path}"
        return result

    try:
        import fitz

        doc = fitz.open(str(pdf_path))
        all_text = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text")
            all_text.append(text)

            # 提取文本块（带位置）
            blocks = []
            try:
                blocks_raw = page.get_text("blocks")
                for b in blocks_raw:
                    if len(b) >= 5:
                        blocks.append({
                            "bbox": [b[0], b[1], b[2], b[3]],
                            "text": b[4].strip(),
                        })
            except Exception:
                pass

            result["pages"].append({
                "page": page_num + 1,
                "text": text,
                "blocks": blocks,
            })

        doc.close()
        result["total_text"] = "\n".join(all_text)
        result["success"] = True
        result["reason"] = f"成功提取 {len(result['pages'])} 页文本"

    except Exception as e:
        result["reason"] = f"extract_text_from_pdf 异常: {e}"

    return result


def extract_titlebar_info(pdf_path: Path) -> dict:
    """提取标题栏信息

    识别标题栏中的关键字段:
    - 图号 (drawing number)
    - 名称 (part name)
    - 材料 (material)
    - 比例 (scale)
    - 日期 (date)
    - 设计者 (designer)

    Returns:
        {
            "success": bool,
            "titlebar": dict,
            "reason": str,
        }
    """
    pdf_path = Path(pdf_path).resolve()

    result = {
        "success": False,
        "titlebar": {},
        "reason": "",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    # 先提取文本
    text_result = extract_text_from_pdf(pdf_path)
    if not text_result["success"]:
        result["reason"] = text_result["reason"]
        return result

    total_text = text_result["total_text"]

    # 正则匹配标题栏字段
    titlebar = {}

    # 图号: LBXXXX / AK-XX-XX / 数字编号
    draw_no_match = re.search(r'(LB\d{4,}|AK[-\d]+|图号[:\s]*([A-Z0-9\-]+))', total_text)
    if draw_no_match:
        titlebar["drawing_number"] = draw_no_match.group(1).strip()

    # 比例: 1:X 或 1:X
    scale_match = re.search(r'比例[:\s]*(1[:\s*\d/]+)', total_text)
    if scale_match:
        titlebar["scale"] = scale_match.group(1).strip()
    else:
        scale_match2 = re.search(r'\b(1[:\s]\d+)\b', total_text)
        if scale_match2:
            titlebar["scale"] = scale_match2.group(1).strip()

    # 材料
    material_match = re.search(r'材料[:\s]*([A-Z0-9\-/]+)', total_text)
    if material_match:
        titlebar["material"] = material_match.group(1).strip()

    # 日期
    date_match = re.search(r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})', total_text)
    if date_match:
        titlebar["date"] = date_match.group(1).strip()

    # 单位
    unit_match = re.search(r'单位[:\s]*(mm|cm|in)', total_text, re.IGNORECASE)
    if unit_match:
        titlebar["unit"] = unit_match.group(1).strip()
    else:
        titlebar["unit"] = "mm"  # 默认 mm

    result["titlebar"] = titlebar
    result["success"] = True
    result["reason"] = "标题栏提取完成"

    return result


def extract_technical_requirements(pdf_path: Path) -> dict:
    """提取技术要求文本

    Returns:
        {
            "success": bool,
            "requirements": list,  # 技术要求条目
            "reason": str,
        }
    """
    pdf_path = Path(pdf_path).resolve()

    result = {
        "success": False,
        "requirements": [],
        "reason": "",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    text_result = extract_text_from_pdf(pdf_path)
    if not text_result["success"]:
        result["reason"] = text_result["reason"]
        return result

    total_text = text_result["total_text"]

    # 查找技术要求段落
    req_section = ""
    patterns = [
        r'技术要求[:\s]*(.*?)(?:\n\n|\Z)',
        r'技术条件[:\s]*(.*?)(?:\n\n|\Z)',
        r'Technical Requirements[:\s]*(.*?)(?:\n\n|\Z)',
    ]
    for pattern in patterns:
        match = re.search(pattern, total_text, re.DOTALL | re.IGNORECASE)
        if match:
            req_section = match.group(1).strip()
            break

    if req_section:
        # 按行分割
        lines = [l.strip() for l in req_section.split("\n") if l.strip()]
        for line in lines:
            # 去除序号前缀 (1. 2. 等)
            cleaned = re.sub(r'^\d+[\.\)]\s*', '', line)
            if cleaned:
                result["requirements"].append(cleaned)

    result["success"] = True
    result["reason"] = f"提取到 {len(result['requirements'])} 条技术要求"

    return result
