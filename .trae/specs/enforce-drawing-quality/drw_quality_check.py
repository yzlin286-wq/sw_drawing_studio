"""
drw_quality_check.py — 对单张 SLDDRW 做 12 项渲染级质检并产出 JSON

接口：
    quality_check(sldddrw_path, sw=None, baseline_avg_dim=21.1, baseline_avg_centermark=10) -> dict

返回字段：
    {
      "file": ...,
      "pass": bool,                  # 12 项是否全过
      "score_pass_count": int,       # 通过项数
      "issues": [...],               # 失败项的简述
      "checks": {                    # 12 项详情
          "view_overlap": {...}, ...
      }
    }

CLI:
    python drw_quality_check.py [SLDDRW 路径]
默认对 c:\\Users\\Vision\\Desktop\\SW 相关\\drw_output\\LB26001-A-04-001_v4.SLDDRW

12 项质检：
  1.  view_overlap         非 sheet 视图 outline 两两不相交
  2.  view_in_frame        所有视图 outline 位于 [0.010,0.010,0.287,0.200] 图框内
  3.  front_view_position  含"前视"/"Front"视图的中心 cx∈[40,180]mm, cy∈[80,180]mm
  4.  scale_in_set         sheet.scale ∈ {(5,1),(3,1),(2,1),(1,1),(1,2),(1,3),(1,4),(1,5)}
  5.  text_height_ge_3_5mm  GetUserPreferenceDoubleValue(89) ≥ 0.0035
  6.  all_13_keys_present  13 个 PROP_KEYS 全部在 cpm.GetNames
  7.  dim_count_sufficient  ΣDisplayDim ≥ 0.5 × baseline_avg_dim
  8.  centermark_count_sufficient ΣCenterMark ≥ 0.5 × baseline_avg_centermark
  9.  has_tech_note         NoteBlock 总数 > 4 (启发式)
  10. has_ra_note           同上 NoteBlock > 4
  11. has_datum_a           同上 NoteBlock > 4
  12. refdoc_correct        每个 type∈{4,7} 视图 GetReferencedDocument 不为空且 path 非空
"""
import os
import re
import sys
import json
import time
import traceback
from collections import Counter
from pathlib import Path

import pythoncom
import win32com.client as wc
from win32com.client import VARIANT

sys.stdout.reconfigure(line_buffering=True)

_SCRIPT_PATH = Path(__file__).resolve()
_BUNDLE_ROOT = Path(os.environ.get("SW_DRAWING_STUDIO_BUNDLE_ROOT", _SCRIPT_PATH.parent.parent.parent.parent)).resolve()
_RUNTIME_ROOT = Path(os.environ.get("SW_DRAWING_STUDIO_RUNTIME_ROOT", _BUNDLE_ROOT)).resolve()


def log(*a, **kw):
    print(*a, **kw, flush=True)


def _dynamic_dispatch(obj):
    try:
        return wc.dynamic.Dispatch(obj)
    except Exception:
        return obj


def _ensure_solidworks_global_lock(operation, part_path=""):
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
            "part_path": str(part_path or ""),
            "reason": guard.get("reason", ""),
            "owner": guard.get("owner", {}),
            "fix_suggestion": guard.get("fix_suggestion", ""),
        }, ensure_ascii=False)
    )


PROP_KEYS = [
    "SWFormatSize", "机型", "品名", "图号", "类别", "数量",
    "材质", "表面处理", "设计", "日期",
    "UNIT_OF_MEASURE", "Material", "重量",
]

ANN_TYPE_NAME = {
    1: "DisplayDim", 2: "Note", 3: "GTOL", 4: "DatumTag", 5: "Balloon",
    6: "NoteBlock", 7: "View", 8: "WeldSym", 9: "SurfFinish",
    10: "DimDot", 13: "CenterMark", 14: "BlockInst", 15: "AreaHatch",
    16: "DimLine", 17: "DatumTarget",
}

GOOD_SCALES = {
    (5, 1), (2, 1), (1, 1),
    (1, 2), (1, 5), (1, 10), (1, 20), (1, 50), (1, 100),
    (10, 1), (20, 1), (50, 1),
}
FRAME = (0.010, 0.010, 0.287, 0.200)  # xmin, ymin, xmax, ymax


GB_RULE_TOGGLES = {
    "gb_titlebar_complete": True,
    "gb_font_is_changfangsong": True,
    "gb_paper_size_correct": True,
    "gb_has_section_view_or_skipped": True,
    "gb_scale_in_extended_set": True,
}
GB_REQUIRE_SECTION = True

GB_TITLEBAR_REQUIRED_GROUPS = [
    ("品名", "机型"),
    ("图号",),
    ("材质", "Material"),
    ("数量",),
    ("设计",),
    ("日期",),
]

GB_PAPER_SIZES_M = {
    "A0_L": (1.189, 0.841),
    "A0_P": (0.841, 1.189),
    "A1_L": (0.841, 0.594),
    "A1_P": (0.594, 0.841),
    "A2_L": (0.594, 0.420),
    "A2_P": (0.420, 0.594),
    "A3_L": (0.420, 0.297),
    "A3_P": (0.297, 0.420),
    "A4_L": (0.297, 0.210),
    "A4_P": (0.210, 0.297),
}


def call(o, name, *args):
    """兼容属性/方法双态"""
    if o is None:
        return None
    try:
        m = getattr(o, name)
    except Exception:
        return None
    try:
        if args:
            return m(*args) if callable(m) else m
        if callable(m):
            try:
                return m()
            except TypeError:
                return m
        return m
    except Exception:
        try:
            return m
        except Exception:
            return None


def to_list(v):
    if v is None:
        return []
    try:
        return list(v)
    except Exception:
        return [v]


def _aabb(outline):
    """outline = [x1,y1,x2,y2] → 规范化为 (xmin,ymin,xmax,ymax)"""
    if not outline or len(outline) < 4:
        return None
    try:
        x1, y1, x2, y2 = float(outline[0]), float(outline[1]), float(outline[2]), float(outline[3])
    except Exception:
        return None
    return (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))


def _rect_intersect(a, b, eps=1e-6):
    """两 AABB 是否相交 (严格相交，相切不算)"""
    if not a or not b:
        return False
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    if ax2 <= bx1 + eps or bx2 <= ax1 + eps:
        return False
    if ay2 <= by1 + eps or by2 <= ay1 + eps:
        return False
    return True


def _rect_in_frame(a, frame=FRAME, eps=1e-6):
    if not a:
        return False
    ax1, ay1, ax2, ay2 = a
    fx1, fy1, fx2, fy2 = frame
    return (ax1 >= fx1 - eps and ay1 >= fy1 - eps
            and ax2 <= fx2 + eps and ay2 <= fy2 + eps)


def _extract_note_text(annotation) -> str:
    """Read SolidWorks Note text through several COM surfaces."""
    candidates = [annotation]
    for attr in ("GetSpecificAnnotation", "GetSpecificAnnotation2", "Note"):
        try:
            obj = getattr(annotation, attr, None)
            if callable(obj):
                obj = obj()
            if obj is not None:
                candidates.append(obj)
        except Exception:
            pass

    for obj in candidates:
        for name in ("GetText", "GetText2", "Text"):
            try:
                value = getattr(obj, name, None)
                if callable(value):
                    value = value()
                if value:
                    return str(value)
            except Exception:
                pass
        try:
            value = str(obj)
            if value and not value.startswith("<"):
                return value
        except Exception:
            pass
    return ""


