from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "sw_drawing_studio.visual_audit_schema_gap.v4_4"

DEFAULT_RAW_ISSUE_SCHEMA = REPO_ROOT / "drw_output" / "issue_schema_validation.json"
DEFAULT_NORMALIZED_ISSUE_SCHEMA = REPO_ROOT / "drw_output" / "issue_schema_validation_normalized.json"
DEFAULT_PRODUCT_GATE = REPO_ROOT / "drw_output" / "diagnostics" / "product_evidence_gate_v4_4.json"
DEFAULT_VISUAL_AUDIT_INDEX = REPO_ROOT / "drw_output" / "visual_audit_index.json"
DEFAULT_VISUAL_AUDIT_REPORT = REPO_ROOT / "drw_output" / "visual_audit_report_v3_0.xlsx"
DEFAULT_RAW_ISSUE_REPAIR_PLAN = REPO_ROOT / "drw_output" / "diagnostics" / "visual_audit_raw_issue_repair_plan_v4_4.json"
DEFAULT_RAW_ISSUE_BACKFILL_OVERLAY = REPO_ROOT / "drw_output" / "diagnostics" / "visual_audit_raw_issue_backfill_overlay_v4_4.json"
DEFAULT_OUT_JSON = REPO_ROOT / "drw_output" / "diagnostics" / "visual_audit_schema_gap_v4_4.json"
DEFAULT_OUT_MD = REPO_ROOT / "drw_output" / "diagnostics" / "visual_audit_schema_gap_v4_4.md"


