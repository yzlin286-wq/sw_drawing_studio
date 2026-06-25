from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


@dataclass
class ImageMetrics:
    path: str
    width: int
    height: int
    mask: np.ndarray
    components: list[dict[str, Any]]
    ink_ratio: float
    ink_bbox: list[float]


def load_image_metrics(png_path: Path | str) -> ImageMetrics:
    path = Path(png_path)
    image = Image.open(path).convert("RGBA")
    rgba = np.asarray(image)
    alpha = rgba[:, :, 3].astype(np.float32) / 255.0
    rgb = rgba[:, :, :3].astype(np.float32)
    # Composite transparent pixels over white so exported drawings and UI crops
    # are measured consistently.
    rgb = rgb * alpha[:, :, None] + 255.0 * (1.0 - alpha[:, :, None])
    gray = (0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]).astype(np.uint8)
    mask = gray < 238
    components = _connected_components(mask)
    return ImageMetrics(
        path=str(path),
        width=int(image.width),
        height=int(image.height),
        mask=mask,
        components=components,
        ink_ratio=_ratio(mask),
        ink_bbox=_mask_bbox(mask),
    )


def detect_drawing_objects(png_path: Path | str) -> dict[str, Any]:
    try:
        metrics = load_image_metrics(png_path)
    except Exception as exc:
        return {
            "success": False,
            "reason": str(exc),
            "source_png": str(png_path),
            "ink_present": False,
            "ink_ratio": 0.0,
            "ink_bbox": [0.0, 0.0, 1.0, 1.0],
            "components": [],
            "view_frame_count": 0,
            "dimension_text_candidate_count": 0,
            "dimension_arrow_candidate_count": 0,
            "centerline_candidate_count": 0,
            "center_mark_candidate_count": 0,
            "section_arrow_candidate_count": 0,
        }

    components = metrics.components
    view_frames = [item for item in components if _is_view_frame_candidate(item)]
    text_candidates = [item for item in components if _is_dimension_text_candidate(item)]
    arrow_candidates = [item for item in components if _is_dimension_arrow_candidate(item)]
    centerline_candidates = [item for item in components if _is_centerline_candidate(item)]
    center_marks = [item for item in components if _is_center_mark_candidate(item)]
    section_arrows = [item for item in components if _is_section_arrow_candidate(item)]

    return {
        "success": True,
        "source_png": metrics.path,
        "width": metrics.width,
        "height": metrics.height,
        "ink_present": bool(metrics.ink_ratio > 0.0001),
        "ink_ratio": round(metrics.ink_ratio, 6),
        "ink_bbox": metrics.ink_bbox,
        "component_count": len(components),
        "components": components[:200],
        "view_frame_count": len(view_frames),
        "view_frames": view_frames[:40],
        "dimension_text_candidate_count": len(text_candidates),
        "dimension_text_candidates": text_candidates[:80],
        "dimension_arrow_candidate_count": len(arrow_candidates),
        "dimension_arrow_candidates": arrow_candidates[:80],
        "centerline_candidate_count": len(centerline_candidates),
        "centerline_candidates": centerline_candidates[:40],
        "center_mark_candidate_count": len(center_marks),
        "center_mark_candidates": center_marks[:40],
        "section_arrow_candidate_count": len(section_arrows),
        "section_arrow_candidates": section_arrows[:40],
    }


def region_stats(png_path: Path | str, box_norm: list[float]) -> dict[str, Any]:
    metrics = load_image_metrics(png_path)
    x0, y0, x1, y1 = _box_xyxy(box_norm)
    left = max(0, min(metrics.width, int(round(x0 * metrics.width))))
    top = max(0, min(metrics.height, int(round(y0 * metrics.height))))
    right = max(left + 1, min(metrics.width, int(round(x1 * metrics.width))))
    bottom = max(top + 1, min(metrics.height, int(round(y1 * metrics.height))))
    region = metrics.mask[top:bottom, left:right]
    components = [
        item for item in metrics.components
        if _center_inside(item.get("bbox", []), [x0, y0, x1 - x0, y1 - y0])
    ]
    return {
        "box_norm": [round(x0, 4), round(y0, 4), round(x1 - x0, 4), round(y1 - y0, 4)],
        "ink_pixels": int(region.sum()),
        "pixel_count": int(region.size),
        "ink_density": round(_ratio(region), 6),
        "component_count": len(components),
        "line_candidate_count": len([item for item in components if _is_line_candidate(item)]),
        "components": components[:80],
    }


