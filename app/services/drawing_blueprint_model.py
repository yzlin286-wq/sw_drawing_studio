from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


SCHEMA = "sw_drawing_studio.drawing_blueprint.v4"


@dataclass
class ViewPlan:
    slot: str
    view_type: str
    required: bool = True
    source: str = "part_class_default"
    center_norm: list[float] = field(default_factory=list)
    scale: str = "auto"
    sw_view_type: str = ""
    create_method: str = "named_view"
    projected_from: str = ""
    outline_norm: list[float] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)


@dataclass
class DimensionPlan:
    required_display_dim_count: int = 0
    reference_display_dim_count: int = 0
    required_overall_dims: list[str] = field(default_factory=list)
    hole_dims: list[str] = field(default_factory=list)
    slot_dims: list[str] = field(default_factory=list)
    radius_dims: list[str] = field(default_factory=list)
    thread_dims: list[str] = field(default_factory=list)
    datum_dims: list[str] = field(default_factory=list)
    inspection_dims: list[str] = field(default_factory=list)
    dimension_intent_groups: list[dict[str, Any]] = field(default_factory=list)
    dimension_targets: list[dict[str, Any]] = field(default_factory=list)
    view_dimension_quotas: dict[str, int] = field(default_factory=dict)
    dimension_priority: list[str] = field(default_factory=list)
    fallback_policy: str = "need_review_when_real_displaydim_unavailable"
    allow_note_substitution: bool = False
    source: str = "part_class_default"
    reasons: list[str] = field(default_factory=list)


@dataclass
class AnnotationPlan:
    roughness_required: bool = False
    datum_required: bool = False
    center_marks_required: bool = False
    centerlines_required: bool = False
    section_arrows_required: bool = False
    symbols: list[dict[str, Any]] = field(default_factory=list)
    source: str = "part_class_default"
    reasons: list[str] = field(default_factory=list)


@dataclass
class TitlebarPlan:
    required_fields: list[str] = field(default_factory=lambda: ["drawing_no", "name", "material", "scale", "date"])
    fields: dict[str, Any] = field(default_factory=dict)
    missing_fields: list[str] = field(default_factory=list)
    source_priority: list[str] = field(
        default_factory=lambda: [
            "ui_input",
            "custom_property",
            "reference_titlebar",
            "filename",
            "default",
        ]
    )
    source: str = "filename_plus_defaults"


@dataclass
class NotesPlan:
    part_class: str = "feature_part"
    required_notes: list[str] = field(default_factory=list)
    optional_notes: list[str] = field(default_factory=list)
    raw_reference_notes: list[str] = field(default_factory=list)
    normalized_notes: list[dict[str, Any]] = field(default_factory=list)
    warning_notes: list[str] = field(default_factory=list)
    note_box_norm: list[float] = field(default_factory=list)
    source: str = "part_class_default"
    reasons: list[str] = field(default_factory=list)


@dataclass
class ValidationPlan:
    required_artifacts: list[str] = field(
        default_factory=lambda: [
            "SLDDRW",
            "PDF",
            "DXF",
            "PNG",
            "drawing_blueprint.json",
            "dimension_validation.json",
            "reference_compare.json",
            "vision_qc.json",
        ]
    )
    view_match_min: float = 0.90
    dimension_match_min: float = 0.80
    titlebar_match_min: float = 0.85
    notes_match_min: float = 0.85
    layout_match_min: float = 0.80
    require_true_display_dim: bool = True
    forbid_note_as_display_dim: bool = True
    forbid_named_view_as_projected: bool = True
    require_ui_visual_review: bool = True
    failure_bucket_required: bool = True
    reasons: list[str] = field(default_factory=list)


@dataclass
class DrawingBlueprint:
    base: str
    part_class: str
    drawing_purpose: str = "manufacturing"
    manufacturing_intent: str = "make_or_inspect"
    reference_storyboard: dict[str, Any] = field(default_factory=dict)
    view_roles: dict[str, Any] = field(default_factory=dict)
    notes_title_policy: dict[str, Any] = field(default_factory=dict)
    visual_acceptance_checklist: list[str] = field(
        default_factory=lambda: [
            "reference_match",
            "view_layout",
            "display_dimensions",
            "dimension_readability",
            "title_block",
            "manufacturing_notes",
        ]
    )
    reference_base: str = ""
    schema: str = SCHEMA
    version: str = "v4.0"
    generated_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))
    view_plan: list[ViewPlan] = field(default_factory=list)
    dimension_plan: DimensionPlan = field(default_factory=DimensionPlan)
    annotation_plan: AnnotationPlan = field(default_factory=AnnotationPlan)
    titlebar_plan: TitlebarPlan = field(default_factory=TitlebarPlan)
    notes_plan: NotesPlan = field(default_factory=NotesPlan)
    validation_plan: ValidationPlan = field(default_factory=ValidationPlan)
    layout_plan: dict[str, Any] = field(default_factory=dict)
    source_inputs: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    def write_json(self, path: Path | str) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(self.to_json(), encoding="utf-8")
        return out

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DrawingBlueprint":
        data = dict(payload)
        data["view_plan"] = [ViewPlan(**item) for item in data.get("view_plan") or []]
        data["dimension_plan"] = DimensionPlan(**(data.get("dimension_plan") or {}))
        data["annotation_plan"] = AnnotationPlan(**(data.get("annotation_plan") or {}))
        data["titlebar_plan"] = TitlebarPlan(**(data.get("titlebar_plan") or {}))
        data["notes_plan"] = NotesPlan(**(data.get("notes_plan") or {}))
        data["validation_plan"] = ValidationPlan(**(data.get("validation_plan") or {}))
        return cls(**data)