def build_visual_audit_schema_gap(
    *,
    raw_issue_schema_path: Path = DEFAULT_RAW_ISSUE_SCHEMA,
    normalized_issue_schema_path: Path = DEFAULT_NORMALIZED_ISSUE_SCHEMA,
    product_gate_path: Path = DEFAULT_PRODUCT_GATE,
    visual_audit_index_path: Path = DEFAULT_VISUAL_AUDIT_INDEX,
    visual_audit_report_path: Path = DEFAULT_VISUAL_AUDIT_REPORT,
    raw_issue_repair_plan_path: Path | None = None,
    raw_issue_backfill_overlay_path: Path | None = None,
    out_json: Path | None = None,
    out_md: Path | None = None,
) -> dict[str, Any]:
    raw = _read_json(raw_issue_schema_path)
    normalized = _read_json(normalized_issue_schema_path)
    product_gate = _read_json(product_gate_path)
    repair_plan = _read_json(raw_issue_repair_plan_path) if raw_issue_repair_plan_path else {}
    backfill_overlay = _read_json(raw_issue_backfill_overlay_path) if raw_issue_backfill_overlay_path else {}

    raw_exists = raw_issue_schema_path.exists() and raw_issue_schema_path.is_file()
    normalized_exists = normalized_issue_schema_path.exists() and normalized_issue_schema_path.is_file()
    index_exists = visual_audit_index_path.exists() and visual_audit_index_path.is_file()
    report_exists = visual_audit_report_path.exists() and visual_audit_report_path.is_file()
    repair_plan_exists = bool(raw_issue_repair_plan_path and raw_issue_repair_plan_path.exists() and raw_issue_repair_plan_path.is_file())
    backfill_overlay_exists = bool(
        raw_issue_backfill_overlay_path
        and raw_issue_backfill_overlay_path.exists()
        and raw_issue_backfill_overlay_path.is_file()
    )
    allowed_actions = product_gate.get("allowed_actions") if isinstance(product_gate.get("allowed_actions"), dict) else {}
    full_scope_allowed = allowed_actions.get("visual_audit_full_scope_allowed") is True

    checks: list[dict[str, Any]] = []
    _add_check(
        checks,
        "raw_issue_schema_report_present",
        raw_exists,
        "Raw historical visual issue schema validation report must exist.",
        {"path": str(raw_issue_schema_path)},
    )
    _add_check(
        checks,
        "raw_issue_schema_pass",
        raw_exists and raw.get("pass") is True and int(raw.get("noncompliant_issue_count") or 0) == 0,
        "Raw historical visual issues must satisfy the final required issue schema.",
        _issue_schema_summary(raw_issue_schema_path, raw),
    )
    _add_check(
        checks,
        "normalized_issue_schema_report_present",
        normalized_exists,
        "Normalized issue schema validation report must exist as supporting evidence.",
        {"path": str(normalized_issue_schema_path)},
    )
    _add_check(
        checks,
        "normalized_issue_schema_pass",
        normalized_exists
        and normalized.get("pass") is True
        and int(normalized.get("noncompliant_issue_count") or 0) == 0,
        "Normalized issue schema proof must pass, but it remains supporting-only evidence.",
        _issue_schema_summary(normalized_issue_schema_path, normalized),
    )
    _add_check(
        checks,
        "final_visual_audit_report_present",
        report_exists and visual_audit_report_path.stat().st_size > 0,
        "Final visual_audit_report_v3_0.xlsx must exist before release evidence can pass.",
        _file_summary(visual_audit_report_path),
    )
    _add_check(
        checks,
        "visual_audit_index_present",
        index_exists and visual_audit_index_path.stat().st_size > 0,
        "Visual Audit index must exist as full-scope inventory evidence.",
        _file_summary(visual_audit_index_path, extra=_visual_audit_index_summary(visual_audit_index_path)),
    )
    _add_check(
        checks,
        "visual_audit_full_scope_allowed",
        full_scope_allowed,
        "Full-scope Visual Audit must wait until the product gate allows it after the requested six drawings pass.",
        {
            "product_gate_path": str(product_gate_path),
            "product_gate_status": product_gate.get("status"),
            "product_gate_pass": product_gate.get("pass"),
            "visual_audit_full_scope_allowed": full_scope_allowed,
            "product_gate_blocking_issue_keys": product_gate.get("blocking_issue_keys") or [],
        },
    )

    failed = [item for item in checks if item["status"] != "pass"]
    status = _status_from_checks(checks)
    payload = {
        "schema": SCHEMA,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "status": status,
        "pass": not failed,
        "release_ready": False,
        "visual_audit_schema_evidence_pass": not failed,
        "api_only_acceptance_allowed": False,
        "application_ui_screenshot_is_final_gate_for_requested_drawings": True,
        "solidworks_runtime_called": False,
        "normalized_supporting_only": True,
        "normalized_cannot_replace_raw": True,
        "raw_issue_repair_plan_present": repair_plan_exists,
        "raw_issue_repair_plan_ready": repair_plan.get("pass") is True,
        "raw_issue_repair_plan_cannot_replace_raw": True,
        "raw_issue_backfill_overlay_present": backfill_overlay_exists,
        "raw_issue_backfill_overlay_ready": backfill_overlay.get("pass") is True,
        "raw_issue_backfill_overlay_cannot_replace_raw": True,
        "raw_issue_schema_pass": raw.get("pass") is True and int(raw.get("noncompliant_issue_count") or 0) == 0,
        "normalized_issue_schema_pass": normalized.get("pass") is True
        and int(normalized.get("noncompliant_issue_count") or 0) == 0,
        "raw_noncompliant_issue_count": int(raw.get("noncompliant_issue_count") or 0),
        "normalized_noncompliant_issue_count": int(normalized.get("noncompliant_issue_count") or 0),
        "visual_audit_report_final_present": report_exists,
        "visual_audit_index_present": index_exists,
        "visual_audit_full_scope_allowed_now": full_scope_allowed,
        "source_artifacts": {
            "raw_issue_schema_validation": str(raw_issue_schema_path),
            "normalized_issue_schema_validation": str(normalized_issue_schema_path),
            "product_evidence_gate": str(product_gate_path),
            "visual_audit_index": str(visual_audit_index_path),
            "visual_audit_report": str(visual_audit_report_path),
            "raw_issue_repair_plan": str(raw_issue_repair_plan_path) if raw_issue_repair_plan_path else "",
            "raw_issue_backfill_overlay": str(raw_issue_backfill_overlay_path) if raw_issue_backfill_overlay_path else "",
        },
        "raw_issue_schema_summary": _issue_schema_summary(raw_issue_schema_path, raw),
        "normalized_issue_schema_summary": _issue_schema_summary(normalized_issue_schema_path, normalized),
        "raw_issue_repair_plan_summary": _raw_issue_repair_plan_summary(raw_issue_repair_plan_path, repair_plan),
        "raw_issue_backfill_overlay_summary": _raw_issue_backfill_overlay_summary(
            raw_issue_backfill_overlay_path,
            backfill_overlay,
        ),
        "checks": checks,
        "blocking_issue_keys": [item["key"] for item in failed],
        "next_required_action": _next_required_action(status),
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
        "# Visual Audit Schema Gap v4.4",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- PASS: `{str(payload.get('pass')).lower()}`",
        "- Release ready: `false`",
        "- Normalized schema proof is supporting-only: `true`",
        "- Normalized proof cannot replace raw historical issue compliance: `true`",
        f"- Raw issue repair plan present: `{str(payload.get('raw_issue_repair_plan_present')).lower()}`",
        f"- Raw issue repair plan can replace raw: `{str(not payload.get('raw_issue_repair_plan_cannot_replace_raw')).lower()}`",
        f"- Raw issue backfill overlay present: `{str(payload.get('raw_issue_backfill_overlay_present')).lower()}`",
        f"- Raw issue backfill overlay can replace raw: `{str(not payload.get('raw_issue_backfill_overlay_cannot_replace_raw')).lower()}`",
        f"- Raw noncompliant issues: `{payload.get('raw_noncompliant_issue_count')}`",
        f"- Final Visual Audit report present: `{str(payload.get('visual_audit_report_final_present')).lower()}`",
        f"- Full-scope Visual Audit allowed now: `{str(payload.get('visual_audit_full_scope_allowed_now')).lower()}`",
        "",
        "## Raw Issue Schema",
        "",
    ]
    raw = payload.get("raw_issue_schema_summary") or {}
    lines.extend(
        [
            f"- Status: `{raw.get('status')}`",
            f"- PASS: `{str(raw.get('pass')).lower()}`",
            f"- Issue count: `{raw.get('issue_count')}`",
            f"- Noncompliant issue count: `{raw.get('noncompliant_issue_count')}`",
            f"- Failure buckets: `{', '.join(raw.get('failure_bucket') or []) or 'none'}`",
            "",
            "## Checks",
            "",
        ]
    )
    for item in payload.get("checks") or []:
        lines.append(f"- `{item.get('status')}` `{item.get('key')}`: {item.get('message')}")
    lines.extend(["", "## Blocking Issues", ""])
    keys = payload.get("blocking_issue_keys") or []
    lines.extend([f"- `{key}`" for key in keys] or ["- None"])
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


