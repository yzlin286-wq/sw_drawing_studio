from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA = "sw_drawing_studio.truth_gate.v1"
DEFAULT_PROFILE = "release-v3"
DRAWING_SUFFIXES = {".slddrw", ".pdf", ".dxf", ".png"}
SUSPICIOUS_RESULT_TOKENS = ("mock", "synthetic", "fallback")


def evaluate_case(case_dir: Path | str, *, profile: str = DEFAULT_PROFILE) -> dict[str, Any]:
    root = Path(case_dir).resolve()
    files = _discover_files(root)
    json_payloads = {
        str(path.relative_to(root) if _is_relative_to(path, root) else path): _read_json(path)
        for path in files["json_files"]
    }
    hard_failures: list[dict[str, Any]] = []

    _check_sw_session(root, files, hard_failures)
    _check_artifact_freshness(root, files, json_payloads, hard_failures)
    _check_note_dimension_substitution(json_payloads, hard_failures)
    _check_mock_synthetic_fallback_release_pass(json_payloads, hard_failures)
    _check_reference_compare_or_reason(root, files, json_payloads, hard_failures)

    return {
        "schema": SCHEMA,
        "profile": profile,
        "case_dir": str(root),
        "pass": not hard_failures,
        "allowed_to_claim_release_pass": not hard_failures,
        "hard_fail_count": len(hard_failures),
        "hard_failures": hard_failures,
        "checked_files": {
            "json_count": len(files["json_files"]),
            "drawing_artifact_count": len(files["drawing_artifacts"]),
            "sw_session": str(files["sw_session"]) if files["sw_session"] else "",
            "reference_compare_count": len(files["reference_compare"]),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Anti-fallback truth gate for release claims.")
    parser.add_argument("--fixtures", required=True, help="Run/case directory to evaluate.")
    parser.add_argument("--profile", default=DEFAULT_PROFILE)
    parser.add_argument("--out", default="")
    args = parser.parse_args(argv)

    report = evaluate_case(Path(args.fixtures), profile=args.profile)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if report["allowed_to_claim_release_pass"] else 1


def _discover_files(root: Path) -> dict[str, Any]:
    json_files = sorted(path for path in root.rglob("*.json") if path.is_file()) if root.exists() else []
    drawing_artifacts = sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in DRAWING_SUFFIXES
    ) if root.exists() else []
    sw_sessions = [path for path in json_files if path.name.lower() == "sw_session.json"]
    reference_compare = [
        path
        for path in json_files
        if "reference_compare" in path.name.lower()
    ]
    return {
        "json_files": json_files,
        "drawing_artifacts": drawing_artifacts,
        "sw_session": sw_sessions[0] if sw_sessions else None,
        "reference_compare": reference_compare,
    }


def _check_sw_session(root: Path, files: dict[str, Any], hard_failures: list[dict[str, Any]]) -> None:
    sw_session_path = files.get("sw_session")
    if not sw_session_path:
        hard_failures.append({
            "key": "sw_session_missing",
            "message": "sw_session.json is required for release truth claims.",
        })
        return
    payload = _read_json(sw_session_path)
    status = str(payload.get("status") or "").strip().lower()
    if status != "connected":
        hard_failures.append({
            "key": "sw_session_not_connected",
            "path": _rel(sw_session_path, root),
            "status": payload.get("status"),
            "message": "sw_session.status must be connected.",
        })


def _check_artifact_freshness(
    root: Path,
    files: dict[str, Any],
    json_payloads: dict[str, Any],
    hard_failures: list[dict[str, Any]],
) -> None:
    job_started_at = _find_first_value(json_payloads.values(), {"job_started_at", "job_started", "started_at"})
    started = _parse_datetime(job_started_at)
    if started is None:
        return

    artifacts = _artifact_paths_from_payloads(root, json_payloads)
    if not artifacts:
        artifacts = list(files["drawing_artifacts"])
    for artifact in artifacts:
        path = artifact if artifact.is_absolute() else root / artifact
        if not path.exists():
            hard_failures.append({
                "key": "drawing_artifact_missing",
                "path": str(path),
                "job_started_at": str(job_started_at),
            })
            continue
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        if mtime < started:
            hard_failures.append({
                "key": "drawing_artifact_stale",
                "path": _rel(path, root),
                "job_started_at": _iso(started),
                "artifact_mtime": _iso(mtime),
                "message": "Drawing artifact mtime must be >= job_started_at.",
            })


def _check_note_dimension_substitution(
    json_payloads: dict[str, Any],
    hard_failures: list[dict[str, Any]],
) -> None:
    part_class = str(_find_first_value(json_payloads.values(), {"part_class", "class"}) or "").strip().lower()
    for path, payload in json_payloads.items():
        for record in _walk_dicts(payload):
            local_part_class = str(record.get("part_class") or part_class).strip().lower()
            if local_part_class != "feature_part":
                continue
            display_dim_count = _to_int(record.get("display_dim_count"))
            note_dim_count = _to_int(record.get("note_dim_count"))
            if display_dim_count == 0 and note_dim_count > 0:
                hard_failures.append({
                    "key": "note_dimensions_masquerade_as_displaydims",
                    "path": path,
                    "part_class": local_part_class,
                    "display_dim_count": display_dim_count,
                    "note_dim_count": note_dim_count,
                    "message": "feature_part cannot claim dimensions from Note annotations.",
                })


def _check_mock_synthetic_fallback_release_pass(
    json_payloads: dict[str, Any],
    hard_failures: list[dict[str, Any]],
) -> None:
    release_pass = any(bool(record.get("release_pass")) for payload in json_payloads.values() for record in _walk_dicts(payload))
    if not release_pass:
        return
    suspicious_paths = []
    for path, payload in json_payloads.items():
        if _contains_token(payload, SUSPICIOUS_RESULT_TOKENS):
            suspicious_paths.append(path)
    if suspicious_paths:
        hard_failures.append({
            "key": "mock_synthetic_or_fallback_claimed_release_pass",
            "paths": sorted(suspicious_paths),
            "tokens": list(SUSPICIOUS_RESULT_TOKENS),
            "message": "mock/synthetic/fallback evidence cannot claim release_pass=true.",
        })


def _check_reference_compare_or_reason(
    root: Path,
    files: dict[str, Any],
    json_payloads: dict[str, Any],
    hard_failures: list[dict[str, Any]],
) -> None:
    if files["reference_compare"]:
        return
    reason = _find_first_value(json_payloads.values(), {"no_reference_reason"})
    if str(reason or "").strip():
        return
    hard_failures.append({
        "key": "reference_compare_missing_without_reason",
        "case_dir": str(root),
        "message": "reference_compare evidence is required unless no_reference_reason is explicit.",
    })


def _artifact_paths_from_payloads(root: Path, json_payloads: dict[str, Any]) -> list[Path]:
    paths: list[Path] = []
    for payload in json_payloads.values():
        for value in _walk_values(payload):
            if not isinstance(value, str):
                continue
            suffix = Path(value).suffix.lower()
            if suffix in DRAWING_SUFFIXES:
                paths.append(_resolve_path(root, value))
    seen = set()
    unique = []
    for path in paths:
        key = str(path).lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def _resolve_path(root: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return (root / path).resolve()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {"value": value}


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    for candidate in (text, text.replace(" ", "T")):
        try:
            parsed = datetime.fromisoformat(candidate)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except Exception:
            continue
    return None


def _walk_dicts(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_dicts(child)


def _walk_values(value: Any):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from _walk_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_values(child)


def _find_first_value(payloads: Any, keys: set[str]) -> Any:
    for payload in payloads:
        for record in _walk_dicts(payload):
            for key, value in record.items():
                if str(key) in keys:
                    return value
    return None


def _contains_token(value: Any, tokens: tuple[str, ...]) -> bool:
    for item in _walk_values(value):
        if isinstance(item, str):
            lower = item.lower()
            if any(token in lower for token in tokens):
                return True
    return False


def _to_int(value: Any) -> int | None:
    try:
        return int(value)
    except Exception:
        return None


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except Exception:
        return str(path)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except Exception:
        return False


if __name__ == "__main__":
    sys.exit(main())
