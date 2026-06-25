"""section_helper.py — Multi-strategy section view creator (SW2025 + pywin32)

Public API
----------
create_section_in_active_drawing(sw, drw) -> bool
    Try several strategies to create a horizontal section view "A" on the
    first non-sheet view of the given drawing document. Returns True on
    success, False on any failure. Never raises.

Strategies (tried in order):
  1) drw.EditSheet() -> SketchManager.CreateLine on sheet sketch ->
     Extension.SelectByID2("Line1","SKETCHSEGMENT",...) ->
     CreateSectionViewAt5 with options [6,0,4,2,1,8]
  2) drw.SetEditMode(2)  (swEditModeSheet) -> CreateLine -> select ->
     CreateSectionViewAt5
  3) view.GetSketch() -> CreateLine inside view sketch -> select ->
     CreateSectionViewAt5
  4) drw.InsertSectionView2(sx, sy, "A")  /  drw.InsertCutAlignedSectionView(...)

Diagnostics: each attempt prints
    (strategy, option, line_count, selected_count, view_type, view_obj_is_None)
"""

from __future__ import annotations

import os
import sys
import time
import traceback

import pythoncom
import win32com.client as wc
from win32com.client import VARIANT


SW_COMMANDS_SECTION_VIEW_CANDIDATES = (
    (1543, "swCommands_SectionView"),
    (2421, "swCommands_AlignedSectionView"),
    (2240, "swCommands_DatumFeature"),
)


SECTION_OPTIONS = (6, 0, 4)
EXCL_VARIANT_NAMES = ("VT_EMPTY", "VT_ERROR_PNF", "VT_DISPATCH")


def _empty_dispatch() -> VARIANT:
    return VARIANT(pythoncom.VT_DISPATCH, None)


def _empty_variant() -> VARIANT:
    """VBA-equivalent `Empty` keyword (VT_EMPTY)."""
    return VARIANT(pythoncom.VT_EMPTY, None)


def _activate_sheet_view(drw):
    """Find the type==1 (sheet) view and call ActivateView on it so the
    sheet sketch becomes the implicit drawing target."""
    v = _call(drw, "GetFirstView")
    while v is not None:
        tp = _call(v, "Type")
        if tp == 1:
            nm = _call(v, "GetName2")
            try:
                drw.ActivateView(nm)
                print(f"[section] activated sheet-view '{nm}'", flush=True)
                return v
            except Exception as e:
                print(f"[section] ActivateView('{nm}') exc: {e}", flush=True)
        v = _call(v, "GetNextView")
    sn = _call(drw, "GetSheetNames") or []
    for n in list(sn):
        try:
            drw.ActivateView(n)
            print(f"[section] activated by sheet-name '{n}'", flush=True)
            return None
        except Exception:
            continue
    return None


def _call(o, name, *a):
    """Robust SW COM accessor: getattr then call if callable, else return value.
    Mirrors the pattern used in drw_generate_v4.py."""
    if o is None:
        return None
    try:
        m = getattr(o, name)
    except Exception:
        return None
    try:
        if callable(m):
            return m(*a)
    except Exception:
        return None
    return m


def _find_first_non_sheet_view(drw):
    v = _call(drw, "GetFirstView")
    while v is not None:
        tp = _call(v, "Type")
        if tp is not None and tp != 1:
            return v
        v = _call(v, "GetNextView")
    return None


def _find_views_via_sheets(drw):
    """Fallback enumeration via Sheet.GetViews when GetFirstView fails."""
    out = []
    sn = _call(drw, "GetSheetNames") or []
    for n in list(sn):
        try:
            sheet = drw.Sheet(n) if callable(getattr(drw, "Sheet", None)) \
                else drw.Sheet
        except Exception:
            sheet = None
        if sheet is None:
            try:
                drw.ActivateSheet(n)
                sheet = _call(drw, "GetCurrentSheet")
            except Exception:
                sheet = None
        if sheet is None:
            continue
        views = _call(sheet, "GetViews")
        try:
            views = list(views) if views is not None else []
        except Exception:
            views = []
        for v in views:
            tp = _call(v, "Type")
            nm = _call(v, "GetName2") or "?"
            out.append((tp, nm, v))
    return out


