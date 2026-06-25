from __future__ import annotations

from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
LB_REFERENCE_SAMPLE_BASES = {
    "LB26001-A-04-006",
    "LB26001-A-04-007",
    "LB26001-A-04-008",
    "LB26001-A-04-009",
    "LB26001-A-04-015",
    "LB26001-A-04-022",
}


def _resolved_path(value: str | Path, *, base_dir: Path | None = None) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path.resolve()
    if base_dir is not None:
        return (base_dir / path).resolve()
    return (REPO_ROOT / path).resolve()


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def generated_png_source_evidence(
    *,
    base: str,
    run_dir: str | Path | None,
    generated_png: str | Path | None,
    source: str = "report_path_inference",
    repo_root: Path = REPO_ROOT,
    base_dir: Path | None = None,
) -> dict[str, Any]:
    base = str(base or "").strip()
    png_text = str(generated_png or "").strip()
    run_text = str(run_dir or "").strip()
    legacy_v5_dir = (repo_root / "drw_output" / "v5").resolve()
    strict_sample = base in LB_REFERENCE_SAMPLE_BASES
    if not png_text:
        return {
            "base": base,
            "path": "",
            "source": source,
            "exists": False,
            "strict_sample": strict_sample,
            "under_run_dir": False,
            "under_legacy_v5": False,
            "strict_source_pass": False,
            "reasons": ["generated_png_missing_or_empty"],
            "acceptance_rule": _acceptance_rule(),
        }

    resolved_png = _resolved_path(png_text, base_dir=base_dir)
    resolved_run_dir = _resolved_path(run_text, base_dir=base_dir) if run_text else Path()
    exists = resolved_png.exists() and resolved_png.is_file() and resolved_png.stat().st_size > 0
    under_run_dir = bool(run_text) and _is_under(resolved_png, resolved_run_dir)
    under_legacy_v5 = _is_under(resolved_png, legacy_v5_dir)
    strict_source_pass = bool(exists and (not strict_sample or (under_run_dir and not under_legacy_v5)))
    reasons: list[str] = []
    if not exists:
        reasons.append("generated_png_missing_or_empty")
    if strict_sample and under_legacy_v5:
        reasons.append("legacy_drw_output_v5_png_not_allowed_for_lb26001_ui_acceptance")
    if strict_sample and exists and not under_run_dir:
        reasons.append("generated_png_not_under_current_run_dir")
    return {
        "base": base,
        "path": str(resolved_png),
        "source": source,
        "exists": exists,
        "strict_sample": strict_sample,
        "under_run_dir": under_run_dir,
        "under_legacy_v5": under_legacy_v5,
        "strict_source_pass": strict_source_pass,
        "reasons": reasons,
        "acceptance_rule": _acceptance_rule(),
    }


def _acceptance_rule() -> str:
    return (
        "For LB26001-A-04-006/007/008/009/015/022, Drawing Review UI evidence must use "
        "the generated PNG from the current run_dir; stale drw_output/v5 images are diagnostic only."
    )
