"""CLI wrapper for strict v4 reference comparison."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.reference_compare_v4 import compare_reference_v4


DEFAULT_REFERENCE_PROFILES = REPO_ROOT / "drw_output" / "reference_style_profile" / "reference_profiles_v4.json"


def _repo_path(value: str) -> Path | None:
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run strict v4 reference comparison from existing artifacts.")
    parser.add_argument("--base", default="")
    parser.add_argument("--blueprint", required=True)
    parser.add_argument("--dimension-validation", required=True)
    parser.add_argument("--vision-qc", required=True)
    parser.add_argument("--generator-warnings", default="")
    parser.add_argument("--reference-profile", default="")
    parser.add_argument("--reference-profiles", default=str(DEFAULT_REFERENCE_PROFILES))
    parser.add_argument("--legacy-reference-compare", default="")
    parser.add_argument("--legacy-reference-style", default="")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    out = _repo_path(args.out)
    payload = compare_reference_v4(
        base=args.base,
        blueprint=_repo_path(args.blueprint),
        dimension_validation=_repo_path(args.dimension_validation),
        vision_qc=_repo_path(args.vision_qc),
        generator_warnings=_repo_path(args.generator_warnings),
        reference_profile=_repo_path(args.reference_profile),
        reference_profiles=_repo_path(args.reference_profiles),
        legacy_reference_compare=_repo_path(args.legacy_reference_compare),
        legacy_reference_style=_repo_path(args.legacy_reference_style),
        out_path=out,
    )
    print(json.dumps({
        "pass": payload.get("pass"),
        "status": payload.get("status"),
        "overall_score": payload.get("overall_score"),
        "report": str(out or ""),
        "reasons": payload.get("reasons", []),
    }, ensure_ascii=False))
    return 0 if payload.get("pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
