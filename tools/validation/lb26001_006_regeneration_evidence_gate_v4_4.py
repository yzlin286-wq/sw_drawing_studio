from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
BASE = "LB26001-A-04-006"
SCHEMA = "sw_drawing_studio.lb26001_006_regeneration_evidence_gate.v4_4"
DEFAULT_OUT_JSON = REPO_ROOT / "drw_output" / "diagnostics" / "lb26001_006_regeneration_evidence_gate_v4_4.json"
DEFAULT_OUT_MD = REPO_ROOT / "drw_output" / "diagnostics" / "lb26001_006_regeneration_evidence_gate_v4_4.md"
DEFAULT_READINESS = REPO_ROOT / "drw_output" / "diagnostics" / "lb26001_006_regression_readiness_v4_2.json"

REQUIRED_ARTIFACT_KEYS = [
    "manifest",
    "sw_session",
    "job_event_log",
    "slddrw",
    "pdf",
    "dxf",
    "png",
    "qc_json",
    "warnings_json",
    "drawing_blueprint",
    "vision_qc",
    "vision_qc_v6",
    "final_quality",
]

FRESH_ARTIFACT_KEYS = [
    "manifest",
    "sw_session",
    "job_event_log",
    "slddrw",
    "pdf",
    "dxf",
    "png",
    "qc_json",
    "warnings_json",
    "drawing_blueprint",
    "vision_qc",
    "vision_qc_v6",
    "final_quality",
]


