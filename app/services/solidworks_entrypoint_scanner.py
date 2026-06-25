from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_PATH = REPO_ROOT / "drw_output" / "diagnostics" / "unguarded_solidworks_entrypoints.json"
SCHEMA = "sw_drawing_studio.unguarded_solidworks_entrypoints.v4_4"

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
    "DocMgr probe": re.compile(r"(?:\bprobe_docmgr\s*\(|\bSWDM[A-Za-z0-9_]*\b)", re.IGNORECASE),
    "SolidWorks COM probe": re.compile(r"\bprobe_solidworks_connection\s*\("),
    "subprocess.run": re.compile(r"\bsubprocess\.run\s*\("),
    "subprocess.Popen": re.compile(r"\bsubprocess\.Popen\s*\("),
    "os.system": re.compile(r"\bos\.system\s*\("),
    "time.sleep": re.compile(r"\btime\.sleep\s*\("),
}

GUARD_TOKENS = (
    "solidworks_global_lock",
    "require_current_job_lock",
    "acquire_lock(",
    "SW_DRAWING_STUDIO_LOCK_JOB_ID",
    "blocked_by_solidworks_lock",
)

COM_PATTERNS = {
    "GetActiveObject",
    "Dispatch",
    "DispatchEx",
    "OpenDoc6",
    "RunMacro2",
    "ReplaceViewModel",
    "AddDimension2",
    "SaveAs",
    "CloseDoc",
    "DialogGuard",
    "Add-in Ping",
    "SolidWorks COM probe",
}

BLOCKING_PATTERNS = {"subprocess.run", "subprocess.Popen", "os.system", "time.sleep"}
DOCMGR_PATTERNS = {"DocMgr probe"}
ALLOWED_UI_SUBPROCESS_HINTS = ("explorer", "startfile")

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
            scope = _scope_for_path(rel)
            guard_status = _guard_status(rel, has_guard_token, matched, stripped)
            entries.append({
                "file": rel,
                "line": line_no,
                "patterns": matched,
                "guard_status": guard_status,
                "scope": scope,
                "risk_bucket": _risk_bucket(rel, scope, matched, guard_status, stripped),
                "requires_global_lock": _requires_global_lock(matched),
                "ui_thread_risk": _is_ui_thread_risk(scope, matched, stripped),
                "service_direct_risk": _is_service_direct_risk(scope, matched, guard_status),
                "text": stripped[:240],
            })

    unguarded = [entry for entry in entries if entry["guard_status"] == "unguarded_or_unknown"]
    addin_hosted = [entry for entry in entries if entry["guard_status"] == "external_addin_needs_host_lock"]
    document_manager = [entry for entry in entries if entry["guard_status"] == "document_manager_com_no_sldworks_session"]
    validation_tool = [entry for entry in entries if entry["guard_status"] == "validation_tool_requires_manual_lock"]
    maintenance_tool = [entry for entry in entries if entry["guard_status"] == "maintenance_tool"]
    test_or_fixture = [entry for entry in entries if entry["guard_status"] == "test_or_fixture"]
    legacy = [entry for entry in entries if entry["guard_status"] == "legacy_experiment"]
    bounded_probe_worker_launcher = [
        entry for entry in entries if entry["guard_status"] == "bounded_probe_worker_launcher"
    ]
    system_health_worker_probe = [
        entry for entry in entries if entry["guard_status"] == "system_health_worker_probe_service"
    ]
    ui_thread_risks = [entry for entry in entries if entry.get("ui_thread_risk")]
    service_direct_risks = [entry for entry in entries if entry.get("service_direct_risk")]
    system_health_ui_direct = [
        entry for entry in entries
        if entry.get("ui_thread_risk")
        and entry["file"] in {"app/ui/system_health_page.py", "app/ui/home_page.py"}
        and (
            any(pattern in set(entry["patterns"]) for pattern in COM_PATTERNS | DOCMGR_PATTERNS)
            or "subprocess.run" in entry["patterns"]
        )
    ]
    external_host_lock_contract = _external_addin_host_lock_contract(root)
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
        "bounded_probe_worker_launcher_count": len(bounded_probe_worker_launcher),
        "system_health_worker_probe_service_count": len(system_health_worker_probe),
        "external_addin_host_lock_contract_status": external_host_lock_contract.get("status"),
        "ui_thread_direct_risk_count": len(ui_thread_risks),
        "service_direct_risk_count": len(service_direct_risks),
        "system_health_ui_thread_direct_probe_count": len(system_health_ui_direct),
        "status": "warning" if unguarded or addin_hosted or ui_thread_risks or service_direct_risks else "pass",
        "policy": {
            "no_com_without_global_lock": True,
            "ui_thread_no_solidworks_com": True,
            "ui_thread_no_long_subprocess": True,
            "system_health_ui_thread_no_addin_ping_docmgr_or_subprocess_run": True,
            "visual_audit_no_solidworks": True,
            "api_metrics_are_supporting_only": True,
        },
        "external_addin_host_lock_contract": external_host_lock_contract,
        "ui_thread_direct_risks": ui_thread_risks,
        "service_direct_risks": service_direct_risks,
        "system_health_ui_thread_direct_probe": system_health_ui_direct,
        "unguarded_or_unknown": unguarded,
        "external_addin_needs_host_lock": addin_hosted,
        "document_manager_com_no_sldworks_session": document_manager,
        "bounded_probe_worker_launcher": bounded_probe_worker_launcher,
        "system_health_worker_probe_service": system_health_worker_probe,
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


