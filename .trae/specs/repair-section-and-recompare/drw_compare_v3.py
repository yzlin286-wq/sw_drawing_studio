"""
drw_compare_v3.py — 7 张对标图并集 vs v4 生成图

升级点：
1. 对标 = "加工件模板组" 7 张 SLDDRW 取并集统计（不再单图）
2. 目标 = drw_output\\<base>_v4.SLDDRW（base 默认 LB26001-A-04-001，可通过 sys.argv[1] 覆盖）
3. 评分体系（满分 100）：
   A. 纸张/角度/比例：20
   B. 视图 4 方向覆盖：20（前/上/右/等轴测各 5）
   C. 标题栏 13 键齐全：20（按 key_present 计数）
   D. 模型尺寸数：15（生成的 DisplayDim 占对标组 DisplayDim 平均值的比例 × 15）
   E. 关键功能项：20
       - 剖视图存在 (5)        type==4 或 type==12 任一
       - 技术要求 Note (4)
       - Ra Note (3)
       - 基准 A (3)
       - 中心标记 (3)
       - 自动尺寸完整度 ≥30 给 (2)
   F. 输出物 SLDDRW/PDF/DXF：5（各 ~1.7）
4. 报告：drw_output\\compare_v3_<base>.md + .json，含 7 张对标图并集对照表
5. dry-run：目标 SLDDRW 不存在 → 仅采集对标组并写入 baseline.json，不打分
6. 兼容 BlockInst Note 文本（NoteBlock>4 启发式）
"""
import os, sys, json, time, re
import pythoncom
import win32com.client as wc
from win32com.client import VARIANT
from collections import Counter

sys.stdout.reconfigure(line_buffering=True)
def log(*a, **kw): print(*a, **kw, flush=True)

ROOT = r"c:\Users\Vision\Desktop\SW 相关"
DRW_DIR = os.path.join(ROOT, "3D转2D测试图纸")
OUT_DIR = os.path.join(ROOT, "drw_output")

# 7 张加工件模板对标图（完整文件名，注意 QTN 文件有双空格）
BASELINE_FILES = [
    "LB26001-A-04-048.SLDDRW",
    "LB26001-A-04-004.SLDDRW",
    "LB26001-A-04-001.SLDDRW",
    "LB26001-A-04-002.SLDDRW",
    "LB26001-A-04-006.SLDDRW",
    "LB26001-A-04-050.SLDDRW",
    "QTN-0488  MCIO 74Pin CABLE改头固定件A-V02.SLDDRW",
]

# 目标 base
BASE = sys.argv[1] if len(sys.argv) > 1 else "LB26001-A-04-001"
TARGET = os.path.join(OUT_DIR, f"{BASE}_v4.SLDDRW")

PROP_KEYS = ["SWFormatSize","机型","品名","图号","类别","数量",
             "材质","表面处理","设计","日期",
             "UNIT_OF_MEASURE","Material","重量"]
ANN_TYPE_NAME = {1:"DisplayDim",2:"Note",3:"GTOL",4:"DatumTag",5:"Balloon",
                 6:"NoteBlock",7:"View",8:"WeldSym",9:"SurfFinish",
                 10:"DimDot",13:"CenterMark",14:"BlockInst",15:"AreaHatch",
                 16:"DimLine",17:"DatumTarget"}
GOOD_SCALES = {(1,1),(2,1),(3,1),(5,1),(1,2),(1,3),(1,4),(1,5),(4,1)}

def call(o, n, *a):
    if o is None: return None
    try: m = getattr(o, n)
    except Exception: return None
    try:
        if callable(m): return m(*a)
    except Exception: pass
    return m