def build_regeneration_evidence_gate(
    *,
    run_dir: Path | None = None,
    summary_path: Path | None = None,
    readiness_path: Path = DEFAULT_READINESS,
    out_json: Path | None = None,
    out_md: Path | None = None,
) -> dict[str, Any]:
    summary = _read_json(summary_path) if summary_path else {}
    selected_case = _select_case(summary, BASE)
    resolved_run_dir = _resolve_run_dir(run_dir, selected_case)
    readiness = _read_json(readiness_path)

    checks: list[dict[str, Any]] = []
    _add_check(
        checks,
        "explicit_006_run_evidence_source",
        resolved_run_dir is not None,
        "Provide --run-dir or --summary for the fresh locked 006 CAD run.",
        {
            "run_dir_arg": str(run_dir or ""),
            "summary_path": str(summary_path or ""),
            "summary_case_found": bool(selected_case),
        },
    )

    manifest: dict[str, Any] = {}
    sw_session: dict[str, Any] = {}
    final_quality: dict[str, Any] = {}
    artifacts: dict[str, dict[str, Any]] = {}
    events: list[dict[str, Any]] = []
    started_epoch: float | None = None
    run_id = ""

    if resolved_run_dir is not None:
        run_id = resolved_run_dir.name
        manifest_path = resolved_run_dir / "manifest.json"
        manifest = _read_json(manifest_path)
        started_epoch = _find_started_epoch(manifest, selected_case)
        artifacts = _collect_artifacts(resolved_run_dir, BASE, started_epoch)
        sw_session = _read_json(Path(artifacts.get("sw_session", {}).get("path") or ""))
        final_quality = _read_json(Path(artifacts.get("final_quality", {}).get("path") or ""))
        events = _load_event_log(resolved_run_dir)
        event_types = sorted({_event_type(event) for event in events if _event_type(event)})

        runs_root = (REPO_ROOT / "drw_output" / "runs").resolve()
        resolved = resolved_run_dir.resolve()
        _add_check(
            checks,
            "run_dir_under_runs",
            resolved.parent == runs_root and bool(run_id),
            "The 006 run directory must be directly under drw_output/runs/<run_id>.",
            {"run_dir": str(resolved_run_dir), "run_id": run_id},
        )
        _add_check(
            checks,
            "manifest_base",
            manifest.get("part_base") == BASE,
            "The worker manifest must identify LB26001-A-04-006.",
            {"part_base": manifest.get("part_base")},
        )
        _add_check(
            checks,
            "manifest_run_id",
            manifest.get("run_id") == run_id,
            "The worker manifest run_id must match the run directory name.",
            {"manifest_run_id": manifest.get("run_id"), "run_id": run_id},
        )
        _add_check(
            checks,
            "manifest_run_dir",
            _same_path(manifest.get("run_dir"), resolved_run_dir),
            "The worker manifest run_dir must match the supplied run directory.",
            {"manifest_run_dir": manifest.get("run_dir"), "run_dir": str(resolved_run_dir)},
        )
        _add_check(
            checks,
            "job_started_at_present",
            started_epoch is not None,
            "The run must expose job_started_at or artifact_freshness.min_mtime.",
            {"started_epoch": started_epoch},
        )
        for key in REQUIRED_ARTIFACT_KEYS:
            info = artifacts.get(key, {})
            _add_check(
                checks,
                f"artifact_{key}",
                bool(info.get("exists") and int(info.get("size_bytes") or 0) > 0),
                f"Missing or empty required 006 artifact: {key}.",
                info,
            )
        stale_required = [
            {"key": key, **(artifacts.get(key) or {})}
            for key in FRESH_ARTIFACT_KEYS
            if not bool((artifacts.get(key) or {}).get("fresh"))
        ]
        _add_check(
            checks,
            "fresh_required_artifacts",
            started_epoch is not None and not stale_required,
            "Required artifacts must have mtime at or after job start.",
            {"started_epoch": started_epoch, "stale_or_missing": stale_required},
        )
        stale_manifest_artifacts = ((manifest.get("artifact_freshness") or {}).get("stale_artifacts") or [])
        _add_check(
            checks,
            "manifest_no_stale_artifacts",
            not stale_manifest_artifacts,
            "The CAD worker manifest must not report stale copied artifacts.",
            {"stale_artifacts": stale_manifest_artifacts},
        )
        _add_check(
            checks,
            "manifest_core_files_ok",
            manifest.get("core_files_ok") is True,
            "The worker manifest must confirm SLDDRW/PDF/DXF/PNG core files.",
            {"core_files_ok": manifest.get("core_files_ok")},
        )
        drawing_usable = manifest.get("drawing_usable") or {}
        _add_check(
            checks,
            "manifest_drawing_usable",
            drawing_usable.get("pass") is True,
            "The worker manifest must report drawing_usable.pass=true.",
            drawing_usable,
        )
        hard_fail = manifest.get("hard_fail") or []
        _add_check(
            checks,
            "manifest_no_hard_fail",
            not hard_fail,
            "The worker manifest must not contain hard_fail entries.",
            {"hard_fail": hard_fail},
        )
        fq_status = str(final_quality.get("status") or "")
        _add_check(
            checks,
            "final_quality_status",
            fq_status in {"pass", "pass_with_warning"} and final_quality.get("deliverable") is True,
            "final_quality.json must be deliverable with pass or pass_with_warning status.",
            {"status": fq_status, "deliverable": final_quality.get("deliverable")},
        )
        _add_check(
            checks,
            "sw_session_connected",
            sw_session.get("status") == "connected" and bool(sw_session.get("sw_pid")),
            "sw_session.json must prove a real SolidWorks connection from the CAD worker.",
            {"status": sw_session.get("status"), "sw_pid": sw_session.get("sw_pid")},
        )
        required_events = {"job_started", "progress", "heartbeat", "job_finished"}
        missing_events = sorted(required_events - set(event_types))
        _add_check(
            checks,
            "worker_jsonl_events",
            not missing_events,
            "job_event_log.jsonl must include job_started/progress/heartbeat/job_finished.",
            {"event_types": event_types, "missing": missing_events, "event_count": len(events)},
        )
        if selected_case:
            _add_check(
                checks,
                "summary_case_is_006",
                _case_base(selected_case) == BASE,
                "The staged summary case must be LB26001-A-04-006.",
                {"case_base": _case_base(selected_case)},
            )

    failed = [item for item in checks if item["status"] != "pass"]
    if resolved_run_dir is None:
        status = "blocked_by_missing_fresh_006_run"
    elif failed:
        status = "blocked_by_regeneration_evidence"
    else:
        status = "regeneration_evidence_pass_requires_application_ui_screenshot_review"

    payload = {
        "schema": SCHEMA,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "base": BASE,
        "status": status,
        "pass": not failed,
        "release_ready": False,
        "report_is_drawing_acceptance_evidence": False,
        "api_only_acceptance_allowed": False,
        "ui_screenshot_acceptance_required": True,
        "application_drawing_review_ui_required": True,
        "solidworks_runtime_called": False,
        "run_id": run_id,
        "run_dir": str(resolved_run_dir or ""),
        "summary_path": str(summary_path or ""),
        "readiness": {
            "path": str(readiness_path),
            "status": readiness.get("status"),
            "ready_to_start_locked_006_cad": readiness.get("ready_to_start_locked_006_cad"),
            "blocking_issue_keys": readiness.get("blocking_issue_keys") or [],
        },
        "artifact_summary": artifacts,
        "event_summary": {
            "event_types": sorted({_event_type(event) for event in events if _event_type(event)}),
            "event_count": len(events),
        },
        "manifest_summary": {
            "part_base": manifest.get("part_base"),
            "run_id": manifest.get("run_id"),
            "run_dir": manifest.get("run_dir"),
            "core_files_ok": manifest.get("core_files_ok"),
            "drawing_usable": manifest.get("drawing_usable"),
            "hard_fail": manifest.get("hard_fail"),
            "artifact_freshness": manifest.get("artifact_freshness"),
        },
        "checks": checks,
        "blocking_issue_keys": [item["key"] for item in failed],
        "next_required_action": _next_action(status),
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
        f"# {payload.get('base')} Regeneration Evidence Gate v4.4",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- PASS: `{str(payload.get('pass')).lower()}`",
        "- Drawing acceptance evidence: `false`",
        "- API-only acceptance allowed: `false`",
        "- Application Drawing Review UI screenshot required: `true`",
        f"- Run dir: `{payload.get('run_dir') or '<missing>'}`",
        "",
        "## Checks",
        "",
    ]
    for item in payload.get("checks") or []:
        lines.append(f"- `{item.get('status')}` `{item.get('key')}`: {item.get('message')}")
    lines.extend(["", "## Blocking Issues", ""])
    keys = payload.get("blocking_issue_keys") or []
    lines.extend([f"- `{key}`" for key in keys] or ["- None"])
    lines.extend(["", "## Next Required Action", "", str(payload.get("next_required_action") or ""), ""])
    return "\n".join(lines)


