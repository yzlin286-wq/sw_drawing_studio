"""Build the v4.4 staged batch sequence gate from existing evidence files.

This tool is deliberately file-only. It summarizes whether the required staged
CAD sequence has evidence strong enough to unlock full-scope Visual Audit and
full_129; it does not launch CAD, workers, OCR, or visual-audit batches.
"""
from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "sw_drawing_studio.staged_batch_sequence_gate.v4_4"
REQUIRED_SEQUENCE = ["024_040", "core_12", "LB26001_36", "medium_30"]
DEFAULT_OUT_JSON = REPO_ROOT / "drw_output" / "diagnostics" / "staged_batch_sequence_gate_v4_4.json"
DEFAULT_OUT_MD = REPO_ROOT / "drw_output" / "diagnostics" / "staged_batch_sequence_gate_v4_4.md"
DEFAULT_STAGE_ROOT = REPO_ROOT / "drw_output" / "staged_validation"


def build_staged_batch_sequence_gate(
    *,
    stage_summaries: dict[str, Path] | None = None,
    stage_root: Path = DEFAULT_STAGE_ROOT,
    out_json: Path | None = None,
    out_md: Path | None = None,
) -> dict[str, Any]:
    stage_summaries = stage_summaries or {}
    stages = [
        _stage_record(stage, stage_summaries.get(stage) or _latest_summary_path(stage_root, stage))
        for stage in REQUIRED_SEQUENCE
    ]
    stage_pass_map = {str(item.get("stage")): bool(item.get("pass")) for item in stages}
    sequence_present = [str(item.get("stage")) for item in stages if item.get("summary_exists")]
    ordered_pass = _ordered_sequence_present(sequence_present)
    all_stages_pass = ordered_pass and all(stage_pass_map.get(stage) is True for stage in REQUIRED_SEQUENCE)
    blocking_issue_keys = _blocking_issue_keys(stages, ordered_pass)
    payload = {
        "schema": SCHEMA,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "status": "pass" if all_stages_pass else "pending",
        "pass": all_stages_pass,
        "required_sequence": REQUIRED_SEQUENCE,
        "sequence": [str(item.get("stage")) for item in stages if item.get("summary_exists")],
        "observed_sequence": sequence_present,
        "stages": stages,
        "solidworks_global_lock_required": True,
        "job_runtime_facade_required": True,
        "qprocess_worker_required": True,
        "application_ui_screenshot_is_final_gate": True,
        "api_only_acceptance_allowed": False,
        "visual_audit_allowed_after_medium_30": all_stages_pass,
        "full_129_allowed_after_visual_audit": all_stages_pass,
        "blocking_issue_keys": blocking_issue_keys,
        "next_required_action": _next_required_action(stages, ordered_pass),
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
        "# Staged Batch Sequence Gate v4.4",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- PASS: `{str(payload.get('pass')).lower()}`",
        f"- Required sequence: `{' -> '.join(payload.get('required_sequence') or [])}`",
        f"- Observed sequence: `{' -> '.join(payload.get('observed_sequence') or [])}`",
        f"- Visual Audit allowed after medium_30: `{str(payload.get('visual_audit_allowed_after_medium_30')).lower()}`",
        f"- full_129 allowed after Visual Audit: `{str(payload.get('full_129_allowed_after_visual_audit')).lower()}`",
        "",
        "## Stages",
        "",
    ]
    for stage in payload.get("stages") or []:
        lines.append(
            f"- `{stage.get('stage')}`: pass=`{str(stage.get('pass')).lower()}`, "
            f"status=`{stage.get('status')}`, summary=`{stage.get('summary_path')}`"
        )
        mismatch = stage.get("mismatch_keys") or []
        if mismatch:
            lines.append(f"  - Missing/failed: `{', '.join(mismatch)}`")
    lines.extend(["", "## Blocking Issues", ""])
    issues = payload.get("blocking_issue_keys") or []
    lines.extend([f"- `{item}`" for item in issues] or ["- None"])
    lines.extend(["", "## Next Required Action", "", str(payload.get("next_required_action") or ""), ""])
    return "\n".join(lines)