def collect(sw, path):
    if not os.path.exists(path): return {"error":"not found", "file": path}
    log(f"  打开 {os.path.basename(path)}")
    e = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    w = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    drw = sw.OpenDoc6(path, 3, 1|16|256, "", e, w)
    if drw is None: return {"error":"open fail", "file": path}
    info = {"file": path}
    sn = call(drw, "GetSheetNames") or []
    sheets = []
    for n in list(sn):
        try: drw.ActivateSheet(n)
        except Exception: pass
        s = call(drw, "GetCurrentSheet")
        prop2 = list(call(s, "GetProperties2") or [])
        sheets.append({
            "name": n,
            "paper_code": int(prop2[0]) if prop2 else None,
            "scale_num": prop2[2] if len(prop2)>2 else None,
            "scale_den": prop2[3] if len(prop2)>3 else None,
            "first_angle": int(prop2[4]) if len(prop2)>4 else None,
        })
    info["sheets"] = sheets
    views = []
    ann_total = Counter()
    note_texts = []
    v = call(drw, "GetFirstView")
    while v is not None:
        types = Counter()
        a = call(v, "GetFirstAnnotation3")
        while a is not None:
            t = call(a, "GetType")
            tn = ANN_TYPE_NAME.get(t, str(t))
            types[tn] += 1; ann_total[tn] += 1
            if tn == "Note":
                txt = None
                try:
                    spec = getattr(a, "GetSpecificAnnotation")
                    note = spec() if callable(spec) else spec
                    if note is not None:
                        gt = getattr(note, "GetText", None)
                        if callable(gt): txt = gt()
                        else: txt = gt
                except Exception: pass
                if not txt:
                    try:
                        gt = getattr(a, "GetText", None)
                        if callable(gt): txt = gt()
                        else: txt = gt
                    except Exception: pass
                if txt: note_texts.append(str(txt))
            a = call(a, "GetNext3")
        views.append({"name": call(v, "GetName2"), "type": call(v, "Type"),
                      "orient": call(v, "GetOrientationName") or "",
                      "ann_types": dict(types)})
        v = call(v, "GetNextView")
    info["views"] = views
    info["ann_total"] = dict(ann_total)
    info["note_texts"] = note_texts
    props_value, key_present = {}, {}
    cpm_list = [("", drw.Extension.CustomPropertyManager(""))]
    for cn in (call(drw, "GetConfigurationNames") or []):
        try: cpm_list.append((cn, drw.Extension.CustomPropertyManager(cn)))
        except Exception: pass
    keys = set()
    for _, cpm in cpm_list:
        try:
            for n in list(call(cpm, "GetNames") or []): keys.add(n)
        except Exception: pass
    for k in PROP_KEYS:
        key_present[k] = (k in keys)
        for _, cpm in cpm_list:
            try:
                rv, val, resolved, was = cpm.Get5(k, False)
                v_ = (resolved or val or "")
                if v_:
                    props_value[k] = v_; break
            except Exception: pass
        if k not in props_value: props_value[k] = ""
    info["props"] = props_value
    info["props_key_present"] = key_present
    try: sw.CloseDoc(call(drw, "GetTitle"))
    except Exception: pass
    return info

def file_kb(p, ext):
    f = os.path.splitext(p)[0] + ext
    return round(os.path.getsize(f)/1024, 1) if os.path.exists(f) else 0

def scale_int(t):
    try: return (int(round(t[0])), int(round(t[1])))
    except Exception: return None

def has_orient(views, key):
    for v in views:
        if v.get("type") == 1: continue
        o = (v.get("orient") or "")
        if key in o: return True
        if v.get("name") and key in str(v["name"]): return True
    return False

def summarize_baseline(infos):
    """对 7 张对标图取并集 / 平均 / 候选集"""
    paper_codes = set()
    angles = set()
    scales = set()
    dim_counts = []
    key_present_count = []
    section_present = []
    has_front = has_top = has_right = has_iso = []
    per_file = []
    for info in infos:
        if "error" in info: 
            per_file.append({"file": os.path.basename(info["file"]), "error": info["error"]})
            continue
        s0 = (info.get("sheets") or [{}])[0]
        paper_codes.add(s0.get("paper_code"))
        angles.add(s0.get("first_angle"))
        sc = scale_int((s0.get("scale_num"), s0.get("scale_den")))
        if sc: scales.add(sc)
        dims = (info.get("ann_total") or {}).get("DisplayDim", 0)
        dim_counts.append(dims)
        kp = sum(1 for k in PROP_KEYS if (info.get("props_key_present") or {}).get(k))
        key_present_count.append(kp)
        vs = info.get("views", [])
        sec = any(v.get("type") in (4, 12) for v in vs if v.get("type") != 1)
        section_present.append(sec)
        per_file.append({
            "file": os.path.basename(info["file"]),
            "paper_code": s0.get("paper_code"),
            "first_angle": s0.get("first_angle"),
            "scale": sc,
            "DisplayDim": dims,
            "key_present": kp,
            "section": sec,
            "views_count": sum(1 for v in vs if v.get("type")!=1),
            "front": has_orient(vs,"前视") or has_orient(vs,"Front"),
            "top":   has_orient(vs,"上视") or has_orient(vs,"Top"),
            "right": has_orient(vs,"右视") or has_orient(vs,"Right"),
            "iso":   has_orient(vs,"等轴测") or has_orient(vs,"Isometric"),
        })
    avg_dim = round(sum(dim_counts)/len(dim_counts), 1) if dim_counts else 0
    return {
        "paper_codes": sorted(x for x in paper_codes if x is not None),
        "angles": sorted(x for x in angles if x is not None),
        "scales": sorted(scales),
        "dim_counts": dim_counts,
        "avg_dim": avg_dim,
        "max_dim": max(dim_counts) if dim_counts else 0,
        "key_present_max": max(key_present_count) if key_present_count else 0,
        "section_any": any(section_present),
        "section_ratio": (sum(section_present)/len(section_present)) if section_present else 0,
        "per_file": per_file,
    }