def _next_action(status: str) -> str:
    if status == "regeneration_evidence_pass_requires_application_ui_screenshot_review":
        return (
            "Open the generated 006 PNG/PDF in the application Drawing Review UI, capture per-drawing screenshots, "
            "and record manual visual judgement before any 007/008/009/015/022 expansion."
        )
    if status == "blocked_by_missing_fresh_006_run":
        return (
            "Start SolidWorks manually, rerun readiness, then run exactly one locked 006 CAD worker. "
            "Do not reuse older run folders as current correction evidence."
        )
    return "Fix the failed regeneration evidence checks, then repeat the locked 006 CAD run and UI screenshot review."


def _read_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
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


def _resolve_run_dir(run_dir: Path | None, selected_case: dict[str, Any]) -> Path | None:
    if run_dir is not None:
        return run_dir.resolve()
    value = selected_case.get("run_dir") if selected_case else ""
    return _repo_path(str(value)).resolve() if value else None


def _select_case(summary: dict[str, Any], base: str) -> dict[str, Any]:
    for item in summary.get("cases") or []:
        if isinstance(item, dict) and _case_base(item) == base:
            return item
    return {}


def _case_base(case: dict[str, Any]) -> str:
    value = str(case.get("part_name") or "")
    if value:
        return value
    part = str(case.get("part") or "")
    return Path(part).stem if part else ""


def _repo_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


def _same_path(value: Any, path: Path) -> bool:
    if not value:
        return False
    try:
        return Path(str(value)).resolve() == path.resolve()
    except Exception:
        return False


def _find_started_epoch(manifest: dict[str, Any], selected_case: dict[str, Any]) -> float | None:
    freshness = manifest.get("artifact_freshness") or {}
    for candidate in [
        freshness.get("min_mtime"),
        manifest.get("job_started_at"),
        selected_case.get("job_started_at") if selected_case else None,
    ]:
        value = _coerce_float(candidate)
        if value is not None:
            return value
    cad_report = selected_case.get("cad_report") if selected_case else ""
    if cad_report:
        value = _first_float_for_key(_read_json(_repo_path(str(cad_report))), "job_started_at")
        if value is not None:
            return value
    return None


