from __future__ import annotations

from pathlib import Path
from typing import Any


REQUIRED_TITLEBAR_FIELDS = ["drawing_no", "name", "material", "scale", "date"]


def build_reference_titlebar_profile(
    *,
    base: str,
    reference_profile: dict[str, Any] | None = None,
    part_path: str | Path | None = None,
) -> dict[str, Any]:
    reference_profile = reference_profile or {}
    fields = dict(reference_profile.get("titlebar_fields") or {})
    fields.setdefault("drawing_no", base)
    if part_path and not fields.get("name"):
        fields["name"] = Path(part_path).stem

    missing = [field for field in REQUIRED_TITLEBAR_FIELDS if not fields.get(field)]
    return {
        "schema": "sw_drawing_studio.reference_titlebar_profile.v4",
        "base": base,
        "fields": fields,
        "required_fields": REQUIRED_TITLEBAR_FIELDS,
        "missing_fields": missing,
        "source_priority": [
            "reference_titlebar",
            "custom_property",
            "filename",
            "default",
        ],
        "source": reference_profile.get("source_profile") or "filename",
        "warnings": [f"titlebar_missing:{field}" for field in missing],
    }
