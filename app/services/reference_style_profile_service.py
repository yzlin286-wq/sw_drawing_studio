from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROFILE_CANDIDATES = [
    REPO_ROOT / "drw_output" / "reference_style_profile" / "lb26001_36_reference_style_profile.json",
    REPO_ROOT / "drw_output" / "reference_style_profile" / "lb26001_reference_style_profile.json",
]
DEFAULT_OUT = REPO_ROOT / "drw_output" / "reference_style_profile" / "reference_profiles_v4.json"


def build_reference_profiles_v4(
    *,
    source_profile: Path | str | None = None,
    out_path: Path | str | None = DEFAULT_OUT,
) -> dict[str, Any]:
    profile_path = Path(source_profile) if source_profile else _first_existing(DEFAULT_PROFILE_CANDIDATES)
    source = _read_json(profile_path)
    samples = source.get("reference_samples") or {}

    profiles: dict[str, Any] = {}
    for base, sample in samples.items():
        if isinstance(sample, dict):
            profiles[str(base)] = normalize_reference_sample(str(base), sample, profile_path)

    payload = {
        "schema": "sw_drawing_studio.reference_profiles.v4",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source_profile": str(profile_path) if profile_path else "",
        "sample_count": len(profiles),
        "profiles": profiles,
        "warnings": [] if profiles else ["no_reference_samples_found"],
    }

    if out_path:
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        payload["output_path"] = str(out)
    return payload


def load_reference_profiles_v4(path: Path | str = DEFAULT_OUT) -> dict[str, Any]:
    return _read_json(Path(path))


def get_reference_profile(base: str, path: Path | str = DEFAULT_OUT) -> dict[str, Any]:
    payload = load_reference_profiles_v4(path)
    profiles = payload.get("profiles") or {}
    return dict(profiles.get(base) or {})


def normalize_reference_sample(base: str, sample: dict[str, Any], source_profile: Path | None = None) -> dict[str, Any]:
    view_layout = [item for item in sample.get("view_layout") or [] if isinstance(item, dict)]
    display_dim_count = _int(sample.get("display_dim_count"))
    return {
        "schema": "sw_drawing_studio.reference_profile_sample.v4",
        "base": base,
        "source_profile": str(source_profile or ""),
        "source_reference": sample.get("path") or "",
        "view_count": _int(sample.get("view_count")),
        "view_types": {str(k): _int(v) for k, v in (sample.get("view_types") or {}).items()},
        "view_positions": [_view_position(item) for item in view_layout],
        "sheet_size": sample.get("sheet_size_m") or {},
        "scale": sample.get("scale") or "reference",
        "display_dim_count": display_dim_count,
        "dimension_bboxes": sample.get("dimension_bboxes") or [],
        "hole_annotations": sample.get("hole_annotations") or [],
        "radius_annotations": sample.get("radius_annotations") or [],
        "thread_annotations": sample.get("thread_annotations") or [],
        "slot_annotations": sample.get("slot_annotations") or [],
        "titlebar_fields": sample.get("titlebar_fields") or {},
        "notes_raw_text": sample.get("notes_raw_text") or sample.get("raw_notes") or [],
        "normalized_notes": sample.get("normalized_notes") or [],
        "roughness_symbols": sample.get("roughness_symbols") or [],
        "datum_symbols": sample.get("datum_symbols") or [],
        "center_marks": sample.get("center_marks") or [],
        "centerlines": sample.get("centerlines") or [],
        "quality": {
            "usable_for_blueprint": bool(sample.get("success", True)),
            "source": sample.get("source") or "",
            "reason": sample.get("reason") or "",
        },
    }


def _view_position(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": item.get("name") or "",
        "type": str(item.get("type") or ""),
        "center_norm": _float_list(item.get("center_norm")),
        "center_m": _float_list(item.get("center_m")),
        "outline_m": _float_list(item.get("outline_m")),
        "size_norm": _float_list(item.get("size_norm")),
    }


def _first_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return paths[0] if paths else None


def _read_json(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except Exception:
        return 0


def _float_list(value: Any) -> list[float]:
    if not isinstance(value, list):
        return []
    result: list[float] = []
    for item in value:
        try:
            result.append(round(float(item), 6))
        except Exception:
            pass
    return result