def _stage_record(stage: str, summary_path: Path | None) -> dict[str, Any]:
    summary = _read_json(summary_path) if summary_path else {}
    summary_exists = bool(summary_path and summary_path.exists() and summary_path.is_file())
    cases = [item for item in summary.get("cases") or [] if isinstance(item, dict)]
    total = _int_value(summary.get("total"))
    processed = _int_value(summary.get("processed"), len(cases))
    deliverable_count = _int_value(summary.get("deliverable_count"))
    required_deliverable_count = _int_value(
        summary.get("required_deliverable_count"),
        math.ceil(total * _float_value(summary.get("deliverable_target_ratio"), 1.0)) if total else 0,
    )
    deliverable_target_met = bool(total > 0 and deliverable_count >= required_deliverable_count)
    execution_completed = bool(summary.get("execution_completed") is True or (total > 0 and processed >= total))
    summary_pass = _pass_flag(summary)
    case_artifacts = _case_artifact_summary(cases)
    contract = {
        "summary_exists": summary_exists,
        "summary_stage_matches": _stage_matches(stage, str(summary.get("stage") or "")),
        "summary_pass": summary_pass,
        "execution_completed": execution_completed,
        "deliverable_target_met": deliverable_target_met,
        "solidworks_lock_owned": _stage_truthy(summary, cases, [
            "solidworks_lock_owned",
            "used_solidworks_global_lock",
            "used_global_solidworks_lock",
            "stage_solidworks_lock_owned",
        ]),
        "job_runtime_facade_proof": _stage_truthy(summary, cases, [
            "used_job_runtime_facade",
            "job_runtime_facade",
            "facade_routed",
            "stage_job_runtime_facade_proof",
        ]) or case_artifacts["facade_submitted_all"],
        "qprocess_worker_proof": _stage_truthy(summary, cases, [
            "used_qprocess",
            "qprocess_worker",
            "worker_qprocess",
            "stage_qprocess_worker_proof",
        ]) or case_artifacts["worker_jsonl_events_all"],
        "application_ui_screenshot_evidence": _stage_truthy(summary, cases, [
            "application_ui_screenshot_evidence",
            "application_ui_review_pass",
            "ui_screenshot_review_pass",
            "manual_visual_judgement_pass",
            "visual_acceptance_pass",
            "stage_application_ui_screenshot_evidence",
        ]),
        "api_only_acceptance_disallowed": (
            summary.get("api_only_acceptance_allowed") is False
            or (bool(cases) and all(case.get("api_only_acceptance_allowed") is False for case in cases))
        ),
        "artifact_contract_present": bool(
            "artifact_contract_pass" in summary
            or "stage_artifact_contract_pass" in summary
            or cases
        ),
        "artifact_contract_pass": _truthy(summary.get("artifact_contract_pass"))
        or _truthy(summary.get("stage_artifact_contract_pass"))
        or case_artifacts["required_artifacts_all"],
    }
    mismatch_keys = [key for key, value in contract.items() if value is not True]
    return {
        "stage": stage,
        "summary_path": str(summary_path or ""),
        "summary_exists": summary_exists,
        "generated_at": summary.get("generated_at"),
        "status": summary.get("status"),
        "pass": not mismatch_keys,
        "summary_pass": summary_pass,
        "total": total,
        "processed": processed,
        "deliverable_count": deliverable_count,
        "required_deliverable_count": required_deliverable_count,
        "run_id": _first_nonempty_case_value(cases, "run_id"),
        "run_dir": _first_nonempty_case_value(cases, "run_dir"),
        "case_artifact_summary": case_artifacts,
        "used_job_runtime_facade": contract["job_runtime_facade_proof"],
        "used_qprocess": contract["qprocess_worker_proof"],
        **contract,
        "mismatch_keys": mismatch_keys,
    }


def _case_artifact_summary(cases: list[dict[str, Any]]) -> dict[str, Any]:
    if not cases:
        return {
            "case_count": 0,
            "required_artifacts_all": False,
            "facade_submitted_all": False,
            "worker_jsonl_events_all": False,
        }
    artifact_keys = ["manifest", "job_event_log"]
    required_artifact_results: list[bool] = []
    facade_results: list[bool] = []
    worker_results: list[bool] = []
    for case in cases:
        cad_report = _read_json(_path_from_value(case.get("cad_report")))
        checks = _checks_map(cad_report.get("checks"))
        artifacts = cad_report.get("artifacts") or {}
        required_artifact_results.append(
            all(
                _check_pass(checks, f"artifact_{key}")
                or _artifact_exists(artifacts.get(key))
                for key in artifact_keys
            )
        )
        facade_results.append(_check_pass(checks, "facade_submitted") or _truthy(cad_report.get("used_job_runtime_facade")))
        worker_results.append(_check_pass(checks, "worker_jsonl_events") or _artifact_exists(artifacts.get("job_event_log")))
    return {
        "case_count": len(cases),
        "required_artifacts_all": all(required_artifact_results),
        "facade_submitted_all": all(facade_results),
        "worker_jsonl_events_all": all(worker_results),
        "required_artifacts_pass_count": sum(1 for item in required_artifact_results if item),
        "facade_submitted_pass_count": sum(1 for item in facade_results if item),
        "worker_jsonl_events_pass_count": sum(1 for item in worker_results if item),
    }