def _list_views(drw):
    out = []
    v = _call(drw, "GetFirstView")
    i = 0
    while v is not None:
        tp = _call(v, "Type")
        nm = _call(v, "GetName2") or "?"
        out.append((i, tp, nm, v))
        v = _call(v, "GetNextView")
        i += 1
    return out


def _get_outline(view):
    outline = _call(view, "GetOutline")
    if outline is None:
        return None
    try:
        return (float(outline[0]), float(outline[1]),
                float(outline[2]), float(outline[3]))
    except Exception:
        return None


def _selected_count(drw):
    try:
        sm = drw.SelectionManager
        n = sm.GetSelectedObjectCount2(-1)
        return int(n)
    except Exception:
        return -1


def _count_sketch_lines(drw):
    """Count sketch segments on the sheet view (type==1) sketch.
    Returns -1 only if GetFirstView itself fails."""
    v = _call(drw, "GetFirstView")
    if v is None:
        return -1
    cnt = 0
    while v is not None:
        tp = _call(v, "Type")
        if tp == 1:
            sk = _call(v, "GetSketch")
            if sk is not None:
                segs = _call(sk, "GetSketchSegments")
                if segs is not None:
                    try:
                        cnt += len(list(segs))
                    except Exception:
                        pass
        v = _call(v, "GetNextView")
    return cnt


def _list_all_views_via_sheet(drw):
    """Enumerate views by scanning all sheets via Sheet.GetViews."""
    out = []
    sn = _call(drw, "GetSheetNames") or []
    for n in list(sn):
        try:
            drw.ActivateSheet(n)
        except Exception:
            pass
        sheet = _call(drw, "GetCurrentSheet")
        views = _call(sheet, "GetViews")
        try:
            views = list(views) if views is not None else []
        except Exception:
            views = []
        for v in views:
            tp = _call(v, "Type")
            nm = _call(v, "GetName2") or "?"
            out.append((tp, nm))
    return out


def _try_create_section_with_options(drw, sx, sy, strategy_id):
    """Try CreateSectionViewAt5 with multiple option flags AND multiple
    forms of the `excludedComponents` argument (VBA `Empty` keyword has no
    direct pywin32 equivalent; we try a few). After every attempt also
    re-scan all sheet views to detect a type==4 view that may have been
    silently created even though COM returned None."""
    DISP_E_PARAMNOTFOUND = -2147352572  # 0x80020004
    excl_variants = [
        ("VT_EMPTY",        _empty_variant()),
        ("VT_ERROR_PNF",    VARIANT(pythoncom.VT_ERROR, DISP_E_PARAMNOTFOUND)),
        ("VT_DISPATCH",     _empty_dispatch()),
    ]
    for opt in SECTION_OPTIONS:
        for excl_name, excl_val in excl_variants:
            sec = None
            exc = None
            try:
                sec = drw.CreateSectionViewAt5(
                    sx, sy, 0.0, "A", int(opt), excl_val, 0)
            except Exception as e:
                exc = e
            line_cnt = _count_sketch_lines(drw)
            sel_cnt = _selected_count(drw)
            vt = None
            if sec is not None:
                try:
                    vt = sec.Type
                except Exception:
                    vt = "?"
            views_after = _list_all_views_via_sheet(drw)
            type4 = sum(1 for t, _ in views_after if t == 4)
            print(f"[section] strategy={strategy_id} opt={opt} "
                  f"excl={excl_name} line_count={line_cnt} "
                  f"selected={sel_cnt} view_type={vt} "
                  f"view_is_None={sec is None} type4_after={type4}"
                  + (f" exc={exc}" if exc else ""), flush=True)
            if sec is not None:
                return sec
            if type4 > 0:
                for t, n in views_after:
                    if t == 4:
                        print(f"[section] silent-success: type=4 view '{n}'",
                              flush=True)
                        return ("__silent__", n)
    return None