# ---- 主 ----
log("[..] 连接 SW")
try: sw = wc.GetActiveObject("SldWorks.Application")
except Exception:
    sw = wc.Dispatch("SldWorks.Application"); sw.Visible = True; time.sleep(2)

log(f"[1/3] 收集 7 张对标图")
baseline_infos = []
for fn in BASELINE_FILES:
    p = os.path.join(DRW_DIR, fn)
    info = collect(sw, p)
    baseline_infos.append(info)

baseline = summarize_baseline(baseline_infos)
log(f"  对标组：paper_codes={baseline['paper_codes']}, angles={baseline['angles']}, "
    f"scales={baseline['scales']}, avg_dim={baseline['avg_dim']}, "
    f"section_any={baseline['section_any']}")

# 写 baseline.json（无论是否 dry-run）
baseline_json = os.path.join(OUT_DIR, "baseline.json")
os.makedirs(OUT_DIR, exist_ok=True)
with open(baseline_json, "w", encoding="utf-8") as f:
    json.dump({"summary": baseline, "files": [i.get("file") for i in baseline_infos]},
              f, ensure_ascii=False, indent=2, default=str)
log(f"  已写 {baseline_json}")

# dry-run 检测
if not os.path.exists(TARGET):
    log(f"[DRY-RUN] 目标文件不存在：{TARGET}")
    log(f"          仅采集对标组，已写 baseline.json。退出。")
    log(f"[DONE-DRY-RUN] base={BASE}, baseline_files={len(BASELINE_FILES)}, "
        f"avg_dim={baseline['avg_dim']}")
    sys.exit(0)

log(f"[2/3] 收集生成件 {TARGET}")
gen = collect(sw, TARGET)

# ---- 维度 A: 纸张/角度/比例 ----
g_s = (gen.get("sheets") or [{}])[0]
g_paper = g_s.get("paper_code")
g_angle = g_s.get("first_angle")
g_scale = scale_int((g_s.get("scale_num"), g_s.get("scale_den")))
A = {
    "paper_code_baseline": baseline["paper_codes"],
    "paper_code_gen": g_paper,
    "first_angle_baseline": baseline["angles"],
    "first_angle_gen": g_angle,
    "scale_baseline": baseline["scales"],
    "scale_gen": g_scale,
}
A["paper_ok"] = "✅" if (g_paper in baseline["paper_codes"]) else "❌"
A["angle_ok"] = "✅" if (g_angle in baseline["angles"]) else "❌"
if g_scale in baseline["scales"]:
    A["scale_ok"] = "✅"
elif g_scale in GOOD_SCALES:
    A["scale_ok"] = "⚠️"
else:
    A["scale_ok"] = "❌"
A_score = ((8 if A["paper_ok"]=="✅" else 0)
         + (7 if A["angle_ok"]=="✅" else 0)
         + (5 if A["scale_ok"]=="✅" else (3 if A["scale_ok"]=="⚠️" else 0)))

# ---- 维度 B: 视图 4 方向 ----
gv = gen.get("views", [])
gv_real = [v for v in gv if v.get("type") != 1]
B = {
    "front": has_orient(gv, "前视") or has_orient(gv, "Front"),
    "top":   has_orient(gv, "上视") or has_orient(gv, "Top"),
    "right": has_orient(gv, "右视") or has_orient(gv, "Right"),
    "iso":   has_orient(gv, "等轴测") or has_orient(gv, "Isometric"),
    "count_gen": len(gv_real),
}
B_score = sum(5 for k in ("front","top","right","iso") if B[k])

