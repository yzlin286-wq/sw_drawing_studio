from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.services.drawing_blueprint_model import ViewPlan


DEFAULT_TITLEBAR_BOX = [0.68, 0.0, 1.0, 0.18]
DEFAULT_NOTES_BOX = [0.58, 0.18, 0.98, 0.35]


def compose_layout(
    *,
    view_plan: list[ViewPlan] | list[dict[str, Any]],
    sheet_size: dict[str, Any] | None = None,
    titlebar_box: list[float] | None = None,
    notes_box: list[float] | None = None,
) -> dict[str, Any]:
    titlebar_box = _box(titlebar_box or DEFAULT_TITLEBAR_BOX)
    notes_box = _box(notes_box or DEFAULT_NOTES_BOX)
    views = [_view_box(view) for view in view_plan]
    overlaps = _overlaps(views)
    titlebar_hits = [view["slot"] for view in views if _intersects(view["box_norm"], titlebar_box)]
    notes_hits = [view["slot"] for view in views if _intersects(view["box_norm"], notes_box)]
    out_of_frame = [view["slot"] for view in views if _out_of_frame(view["box_norm"])]
    utilization = round(sum(_area(view["box_norm"]) for view in views), 4)

    payload = {
        "schema": "sw_drawing_studio.layout_composition.v4",
        "sheet_size": sheet_size or {},
        "titlebar_box_norm": titlebar_box,
        "notes_box_norm": notes_box,
        "views": views,
        "view_overlap": bool(overlaps),
        "overlap_pairs": overlaps,
        "out_of_frame": bool(out_of_frame),
        "out_of_frame_slots": out_of_frame,
        "titlebar_collision": bool(titlebar_hits),
        "titlebar_collision_slots": titlebar_hits,
        "notes_collision": bool(notes_hits),
        "notes_collision_slots": notes_hits,
        "dimension_collision": None,
        "utilization": utilization,
        "readability_score": _readability_score(overlaps, titlebar_hits, notes_hits, out_of_frame, utilization),
    }
    return payload


def write_layout_composition(layout: dict[str, Any], path: Path | str) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(layout, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def _view_box(view: ViewPlan | dict[str, Any]) -> dict[str, Any]:
    data = view.__dict__ if isinstance(view, ViewPlan) else dict(view)
    center = _center(data.get("center_norm"))
    outline = _box(data.get("outline_norm"))
    if not outline:
        width = 0.18 if data.get("view_type") != "iso" else 0.14
        height = 0.16 if data.get("view_type") != "iso" else 0.14
        outline = [
            round(center[0] - width / 2, 4),
            round(center[1] - height / 2, 4),
            round(center[0] + width / 2, 4),
            round(center[1] + height / 2, 4),
        ]
    return {
        "slot": data.get("slot") or "",
        "view_type": data.get("view_type") or "",
        "center_norm": center,
        "box_norm": outline,
    }


def _center(value: Any) -> list[float]:
    values = _float_list(value)
    if len(values) >= 2:
        return values[:2]
    return [0.5, 0.5]


def _box(value: Any) -> list[float]:
    values = _float_list(value)
    if len(values) >= 4:
        x0, y0, x1, y1 = values[:4]
        return [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)]
    return []


def _float_list(value: Any) -> list[float]:
    if not isinstance(value, list):
        return []
    result: list[float] = []
    for item in value:
        try:
            result.append(round(float(item), 4))
        except Exception:
            pass
    return result


def _overlaps(views: list[dict[str, Any]]) -> list[list[str]]:
    pairs: list[list[str]] = []
    for index, left in enumerate(views):
        for right in views[index + 1:]:
            if _intersects(left["box_norm"], right["box_norm"]):
                pairs.append([left["slot"], right["slot"]])
    return pairs


def _intersects(left: list[float], right: list[float]) -> bool:
    if len(left) < 4 or len(right) < 4:
        return False
    return not (left[2] <= right[0] or right[2] <= left[0] or left[3] <= right[1] or right[3] <= left[1])


def _out_of_frame(box: list[float]) -> bool:
    return len(box) < 4 or box[0] < 0.0 or box[1] < 0.0 or box[2] > 1.0 or box[3] > 1.0


def _area(box: list[float]) -> float:
    if len(box) < 4:
        return 0.0
    return max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])


def _readability_score(
    overlaps: list[list[str]],
    titlebar_hits: list[str],
    notes_hits: list[str],
    out_of_frame: list[str],
    utilization: float,
) -> float:
    score = 1.0
    score -= min(0.45, len(overlaps) * 0.15)
    score -= min(0.25, len(titlebar_hits) * 0.10)
    score -= min(0.20, len(notes_hits) * 0.08)
    score -= min(0.25, len(out_of_frame) * 0.12)
    if utilization < 0.04:
        score -= 0.10
    if utilization > 0.55:
        score -= 0.15
    return round(max(0.0, score), 3)