def _open_drw(sw, path):
    sw = _dynamic_dispatch(sw)
    e = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    w = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    drw = sw.OpenDoc6(path, 3, 1 | 16 | 256, "", e, w)
    return drw


def _open_doc_with_retry(sw, slddrw_path, max_attempts=3):
    sw = _dynamic_dispatch(sw)
    """对 OpenDoc6 做 retry，缓解 SW2025 marshaling 偶发返回 None。"""
    err = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    warn = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    last = None
    for i in range(max_attempts):
        try:
            sw.SetUserPreferenceIntegerValue(9, 1)
        except Exception:
            pass
        err.value = 0
        warn.value = 0
        m = sw.OpenDoc6(str(slddrw_path), 3, 257, "", err, warn)
        if m is not None:
            return m
        last = (err.value, warn.value)
        log(f"[quality_check] OpenDoc6 attempt {i+1} returned None, err/warn={last}")
        time.sleep(2.0 + i * 1.5)
    log(f"[quality_check] OpenDoc6 retried {max_attempts} times, last err/warn: {last}")
    return None


def _get_view_ref_model_path(view) -> str:
    """优先 view.ReferencedDocument.GetPathName()，失败回退 view.GetReferencedModelName()"""
    try:
        ref_doc = view.ReferencedDocument
        if ref_doc:
            try:
                p = ref_doc.GetPathName()
                if p:
                    return str(p)
            except Exception:
                pass
    except Exception:
        pass
    try:
        p = view.GetReferencedModelName()
        if p:
            return str(p)
    except Exception:
        pass
    return ""


def classify_refdoc_status(ref_path: str, expected_part: str) -> dict:
    """按 spec 规约的三分支分类 refdoc 状态

    返回 {pass, severity, message}
    severity: 'ok' / 'warning'
    """
    from pathlib import Path
    if not expected_part:
        if ref_path:
            return {"pass": True, "severity": "ok", "message": "视图引用模型路径存在"}
        return {"pass": False, "severity": "warning", "message": "SolidWorks API 未返回视图引用文档；不阻断图纸导出"}

    expected_name = Path(expected_part).name.lower()
    if ref_path and Path(ref_path).name.lower() == expected_name:
        return {"pass": True, "severity": "ok", "message": "视图引用模型路径匹配"}
    if ref_path:
        return {"pass": False, "severity": "warning", "message": "视图引用存在，但与预期模型名不一致"}
    return {"pass": False, "severity": "warning", "message": "SolidWorks API 未返回视图引用文档；不阻断图纸导出"}


def _check_refdoc_correct(info, expected_part_path: str = ""):
    """refdoc 检查：用 GetReferencedModelName 兜底 + 文件名匹配

    info: _collect 返回的 dict，需包含 views 列表
    expected_part_path: 期望的零件文件路径（绝对路径），用于文件名匹配
    """
    from pathlib import Path
    expected_name = Path(expected_part_path).name.lower() if expected_part_path else ""

    views = info.get("views", []) if isinstance(info, dict) else []
    target_views = [v for v in views if v.get("type") != 1]

    bad_ref = []
    name_match = []
    ref_present = []

    for v in target_views:
        vname = v.get("name") or ""
        ref_path = v.get("ref_doc") or ""
        rd_present = bool(v.get("ref_doc_present"))

        if rd_present:
            ref_present.append(vname)

        if expected_name and ref_path:
            if Path(ref_path).name.lower() == expected_name:
                name_match.append(vname)
            else:
                bad_ref.append({"view": vname, "ref": ref_path, "expected": expected_name})
        elif not ref_path:
            bad_ref.append({"view": vname, "ref": "", "expected": expected_name})

    passed = (len(name_match) >= 1) or (len(ref_present) >= 1)
    return {
        "pass": passed,
        "severity": "warning",
        "reason": "" if passed else "SW2025 SaveAs 后 ReferencedDocument 未持久化",
        "total_views": len(target_views),
        "checked_count": len(target_views),
        "name_match": name_match,
        "name_match_count": len(name_match),
        "ref_present": ref_present,
        "ref_present_count": len(ref_present),
        "bad_ref": bad_ref,
        "expected_part_path": expected_part_path,
    }


def _check_has_tech_note(model):
    """技术要求 Note 检查
    输入：model（含 ann_total_by_type / note_texts 的 info dict）
    输出：dict {pass, noteblock_total, has_3_lines_in_one_note, has_keyword}
    """
    ann = model.get("ann_total_by_type", {}) if model else {}
    noteblock_total = ann.get("NoteBlock", 0)
    note_texts = model.get("note_texts", []) if model else []
    total = noteblock_total

    has_3_lines_in_one_note = False
    for txt in note_texts:
        if not txt:
            continue
        try:
            matches = re.findall(r"^\s*[1-9]\.|^\s*[1-9]、", txt, re.M)
        except Exception:
            matches = []
        if len(matches) >= 3:
            has_3_lines_in_one_note = True
            break

    has_keyword = False
    if total >= 1:
        for txt in note_texts:
            if not txt:
                continue
            if ("技术要求" in txt) or ("GB" in txt) or ("公差" in txt):
                has_keyword = True
                break

    if has_3_lines_in_one_note:
        passed = True
    elif total >= 1 and has_keyword:
        passed = True
    else:
        passed = False

    return {
        "pass": passed,
        "noteblock_total": noteblock_total,
        "has_3_lines_in_one_note": has_3_lines_in_one_note,
        "has_keyword": has_keyword,
    }


def _check_has_ra_note(model):
    """粗糙度 Note 检查
    输出：dict {pass, noteblock_total, has_keyword}
    """
    ann = model.get("ann_total_by_type", {}) if model else {}
    noteblock_total = ann.get("NoteBlock", 0)
    note_texts = model.get("note_texts", []) if model else []

    has_keyword = False
    for txt in note_texts:
        if not txt:
            continue
        if ("Ra" in txt) or ("ra" in txt) or ("粗糙" in txt):
            has_keyword = True
            break

    passed = (noteblock_total >= 1) and has_keyword
    return {
        "pass": passed,
        "noteblock_total": noteblock_total,
        "has_keyword": has_keyword,
    }


def _check_has_datum_a(model):
    """基准 A 检查
    输出：dict {pass, noteblock_total, has_keyword, has_datum_tag_entity}
    """
    ann = model.get("ann_total_by_type", {}) if model else {}
    noteblock_total = ann.get("NoteBlock", 0)
    note_texts = model.get("note_texts", []) if model else []
    has_datum_tag_entity = bool(model.get("has_datum_tag_entity", False)) if model else False

    has_keyword = False
    for txt in note_texts:
        if not txt:
            continue
        if ("△A" in txt) or ("基准" in txt) or ("datum" in txt) or ("Datum" in txt):
            has_keyword = True
            break

    passed = (noteblock_total >= 1) and (has_keyword or has_datum_tag_entity)
    return {
        "pass": passed,
        "noteblock_total": noteblock_total,
        "has_keyword": has_keyword,
        "has_datum_tag_entity": has_datum_tag_entity,
    }


def _check_scale_gb_standard(scale_label: str) -> dict:
    """检查比例是否为 GB/T 14690 标准值"""
    try:
        from app.services.scale_advisor import is_gb_standard_scale
        ok = is_gb_standard_scale(scale_label)
        return {
            "pass": ok,
            "severity": "warning" if not ok else "info",
            "reason": "" if ok else f"{scale_label} 非GB/T 14690标准比例",
            "value": scale_label,
        }
    except Exception as e:
        return {"pass": True, "severity": "info", "reason": f"检查跳过: {e}", "value": scale_label}