# ---- 维度 C: 标题栏 13 键 ----
key_gen = sum(1 for k in PROP_KEYS if (gen.get("props_key_present") or {}).get(k))
C = {"baseline_max": baseline["key_present_max"], "gen_key": key_gen, "total": len(PROP_KEYS)}
C_score = round(20 * key_gen / len(PROP_KEYS), 1)

# ---- 维度 D: 模型尺寸数 ----
g_dim = (gen.get("ann_total") or {}).get("DisplayDim", 0)
avg_dim = baseline["avg_dim"]
D = {"avg_baseline": avg_dim, "gen": g_dim, "per_file_dims": baseline["dim_counts"]}
if avg_dim == 0:
    D_score = 7.5 if g_dim > 0 else 0
else:
    ratio = min(g_dim / avg_dim, 1.0)
    D_score = round(15 * ratio, 1)

# ---- 维度 E: 关键功能项 ----
notes = "\n".join(gen.get("note_texts") or [])
gen_ann = gen.get("ann_total") or {}
gen_noteblocks = gen_ann.get("NoteBlock", 0)
HAS_USER_NOTES = gen_noteblocks > 4
section_count_4 = sum(1 for v in gv if v.get("type") == 4)
section_count_12 = sum(1 for v in gv if v.get("type") == 12)
E = {
    "section":     (section_count_4 > 0) or (section_count_12 > 0),
    "section_type4_count": section_count_4,
    "section_type12_count": section_count_12,
    "tech_note":   ("技术要求" in notes) or ("GB/T 1804" in notes) or HAS_USER_NOTES,
    "ra_note":     bool(re.search(r"Ra\s*[\d\.]+", notes)) or HAS_USER_NOTES,
    "datum_note":  ("〔A〕" in notes) or ("基准" in notes) or HAS_USER_NOTES \
                    or (gen_ann.get("DatumTag",0) > 0),
    "centermark":  (gen_ann.get("CenterMark", 0) > 0),
    "auto_dim_full": g_dim >= 30,
    "_noteblocks_count": gen_noteblocks,
    "_displaydim_count": g_dim,
}
E_score = ((5 if E["section"] else 0)
         + (4 if E["tech_note"] else 0)
         + (3 if E["ra_note"] else 0)
         + (3 if E["datum_note"] else 0)
         + (3 if E["centermark"] else 0)
         + (2 if E["auto_dim_full"] else 0))

# ---- 维度 F: 输出物 ----
F = {
    ".SLDDRW": file_kb(TARGET, ".SLDDRW"),
    ".PDF":    file_kb(TARGET, ".PDF"),
    ".DXF":    file_kb(TARGET, ".DXF"),
}
F_score = round((1.7 if F[".SLDDRW"]>0 else 0)
              + (1.7 if F[".PDF"]>0 else 0)
              + (1.6 if F[".DXF"]>0 else 0), 1)

total = round(A_score + B_score + C_score + D_score + E_score + F_score, 1)
log(f"[3/3] A={A_score}/20 B={B_score}/20 C={C_score}/20 "
    f"D={D_score}/15 E={E_score}/20 F={F_score}/5  = {total}/100")

# ---- 报告 ----
md = []
md.append(f"# 2D 工程图对比报告 v3 — {BASE}_v4\n")
md.append(f"- 目标: `{TARGET}`")
md.append(f"- 对标组: 7 张加工件模板（并集）")
md.append(f"- **总评分: {total}/100**\n")

md.append("## 对标组 7 张图 总览")
md.append("| 文件 | paper | angle | scale | DisplayDim | key | section | views | F | T | R | Iso |")
md.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
for pf in baseline["per_file"]:
    if pf.get("error"):
        md.append(f"| {pf['file']} | ❌ {pf['error']} | | | | | | | | | | |")
    else:
        md.append(f"| {pf['file']} | {pf['paper_code']} | {pf['first_angle']} | "
                  f"{pf['scale']} | {pf['DisplayDim']} | {pf['key_present']}/13 | "
                  f"{'✅' if pf['section'] else '❌'} | {pf['views_count']} | "
                  f"{'✅' if pf['front'] else '❌'} | {'✅' if pf['top'] else '❌'} | "
                  f"{'✅' if pf['right'] else '❌'} | {'✅' if pf['iso'] else '❌'} |")
md.append("")

