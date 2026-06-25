from __future__ import annotations

import argparse
from collections import Counter
import json
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "sw_drawing_studio.visual_audit_raw_issue_repair_plan.v4_4"

DEFAULT_RAW_ISSUE_SCHEMA = REPO_ROOT / "drw_output" / "issue_schema_validation.json"
DEFAULT_NORMALIZED_ISSUE_SCHEMA = REPO_ROOT / "drw_output" / "issue_schema_validation_normalized.json"
DEFAULT_NORMALIZED_INDEX = REPO_ROOT / "drw_output" / "visual_audit" / "normalized_issue_index.json"
DEFAULT_OUT_JSON = REPO_ROOT / "drw_output" / "diagnostics" / "visual_audit_raw_issue_repair_plan_v4_4.json"
DEFAULT_OUT_MD = REPO_ROOT / "drw_output" / "diagnostics" / "visual_audit_raw_issue_repair_plan_v4_4.md"

LOSSY_WARNING_KEYS = {
    "issue_was_not_object",
    "bbox_missing_or_invalid_default_full_page",
    "confidence_missing_or_invalid_default_zero",
    "evidence_missing_synthesized_from_legacy_record",
}


def build_repair_plan(
    *,
    raw_issue_schema_path: Path = DEFAULT_RAW_ISSUE_SCHEMA,
    normalized_issue_schema_path: Path = DEFAULT_NORMALIZED_ISSUE_SCHEMA,
    normalized_index_path: Path = DEFAULT_NORMALIZED_INDEX,
    out_json: Path | None = None,
    out_md: Path | None = None,
) -> dict[str, Any]:
    raw = _read_json(raw_issue_schema_path)
    normalized_validation = _read_json(normalized_issue_schema_path)
    normalized_index = _read_json(normalized_index_path)

    raw_failures = [item for item in raw.get("failures") or [] if isinstance(item, dict)]
    normalized_issues = [item for item in normalized_index.get("issues") or [] if isinstance(item, dict)]
    normalized_keys = _normalized_issue_keys(normalized_issues)

    missing_replacements: list[dict[str, Any]] = []
    source_counts: Counter[str] = Counter()
    missing_field_counts: Counter[str] = Counter()
    invalid_field_counts: Counter[str] = Counter()
    for failure in raw_failures:
        source_file = _source_key(failure.get("file"))
        issue_path = str(failure.get("issue_path") or "")
        key = (source_file, issue_path)
        source_counts[source_file] += 1
        missing_field_counts.update(str(item) for item in failure.get("missing_fields") or [])
        invalid_field_counts.update(str(item) for item in failure.get("invalid_fields") or [])
        if key not in normalized_keys:
            missing_replacements.append(
                {
                    "file": failure.get("file"),
                    "issue_path": issue_path,
                    "issue_key": failure.get("issue_key"),
                    "missing_fields": failure.get("missing_fields") or [],
                    "invalid_fields": failure.get("invalid_fields") or [],
                }
            )

    warning_counts = Counter()
    lossy_issue_count = 0
    for issue in normalized_issues:
        warnings = [str(item) for item in ((issue.get("normalization") or {}).get("warnings") or [])]
        warning_counts.update(warnings)
        if any(item in LOSSY_WARNING_KEYS for item in warnings):
            lossy_issue_count += 1

    normalized_validation_pass = (
        normalized_validation.get("pass") is True
        and int(normalized_validation.get("noncompliant_issue_count") or 0) == 0
    )
    normalized_index_covers_raw_issue_count = int(normalized_index.get("issue_count") or 0) == int(raw.get("issue_count") or 0)
    normalized_records_for_all_raw_failures = not missing_replacements
    repair_overlay_ready = bool(
        raw_failures
        and normalized_validation_pass
        and normalized_index_covers_raw_issue_count
        and normalized_records_for_all_raw_failures
    )
    raw_pass = raw.get("pass") is True and int(raw.get("noncompliant_issue_count") or 0) == 0
    status = (
        "raw_issue_schema_already_pass"
        if raw_pass
        else "repair_overlay_ready_requires_raw_backfill"
        if repair_overlay_ready
        else "repair_overlay_incomplete"
    )

    payload = {
        "schema": SCHEMA,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "status": status,
        "pass": repair_overlay_ready or raw_pass,
        "release_ready": False,
        "solidworks_runtime_called": False,
        "historical_artifacts_modified": False,
        "in_place_mutation_allowed": False,
        "normalized_supporting_only": True,
        "normalized_cannot_replace_raw": True,
        "raw_artifacts_remain_source_of_truth": True,
        "raw_issue_schema_pass": raw_pass,
        "raw_issue_count": int(raw.get("issue_count") or 0),
        "raw_noncompliant_issue_count": int(raw.get("noncompliant_issue_count") or 0),
        "raw_failure_count": len(raw_failures),
        "normalized_issue_count": int(normalized_index.get("issue_count") or 0),
        "normalized_validation_pass": normalized_validation_pass,
        "normalized_index_covers_raw_issue_count": normalized_index_covers_raw_issue_count,
        "normalized_records_for_all_raw_failures": normalized_records_for_all_raw_failures,
        "missing_replacement_count": len(missing_replacements),
        "lossy_normalized_issue_count": lossy_issue_count,
        "requires_human_review_for_lossy_records": lossy_issue_count > 0,
        "normalization_warning_counts": dict(warning_counts.most_common()),
        "lossy_warning_counts": {key: warning_counts.get(key, 0) for key in sorted(LOSSY_WARNING_KEYS)},
        "raw_missing_field_counts": dict(missing_field_counts.most_common()),
        "raw_invalid_field_counts": dict(invalid_field_counts.most_common()),
        "top_raw_failure_sources": [
            {"file": file, "failure_count": count}
            for file, count in source_counts.most_common(20)
        ],
        "missing_replacements": missing_replacements[:100],
        "source_artifacts": {
            "raw_issue_schema_validation": str(raw_issue_schema_path),
            "normalized_issue_schema_validation": str(normalized_issue_schema_path),
            "normalized_issue_index": str(normalized_index_path),
        },
        "allowed_next_actions": {
            "use_as_release_pass": False,
            "use_as_raw_schema_replacement": False,
            "write_back_after_user_approval_and_backup": repair_overlay_ready and not raw_pass,
            "regenerate_full_visual_audit_after_requested_six_pass": True,
        },
        "next_required_action": _next_required_action(status, lossy_issue_count),
    }

    if out_json is not None:
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if out_md is not None:
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text(render_markdown(payload), encoding="utf-8")
    return payload


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Visual Audit Raw Issue Repair Plan v4.4",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- PASS: `{str(payload.get('pass')).lower()}`",
        "- Release ready: `false`",
        "- Historical artifacts modified: `false`",
        "- Normalized proof is supporting-only: `true`",
        "- Normalized proof cannot replace raw: `true`",
        f"- Raw issues: `{payload.get('raw_issue_count')}`",
        f"- Raw noncompliant issues: `{payload.get('raw_noncompliant_issue_count')}`",
        f"- Missing normalized replacements: `{payload.get('missing_replacement_count')}`",
        f"- Lossy normalized issues needing human review: `{payload.get('lossy_normalized_issue_count')}`",
        "",
        "## Top Raw Failure Sources",
        "",
    ]
    for item in payload.get("top_raw_failure_sources") or []:
        lines.append(f"- `{item.get('failure_count')}` `{item.get('file')}`")
    lines.extend(["", "## Next Required Action", "", str(payload.get("next_required_action") or ""), ""])
    return "\n".join(lines)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _normalized_issue_keys(issues: list[dict[str, Any]]) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for issue in issues:
        normalization = issue.get("normalization") if isinstance(issue.get("normalization"), dict) else {}
        source_file = _source_key(normalization.get("source_file") or (issue.get("evidence") or {}).get("source_file"))
        issue_path = str(normalization.get("issue_path") or (issue.get("evidence") or {}).get("issue_path") or "")
        if source_file and issue_path:
            keys.add((source_file, issue_path))
    return keys


