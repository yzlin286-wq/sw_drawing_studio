"""v2.0 Task 6: PDF Render Service

PDF 统一 300 DPI 渲染为 PNG，供后续 OCR / 模板匹配 / YOLO / LLM 使用
"""
from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Any


def render_pdf_to_png(
    pdf_path: Path,
    output_dir: Path,
    dpi: int = 300,
    run_id: str = "",
) -> dict:
    """将 PDF 渲染为 PNG

    Args:
        pdf_path: PDF 文件路径
        output_dir: 输出目录
        dpi: 渲染 DPI（默认 300）
        run_id: run_id

    Returns:
        {
            "success": bool,
            "pdf_path": str,
            "output_dir": str,
            "dpi": int,
            "pages": list,  # [{page: int, png_path: str, width: int, height: int}]
            "page_count": int,
            "reason": str,
        }
    """
    pdf_path = Path(pdf_path).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    result = {
        "success": False,
        "pdf_path": str(pdf_path),
        "output_dir": str(output_dir),
        "dpi": dpi,
        "pages": [],
        "page_count": 0,
        "reason": "",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    if not pdf_path.exists():
        result["reason"] = f"PDF 不存在: {pdf_path}"
        return result

    try:
        import fitz  # PyMuPDF

        doc = fitz.open(str(pdf_path))
        result["page_count"] = len(doc)

        # 计算缩放矩阵（300 DPI）
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)

        for page_num in range(len(doc)):
            page = doc[page_num]
            pix = page.get_pixmap(matrix=mat)

            png_name = f"page_{page_num + 1:03d}_{run_id}.png" if run_id else f"page_{page_num + 1:03d}.png"
            png_path = output_dir / png_name
            pix.save(str(png_path))

            result["pages"].append({
                "page": page_num + 1,
                "png_path": str(png_path),
                "width": pix.width,
                "height": pix.height,
            })

        doc.close()
        result["success"] = True
        result["reason"] = f"成功渲染 {result['page_count']} 页"

    except ImportError:
        result["reason"] = "PyMuPDF (fitz) 未安装"
    except Exception as e:
        result["reason"] = f"render_pdf_to_png 异常: {e}"

    return result


def render_pdf_first_page(
    pdf_path: Path,
    output_png: Path,
    dpi: int = 300,
) -> dict:
    """渲染 PDF 第一页为 PNG"""
    pdf_path = Path(pdf_path).resolve()
    output_png = Path(output_png).resolve()
    output_png.parent.mkdir(parents=True, exist_ok=True)

    result = {
        "success": False,
        "pdf_path": str(pdf_path),
        "png_path": str(output_png),
        "dpi": dpi,
        "reason": "",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    try:
        import fitz

        doc = fitz.open(str(pdf_path))
        if len(doc) == 0:
            result["reason"] = "PDF 无页面"
            return result

        page = doc[0]
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        pix.save(str(output_png))

        result["width"] = pix.width
        result["height"] = pix.height
        result["success"] = True
        result["reason"] = "成功渲染第一页"

        doc.close()
    except Exception as e:
        result["reason"] = f"render_pdf_first_page 异常: {e}"

    return result