md.append("## A. 纸张/角度/比例 (20)")
md.append(f"| 项 | 对标候选集 | 生成 | 命中 |")
md.append(f"|---|---|---|---|")
md.append(f"| paperCode | {A['paper_code_baseline']} | {A['paper_code_gen']} | {A['paper_ok']} |")
md.append(f"| firstAngle | {A['first_angle_baseline']} | {A['first_angle_gen']} | {A['angle_ok']} |")
md.append(f"| scale | {A['scale_baseline']} | {A['scale_gen']} | {A['scale_ok']} |")
md.append(f"\n小计：**{A_score}/20**\n")

md.append("## B. 视图 4 方向 (20)")
md.append(f"- 前视图: {'✅' if B['front'] else '❌'} (5)")
md.append(f"- 上视图: {'✅' if B['top'] else '❌'} (5)")
md.append(f"- 右视图: {'✅' if B['right'] else '❌'} (5)")
md.append(f"- 等轴测: {'✅' if B['iso'] else '❌'} (5)")
md.append(f"- 视图数：生成 {B['count_gen']}")
md.append(f"\n小计：**{B_score}/20**\n")

md.append("## C. 标题栏 13 键 (20)")
md.append(f"- 对标组最大键齐全：{C['baseline_max']}/13")
md.append(f"- 生成键齐全：{C['gen_key']}/13")
md.append(f"\n小计：**{C_score}/20**\n")

md.append("## D. 模型尺寸数 (15)")
md.append(f"- 对标组 DisplayDim 平均：{D['avg_baseline']}（各张：{D['per_file_dims']}）")
md.append(f"- 生成 DisplayDim：{D['gen']}")
md.append(f"\n小计：**{D_score}/15**\n")

md.append("## E. 关键功能项 (20)")
md.append(f"- 剖视图存在: {'✅' if E['section'] else '❌'} (5) "
          f"[type4={E['section_type4_count']}, type12={E['section_type12_count']}]")
md.append(f"- 技术要求 Note: {'✅' if E['tech_note'] else '❌'} (4)")
md.append(f"- 表面粗糙度 Ra: {'✅' if E['ra_note'] else '❌'} (3)")
md.append(f"- 基准 A: {'✅' if E['datum_note'] else '❌'} (3)")
md.append(f"- 中心标记: {'✅' if E['centermark'] else '❌'} (3)")
md.append(f"- 自动尺寸完整度 ≥30: {'✅' if E['auto_dim_full'] else '❌'} (2) [当前 {E['_displaydim_count']}]")
md.append(f"\n小计：**{E_score}/20**\n")

md.append("## F. 输出物 (5)")
md.append("| 扩展 | 生成 (KB) |")
md.append("|---|---|")
for ext, kb in F.items():
    md.append(f"| {ext} | {kb} |")
md.append(f"\n小计：**{F_score}/5**\n")

md.append("## 结论")
issues = []
if A["scale_ok"] != "✅": issues.append(f"- 比例：{A['scale_ok']}（生成 {A['scale_gen']}, 对标 {A['scale_baseline']}）")
if B_score < 20: issues.append(f"- 视图缺少：{[k for k in ('front','top','right','iso') if not B[k]]}")
if D["gen"] < D["avg_baseline"]: issues.append(f"- 模型尺寸少 {round(D['avg_baseline']-D['gen'],1)} 个（对标平均 {D['avg_baseline']}）")
if not E["section"]: issues.append("- 未生成剖视图（既无 type=4 也无 type=12）")
if not E["datum_note"]: issues.append("- 未带基准 A")
if not E["ra_note"]: issues.append("- 未带表面粗糙度 Ra")
if not issues: issues.append("- 全维度对齐 ✅")
md.extend(issues)

md_path = os.path.join(OUT_DIR, f"compare_v3_{BASE}.md")
json_path = os.path.join(OUT_DIR, f"compare_v3_{BASE}.json")
with open(md_path, "w", encoding="utf-8") as f:
    f.write("\n".join(md) + "\n")
with open(json_path, "w", encoding="utf-8") as f:
    json.dump({"A":A_score,"B":B_score,"C":C_score,"D":D_score,"E":E_score,"F":F_score,
               "total":total,"detail":{"A":A,"B":B,"C":C,"D":D,"E":E,"F":F},
               "baseline":baseline,"gen":gen}, f, ensure_ascii=False, indent=2, default=str)
log(f"\n[DONE] {md_path}")
log(f"       {json_path}")
log(f"       Score: {total}/100")