def _check_titlebar_complete(src_props: dict, template: dict = None) -> dict:
    """检查标题栏 7 行字段完整性"""
    required_fields = ["品名", "图号", "材质", "数量", "表面处理", "类别", "机型"]
    template = template or {}
    company = template.get("company", {}) if template else {}
    drawing = template.get("drawing", {}) if template else {}

    missing = []
    for field in required_fields:
        val = src_props.get(field, "")
        if not val:
            missing.append(field)

    # 检查模板字段
    if not company.get("name"):
        missing.append("公司名")
    if not drawing.get("designer"):
        missing.append("制图人")
    if not drawing.get("reviewer"):
        missing.append("审核人")

    ok = len(missing) == 0
    return {
        "pass": ok,
        "severity": "warning" if not ok else "info",
        "reason": "" if ok else f"字段缺失: {', '.join(missing)}",
        "missing": missing,
    }


def _check_model_2d_consistency(part_path: str, slddrw_png_path: str, llm) -> dict:
    """检查 3D-2D 视觉一致性"""
    if not llm:
        return {"pass": True, "severity": "info", "reason": "LLM 不可用，跳过", "consistency": None}
    try:
        from app.services.model_compare import compare_model_2d
        result = compare_model_2d(part_path, slddrw_png_path, llm)
        consistency = result.get("consistency", 0)
        ok = consistency >= 50
        missing = result.get("missing_views", [])
        diff = result.get("structural_diff", "")
        reason = ""
        if not ok:
            reason = f"3D-2D一致性={consistency}/100"
            if missing:
                reason += f", 缺失视图: {', '.join(missing)}"
        return {
            "pass": ok,
            "severity": "warning" if not ok else "info",
            "reason": reason,
            "consistency": consistency,
            "missing_views": missing,
            "structural_diff": diff,
        }
    except Exception as e:
        return {"pass": True, "severity": "info", "reason": f"检查跳过: {e}", "consistency": None}


def _collect(sw, path):
    sw = _dynamic_dispatch(sw)
    """采集质检所需信息"""
    info = {"path": path}
    drw = _open_doc_with_retry(sw, path)
    if drw is None:
        info["error"] = "OpenDoc6 returned None after retry"
        return info, None

    # 文档级
    # text_height: 与 probe_drwdot 对齐 — 先读 89，若 < 0.0035 再尝试 GetUserPreferenceTextFormat(1).CharHeight，取 max
    _th_pref = 0.0
    try:
        _th_pref = float(call(drw, "GetUserPreferenceDoubleValue", 89) or 0.0)
    except Exception:
        _th_pref = 0.0
    _th_tf = 0.0
    if _th_pref < 0.0035:
        try:
            tf = drw.GetUserPreferenceTextFormat(1)
            if tf is not None:
                _th_tf = float(tf.CharHeight or 0.0)
        except Exception:
            _th_tf = 0.0
    info["text_height_m"] = max(_th_pref, _th_tf)

    # sheets
    sheets = []
    for sn in to_list(call(drw, "GetSheetNames")):
        try:
            drw.ActivateSheet(sn)
        except Exception:
            pass
        s = call(drw, "GetCurrentSheet")
        prop2 = to_list(call(s, "GetProperties2"))
        sheet_w = None
        sheet_h = None
        try:
            sz = to_list(call(s, "GetSize"))
            if sz and len(sz) >= 2:
                sheet_w = float(sz[0]) if sz[0] is not None else None
                sheet_h = float(sz[1]) if sz[1] is not None else None
        except Exception:
            pass
        # 兜底：GetSize 不可用时，用 GetProperties2 的 [5]/[6] 拿宽高（与 probe_drwdot 一致）
        if (sheet_w is None or sheet_h is None) and prop2 and len(prop2) >= 7:
            try:
                sheet_w = float(prop2[5]) if prop2[5] is not None else sheet_w
                sheet_h = float(prop2[6]) if prop2[6] is not None else sheet_h
            except Exception:
                pass
        sheets.append({
            "name": sn,
            "paper_code": int(prop2[0]) if prop2 else None,
            "scale_num": prop2[2] if len(prop2) > 2 else None,
            "scale_den": prop2[3] if len(prop2) > 3 else None,
            "first_angle": int(prop2[4]) if len(prop2) > 4 else None,
            "width_m": sheet_w,
            "height_m": sheet_h,
        })
    info["sheets"] = sheets

    # views
    views = []
    ann_grand = Counter()
    display_dim_api_total = 0
    note_texts = []
    note_typefaces = []
    has_datum_tag_entity = False
    v = call(drw, "GetFirstView")
    idx = 0
    while v is not None:
        vtype = call(v, "Type")
        ann_types = Counter()
        a = call(v, "GetFirstAnnotation3")
        while a is not None:
            t = call(a, "GetType")
            tn = ANN_TYPE_NAME.get(t, str(t))
            ann_types[tn] += 1
            ann_grand[tn] += 1
            if t == 4:
                has_datum_tag_entity = True
            if t in (2, 6):
                txt = _extract_note_text(a)
                note_texts.append(str(txt))
                # 抽取字体（仅取首段）
                try:
                    inner = getattr(a, "Note", None)
                    if inner is None:
                        inner = a
                    fmt = inner.GetTextFormat(0)
                    tf = getattr(fmt, "TypeFaceName", None)
                    if tf:
                        note_typefaces.append(str(tf))
                except Exception:
                    pass
            a = call(a, "GetNext3")

        view_display_dim_count = 0
        try:
            view_display_dim_count = max(view_display_dim_count, len(to_list(call(v, "GetDisplayDimensions"))))
        except Exception:
            pass
        try:
            dd = call(v, "GetFirstDisplayDimension")
            seen_dd = 0
            while dd is not None and seen_dd < 2000:
                seen_dd += 1
                try:
                    dd = v.GetNextDisplayDimension(dd)
                except Exception:
                    break
            view_display_dim_count = max(view_display_dim_count, seen_dd)
        except Exception:
            pass
        display_dim_api_total += view_display_dim_count

        ref = call(v, "GetReferencedDocument")
        ref_path = ""
        if ref is not None:
            try:
                ref_path = call(ref, "GetPathName") or ""
            except Exception:
                ref_path = ""
        if not ref_path:
            try:
                ref_path = _get_view_ref_model_path(v) or ""
            except Exception:
                ref_path = ref_path or ""

        views.append({
            "index": idx,
            "name": call(v, "GetName2"),
            "type": vtype,
            "orient": call(v, "GetOrientationName") or "",
            "position": to_list(call(v, "Position")),
            "outline": to_list(call(v, "GetOutline")),
            "ref_doc": ref_path,
            "ref_doc_present": ref is not None,
            "ann_types": dict(ann_types),
        })
        idx += 1
        v = call(v, "GetNextView")
    if display_dim_api_total > ann_grand.get("DisplayDim", 0):
        info["display_dim_count_source"] = "display_dimension_api"
        info["display_dim_count_annotation_chain"] = int(ann_grand.get("DisplayDim", 0))
        ann_grand["DisplayDim"] = int(display_dim_api_total)
    else:
        info["display_dim_count_source"] = "annotation_chain"
        info["display_dim_count_annotation_chain"] = int(ann_grand.get("DisplayDim", 0))
    info["display_dim_count_api"] = int(display_dim_api_total)
    info["views"] = views
    info["ann_total_by_type"] = dict(ann_grand)
    info["note_texts"] = note_texts
    info["note_typefaces"] = note_typefaces
    info["has_datum_tag_entity"] = has_datum_tag_entity

    # props
    cpm_list = []
    try:
        cpm_list.append(("", drw.Extension.CustomPropertyManager("")))
    except Exception:
        pass
    for cn in to_list(call(drw, "GetConfigurationNames")):
        try:
            cpm_list.append((cn, drw.Extension.CustomPropertyManager(cn)))
        except Exception:
            pass
    keys_seen = set()
    prop_values = {}
    for _, cpm in cpm_list:
        try:
            for n in to_list(call(cpm, "GetNames")):
                keys_seen.add(n)
                if n not in prop_values:
                    try:
                        # Get4 returns (cached_value, resolved_value, was_resolved, link_to_property)
                        gv = cpm.Get4(n, False)
                        val = ""
                        if isinstance(gv, tuple):
                            for v_ in gv:
                                if isinstance(v_, str) and v_.strip():
                                    val = v_.strip()
                                    break
                        elif isinstance(gv, str):
                            val = gv.strip()
                        prop_values[n] = val
                    except Exception:
                        prop_values[n] = ""
        except Exception:
            pass
    info["props_key_present"] = {k: (k in keys_seen) for k in PROP_KEYS}
    info["prop_values"] = prop_values

    title = call(drw, "GetTitle")
    return info, title


