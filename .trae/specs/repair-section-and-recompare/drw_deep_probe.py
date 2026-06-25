"""
drw_deep_probe.py — 7 张真实公司工程图的深度采样

每张图提取：
  - title / path
  - sheets[]: paperCode/firstAngle/scale_num/scale_den/width_m/height_m/template
  - views[]: name, type, orient, scale_ratio, position, outline
  - views[].annotations: 按类型计数 + 对 Note 抓 GetText (兼容 GetSpecificAnnotation 属性化)
  - 自定义属性 13 项 (PROP_KEYS)
  - BOM/表格 (drw.GetTableAnnotations)
  - 全文档字体 / 文字高度 (GetUserPreferenceDoubleValue 89=textHeight)

输出:
  c:\\Users\\Vision\\Desktop\\SW 相关\\.trae\\specs\\repair-section-and-recompare\\deep_probe.json

兼容性要点：
  - pywin32 经常把无参方法当成属性 → 用 call(obj, name, *args) 双态助手
  - OpenDoc6 options=1|16|256 = Silent + LoadModel + DontDisplayReferenceWarnings
  - sys.stdout.reconfigure(line_buffering=True) + log() 而非 print
  - 关闭文档：sw.CloseDoc(call(drw, "GetTitle"))
"""
import os
import sys
import json
import time
import traceback
from collections import Counter

import pythoncom
import win32com.client as wc
from win32com.client import VARIANT

sys.stdout.reconfigure(line_buffering=True)


def log(*a, **kw):
    print(*a, **kw, flush=True)