def _add_check(
    checks: list[dict[str, Any]],
    key: str,
    passed: bool,
    message: str,
    details: dict[str, Any] | None = None,
) -> None:
    checks.append({
        "key": key,
        "status": "pass" if passed else "fail",
        "message": message,
        "details": details or {},
    })


def _status_from_checks(checks: list[dict[str, Any]]) -> str:
    failed_keys = {item["key"] for item in checks if item.get("status") != "pass"}
    if "raw_issue_schema_report_present" in failed_keys:
        return "blocked_by_missing_raw_issue_schema"
    if "raw_issue_schema_pass" in failed_keys:
        return "raw_issue_schema_noncompliant"
    if "final_visual_audit_report_present" in failed_keys:
        return "blocked_by_missing_final_visual_audit_report"
    if "normalized_issue_schema_report_present" in failed_keys or "normalized_issue_schema_pass" in failed_keys:
        return "normalized_issue_schema_noncompliant"
    if "visual_audit_index_present" in failed_keys:
        return "blocked_by_missing_visual_audit_index"
    if "visual_audit_full_scope_allowed" in failed_keys:
        return "blocked_by_validation_sequence"
    return "pass"


def _issue_schema_summary(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": str(path),
        "exists": path.exists() and path.is_file(),
        "schema": payload.get("schema"),
        "generated_at": payload.get("generated_at"),
        "status": payload.get("status"),
        "pass": payload.get("pass"),
        "issue_count": payload.get("issue_count"),
        "noncompliant_issue_count": payload.get("noncompliant_issue_count"),
        "failure_bucket": payload.get("failure_bucket") or [],
        "missing_field_counts_top": _top_mapping(payload.get("missing_field_counts")),
        "invalid_field_counts_top": _top_mapping(payload.get("invalid_field_counts")),
        "top_failure_files": _top_list(payload.get("top_failure_files")),
        "fix_suggestions": _top_list(payload.get("fix_suggestions"), limit=5),
    }


