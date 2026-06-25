from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REFERENCE_ROOT = REPO_ROOT / "3D转2D测试图纸"
SUPPORTED = {".sldprt", ".sldasm", ".slddrw", ".pdf", ".png", ".dxf"}


def build_reference_pairs(
    *,
    root: Path | str = DEFAULT_REFERENCE_ROOT,
    out_path: Path | str | None = None,
) -> dict[str, Any]:
    root = Path(root)
    files = _scan_files(root)
    stems = sorted({path.stem for path in files})
    pairs: list[dict[str, Any]] = []
    for stem in stems:
        by_ext = {ext: sorted([p for p in files if p.stem == stem and p.suffix.lower() == ext]) for ext in SUPPORTED}
        part = _one(by_ext.get(".sldprt") or [])
        assembly = _one(by_ext.get(".sldasm") or [])
        drawings = by_ext.get(".slddrw") or []
        status = "paired" if drawings and (part or assembly) else "missing_reference"
        reason = ""
        if len(drawings) > 1:
            status = "ambiguous"
            reason = "multiple_slddrw_references"
        elif drawings and not (part or assembly):
            status = "reference_without_3d"
            reason = "no_matching_sldprt_or_sldasm"
        elif not drawings:
            reason = "missing_slddrw_reference"

        pairs.append({
            "base": stem,
            "part": str(part) if part else "",
            "assembly": str(assembly) if assembly else "",
            "reference_drawing": str(drawings[0]) if len(drawings) == 1 else "",
            "reference_pdf": str(_one(by_ext.get(".pdf") or []) or ""),
            "reference_png": str(_one(by_ext.get(".png") or []) or ""),
            "reference_dxf": str(_one(by_ext.get(".dxf") or []) or ""),
            "status": status,
            "reason": reason,
        })

    payload = {
        "schema": "sw_drawing_studio.reference_pairs.v4",
        "root": str(root),
        "pair_count": len(pairs),
        "pairs": pairs,
    }
    if out_path:
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        payload["output_path"] = str(out)
    return payload


def _scan_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in SUPPORTED)


def _one(paths: list[Path]) -> Path | None:
    return paths[0] if paths else None