def quality_check(sldddrw_path, sw=None, baseline_avg_dim=21.1, baseline_avg_centermark=10,
                  expected_part_path: str = ""):
    """对单张 SLDDRW 做 12 项渲染级质检并产出 JSON-friendly dict"""
    _ensure_solidworks_global_lock("drw_quality_check.quality_check", sldddrw_path)
    result = {
        "file": sldddrw_path,
        "pass": False,
        "score_pass_count": 0,
        "issues": [],
        "checks": {},
    }

    if not os.path.exists(sldddrw_path):
        result["issues"].append(f"file not found: {sldddrw_path}")
        result["checks"]["__error__"] = "file not found"
        return result

    own_sw = False
    if sw is None:
        try:
            sw = _dynamic_dispatch(wc.GetActiveObject("SldWorks.Application"))
        except Exception:
            sw = _dynamic_dispatch(wc.Dispatch("SldWorks.Application"))
            sw.Visible = True
            time.sleep(2)
            own_sw = True
    else:
        sw = _dynamic_dispatch(sw)

    info, title = _collect(sw, sldddrw_path)
    if "error" in info:
        # 降级模式：OpenDoc6 失败时根据文件大小给出最低存在性信号
        try:
            file_size = os.path.getsize(sldddrw_path)
        except Exception:
            file_size = 0
        result["issues"].append("model_open_failed")
        result["issues"].append(info["error"])
        result["checks"]["__error__"] = info["error"]
        result["checks"]["__file_size__"] = file_size
        if file_size > 0:
            result["score_pass_count"] = 1
            result["checks"]["__degraded_existence_pass__"] = True
        else:
            result["score_pass_count"] = 0
        try:
            if title:
                sw.CloseDoc(title)
        except Exception:
            pass
        return result

    views = info.get("views", [])
    sheets = info.get("sheets", [])
    real_views = [v for v in views if v.get("type") != 1]

    # ========== 1. view_overlap ==========
    overlaps = []
    for i in range(len(real_views)):
        for j in range(i + 1, len(real_views)):
            a = _aabb(real_views[i].get("outline"))
            b = _aabb(real_views[j].get("outline"))
            if _rect_intersect(a, b):
                overlaps.append({
                    "a": real_views[i].get("name"),
                    "b": real_views[j].get("name"),
                    "a_outline": real_views[i].get("outline"),
                    "b_outline": real_views[j].get("outline"),
                })
    chk_overlap = {
        "pass": len(overlaps) == 0,
        "overlap_pairs": overlaps,
        "real_view_count": len(real_views),
    }
    result["checks"]["view_overlap"] = chk_overlap
    if not chk_overlap["pass"]:
        result["issues"].append(
            f"view_overlap: {len(overlaps)} 对视图重叠"
        )

    # ========== 2. view_in_frame ==========
    out_of_frame = []
    for v in real_views:
        a = _aabb(v.get("outline"))
        if not _rect_in_frame(a):
            out_of_frame.append({
                "name": v.get("name"),
                "outline": v.get("outline"),
            })
    chk_frame = {
        "pass": len(out_of_frame) == 0,
        "frame": list(FRAME),
        "out_of_frame": out_of_frame,
    }
    result["checks"]["view_in_frame"] = chk_frame
    if not chk_frame["pass"]:
        result["issues"].append(
            f"view_in_frame: {len(out_of_frame)} 个视图越界"
        )

    # ========== 3. front_view_position ==========
    fronts = []
    for v in real_views:
        orient = v.get("orient") or ""
        name = v.get("name") or ""
        if ("前视" in orient) or ("Front" in orient) \
                or ("前视" in name) or ("Front" in name):
            fronts.append(v)
    front_chk_pass = False
    front_detail = {"found": len(fronts), "candidates": []}
    if fronts:
        for fv in fronts:
            pos = fv.get("position") or []
            cx_m = pos[0] if len(pos) >= 1 else None
            cy_m = pos[1] if len(pos) >= 2 else None
            if cx_m is None or cy_m is None:
                # 用 outline 中点兜底
                a = _aabb(fv.get("outline"))
                if a:
                    cx_m = (a[0] + a[2]) / 2
                    cy_m = (a[1] + a[3]) / 2
            ok = False
            if cx_m is not None and cy_m is not None:
                cx_mm = cx_m * 1000
                cy_mm = cy_m * 1000
                ok = (40 <= cx_mm <= 180) and (80 <= cy_mm <= 180)
                front_detail["candidates"].append({
                    "name": fv.get("name"),
                    "cx_mm": round(cx_mm, 2),
                    "cy_mm": round(cy_mm, 2),
                    "in_zone": ok,
                })
            if ok:
                front_chk_pass = True
    chk_front = {
        "pass": front_chk_pass,
        "detail": front_detail,
    }
    result["checks"]["front_view_position"] = chk_front
    if not chk_front["pass"]:
        if not fronts:
            result["issues"].append("front_view_position: 未找到前视图")
        else:
            result["issues"].append(
                "front_view_position: 前视图位置不在 [40-180mm,80-180mm] 区间"
            )

    # ========== 4. scale_in_set ==========
    s0 = sheets[0] if sheets else {}
    scale = None
    try:
        if s0.get("scale_num") is not None and s0.get("scale_den") is not None:
            scale = (int(round(float(s0["scale_num"]))),
                     int(round(float(s0["scale_den"]))))
    except Exception:
        scale = None
    chk_scale = {
        "pass": scale in GOOD_SCALES if scale else False,
        "scale": scale,
        "allowed": sorted(GOOD_SCALES),
    }
    result["checks"]["scale_in_set"] = chk_scale
    if not chk_scale["pass"]:
        result["issues"].append(f"scale_in_set: 比例 {scale} 不在白名单")

    # ========== 5. text_height_ge_3_5mm ==========
    th = info.get("text_height_m")
    try:
        th_v = float(th) if th is not None else 0.0
    except Exception:
        th_v = 0.0
    chk_th = {
        "pass": th_v >= 0.0035,
        "text_height_m": th_v,
        "threshold_m": 0.0035,
    }
    result["checks"]["text_height_ge_3_5mm"] = chk_th
    if not chk_th["pass"]:
        result["issues"].append(
            f"text_height_ge_3_5mm: 文字高度 {th_v:.4f}m < 0.0035m"
        )

    # ========== 6. all_13_keys_present ==========
    kp = info.get("props_key_present", {})
    missing = [k for k in PROP_KEYS if not kp.get(k)]
    chk_keys = {
        "pass": len(missing) == 0,
        "missing": missing,
        "present_count": sum(1 for k in PROP_KEYS if kp.get(k)),
        "total": len(PROP_KEYS),
    }
    result["checks"]["all_13_keys_present"] = chk_keys
    if not chk_keys["pass"]:
        result["issues"].append(f"all_13_keys_present: 缺 {len(missing)} 键")

    # ========== 7. dim_count_sufficient（v1.4 Task 4.3: 阈值降低为硬性 5）==========
    ann = info.get("ann_total_by_type", {})
    dim_total = ann.get("DisplayDim", 0)
    dim_thr = max(5, 0.5 * baseline_avg_dim)  # v1.4: 至少 5 个尺寸
    # v1.4: 若 dim_total >= 5 则 pass（硬性阈值）
    dim_pass = dim_total >= 5
    chk_dim = {
        "pass": dim_pass,
        "dim_total": dim_total,
        "threshold": 5,
        "baseline_avg_dim": baseline_avg_dim,
        "v14_hard_threshold": 5,
        "source": info.get("display_dim_count_source", "annotation_chain"),
        "annotation_chain_count": info.get("display_dim_count_annotation_chain", dim_total),
        "api_count": info.get("display_dim_count_api", 0),
    }
    result["checks"]["dim_count_sufficient"] = chk_dim
    if not chk_dim["pass"]:
        result["issues"].append(
            f"dim_count_sufficient: DisplayDim={dim_total} < 5"
        )

    # ========== v1.6 Task 5: dimension_coverage 字段 ==========
    # 从同目录 warnings.json 和 seed_dim.json 读取尺寸来源信息
    _drw_dir_dc = Path(sldddrw_path).parent
    _drw_stem_dc = Path(sldddrw_path).stem.replace("_v5", "")
    _dim_source = "none"
    _overall_length = None
    _overall_width = None
    _overall_height = None
    _hole_diameter = None
    _hole_location = None
    _associativity = "unknown"

    # 读取 warnings.json 判断尺寸来源
    _warn_json_path = _drw_dir_dc / f"{Path(sldddrw_path).stem}_warnings.json"
    if _warn_json_path.exists():
        try:
            _warn_data = json.loads(_warn_json_path.read_text(encoding="utf-8"))
            _warn_codes = [w.get("code", "") for w in _warn_data.get("warnings", [])]
            if "dim_via_sidecar" in _warn_codes:
                _dim_source = "model_items"
                _associativity = "model"
            elif "dim_seed_used" in _warn_codes:
                _dim_source = "model_seed"
                _associativity = "model_seed"
            elif dim_total > 0:
                _dim_source = "drawing_sketch_fallback"
                _associativity = "non_model"
            else:
                _dim_source = "none"
                _associativity = "none"
            # 读取 bbox_m
            _bbox_m = _warn_data.get("bbox_m")
            if _bbox_m and len(_bbox_m) >= 3:
                _overall_length = float(_bbox_m[0])
                _overall_width = float(_bbox_m[1])
                _overall_height = float(_bbox_m[2])
        except Exception:
            pass

    # 读取 seed_dim.json 补充 overall 信息
    _seed_json_path = _drw_dir_dc / "seed_dim.json"
    if not _seed_json_path.exists():
        _seed_json_path = _drw_dir_dc / "input_work" / "seed_dim.json"
    if _seed_json_path.exists():
        try:
            _seed_data = json.loads(_seed_json_path.read_text(encoding="utf-8"))
            if _overall_length is None and _seed_data.get("overall_length") is not None:
                _overall_length = float(_seed_data["overall_length"])
            if _overall_width is None and _seed_data.get("overall_width") is not None:
                _overall_width = float(_seed_data["overall_width"])
            if _overall_height is None and _seed_data.get("overall_height") is not None:
                _overall_height = float(_seed_data["overall_height"])
            if _seed_data.get("success") and _seed_data.get("seed_dim_count", 0) > 0:
                if _dim_source == "none":
                    _dim_source = "model_seed"
                    _associativity = "model_seed"
        except Exception:
            pass

    dimension_coverage = {
        "dim_total": dim_total,
        "source": _dim_source,
        "overall_length": _overall_length,
        "overall_width": _overall_width,
        "overall_height": _overall_height,
        "hole_diameter": _hole_diameter,
        "hole_location": _hole_location,
        "associativity": _associativity,
    }
    result["checks"]["dimension_coverage"] = dimension_coverage

    # ========== 8. centermark_count_sufficient ==========
    cm_total = ann.get("CenterMark", 0)
    cm_thr = 0.5 * baseline_avg_centermark
    chk_cm = {
        "pass": cm_total >= cm_thr,
        "centermark_total": cm_total,
        "threshold": cm_thr,
        "baseline_avg_centermark": baseline_avg_centermark,
    }
    result["checks"]["centermark_count_sufficient"] = chk_cm
    if not chk_cm["pass"]:
        result["issues"].append(
            f"centermark_count_sufficient: CenterMark={cm_total} < {cm_thr}"
        )

    # ========== 9/10/11: NoteBlock 文本/实体启发式 ==========
    noteblock_total = ann.get("NoteBlock", 0)

    chk_tech = _check_has_tech_note(info)
    result["checks"]["has_tech_note"] = chk_tech
    if not chk_tech["pass"]:
        result["issues"].append(
            f"has_tech_note: NoteBlock={chk_tech.get('noteblock_total')} "
            f"3lines={chk_tech.get('has_3_lines_in_one_note')} "
            f"keyword={chk_tech.get('has_keyword')}"
        )

    chk_ra = _check_has_ra_note(info)
    result["checks"]["has_ra_note"] = chk_ra
    if not chk_ra["pass"]:
        result["issues"].append(
            f"has_ra_note: NoteBlock={chk_ra.get('noteblock_total')} "
            f"keyword={chk_ra.get('has_keyword')}"
        )

    chk_datum = _check_has_datum_a(info)
    result["checks"]["has_datum_a"] = chk_datum
    if not chk_datum["pass"]:
        result["issues"].append(
            f"has_datum_a: NoteBlock={chk_datum.get('noteblock_total')} "
            f"keyword={chk_datum.get('has_keyword')} "
            f"datum_tag={chk_datum.get('has_datum_tag_entity')}"
        )

    # ========== 12. refdoc_correct ==========
    # 推断 expected_part：优先入参，否则从 SLDDRW 同目录/3D转2D测试图纸/ 推断同名 SLDPRT
    expected_part = expected_part_path or ""
    if not expected_part:
        try:
            from pathlib import Path as _P
            slddrw = _P(sldddrw_path)
            base = slddrw.stem
            if base.endswith("_v5"):
                base = base[:-3]
            elif base.endswith("_v6"):
                base = base[:-3]
            elif base.endswith("_v4"):
                base = base[:-3]
            for cand in [
                _RUNTIME_ROOT / "3D转2D测试图纸" / f"{base}.SLDPRT",
                slddrw.parent / f"{base}.SLDPRT",
            ]:
                if cand.exists():
                    expected_part = str(cand.resolve())
                    break
        except Exception:
            expected_part = ""

    chk_ref = _check_refdoc_correct(info, expected_part_path=expected_part)
    result["checks"]["refdoc_correct"] = chk_ref
    if not chk_ref["pass"]:
        if chk_ref.get("checked_count", 0) == 0:
            result["issues"].append("refdoc_correct: 无非 sheet 视图可检")
        else:
            result["issues"].append(
                f"refdoc_correct: name_match={chk_ref.get('name_match_count')} "
                f"ref_present={chk_ref.get('ref_present_count')} "
                f"bad={len(chk_ref.get('bad_ref', []))}"
            )

    # ========== GB 扩展 13: gb_titlebar_complete ==========
    if GB_RULE_TOGGLES.get("gb_titlebar_complete", True):
        prop_values = info.get("prop_values", {}) or {}
        missing_groups = []
        for grp in GB_TITLEBAR_REQUIRED_GROUPS:
            ok = False
            for k in grp:
                val = prop_values.get(k, "")
                if isinstance(val, str) and val.strip():
                    ok = True
                    break
            if not ok:
                missing_groups.append("|".join(grp))
        chk_tb = {
            "pass": len(missing_groups) == 0,
            "missing_groups": missing_groups,
            "checked_count": len(GB_TITLEBAR_REQUIRED_GROUPS),
        }
        if not chk_tb["pass"]:
            result["issues"].append(
                f"gb_titlebar_complete: 缺 {len(missing_groups)} 组核心字段: {missing_groups}"
            )
    else:
        chk_tb = {"pass": True, "skipped": True}
    result["checks"]["gb_titlebar_complete"] = chk_tb

    # ========== GB 扩展 14: gb_font_is_changfangsong ==========
    if GB_RULE_TOGGLES.get("gb_font_is_changfangsong", True):
        typefaces = info.get("note_typefaces", []) or []
        joined = "|".join(typefaces).lower()
        keywords = ["仿宋", "fangsong", "fang_song", "fang song"]
        has_cfs = any(kw in joined for kw in keywords) or any(kw in joined for kw in ["仿宋_gb2312", "仿宋"])
        chk_font = {
            "pass": bool(has_cfs) if typefaces else False,
            "typefaces_sample": typefaces[:5],
            "typefaces_count": len(typefaces),
        }
        if not chk_font["pass"]:
            result["issues"].append(
                f"gb_font_is_changfangsong: 未发现仿宋字体 (count={len(typefaces)})"
            )
    else:
        chk_font = {"pass": True, "skipped": True}
    result["checks"]["gb_font_is_changfangsong"] = chk_font

    # ========== GB 扩展 15: gb_paper_size_correct ==========
    if GB_RULE_TOGGLES.get("gb_paper_size_correct", True):
        s0 = sheets[0] if sheets else {}
        w = s0.get("width_m")
        h = s0.get("height_m")
        matched = None
        if w is not None and h is not None:
            for label, (ew, eh) in GB_PAPER_SIZES_M.items():
                if abs(float(w) - ew) <= 0.005 and abs(float(h) - eh) <= 0.005:
                    matched = label
                    break
        chk_paper = {
            "pass": matched is not None,
            "width_m": w,
            "height_m": h,
            "matched": matched,
        }
        if not chk_paper["pass"]:
            result["issues"].append(
                f"gb_paper_size_correct: sheet ({w}, {h}) 不在 A0~A4 标准 (横/纵)"
            )
    else:
        chk_paper = {"pass": True, "skipped": True}
    result["checks"]["gb_paper_size_correct"] = chk_paper

    # ========== GB 扩展 16: gb_has_section_view_or_skipped ==========
    if GB_RULE_TOGGLES.get("gb_has_section_view_or_skipped", True) and GB_REQUIRE_SECTION:
        # SW IView.Type: 3=swDrawingSectionView, 4=swDrawingDetailView (按 Help)
        section_count = sum(1 for vv in views if vv.get("type") == 3)
        chk_sec = {
            "pass": section_count >= 1,
            "section_count": section_count,
            "require_section": True,
        }
        if not chk_sec["pass"]:
            result["issues"].append(
                f"gb_has_section_view_or_skipped: 无剖视图 (require_section=True)"
            )
    else:
        chk_sec = {"pass": True, "skipped": True, "require_section": GB_REQUIRE_SECTION}
    result["checks"]["gb_has_section_view_or_skipped"] = chk_sec

    # ========== GB 扩展 17: gb_scale_in_extended_set ==========
    if GB_RULE_TOGGLES.get("gb_scale_in_extended_set", True):
        ext_pass = chk_scale.get("scale") in GOOD_SCALES if chk_scale.get("scale") else False
        chk_scale_ext = {
            "pass": ext_pass,
            "scale": chk_scale.get("scale"),
            "allowed": sorted(GOOD_SCALES),
        }
        if not chk_scale_ext["pass"]:
            result["issues"].append(
                f"gb_scale_in_extended_set: 比例 {chk_scale.get('scale')} 不在 GB/T 14690 全集"
            )
    else:
        chk_scale_ext = {"pass": True, "skipped": True}
    result["checks"]["gb_scale_in_extended_set"] = chk_scale_ext

    # ========== v1.3 扩展: scale_gb_standard / titlebar_complete / model_2d_consistency ==========
    from pathlib import Path as _Path2

    # scale_gb_standard: 检查比例是否为 GB/T 14690 标准值
    scale_label = f"{scale[0]}:{scale[1]}" if scale else ""
    result["checks"]["scale_gb_standard"] = _check_scale_gb_standard(scale_label)

    # titlebar_complete: 检查标题栏 7 行字段完整性
    src_props = info.get("prop_values", {}) or {}
    template = {}
    try:
        import yaml as _yaml
        _tpl_path = _BUNDLE_ROOT / "config" / "titlebar_template.yaml"
        if _tpl_path.exists():
            with open(_tpl_path, "r", encoding="utf-8") as _f:
                template = _yaml.safe_load(_f) or {}
    except Exception:
        template = {}
    result["checks"]["titlebar_complete"] = _check_titlebar_complete(src_props, template)

    # model_2d_consistency: 仅在 LLM 可用时调用
    _llm = None
    try:
        from app.services.llm_client import build_default_client
        _cand = build_default_client()
        if _cand and (_cand.model or _cand.vision_model) and _cand.base_url:
            _llm = _cand
    except Exception:
        _llm = None
    if _llm and expected_part:
        _slddrw_png_path = str(_Path2(sldddrw_path).with_suffix(".PNG"))
        result["checks"]["model_2d_consistency"] = _check_model_2d_consistency(
            expected_part, _slddrw_png_path, _llm
        )

    # ========== 汇总 ==========
    check_keys_order = [
        "view_overlap", "view_in_frame", "front_view_position",
        "scale_in_set", "text_height_ge_3_5mm", "all_13_keys_present",
        "dim_count_sufficient", "centermark_count_sufficient",
        "has_tech_note", "has_ra_note", "has_datum_a",
        "refdoc_correct",
        # GB-strict 扩展
        "gb_titlebar_complete",
        "gb_font_is_changfangsong",
        "gb_paper_size_correct",
        "gb_has_section_view_or_skipped",
        "gb_scale_in_extended_set",
    ]
    pass_cnt = sum(1 for k in check_keys_order
                   if result["checks"].get(k, {}).get("pass"))
    result["score_pass_count"] = pass_cnt
    result["pass"] = (pass_cnt == len(check_keys_order))
    result["_check_order"] = check_keys_order

    # 关闭文档
    try:
        if title:
            sw.CloseDoc(title)
    except Exception:
        pass

    # === Spec release-v1: 双轨字段 ===
    hard_fail = []
    warnings_list = []

    if result.get("__error__") or "OpenDoc6" in str(result.get("checks", {}).get("__error__", "")):
        hard_fail.append("opendoc_failed")
    if not Path(sldddrw_path).exists() or Path(sldddrw_path).stat().st_size <= 0:
        hard_fail.append("drawing_not_created")
    _drw_dir = Path(sldddrw_path).parent
    _drw_stem = Path(sldddrw_path).stem
    if not (_drw_dir / f"{_drw_stem}.PDF").exists() and not (_drw_dir / f"{_drw_stem}.pdf").exists():
        hard_fail.append("pdf_missing")
    if not (_drw_dir / f"{_drw_stem}.DXF").exists() and not (_drw_dir / f"{_drw_stem}.dxf").exists():
        hard_fail.append("dxf_missing")
    if not (_drw_dir / f"{_drw_stem}.PNG").exists() and not (_drw_dir / f"{_drw_stem}.png").exists():
        hard_fail.append("png_missing")

    _checks = result.get("checks", {})
    if _checks.get("view_overlap", {}).get("pass") is False:
        hard_fail.append("view_overlap")
    if _checks.get("view_in_frame", {}).get("pass") is False:
        hard_fail.append("view_out_of_frame")
    _dim_total = _checks.get("dim_count_sufficient", {}).get("dim_total", 0)

    # v1.7 Task 5: QC 等级制（dimension_grade / usable_for）
    # 读取 part_class.json 和 dimension_sidecar_result.json（由 drw_generate_v6 写入 run_dir/qc/）
    _part_class = "feature_part"
    _standard_annotation_present = False
    _sidecar_overall = {}
    _run_dir_env = os.environ.get("RUN_DIR", "")
    _qc_dir_v17 = Path(_run_dir_env) / "qc" if _run_dir_env else None
    # 降级：若 RUN_DIR 未注入，尝试从 drw_dir 推断（兼容旧调用）
    if _qc_dir_v17 is None or not _qc_dir_v17.exists():
        _qc_dir_v17 = _drw_dir
    _part_class_json = _qc_dir_v17 / "part_class.json"
    if _part_class_json.exists():
        try:
            _pc_data = json.loads(_part_class_json.read_text(encoding="utf-8"))
            _part_class = _pc_data.get("part_class", "feature_part")
        except Exception:
            pass
    _sidecar_json = _qc_dir_v17 / "dimension_sidecar_result.json"
    _sidecar_success = False
    _sidecar_annotations_added = 0
    if _sidecar_json.exists():
        try:
            _sc_data = json.loads(_sidecar_json.read_text(encoding="utf-8"))
            _standard_annotation_present = bool(_sc_data.get("standard_annotation_present", False))
            _sidecar_success = bool(_sc_data.get("success", False))
            _sidecar_annotations_added = int(_sc_data.get("annotations_added", 0))
            for _k in ("overall_length", "overall_width", "overall_height", "fastener_spec", "spring_spec"):
                if _sc_data.get(_k) is not None:
                    _sidecar_overall[_k] = _sc_data[_k]
        except Exception:
            pass

    _is_purchased_like = _part_class in ("fastener", "spring", "purchased_part")
    # v1.7: sidecar 有效标注 = sidecar 成功且添加了标注（Note 或 DisplayDim）
    # 对非采购类零件（如 long_thin），sidecar Note 标注也算"有效 sidecar 标注"
    _has_valid_sidecar_annotation = (
        _sidecar_success and _sidecar_annotations_added > 0 and bool(_sidecar_overall)
    )

    # v1.7 Task 5: 计算 dimension_grade
    # A = 完整制造图 (dim_total >= 5 且 associativity=model 且有 overall 三向)
    # B = 基础制造图 (dim_total >= 5 但 associativity 非 model，或 dim_total >= 3，或 sidecar 标注 >= 3)
    # C = 采购/装配图 (采购类 + standard_annotation_present=true，或 dim_total > 0，或有有效 sidecar 标注)
    # D = 不可交付 (dim_total=0 且非采购类且无 sidecar 标注，或采购类无 standard_annotation)
    _dim_cov = _checks.get("dimension_coverage", {})
    _assoc = _dim_cov.get("associativity", "unknown")
    _has_overall3 = all(_dim_cov.get(k) is not None for k in ("overall_length", "overall_width", "overall_height"))
    # v1.8 Task 3: sidecar 标注数（从 dimension_sidecar_result.json）
    _sidecar_annotation_count = 0
    if _sidecar_json.exists():
        try:
            _sidecar_annotation_count = int(_sc_data.get("annotations_added", 0))
        except Exception:
            pass
    # v1.8 Task 3: sidecar 有 overall 三向（Note 方式）
    _sidecar_has_overall3 = all(
        _sidecar_overall.get(k) is not None
        for k in ("overall_length", "overall_width", "overall_height")
    )
    if _dim_total >= 5 and _assoc == "model" and _has_overall3:
        _dimension_grade = "A"
    elif _dim_total >= 5:
        _dimension_grade = "B"
    elif _is_purchased_like and _standard_annotation_present:
        _dimension_grade = "C"
    elif _dim_total >= 3:
        _dimension_grade = "B"
    elif _dim_total > 0:
        _dimension_grade = "C"
    elif _has_valid_sidecar_annotation and _sidecar_has_overall3 and _sidecar_annotation_count >= 3:
        # v1.8 Task 3: sidecar 补全总长/总宽/总高 3 项 Note 标注 → B 级基础制造图
        _dimension_grade = "B"
    elif _has_valid_sidecar_annotation:
        # v1.7: 有有效 sidecar 标注（Note 方式的总长/总宽/总高）→ C 级装配图
        _dimension_grade = "C"
    else:
        _dimension_grade = "D"

    # v1.7 Task 5: 计算 usable_for
    if _dimension_grade == "A":
        _usable_for = ["manufacturing", "assembly", "procurement"]
    elif _dimension_grade == "B":
        _usable_for = ["manufacturing", "assembly", "procurement"]
    elif _dimension_grade == "C":
        if _is_purchased_like:
            _usable_for = ["procurement", "assembly"]
        else:
            _usable_for = ["assembly"]
    else:
        _usable_for = []

    # v1.7 Task 5: hard_fail 逻辑按 part_class 分级
    # 对 feature_part / machined_part: dim_total < 5 仍 hard_fail（除非有有效 sidecar 标注）
    # 对 fastener / spring / purchased_part: standard_annotation_present=true 时，
    #   dim_total < 5 不直接 hard_fail，而是 C 级
    if _dim_total == 0:
        if _is_purchased_like and _standard_annotation_present:
            # 采购类有标准标注，降级为 warning，不进 hard_fail
            warnings_list.append("dim_total_zero_purchased_with_std_anno")
        elif _has_valid_sidecar_annotation:
            # v1.7: 有有效 sidecar 标注（Note 总长/总宽/总高），降级为 warning
            warnings_list.append("dim_total_zero_with_sidecar_annotation")
        else:
            hard_fail.append("dim_total_zero")
    elif _dim_total < 5:
        if _is_purchased_like and _standard_annotation_present:
            # 采购类 C 级，不进 hard_fail
            warnings_list.append("dim_total_below_threshold_purchased_c_grade")
        else:
            warnings_list.append("dim_total_below_threshold")
    if result.get("score_pass_count", 0) < 10:
        # v1.7 Task 5: 采购类 C 级不强制 qc_pass_too_low
        if _is_purchased_like and _standard_annotation_present and _dimension_grade == "C":
            warnings_list.append("qc_pass_too_low_purchased_c_grade")
        elif _has_valid_sidecar_annotation and _dimension_grade in ("B", "C"):
            # v1.8 Task 3: sidecar 标注达 B/C 级也不强制 qc_pass_too_low
            warnings_list.append("qc_pass_too_low_sidecar_bc_grade")
        else:
            hard_fail.append("qc_pass_too_low")
    _vision = _checks.get("vision_score", {}).get("score")
    if _vision is not None and _vision < 60:
        hard_fail.append("vision_score_too_low")

    for key in ["refdoc_correct", "has_datum_a", "has_ra_note", "gb_titlebar_complete", "gb_has_section_view_or_skipped",
                "scale_gb_standard", "titlebar_complete", "model_2d_consistency"]:
        blk = _checks.get(key, {})
        if blk.get("pass") is False:
            warnings_list.append(key)

    # v1.6 Task 5: non_model_associative_dimension 作为 warning
    if _dim_cov.get("associativity") in ("non_model", "none", "unknown"):
        warnings_list.append("non_model_associative_dimension")

    drawing_usable = {
        "pass": len(hard_fail) == 0,
        "criteria": {
            "files_exported": ("drawing_not_created" not in hard_fail) and ("pdf_missing" not in hard_fail) and ("dxf_missing" not in hard_fail) and ("png_missing" not in hard_fail),
            "view_in_frame": _checks.get("view_in_frame", {}).get("pass", False),
            "view_overlap_ok": _checks.get("view_overlap", {}).get("pass", False),
            "dim_total": _dim_total,
            "qc_pass_count": result.get("score_pass_count", 0),
            "vision_score": _vision,
        },
    }

    result["hard_fail"] = hard_fail
    result["warnings"] = warnings_list
    result["drawing_usable"] = drawing_usable
    # v1.7 Task 5: 新增 dimension_grade / usable_for / part_class / standard_annotation_present
    result["dimension_grade"] = _dimension_grade
    result["usable_for"] = _usable_for
    result["part_class"] = _part_class
    result["standard_annotation_present"] = _standard_annotation_present
    result["has_valid_sidecar_annotation"] = _has_valid_sidecar_annotation
    # v1.8 Task 3: dimension_sources（区分 DisplayDim / Note dim / Standard annotation）
    _dim_sources = {
        "display_dim_count": _dim_total,
        "note_dim_count": _sidecar_annotation_count if _has_valid_sidecar_annotation else 0,
        "standard_annotation_present": _standard_annotation_present,
        "sidecar_overall": _sidecar_overall if _sidecar_overall else None,
        "sources_summary": [],
    }
    if _dim_total > 0:
        _dim_sources["sources_summary"].append(f"model_display_dim={_dim_total}")
    if _has_valid_sidecar_annotation and _sidecar_annotation_count > 0:
        _dim_sources["sources_summary"].append(f"sidecar_note={_sidecar_annotation_count}")
    if _standard_annotation_present:
        _dim_sources["sources_summary"].append("standard_annotation=true")
    result["dimension_sources"] = _dim_sources
    if _sidecar_overall:
        result["sidecar_overall"] = _sidecar_overall

    # === Spec enhance-v1-1 Task 4: diagnostics 字段 ===
    diagnostics = {
        "sw_revision": "",
        "refdoc_strategy": "ReferencedDocument -> GetReferencedModelName fallback",
        "replace_view_model_result": None,
        "cfg_name": "",
    }
    try:
        if sw is not None:
            try:
                diagnostics["sw_revision"] = str(sw.RevisionNumber())
            except Exception:
                try:
                    diagnostics["sw_revision"] = str(sw.RevisionNumber)
                except Exception:
                    pass
    except Exception:
        pass
    result["diagnostics"] = diagnostics
    # === end ===

    # v1.8 Task 2: drawing_accuracy_score
    try:
        import sys as _sys
        _v18_root = str(_BUNDLE_ROOT)
        if _v18_root not in _sys.path:
            _sys.path.insert(0, _v18_root)
        from app.services.drawing_accuracy_score import compute_drawing_accuracy_score
        result["drawing_accuracy_score"] = compute_drawing_accuracy_score(result)
    except Exception as _e:
        result["drawing_accuracy_score"] = {"total": 0, "error": str(_e)}

    # v1.9 Task 6: QC 字段升级（顶层字段，不删除 v1.8 字段）
    result["display_dim_count"] = _dim_total
    result["display_dim_count_source"] = _checks.get("dim_count_sufficient", {}).get("source", "annotation_chain")
    result["display_dim_count_api"] = _checks.get("dim_count_sufficient", {}).get("api_count", 0)
    result["note_dim_count"] = _sidecar_annotation_count if _has_valid_sidecar_annotation else 0
    result["model_associative_dim_count"] = 0  # 由 Add-in GenerateAssociativeDimensions 填充
    result["addin_dimension_count"] = 0  # 由 Add-in GenerateAssociativeDimensions 填充
    result["docmgr_reference_count"] = 0  # 由 Document Manager 填充
    result["pmi_available"] = False  # 由 PMI Probe 填充

    return result


