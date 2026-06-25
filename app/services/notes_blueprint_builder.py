from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.services.drawing_blueprint_model import NotesPlan


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO_ROOT / "config" / "drawing_note_blueprints.yaml"


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml

        if path.exists():
            return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        pass
    return {}


def _text_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _normalized_notes(reference_notes_profile: dict[str, Any]) -> list[dict[str, Any]]:
    raw = reference_notes_profile.get("normalized_notes")
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    notes = []
    for text in _text_list(reference_notes_profile.get("raw_text") or reference_notes_profile.get("raw_notes")):
        notes.append({"type": "reference_raw", "text": text, "source": "reference_notes"})
    return notes


def build_notes_plan(
    *,
    part_class: str,
    reference_notes_profile: dict[str, Any] | None = None,
    config_path: Path | str = DEFAULT_CONFIG,
) -> NotesPlan:
    reference_notes_profile = reference_notes_profile or {}
    config = _load_yaml(Path(config_path))
    template = config.get(part_class) or config.get("default") or {}

    raw_reference_notes = _text_list(
        reference_notes_profile.get("raw_text")
        or reference_notes_profile.get("raw_notes")
        or reference_notes_profile.get("notes")
    )
    normalized = _normalized_notes(reference_notes_profile)

    required = _text_list(template.get("required_notes"))
    optional = _text_list(template.get("optional_notes"))
    warning_notes: list[str] = []

    reference_required = [
        str(item.get("text", "")).strip()
        for item in normalized
        if isinstance(item, dict) and str(item.get("text", "")).strip()
    ]
    if reference_required:
        required = _merge_unique(reference_required + required)

    for key, label in [
        ("roughness", "reference roughness note must be preserved"),
        ("datum", "reference datum note must be preserved"),
        ("red_warning", "reference red warning note must be preserved"),
        ("technical_requirement", "reference technical requirement must be preserved"),
    ]:
        if reference_notes_profile.get(key) is True:
            warning_notes.append(label)

    source = "reference_notes_plus_part_class" if raw_reference_notes or normalized else "part_class_default"
    reasons = [
        f"part_class={part_class}",
        f"required_notes={len(required)}",
        f"optional_notes={len(optional)}",
    ]
    if not raw_reference_notes and not normalized:
        reasons.append("no_reference_notes_profile_available")

    return NotesPlan(
        part_class=part_class,
        required_notes=required,
        optional_notes=optional,
        raw_reference_notes=raw_reference_notes,
        normalized_notes=normalized,
        warning_notes=warning_notes,
        note_box_norm=_box(reference_notes_profile.get("note_box_norm") or reference_notes_profile.get("bbox")),
        source=source,
        reasons=reasons,
    )


def write_notes_plan(plan: NotesPlan, path: Path | str) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan.__dict__, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def _merge_unique(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = value.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(key)
    return result


def _box(value: Any) -> list[float]:
    if not isinstance(value, list) or len(value) < 4:
        return []
    try:
        return [round(float(item), 4) for item in value[:4]]
    except Exception:
        return []