def _connected_components(mask: np.ndarray) -> list[dict[str, Any]]:
    try:
        import cv2  # type: ignore

        labels, _, stats, _ = cv2.connectedComponentsWithStats(mask.astype("uint8"), connectivity=8)
        height, width = mask.shape
        result: list[dict[str, Any]] = []
        for index in range(1, int(labels)):
            x, y, w, h, area = [int(value) for value in stats[index]]
            if area < 4:
                continue
            result.append(_component(width, height, x, y, w, h, area))
        result.sort(key=lambda item: item["area"], reverse=True)
        return result
    except Exception:
        bbox = _mask_bbox(mask)
        if bbox == [0.0, 0.0, 0.0, 0.0]:
            return []
        h, w = mask.shape
        x, y, bw, bh = bbox
        return [_component(w, h, int(x * w), int(y * h), int(bw * w), int(bh * h), int(mask.sum()))]


def _component(width: int, height: int, x: int, y: int, w: int, h: int, area: int) -> dict[str, Any]:
    bbox = [
        round(x / max(1, width), 6),
        round(y / max(1, height), 6),
        round(w / max(1, width), 6),
        round(h / max(1, height), 6),
    ]
    aspect = float(w) / float(h or 1)
    return {
        "bbox": bbox,
        "area": int(area),
        "area_norm": round(area / float(max(1, width * height)), 8),
        "aspect": round(aspect, 3),
    }


def _ratio(mask: np.ndarray) -> float:
    if mask.size <= 0:
        return 0.0
    return float(mask.sum()) / float(mask.size)


def _mask_bbox(mask: np.ndarray) -> list[float]:
    ys, xs = np.where(mask)
    if len(xs) == 0 or len(ys) == 0:
        return [0.0, 0.0, 0.0, 0.0]
    height, width = mask.shape
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    return [
        round(x0 / max(1, width), 6),
        round(y0 / max(1, height), 6),
        round((x1 - x0) / max(1, width), 6),
        round((y1 - y0) / max(1, height), 6),
    ]


def _box_xyxy(box_norm: list[float]) -> tuple[float, float, float, float]:
    if len(box_norm) >= 4:
        x0, y0, x2, y2 = [float(value) for value in box_norm[:4]]
        if x2 > x0 and y2 > y0:
            return _clamp(x0), _clamp(y0), _clamp(x2), _clamp(y2)
        return _clamp(x0), _clamp(y0), _clamp(x0 + max(0.0, x2)), _clamp(y0 + max(0.0, y2))
    return 0.0, 0.0, 1.0, 1.0


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _center_inside(component_bbox: list[float], region_bbox: list[float]) -> bool:
    if len(component_bbox) < 4 or len(region_bbox) < 4:
        return False
    cx = component_bbox[0] + component_bbox[2] / 2.0
    cy = component_bbox[1] + component_bbox[3] / 2.0
    return (
        region_bbox[0] <= cx <= region_bbox[0] + region_bbox[2]
        and region_bbox[1] <= cy <= region_bbox[1] + region_bbox[3]
    )


def _is_line_candidate(item: dict[str, Any]) -> bool:
    aspect = float(item.get("aspect") or 0)
    width = float((item.get("bbox") or [0, 0, 0, 0])[2])
    height = float((item.get("bbox") or [0, 0, 0, 0])[3])
    return (aspect >= 6.0 and width >= 0.025) or (aspect <= 0.18 and height >= 0.025)


def _is_view_frame_candidate(item: dict[str, Any]) -> bool:
    bbox = item.get("bbox") or [0, 0, 0, 0]
    width, height = float(bbox[2]), float(bbox[3])
    return width >= 0.055 and height >= 0.035 and float(item.get("area") or 0) >= 25


def _is_dimension_text_candidate(item: dict[str, Any]) -> bool:
    bbox = item.get("bbox") or [0, 0, 0, 0]
    width, height = float(bbox[2]), float(bbox[3])
    aspect = float(item.get("aspect") or 0)
    return 0.002 <= width <= 0.08 and 0.002 <= height <= 0.045 and 0.2 <= aspect <= 8.0


def _is_dimension_arrow_candidate(item: dict[str, Any]) -> bool:
    bbox = item.get("bbox") or [0, 0, 0, 0]
    width, height = float(bbox[2]), float(bbox[3])
    aspect = float(item.get("aspect") or 0)
    return max(width, height) <= 0.08 and min(width, height) <= 0.018 and (aspect >= 3.0 or aspect <= 0.34)


def _is_centerline_candidate(item: dict[str, Any]) -> bool:
    return _is_line_candidate(item) and float(item.get("area_norm") or 0.0) <= 0.02


def _is_center_mark_candidate(item: dict[str, Any]) -> bool:
    bbox = item.get("bbox") or [0, 0, 0, 0]
    width, height = float(bbox[2]), float(bbox[3])
    return 0.006 <= width <= 0.08 and 0.006 <= height <= 0.08 and abs(width - height) <= 0.03


def _is_section_arrow_candidate(item: dict[str, Any]) -> bool:
    bbox = item.get("bbox") or [0, 0, 0, 0]
    width, height = float(bbox[2]), float(bbox[3])
    aspect = float(item.get("aspect") or 0)
    return max(width, height) <= 0.06 and min(width, height) <= 0.03 and 0.45 <= aspect <= 2.4