def _guard_status(rel: str, has_guard_token: bool, patterns: list[str], text: str) -> str:
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
    if _scope_for_path(rel) == "worker":
        return "worker_process"
    if _is_bounded_probe_worker_launcher(rel, patterns):
        return "bounded_probe_worker_launcher"
    if _is_system_health_worker_probe_service(rel, patterns):
        return "system_health_worker_probe_service"
    if _is_known_worker_launcher(rel, patterns):
        return "worker_launcher"
    if _is_allowed_ui_subprocess(patterns, text):
        return "ui_shell_open_allowlisted"
    return "guarded" if has_guard_token else "unguarded_or_unknown"


def _scope_for_path(rel: str) -> str:
    if rel.startswith("app/ui/"):
        return "ui"
    if rel.startswith("app/workers/"):
        return "worker"
    if rel.startswith("app/services/"):
        return "service"
    if rel.startswith("tools/"):
        return "tool"
    return "other"


def _requires_global_lock(patterns: list[str]) -> bool:
    names = set(patterns)
    return bool(names & COM_PATTERNS) and not bool(names <= DOCMGR_PATTERNS)


def _is_ui_thread_risk(scope: str, patterns: list[str], text: str) -> bool:
    if scope != "ui":
        return False
    names = set(patterns)
    if names & (COM_PATTERNS | DOCMGR_PATTERNS):
        return True
    if names & BLOCKING_PATTERNS and not _is_allowed_ui_subprocess(patterns, text):
        return True
    return False


def _is_service_direct_risk(scope: str, patterns: list[str], guard_status: str) -> bool:
    if scope != "service":
        return False
    names = set(patterns)
    if guard_status in {
        "worker_launcher",
        "bounded_probe_worker_launcher",
        "system_health_worker_probe_service",
        "document_manager_com_no_sldworks_session",
    }:
        return False
    if names & COM_PATTERNS and guard_status != "guarded":
        return True
    if names & DOCMGR_PATTERNS:
        return True
    return False


def _risk_bucket(rel: str, scope: str, patterns: list[str], guard_status: str, text: str) -> str:
    names = set(patterns)
    if _is_ui_thread_risk(scope, patterns, text):
        return "ui_thread_direct_blocking_or_com"
    if _is_service_direct_risk(scope, patterns, guard_status):
        return "service_direct_com_or_probe"
    if scope == "worker":
        return "worker_process_allowed"
    if guard_status == "bounded_probe_worker_launcher":
        return "bounded_probe_worker_launcher_allowed"
    if guard_status == "system_health_worker_probe_service":
        return "system_health_worker_probe_service_allowed"
    if guard_status == "worker_launcher":
        return "worker_launcher_allowed"
    if guard_status == "guarded":
        return "global_lock_guarded"
    if names & DOCMGR_PATTERNS:
        return "document_manager_probe"
    if names & BLOCKING_PATTERNS:
        return "blocking_call_requires_review"
    if names & COM_PATTERNS:
        return "solidworks_com_requires_lock"
    return "requires_review"


