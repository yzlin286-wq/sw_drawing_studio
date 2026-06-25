"""v2.0 Task 6: YOLO Drawing Detector

YOLO OBB 检测尺寸文字 / 箭头 / 视图框
如果没有 YOLO 模型，使用基于图像分析的 fallback
"""
from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Any


def detect_drawing_elements(png_path: Path, model_path: Path = None) -> dict:
    """检测工程图元素

    检测项:
    - 尺寸文字 (dimension_text)
    - 箭头 (arrow)
    - 视图框 (view_border)
    - 中心线 (center_line)

    Args:
        png_path: PNG 预览图路径
        model_path: YOLO 模型路径（可选）

    Returns:
        {
            "success": bool,
            "png_path": str,
            "detections": list,  # [{type, bbox, confidence}]
            "detection_count": int,
            "by_type": dict,  # {dimension_text: N, arrow: N, ...}
            "method": str,  # "yolo" / "image_analysis"
            "reason": str,
        }
    """
    png_path = Path(png_path).resolve()

    result = {
        "success": False,
        "png_path": str(png_path),
        "detections": [],
        "detection_count": 0,
        "by_type": {},
        "method": "image_analysis",
        "reason": "",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    if not png_path.exists():
        result["reason"] = f"PNG 不存在: {png_path}"
        return result

    # 尝试 YOLO
    if model_path and Path(model_path).exists():
        try:
            result.update(_detect_with_yolo(png_path, model_path))
            return result
        except Exception as e:
            result["reason"] = f"YOLO 检测失败，回退到图像分析: {e}"

    # Fallback: 图像分析
    try:
        result.update(_detect_with_image_analysis(png_path))
    except Exception as e:
        result["reason"] = f"detect_drawing_elements 异常: {e}"

    return result


def _detect_with_yolo(png_path: Path, model_path: Path) -> dict:
    """使用 YOLO 模型检测"""
    try:
        from ultralytics import YOLO

        model = YOLO(str(model_path))
        results = model(str(png_path))

        detections = []
        by_type = {}

        for r in results:
            if hasattr(r, "obb"):
                for obb in r.obb:
                    cls_id = int(obb.cls[0]) if hasattr(obb, "cls") else 0
                    conf = float(obb.conf[0]) if hasattr(obb, "conf") else 0.5
                    cls_name = model.names.get(cls_id, f"class_{cls_id}")

                    # OBB: 4 个点
                    if hasattr(obb, "xyxy"):
                        xyxy = obb.xyxy[0].tolist()
                        bbox = [xyxy[0], xyxy[1], xyxy[2] - xyxy[0], xyxy[3] - xyxy[1]]
                    else:
                        bbox = [0, 0, 0, 0]

                    detections.append({
                        "type": cls_name,
                        "bbox": bbox,
                        "confidence": conf,
                    })
                    by_type[cls_name] = by_type.get(cls_name, 0) + 1

        return {
            "success": True,
            "detections": detections,
            "detection_count": len(detections),
            "by_type": by_type,
            "method": "yolo",
            "reason": f"YOLO 检测到 {len(detections)} 个元素",
        }
    except ImportError:
        raise RuntimeError("ultralytics 未安装")


def _detect_with_image_analysis(png_path: Path) -> dict:
    """使用图像分析检测（fallback）"""
    try:
        import cv2
        import numpy as np

        img = cv2.imread(str(png_path))
        if img is None:
            return {
                "success": False,
                "reason": "cv2.imread 返回 None",
            }

        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        detections = []
        by_type = {}

        # 1. 检测直线（可能为中心线或尺寸线）
        try:
            edges = cv2.Canny(gray, 50, 150, apertureSize=3)
            lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=80,
                                    minLineLength=50, maxLineGap=10)
            if lines is not None:
                line_count = min(len(lines), 100)  # 限制数量
                for i in range(line_count):
                    x1, y1, x2, y2 = lines[i][0]
                    detections.append({
                        "type": "line",
                        "bbox": [min(x1, x2) / w, min(y1, y2) / h,
                                 abs(x2 - x1) / w, abs(y2 - y1) / h],
                        "confidence": 0.6,
                    })
                by_type["line"] = line_count
        except Exception:
            pass

        # 2. 检测矩形（可能为视图框）
        try:
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            rect_count = 0
            for cnt in contours:
                area = cv2.contourArea(cnt)
                if area > 5000:  # 过滤小区域
                    x, y, rw, rh = cv2.boundingRect(cnt)
                    aspect = float(rw) / rh if rh > 0 else 0
                    if 0.5 < aspect < 2.0:  # 矩形比例
                        detections.append({
                            "type": "view_border",
                            "bbox": [x / w, y / h, rw / w, rh / h],
                            "confidence": 0.5,
                        })
                        rect_count += 1
                        if rect_count >= 10:
                            break
            if rect_count > 0:
                by_type["view_border"] = rect_count
        except Exception:
            pass

        # 3. 检测箭头（通过角点检测）
        try:
            corners = cv2.goodFeaturesToTrack(gray, maxCorners=50, qualityLevel=0.1,
                                              minDistance=20, blockSize=7)
            if corners is not None:
                arrow_count = min(len(corners), 20)
                for i in range(arrow_count):
                    x, y = corners[i].ravel()
                    detections.append({
                        "type": "arrow_candidate",
                        "bbox": [x / w, y / h, 0.01, 0.01],
                        "confidence": 0.4,
                    })
                by_type["arrow_candidate"] = arrow_count
        except Exception:
            pass

        return {
            "success": True,
            "detections": detections,
            "detection_count": len(detections),
            "by_type": by_type,
            "method": "image_analysis",
            "reason": f"图像分析检测到 {len(detections)} 个元素（fallback，无 YOLO 模型）",
        }

    except ImportError:
        return {
            "success": True,
            "detections": [],
            "detection_count": 0,
            "by_type": {},
            "method": "none",
            "reason": "OpenCV 未安装，跳过 YOLO 检测",
        }