def _select_line(drw, line, cx, cy):
    """Select sketch line as section cut line.
    Strategy: keep auto-selection from CreateLine if already selected,
    else SelectByID2 with mark=4 (section line mark), else line.Select4."""
    if _selected_count(drw) >= 1:
        print(f"[section] line auto-selected (selected={_selected_count(drw)})",
              flush=True)
        return True
    callout = _empty_dispatch()
    for mark in (4, 0):
        try:
            ext = drw.Extension
            ok = ext.SelectByID2(
                "Line1", "SKETCHSEGMENT",
                cx, cy, 0.0,
                False, mark, callout, 0,
            )
            if ok and _selected_count(drw) >= 1:
                print(f"[section] SelectByID2 ok mark={mark}", flush=True)
                return True
        except Exception:
            pass
    try:
        if line is not None:
            ok = line.Select4(False, None)
            if ok and _selected_count(drw) >= 1:
                print("[section] line.Select4 ok", flush=True)
                return True
    except Exception:
        pass
    return False


def _strategy_1_edit_sheet(drw, view):
    print("[section] === Strategy 1: EditSheet + sheet sketch ===", flush=True)
    try:
        try:
            drw.ClearSelection2(True)
        except Exception:
            pass
        _activate_sheet_view(drw)
        try:
            drw.EditSheet()
        except Exception as e:
            print(f"[section] s1 EditSheet exc: {e}", flush=True)

        bbox = _get_outline(view)
        if bbox is None:
            print("[section] s1 outline=None", flush=True)
            return None
        xmin, ymin, xmax, ymax = bbox
        cx = (xmin + xmax) / 2.0
        cy = (ymin + ymax) / 2.0
        sx = cx
        sy = ymin - 0.04

        line = None
        try:
            sm = drw.SketchManager
            line = sm.CreateLine(xmin - 0.005, cy, 0.0,
                                 xmax + 0.005, cy, 0.0)
        except Exception as e:
            print(f"[section] s1 CreateLine exc: {e}", flush=True)
            return None
        if line is None:
            print("[section] s1 CreateLine returned None", flush=True)
            return None

        ok_sel = _select_line(drw, line, cx, cy)
        print(f"[section] s1 select_ok={ok_sel} selected={_selected_count(drw)}",
              flush=True)
        if not ok_sel:
            return None

        sec = _try_create_section_with_options(drw, sx, sy, 1)
        if sec is not None:
            return sec
        return None
    except Exception as e:
        print(f"[section] s1 outer exc: {e}", flush=True)
        return None


def _strategy_2_setEditMode(drw, view):
    print("[section] === Strategy 2: SetEditMode(2) + sheet sketch ===",
          flush=True)
    try:
        try:
            drw.ClearSelection2(True)
        except Exception:
            pass
        try:
            ok_em = drw.SetEditMode(2)
            print(f"[section] s2 SetEditMode(2) -> {ok_em}", flush=True)
        except Exception as e:
            print(f"[section] s2 SetEditMode exc: {e}", flush=True)

        bbox = _get_outline(view)
        if bbox is None:
            return None
        xmin, ymin, xmax, ymax = bbox
        cx = (xmin + xmax) / 2.0
        cy = (ymin + ymax) / 2.0
        sx = cx
        sy = ymin - 0.04

        line = None
        try:
            sm = drw.SketchManager
            line = sm.CreateLine(xmin - 0.005, cy, 0.0,
                                 xmax + 0.005, cy, 0.0)
        except Exception as e:
            print(f"[section] s2 CreateLine exc: {e}", flush=True)
            return None
        if line is None:
            print("[section] s2 CreateLine None", flush=True)
            return None

        try:
            drw.ClearSelection2(True)
        except Exception:
            pass

        ok_sel = _select_line(drw, line, cx, cy)
        print(f"[section] s2 select_ok={ok_sel} selected={_selected_count(drw)}",
              flush=True)
        if not ok_sel:
            return None

        return _try_create_section_with_options(drw, sx, sy, 2)
    except Exception as e:
        print(f"[section] s2 outer exc: {e}", flush=True)
        return None


