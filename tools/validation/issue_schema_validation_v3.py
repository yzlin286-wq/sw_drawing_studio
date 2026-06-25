"""Validate v3.0 visual issue schema completeness.

This is an offline evidence validator. It scans existing JSON artifacts for
visual issue lists and verifies that every issue has the fields required by the
v3.0 final acceptance gate. It does not modify historical artifacts or relax
thresholds.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCAN_ROOTS = [
    REPO_ROOT / "drw_output" / "runs",
    REPO_ROOT / "drw_output" / "v5",
    REPO_ROOT / "drw_output" / "v22_validation",
    REPO_ROOT / "drw_output" / "batch_reports",
    REPO_ROOT / "drw_output" / "ui_acceptance",
]
DEFAULT_OUT = REPO_ROOT / "drw_output" / "issue_schema_validation.json"
REQUIRED_FIELDS = [
    "key",
    "severity",
    "bbox",
    "source",
    "confidence",
    "evidence",
    "fix_suggestion",
    "auto_fix_available",
    "human_review_status",
]


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _iter_json_files(roots: list[Path]) -> list[Path]:
    files: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        if root.is_file() and root.suffix.lower() == ".json":
            files.append(root)
            continue
        for path in root.rglob("*.json"):
            if path.is_file():
                files.append(path)
    return sorted(files)


def _find_issue_lists(node: Any, location: str = "$") -> list[tuple[str, list[Any]]]:
    found: list[tuple[str, list[Any]]] = []
    if isinstance(node, dict):
        for key, value in node.items():
            child_location = f"{location}.{key}"
            if key == "issues" and isinstance(value, list):
                found.append((child_location, value))
            else:
                found.extend(_find_issue_lists(value, child_location))
    elif isinstance(node, list):
        for index, item in enumerate(node):
            found.extend(_find_issue_lists(item, f"{location}[{index}]"))
    return found


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def _validate_bbox(value: Any) -> str:
    if not isinstance(value, list) or len(value) < 4:
        return "bbox_must_be_list_len4"
    try:
        nums = [float(v) for v in value[:4]]
    except Exception:
        return "bbox_values_must_be_numeric"
    if any(v < 0 or v > 1 for v in nums):
        return "bbox_values_must_be_normalized_0_to_1"
    if nums[2] <= 0 or nums[3] <= 0:
        return "bbox_width_height_must_be_positive"
    return ""


def _validate_confidence(value: Any) -> str:
    try:
        number = float(value)
    except Exception:
        return "confidence_must_be_numeric"
    if number < 0 or number > 1:
        return "confidence_must_be_0_to_1"
    return ""


def _validate_issue(issue: Any) -> dict[str, Any]:
    if not isinstance(issue, dict):
        return {
            "issue_key": str(issue)[:120],
            "missing_fields": list(REQUIRED_FIELDS),
            "invalid_fields": ["issue_must_be_object"],
        }

    missing = [field for field in REQUIRED_FIELDS if field not in issue or not _has_value(issue.get(field))]
    invalid: list[str] = []
    if "bbox" in issue and _has_value(issue.get("bbox")):
        bbox_error = _validate_bbox(issue.get("bbox"))
        if bbox_error:
            invalid.append(bbox_error)
    if "confidence" in issue and _has_value(issue.get("confidence")):
        confidence_error = _validate_confidence(issue.get("confidence"))
        if confidence_error:
            invalid.append(confidence_error)
    if "auto_fix_available" in issue and not isinstance(issue.get("auto_fix_available"), bool):
        invalid.append("auto_fix_available_must_be_boolean")
    return {
        "issue_key": str(issue.get("key") or "")[:120],
        "missing_fields": missing,
        "invalid_fields": invalid,
    }


def validate_issue_schema(paths: list[Path]) -> dict[str, Any]:
    scanned_files = 0
    files_with_issues = 0
    issue_count = 0
    compliant_count = 0
    failures: list[dict[str, Any]] = []

    for path in paths:
        payload = _read_json(path)
        if payload is None:
            continue
        scanned_files += 1
        issue_lists = _find_issue_lists(payload)
        if not issue_lists:
            continue
        files_with_issues += 1
        for issue_path, issues in issue_lists:
            for index, issue in enumerate(issues):
                issue_count += 1
                result = _validate_issue(issue)
                if result["missing_fields"] or result["invalid_fields"]:
                    failures.append(
                        {
                            "file": str(path),
                            "issue_path": f"{issue_path}[{index}]",
                            "issue_key": result["issue_key"],
                            "missing_fields": result["missing_fields"],
                            "invalid_fields": result["invalid_fields"],
                            "fix_suggestion": (
                                "Regenerate this Vision QC artifact with v5 schema or normalize the issue record to "
                                "include key, severity, bbox, source, confidence, evidence, fix_suggestion, "
                                "auto_fix_available, and human_review_status."
                            ),
                        }
                    )
                else:
                    compliant_count += 1

    noncompliant_count = len(failures)
    missing_field_counts: Counter[str] = Counter()
    invalid_field_counts: Counter[str] = Counter()
    failure_file_counts: Counter[str] = Counter()
    for item in failures:
        missing_field_counts.update(item.get("missing_fields") or [])
        invalid_field_counts.update(item.get("invalid_fields") or [])
        failure_file_counts[str(item.get("file") or "")] += 1
    if issue_count == 0:
        status = "fail"
        reasons = ["no_visual_issues_found"]
    elif noncompliant_count:
        status = "fail"
        reasons = ["vision_issue_schema_incomplete"]
    else:
        status = "pass"
        reasons = []

    return {
        "schema": "sw_drawing_studio.issue_schema_validation.v1",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "required_fields": REQUIRED_FIELDS,
        "status": status,
        "pass": status == "pass",
        "scanned_files": scanned_files,
        "files_with_issues": files_with_issues,
        "issue_count": issue_count,
        "compliant_issue_count": compliant_count,
        "noncompliant_issue_count": noncompliant_count,
        "failure_bucket": reasons,
        "missing_field_counts": dict(missing_field_counts.most_common()),
        "invalid_field_counts": dict(invalid_field_counts.most_common()),
        "top_failure_files": [
            {"file": file, "failure_count": count}
            for file, count in failure_file_counts.most_common(20)
        ],
        "failures": failures,
        "fix_suggestions": sorted({item["fix_suggestion"] for item in failures})
        or ["No action needed; all discovered visual issues satisfy the required schema."],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate v3.0 visual issue schema completeness.")
    parser.add_argument("--root", action="append", default=[], help="Scan root; repeat for multiple roots.")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    roots = [Path(item) for item in args.root] if args.root else list(DEFAULT_SCAN_ROOTS)
    roots = [path if path.is_absolute() else (REPO_ROOT / path).resolve() for path in roots]
    out = Path(args.out)
    if not out.is_absolute():
        out = (REPO_ROOT / out).resolve()

    payload = validate_issue_schema(_iter_json_files(roots))
    payload["scan_roots"] = [str(path) for path in roots]
    _write_json(out, payload)
    print(json.dumps({
        "pass": payload["pass"],
        "status": payload["status"],
        "report": str(out),
        "issue_count": payload["issue_count"],
        "noncompliant_issue_count": payload["noncompliant_issue_count"],
    }, ensure_ascii=False))
    return 0 if payload["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