def blueprint_json_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://local.sw-drawing-studio/schemas/drawing_blueprint_v4.json",
        "title": "DrawingBlueprint v4",
        "type": "object",
        "required": [
            "schema",
            "version",
            "base",
            "part_class",
            "view_plan",
            "dimension_plan",
            "annotation_plan",
            "titlebar_plan",
            "notes_plan",
            "validation_plan",
        ],
        "properties": {
            "schema": {"const": SCHEMA},
            "version": {"type": "string"},
            "base": {"type": "string", "minLength": 1},
            "part_class": {"type": "string", "minLength": 1},
            "drawing_purpose": {"type": "string"},
            "manufacturing_intent": {"type": "string"},
            "reference_storyboard": {"type": "object"},
            "view_roles": {"type": "object"},
            "notes_title_policy": {"type": "object"},
            "visual_acceptance_checklist": {"type": "array", "items": {"type": "string"}},
            "reference_base": {"type": "string"},
            "generated_at": {"type": "string"},
            "view_plan": {
                "type": "array",
                "items": {"$ref": "#/$defs/ViewPlan"},
            },
            "dimension_plan": {"$ref": "#/$defs/DimensionPlan"},
            "annotation_plan": {"$ref": "#/$defs/AnnotationPlan"},
            "titlebar_plan": {"$ref": "#/$defs/TitlebarPlan"},
            "notes_plan": {"$ref": "#/$defs/NotesPlan"},
            "validation_plan": {"$ref": "#/$defs/ValidationPlan"},
            "layout_plan": {"type": "object"},
            "source_inputs": {"type": "object"},
            "warnings": {"type": "array", "items": {"type": "string"}},
            "reasons": {"type": "array", "items": {"type": "string"}},
        },
        "$defs": {
            "ViewPlan": {
                "type": "object",
                "required": ["slot", "view_type", "required", "source", "create_method"],
                "properties": {
                    "slot": {"type": "string"},
                    "view_type": {"type": "string"},
                    "required": {"type": "boolean"},
                    "source": {"type": "string"},
                    "center_norm": {"type": "array", "items": {"type": "number"}},
                    "scale": {"type": "string"},
                    "sw_view_type": {"type": "string"},
                    "create_method": {"type": "string"},
                    "projected_from": {"type": "string"},
                    "outline_norm": {"type": "array", "items": {"type": "number"}},
                    "reasons": {"type": "array", "items": {"type": "string"}},
                },
            },
            "DimensionPlan": {
                "type": "object",
                "required": [
                    "required_display_dim_count",
                    "allow_note_substitution",
                    "fallback_policy",
                ],
                "properties": {
                    "required_display_dim_count": {"type": "integer", "minimum": 0},
                    "reference_display_dim_count": {"type": "integer", "minimum": 0},
                    "required_overall_dims": {"type": "array", "items": {"type": "string"}},
                    "hole_dims": {"type": "array", "items": {"type": "string"}},
                    "slot_dims": {"type": "array", "items": {"type": "string"}},
                    "radius_dims": {"type": "array", "items": {"type": "string"}},
                    "thread_dims": {"type": "array", "items": {"type": "string"}},
                    "datum_dims": {"type": "array", "items": {"type": "string"}},
                    "inspection_dims": {"type": "array", "items": {"type": "string"}},
                    "dimension_intent_groups": {"type": "array", "items": {"type": "object"}},
                    "dimension_targets": {"type": "array", "items": {"type": "object"}},
                    "view_dimension_quotas": {
                        "type": "object",
                        "additionalProperties": {"type": "integer", "minimum": 0},
                    },
                    "dimension_priority": {"type": "array", "items": {"type": "string"}},
                    "fallback_policy": {"type": "string"},
                    "allow_note_substitution": {"const": False},
                    "source": {"type": "string"},
                    "reasons": {"type": "array", "items": {"type": "string"}},
                },
            },
            "AnnotationPlan": {"type": "object"},
            "TitlebarPlan": {"type": "object"},
            "NotesPlan": {"type": "object"},
            "ValidationPlan": {
                "type": "object",
                "required": [
                    "required_artifacts",
                    "require_true_display_dim",
                    "forbid_note_as_display_dim",
                    "forbid_named_view_as_projected",
                    "require_ui_visual_review",
                ],
                "properties": {
                    "required_artifacts": {"type": "array", "items": {"type": "string"}},
                    "view_match_min": {"type": "number"},
                    "dimension_match_min": {"type": "number"},
                    "titlebar_match_min": {"type": "number"},
                    "notes_match_min": {"type": "number"},
                    "layout_match_min": {"type": "number"},
                    "require_true_display_dim": {"type": "boolean"},
                    "forbid_note_as_display_dim": {"const": True},
                    "forbid_named_view_as_projected": {"const": True},
                    "require_ui_visual_review": {"const": True},
                    "failure_bucket_required": {"const": True},
                    "reasons": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        "additionalProperties": False,
    }


def write_blueprint_json_schema(path: Path | str) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(blueprint_json_schema(), ensure_ascii=False, indent=2), encoding="utf-8")
    return out