def _file_summary(path: Path, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    exists = path.exists() and path.is_file()
    payload = {
        "path": str(path),
        "exists": exists,
        "size_bytes": path.stat().st_size if exists else 0,
    }
    if extra:
        payload.update(extra)
    return payload


def _visual_audit_index_summary(path: Path) -> dict[str, Any]:
    payload = _read_json(path)
    return {
        "schema": payload.get("schema"),
        "generated_at": payload.get("generated_at"),
        "total_files": payload.get("total_files"),
        "total_bases": payload.get("total_bases"),
    }


def _raw_issue_repair_plan_summary(path: Path | None, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": str(path or ""),
        "exists": bool(path and path.exists() and path.is_file()),
        "schema": payload.get("schema"),
        "generated_at": payload.get("generated_at"),
        "status": payload.get("status"),
        "pass": payload.get("pass"),
        "release_ready": payload.get("release_ready"),
        "raw_noncompliant_issue_count": payload.get("raw_noncompliant_issue_count"),
        "missing_replacement_count": payload.get("missing_replacement_count"),
        "lossy_normalized_issue_count": payload.get("lossy_normalized_issue_count"),
        "normalized_cannot_replace_raw": payload.get("normalized_cannot_replace_raw"),
        "historical_artifacts_modified": payload.get("historical_artifacts_modified"),
    }


def _raw_issue_backfill_overlay_summary(path: Path | None, payload: dict[str, Any]) -> dict[str, Any]:
    output_jsonl = payload.get("output_jsonl") if isinstance(payload.get("output_jsonl"), dict) else {}
    return {
        "path": str(path or ""),
        "exists": bool(path and path.exists() and path.is_file()),
        "schema": payload.get("schema"),
        "generated_at": payload.get("generated_at"),
        "status": payload.get("status"),
        "pass": payload.get("pass"),
        "release_ready": payload.get("release_ready"),
        "raw_failure_count": payload.get("raw_failure_count"),
        "overlay_record_count": payload.get("overlay_record_count"),
        "missing_replacement_count": payload.get("missing_replacement_count"),
        "lossy_overlay_record_count": payload.get("lossy_overlay_record_count"),
        "normalized_cannot_replace_raw": payload.get("normalized_cannot_replace_raw"),
        "historical_artifacts_modified": payload.get("historical_artifacts_modified"),
        "jsonl_line_count": output_jsonl.get("line_count"),
        "jsonl_sha256": output_jsonl.get("sha256"),
    }


def _top_mapping(value: Any, limit: int = 10) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return dict(list(value.items())[:limit])


def _top_list(value: Any, limit: int = 10) -> list[Any]:
    if not isinstance(value, list):
        return []
    return value[:limit]


def _next_required_action(status: str) -> str:
    if status == "raw_issue_schema_noncompliant":
        return (
            "Do not treat normalized issue schema output as release evidence. After 006 and the requested six "
            "drawings pass application UI screenshot review, rerun full-scope Visual Audit and raw schema validation "
            "so historical visual issues are regenerated or corrected with the required fields."
        )
    if status == "blocked_by_missing_final_visual_audit_report":
        return "Generate the final drw_output/visual_audit_report_v3_0.xlsx after full-scope Visual Audit is allowed."
    if status == "blocked_by_validation_sequence":
        return (
            "Keep full-scope Visual Audit blocked until the requested six drawings pass application UI screenshot "
            "review and the product gate allows the next stage."
        )
    if status == "pass":
        return "Visual Audit schema evidence is complete; continue through the remaining product evidence gates."
    return "Restore or regenerate the missing Visual Audit/schema evidence, then rebuild this diagnostic report."


def _repo_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v4.4 Visual Audit issue-schema gap report.")
    parser.add_argument("--raw-issue-schema", default=str(DEFAULT_RAW_ISSUE_SCHEMA))
    parser.add_argument("--normalized-issue-schema", default=str(DEFAULT_NORMALIZED_ISSUE_SCHEMA))
    parser.add_argument("--product-gate", default=str(DEFAULT_PRODUCT_GATE))
    parser.add_argument("--visual-audit-index", default=str(DEFAULT_VISUAL_AUDIT_INDEX))
    parser.add_argument("--visual-audit-report", default=str(DEFAULT_VISUAL_AUDIT_REPORT))
    parser.add_argument("--raw-issue-repair-plan", default=str(DEFAULT_RAW_ISSUE_REPAIR_PLAN))
    parser.add_argument("--raw-issue-backfill-overlay", default=str(DEFAULT_RAW_ISSUE_BACKFILL_OVERLAY))
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    parser.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    args = parser.parse_args()
    payload = build_visual_audit_schema_gap(
        raw_issue_schema_path=_repo_path(args.raw_issue_schema),
        normalized_issue_schema_path=_repo_path(args.normalized_issue_schema),
        product_gate_path=_repo_path(args.product_gate),
        visual_audit_index_path=_repo_path(args.visual_audit_index),
        visual_audit_report_path=_repo_path(args.visual_audit_report),
        raw_issue_repair_plan_path=_repo_path(args.raw_issue_repair_plan),
        raw_issue_backfill_overlay_path=_repo_path(args.raw_issue_backfill_overlay),
        out_json=_repo_path(args.out_json),
        out_md=_repo_path(args.out_md),
    )
    print(json.dumps({
        "status": payload.get("status"),
        "pass": payload.get("pass"),
        "raw_noncompliant_issue_count": payload.get("raw_noncompliant_issue_count"),
        "blocking_issue_keys": payload.get("blocking_issue_keys"),
        "out_json": str(_repo_path(args.out_json)),
        "out_md": str(_repo_path(args.out_md)),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
