"""Build a non-destructive raw visual issue backfill overlay.

The overlay maps every raw schema failure to the normalized replacement record
that can be reviewed before a future raw backfill or full Visual Audit
regeneration. It never edits historical artifacts and is not release evidence.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "sw_drawing_studio.visual_audit_raw_issue_backfill_overlay.v4_4"
RECORD_SCHEMA = "sw_drawing_studio.visual_audit_raw_issue_backfill_overlay_record.v4_4"

DEFAULT_RAW_ISSUE_SCHEMA = REPO_ROOT / "drw_output" / "issue_schema_validation.json"
DEFAULT_NORMALIZED_INDEX = REPO_ROOT / "drw_output" / "visual_audit" / "normalized_issue_index.json"
DEFAULT_OUT_JSONL = REPO_ROOT / "drw_output" / "visual_audit" / "raw_issue_backfill_overlay_v4_4.jsonl"
DEFAULT_OUT_SUMMARY = REPO_ROOT / "drw_output" / "diagnostics" / "visual_audit_raw_issue_backfill_overlay_v4_4.json"
DEFAULT_OUT_MD = REPO_ROOT / "drw_output" / "diagnostics" / "visual_audit_raw_issue_backfill_overlay_v4_4.md"

LOSSY_WARNING_KEYS = {
    "issue_was_not_object",
    "bbox_missing_or_invalid_default_full_page",
    "confidence_missing_or_invalid_default_zero",
    "evidence_missing_synthesized_from_legacy_record",
}


def build_overlay(
    *,
    raw_issue_schema_path: Path = DEFAULT_RAW_ISSUE_SCHEMA,
    normalized_index_path: Path = DEFAULT_NORMALIZED_INDEX,
    out_jsonl: Path | None = None,
    out_summary: Path | None = None,
    out_md: Path | None = None,
) -> dict[str, Any]:
    raw = _read_json(raw_issue_schema_path)
    normalized_index = _read_json(normalized_index_path)

    raw_failures = [item for item in raw.get("failures") or [] if isinstance(item, dict)]
    normalized_issues = [item for item in normalized_index.get("issues") or [] if isinstance(item, dict)]
    normalized_by_key = _normalized_issue_map(normalized_issues)

    missing_replacements: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    warning_counts: Counter[str] = Counter()
    lossy_count = 0

    for index, failure in enumerate(raw_failures):
        source_file = _source_key(failure.get("file"))
        issue_path = str(failure.get("issue_path") or "")
        normalized_issue = normalized_by_key.get((source_file, issue_path))
        if not normalized_issue:
            missing_replacements.append(
                {
                    "file": failure.get("file"),
                    "source_key": source_file,
                    "issue_path": issue_path,
                    "issue_key": failure.get("issue_key"),
                    "missing_fields": failure.get("missing_fields") or [],
                    "invalid_fields": failure.get("invalid_fields") or [],
                }
            )
            continue

        warnings = [str(item) for item in ((normalized_issue.get("normalization") or {}).get("warnings") or [])]
        warning_counts.update(warnings)
        lossy = any(item in LOSSY_WARNING_KEYS for item in warnings)
        if lossy:
            lossy_count += 1
        records.append(
            {
                "schema": RECORD_SCHEMA,
                "overlay_index": len(records),
                "raw_failure_index": index,
                "source_file": source_file,
                "issue_path": issue_path,
                "raw_issue_key": failure.get("issue_key"),
                "raw_missing_fields": failure.get("missing_fields") or [],
                "raw_invalid_fields": failure.get("invalid_fields") or [],
                "normalized_issue": normalized_issue,
                "normalization_warnings": warnings,
                "requires_human_review": bool(lossy),
                "historical_artifact_modified": False,
                "write_back_policy": "review_or_regenerate_before_raw_backfill",
            }
        )

    jsonl_summary = _write_jsonl(out_jsonl, records) if out_jsonl is not None else _jsonl_preview(records)
    raw_pass = raw.get("pass") is True and int(raw.get("noncompliant_issue_count") or 0) == 0
    overlay_ready = bool(raw_failures and not missing_replacements and len(records) == len(raw_failures))
    status = (
        "raw_issue_schema_already_pass"
        if raw_pass
        else "overlay_ready_requires_human_review"
        if overlay_ready
        else "overlay_incomplete"
    )

    payload = {
        "schema": SCHEMA,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "status": status,
        "pass": raw_pass or overlay_ready,
        "release_ready": False,
        "solidworks_runtime_called": False,
        "historical_artifacts_modified": False,
        "in_place_mutation_allowed": False,
        "normalized_supporting_only": True,
        "normalized_cannot_replace_raw": True,
        "raw_schema_replacement_allowed": False,
        "raw_issue_schema_pass": raw_pass,
        "raw_issue_count": int(raw.get("issue_count") or 0),
        "raw_failure_count": len(raw_failures),
        "raw_noncompliant_issue_count": int(raw.get("noncompliant_issue_count") or 0),
        "normalized_issue_count": int(normalized_index.get("issue_count") or 0),
        "overlay_record_count": len(records),
        "missing_replacement_count": len(missing_replacements),
        "lossy_overlay_record_count": lossy_count,
        "requires_human_review_for_lossy_records": lossy_count > 0,
        "normalization_warning_counts": dict(warning_counts.most_common()),
        "lossy_warning_counts": {key: warning_counts.get(key, 0) for key in sorted(LOSSY_WARNING_KEYS)},
        "missing_replacements": missing_replacements[:100],
        "output_jsonl": jsonl_summary,
        "source_artifacts": {
            "raw_issue_schema_validation": str(raw_issue_schema_path),
            "normalized_issue_index": str(normalized_index_path),
        },
        "allowed_next_actions": {
            "use_as_release_pass": False,
            "use_as_raw_schema_replacement": False,
            "modify_historical_artifacts": False,
            "use_as_review_input_for_future_backfill": overlay_ready,
        },
        "next_required_action": _next_required_action(status, lossy_count),
    }

    if out_summary is not None:
        out_summary.parent.mkdir(parents=True, exist_ok=True)
        out_summary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if out_md is not None:
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text(render_markdown(payload), encoding="utf-8")
    return payload


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Visual Audit Raw Issue Backfill Overlay v4.4",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- PASS: `{str(payload.get('pass')).lower()}`",
        "- Release ready: `false`",
        "- Historical artifacts modified: `false`",
        "- Normalized proof is supporting-only: `true`",
        "- Raw schema replacement allowed: `false`",
        f"- Raw failures: `{payload.get('raw_failure_count')}`",
        f"- Overlay records: `{payload.get('overlay_record_count')}`",
        f"- Missing replacements: `{payload.get('missing_replacement_count')}`",
        f"- Lossy records needing review: `{payload.get('lossy_overlay_record_count')}`",
        f"- JSONL SHA256: `{(payload.get('output_jsonl') or {}).get('sha256') or ''}`",
        "",
        "## Next Required Action",
        "",
        str(payload.get("next_required_action") or ""),
        "",
    ]
    return "\n".join(lines)


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            line = json.dumps(record, ensure_ascii=False, sort_keys=True)
            encoded = (line + "\n").encode("utf-8")
            digest.update(encoded)
            handle.write(line + "\n")
    return {
        "path": str(path),
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else 0,
        "line_count": len(records),
        "sha256": digest.hexdigest(),
    }


def _jsonl_preview(records: list[dict[str, Any]]) -> dict[str, Any]:
    digest = hashlib.sha256()
    for record in records:
        digest.update((json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8"))
    return {
        "path": "",
        "exists": False,
        "size_bytes": 0,
        "line_count": len(records),
        "sha256": digest.hexdigest(),
    }


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _normalized_issue_map(issues: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    mapped: dict[tuple[str, str], dict[str, Any]] = {}
    for issue in issues:
        normalization = issue.get("normalization") if isinstance(issue.get("normalization"), dict) else {}
        evidence = issue.get("evidence") if isinstance(issue.get("evidence"), dict) else {}
        source_file = _source_key(normalization.get("source_file") or evidence.get("source_file"))
        issue_path = str(normalization.get("issue_path") or evidence.get("issue_path") or "")
        if source_file and issue_path:
            mapped[(source_file, issue_path)] = issue
    return mapped


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


def _next_required_action(status: str, lossy_count: int) -> str:
    if status == "raw_issue_schema_already_pass":
        return "Raw issue schema already passes; keep the overlay only as an audit trail if needed."
    if status == "overlay_ready_requires_human_review":
        return (
            "Use the JSONL overlay as a review/backfill input only after 006 and the requested six drawings pass. "
            "Back up or regenerate raw artifacts before any write-back; lossy records require human review."
            if lossy_count
            else "Use the JSONL overlay as a review/backfill input only after the product gate allows full Visual Audit."
        )
    return "Fix normalized issue coverage first; some raw schema failures have no traceable normalized replacement."


def _repo_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a v4.4 raw issue backfill JSONL overlay.")
    parser.add_argument("--raw-issue-schema", default=str(DEFAULT_RAW_ISSUE_SCHEMA))
    parser.add_argument("--normalized-index", default=str(DEFAULT_NORMALIZED_INDEX))
    parser.add_argument("--out-jsonl", default=str(DEFAULT_OUT_JSONL))
    parser.add_argument("--out-summary", default=str(DEFAULT_OUT_SUMMARY))
    parser.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    args = parser.parse_args()

    payload = build_overlay(
        raw_issue_schema_path=_repo_path(args.raw_issue_schema),
        normalized_index_path=_repo_path(args.normalized_index),
        out_jsonl=_repo_path(args.out_jsonl),
        out_summary=_repo_path(args.out_summary),
        out_md=_repo_path(args.out_md),
    )
    print(
        json.dumps(
            {
                "status": payload.get("status"),
                "pass": payload.get("pass"),
                "raw_failure_count": payload.get("raw_failure_count"),
                "overlay_record_count": payload.get("overlay_record_count"),
                "missing_replacement_count": payload.get("missing_replacement_count"),
                "lossy_overlay_record_count": payload.get("lossy_overlay_record_count"),
                "out_summary": str(_repo_path(args.out_summary)),
                "out_jsonl": str(_repo_path(args.out_jsonl)),
            },
            ensure_ascii=False,
        )
    )
    return 0 if payload.get("pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
