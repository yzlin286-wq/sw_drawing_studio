"""
SLDDRW 探针 v2 (鲁棒版)
- pywin32 经常把无参方法当成属性，因此一律先尝试属性、再尝试调用
- 对每个图纸提取：标题/路径/单位/精度、Sheet 列表与 Sheet 属性、视图(Type/方向/比例/位置/外框/标注数)、
  自定义属性（先用 GetAll 兜底，再用 Get5 单条），表格(BOM)，注释样式
"""
import os
import json
import time
import traceback
import pythoncom
import win32com.client as win32com_client
from win32com.client import VARIANT

ROOT = r"c:\Users\Vision\Desktop\SW 相关"
TARGETS = [
    r"3D转2D测试图纸\LB26001-A-04-001.SLDDRW",
    r"3D转2D测试图纸\LB26001-A-04-002.SLDDRW",
    r"3D转2D测试图纸\LB26001-A-04-006.SLDDRW",
    r"3D转2D测试图纸\LB26001-A-04-050.SLDDRW",
    r"3D转2D测试图纸\QTN-0488  MCIO 74Pin CABLE改头固定件A-V02.SLDDRW",
    r"3D转2D测试图纸\昆仑BP_6xU2_NVME-J20仿生头8pin.SLDDRW",
]
OUT = os.path.join(ROOT, ".trae", "specs", "study-solidworks-skill", "drw_probe.json")

# ---- pywin32 双态助手 ----
def m(obj, name, *args, default=None):
    """读取 COM 成员，兼容属性/方法双态。"""
    if obj is None:
        return default
    try:
        member = getattr(obj, name)
    except Exception:
        return default
    try:
        if args:
            return member(*args) if callable(member) else member
        if callable(member):
            try:
                return member()
            except TypeError:
                return member
        return member
    except Exception:
        return default

def to_list(v):
    if v is None:
        return []
    try:
        return list(v)
    except Exception:
        return [v]

def open_drw(sw, path):
    errs = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    warns = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    # DRAWING + Silent (1) + LoadModel (16)；不要 ReadOnly，否则视图层不加载
    drw = sw.OpenDoc6(path, 3, 1 | 16, "", errs, warns)
    return drw, errs.value, warns.value

print("[..] 连接 SolidWorks")
try:
    sw = win32com_client.GetActiveObject("SldWorks.Application")
except Exception:
    sw = win32com_client.Dispatch("SldWorks.Application")
    sw.Visible = True
    time.sleep(2)

results = []
for rel in TARGETS:
    path = os.path.join(ROOT, rel)
    if not os.path.exists(path):
        continue
    print(f"\n=== {os.path.basename(path)} ===")
    drw, e, w = open_drw(sw, path)
    if drw is None:
        print(f"  [FAIL] errors={e}")
        continue
    info = {"file": rel, "errors": e, "warnings": w}

    info["title"] = m(drw, "GetTitle")
    info["path"] = m(drw, "GetPathName")
    # 单位与精度（数值代码先取，含义在最后归纳）
    info["unit_system"] = m(drw, "GetUserPreferenceIntegerValue", 127)
    info["length_unit_code"] = m(drw, "GetUserPreferenceIntegerValue", 35)
    info["decimal_places"] = m(drw, "GetUserPreferenceIntegerValue", 33)
    info["dual_dim"] = m(drw, "GetUserPreferenceToggle", 94)
    info["text_height_m"] = m(drw, "GetUserPreferenceDoubleValue", 89)
    info["arrow_size_m"] = m(drw, "GetUserPreferenceDoubleValue", 2)

    # Sheet
    sheet = m(drw, "GetCurrentSheet")
    sheets = []
    sheet_names = to_list(m(drw, "GetSheetNames"))
    info["sheet_names"] = sheet_names
    for sn in sheet_names:
        # 切换到该 Sheet
        try:
            drw.ActivateSheet(sn)
        except Exception:
            pass
        s = m(drw, "GetCurrentSheet")
        if s is None:
            continue
        props = to_list(m(s, "GetProperties2"))
        size = to_list(m(s, "GetSize"))
        sheets.append({
            "name": m(s, "GetName"),
            "template": m(s, "GetTemplateName"),
            "properties2": props,   # [paperSize, templateIn, scaleNum, scaleDen, firstAngle, ...]
            "size_w_h_m": size,
        })
    info["sheets"] = sheets

    # 视图（属性而非方法）
    views_data = []
    try:
        view = m(drw, "GetFirstView")
        idx = 0
        while view is not None:
            v = {
                "index": idx,
                "name": m(view, "GetName2"),
                "type": m(view, "Type"),
                "scale_ratio": to_list(m(view, "ScaleRatio")),
                "position": to_list(m(view, "Position")),
                "outline_xy_min_max_m": to_list(m(view, "GetOutline")),
                "orientation": m(view, "GetOrientationName"),
            }
            ref = m(view, "GetReferencedDocument")
            v["ref_doc"] = m(ref, "GetPathName") if ref else None

            # 标注计数
            ann = m(view, "GetFirstAnnotation3")
            cnt = 0
            types = {}
            while ann is not None:
                cnt += 1
                t = m(ann, "GetType")
                types[str(t)] = types.get(str(t), 0) + 1
                ann = m(ann, "GetNext3")
            v["annotation_count"] = cnt
            v["annotation_type_hist"] = types
            views_data.append(v)
            idx += 1
            view = m(view, "GetNextView")
    except Exception as exc:
        views_data.append({"error": str(exc)})
    info["views"] = views_data

    # 自定义属性 —— 用 GetAll3 一次拿完
    try:
        cpm = drw.Extension.CustomPropertyManager("")
        names = to_list(m(cpm, "GetNames"))
        props = {}
        try:
            # GetAll3 -> (PropNames, PropTypes, PropValues, ResolvedValues, PropLink)
            res = cpm.GetAll3()
            if res and len(res) >= 4:
                pnames = to_list(res[0])
                pvalues = to_list(res[2])
                presolved = to_list(res[3])
                for i, n in enumerate(pnames):
                    props[n] = {
                        "value": pvalues[i] if i < len(pvalues) else None,
                        "resolved": presolved[i] if i < len(presolved) else None,
                    }
        except Exception as exc:
            # fallback: Get5 by-ref
            for n in names:
                try:
                    val_o = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_BSTR, "")
                    res_o = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_BSTR, "")
                    was_o = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_BOOL, False)
                    cpm.Get5(n, False, val_o, res_o, was_o)
                    props[n] = {"value": val_o.value, "resolved": res_o.value}
                except Exception as e2:
                    props[n] = {"error": str(e2)}
        info["custom_properties"] = props
    except Exception as exc:
        info["custom_properties_error"] = str(exc)

    # 表格 / BOM
    tables = []
    try:
        anns = m(drw, "GetTableAnnotations")
        if anns:
            for t in anns:
                tables.append({
                    "type": m(t, "Type"),
                    "title": m(t, "Title"),
                    "rows": m(t, "RowCount"),
                    "cols": m(t, "ColumnCount"),
                })
    except Exception:
        pass
    info["tables"] = tables

    # 关闭
    try:
        sw.CloseDoc(m(drw, "GetTitle"))
    except Exception:
        pass

    results.append(info)
    print(f"  [OK] sheets={len(sheets)} views={len(views_data)} props={len(info.get('custom_properties', {}) or {})}")

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2, default=str)
print(f"\n[DONE] {OUT}")
