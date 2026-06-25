from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.drawing_object_detector import region_stats
from app.services.drawing_layout_composer import DEFAULT_TITLEBAR_BOX


def detect_titlebar(
    png_path: Path | str,
    *,
    blueprint: dict[str, Any] | None = None,
) -> dict[str, Any]:
    layout = (blueprint or {}).get("layout_plan") or {}
    box = _sheet_box_to_image_box(layout.get("titlebar_box_norm") or DEFAULT_TITLEBAR_BOX)
    try:
        stats = region_stats(png_path, box)
    except Exception as exc:
        return {
            "success": False,
            "reason": str(exc),
            "box_norm": _issue_box(box),
            "detected": False,
            "ink_density": 0.0,
            "line_candidate_count": 0,
        }
    detected = stats["ink_density"] >= 0.0008 or stats["line_candidate_count"] >= 2
    return {
        "success": True,
        "box_norm": stats["box_norm"],
        "detected": bool(detected),
        "ink_density": stats["ink_density"],
        "line_candidate_count": stats["line_candidate_count"],
        "component_count": stats["component_count"],
        "source": "titlebar_region_ink_density",
    }


def _issue_box(box: list[float]) -> list[float]:
    if len(box) >= 4 and box[2] > box[0] and box[3] > box[1]:
        return [box[0], box[1], box[2] - box[0], box[3] - box[1]]
    if len(box) >= 4:
        return box[:4]
    return [0.68, 0.0, 0.32, 0.18]


def _sheet_box_to_image_box(box: list[float]) -> list[float]:
    if len(box) >= 4 and box[2] > box[0] and box[3] > box[1]:
        x0, y0, x1, y1 = [float(value) for value in box[:4]]
        return [x0, 1.0 - y1, x1, 1.0 - y0]
    return box
