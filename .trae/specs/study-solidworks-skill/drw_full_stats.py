"""
全量扫描 SLDDRW，统计：纸张/比例/投影/视图布局/标注种类/自定义属性键集合
"""
import os, json, time, glob, traceback, pythoncom, sys
import win32com.client as wc
from win32com.client import VARIANT
from collections import Counter, defaultdict

sys.stdout.reconfigure(line_buffering=True)
def log(*a, **kw):
    print(*a, **kw, flush=True)

ROOT = r"c:\Users\Vision\Desktop\SW 相关"
DRW_DIR = os.path.join(ROOT, "3D转2D测试图纸")
OUT = os.path.join(ROOT, ".trae", "specs", "study-solidworks-skill", "drw_full_stats.json")

# 论文里的纸张尺寸枚举 swDwgPaperSizes_e
PAPER_E = {0:"A_LANDSCAPE",1:"A_PORTRAIT",2:"B_LANDSCAPE",3:"C_LANDSCAPE",
           4:"D_LANDSCAPE",5:"E_LANDSCAPE",6:"A4_LANDSCAPE",7:"A4_PORTRAIT",
           8:"A3_LANDSCAPE",9:"A2_LANDSCAPE",10:"A1_LANDSCAPE",11:"A0_LANDSCAPE",
           12:"USER_DEFINED"}
ANN_TYPE = {1:"DisplayDim",2:"Note",3:"GTOL",4:"DatumTag",5:"BalloonAnn",
            6:"Note(注释/标题栏块)",7:"View",8:"WeldSym",9:"SfSym",
            10:"DimDot",13:"CenterMark",14:"BlockInst",15:"AreaHatch",
            16:"DimensionLine"}

def call(obj, name, *args):
    if obj is None: return None
    try: m = getattr(obj, name)
    except Exception: return None
    try:
        if callable(m): return m(*args)
    except Exception: pass
    try: return m
    except Exception: return None

log("[..] 连接 SW")
try: sw = wc.GetActiveObject("SldWorks.Application")
except Exception:
    sw = wc.Dispatch("SldWorks.Application"); sw.Visible = True; time.sleep(2)

# 抑制对话框
try:
    sw.SetUserPreferenceToggle(8, False)   # swInputDimValOnCreate -> not relevant but harmless
    sw.SetUserPreferenceToggle(196, True)  # swDocumentLoadDoNotPrompt
except Exception as exc:
    log("  设置静默偏好失败:", exc)

paths = sorted(glob.glob(os.path.join(DRW_DIR, "*.SLDDRW")))
log(f"共 {len(paths)} 张 SLDDRW")

results = []
for p in paths:
    base = os.path.basename(p)
    log(f"\n=== {base}")
    e = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    w = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    # Silent (1) + LoadModel (16) + DontDisplayReferenceWarnings (256) ≈ 273
    drw = sw.OpenDoc6(p, 3, 1 | 16 | 256, "", e, w)
    if drw is None:
        log("  [FAIL]", e.value); continue
    info = {"file": base}

    sheets = []
    sn = call(drw, "GetSheetNames") or []
    for n in list(sn):
        try: drw.ActivateSheet(n)
        except Exception: pass
        s = call(drw, "GetCurrentSheet")
        if s is None: continue
        prop2 = list(call(s, "GetProperties2") or [])
        sheet = {
            "name": n,
            "paper_code": int(prop2[0]) if prop2 else None,
            "paper_label": PAPER_E.get(int(prop2[0]) if prop2 else -1, "?"),
            "scale_num": prop2[2] if len(prop2)>2 else None,
            "scale_den": prop2[3] if len(prop2)>3 else None,
            "first_angle": int(prop2[4]) if len(prop2)>4 else None,  # 1=第一角
            "width_m": prop2[5] if len(prop2)>5 else None,
            "height_m": prop2[6] if len(prop2)>6 else None,
            "template": call(s, "GetTemplateName"),
        }
        sheets.append(sheet)
    info["sheets"] = sheets

    # 视图统计
    v_list = []
    v = call(drw, "GetFirstView")
    while v is not None:
        ann_types = Counter()
        a = call(v, "GetFirstAnnotation3")
        cnt = 0
        while a is not None:
            cnt += 1
            t = call(a, "GetType")
            ann_types[ANN_TYPE.get(t, str(t))] += 1
            a = call(a, "GetNext3")
        v_list.append({
            "name": call(v, "GetName2"),
            "type": call(v, "Type"),
            "orient": call(v, "GetOrientationName"),
            "scale": list(call(v, "ScaleRatio") or []),
            "pos_m": list(call(v, "Position") or []),
            "outline_m": list(call(v, "GetOutline") or []),
            "ann_total": cnt,
            "ann_types": dict(ann_types),
        })
        v = call(v, "GetNextView")
    info["views"] = v_list

    # 自定义属性
    try:
        cpm = drw.Extension.CustomPropertyManager("")
        names = list(call(cpm, "GetNames") or [])
        prop = {}
        for n in names:
            try:
                rv, value, resolved, was = cpm.Get5(n, False)
                prop[n] = resolved or value
            except Exception:
                prop[n] = ""
        info["props"] = prop
    except Exception as exc:
        info["props_err"] = str(exc)

    sw.CloseDoc(call(drw, "GetTitle"))
    results.append(info)

# 汇总
agg = {
    "total": len(results),
    "paper": Counter(),
    "scale": Counter(),
    "first_angle": Counter(),
    "view_orient": Counter(),
    "view_type": Counter(),
    "prop_keys": Counter(),
    "prop_value_examples": defaultdict(set),
}
for r in results:
    for s in r.get("sheets", []):
        agg["paper"][s.get("paper_label")] += 1
        sd, sn_ = s.get("scale_den"), s.get("scale_num")
        if sd and sn_:
            agg["scale"][f"{int(sn_)}:{int(sd)}"] += 1
        agg["first_angle"][s.get("first_angle")] += 1
    for v in r.get("views", []):
        if v["type"] != 1:
            agg["view_orient"][v.get("orient") or ""] += 1
            agg["view_type"][v.get("type")] += 1
    for k, val in (r.get("props") or {}).items():
        agg["prop_keys"][k] += 1
        if val:
            agg["prop_value_examples"][k].add(str(val)[:40])
            if len(agg["prop_value_examples"][k]) > 8:
                agg["prop_value_examples"][k] = set(list(agg["prop_value_examples"][k])[:8])

# 序列化
agg2 = {
    "total": agg["total"],
    "paper": dict(agg["paper"]),
    "scale": dict(agg["scale"]),
    "first_angle": dict(agg["first_angle"]),
    "view_orient": dict(agg["view_orient"]),
    "view_type": dict(agg["view_type"]),
    "prop_keys": dict(agg["prop_keys"]),
    "prop_value_examples": {k: sorted(list(v)) for k, v in agg["prop_value_examples"].items()},
}
out = {"summary": agg2, "items": results}
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2, default=str)
log("\n=== SUMMARY ===")
for k, v in agg2.items():
    log(f"{k}: {v}")
log(f"\n[DONE] {OUT}")
