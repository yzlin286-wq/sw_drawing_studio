"""v3.0 reference drawing comparison smoke.

Compares the fresh Real CAD Smoke drawing with the same-name original 2D
SLDDRW under 3D转2D测试图纸. The comparison is intentionally structured and
truthful: it records weak or missing metrics as differences instead of
pretending a full reference-comparison suite is complete.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CAD_SMOKE = REPO_ROOT / "drw_output" / "cad_smoke_v3_0.json"
DEFAULT_OUT = REPO_ROOT / "drw_output" / "reference_compare_smoke.json"
SIDECAR_EXE = REPO_ROOT / "tools" / "SwReferenceMetricsSidecar" / "bin" / "SwReferenceMetricsSidecar.exe"
SIDECAR_OUT_DIR = REPO_ROOT / "drw_output" / "reference_metrics_sidecar"
ANNOTATION_PROBE_TIMEOUT_S = 45

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.solidworks_com_probe_service import probe_solidworks_connection


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _safe_artifact_label(label: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", label).strip("._")
    return safe or "drawing"


def _find_first(run_dir: Path, patterns: list[str]) -> Path | None:
    for pattern in patterns:
        for path in sorted(run_dir.glob(pattern)):
            if path.is_file():
                return path
    return None


def _resolve_repo_path(path: Path) -> Path:
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.resolve()


def _resolve_optional_repo_path(path: Path | None) -> Path | None:
    if path is None:
        return None
    if str(path) in {"", "."}:
        return None
    return _resolve_repo_path(path)


def _resolve_reference_drawing(part_path: Path | None, reference_dir: Path, base: str) -> Path:
    reference_dir = _resolve_repo_path(reference_dir)
    reference = reference_dir / f"{base}.SLDDRW"
    sibling = part_path.with_suffix(".SLDDRW") if part_path else None
    if reference.exists():
        return reference
    if sibling and sibling.exists():
        return sibling
    return reference


def _safe_value(obj: Any, name: str, default: Any = None) -> Any:
    try:
        value = getattr(obj, name)
        return value() if callable(value) else value
    except Exception:
        return default


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    try:
        return list(value)
    except TypeError:
        return [value]
    except Exception:
        return []


def _wrap_dispatch(value: Any) -> Any:
    try:
        import win32com.client as wc

        return wc.dynamic.Dispatch(value)
    except Exception:
        return value


def _ensure_solidworks_global_lock(operation: str, path: str | Path = "") -> None:
    try:
        from app.services.solidworks_global_lock import require_current_job_lock

        guard = require_current_job_lock(operation)
    except Exception as exc:
        raise RuntimeError(f"blocked_by_solidworks_lock: lock_guard_unavailable: {exc}")
    if guard.get("ok"):
        return
    raise RuntimeError(
        "blocked_by_solidworks_lock: "
        + json.dumps({
            "operation": operation,
            "path": str(path or ""),
            "reason": guard.get("reason", ""),
            "owner": guard.get("owner", {}),
            "fix_suggestion": guard.get("fix_suggestion", ""),
        }, ensure_ascii=False)
    )


def _flatten_dispatch_items(value: Any) -> list[Any]:
    items: list[Any] = []

    def walk(raw: Any) -> None:
        if raw is None:
            return
        if isinstance(raw, (list, tuple)):
            for child in raw:
                walk(child)
            return
        items.append(_wrap_dispatch(raw))

    walk(value)
    return items


def _connect_sw():
    _ensure_solidworks_global_lock("reference_compare_smoke_v3.connect_sw")
    import win32com.client as wc

    try:
        return wc.dynamic.Dispatch(wc.GetActiveObject("SldWorks.Application")), "get_active_object"
    except Exception:
        return wc.dynamic.Dispatch(wc.Dispatch("SldWorks.Application")), "dispatch"


def _count_display_dims(view: Any) -> int:
    try:
        dims = _safe_value(view, "GetDisplayDimensions")
        if dims:
            return len(dims)
    except Exception:
        pass
    count = 0
    try:
        dim = _safe_value(view, "GetFirstDisplayDimension")
        seen = 0
        while dim is not None and seen < 10000:
            count += 1
            seen += 1
            dim = view.GetNextDisplayDimension(dim)
    except Exception:
        pass
    return count


def _annotation_type(annotation: Any) -> int:
    for method in ("GetType", "GetType2"):
        try:
            value = _safe_value(annotation, method)
            if value is not None:
                return int(value)
        except Exception:
            continue
    return -1


def _annotation_name(annotation: Any) -> str:
    for method in ("GetName", "GetName2", "GetNameForSelection", "Name"):
        try:
            value = _safe_value(annotation, method)
            if value:
                return str(value)
        except Exception:
            continue
    return ""


def _is_cosmetic_thread_annotation(annotation: Any) -> bool:
    name = _annotation_name(annotation).lower()
    return any(token in name for token in ("孔螺", "螺纹线", "螺蚊线", "cosmetic thread", "thread"))


def _count_display_dim_annotation_items(items: Any) -> int:
    count = 0
    for annotation in _flatten_dispatch_items(items):
        if _annotation_type(annotation) == 1 and not _is_cosmetic_thread_annotation(annotation):
            count += 1
    return count


def _count_display_dim_annotations(view: Any) -> int:
    count = _count_display_dim_annotation_items(_safe_value(view, "GetAnnotations"))
    annotation = None
    for method in ("GetFirstAnnotation3", "GetFirstAnnotation2", "GetFirstAnnotation"):
        annotation = _safe_value(view, method)
        if annotation is not None:
            break
    seen = 0
    while annotation is not None and seen < 10000:
        if _annotation_type(annotation) == 1 and not _is_cosmetic_thread_annotation(annotation):
            count += 1
        seen += 1
        next_annotation = None
        for method in ("GetNext3", "GetNext2", "GetNext"):
            next_annotation = _safe_value(annotation, method)
            if next_annotation is not None:
                break
        annotation = next_annotation
    return count


def _annotation_count(doc: Any) -> int:
    annotations = _safe_value(doc, "GetAnnotations")
    try:
        return len(annotations) if annotations else 0
    except Exception:
        return 0


def _collect_views(doc: Any, sheet: Any) -> list[Any]:
    views: list[Any] = []

    def append_chain(start: Any, include_start: bool = True) -> None:
        view = start if include_start else _safe_value(start, "GetNextView")
        seen = 0
        while view is not None and seen < 1000:
            views.append(view)
            seen += 1
            view = _safe_value(view, "GetNextView")

    for raw_view in _flatten_dispatch_items(_safe_value(sheet, "GetViews") if sheet is not None else None):
        views.append(raw_view)
    if views:
        return views

    # Some pywin32 bindings expose sheet views via ModelDoc2.GetViews; each
    # sheet view then links to drawing views through GetNextView.
    for sheet_view in _flatten_dispatch_items(_safe_value(doc, "GetViews")):
        views.append(sheet_view)
    if views:
        return views

    # SolidWorks DrawingDoc.GetFirstView usually returns the sheet pseudo-view
    # first, followed by real drawing views through GetNextView.
    append_chain(_safe_value(doc, "GetFirstView"), include_start=True)
    if views:
        return views

    # Last fallback: activate each sheet, then traverse the DrawingDoc view
    # chain. This is validation-only code, never UI-thread code.
    for sheet_name in _as_list(_safe_value(doc, "GetSheetNames")):
        try:
            _safe_value(doc, "ActivateSheet", None)
        except Exception:
            pass
        try:
            activate = getattr(doc, "ActivateSheet")
            activate(sheet_name)
        except Exception:
            continue
        append_chain(_safe_value(doc, "GetFirstView"), include_start=True)
        if views:
            break
    return views


def _view_outline(view: Any) -> list[float]:
    outline = _safe_value(view, "Outline")
    if not outline:
        outline = _safe_value(view, "GetOutline")
    if not outline:
        return []
    try:
        return [float(x) for x in outline[:4]]
    except Exception:
        return []


def _open_metrics(sw: Any, path: Path) -> dict[str, Any]:
    import pythoncom
    import win32com.client as wc
    from win32com.client import VARIANT

    result: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "success": False,
        "open_errors": None,
        "open_warnings": None,
        "reason": "",
        "sheet": {},
        "view_count": 0,
        "view_types": {},
        "view_names": [],
        "view_outlines": [],
        "display_dim_count": 0,
        "annotation_count": 0,
        "file_size_bytes": path.stat().st_size if path.exists() else 0,
    }
    if not path.exists():
        result["reason"] = "drawing_not_found"
        return result

    doc = None
    title = ""
    try:
        errors = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        warnings = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        doc = sw.OpenDoc6(str(path), 3, 1, "", errors, warnings)
        result["open_errors"] = int(errors.value)
        result["open_warnings"] = int(warnings.value)
        if doc is None:
            result["reason"] = f"OpenDoc6 returned None errors={errors.value} warnings={warnings.value}"
            return result
        title = str(_safe_value(doc, "GetTitle", ""))
        doc_candidates = [doc]
        try:
            cast_doc = wc.CastTo(doc, "DrawingDoc")
            if cast_doc is not None:
                doc_candidates.insert(0, cast_doc)
        except Exception:
            pass
        sheet = None
        views: list[Any] = []
        for doc_candidate in doc_candidates:
            sheet = _safe_value(doc_candidate, "GetCurrentSheet")
            if sheet is not None:
                result["sheet"] = {
                    "name": str(_safe_value(sheet, "Name", "")),
                    "paper_size": _safe_value(sheet, "GetSize"),
                    "properties": list(_safe_value(sheet, "GetProperties2", []) or []),
                }
            views = _collect_views(doc_candidate, sheet)
            if views:
                break
        view_types: Counter[str] = Counter()
        display_dim_count = 0
        display_dim_annotation_count = 0
        view_names: list[str] = []
        outlines: list[dict[str, Any]] = []
        seen_view_keys: set[tuple[str, str, str]] = set()
        for view in views:
            name = str(_safe_value(view, "Name", ""))
            vtype = str(_safe_value(view, "Type", ""))
            outline = _view_outline(view)
            # Skip the sheet pseudo-view when traversing via GetFirstView.
            if not outline and (not vtype or vtype == "0"):
                continue
            view_key = (name, vtype, json.dumps(outline, ensure_ascii=False))
            if view_key in seen_view_keys:
                continue
            seen_view_keys.add(view_key)
            view_names.append(name)
            view_types[vtype] += 1
            display_dim_count += _count_display_dims(view)
            display_dim_annotation_count += _count_display_dim_annotations(view)
            if outline:
                outlines.append({"name": name, "type": vtype, "outline": outline})
        display_dim_annotation_count = max(
            display_dim_annotation_count,
            _count_display_dim_annotation_items(_safe_value(doc, "GetAnnotations")),
        )
        result.update({
            "success": True,
            "view_count": len(view_names),
            "view_types": dict(view_types),
            "view_names": view_names,
            "view_outlines": outlines,
            "display_dim_count": display_dim_count,
            "display_dim_annotation_count": display_dim_annotation_count,
            "display_dim_count_source": "display_dimension_api",
            "annotation_count": _annotation_count(doc),
        })
    except Exception as exc:
        result["reason"] = str(exc)
    finally:
        if doc is not None:
            try:
                sw.CloseDoc(title or str(path))
            except Exception:
                pass
    return result


def _metric_summary(metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": metrics.get("source", "pywin32"),
        "success": bool(metrics.get("success")),
        "reason": metrics.get("reason", ""),
        "view_count": int(metrics.get("view_count") or 0),
        "display_dim_count": int(metrics.get("display_dim_count") or 0),
        "display_dim_annotation_count": int(metrics.get("display_dim_annotation_count") or 0),
        "display_dim_count_source": metrics.get("display_dim_count_source", ""),
        "annotation_count": int(metrics.get("annotation_count") or 0),
        "open_errors": metrics.get("open_errors"),
        "open_warnings": metrics.get("open_warnings"),
    }


def _metrics_need_sidecar(metrics: dict[str, Any], *, require_dimension_baseline: bool) -> bool:
    if not metrics.get("success"):
        return True
    if int(metrics.get("view_count") or 0) <= 0:
        return True
    if require_dimension_baseline and int(metrics.get("display_dim_count") or 0) <= 0:
        return True
    return False


def _sheet_bounds(metrics: dict[str, Any]) -> tuple[float, float, float, float] | None:
    sheet = metrics.get("sheet") or {}
    properties = sheet.get("properties") or []
    try:
        if len(properties) >= 7:
            width = float(properties[5])
            height = float(properties[6])
            if width > 0 and height > 0:
                return (-0.005, -0.005, width + 0.005, height + 0.005)
    except Exception:
        pass
    paper_size = sheet.get("paper_size") or []
    try:
        if len(paper_size) >= 2:
            width = float(paper_size[0])
            height = float(paper_size[1])
            if width > 0 and height > 0:
                return (-0.005, -0.005, width + 0.005, height + 0.005)
    except Exception:
        pass
    return (-0.005, -0.005, 0.302, 0.215)


def _outline_intersects_bounds(outline: list[Any], bounds: tuple[float, float, float, float]) -> bool:
    if len(outline) < 4:
        return True
    try:
        x0, y0, x1, y1 = [float(v) for v in outline[:4]]
    except Exception:
        return True
    if x1 < x0:
        x0, x1 = x1, x0
    if y1 < y0:
        y0, y1 = y1, y0
    bx0, by0, bx1, by1 = bounds
    return x1 >= bx0 and x0 <= bx1 and y1 >= by0 and y0 <= by1


def _normalize_view_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    outlines = metrics.get("view_outlines") or []
    if not metrics.get("success") or not outlines:
        return metrics
    bounds = _sheet_bounds(metrics)
    if bounds is None:
        return metrics

    kept: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    for item in outlines:
        outline = item.get("outline") if isinstance(item, dict) else None
        if outline and _outline_intersects_bounds(list(outline), bounds):
            kept.append(item)
        elif outline:
            removed.append(item)
        else:
            kept.append(item)

    if not removed or not kept:
        return metrics

    normalized = dict(metrics)
    normalized["raw_view_count"] = int(metrics.get("view_count") or len(outlines))
    normalized["raw_view_types"] = metrics.get("view_types") or {}
    normalized["raw_view_names"] = list(metrics.get("view_names") or [])
    normalized["raw_view_outlines"] = outlines
    normalized["view_outlines"] = kept
    normalized["view_names"] = [str(item.get("name") or "") for item in kept]
    normalized["view_types"] = dict(Counter(str(item.get("type") or "") for item in kept))
    normalized["view_count"] = len(kept)
    normalized["view_filter"] = {
        "applied": True,
        "reason": "removed_off_sheet_palette_views",
        "sheet_bounds": [round(v, 6) for v in bounds],
        "removed_count": len(removed),
        "removed_names": [str(item.get("name") or "") for item in removed],
    }
    return normalized


def _sidecar_failure_payload(path: Path, out_path: Path, reason: str) -> dict[str, Any]:
    return {
        "schema": "sw_drawing_studio.reference_metrics.v1",
        "source": "csharp_sidecar",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "path": str(path),
        "exists": path.exists(),
        "success": False,
        "status": "error",
        "reason": reason,
        "sidecar_report": str(out_path),
        "view_count": 0,
        "view_types": {},
        "view_names": [],
        "view_outlines": [],
        "display_dim_count": 0,
        "display_dim_annotation_count": 0,
        "display_dim_count_source": "",
        "annotation_count": 0,
        "file_size_bytes": path.stat().st_size if path.exists() else 0,
        "warnings": [],
    }


def _probe_failure_bucket(probe_result: dict[str, Any]) -> str:
    status = str(probe_result.get("status") or "")
    reason = str(probe_result.get("reason") or "")
    if status == "timeout" or "timed out" in reason.lower():
        return "solidworks_com_active_object_timeout"
    return "solidworks_com_unavailable"


def _probe_failure_reason(probe_result: dict[str, Any]) -> str:
    bucket = _probe_failure_bucket(probe_result)
    reason = str(probe_result.get("reason") or probe_result.get("status") or "SolidWorks COM probe failed")
    return f"{bucket}: {reason}"


def _probe_failure_metrics(path: Path, label: str, probe_result: dict[str, Any]) -> dict[str, Any]:
    out_path = SIDECAR_OUT_DIR / f"{_safe_artifact_label(label)}.json"
    result = _sidecar_failure_payload(path, out_path, _probe_failure_reason(probe_result))
    result["source"] = "solidworks_com_probe"
    result["failure_bucket"] = _probe_failure_bucket(probe_result)
    result["connection_probe"] = probe_result
    _write_json(out_path, result)
    return result


def _merge_annotation_display_dim_fallback(
    metrics: dict[str, Any],
    supplemental: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(metrics)
    if not supplemental:
        return merged

    merged["annotation_probe"] = _metric_summary(supplemental)
    if supplemental.get("annotation_probe_report"):
        merged["annotation_probe_report"] = supplemental.get("annotation_probe_report")
    if not supplemental.get("success"):
        warnings = list(merged.get("warnings") or [])
        if "display_dim_annotation_probe_failed" not in warnings:
            warnings.append("display_dim_annotation_probe_failed")
        merged["warnings"] = warnings
        return merged

    annotation_count = int(supplemental.get("display_dim_annotation_count") or 0)
    merged["display_dim_annotation_count"] = annotation_count
    if int(merged.get("display_dim_count") or 0) <= 0 and annotation_count > 0:
        merged["display_dim_count_api"] = int(merged.get("display_dim_count") or 0)
        merged["display_dim_count"] = annotation_count
        merged["display_dim_count_source"] = "annotation_type1"
        warnings = list(merged.get("warnings") or [])
        if "display_dim_count_from_annotation_type1" not in warnings:
            warnings.append("display_dim_count_from_annotation_type1")
        merged["warnings"] = warnings
    else:
        merged.setdefault("display_dim_count_source", "display_dimension_api")
    return merged


def _annotation_probe_payload(path: Path, out_path: Path | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema": "sw_drawing_studio.reference_annotation_probe.v1",
        "source": "pywin32_annotation_probe",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "path": str(path),
        "exists": path.exists(),
        "success": False,
        "reason": "",
        "view_count": 0,
        "view_types": {},
        "view_names": [],
        "view_outlines": [],
        "display_dim_count": 0,
        "display_dim_annotation_count": 0,
        "display_dim_count_source": "annotation_type1",
        "annotation_count": 0,
        "warnings": [],
    }
    if not path.exists():
        payload["reason"] = "drawing_not_found"
    else:
        try:
            import win32com.client as wc

            _ensure_solidworks_global_lock("reference_compare_smoke_v3.annotation_probe", path)
            sw = wc.GetActiveObject("SldWorks.Application")
            metrics = _open_metrics(sw, path)
            payload.update(metrics)
            payload["source"] = "pywin32_annotation_probe"
            payload["display_dim_count_source"] = "annotation_type1"
            payload["success"] = bool(metrics.get("success"))
            if not payload["success"]:
                payload["reason"] = str(metrics.get("reason") or "annotation probe failed")
        except Exception as exc:
            payload["reason"] = f"annotation_probe_exception: {exc}"
    if out_path is not None:
        payload["annotation_probe_report"] = str(out_path)
        _write_json(out_path, payload)
    return payload


def _run_annotation_probe(path: Path, label: str, *, timeout_s: int = ANNOTATION_PROBE_TIMEOUT_S) -> dict[str, Any]:
    out_path = SIDECAR_OUT_DIR / f"{_safe_artifact_label(label)}_annotation_probe.json"
    timeout = max(5, min(int(timeout_s or ANNOTATION_PROBE_TIMEOUT_S), ANNOTATION_PROBE_TIMEOUT_S))
    result: dict[str, Any] = {
        "source": "pywin32_annotation_probe",
        "path": str(path),
        "exists": path.exists(),
        "success": False,
        "reason": "",
        "annotation_probe_report": str(out_path),
        "display_dim_annotation_count": 0,
    }
    try:
        completed = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "--annotation-probe-drawing",
                str(path),
                "--annotation-probe-out",
                str(out_path),
            ],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
        result["returncode"] = completed.returncode
        result["stdout"] = completed.stdout.strip()
        result["stderr"] = completed.stderr.strip()
        payload = _read_json(out_path)
        if payload:
            payload["returncode"] = completed.returncode
            payload["stdout"] = completed.stdout.strip()
            payload["stderr"] = completed.stderr.strip()
            payload["annotation_probe_report"] = str(out_path)
            return payload
        result["reason"] = f"annotation_probe_output_missing: {out_path}"
    except subprocess.TimeoutExpired as exc:
        result["reason"] = f"annotation_probe_timeout_after_{timeout}s"
        result["stdout"] = (exc.stdout or "").strip() if isinstance(exc.stdout, str) else ""
        result["stderr"] = (exc.stderr or "").strip() if isinstance(exc.stderr, str) else ""
    except Exception as exc:
        result["reason"] = f"annotation_probe_exception: {exc}"
    _write_json(out_path, result)
    return result


def _run_reference_metrics_sidecar(path: Path, label: str, *, timeout_s: int = 180) -> dict[str, Any]:
    out_path = SIDECAR_OUT_DIR / f"{_safe_artifact_label(label)}.json"
    result: dict[str, Any] = _sidecar_failure_payload(path, out_path, "")
    if not SIDECAR_EXE.exists():
        result["reason"] = f"sidecar_missing: {SIDECAR_EXE}"
        _write_json(out_path, result)
        return result

    try:
        completed = subprocess.run(
            [str(SIDECAR_EXE), "--drawing", str(path), "--out", str(out_path)],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
            check=False,
        )
        result["returncode"] = completed.returncode
        result["stdout"] = completed.stdout.strip()
        result["stderr"] = completed.stderr.strip()
        if out_path.exists():
            sidecar_payload = _read_json(out_path)
            if sidecar_payload:
                sidecar_payload["sidecar_report"] = str(out_path)
                sidecar_payload["returncode"] = completed.returncode
                sidecar_payload["stdout"] = completed.stdout.strip()
                sidecar_payload["stderr"] = completed.stderr.strip()
                supplemental = _run_annotation_probe(path, label, timeout_s=timeout_s)
                sidecar_payload = _merge_annotation_display_dim_fallback(sidecar_payload, supplemental)
                _write_json(out_path, sidecar_payload)
                return sidecar_payload
        result["reason"] = f"sidecar_output_missing: {out_path}"
    except subprocess.TimeoutExpired as exc:
        result["reason"] = f"sidecar_timeout_after_{timeout_s}s"
        result["stdout"] = (exc.stdout or "").strip() if isinstance(exc.stdout, str) else ""
        result["stderr"] = (exc.stderr or "").strip() if isinstance(exc.stderr, str) else ""
    except Exception as exc:
        result["reason"] = f"sidecar_exception: {exc}"
    _write_json(out_path, result)
    return result


def _maybe_upgrade_metrics_with_sidecar(
    metrics: dict[str, Any],
    path: Path,
    label: str,
    *,
    require_dimension_baseline: bool,
    timeout_s: int = 180,
) -> dict[str, Any]:
    if not _metrics_need_sidecar(metrics, require_dimension_baseline=require_dimension_baseline):
        metrics.setdefault("source", "pywin32")
        return metrics

    python_summary = _metric_summary(metrics)
    sidecar_metrics = _run_reference_metrics_sidecar(path, label, timeout_s=timeout_s)
    sidecar_metrics["python_metrics"] = python_summary
    if sidecar_metrics.get("success"):
        sidecar_metrics.setdefault("source", "csharp_sidecar")
        return sidecar_metrics

    metrics.setdefault("source", "pywin32")
    metrics["sidecar_attempt"] = sidecar_metrics
    return metrics


def _ratio_score(generated: float, reference: float) -> float:
    if reference <= 0:
        return 1.0 if generated >= 0 else 0.0
    return round(min(generated / reference, 1.0), 3)


def _truthy_metric(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value > 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "present", "pass"}
    return bool(value)


def _reference_requires_annotation(reference: dict[str, Any], key: str) -> bool:
    if key == "gb_has_section_view_or_skipped":
        view_types = {str(k) for k in (reference.get("view_types") or {}).keys()}
        view_names = [str(v) for v in reference.get("view_names") or []]
        return "3" in view_types or any(("剖" in name or "section" in name.lower()) for name in view_names)

    evidence_keys = {
        "has_tech_note": ("has_tech_note", "tech_note_present", "tech_note_count"),
        "has_ra_note": ("has_ra_note", "roughness_count", "surface_finish_count"),
        "has_datum_a": ("has_datum_a", "datum_count", "datum_a_present"),
    }
    for metric_key in evidence_keys.get(key, ()):
        if _truthy_metric(reference.get(metric_key)):
            return True
    return False


def _score(reference: dict[str, Any], generated: dict[str, Any], qc: dict[str, Any], *, base: str = "") -> dict[str, Any]:
    from tools.validation.dimension_validation_smoke_v3 import (
        _bool,
        _has_sidecar_dimension_evidence,
        _is_strict_reference_intent_dimension_case,
    )

    differences: list[dict[str, Any]] = []
    metric_quality: dict[str, Any] = {
        "reference": {"usable": True, "weak_reasons": [], "annotation_evidence_skipped": []},
        "generated": {"usable": True, "weak_reasons": [], "fallbacks": []},
    }
    checks = qc.get("checks") or {}
    warnings = set(qc.get("warnings") or [])
    scoring_base = str(base or qc.get("base") or qc.get("part_base") or generated.get("base") or "").strip()
    strict_reference_intent_case = _is_strict_reference_intent_dimension_case(scoring_base, qc=qc)
    metric_quality["generated"]["strict_reference_intent_case"] = strict_reference_intent_case
    metric_quality["generated"]["sidecar_policy_allowed"] = not strict_reference_intent_case

    def mark_weak(scope: str, key: str, severity: str, reference_value: str, generated_value: str, fix: str) -> None:
        metric_quality[scope]["usable"] = False
        metric_quality[scope]["weak_reasons"].append(key)
        differences.append({
            "key": key,
            "severity": severity,
            "reference": reference_value,
            "generated": generated_value,
            "fix_suggestion": fix,
        })

    if not reference.get("success"):
        mark_weak(
            "reference",
            "reference_metrics_unavailable",
            "need_review",
            str(reference.get("reason", "")),
            "",
            "Verify SolidWorks can open the reference SLDDRW and extract drawing views.",
        )
    if not generated.get("success"):
        metric_quality["generated"]["usable"] = False
        metric_quality["generated"]["weak_reasons"].append("generated_metrics_unavailable")
        differences.append({
            "key": "generated_metrics_unavailable",
            "severity": "fail",
            "reference": "",
            "generated": generated.get("reason", ""),
            "fix_suggestion": "Regenerate the smoke drawing and rerun comparison.",
        })

    ref_views = int(reference.get("view_count") or 0)
    gen_views_from_metrics = int(generated.get("view_count") or 0)
    gen_views_from_qc = int(((checks.get("view_overlap") or {}).get("real_view_count")) or 0)
    gen_views = gen_views_from_metrics or gen_views_from_qc
    if gen_views_from_metrics <= 0 and gen_views_from_qc > 0:
        metric_quality["generated"]["fallbacks"].append("qc.view_overlap.real_view_count")
    if reference.get("success") and ref_views <= 0:
        mark_weak(
            "reference",
            "reference_view_metrics_empty",
            "need_review",
            "view_count=0",
            str(gen_views),
            "Fix reference view extraction; empty reference views cannot prove comparison coverage.",
        )
    if generated.get("success") and gen_views <= 0:
        mark_weak(
            "generated",
            "generated_view_metrics_empty",
            "need_review",
            str(ref_views),
            "view_count=0",
            "Fix generated drawing view extraction or regenerate the smoke drawing.",
        )
    if ref_views <= 0:
        view_count_score = 0.0
    elif gen_views <= 0:
        view_count_score = 0.0
    else:
        view_count_score = min(gen_views / ref_views, ref_views / gen_views, 1.0)
    ref_types = set((reference.get("view_types") or {}).keys())
    gen_types = set((generated.get("view_types") or {}).keys())
    type_score = 0.0 if ref_views <= 0 else (1.0 if not ref_types else len(ref_types & gen_types) / max(len(ref_types), 1))
    view_match_score = round((view_count_score * 0.6) + (type_score * 0.4), 3)
    if gen_views < ref_views:
        differences.append({
            "key": "view_count_lower_than_reference",
            "severity": "warning",
            "reference": str(ref_views),
            "generated": str(gen_views),
            "fix_suggestion": "Add missing views or document why the generated layout is acceptable.",
        })
    if ref_views > 0 and gen_views > ref_views:
        differences.append({
            "key": "view_count_higher_than_reference",
            "severity": "need_review",
            "reference": str(ref_views),
            "generated": str(gen_views),
            "fix_suggestion": "Remove extra generated views or prove the reference drawing requires an additional view.",
        })
    if ref_types and not ref_types.issubset(gen_types):
        differences.append({
            "key": "view_type_mismatch",
            "severity": "warning",
            "reference": json.dumps(sorted(ref_types), ensure_ascii=False),
            "generated": json.dumps(sorted(gen_types), ensure_ascii=False),
            "fix_suggestion": "Compare projection/detail/section view strategy against the reference drawing.",
        })
    if ref_types and not gen_types.issubset(ref_types):
        differences.append({
            "key": "view_type_extra_than_reference",
            "severity": "need_review",
            "reference": json.dumps(sorted(ref_types), ensure_ascii=False),
            "generated": json.dumps(sorted(gen_types), ensure_ascii=False),
            "fix_suggestion": "Do not add section/detail/view families that are absent from the same-name reference drawing.",
        })

    ref_dims = int(reference.get("display_dim_count") or 0)
    generated_metric_dims = int(generated.get("display_dim_count") or 0)
    qc_metric_dims = int(qc.get("display_dim_count") or 0)
    gen_dims = generated_metric_dims or qc_metric_dims
    if generated_metric_dims <= 0 and qc_metric_dims > 0:
        metric_quality["generated"]["fallbacks"].append("qc.display_dim_count")
    dim_sources = qc.get("dimension_sources") or {}
    coverage = checks.get("dimension_coverage") or {}
    note_dim_count = int(qc.get("note_dim_count") or dim_sources.get("note_dim_count") or 0)
    standard_annotation_count = 1 if _bool(qc.get("standard_annotation_present")) else 0
    has_policy_dimension_evidence, dimension_policy = _has_sidecar_dimension_evidence(
        part_class=str(qc.get("part_class") or ""),
        display_dim_count=gen_dims,
        note_dim_count=note_dim_count,
        standard_annotation_count=standard_annotation_count,
        coverage=coverage,
        warnings=list(warnings),
        dim_sources=dim_sources,
        allow_sidecar_policy=not strict_reference_intent_case,
    )
    if reference.get("success") and ref_dims <= 0:
        mark_weak(
            "reference",
            "reference_display_dim_metrics_empty",
            "need_review",
            "display_dim_count=0",
            str(gen_dims),
            "Fix reference DisplayDim extraction; an empty reference dimension baseline cannot prove coverage.",
        )
    if generated.get("success") and gen_dims <= 0 and not has_policy_dimension_evidence:
        mark_weak(
            "generated",
            "generated_display_dim_metrics_empty",
            "need_review",
            str(ref_dims),
            "display_dim_count=0",
            "Fix generated DisplayDim extraction or rerun dimension generation.",
        )
    if generated.get("success") and gen_dims <= 0 and has_policy_dimension_evidence:
        metric_quality["generated"]["fallbacks"].append(f"part_class_policy.{dimension_policy}")
        differences.append({
            "key": "generated_display_dim_zero_with_part_class_policy",
            "severity": "warning",
            "reference": str(ref_dims),
            "generated": f"DisplayDim=0; note_dim_count={note_dim_count}; policy={dimension_policy}",
            "fix_suggestion": "Keep Note/sidecar annotations separate from DisplayDim; review whether part-class exemption is acceptable.",
        })
    dimension_match_score = (
        0.0 if ref_dims <= 0
        else 0.8 if gen_dims <= 0 and has_policy_dimension_evidence
        else _ratio_score(gen_dims, ref_dims)
    )
    if ref_dims and gen_dims < ref_dims:
        differences.append({
            "key": "display_dim_count_lower_than_reference",
            "severity": "warning",
            "reference": str(ref_dims),
            "generated": str(gen_dims),
            "fix_suggestion": "Add missing DisplayDim dimensions or record an engineering exemption.",
        })

    titlebar = checks.get("all_13_keys_present") or {}
    titlebar_match_score = 1.0 if titlebar.get("pass") is True else round(float(titlebar.get("present_count") or 0) / 13.0, 3)
    annotation_penalty = 0.0
    for key in ["has_tech_note", "has_ra_note", "has_datum_a", "gb_has_section_view_or_skipped"]:
        if key in warnings and _reference_requires_annotation(reference, key):
            annotation_penalty += 0.15
            differences.append({
                "key": key,
                "severity": "warning",
                "reference": "present or expected in reference policy",
                "generated": "missing or weak",
                "fix_suggestion": "Fix generated drawing annotation or document part-class exemption.",
            })
        elif key in warnings:
            metric_quality["reference"]["annotation_evidence_skipped"].append(key)
    annotation_match_score = round(max(0.0, 1.0 - annotation_penalty), 3)

    layout_score = 1.0
    if (checks.get("view_overlap") or {}).get("pass") is False:
        layout_score -= 0.35
    if (checks.get("view_in_frame") or {}).get("pass") is False:
        layout_score -= 0.35
    layout_match_score = round(max(0.0, layout_score), 3)

    overall = round(
        view_match_score * 0.25
        + dimension_match_score * 0.25
        + titlebar_match_score * 0.15
        + annotation_match_score * 0.2
        + layout_match_score * 0.15,
        3,
    )
    if any(d["severity"] == "fail" for d in differences):
        status = "fail"
    elif any(d["severity"] == "need_review" for d in differences):
        status = "need_review"
    elif overall >= 0.8 and differences:
        status = "pass_with_warning"
    elif overall >= 0.8:
        status = "pass"
    elif overall >= 0.65:
        status = "need_review"
    else:
        status = "fail"

    return {
        "view_match_score": view_match_score,
        "dimension_match_score": dimension_match_score,
        "titlebar_match_score": titlebar_match_score,
        "annotation_match_score": annotation_match_score,
        "layout_match_score": layout_match_score,
        "overall_score": overall,
        "status": status,
        "differences": differences,
        "metric_quality": metric_quality,
    }


def compare(
    run_dir: Path,
    reference_dir: Path,
    out_path: Path,
    part_path: Path | None = None,
    cad_smoke_path: Path | None = None,
    metrics_mode: str = "sidecar_first",
    sidecar_timeout_s: int = 180,
    com_probe_timeout_s: float = 3.0,
) -> dict[str, Any]:
    cad_smoke = _read_json(cad_smoke_path or DEFAULT_CAD_SMOKE)
    part_path = _resolve_optional_repo_path(part_path or Path(str(cad_smoke.get("part_path") or "")))
    base = (part_path.stem if part_path else "") or (run_dir.name if run_dir.exists() else "")
    generated = _find_first(run_dir, ["drawing/*.SLDDRW"])
    reference = _resolve_reference_drawing(part_path, reference_dir, base)
    qc_path = _find_first(run_dir, ["qc/*_qc.json"])
    qc = _read_json(qc_path) if qc_path else {}

    connection_method = ""
    connection_probe: dict[str, Any] = {}
    if com_probe_timeout_s > 0:
        connection_probe = probe_solidworks_connection(
            timeout_s=com_probe_timeout_s,
            allow_dispatch=metrics_mode == "pywin32_first",
        )
        if connection_probe.get("status") != "connected":
            connection_method = str(connection_probe.get("connection_method") or connection_probe.get("method") or "solidworks_com_probe")
            reference_metrics = _probe_failure_metrics(reference, f"{base}_reference", connection_probe)
            generated_metrics = (
                _probe_failure_metrics(generated, f"{base}_generated", connection_probe)
                if generated
                else {"path": "", "success": False, "reason": "generated drawing missing"}
            )
        else:
            connection_method = str(connection_probe.get("connection_method") or connection_probe.get("method") or "")
    if not connection_probe or connection_probe.get("status") == "connected":
        if metrics_mode in {"sidecar_first", "sidecar_only"}:
            connection_method = connection_method or "sidecar_subprocess"
            reference_metrics = _run_reference_metrics_sidecar(
                reference,
                f"{base}_reference",
                timeout_s=sidecar_timeout_s,
            )
            generated_metrics = (
                _run_reference_metrics_sidecar(generated, f"{base}_generated", timeout_s=sidecar_timeout_s)
                if generated
                else {"path": "", "success": False, "reason": "generated drawing missing"}
            )
            if metrics_mode == "sidecar_first" and reference_metrics.get("reason", "").startswith("sidecar_missing"):
                try:
                    sw, connection_method = _connect_sw()
                    reference_metrics = _open_metrics(sw, reference)
                    generated_metrics = _open_metrics(sw, generated) if generated else {"success": False, "reason": "generated drawing missing"}
                except Exception as exc:
                    reference_metrics = {"path": str(reference), "success": False, "reason": str(exc)}
                    generated_metrics = {"path": str(generated or ""), "success": False, "reason": str(exc)}
                reference_metrics = _maybe_upgrade_metrics_with_sidecar(
                    reference_metrics,
                    reference,
                    f"{base}_reference",
                    require_dimension_baseline=True,
                    timeout_s=sidecar_timeout_s,
                )
                if generated:
                    generated_metrics = _maybe_upgrade_metrics_with_sidecar(
                        generated_metrics,
                        generated,
                        f"{base}_generated",
                        require_dimension_baseline=False,
                        timeout_s=sidecar_timeout_s,
                    )
        else:
            try:
                sw, connection_method = _connect_sw()
                reference_metrics = _open_metrics(sw, reference)
                generated_metrics = _open_metrics(sw, generated) if generated else {"success": False, "reason": "generated drawing missing"}
            except Exception as exc:
                reference_metrics = {"path": str(reference), "success": False, "reason": str(exc)}
                generated_metrics = {"path": str(generated or ""), "success": False, "reason": str(exc)}
            reference_metrics = _maybe_upgrade_metrics_with_sidecar(
                reference_metrics,
                reference,
                f"{base}_reference",
                require_dimension_baseline=True,
                timeout_s=sidecar_timeout_s,
            )
            if generated:
                generated_metrics = _maybe_upgrade_metrics_with_sidecar(
                    generated_metrics,
                    generated,
                    f"{base}_generated",
                    require_dimension_baseline=False,
                    timeout_s=sidecar_timeout_s,
                )

    reference_metrics = _normalize_view_metrics(reference_metrics)
    if generated:
        generated_metrics = _normalize_view_metrics(generated_metrics)

        scoring = _score(reference_metrics, generated_metrics, qc, base=base)
    payload = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "reference_compare_smoke_v3",
        "metrics_mode": metrics_mode,
        "sidecar_timeout_s": sidecar_timeout_s,
        "part": str(part_path or ""),
        "reference_drawing": str(reference),
        "generated_drawing": str(generated or ""),
        "run_dir": str(run_dir),
        "connection_method": connection_method,
        "connection_probe": connection_probe,
        "reference_metrics": reference_metrics,
        "generated_metrics": generated_metrics,
        "sidecar_artifacts": {
            "reference": reference_metrics.get("sidecar_report"),
            "generated": generated_metrics.get("sidecar_report"),
        },
        "view_match_score": scoring["view_match_score"],
        "dimension_match_score": scoring["dimension_match_score"],
        "titlebar_match_score": scoring["titlebar_match_score"],
        "annotation_match_score": scoring["annotation_match_score"],
        "layout_match_score": scoring["layout_match_score"],
        "overall_score": scoring["overall_score"],
        "status": scoring["status"],
        "differences": scoring["differences"],
        "metric_quality": scoring["metric_quality"],
        "pass": scoring["status"] in {"pass", "pass_with_warning"},
    }
    payload["reasons"] = [d["key"] for d in scoring["differences"] if d.get("severity") in {"fail", "warning", "need_review"}]
    if connection_probe and connection_probe.get("status") != "connected":
        payload["failure_bucket"] = _probe_failure_bucket(connection_probe)
        payload["reasons"].insert(0, payload["failure_bucket"])
    payload["fix_suggestions"] = [d["fix_suggestion"] for d in scoring["differences"] if d.get("fix_suggestion")]
    if payload.get("failure_bucket"):
        payload["fix_suggestions"].insert(0, "保存当前 SolidWorks 文档后重启 SolidWorks，再重新运行参考对比。")
    _write_json(out_path, payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run v3.0 reference drawing comparison smoke.")
    parser.add_argument("--annotation-probe-drawing", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    parser.add_argument("--annotation-probe-out", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    parser.add_argument("--run-dir", default="", help="Run directory. Defaults to drw_output/cad_smoke_v3_0.json run_dir.")
    parser.add_argument("--part", default="", help="Part/assembly path used to locate the same-name reference SLDDRW.")
    parser.add_argument("--cad-smoke", default=str(DEFAULT_CAD_SMOKE), help="CAD smoke report used when --run-dir or --part is omitted.")
    parser.add_argument("--reference-dir", default=str(REPO_ROOT / "3D转2D测试图纸"))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--metrics-mode", choices=["sidecar_first", "sidecar_only", "pywin32_first"], default="sidecar_first",
                        help="Metric extraction strategy. sidecar modes keep SolidWorks COM work in a timeout-bounded subprocess.")
    parser.add_argument("--sidecar-timeout-s", type=int, default=180,
                        help="Timeout for each SwReferenceMetricsSidecar extraction.")
    parser.add_argument("--com-probe-timeout-s", type=float, default=3.0,
                        help="Fast preflight timeout for SolidWorks COM before metric extraction. Use <=0 to disable.")
    args = parser.parse_args()
    if hasattr(args, "annotation_probe_drawing"):
        drawing = Path(args.annotation_probe_drawing)
        if not drawing.is_absolute():
            drawing = (REPO_ROOT / drawing).resolve()
        out_arg = getattr(args, "annotation_probe_out", "")
        out = Path(out_arg) if out_arg else SIDECAR_OUT_DIR / f"{_safe_artifact_label(drawing.stem)}_annotation_probe.json"
        if not out.is_absolute():
            out = (REPO_ROOT / out).resolve()
        payload = _annotation_probe_payload(drawing, out)
        print(json.dumps(payload, ensure_ascii=False))
        return 0 if payload.get("success") else 1

    cad_smoke_path = Path(args.cad_smoke)
    if not cad_smoke_path.is_absolute():
        cad_smoke_path = (REPO_ROOT / cad_smoke_path).resolve()
    cad_smoke = _read_json(cad_smoke_path)
    run_dir = Path(args.run_dir) if args.run_dir else Path(str(cad_smoke.get("run_dir") or ""))
    if not run_dir.is_absolute():
        run_dir = (REPO_ROOT / run_dir).resolve()
    reference_dir = Path(args.reference_dir)
    if not reference_dir.is_absolute():
        reference_dir = (REPO_ROOT / reference_dir).resolve()
    out = Path(args.out)
    if not out.is_absolute():
        out = (REPO_ROOT / out).resolve()
    part = Path(args.part) if args.part else None
    if part is not None and not part.is_absolute():
        part = (REPO_ROOT / part).resolve()

    if not run_dir.exists():
        payload = {
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "mode": "reference_compare_smoke_v3",
            "run_dir": str(run_dir),
            "status": "fail",
            "pass": False,
            "reasons": [f"run_dir not found: {run_dir}"],
            "fix_suggestions": ["Run Real CAD Smoke first."],
        }
        _write_json(out, payload)
        print(json.dumps({"pass": False, "status": "fail", "report": str(out), "reasons": payload["reasons"]}, ensure_ascii=False))
        return 1

    payload = compare(
        run_dir,
        reference_dir,
        out,
        part_path=part,
        cad_smoke_path=cad_smoke_path,
        metrics_mode=args.metrics_mode,
        sidecar_timeout_s=args.sidecar_timeout_s,
        com_probe_timeout_s=args.com_probe_timeout_s,
    )
    print(json.dumps({
        "pass": payload["pass"],
        "status": payload["status"],
        "overall_score": payload["overall_score"],
        "report": str(out),
        "reasons": payload.get("reasons", []),
    }, ensure_ascii=False))
    return 0 if payload["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
