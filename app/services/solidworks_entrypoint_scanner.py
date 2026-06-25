from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_PATH = REPO_ROOT / "drw_output" / "diagnostics" / "unguarded_solidworks_entrypoints.json"
SCHEMA = "sw_drawing_studio.unguarded_solidworks_entrypoints.v4_2"

PATTERNS: dict[str, re.Pattern[str]] = {
    "GetActiveObject": re.compile(r"\bGetActiveObject\s*\("),
    "Dispatch": re.compile(r"\bDispatch\s*\("),
    "DispatchEx": re.compile(r"\bDispatchEx\s*\("),
    "OpenDoc6": re.compile(r"\bOpenDoc6\s*\("),
    "RunMacro2": re.compile(r"\bRunMacro2\s*\("),
    "ReplaceViewModel": re.compile(r"\bReplaceViewModel\s*\("),
    "AddDimension2": re.compile(r"\bAddDimension2\s*\("),
    "SaveAs": re.compile(r"\bSaveAs\s*\("),
    "CloseDoc": re.compile(r"\bCloseDoc\s*\("),
    "DialogGuard": re.compile(r"\bDialogGuard\b"),
    "Add-in Ping": re.compile(r"(?:\bPing\s*\(|\bAddInPing\s*\(|\baddin_ping\s*\(|\b_probe_addin_ping\s*\()", re.IGNORECASE),
}

GUARD_TOKENS = (
    "solidworks_global_lock",
    "require_current_job_lock",
    "acquire_lock(",
    "SW_DRAWING_STUDIO_LOCK_JOB_ID",
    "blocked_by_solidworks_lock",
)

SKIP_DIRS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    "drw_output",
    "dist",
    "dist_v3_smoke",
    "build",
    ".mypy_cache",
}

EXTENSIONS = {".py", ".cs", ".ps1", ".bat", ".cmd"}


def scan_solidworks_entrypoints(root: Path | str = REPO_ROOT) -> dict[str, Any]:
    root = Path(root)
    entries: list[dict[str, Any]] = []
    scanned_files = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in EXTENSIONS:
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        rel = path.relative_to(root).as_posix()
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        scanned_files += 1
        has_guard_token = any(token in text for token in GUARD_TOKENS)
        for line_no, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if not stripped or _is_comment_line(stripped):
                continue
            code_line = _strip_string_literals(stripped)
            if not code_line.strip():
                continue
            matched = [name for name, pattern in PATTERNS.items() if pattern.search(code_line)]
            if not matched:
                continue
            guard_status = _guard_status(rel, has_guard_token)
            entries.append({
                "file": rel,
                "line": line_no,
                "patterns": matched,
                "guard_status": guard_status,
                "text": stripped[:240],
            })

    unguarded = [entry for entry in entries if entry["guard_status"] == "unguarded_or_unknown"]
    addin_hosted = [entry for entry in entries if entry["guard_status"] == "external_addin_needs_host_lock"]
    document_manager = [entry for entry in entries if entry["guard_status"] == "document_manager_com_no_sldworks_session"]
    validation_tool = [entry for entry in entries if entry["guard_status"] == "validation_tool_requires_manual_lock"]
    maintenance_tool = [entry for entry in entries if entry["guard_status"] == "maintenance_tool"]
    test_or_fixture = [entry for entry in entries if entry["guard_status"] == "test_or_fixture"]
    legacy = [entry for entry in entries if entry["guard_status"] == "legacy_experiment"]
    report = {
        "schema": SCHEMA,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "root": str(root),
        "scanned_files": scanned_files,
        "entrypoint_count": len(entries),
        "guarded_count": sum(1 for entry in entries if entry["guard_status"] == "guarded"),
        "unguarded_or_unknown_count": len(unguarded),
        "external_addin_needs_host_lock_count": len(addin_hosted),
        "document_manager_com_count": len(document_manager),
        "validation_tool_requires_manual_lock_count": len(validation_tool),
        "maintenance_tool_count": len(maintenance_tool),
        "test_or_fixture_count": len(test_or_fixture),
        "legacy_experiment_count": len(legacy),
        "status": "warning" if unguarded or addin_hosted else "pass",
        "policy": {
            "no_com_without_global_lock": True,
            "ui_thread_no_solidworks_com": True,
            "visual_audit_no_solidworks": True,
            "api_metrics_are_supporting_only": True,
        },
        "unguarded_or_unknown": unguarded,
        "external_addin_needs_host_lock": addin_hosted,
        "document_manager_com_no_sldworks_session": document_manager,
        "validation_tool_requires_manual_lock": validation_tool,
        "maintenance_tool": maintenance_tool,
        "test_or_fixture": test_or_fixture,
        "legacy_experiment": legacy,
        "entries": entries,
    }
    return report


def write_entrypoint_report(
    *,
    root: Path | str = REPO_ROOT,
    out_path: Path | str = DEFAULT_OUT_PATH,
) -> dict[str, Any]:
    report = scan_solidworks_entrypoints(root)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report["report_path"] = str(out)
    return report


def _guard_status(rel: str, has_guard_token: bool) -> str:
    if _is_document_manager_path(rel):
        return "document_manager_com_no_sldworks_session"
    if _is_external_sidecar_path(rel):
        return "external_addin_needs_host_lock"
    if _is_validation_tool(rel):
        return "validation_tool_requires_manual_lock"
    if _is_test_or_fixture(rel):
        return "test_or_fixture"
    if _is_maintenance_tool(rel):
        return "maintenance_tool"
    if _is_legacy_experiment(rel):
        return "legacy_experiment"
    return "guarded" if has_guard_token else "unguarded_or_unknown"


def _is_comment_line(stripped: str) -> bool:
    return stripped.startswith(("#", "//", "*", "REM ", "::"))


def _strip_string_literals(line: str) -> str:
    string_re = re.compile(
        r"(?i)(?:[rubf]{0,3})("
        r"\"\"\".*?\"\"\"|'''.*?'''|"
        r"\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'"
        r")"
    )
    return string_re.sub('""', line)


def _is_legacy_experiment(rel: str) -> bool:
    name = Path(rel).name
    return (
        name.startswith("_tmp_")
        or name.startswith("smoke_v1_")
        or name.startswith("run_v1_")
        or name.startswith("run_v2_")
        or name.startswith("capture_v1_")
        or name.startswith("freeze_v1_")
        or rel.startswith(".agents/")
        or rel.startswith(".trae/")
    )


def _is_document_manager_path(rel: str) -> bool:
    return (
        rel in {"app/services/docmgr_service.py", "app/services/sw_docmgr_relink.py"}
        or rel.startswith("tools/SwDocMgrRelink/")
    )


def _is_external_sidecar_path(rel: str) -> bool:
    return rel.startswith((
        "tools/SwDrawingStudioAddin/",
        "tools/SwDimensionSidecar/",
        "tools/SwReferenceMetricsSidecar/",
    ))


def _is_validation_tool(rel: str) -> bool:
    return rel.startswith("tools/validation/")


def _is_test_or_fixture(rel: str) -> bool:
    name = Path(rel).name
    return rel.startswith("tests/") or name.startswith("test_") or name.endswith("_test.py")


def _is_maintenance_tool(rel: str) -> bool:
    return rel.startswith("templates/") or rel in {"register_addin.py"}


__all__ = ["scan_solidworks_entrypoints", "write_entrypoint_report"]