def _latest_summary_path(stage_root: Path, stage: str) -> Path | None:
    root = stage_root / stage
    if not root.exists():
        return None
    matches = [
        path for path in root.glob("*/summary.json")
        if path.is_file()
    ]
    if not matches:
        direct = root / "summary.json"
        return direct if direct.exists() else None
    return max(matches, key=lambda path: path.stat().st_mtime)


def _blocking_issue_keys(stages: list[dict[str, Any]], ordered_pass: bool) -> list[str]:
    keys: list[str] = []
    if not ordered_pass:
        keys.append("required_sequence_missing_or_out_of_order")
    for stage in stages:
        if stage.get("pass") is True:
            continue
        stage_name = str(stage.get("stage") or "unknown")
        if not stage.get("summary_exists"):
            keys.append(f"{stage_name}_summary_missing")
            continue
        for mismatch in stage.get("mismatch_keys") or []:
            keys.append(f"{stage_name}_{mismatch}")
    return _unique(keys)


def _next_required_action(stages: list[dict[str, Any]], ordered_pass: bool) -> str:
    for stage in stages:
        if stage.get("pass") is not True:
            name = stage.get("stage")
            if not stage.get("summary_exists"):
                return f"Produce a current staged validation summary for {name} only after prior gates allow it."
            mismatch = ", ".join(stage.get("mismatch_keys") or [])
            return f"Refresh {name} staged evidence with current v4.4 UI screenshot and worker-contract proof: {mismatch}."
    if not ordered_pass:
        return "Regenerate staged evidence in the required 024/040 -> core_12 -> LB26001_36 -> medium_30 order."
    return "Staged sequence proof is complete."


def _ordered_sequence_present(sequence: list[str]) -> bool:
    if sequence != REQUIRED_SEQUENCE:
        return False
    return True


def _stage_truthy(summary: dict[str, Any], cases: list[dict[str, Any]], keys: list[str]) -> bool:
    if any(_truthy(summary.get(key)) for key in keys):
        return True
    if not cases:
        return False
    return all(any(_truthy(case.get(key)) for key in keys) for case in cases)


def _read_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _path_from_value(value: Any) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    path = Path(value)
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


def _checks_map(value: Any) -> dict[str, bool]:
    if not isinstance(value, list):
        return {}
    result: dict[str, bool] = {}
    for item in value:
        if isinstance(item, dict) and item.get("key"):
            result[str(item.get("key"))] = item.get("pass") is True
    return result


def _check_pass(checks: dict[str, bool], key: str) -> bool:
    return checks.get(key) is True


def _artifact_exists(value: Any) -> bool:
    return isinstance(value, dict) and value.get("exists") is True


def _pass_flag(payload: dict[str, Any]) -> bool:
    return payload.get("pass") is True or str(payload.get("status") or "").lower() in {"pass", "passed"}


def _truthy(value: Any) -> bool:
    if value is True:
        return True
    if isinstance(value, str) and value.strip().lower() in {"true", "yes", "pass", "passed", "ok"}:
        return True
    return False


def _stage_matches(expected: str, observed: str) -> bool:
    return expected.lower() == observed.lower()


def _int_value(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _float_value(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _first_nonempty_case_value(cases: list[dict[str, Any]], key: str) -> str:
    for case in cases:
        value = case.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def _parse_stage_summary_arg(values: list[str]) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"Expected STAGE=PATH, got {value!r}")
        stage, path = value.split("=", 1)
        if stage not in REQUIRED_SEQUENCE:
            raise ValueError(f"Unknown stage {stage!r}; expected one of {REQUIRED_SEQUENCE}")
        result[stage] = Path(path)
    return result


def _repo_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v4.4 staged batch sequence gate report.")
    parser.add_argument("--stage-root", default=str(DEFAULT_STAGE_ROOT))
    parser.add_argument(
        "--stage-summary",
        action="append",
        default=[],
        help="Explicit summary override in STAGE=PATH form.",
    )
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    parser.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    args = parser.parse_args()
    payload = build_staged_batch_sequence_gate(
        stage_summaries={stage: _repo_path(str(path)) for stage, path in _parse_stage_summary_arg(args.stage_summary).items()},
        stage_root=_repo_path(args.stage_root),
        out_json=_repo_path(args.out_json),
        out_md=_repo_path(args.out_md),
    )
    print(json.dumps({
        "status": payload.get("status"),
        "pass": payload.get("pass"),
        "blocking_issue_keys": payload.get("blocking_issue_keys"),
        "out_json": str(_repo_path(args.out_json)),
        "out_md": str(_repo_path(args.out_md)),
    }, ensure_ascii=False))
    return 0 if payload.get("pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
