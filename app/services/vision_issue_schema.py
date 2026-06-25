from __future__ import annotations

import json
import re
from typing import Any


REQUIRED_ISSUE_FIELDS = [
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

_DEFAULT_BBOX = [0.0, 0.0, 1.0, 1.0]
_DEFAULT_FIX = (
    "人工复核原始视觉证据；必要时重新运行 Vision QC v5，生成带 bbox、confidence、evidence 的结构化 issue。"
)


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def _first_text(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _safe_json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except Exception:
        return repr(value)


def _slug_key(text: str) -> str:
    value = (text or "legacy_issue").strip().lower()
    value = re.sub(r"[^a-z0-9_\-\u4e00-\u9fff]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_-")
    if not value:
        value = "legacy_issue"
    return value[:80]


def _severity(value: Any, warnings: list[str]) -> str:
    text = _first_text(value).lower()
    mapping = {
        "fatal": "critical",
        "error": "critical",
        "fail": "critical",
        "failed": "critical",
        "warning": "minor",
        "warn": "minor",
        "need_review": "major",
        "review": "major",
    }
    if text:
        return mapping.get(text, text)
    warnings.append("severity_missing_default_major")
    return "major"


def _bbox_from_dict(issue: dict[str, Any]) -> Any:
    if "bbox" in issue:
        return issue.get("bbox")
    keys = ["x", "y", "w", "h"]
    if all(key in issue for key in keys):
        return [issue.get(key) for key in keys]
    keys = ["left", "top", "width", "height"]
    if all(key in issue for key in keys):
        return [issue.get(key) for key in keys]
    return None


def _coerce_bbox(value: Any, warnings: list[str]) -> list[float]:
    if isinstance(value, (tuple, list)) and len(value) >= 4:
        try:
            nums = [float(item) for item in value[:4]]
        except Exception:
            nums = []
        if len(nums) == 4:
            if nums[2] > 0 and nums[3] > 0 and all(0.0 <= item <= 1.0 for item in nums):
                return nums
            if nums[2] > 0 and nums[3] > 0 and all(0.0 <= item <= 100.0 for item in nums):
                warnings.append("bbox_percent_normalized")
                return [max(0.0, min(1.0, item / 100.0)) for item in nums]
    warnings.append("bbox_missing_or_invalid_default_full_page")
    return list(_DEFAULT_BBOX)


def _coerce_confidence(value: Any, warnings: list[str]) -> float:
    if value is not None and _has_value(value):
        try:
            number = float(value)
        except Exception:
            number = -1.0
        if 0.0 <= number <= 1.0:
            return number
        if 1.0 < number <= 100.0:
            warnings.append("confidence_percent_normalized")
            return number / 100.0
    warnings.append("confidence_missing_or_invalid_default_zero")
    return 0.0


def _coerce_evidence(issue: Any, source_file: str, issue_path: str, warnings: list[str]) -> dict[str, Any]:
    evidence_value: Any = None
    description = ""
    if isinstance(issue, dict):
        evidence_value = issue.get("evidence")
        description = _first_text(
            issue.get("description"),
            issue.get("desc"),
            issue.get("message"),
            issue.get("reason"),
            issue.get("key"),
        )
    else:
        description = _first_text(issue)

    if isinstance(evidence_value, dict) and evidence_value:
        evidence = dict(evidence_value)
    elif isinstance(evidence_value, list) and evidence_value:
        evidence = {"items": evidence_value}
    elif _has_value(evidence_value):
        evidence = {"text": str(evidence_value)}
    else:
        warnings.append("evidence_missing_synthesized_from_legacy_record")
        evidence = {}

    if description and "description" not in evidence:
        evidence["description"] = description
    if source_file:
        evidence["source_file"] = source_file
    if issue_path:
        evidence["issue_path"] = issue_path
    if warnings:
        evidence["normalization_warnings"] = list(warnings)
    evidence["raw_issue_json"] = _safe_json(issue)
    return evidence


def normalize_issue(
    issue: Any,
    *,
    source_file: str = "",
    issue_path: str = "",
    default_source: str = "legacy",
) -> dict[str, Any]:
    """Return one v3 visual issue record without hiding legacy uncertainty."""
    warnings: list[str] = []

    if isinstance(issue, dict):
        key_text = _first_text(
            issue.get("key"),
            issue.get("type"),
            issue.get("name"),
            issue.get("description"),
            issue.get("desc"),
            issue.get("message"),
        )
        result = dict(issue)
        result["key"] = _slug_key(key_text)
        result["severity"] = _severity(issue.get("severity") or issue.get("level"), warnings)
        result["bbox"] = _coerce_bbox(_bbox_from_dict(issue), warnings)
        result["source"] = _first_text(issue.get("source"), issue.get("origin"), default_source)
        confidence_value = issue.get("confidence") if "confidence" in issue else issue.get("score")
        result["confidence"] = _coerce_confidence(confidence_value, warnings)
        result["fix_suggestion"] = _first_text(issue.get("fix_suggestion"), issue.get("fix"), _DEFAULT_FIX)
        auto_fix = issue.get("auto_fix_available")
        if not isinstance(auto_fix, bool):
            warnings.append("auto_fix_available_missing_or_invalid_default_false")
            auto_fix = False
        result["auto_fix_available"] = auto_fix
        result["human_review_status"] = _first_text(
            issue.get("human_review_status"),
            issue.get("human_review"),
            issue.get("review_status"),
            "pending",
        )
    else:
        text = _first_text(issue, "legacy_issue")
        warnings.extend(
            [
                "issue_was_not_object",
                "severity_missing_default_major",
                "bbox_missing_or_invalid_default_full_page",
                "confidence_missing_or_invalid_default_zero",
                "evidence_missing_synthesized_from_legacy_record",
                "auto_fix_available_missing_or_invalid_default_false",
            ]
        )
        result = {
            "key": _slug_key(text),
            "severity": "major",
            "bbox": list(_DEFAULT_BBOX),
            "source": default_source,
            "confidence": 0.0,
            "fix_suggestion": _DEFAULT_FIX,
            "auto_fix_available": False,
            "human_review_status": "pending",
            "description": text,
        }

    evidence = _coerce_evidence(issue, source_file, issue_path, warnings)
    warnings = list(dict.fromkeys(warnings))
    if warnings:
        evidence["normalization_warnings"] = warnings
    result["evidence"] = evidence
    result["normalization"] = {
        "schema": "sw_drawing_studio.normalized_issue.v1",
        "status": "normalized_with_warnings" if warnings else "preserved",
        "warnings": warnings,
        "source_file": source_file,
        "issue_path": issue_path,
    }
    for field in REQUIRED_ISSUE_FIELDS:
        if not _has_value(result.get(field)):
            result[field] = _DEFAULT_FIX if field == "fix_suggestion" else "unknown"
    return result
