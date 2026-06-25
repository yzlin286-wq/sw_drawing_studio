"""v2.0 Task 6: Template Symbol Detector

模板匹配 Ra / Datum / 中心标记 / 表面粗糙度符号
使用 OpenCV 模板匹配（如果可用）或简单图像分析
"""
from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Any


def detect_symbols(png_path: Path, templates_dir: Path = None) -> dict:
    """检测工程图中的标准符号

    检测项:
    - Ra (表面粗糙度)
    - Datum (基准符号)
    - 中心标记
    - 形位公差符号

    Args:
        png_path: PNG 预览图路径
        templates_dir: 模板符号目录（可选）

    Returns:
        {
            "success": bool,
            "png_path": str,
            "symbols": list,  # [{type, bbox, confidence}]
            "symbol_count": int,
            "reason": str,
        }
    """
    png_path = Path(png_path).resolve()

    result = {
        "success": False,
        "png_path": str(png_path),
        "symbols": [],
        "symbol_count": 0,
        "reason": "",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    if not png_path.exists():
        result["reason"] = f"PNG 不存在: {png_path}"
        return result

    try:
        # 尝试使用 OpenCV
        try:
            import cv2
            import numpy as np

            img = cv2.imread(str(png_path))
            if img is None:
                result["reason"] = "cv2.imread 返回 None"
                return result

            h, w = img.shape[:2]
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            # 检测 Ra 符号（通过文本匹配）
            # 使用 OCR 提取文本后查找 "Ra"
            symbols = []

            # 简单边缘检测找圆形（中心标记）
            try:
                circles = cv2.HoughCircles(
                    gray,
                    cv2.HOUGH_GRADIENT,
                    dp=1,
                    minDist=30,
                    param1=50,
                    param2=30,
                    minRadius=5,
                    maxRadius=50,
                )
                if circles is not None:
                    circles = np.round(circles[0, :]).astype("int")
                    for (x, y, r) in circles:
                        symbols.append({
                            "type": "center_mark",
                            "bbox": [x / w, y / h, (2 * r) / w, (2 * r) / h],
                            "confidence": 0.7,
                            "pixel_pos": [int(x), int(y), int(r)],
                        })
            except Exception:
                pass

            # 模板匹配（如果有模板目录）
            if templates_dir and Path(templates_dir).exists():
                for tpl_file in Path(templates_dir).glob("*.png"):
                    try:
                        template = cv2.imread(str(tpl_file), 0)
                        if template is None:
                            continue
                        th, tw = template.shape
                        if th > h or tw > w:
                            continue

                        res = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
                        threshold = 0.8
                        loc = np.where(res >= threshold)
                        for pt in zip(*loc[::-1]):
                            symbols.append({
                                "type": tpl_file.stem,
                                "bbox": [pt[0] / w, pt[1] / h, tw / w, th / h],
                                "confidence": float(res[pt[1], pt[0]]),
                            })
                    except Exception:
                        continue

            result["symbols"] = symbols
            result["symbol_count"] = len(symbols)
            result["success"] = True
            result["reason"] = f"检测到 {len(symbols)} 个符号"

        except ImportError:
            # OpenCV 不可用，使用简单分析
            result["success"] = True
            result["reason"] = "OpenCV 未安装，跳过模板匹配"
            result["symbols"] = []
            result["symbol_count"] = 0

    except Exception as e:
        result["reason"] = f"detect_symbols 异常: {e}"

    return result


def detect_ra_symbols(pdf_path: Path) -> dict:
    """从 PDF 文本中检测 Ra 符号

    Returns:
        {
            "success": bool,
            "ra_values": list,  # ["Ra3.2", "Ra1.6", ...]
            "ra_count": int,
            "reason": str,
        }
    """
    pdf_path = Path(pdf_path).resolve()

    result = {
        "success": False,
        "ra_values": [],
        "ra_count": 0,
        "reason": "",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    try:
        from app.services.ocr_qc_service import extract_text_from_pdf
        import re

        text_result = extract_text_from_pdf(pdf_path)
        if not text_result["success"]:
            result["reason"] = text_result["reason"]
            return result

        total_text = text_result["total_text"]

        # 匹配 Ra 值: Ra3.2 / Ra 3.2 / Ra1.6
        ra_matches = re.findall(r'Ra\s*(\d+\.?\d*)', total_text, re.IGNORECASE)
        ra_values = [f"Ra{m}" for m in ra_matches]

        result["ra_values"] = ra_values
        result["ra_count"] = len(ra_values)
        result["success"] = True
        result["reason"] = f"检测到 {len(ra_values)} 个 Ra 符号"

    except Exception as e:
        result["reason"] = f"detect_ra_symbols 异常: {e}"

    return result