def _strategy_3_view_sketch(drw, view):
    print("[section] === Strategy 3: view.GetSketch() ===", flush=True)
    try:
        try:
            drw.ClearSelection2(True)
        except Exception:
            pass

        bbox = _get_outline(view)
        if bbox is None:
            return None
        xmin, ymin, xmax, ymax = bbox
        cx = (xmin + xmax) / 2.0
        cy = (ymin + ymax) / 2.0
        sx = cx
        sy = ymin - 0.04

        try:
            view.ActivateView(view.GetName2())
        except Exception:
            pass
        try:
            view_sketch = view.GetSketch
            if callable(view_sketch):
                view_sketch = view_sketch()
        except Exception:
            view_sketch = None
        print(f"[section] s3 view_sketch={view_sketch is not None}", flush=True)

        line = None
        try:
            sm = drw.SketchManager
            line = sm.CreateLine(xmin - 0.005, cy, 0.0,
                                 xmax + 0.005, cy, 0.0)
        except Exception as e:
            print(f"[section] s3 CreateLine exc: {e}", flush=True)
            return None
        if line is None:
            print("[section] s3 CreateLine None", flush=True)
            return None

        try:
            drw.ClearSelection2(True)
        except Exception:
            pass

        ok_sel = _select_line(drw, line, cx, cy)
        print(f"[section] s3 select_ok={ok_sel} selected={_selected_count(drw)}",
              flush=True)
        if not ok_sel:
            return None

        return _try_create_section_with_options(drw, sx, sy, 3)
    except Exception as e:
        print(f"[section] s3 outer exc: {e}", flush=True)
        return None


def _strategy_4_legacy_insert(drw, view):
    print("[section] === Strategy 4: legacy InsertSectionView2 ===",
          flush=True)
    bbox = _get_outline(view)
    if bbox is None:
        return None
    xmin, ymin, xmax, ymax = bbox
    cx = (xmin + xmax) / 2.0
    cy = (ymin + ymax) / 2.0
    sx = cx
    sy = ymin - 0.04

    try:
        try:
            drw.EditSheet()
        except Exception:
            pass
        try:
            sm = drw.SketchManager
            line = sm.CreateLine(xmin - 0.005, cy, 0.0,
                                 xmax + 0.005, cy, 0.0)
            print(f"[section] s4 line_created={line is not None}", flush=True)
        except Exception as e:
            print(f"[section] s4 CreateLine exc: {e}", flush=True)
            line = None

        try:
            drw.ClearSelection2(True)
        except Exception:
            pass
        try:
            ext = drw.Extension
            ext.SelectByID2("Line1", "SKETCHSEGMENT",
                            cx, cy, 0.0, False, 4,
                            _empty_dispatch(), 0)
        except Exception:
            pass
    except Exception:
        pass

    sel_cnt = _selected_count(drw)
    print(f"[section] s4 selected={sel_cnt}", flush=True)

    sec = None
    for fn_name in ("InsertSectionView2", "InsertSectionView",
                    "InsertCutAlignedSectionView", "CreateSectionView",
                    "CreateSectionViewAt"):
        try:
            fn = getattr(drw, fn_name, None)
            if fn is None or not callable(fn):
                print(f"[section] s4 {fn_name} not callable", flush=True)
                continue
            sigs = [
                (sx, sy, 0.0, "A", 6),
                (sx, sy, 0.0, "A"),
                (sx, sy, "A"),
                (sx, sy, 0.0),
                (sx, sy),
            ]
            for s in sigs:
                try:
                    sec = fn(*s)
                except Exception as e:
                    last_exc = e
                    sec = None
                if sec is not None:
                    break
            vt = None
            if sec is not None:
                try:
                    vt = sec.Type
                except Exception:
                    vt = "?"
            print(f"[section] s4 {fn_name} -> view_type={vt} "
                  f"is_None={sec is None}", flush=True)
            if sec is not None:
                return sec
        except Exception as e:
            print(f"[section] s4 {fn_name} exc: {e}", flush=True)
    return None


