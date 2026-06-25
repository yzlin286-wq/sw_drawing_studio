"""Probe SolidWorks drawing dimension APIs on a copied SLDDRW.

This validation helper is intentionally outside the desktop UI path. It opens a
copy of a generated drawing, tries bounded IDrawingDoc.AutoDimension calls on
real drawing views, and records before/after/reopen DisplayDimension evidence.
It never modifies the source drawing passed on the command line.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_DIR = REPO_ROOT / "drw_output" / "_dim_probe"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.validation.reference_compare_smoke_v3 import (  # noqa: E402
    _collect_views,
    _count_display_dim_annotation_items,
    _count_display_dim_annotations,
    _count_display_dims,
    _open_metrics,
    _safe_value,
    _view_outline,
)


DOC_TYPE_DRAWING = 3
OPEN_SILENT = 1
SAVE_SILENT = 1

AUTODIM_CANDIDATES: list[tuple[str, tuple[int, int, int, int, int]]] = [
    # entities, horizontal scheme, horizontal placement, vertical scheme,
    # vertical placement. Values follow SOLIDWORKS swAutodim* enums.
    ("preselect_baseline_above_right", (0, 1, 1, 1, 1)),
    ("all_baseline_above_right", (1, 1, 1, 1, 1)),
    ("selected_baseline_above_right", (2, 1, 1, 1, 1)),
    ("preselect_baseline_below_left", (0, 1, -1, 1, -1)),
    ("preselect_ordinate_above_right", (0, 2, 1, 2, 1)),
]


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _timestamp() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def _connect_sw(*, allow_dispatch: bool = False) -> tuple[Any | None, str, str]:
    from app.services.solidworks_global_lock import require_current_job_lock

    guard = require_current_job_lock("dimension_api_probe_v3.connect_sw")
    if not guard.get("ok"):
        return (
            None,
            "blocked_by_solidworks_lock",
            json.dumps({
                "reason": guard.get("reason", ""),
                "owner": guard.get("owner", {}),
                "fix_suggestion": guard.get("fix_suggestion", ""),
            }, ensure_ascii=False),
        )
    import win32com.client as wc

    try:
        return wc.GetActiveObject("SldWorks.Application"), "get_active_object", ""
    except Exception as exc:
        if not allow_dispatch:
            return None, "get_active_object", str(exc)
    try:
        return wc.Dispatch("SldWorks.Application"), "dispatch", ""
    except Exception as exc:
        return None, "dispatch", str(exc)


def _variant_i4(value: int = 0) -> Any:
    import pythoncom
    from win32com.client import VARIANT

    return VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, int(value))


def _open_drawing(sw: Any, path: Path) -> tuple[Any | None, dict[str, Any]]:
    errors = _variant_i4()
    warnings = _variant_i4()
    info: dict[str, Any] = {
        "path": str(path),
        "errors": None,
        "warnings": None,
        "reason": "",
    }
    try:
        doc = sw.OpenDoc6(str(path), DOC_TYPE_DRAWING, OPEN_SILENT, "", errors, warnings)
        info["errors"] = int(errors.value)
        info["warnings"] = int(warnings.value)
        if doc is None:
            info["reason"] = "OpenDoc6 returned None"
        return doc, info
    except Exception as exc:
        info["reason"] = str(exc)
        return None, info


def _close_doc(sw: Any, doc: Any | None, path: Path) -> None:
    if doc is None:
        return
    title = str(_safe_value(doc, "GetTitle", "") or path.name)
    for candidate in (title, path.name, str(path)):
        try:
            sw.CloseDoc(candidate)
            return
        except Exception:
            pass


def _save_doc(doc: Any) -> dict[str, Any]:
    errors = _variant_i4()
    warnings = _variant_i4()
    result: dict[str, Any] = {
        "success": False,
        "errors": None,
        "warnings": None,
        "reason": "",
    }
    try:
        saved = doc.Save3(SAVE_SILENT, errors, warnings)
        result.update({
            "success": bool(saved),
            "errors": int(errors.value),
            "warnings": int(warnings.value),
        })
    except Exception as exc:
        result["reason"] = str(exc)
        try:
            saved = doc.Save()
            result["success"] = bool(saved)
            result["reason"] = result["reason"] or "Save3 failed; Save fallback used"
        except Exception as fallback_exc:
            result["reason"] = f"{result['reason']}; Save fallback failed: {fallback_exc}"
    return result


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    try:
        return list(value)
    except Exception:
        return [value]


def _current_sheet(doc: Any) -> Any | None:
    return _safe_value(doc, "GetCurrentSheet")


def _sheet_name(sheet: Any | None) -> str:
    return str(_safe_value(sheet, "Name", "") or "")


def _view_name(view: Any) -> str:
    return str(_safe_value(view, "Name", "") or "")


def _view_type(view: Any) -> str:
    return str(_safe_value(view, "Type", "") or "")


def _is_sheet_pseudo_view(view: Any) -> bool:
    name = _view_name(view).lower()
    view_type = _view_type(view)
    if view_type in {"0", "1"} and (name.startswith("sheet") or name.startswith("图纸")):
        return True
    outline = _view_outline(view)
    return bool(view_type == "1" and len(outline) >= 4 and outline[2] >= 0.25 and outline[3] >= 0.18)


def _view_position(view: Any) -> tuple[float, float]:
    try:
        values = _as_list(_safe_value(view, "Position"))
        if len(values) >= 2:
            return float(values[0]), float(values[1])
    except Exception:
        pass
    outline = _view_outline(view)
    if len(outline) >= 4:
        return (float(outline[0]) + float(outline[2])) / 2.0, (float(outline[1]) + float(outline[3])) / 2.0
    return 0.0, 0.0


def _clear_selection(doc: Any) -> None:
    for method_name, args in (
        ("ClearSelection2", (True,)),
        ("ClearSelection", ()),
    ):
        try:
            method = getattr(doc, method_name)
            method(*args)
            return
        except Exception:
            pass


def _select_view(doc: Any, view: Any, sheet_name: str) -> dict[str, Any]:
    name = _view_name(view)
    px, py = _view_position(view)
    attempts: list[dict[str, Any]] = []

    _clear_selection(doc)
    try:
        if name and callable(getattr(doc, "ActivateView", None)):
            attempts.append({"method": "ActivateView", "ok": bool(doc.ActivateView(name))})
    except Exception as exc:
        attempts.append({"method": "ActivateView", "ok": False, "reason": str(exc)})
    try:
        doc.ActiveDrawingView = view
        attempts.append({"method": "ActiveDrawingView", "ok": True})
    except Exception as exc:
        attempts.append({"method": "ActiveDrawingView", "ok": False, "reason": str(exc)})

    for feature_method in ("GetFeature", "IGetFeature"):
        try:
            feature = getattr(view, feature_method)()
        except Exception as exc:
            attempts.append({"method": feature_method, "ok": False, "reason": str(exc)})
            continue
        for select_method, args in (
            ("Select2", (False, 0)),
            ("Select", (False,)),
            ("Select", ()),
        ):
            try:
                method = getattr(feature, select_method, None)
                if not callable(method):
                    continue
                selected = method(*args)
                ok = bool(selected)
                attempts.append({
                    "method": f"{feature_method}.{select_method}",
                    "args": list(args),
                    "ok": ok,
                    "returned": str(selected),
                })
                if ok:
                    return {"success": True, "method": f"{feature_method}.{select_method}", "attempts": attempts}
            except Exception as exc:
                attempts.append({
                    "method": f"{feature_method}.{select_method}",
                    "args": list(args),
                    "ok": False,
                    "reason": str(exc),
                })

    for method_name, args in (
        ("Select", (False,)),
        ("Select", (True,)),
        ("Select", ()),
        ("Select2", (False, 0)),
        ("Select2", (True, 0)),
    ):
        try:
            method = getattr(view, method_name, None)
            if not callable(method):
                continue
            selected = method(*args)
            ok = selected is not False
            attempts.append({"method": method_name, "args": list(args), "ok": bool(ok), "returned": str(selected)})
            if ok:
                return {"success": True, "method": method_name, "attempts": attempts}
        except Exception as exc:
            attempts.append({"method": method_name, "args": list(args), "ok": False, "reason": str(exc)})

    name_candidates = [candidate for candidate in (name, f"{name}@{sheet_name}" if name and sheet_name else "") if candidate]
    try:
        ext = getattr(doc, "Extension")
    except Exception:
        ext = None
    try:
        import pythoncom
        from win32com.client import VARIANT

        callout_variants = [
            ("None", None),
            ("Empty", pythoncom.Empty),
            ("Missing", pythoncom.Missing),
            ("VT_DISPATCH_None", VARIANT(pythoncom.VT_DISPATCH, None)),
            ("VT_UNKNOWN_None", VARIANT(pythoncom.VT_UNKNOWN, None)),
        ]
    except Exception:
        callout_variants = [("None", None)]
    for candidate_name in name_candidates:
        for select_type in ("DRAWINGVIEW", ""):
            for x_sel, y_sel in ((px, py), (0.0, 0.0)):
                for callout_label, callout in callout_variants:
                    try:
                        if ext is None:
                            raise RuntimeError("ModelDoc2.Extension unavailable")
                        selected = ext.SelectByID2(
                            candidate_name,
                            select_type,
                            float(x_sel),
                            float(y_sel),
                            0.0,
                            False,
                            0,
                            callout,
                            0,
                        )
                        ok = bool(selected)
                        attempts.append({
                            "method": "Extension.SelectByID2",
                            "name": candidate_name,
                            "type": select_type,
                            "point": [x_sel, y_sel],
                            "callout": callout_label,
                            "ok": ok,
                        })
                        if ok:
                            return {"success": True, "method": "Extension.SelectByID2", "attempts": attempts}
                    except Exception as exc:
                        attempts.append({
                            "method": "Extension.SelectByID2",
                            "name": candidate_name,
                            "type": select_type,
                            "point": [x_sel, y_sel],
                            "callout": callout_label,
                            "ok": False,
                            "reason": str(exc),
                        })
    return {"success": False, "method": "", "attempts": attempts}


def _collect_open_metrics(doc: Any) -> dict[str, Any]:
    sheet = _current_sheet(doc)
    views = _collect_views(doc, sheet)
    view_items: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    display_dim_count = 0
    display_dim_annotation_count = 0
    for view in views:
        name = _view_name(view)
        view_type = _view_type(view)
        outline = _view_outline(view)
        if _is_sheet_pseudo_view(view):
            continue
        if not outline and (not view_type or view_type == "0"):
            continue
        key = (name, view_type, json.dumps(outline, ensure_ascii=False))
        if key in seen:
            continue
        seen.add(key)
        dim_count = _count_display_dims(view)
        annotation_dim_count = _count_display_dim_annotations(view)
        display_dim_count += dim_count
        display_dim_annotation_count += annotation_dim_count
        view_items.append({
            "name": name,
            "type": view_type,
            "outline": outline,
            "display_dim_count": dim_count,
            "display_dim_annotation_count": annotation_dim_count,
        })
    display_dim_annotation_count = max(
        display_dim_annotation_count,
        _count_display_dim_annotation_items(_safe_value(doc, "GetAnnotations")),
    )
    return {
        "sheet_name": _sheet_name(sheet),
        "view_count": len(view_items),
        "views": view_items,
        "display_dim_count": display_dim_count,
        "display_dim_annotation_count": display_dim_annotation_count,
        "annotation_count": len(_as_list(_safe_value(doc, "GetAnnotations"))),
    }


def _dimension_signal(metrics: dict[str, Any]) -> int:
    return max(
        int(metrics.get("display_dim_count") or 0),
        int(metrics.get("display_dim_annotation_count") or 0),
    )


def _reopen_metrics(sw: Any, path: Path) -> dict[str, Any]:
    metrics = _open_metrics(sw, path)
    return {
        "success": bool(metrics.get("success")),
        "reason": metrics.get("reason", ""),
        "open_errors": metrics.get("open_errors"),
        "open_warnings": metrics.get("open_warnings"),
        "view_count": int(metrics.get("view_count") or 0),
        "display_dim_count": int(metrics.get("display_dim_count") or 0),
        "display_dim_annotation_count": int(metrics.get("display_dim_annotation_count") or 0),
        "display_dim_count_source": metrics.get("display_dim_count_source", ""),
        "annotation_count": int(metrics.get("annotation_count") or 0),
    }


def run_probe(
    drawing: Path,
    out_dir: Path,
    *,
    target_display_dim_count: int,
    max_views: int,
    allow_dispatch: bool,
) -> dict[str, Any]:
    import pythoncom

    pythoncom.CoInitialize()
    started = time.time()
    out_dir.mkdir(parents=True, exist_ok=True)
    probe_dir = out_dir / f"{drawing.stem}_autodim_{_timestamp()}"
    probe_dir.mkdir(parents=True, exist_ok=False)
    probe_drawing = probe_dir / f"{drawing.stem}_autodim_probe{drawing.suffix}"
    shutil.copy2(drawing, probe_drawing)

    result: dict[str, Any] = {
        "tool": "dimension_api_probe_v3",
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "source_drawing": str(drawing),
        "probe_drawing": str(probe_drawing),
        "target_display_dim_count": int(target_display_dim_count),
        "max_views": int(max_views),
        "success": False,
        "status": "fail",
        "reason": "",
        "connection": {},
        "open": {},
        "before_metrics": {},
        "attempts": [],
        "after_metrics": {},
        "save": {},
        "reopened_metrics": {},
        "elapsed_s": 0.0,
    }

    sw, method, reason = _connect_sw(allow_dispatch=allow_dispatch)
    result["connection"] = {"method": method, "success": sw is not None, "reason": reason}
    if sw is None:
        result["reason"] = "solidworks_not_connected"
        result["elapsed_s"] = round(time.time() - started, 3)
        return result

    doc = None
    try:
        doc, open_info = _open_drawing(sw, probe_drawing)
        result["open"] = open_info
        if doc is None:
            result["reason"] = "open_probe_drawing_failed"
            return result

        before_metrics = _collect_open_metrics(doc)
        result["before_metrics"] = before_metrics
        before_signal = _dimension_signal(before_metrics)
        sheet_name = str(before_metrics.get("sheet_name") or "")
        current_signal = before_signal

        candidate_views = [
            view
            for view in _collect_views(doc, _current_sheet(doc))
            if not _is_sheet_pseudo_view(view) and (_view_outline(view) or (_view_type(view) and _view_type(view) != "0"))
        ]
        seen_views: set[tuple[str, str, str]] = set()
        unique_views: list[Any] = []
        for view in candidate_views:
            key = (_view_name(view), _view_type(view), json.dumps(_view_outline(view), ensure_ascii=False))
            if key in seen_views:
                continue
            seen_views.add(key)
            unique_views.append(view)

        for view_index, view in enumerate(unique_views[:max_views]):
            view_info = {
                "view_index": view_index,
                "view_name": _view_name(view),
                "view_type": _view_type(view),
                "outline": _view_outline(view),
                "selection": {},
                "candidate_results": [],
            }
            selection = _select_view(doc, view, sheet_name)
            view_info["selection"] = selection
            if not selection.get("success"):
                result["attempts"].append(view_info)
                continue

            for label, args in AUTODIM_CANDIDATES:
                before_call = _collect_open_metrics(doc)
                before_call_signal = _dimension_signal(before_call)
                try:
                    returned = doc.AutoDimension(*args)
                    call_result: dict[str, Any] = {
                        "label": label,
                        "args": list(args),
                        "success": True,
                        "returned": str(returned),
                    }
                except Exception as exc:
                    call_result = {
                        "label": label,
                        "args": list(args),
                        "success": False,
                        "reason": str(exc),
                    }

                after_call = _collect_open_metrics(doc)
                after_call_signal = _dimension_signal(after_call)
                call_result.update({
                    "before_signal": before_call_signal,
                    "after_signal": after_call_signal,
                    "delta_signal": after_call_signal - before_call_signal,
                    "after_metrics": {
                        "display_dim_count": after_call.get("display_dim_count", 0),
                        "display_dim_annotation_count": after_call.get("display_dim_annotation_count", 0),
                    },
                })
                view_info["candidate_results"].append(call_result)
                current_signal = max(current_signal, after_call_signal)
                if target_display_dim_count > 0 and current_signal >= target_display_dim_count:
                    break
                _select_view(doc, view, sheet_name)

            result["attempts"].append(view_info)
            if target_display_dim_count > 0 and current_signal >= target_display_dim_count:
                break

        result["after_metrics"] = _collect_open_metrics(doc)
        result["save"] = _save_doc(doc)
    finally:
        _close_doc(sw, doc, probe_drawing)

    result["reopened_metrics"] = _reopen_metrics(sw, probe_drawing)
    reopened_signal = _dimension_signal(result["reopened_metrics"])
    before_signal = _dimension_signal(result.get("before_metrics") or {})
    result["success"] = reopened_signal > before_signal
    if target_display_dim_count > 0 and reopened_signal >= target_display_dim_count:
        result["status"] = "pass"
        result["reason"] = ""
    elif result["success"]:
        result["status"] = "pass_with_warning"
        result["reason"] = "autodimension_increased_display_dim_but_below_target"
    else:
        result["status"] = "fail"
        result["reason"] = "autodimension_did_not_increase_persisted_display_dim"
    result["elapsed_s"] = round(time.time() - started, 3)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--drawing", required=True, type=Path, help="Generated SLDDRW to copy and probe.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--target-display-dim-count", type=int, default=12)
    parser.add_argument("--max-views", type=int, default=4)
    parser.add_argument("--allow-dispatch", action="store_true")
    args = parser.parse_args(argv)

    drawing = args.drawing
    if not drawing.is_absolute():
        drawing = (REPO_ROOT / drawing).resolve()
    out_dir = args.out_dir
    if not out_dir.is_absolute():
        out_dir = (REPO_ROOT / out_dir).resolve()
    out_path = args.out
    if out_path is not None and not out_path.is_absolute():
        out_path = (REPO_ROOT / out_path).resolve()

    if not drawing.exists():
        payload = {
            "tool": "dimension_api_probe_v3",
            "success": False,
            "status": "fail",
            "reason": "drawing_not_found",
            "source_drawing": str(drawing),
        }
        if out_path:
            _write_json(out_path, payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 2

    payload = run_probe(
        drawing,
        out_dir,
        target_display_dim_count=args.target_display_dim_count,
        max_views=args.max_views,
        allow_dispatch=bool(args.allow_dispatch),
    )
    if out_path is None:
        out_path = Path(payload["probe_drawing"]).with_name("dimension_api_probe_v3.json")
    _write_json(out_path, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