def _source_key(value: Any) -> str:
    text = str(value or "").replace("\\", "/")
    if not text:
        return ""
    try:
        path = Path(text)
        if path.is_absolute():
            text = str(path.resolve().relative_to(REPO_ROOT)).replace("\\", "/")
    except Exception:
        pass
    marker = "drw_output/"
    lowered = text.lower()
    if marker in lowered:
        text = text[lowered.index(marker) :]
    return text.strip("/")


def _next_required_action(status: str, lossy_issue_count: int) -> str:
    if status == "raw_issue_schema_already_pass":
        return "Raw issue schema already passes; continue with final Visual Audit sequencing."
    if status == "repair_overlay_ready_requires_raw_backfill":
        return (
            "Normalized replacement coverage exists for every raw failure, but it is supporting-only evidence. "
            "After the requested UI-gated drawing sequence allows full Visual Audit, back up or regenerate the raw "
            "artifacts and rerun raw issue schema validation; records with lossy defaults require human review."
            if lossy_issue_count
            else "Normalized replacement coverage exists for every raw failure; run an approved raw backfill or regeneration pass before release."
        )
    return "Fix normalized issue index coverage first; some raw failures do not have traceable normalized replacement records."


def _repo_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a v4.4 raw visual issue schema repair readiness plan.")
    parser.add_argument("--raw-issue-schema", default=str(DEFAULT_RAW_ISSUE_SCHEMA))
    parser.add_argument("--normalized-issue-schema", default=str(DEFAULT_NORMALIZED_ISSUE_SCHEMA))
    parser.add_argument("--normalized-index", default=str(DEFAULT_NORMALIZED_INDEX))
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    parser.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    args = parser.parse_args()
    payload = build_repair_plan(
        raw_issue_schema_path=_repo_path(args.raw_issue_schema),
        normalized_issue_schema_path=_repo_path(args.normalized_issue_schema),
        normalized_index_path=_repo_path(args.normalized_index),
        out_json=_repo_path(args.out_json),
        out_md=_repo_path(args.out_md),
    )
    print(
        json.dumps(
            {
                "status": payload.get("status"),
                "pass": payload.get("pass"),
                "raw_noncompliant_issue_count": payload.get("raw_noncompliant_issue_count"),
                "missing_replacement_count": payload.get("missing_replacement_count"),
                "lossy_normalized_issue_count": payload.get("lossy_normalized_issue_count"),
                "out_json": str(_repo_path(args.out_json)),
            },
            ensure_ascii=False,
        )
    )
    return 0 if payload.get("pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