def _strategy_5_force_rebuild(drw, view):
    """Strategy 5: rebuild + force ActiveDoc reattach + CreateSectionViewAt5
    using the same call as VBA but after EditRebuild3."""
    print("[section] === Strategy 5: EditRebuild + CreateSectionViewAt5 ===",
          flush=True)
    try:
        try:
            drw.ClearSelection2(True)
        except Exception:
            pass
        _activate_sheet_view(drw)
        try:
            drw.EditSheet()
        except Exception:
            pass

        bbox = _get_outline(view)
        if bbox is None:
            return None
        xmin, ymin, xmax, ymax = bbox
        cx = (xmin + xmax) / 2.0
        cy = (ymin + ymax) / 2.0
        sx = cx
        sy = ymin - 0.04

        line = None
        try:
            sm = drw.SketchManager
            line = sm.CreateLine(xmin - 0.005, cy, 0.0,
                                 xmax + 0.005, cy, 0.0)
        except Exception as e:
            print(f"[section] s5 CreateLine exc: {e}", flush=True)
            return None
        if line is None:
            return None

        try:
            ok_rb = drw.EditRebuild3()
            print(f"[section] s5 EditRebuild3 -> {ok_rb}", flush=True)
        except Exception as e:
            print(f"[section] s5 EditRebuild3 exc: {e}", flush=True)
        try:
            drw.ForceRebuild3(False)
        except Exception:
            pass

        ok_sel = _select_line(drw, line, cx, cy)
        print(f"[section] s5 select_ok={ok_sel} selected={_selected_count(drw)}",
              flush=True)
        if not ok_sel:
            return None

        return _try_create_section_with_options(drw, sx, sy, 5)
    except Exception as e:
        print(f"[section] s5 outer exc: {e}", flush=True)
        return None


def _strategy_6_runcommand_macro(drw, view):
    """Strategy 6: try sw.RunMacro2 against auto_section.swp (only .swp;
    .bas hangs SW because it's not a valid macro file)."""
    print("[section] === Strategy 6: RunMacro2(auto_section.swp) ===",
          flush=True)
    here = os.path.dirname(os.path.abspath(__file__))
    swp = os.path.join(here, "auto_section.swp")
    if not os.path.exists(swp):
        print(f"[section] s6 no .swp at {swp} (skip — only .bas present, "
              "needs user to compile via SW > Tools > Macro > Save as .swp)",
              flush=True)
        return None
    try:
        sw = wc.GetActiveObject("SldWorks.Application")
        before = _list_all_views_via_sheet(drw)
        before_t4 = sum(1 for t, _ in before if t == 4)
        try:
            res = sw.RunMacro2(swp, "auto_section", "main", 0,
                               VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0))
        except Exception as e:
            print(f"[section] s6 RunMacro2 exc: {e}", flush=True)
            res = None
        print(f"[section] s6 RunMacro2 -> {res}", flush=True)
        after = _list_all_views_via_sheet(drw)
        after_t4 = sum(1 for t, _ in after if t == 4)
        if after_t4 > before_t4:
            print(f"[section] s6 success type4 {before_t4}->{after_t4}",
                  flush=True)
            return ("__silent__", "macro")
    except Exception as e:
        print(f"[section] s6 outer exc: {e}", flush=True)
    return None