def _print_brief(res):
    log(f"\n[QC] {os.path.basename(res.get('file', ''))}")
    if "__error__" in res.get("checks", {}):
        log(f"  ❌ ERROR: {res['checks']['__error__']}")
        return
    order = res.get("_check_order") or list(res.get("checks", {}).keys())
    for k in order:
        c = res["checks"].get(k, {})
        ok = "✅" if c.get("pass") else "❌"
        # 简要数值
        extra = ""
        if k == "view_overlap":
            extra = f"overlap_pairs={len(c.get('overlap_pairs', []))}"
        elif k == "view_in_frame":
            extra = f"out_of_frame={len(c.get('out_of_frame', []))}"
        elif k == "front_view_position":
            extra = f"found={c.get('detail', {}).get('found', 0)}"
        elif k == "scale_in_set":
            extra = f"scale={c.get('scale')}"
        elif k == "text_height_ge_3_5mm":
            extra = f"h={c.get('text_height_m'):.4f}m"
        elif k == "all_13_keys_present":
            extra = f"present={c.get('present_count')}/{c.get('total')}"
        elif k == "dim_count_sufficient":
            extra = f"DisplayDim={c.get('dim_total')} thr={c.get('threshold')}"
        elif k == "centermark_count_sufficient":
            extra = f"CenterMark={c.get('centermark_total')} thr={c.get('threshold')}"
        elif k in ("has_tech_note", "has_ra_note", "has_datum_a"):
            extra = f"NoteBlock={c.get('noteblock_total')}"
        elif k == "refdoc_correct":
            extra = f"checked={c.get('checked_count')} bad={len(c.get('bad_ref', []))}"
        log(f"  {ok} {k}  {extra}")
    log(f"  → pass={res['pass']}  score_pass_count={res['score_pass_count']}/12")
    if res.get("issues"):
        log(f"  issues ({len(res['issues'])}):")
        for it in res["issues"]:
            log(f"    - {it}")


def main():
    default_path = r"c:\Users\Vision\Desktop\SW 相关\drw_output\LB26001-A-04-001_v4.SLDDRW"
    path = sys.argv[1] if len(sys.argv) > 1 else default_path

    log(f"[..] quality_check: {path}")
    try:
        res = quality_check(path)
    except Exception as exc:
        log(f"[ERROR] {exc}")
        log(traceback.format_exc())
        return 1

    _print_brief(res)

    # 写 JSON 落盘
    out_dir = os.path.dirname(path) or "."
    base = os.path.splitext(os.path.basename(path))[0]
    out_json = os.path.join(out_dir, f"{base}_qc.json")
    try:
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=2, default=str)
        log(f"\n[DONE] {out_json}")
    except Exception as exc:
        log(f"[WARN] 写 JSON 失败: {exc}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