ROOT = r"c:\Users\Vision\Desktop\SW 相关"
TARGETS = [
    r"3D转2D测试图纸\LB26001-A-04-048.SLDDRW",
    r"3D转2D测试图纸\LB26001-A-04-004.SLDDRW",
    r"3D转2D测试图纸\LB26001-A-04-001.SLDDRW",
    r"3D转2D测试图纸\LB26001-A-04-002.SLDDRW",
    r"3D转2D测试图纸\LB26001-A-04-006.SLDDRW",
    r"3D转2D测试图纸\LB26001-A-04-050.SLDDRW",
    r"3D转2D测试图纸\QTN-0488  MCIO 74Pin CABLE改头固定件A-V02.SLDDRW",
]
OUT_PATH = os.path.join(
    ROOT, ".trae", "specs", "repair-section-and-recompare", "deep_probe.json"
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

VIEW_TYPE_NAME = {
    1: "Sheet", 2: "Detail", 3: "Section", 4: "Section",
    5: "Auxiliary", 6: "Projection", 7: "Named", 8: "Detail",
    9: "Broken", 10: "AlternatePos", 11: "DetailCircle", 12: "Section",
}


def call(obj, name, *args):
    """兼容属性/方法双态：先 callable 调用，失败 fallback 属性。"""
    if obj is None:
        return None
    try:
        m = getattr(obj, name)
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


def get_note_text(ann):
    """从 IAnnotation 抓 Note 文本，兼容 GetSpecificAnnotation 属性化。"""
    txt = None
    try:
        spec = getattr(ann, "GetSpecificAnnotation", None)
        if spec is not None:
            note = spec() if callable(spec) else spec
            if note is not None:
                gt = getattr(note, "GetText", None)
                if gt is not None:
                    txt = gt() if callable(gt) else gt
    except Exception:
        pass
    if not txt:
        try:
            gt = getattr(ann, "GetText", None)
            if gt is not None:
                txt = gt() if callable(gt) else gt
        except Exception:
            pass
    return str(txt) if txt else ""


def open_doc(sw, path):
    e = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    w = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    # 3 = swDocDRAWING; options = 1 (Silent) | 16 (LoadModel) | 256 (DontDisplayReferenceWarnings)
    drw = sw.OpenDoc6(path, 3, 1 | 16 | 256, "", e, w)
    return drw, e.value, w.value


def collect_one(sw, path):
    info = {"path": path, "exists": os.path.exists(path)}
    if not info["exists"]:
        info["error"] = "file not found"
        return info

    log(f"  [open] {os.path.basename(path)}")
    drw, e_code, w_code = open_doc(sw, path)
    info["open_errors"] = e_code
    info["open_warnings"] = w_code
    if drw is None:
        info["error"] = "OpenDoc6 returned None"
        return info

    info["title"] = call(drw, "GetTitle")
    info["doc_path"] = call(drw, "GetPathName")

    # 文档级字体 / 文字高度
    info["text_height_m"] = call(drw, "GetUserPreferenceDoubleValue", 89)
    info["arrow_size_m"] = call(drw, "GetUserPreferenceDoubleValue", 2)
    info["unit_system"] = call(drw, "GetUserPreferenceIntegerValue", 127)
    info["length_unit_code"] = call(drw, "GetUserPreferenceIntegerValue", 35)
    info["decimal_places"] = call(drw, "GetUserPreferenceIntegerValue", 33)

    # ---- Sheets ----
    sheets = []
    sheet_names = to_list(call(drw, "GetSheetNames"))
    for sn in sheet_names:
        try:
            drw.ActivateSheet(sn)
        except Exception:
            pass
        s = call(drw, "GetCurrentSheet")
        if s is None:
            sheets.append({"name": sn, "error": "no sheet object"})
            continue
        prop2 = to_list(call(s, "GetProperties2"))
        size = to_list(call(s, "GetSize"))
        # GetSize 返回 [code, width_m, height_m] 或 [width_m, height_m]
        width_m = None
        height_m = None
        if size:
            if len(size) >= 3:
                try:
                    width_m = float(size[1])
                    height_m = float(size[2])
                except Exception:
                    pass
            if (width_m is None or height_m is None) and len(size) >= 2:
                try:
                    width_m = float(size[-2])
                    height_m = float(size[-1])
                except Exception:
                    pass
        sheets.append({
            "name": call(s, "GetName") or sn,
            "template": call(s, "GetTemplateName"),
            "paper_code": int(prop2[0]) if prop2 else None,
            "scale_num": prop2[2] if len(prop2) > 2 else None,
            "scale_den": prop2[3] if len(prop2) > 3 else None,
            "first_angle": int(prop2[4]) if len(prop2) > 4 else None,
            "width_m": width_m,
            "height_m": height_m,
            "raw_properties2": [str(x) for x in prop2],
        })
    info["sheets"] = sheets

    # ---- Views ----
    views = []
    ann_grand = Counter()
    section_count = 0
    note_total_texts = []
    try:
        v = call(drw, "GetFirstView")
        idx = 0
        while v is not None:
            vtype = call(v, "Type")
            type_name = VIEW_TYPE_NAME.get(vtype, str(vtype))
            if vtype in (3, 4, 12):
                section_count += 1

            # 标注扫描
            ann_types = Counter()
            ann_count = 0
            note_texts = []
            a = call(v, "GetFirstAnnotation3")
            while a is not None:
                t = call(a, "GetType")
                tn = ANN_TYPE_NAME.get(t, str(t))
                ann_types[tn] += 1
                ann_grand[tn] += 1
                ann_count += 1
                if tn == "Note":
                    txt = get_note_text(a)
                    if txt:
                        note_texts.append(txt)
                        note_total_texts.append(txt)
                a = call(a, "GetNext3")

            ref = call(v, "GetReferencedDocument")
            ref_path = call(ref, "GetPathName") if ref else None

            views.append({
                "index": idx,
                "name": call(v, "GetName2"),
                "type": vtype,
                "type_name": type_name,
                "orient": call(v, "GetOrientationName") or "",
                "scale_ratio": to_list(call(v, "ScaleRatio")),
                "position": to_list(call(v, "Position")),
                "outline": to_list(call(v, "GetOutline")),
                "ref_doc": ref_path,
                "annotation_count": ann_count,
                "annotation_types": dict(ann_types),
                "note_texts": note_texts,
            })
            idx += 1
            v = call(v, "GetNextView")
    except Exception as exc:
        views.append({"error": str(exc), "tb": traceback.format_exc()})

    info["views"] = views
    info["ann_total_by_type"] = dict(ann_grand)
    info["ann_total"] = sum(ann_grand.values())
    info["section_view_count"] = section_count

    # ---- 自定义属性 13 项 ----
    props_value = {}
    key_present = {}
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
    for _, cpm in cpm_list:
        try:
            for n in to_list(call(cpm, "GetNames")):
                keys_seen.add(n)
        except Exception:
            pass

    for k in PROP_KEYS:
        key_present[k] = (k in keys_seen)
        v_pick = ""
        for _, cpm in cpm_list:
            try:
                rv = cpm.Get5(k, False)
                # rv = (retval, val, resolved, wasResolved)
                val = rv[1] if len(rv) > 1 else ""
                resolved = rv[2] if len(rv) > 2 else ""
                v_ = (resolved or val or "")
                if v_:
                    v_pick = v_
                    break
            except Exception:
                pass
        props_value[k] = v_pick

    info["props"] = props_value
    info["props_key_present"] = key_present
    info["props_filled_count"] = sum(1 for k in PROP_KEYS if props_value.get(k))
    info["props_key_count"] = sum(1 for k in PROP_KEYS if key_present.get(k))

    # ---- 表格 / BOM ----
    tables = []
    try:
        tabs = call(drw, "GetTableAnnotations")
        if tabs:
            for t in tabs:
                tables.append({
                    "type": call(t, "Type"),
                    "title": call(t, "Title"),
                    "rows": call(t, "RowCount"),
                    "cols": call(t, "ColumnCount"),
                })
    except Exception as exc:
        info["tables_error"] = str(exc)
    info["tables"] = tables

    # 注释文本汇总
    info["note_texts_sample"] = note_total_texts[:30]
    info["note_text_total"] = len(note_total_texts)

    # 关闭
    try:
        sw.CloseDoc(call(drw, "GetTitle"))
    except Exception:
        pass

    return info


def main():
    log("[..] 连接 SolidWorks")
    try:
        sw = wc.GetActiveObject("SldWorks.Application")
    except Exception:
        sw = wc.Dispatch("SldWorks.Application")
        sw.Visible = True
        time.sleep(2)

    results = []
    for idx, rel in enumerate(TARGETS, 1):
        path = os.path.join(ROOT, rel) if not os.path.isabs(rel) else rel
        log(f"\n=== [{idx}/{len(TARGETS)}] {os.path.basename(path)} ===")
        try:
            info = collect_one(sw, path)
        except Exception as exc:
            info = {
                "path": path,
                "error": str(exc),
                "tb": traceback.format_exc(),
            }
        results.append(info)

        # 概要打印
        n_views = len(info.get("views", []))
        n_section = info.get("section_view_count", 0)
        n_ann = info.get("ann_total", 0)
        n_filled = info.get("props_filled_count", 0)
        n_keys = info.get("props_key_count", 0)
        log(
            f"  [SUM] views={n_views}  sections={n_section}  "
            f"annotations={n_ann}  props_filled={n_filled}/13  props_key={n_keys}/13"
        )

    # 写 JSON
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)

    size_kb = round(os.path.getsize(OUT_PATH) / 1024, 1)
    log(f"\n[DONE] {OUT_PATH}  ({size_kb} KB)")

    # 末尾再打一次每张图的概要表
    log("\n========== 总览 ==========")
    log(f"{'idx':<4}{'file':<55}{'views':<8}{'sec':<6}{'ann':<8}{'p_fill':<8}{'p_key':<7}")
    for i, r in enumerate(results, 1):
        fname = os.path.basename(r.get("path", ""))[:53]
        log(
            f"{i:<4}{fname:<55}"
            f"{len(r.get('views', [])):<8}"
            f"{r.get('section_view_count', 0):<6}"
            f"{r.get('ann_total', 0):<8}"
            f"{r.get('props_filled_count', 0):<8}"
            f"{r.get('props_key_count', 0):<7}"
        )


if __name__ == "__main__":
    main()