def _strategy_7_runcommand_builtin(drw, view):
    """Strategy 7: trigger SolidWorks built-in `Insert > Section View` command
    via sw.RunCommand(commandID, ""). This bypasses the CreateSectionViewAt5
    COM marshalling problem entirely, but is asynchronous and may pop a UI
    dialog. We are tolerant of failure here — if no type=4 view appears we
    simply return None.
    """
    print("[section] === Strategy 7: sw.RunCommand(swCommands_SectionView) ===",
          flush=True)
    try:
        sw = wc.GetActiveObject("SldWorks.Application")
    except Exception as e:
        print(f"[section] s7 GetActiveObject exc: {e}", flush=True)
        return None

    try:
        try:
            sw.SetUserPreferenceToggle(196, True)
        except Exception:
            pass

        try:
            drw.ClearSelection2(True)
        except Exception:
            pass
        _activate_sheet_view(drw)
        try:
            drw.EditSheet()
        except Exception as e:
            print(f"[section] s7 EditSheet exc: {e}", flush=True)

        bbox = _get_outline(view)
        if bbox is None:
            print("[section] s7 outline=None", flush=True)
            return None
        xmin, ymin, xmax, ymax = bbox
        cx = (xmin + xmax) / 2.0
        cy = (ymin + ymax) / 2.0

        line = None
        try:
            sm = drw.SketchManager
            line = sm.CreateLine(xmin - 0.005, cy, 0.0,
                                 xmax + 0.005, cy, 0.0)
        except Exception as e:
            print(f"[section] s7 CreateLine exc: {e}", flush=True)
            return None
        if line is None:
            print("[section] s7 CreateLine None", flush=True)
            return None

        try:
            drw.ClearSelection2(True)
        except Exception:
            pass

        ok_sel = False
        callout = _empty_dispatch()
        try:
            ext = drw.Extension
            ok_sel = bool(ext.SelectByID2(
                "Line1", "SKETCHSEGMENT",
                cx, cy, 0.0,
                False, 1, callout, 0,
            ))
        except Exception as e:
            print(f"[section] s7 SelectByID2 exc: {e}", flush=True)
        if not ok_sel:
            ok_sel = _select_line(drw, line, cx, cy)
        print(f"[section] s7 select_ok={ok_sel} selected={_selected_count(drw)}",
              flush=True)
        if not ok_sel:
            return None

        before = _list_all_views_via_sheet(drw)
        before_t4 = sum(1 for t, _ in before if t == 4)

        for cmd_id, cmd_name in SW_COMMANDS_SECTION_VIEW_CANDIDATES:
            res = None
            exc = None
            try:
                res = sw.RunCommand(int(cmd_id), "")
            except Exception as e:
                exc = e
            print(f"[section] s7 RunCommand({cmd_id}={cmd_name}) -> {res}"
                  + (f" exc={exc}" if exc else ""), flush=True)
            try:
                time.sleep(1.5)
            except Exception:
                pass
            try:
                drw.ClearSelection2(True)
            except Exception:
                pass
            after = _list_all_views_via_sheet(drw)
            after_t4 = sum(1 for t, _ in after if t == 4)
            print(f"[section] s7 cmd={cmd_id} type4 {before_t4}->{after_t4}",
                  flush=True)
            if after_t4 > before_t4:
                for t, n in after:
                    if t == 4:
                        print(f"[section] s7 success via cmd={cmd_id} "
                              f"({cmd_name}) view='{n}'", flush=True)
                        return ("__silent__", n)
            try:
                ext = drw.Extension
                ext.SelectByID2(
                    "Line1", "SKETCHSEGMENT",
                    cx, cy, 0.0,
                    False, 1, callout, 0,
                )
            except Exception:
                pass
        return None
    except Exception as e:
        print(f"[section] s7 outer exc: {e}", flush=True)
        return None


