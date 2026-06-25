from __future__ import annotations

from typing import Any


def build_reference_dimension_profile(reference_profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "sw_drawing_studio.reference_dimension_profile.v4",
        "base": reference_profile.get("base") or "",
        "display_dim_count": _int(reference_profile.get("display_dim_count")),
        "required_display_dim_count": _int(reference_profile.get("display_dim_count")),
        "dimension_bboxes": reference_profile.get("dimension_bboxes") or [],
        "hole_dims": reference_profile.get("hole_annotations") or [],
        "slot_dims": reference_profile.get("slot_annotations") or [],
        "radius_dims": reference_profile.get("radius_annotations") or [],
        "thread_dims": reference_profile.get("thread_annotations") or [],
        "datum_dims": reference_profile.get("datum_symbols") or [],
        "center_marks": reference_profile.get("center_marks") or [],
        "source": reference_profile.get("source_profile") or "",
        "warnings": [] if reference_profile else ["reference_profile_missing"],
    }


def _int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except Exception:
        return 0