def _coerce_float(value: Any) -> float | None:
    if value in ("", None):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _first_float_for_key(value: Any, key: str) -> float | None:
    if isinstance(value, dict):
        if key in value:
            number = _coerce_float(value.get(key))
            if number is not None:
                return number
        for item in value.values():
            number = _first_float_for_key(item, key)
            if number is not None:
                return number
    elif isinstance(value, list):
        for item in value:
            number = _first_float_for_key(item, key)
            if number is not None:
                return number
    return None


def _path_info(path: Path | None, started_epoch: float | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {
            "path": str(path or ""),
            "exists": False,
            "size_bytes": 0,
            "mtime_epoch": None,
            "fresh": False,
        }
    stat = path.stat()
    return {
        "path": str(path),
        "exists": True,
        "size_bytes": stat.st_size,
        "mtime_epoch": stat.st_mtime,
        "fresh": bool(started_epoch is not None and stat.st_mtime >= started_epoch - 1.0),
    }


def _find_first(run_dir: Path, patterns: list[str]) -> Path | None:
    for pattern in patterns:
        for path in sorted(run_dir.glob(pattern)):
            if path.is_file():
                return path
    return None


def _collect_artifacts(run_dir: Path, base: str, started_epoch: float | None) -> dict[str, dict[str, Any]]:
    paths = {
        "manifest": run_dir / "manifest.json",
        "sw_session": run_dir / "sw_session.json",
        "job_event_log": run_dir / "job_event_log.jsonl",
        "slddrw": _find_first(run_dir, [f"drawing/{base}_v5.SLDDRW", "drawing/*.SLDDRW"]),
        "pdf": _find_first(run_dir, [f"drawing/{base}_v5.PDF", "drawing/*.PDF"]),
        "dxf": _find_first(run_dir, [f"drawing/{base}_v5.DXF", "drawing/*.DXF"]),
        "png": _find_first(run_dir, [f"drawing/{base}_v5.PNG", "drawing/*.PNG"]),
        "qc_json": _find_first(run_dir, [f"qc/{base}_v5_qc.json", "qc/*_qc.json"]),
        "warnings_json": _find_first(run_dir, [f"qc/{base}_v5_warnings.json", "qc/*_warnings.json"]),
        "drawing_blueprint": _find_first(run_dir, ["qc/drawing_blueprint.json", "qc/*drawing_blueprint*.json"]),
        "vision_qc": _find_first(run_dir, ["qc/vision_qc_v6.json", "qc/vision_qc_v2.json", "qc/vision_qc_v5.json", "qc/*_v5_vision.json"]),
        "vision_qc_v6": _find_first(run_dir, ["qc/vision_qc_v6.json"]),
        "final_quality": run_dir / "qc" / "final_quality.json",
    }
    return {key: _path_info(path, started_epoch) for key, path in paths.items()}


def _load_event_log(run_dir: Path) -> list[dict[str, Any]]:
    path = run_dir / "job_event_log.jsonl"
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            events.append(value)
    return events


def _event_type(event: dict[str, Any]) -> str:
    return str(event.get("event_type") or event.get("type") or "")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate fresh regeneration evidence for LB26001-A-04-006.")
    parser.add_argument("--run-dir", default="")
    parser.add_argument("--summary", default="")
    parser.add_argument("--readiness", default=str(DEFAULT_READINESS))
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    parser.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    args = parser.parse_args()

    payload = build_regeneration_evidence_gate(
        run_dir=_repo_path(args.run_dir) if args.run_dir else None,
        summary_path=_repo_path(args.summary) if args.summary else None,
        readiness_path=_repo_path(args.readiness),
        out_json=_repo_path(args.out_json),
        out_md=_repo_path(args.out_md),
    )
    print(json.dumps({
        "status": payload.get("status"),
        "pass": payload.get("pass"),
        "run_dir": payload.get("run_dir"),
        "blocking_issue_keys": payload.get("blocking_issue_keys"),
        "out_json": str(_repo_path(args.out_json)),
        "out_md": str(_repo_path(args.out_md)),
    }, ensure_ascii=False))
    return 0 if payload.get("pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