def fallback_create_section_via_section_command(sw, drw):
    """Standalone fallback: select a horizontal sketch segment on the first
    non-sheet view's mid-line and then call sw.RunCommand for each known
    Section View command id. Returns True if a type=4 view appears, else
    False. Never raises.
    """
    try:
        if drw is None or sw is None:
            return False
        try:
            sw.SetUserPreferenceToggle(196, True)
        except Exception:
            pass
        try:
            drw.ClearSelection2(True)
        except Exception:
            pass
        _activate_sheet_view(drw)
        try:
            drw.EditSheet()
        except Exception:
            pass
        view = _find_first_non_sheet_view(drw)
        if view is None:
            sheet_views = _find_views_via_sheets(drw)
            for tp, _nm, v in sheet_views:
                if tp is not None and tp != 1:
                    view = v
                    break
        if view is None:
            print("[section] fallback: no non-sheet view", flush=True)
            return False
        bbox = _get_outline(view)
        if bbox is None:
            return False
        xmin, ymin, xmax, ymax = bbox
        cx = (xmin + xmax) / 2.0
        cy = (ymin + ymax) / 2.0
        try:
            sm = drw.SketchManager
            line = sm.CreateLine(xmin - 0.005, cy, 0.0,
                                 xmax + 0.005, cy, 0.0)
        except Exception:
            line = None
        if line is None:
            return False
        try:
            drw.ClearSelection2(True)
        except Exception:
            pass
        callout = _empty_dispatch()
        ok_sel = False
        try:
            ext = drw.Extension
            ok_sel = bool(ext.SelectByID2(
                "Line1", "SKETCHSEGMENT",
                cx, cy, 0.0, False, 1, callout, 0,
            ))
        except Exception:
            ok_sel = False
        if not ok_sel:
            ok_sel = _select_line(drw, line, cx, cy)
        if not ok_sel:
            print("[section] fallback: select failed", flush=True)
            return False
        before = _list_all_views_via_sheet(drw)
        before_t4 = sum(1 for t, _ in before if t == 4)
        for cmd_id, cmd_name in SW_COMMANDS_SECTION_VIEW_CANDIDATES:
            try:
                sw.RunCommand(int(cmd_id), "")
            except Exception as e:
                print(f"[section] fallback RunCommand({cmd_id}) exc: {e}",
                      flush=True)
                continue
            try:
                time.sleep(1.5)
            except Exception:
                pass
            try:
                drw.ClearSelection2(True)
            except Exception:
                pass
            after = _list_all_views_via_sheet(drw)
            after_t4 = sum(1 for t, _ in after if t == 4)
            print(f"[section] fallback cmd={cmd_id}({cmd_name}) type4 "
                  f"{before_t4}->{after_t4}", flush=True)
            if after_t4 > before_t4:
                return True
            try:
                ext = drw.Extension
                ext.SelectByID2(
                    "Line1", "SKETCHSEGMENT",
                    cx, cy, 0.0, False, 1, callout, 0,
                )
            except Exception:
                pass
        return False
    except Exception as e:
        print(f"[section] fallback outer exc: {e}", flush=True)
        return False


def _cleanup_temp_sketch(drw):
    try:
        drw.ClearSelection2(True)
    except Exception:
        pass
    try:
        drw.SetEditMode(2)
    except Exception:
        pass
    try:
        drw.EditSheet()
    except Exception:
        pass


