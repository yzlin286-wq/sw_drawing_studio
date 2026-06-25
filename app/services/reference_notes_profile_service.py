from __future__ import annotations

from typing import Any


def build_reference_notes_profile(reference_profile: dict[str, Any]) -> dict[str, Any]:
    raw_notes = _text_list(reference_profile.get("notes_raw_text"))
    normalized = [
        item for item in (reference_profile.get("normalized_notes") or [])
        if isinstance(item, dict)
    ]
    roughness = reference_profile.get("roughness_symbols") or []
    datum = reference_profile.get("datum_symbols") or []

    return {
        "schema": "sw_drawing_studio.reference_notes_profile.v4",
        "base": reference_profile.get("base") or "",
        "raw_text": raw_notes,
        "normalized_notes": normalized,
        "roughness": bool(roughness) or _contains_any(raw_notes, ["Ra", "粗糙度"]),
        "datum": bool(datum) or _contains_any(raw_notes, ["基准", "datum", "Datum"]),
        "red_warning": _contains_any(raw_notes, ["红", "警示", "加红", "另加工"]),
        "technical_requirement": _contains_any(raw_notes, ["技术要求", "去毛刺", "未注"]),
        "roughness_symbols": roughness,
        "datum_symbols": datum,
        "source": reference_profile.get("source_profile") or "",
        "warnings": [] if reference_profile else ["reference_profile_missing"],
    }


def _text_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _contains_any(values: list[str], needles: list[str]) -> bool:
    text = "\n".join(values)
    lower_text = text.lower()
    return any(needle in text or needle.lower() in lower_text for needle in needles)