def _is_known_worker_launcher(rel: str, patterns: list[str]) -> bool:
    if not (set(patterns) & BLOCKING_PATTERNS):
        return False
    return rel in {
        "app/services/job_runner.py",
        "app/services/resource_paths.py",
        "app/services/solidworks_com_probe_service.py",
    }


def _is_bounded_probe_worker_launcher(rel: str, patterns: list[str]) -> bool:
    names = set(patterns)
    if rel == "app/services/solidworks_com_probe_service.py":
        return bool(names & (BLOCKING_PATTERNS | {"SolidWorks COM probe"}))
    if rel == "app/services/sw_connection_guard.py":
        return "SolidWorks COM probe" in names
    return False


def _is_system_health_worker_probe_service(rel: str, patterns: list[str]) -> bool:
    if rel != "app/services/system_health_service.py":
        return False
    return bool(set(patterns) & DOCMGR_PATTERNS)


def _is_allowed_ui_subprocess(patterns: list[str], text: str) -> bool:
    if not (set(patterns) & {"subprocess.Popen"}):
        return False
    lowered = text.lower()
    return any(hint in lowered for hint in ALLOWED_UI_SUBPROCESS_HINTS)


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


def _external_addin_host_lock_contract(root: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def text(rel: str) -> str:
        try:
            return (root / rel).read_text(encoding="utf-8", errors="replace")
        except Exception:
            return ""

    def add(key: str, rel: str, required: list[str], note: str) -> None:
        content = text(rel)
        missing = [item for item in required if item not in content]
        checks.append({
            "key": key,
            "file": rel,
            "status": "pass" if not missing else "fail",
            "missing": missing,
            "note": note,
        })

    add(
        "cad_worker_holds_global_lock_before_pipeline",
        "app/workers/cad_job_worker.py",
        ["acquire_lock(", "SW_DRAWING_STUDIO_LOCK_JOB_ID", "release_lock("],
        "CAD worker owns the SolidWorks global lock and passes the lock job id to generation subprocesses.",
    )
    add(
        "batch_worker_holds_global_lock_before_children",
        "app/workers/batch_job_worker.py",
        ["acquire_lock(", "SW_DRAWING_STUDIO_LOCK_JOB_ID", "release_lock("],
        "Batch worker serializes child CAD work under the same SolidWorks global lock contract.",
    )
    add(
        "drawing_review_addin_action_has_lock",
        "app/workers/drawing_review_worker.py",
        ["acquire_lock(", "generate_dimensions_v3", "release_lock("],
        "Drawing Review Add-in dimensions are submitted from a QProcess worker after acquiring the lock.",
    )
    add(
        "addin_client_requires_current_job_lock",
        "app/services/sw_addin_client.py",
        ['require_current_job_lock("sw_addin_client._get_sw_app")'],
        "Every Python call that obtains SolidWorks for the Add-in API goes through _get_sw_app lock validation.",
    )
    add(
        "dimension_sidecar_requires_current_job_lock",
        "app/services/dimension_sidecar_service.py",
        ['require_current_job_lock("dimension_sidecar_service.run_dimension_sidecar")'],
        "Dimension sidecar entrypoint checks the active job lock before invoking C# sidecar or Python COM fallback.",
    )
    add(
        "v6_generator_sidecar_runs_inside_worker_pipeline",
        ".trae/specs/build-v6-and-validate-exe-ui/drw_generate_v6.py",
        ["run_dimension_sidecar(", "SW_DRAWING_STUDIO_LOCK_JOB_ID"],
        "v6 generator calls the sidecar from the CAD worker subprocess environment that carries the lock job id.",
    )

    failed = [check for check in checks if check["status"] != "pass"]
    return {
        "schema": "sw_drawing_studio.external_addin_host_lock_contract.v4_4",
        "status": "pass" if not failed else "warning",
        "pass": not failed,
        "check_count": len(checks),
        "failed_count": len(failed),
        "checks": checks,
        "external_sources": [
            "tools/SwDrawingStudioAddin/",
            "tools/SwDimensionSidecar/",
            "tools/SwReferenceMetricsSidecar/",
        ],
        "interpretation": (
            "External Add-in and sidecar source files cannot acquire the Python global lock themselves; "
            "their Python host entrypoints must prove QProcess worker routing and current-job lock ownership."
        ),
    }


__all__ = ["scan_solidworks_entrypoints", "write_entrypoint_report"]
