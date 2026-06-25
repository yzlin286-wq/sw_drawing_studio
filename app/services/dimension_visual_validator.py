from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.drawing_object_detector import detect_drawing_objects


def validate_dimension_visuals(
    png_path: Path | str,
    *,
    blueprint: dict[str, Any] | None = None,
    drawing_objects: dict[str, Any] | None = None,
) -> dict[str, Any]:
    blueprint = blueprint or {}
    drawing_objects = drawing_objects or detect_drawing_objects(png_path)
    dimension_plan = blueprint.get("dimension_plan") or {}
    required_display_dim_count = _int(dimension_plan.get("required_display_dim_count"))
    text_candidates = _int(drawing_objects.get("dimension_text_candidate_count"))
    arrow_candidates = _int(drawing_objects.get("dimension_arrow_candidate_count"))
    min_visual_candidates = _visual_floor(required_display_dim_count)
    too_sparse = required_display_dim_count > 0 and text_candidates < min_visual_candidates
    too_dense = required_display_dim_count > 0 and text_candidates > max(required_display_dim_count * 8, 80)
    cluster = _dimension_text_cluster_summary(
        drawing_objects.get("dimension_text_candidates") or [],
        required_display_dim_count,
        blueprint,
    )

    return {
        "success": bool(drawing_objects.get("success", False)),
        "required_display_dim_count": required_display_dim_count,
        "dimension_text_candidate_count": text_candidates,
        "dimension_arrow_candidate_count": arrow_candidates,
        "min_visual_candidate_count": min_visual_candidates,
        "visual_dimension_coverage_pass": not too_sparse,
        "visual_dimension_density_pass": not too_dense,
        "visual_dimension_cluster_pass": not bool(cluster.get("dimension_text_clustered")),
        **cluster,
        "text_candidate_examples": (drawing_objects.get("dimension_text_candidates") or [])[:20],
        "arrow_candidate_examples": (drawing_objects.get("dimension_arrow_candidates") or [])[:20],
        "source": "dimension_visual_candidates",
    }


def _visual_floor(required_display_dim_count: int) -> int:
    if required_display_dim_count <= 0:
        return 0
    if required_display_dim_count <= 4:
        return max(1, required_display_dim_count)
    return max(4, min(required_display_dim_count, required_display_dim_count // 2))


def _dimension_text_cluster_summary(
    candidates: list[dict[str, Any]],
    required_display_dim_count: int,
    blueprint: dict[str, Any],
) -> dict[str, Any]:
    centers: list[tuple[float, float, dict[str, Any]]] = []
    for item in candidates:
        bbox = item.get("bbox") if isinstance(item, dict) else None
        if not isinstance(bbox, list) or len(bbox) < 4:
            continue
        try:
            x = float(bbox[0]) + float(bbox[2]) / 2.0
            y = float(bbox[1]) + float(bbox[3]) / 2.0
        except Exception:
            continue
        centers.append((x, y, item))

    threshold = _dimension_cluster_threshold(required_display_dim_count)
    window_x = 0.075
    window_y = 0.060
    best: list[tuple[float, float, dict[str, Any]]] = []
    for center_x, center_y, _item in centers:
        group = [
            item
            for item in centers
            if abs(item[0] - center_x) <= window_x and abs(item[1] - center_y) <= window_y
        ]
        if len(group) > len(best):
            best = group

    clustered = (
        _reference_style_dimension_readability_required(blueprint)
        and required_display_dim_count > 0
        and len(best) >= threshold
    )
    return {
        "reference_style_dimension_readability_required": _reference_style_dimension_readability_required(blueprint),
        "dimension_text_cluster_window_norm": [window_x, window_y],
        "max_local_dimension_text_cluster_count": len(best),
        "dimension_text_cluster_threshold": threshold,
        "dimension_text_clustered": bool(clustered),
        "dimension_text_cluster_bbox_norm": _cluster_bbox(best),
        "dimension_text_cluster_examples": [item[2] for item in best[:20]],
    }


def _dimension_cluster_threshold(required_display_dim_count: int) -> int:
    if required_display_dim_count <= 0:
        return 999999
    return max(6, min(12, int(round(required_display_dim_count * 0.55))))


def _reference_style_dimension_readability_required(blueprint: dict[str, Any]) -> bool:
    layout = (blueprint or {}).get("layout_plan") or {}
    policy = layout.get("sheet_template_policy") or {}
    dimension_plan = (blueprint or {}).get("dimension_plan") or {}
    if isinstance(policy, dict) and (
        policy.get("default_template_artifacts_allowed") is False
        or policy.get("skip_builtin_gb_frame_titleblock") is True
        or str(policy.get("policy") or "") == "strip_default_template_artifacts"
    ):
        return True
    return bool(dimension_plan.get("dimension_targets"))


def _cluster_bbox(group: list[tuple[float, float, dict[str, Any]]]) -> list[float]:
    boxes: list[list[float]] = []
    for _x, _y, item in group:
        bbox = item.get("bbox") if isinstance(item, dict) else None
        if isinstance(bbox, list) and len(bbox) >= 4:
            try:
                boxes.append([float(value) for value in bbox[:4]])
            except Exception:
                pass
    if not boxes:
        return []
    left = min(box[0] for box in boxes)
    top = min(box[1] for box in boxes)
    right = max(box[0] + box[2] for box in boxes)
    bottom = max(box[1] + box[3] for box in boxes)
    return [round(left, 6), round(top, 6), round(right - left, 6), round(bottom - top, 6)]


def _int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except Exception:
        return 0