def create_section_in_active_drawing(sw, drw) -> bool:
    """Multi-strategy section creator. Never raises; returns True/False."""
    try:
        if drw is None:
            print("[section] drw is None", flush=True)
            return False

        try:
            tp = drw.GetType
            if callable(tp):
                tp = tp()
        except Exception:
            tp = None
        if tp != 3:
            print(f"[section] active doc is not a drawing (type={tp})",
                  flush=True)
            return False

        try:
            drw.ClearSelection2(True)
        except Exception:
            pass
        try:
            drw.EditSheet()
            print("[section] called drw.EditSheet() at entry", flush=True)
        except Exception as e:
            print(f"[section] entry EditSheet exc: {e}", flush=True)
        try:
            sn = _call(drw, "GetSheetNames") or []
            if sn:
                drw.ActivateSheet(list(sn)[0])
                print(f"[section] activated sheet {list(sn)[0]}", flush=True)
        except Exception:
            pass

        view = _find_first_non_sheet_view(drw)
        if view is None:
            print("[section] GetFirstView path found nothing, "
                  "trying Sheet.GetViews fallback...", flush=True)
            sheet_views = _find_views_via_sheets(drw)
            print(f"[section] sheet_views_count={len(sheet_views)}",
                  flush=True)
            for tp, nm, v in sheet_views:
                print(f"  sheet_view type={tp} name={nm}", flush=True)
                if tp is not None and tp != 1 and view is None:
                    view = v
        if view is None:
            print("[section] no non-sheet view found", flush=True)
            return False
        try:
            print(f"[section] target view name={_call(view, 'GetName2')} "
                  f"type={_call(view, 'Type')}", flush=True)
        except Exception:
            pass

        before_views = [(t, n) for (_, t, n, _) in _list_views(drw)]

        for strat_fn in (
            _strategy_1_edit_sheet,
            _strategy_2_setEditMode,
            _strategy_3_view_sketch,
            _strategy_4_legacy_insert,
            _strategy_5_force_rebuild,
            _strategy_6_runcommand_macro,
            _strategy_7_runcommand_builtin,
        ):
            try:
                sec = strat_fn(drw, view)
            except Exception as e:
                print(f"[section] {strat_fn.__name__} unhandled exc: {e}",
                      flush=True)
                sec = None
            if sec is not None:
                if isinstance(sec, tuple) and sec and sec[0] == "__silent__":
                    print(f"[section] SUCCESS via {strat_fn.__name__} "
                          f"(silent, view='{sec[1]}')", flush=True)
                    return True
                try:
                    vt = sec.Type
                except Exception:
                    vt = "?"
                print(f"[section] SUCCESS via {strat_fn.__name__} "
                      f"view_type={vt}", flush=True)
                return True
            _cleanup_temp_sketch(drw)

        after_views = [(t, n) for (_, t, n, _) in _list_views(drw)]
        new_section = any(t == 4 for t, _ in after_views) and \
                      after_views != before_views
        if new_section:
            print("[section] late-detected type=4 view, treating as success",
                  flush=True)
            return True

        print("[section] all strategies failed", flush=True)
        return False
    except pythoncom.com_error as e:
        print(f"[section] com_error: {e}", flush=True)
        return False
    except Exception as e:
        print(f"[section] unexpected error: {e}\n{traceback.format_exc()}",
              flush=True)
        return False


if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)
    print("[section] connecting to SolidWorks...", flush=True)
    try:
        sw = wc.GetActiveObject("SldWorks.Application")
    except Exception as e:
        print(f"[section] GetActiveObject failed: {e}", flush=True)
        sys.exit(1)

    drw = sw.ActiveDoc
    try:
        _gt = drw.GetType
        gt_val = _gt() if callable(_gt) else _gt
    except Exception:
        gt_val = None
    print(f"[section] Before: drw_type={gt_val}", flush=True)

    ok = create_section_in_active_drawing(sw, drw)
    print(f"[section] create_section -> {ok}", flush=True)

    if drw is not None:
        try:
            v = drw.GetFirstView
            if callable(v):
                v = v()
        except Exception:
            v = None
        i = 0
        while v is not None:
            try:
                tp = v.Type
            except Exception:
                tp = "?"
            try:
                nm = v.GetName2()
            except Exception:
                nm = "?"
            print(f"  view[{i}] type={tp} name={nm}", flush=True)
            try:
                nxt = v.GetNextView
                if callable(nxt):
                    nxt = nxt()
            except Exception:
                nxt = None
            v = nxt
            i += 1
