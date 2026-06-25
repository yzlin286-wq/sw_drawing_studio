"""Build a normalized visual issue index without modifying historical artifacts."""
from __future__ import annotations

import argparse
from collections import Counter
import json
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.vision_issue_schema import normalize_issue
from tools.validation.issue_schema_validation_v3 import (
    DEFAULT_SCAN_ROOTS,
    _find_issue_lists,
    _iter_json_files,
    _read_json,
    _write_json,
    validate_issue_schema,
)


DEFAULT_OUT = REPO_ROOT / "drw_output" / "visual_audit" / "normalized_issue_index.json"
DEFAULT_VALIDATION_OUT = REPO_ROOT / "drw_output" / "issue_schema_validation_normalized.json"


def _relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except Exception:
        return str(path)


def build_normalized_issue_index(roots: list[Path], out: Path) -> dict[str, Any]:
    paths = _iter_json_files(roots)
    issues: list[dict[str, Any]] = []
    files_with_issues = 0
    source_issue_lists = 0
    warning_counts: Counter[str] = Counter()

    for path in paths:
        payload = _read_json(path)
        if payload is None:
            continue
        issue_lists = _find_issue_lists(payload)
        if not issue_lists:
            continue
        files_with_issues += 1
        source_name = _relative(path)
        for issue_path, raw_issues in issue_lists:
            source_issue_lists += 1
            for index, issue in enumerate(raw_issues):
                normalized = normalize_issue(
                    issue,
                    source_file=source_name,
                    issue_path=f"{issue_path}[{index}]",
                    default_source="historical_visual_audit",
                )
                warnings = normalized.get("normalization", {}).get("warnings") or []
                warning_counts.update(str(item) for item in warnings)
                issues.append(normalized)

    payload = {
        "schema": "sw_drawing_studio.normalized_issue_index.v1",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "status": "pass" if issues else "fail",
        "pass": bool(issues),
        "scan_roots": [_relative(path) for path in roots],
        "scanned_json_files": len(paths),
        "files_with_issues": files_with_issues,
        "source_issue_lists": source_issue_lists,
        "issue_count": len(issues),
        "normalization_warning_count": sum(warning_counts.values()),
        "normalization_warning_counts": dict(warning_counts.most_common()),
        "issues": issues,
        "notes": [
            "This index is normalized evidence for review; it does not edit or replace the original historical JSON artifacts.",
            "Fallback full-page bbox or zero confidence means the legacy source lacked precise evidence and requires human review.",
        ],
    }
    _write_json(out, payload)
    return payload


def write_validation_report(index_path: Path, validation_out: Path) -> dict[str, Any]:
    validation = validate_issue_schema([index_path])
    validation["scan_roots"] = [str(index_path)]
    _write_json(validation_out, validation)
    return validation


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize visual issue lists into a v3.0 review index.")
    parser.add_argument("--root", action="append", default=[], help="Scan root; repeat for multiple roots.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Normalized issue index output path.")
    parser.add_argument(
        "--validation-out",
        default=str(DEFAULT_VALIDATION_OUT),
        help="Output path for schema validation of the normalized issue index.",
    )
    args = parser.parse_args()

    roots = [Path(item) for item in args.root] if args.root else list(DEFAULT_SCAN_ROOTS)
    roots = [path if path.is_absolute() else (REPO_ROOT / path).resolve() for path in roots]
    out = Path(args.out)
    if not out.is_absolute():
        out = (REPO_ROOT / out).resolve()
    validation_out = Path(args.validation_out)
    if not validation_out.is_absolute():
        validation_out = (REPO_ROOT / validation_out).resolve()

    payload = build_normalized_issue_index(roots, out)
    validation = write_validation_report(out, validation_out)
    print(
        json.dumps(
            {
                "pass": bool(payload.get("pass")) and bool(validation.get("pass")),
                "index": str(out),
                "validation": str(validation_out),
                "issue_count": payload.get("issue_count", 0),
                "normalization_warning_count": payload.get("normalization_warning_count", 0),
                "validation_status": validation.get("status"),
                "validation_noncompliant_issue_count": validation.get("noncompliant_issue_count", 0),
            },
            ensure_ascii=False,
        )
    )
    return 0 if payload.get("pass") and validation.get("pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
