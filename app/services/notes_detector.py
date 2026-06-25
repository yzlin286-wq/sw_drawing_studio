from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.drawing_object_detector import region_stats
from app.services.drawing_layout_composer import DEFAULT_NOTES_BOX


def detect_notes(
    png_path: Path | str,
    *,
    blueprint: dict[str, Any] | None = None,
) -> dict[str, Any]:
    blueprint = blueprint or {}
    layout = blueprint.get("layout_plan") or {}
    notes_plan = blueprint.get("notes_plan") or {}
    box = _sheet_box_to_image_box(layout.get("notes_box_norm") or notes_plan.get("note_box_norm") or DEFAULT_NOTES_BOX)
    required_notes = list(notes_plan.get("required_notes") or [])
    raw_reference_notes = list(notes_plan.get("raw_reference_notes") or [])
    warning_notes = list(notes_plan.get("warning_notes") or [])
    requires_technical = bool(required_notes or raw_reference_notes or warning_notes)
    try:
        stats = region_stats(png_path, box)
    except Exception as exc:
        return {
            "success": False,
            "reason": str(exc),
            "box_norm": _issue_box(box),
            "detected": False,
            "technical_requirements_detected": False,
            "required_notes": required_notes,
            "ink_density": 0.0,
        }
    detected = stats["ink_density"] >= 0.0006 or stats["component_count"] >= 2
    return {
        "success": True,
        "box_norm": stats["box_norm"],
        "detected": bool(detected),
        "technical_requirements_detected": bool(detected and requires_technical),
        "requires_technical_requirements": requires_technical,
        "required_notes": required_notes,
        "raw_reference_note_count": len(raw_reference_notes),
        "warning_note_count": len(warning_notes),
        "ink_density": stats["ink_density"],
        "component_count": stats["component_count"],
        "source": "notes_region_ink_density",
    }


def _issue_box(box: list[float]) -> list[float]:
    if len(box) >= 4 and box[2] > box[0] and box[3] > box[1]:
        return [box[0], box[1], box[2] - box[0], box[3] - box[1]]
    if len(box) >= 4:
        return box[:4]
    return [0.58, 0.18, 0.40, 0.17]


def _sheet_box_to_image_box(box: list[float]) -> list[float]:
    if len(box) >= 4 and box[2] > box[0] and box[3] > box[1]:
        x0, y0, x1, y1 = [float(value) for value in box[:4]]
        return [x0, 1.0 - y1, x1, 1.0 - y0]
    return box
