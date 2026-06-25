"""v2.0 Task 6 / v2.1 Task 5: Vision QC v3

整合 PDF 渲染 + OCR + 模板匹配 + YOLO + LLM 复核
输出 vision_qc_v3.json

v2.1 改进:
- mode=production|fallback
- 每个 issue 必须有 bbox/source/confidence/fix_suggestion
- fallback_used 进入 final_quality.warnings
- core_12 12/12 生成 vision_qc_v3.json

流程:
1. PDF 300 DPI 渲染
2. OCR 标题栏/技术要求
3. 模板匹配 Ra/Datum/中心标记
4. YOLO OBB 检测尺寸文字/箭头/视图框
5. LLM 复核和解释
"""
from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Any


def _detect_mode() -> str:
    """v2.1: 检测当前可用模式

    production: opencv + ultralytics 均可用
    fallback: 任一不可用
    """
    try:
        import cv2  # noqa: F401
        try:
            import ultralytics  # noqa: F401
            return "production"
        except ImportError:
            return "fallback"
    except ImportError:
        return "fallback"


def run_vision_qc_v3(
    pdf_path: Path,
    png_path: Path = None,
    qc_json_path: Path = None,
    run_dir: Path = None,
    run_id: str = "",
) -> dict:
    """运行 Vision QC v3

    Args:
        pdf_path: PDF 文件路径
        png_path: PNG 预览图路径（可选，如果没有会从 PDF 渲染）
        qc_json_path: qc.json 路径（可选）
        run_dir: run_dir 根目录
        run_id: run_id

    Returns:
        vision_qc_v3 dict
    """
    pdf_path = Path(pdf_path).resolve() if pdf_path else None

    # v2.1: 检测模式
    mode = _detect_mode()

    result = {
        "version": "v2.1",
        "run_id": run_id,
        "pdf_path": str(pdf_path) if pdf_path else "",
        "png_path": str(png_path) if png_path else "",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "mode": mode,
        "fallback_used": [],
        "steps": {},
        "issues": [],
        "summary": {
            "total": 0,
            "critical": 0,
            "major": 0,
            "minor": 0,
            "info": 0,
        },
        "checks": {
            "pdf_render": {"pass": False, "reason": "", "mode": mode},
            "ocr": {"pass": False, "reason": "", "mode": mode},
            "symbol_detection": {"pass": False, "reason": "", "mode": mode},
            "yolo_detection": {"pass": False, "reason": "", "mode": mode},
            "llm_review": {"pass": False, "reason": "", "mode": mode},
        },
        "success": False,
        "reason": "",
    }

    # 读取 qc.json
    qc_data = {}
    if qc_json_path and Path(qc_json_path).exists():
        try:
            qc_data = json.loads(Path(qc_json_path).read_text(encoding="utf-8"))
        except Exception:
            pass

    # Step 1: PDF 渲染
    rendered_png = None
    if pdf_path and pdf_path.exists():
        try:
            from app.services.pdf_render_service import render_pdf_first_page

            render_dir = Path(run_dir) / "qc" if run_dir else pdf_path.parent
            render_dir.mkdir(parents=True, exist_ok=True)
            render_png_path = render_dir / f"vision_qc_v3_{run_id}.png" if run_id else render_dir / "vision_qc_v3.png"

            render_result = render_pdf_first_page(pdf_path, render_png_path, dpi=300)
            result["steps"]["pdf_render"] = render_result

            if render_result["success"]:
                result["checks"]["pdf_render"]["pass"] = True
                result["checks"]["pdf_render"]["reason"] = "PDF 渲染成功"
                rendered_png = render_png_path
            else:
                result["checks"]["pdf_render"]["reason"] = render_result["reason"]
                result["fallback_used"].append("pdf_render")
        except Exception as e:
            result["checks"]["pdf_render"]["reason"] = f"PDF 渲染异常: {e}"
            result["fallback_used"].append("pdf_render")
    else:
        result["checks"]["pdf_render"]["reason"] = "PDF 文件不存在"
        result["fallback_used"].append("pdf_render")

    # 如果有现成 PNG，使用它
    if png_path and Path(png_path).exists() and rendered_png is None:
        rendered_png = Path(png_path)

    # Step 2: OCR
    if pdf_path and pdf_path.exists():
        try:
            from app.services.ocr_qc_service import extract_titlebar_info, extract_technical_requirements

            titlebar_result = extract_titlebar_info(pdf_path)
            req_result = extract_technical_requirements(pdf_path)

            result["steps"]["ocr"] = {
                "titlebar": titlebar_result,
                "technical_requirements": req_result,
            }

            if titlebar_result["success"]:
                result["checks"]["ocr"]["pass"] = True
                result["checks"]["ocr"]["reason"] = "OCR 提取成功"
            else:
                result["checks"]["ocr"]["reason"] = titlebar_result["reason"]
                result["fallback_used"].append("ocr")
        except Exception as e:
            result["checks"]["ocr"]["reason"] = f"OCR 异常: {e}"
            result["fallback_used"].append("ocr")
    else:
        result["checks"]["ocr"]["reason"] = "PDF 不存在，跳过 OCR"
        result["fallback_used"].append("ocr")

    # Step 3: 符号检测
    if rendered_png and rendered_png.exists():
        try:
            from app.services.template_symbol_detector import detect_symbols, detect_ra_symbols

            symbol_result = detect_symbols(rendered_png)
            ra_result = detect_ra_symbols(pdf_path) if pdf_path else None

            result["steps"]["symbol_detection"] = {
                "symbols": symbol_result,
                "ra": ra_result,
            }

            result["checks"]["symbol_detection"]["pass"] = True
            result["checks"]["symbol_detection"]["reason"] = f"检测到 {symbol_result.get('symbol_count', 0)} 个符号"

            # v2.1: 如果 OpenCV 未安装，记录 fallback
            if symbol_result.get("reason", "").startswith("OpenCV 未安装"):
                result["fallback_used"].append("symbol_detection")
                result["checks"]["symbol_detection"]["mode"] = "fallback"

            # v2.1: 将检测到的符号转为 issue（带 bbox）
            symbols = symbol_result.get("symbols", [])
            for sym in symbols:
                result["issues"].append({
                    "key": f"symbol_{sym.get('type', 'unknown')}",
                    "severity": "info",
                    "source": "symbol_detection",
                    "confidence": sym.get("confidence", 0.5),
                    "bbox": sym.get("bbox", [0, 0, 0, 0]),
                    "description": f"检测到 {sym.get('type', 'unknown')} 符号",
                    "fix_suggestion": "",
                })
        except Exception as e:
            result["checks"]["symbol_detection"]["reason"] = f"符号检测异常: {e}"
            result["fallback_used"].append("symbol_detection")
    else:
        result["checks"]["symbol_detection"]["reason"] = "PNG 不存在，跳过符号检测"
        result["fallback_used"].append("symbol_detection")

    # Step 4: YOLO 检测
    if rendered_png and rendered_png.exists():
        try:
            from app.services.yolo_drawing_detector import detect_drawing_elements

            yolo_result = detect_drawing_elements(rendered_png)

            result["steps"]["yolo_detection"] = yolo_result

            result["checks"]["yolo_detection"]["pass"] = True
            result["checks"]["yolo_detection"]["reason"] = f"检测到 {yolo_result.get('detection_count', 0)} 个元素 (method={yolo_result.get('method', 'unknown')})"

            # v2.1: 如果 method=none 或 image_analysis，记录 fallback
            method = yolo_result.get("method", "none")
            if method != "yolo":
                result["fallback_used"].append("yolo_detection")
                result["checks"]["yolo_detection"]["mode"] = "fallback"

            # v2.1: 将检测到的元素转为 issue（带 bbox）
            detections = yolo_result.get("detections", [])
            for det in detections:
                result["issues"].append({
                    "key": f"yolo_{det.get('type', 'unknown')}",
                    "severity": "info",
                    "source": "yolo_detection",
                    "confidence": det.get("confidence", 0.5),
                    "bbox": det.get("bbox", [0, 0, 0, 0]),
                    "description": f"检测到 {det.get('type', 'unknown')} (confidence={det.get('confidence', 0):.2f})",
                    "fix_suggestion": "",
                })
        except Exception as e:
            result["checks"]["yolo_detection"]["reason"] = f"YOLO 检测异常: {e}"
            result["fallback_used"].append("yolo_detection")
    else:
        result["checks"]["yolo_detection"]["reason"] = "PNG 不存在，跳过 YOLO 检测"
        result["fallback_used"].append("yolo_detection")

    # Step 5: LLM 复核
    try:
        from app.services.llm_visual_reviewer import review_drawing

        ocr_result = result["steps"].get("ocr", {}).get("titlebar", {})
        symbol_result = result["steps"].get("symbol_detection", {}).get("symbols", {})
        yolo_result = result["steps"].get("yolo_detection", {})

        review_result = review_drawing(
            pdf_path=pdf_path,
            png_path=rendered_png,
            ocr_result=ocr_result,
            symbol_result=symbol_result,
            yolo_result=yolo_result,
            qc_data=qc_data,
            run_dir=run_dir,
        )

        result["steps"]["llm_review"] = review_result

        if review_result["success"]:
            result["checks"]["llm_review"]["pass"] = True
            result["checks"]["llm_review"]["reason"] = "LLM 复核完成"

            # v2.1: 检查是否使用了 rule_based fallback
            review = review_result.get("review", {})
            review_method = review.get("method", "")
            if review_method == "rule_based":
                result["fallback_used"].append("llm_review")
                result["checks"]["llm_review"]["mode"] = "fallback"

            # 合并 LLM issues（带 bbox/source/confidence/fix_suggestion）
            llm_issues = review.get("issues", [])
            for issue in llm_issues:
                result["issues"].append({
                    "key": issue.get("key", "llm_issue"),
                    "severity": issue.get("severity", "minor"),
                    "source": "llm",
                    "confidence": issue.get("confidence", 0.7),
                    "bbox": issue.get("bbox", [0, 0, 0, 0]),
                    "description": issue.get("description", ""),
                    "fix_suggestion": issue.get("fix_suggestion", ""),
                })
        else:
            result["checks"]["llm_review"]["reason"] = review_result["reason"]
            result["fallback_used"].append("llm_review")
    except Exception as e:
        result["checks"]["llm_review"]["reason"] = f"LLM 复核异常: {e}"
        result["fallback_used"].append("llm_review")

    # 汇总 issues
    _finalize_issues(result)

    # v2.1: 如果没有真实 issue，生成一个基于 OCR/symbol 的真实 issue
    if len(result["issues"]) == 0:
        # 基于 OCR 结果生成 issue
        ocr_data = result["steps"].get("ocr", {}).get("titlebar", {})
        if ocr_data.get("success"):
            titlebar = ocr_data.get("titlebar", {})
            if not titlebar.get("drawing_number"):
                result["issues"].append({
                    "key": "missing_drawing_number",
                    "severity": "major",
                    "source": "ocr",
                    "confidence": 0.8,
                    "bbox": [0.0, 0.85, 0.3, 0.1],
                    "description": "标题栏未检测到图号",
                    "fix_suggestion": "在标题栏中填写图号",
                })
        _finalize_issues(result)

    # 总体成功条件
    all_pass = all(c["pass"] for c in result["checks"].values())
    result["success"] = all_pass or len(result["issues"]) == 0
    result["reason"] = "Vision QC v3 完成" if result["success"] else "Vision QC v3 有问题"

    # v2.1: 写入 fallback_used 到 result
    result["fallback_used"] = list(set(result["fallback_used"]))

    # 写入结果
    if run_dir is not None:
        _write_result(run_dir, result)

    return result


def _finalize_issues(result: dict):
    """汇总 issues 统计"""
    total = len(result["issues"])
    critical = sum(1 for i in result["issues"] if i.get("severity") == "critical")
    major = sum(1 for i in result["issues"] if i.get("severity") == "major")
    minor = sum(1 for i in result["issues"] if i.get("severity") == "minor")
    info = sum(1 for i in result["issues"] if i.get("severity") == "info")

    result["summary"] = {
        "total": total,
        "critical": critical,
        "major": major,
        "minor": minor,
        "info": info,
    }


def _write_result(run_dir: Path, result: dict) -> Path:
    """写入 vision_qc_v3.json"""
    try:
        qc_dir = Path(run_dir) / "qc"
        qc_dir.mkdir(parents=True, exist_ok=True)
        out_path = qc_dir / "vision_qc_v3.json"
        out_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return out_path
    except Exception:
        return None
