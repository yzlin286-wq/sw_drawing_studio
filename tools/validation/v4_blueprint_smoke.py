from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.drawing_blueprint_builder import build_drawing_blueprint
from app.services.drawing_blueprint_model import write_blueprint_json_schema
from app.services.reference_style_profile_service import build_reference_profiles_v4


DEFAULT_BASES = [
    "LB26001-A-04-006",
    "LB26001-A-04-007",
    "LB26001-A-04-008",
    "LB26001-A-04-009",
    "LB26001-A-04-015",
    "LB26001-A-04-022",
]


def run_smoke(
    *,
    bases: list[str],
    part_class: str,
    out_dir: Path,
    source_profile: Path | None = None,
) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    profiles_path = REPO_ROOT / "drw_output" / "reference_style_profile" / "reference_profiles_v4.json"
    profiles = build_reference_profiles_v4(source_profile=source_profile, out_path=profiles_path)
    samples = profiles.get("profiles") or {}
    blueprints = {}
    reasons = []

    for base in bases:
        reference_profile = samples.get(base) or {}
        if not reference_profile:
            reasons.append(f"missing_reference_profile:{base}")
        blueprint = build_drawing_blueprint(
            base=base,
            part_class=part_class,
            reference_profile=reference_profile,
        )
        blueprints[base] = blueprint.to_dict()

    aggregate = {
        "schema": "sw_drawing_studio.drawing_blueprints_v4.smoke",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "status": "pass" if not reasons else "need_review",
        "pass": not reasons,
        "bases": bases,
        "part_class": part_class,
        "reference_profiles_v4": str(profiles_path),
        "blueprint_count": len(blueprints),
        "blueprints": blueprints,
        "reasons": reasons,
    }
    blueprints_path = out_dir / "drawing_blueprints_v4.json"
    schema_path = out_dir / "drawing_blueprint_schema_v4.json"
    blueprints_path.write_text(json.dumps(aggregate, ensure_ascii=False, indent=2), encoding="utf-8")
    write_blueprint_json_schema(schema_path)
    aggregate["output_path"] = str(blueprints_path)
    aggregate["schema_path"] = str(schema_path)
    return aggregate


def main() -> int:
    parser = argparse.ArgumentParser(description="Build v4 reference profiles and DrawingBlueprint smoke artifacts.")
    parser.add_argument("--base", action="append", dest="bases", help="Base name. Repeat to override default six.")
    parser.add_argument("--part-class", default="machined_part")
    parser.add_argument("--source-profile", default="")
    parser.add_argument("--out-dir", default=str(REPO_ROOT / "drw_output" / "v4_blueprint_smoke"))
    args = parser.parse_args()

    result = run_smoke(
        bases=args.bases or DEFAULT_BASES,
        part_class=args.part_class,
        out_dir=Path(args.out_dir),
        source_profile=Path(args.source_profile) if args.source_profile else None,
    )
    print(json.dumps({
        "pass": result["pass"],
        "status": result["status"],
        "blueprint_count": result["blueprint_count"],
        "output_path": result["output_path"],
        "schema_path": result["schema_path"],
        "reference_profiles_v4": result["reference_profiles_v4"],
        "reasons": result["reasons"],
    }, ensure_ascii=False))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
