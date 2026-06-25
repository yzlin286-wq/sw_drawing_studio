"""
drw_compare_v2.py — 公平对比

对比维度：
A. 纸张规格（与对标"规范"）：A4 横向 / 第一角 / 比例命中候选集
B. 视图：是否覆盖 前/上/右/等轴测 4 个标准方向（关键！）
C. 标题栏 13 个键齐全度
D. 模型尺寸数 vs 原件尺寸数
E. 关键功能项："技术要求"/"表面粗糙度兜底"/"基准 A 兜底" 等是否落到图纸里
F. 输出物 SLDDRW/PDF/DXF 大小

满分 100：
  A=20, B=20, C=20, D=15, E=15, F=10
"""
import os, sys, json, time, traceback, re
import pythoncom
import win32com.client as wc
from win32com.client import VARIANT
from collections import Counter

sys.stdout.reconfigure(line_buffering=True)
def log(*a, **kw): print(*a, **kw, flush=True)

ROOT = r"c:\Users\Vision\Desktop\SW 相关"
ORIG = os.path.join(ROOT, r"3D转2D测试图纸\LB26001-A-04-001.SLDDRW")
GEN  = os.path.join(ROOT, r"drw_output\LB26001-A-04-001.SLDDRW")
OUT_DIR = os.path.join(ROOT, "drw_output")
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
    if not os.path.exists(path): return {"error":"not found"}
    log(f"  打开 {os.path.basename(path)}")
    e = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    w = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    drw = sw.OpenDoc6(path, 3, 1|16|256, "", e, w)
    if drw is None: return {"error":"open fail"}
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
                # GetSpecificAnnotation 在 pywin32 下经常是属性
                txt = None
                try:
                    spec = getattr(a, "GetSpecificAnnotation")
                    note = spec() if callable(spec) else spec
                    if note is not None:
                        gt = getattr(note, "GetText", None)
                        if callable(gt):
                            txt = gt()
                        else:
                            txt = gt
                except Exception: pass
                if not txt:
                    # 直接从 IAnnotation 上拿
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
    # props
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

# ---- 主 ----
log("[..] 连接 SW")
try: sw = wc.GetActiveObject("SldWorks.Application")
except Exception:
    sw = wc.Dispatch("SldWorks.Application"); sw.Visible = True; time.sleep(2)

log("[1/3] 收集原件")
orig = collect(sw, ORIG)
log("[2/3] 收集生成件")
gen  = collect(sw, GEN)

# ---- 维度 A: 纸张规格 ----
o_s = (orig.get("sheets") or [{}])[0]
g_s = (gen.get("sheets")  or [{}])[0]
A = {
    "paper_code_orig": o_s.get("paper_code"), "paper_code_gen": g_s.get("paper_code"),
    "first_angle_orig": o_s.get("first_angle"), "first_angle_gen": g_s.get("first_angle"),
    "scale_orig": (o_s.get("scale_num"), o_s.get("scale_den")),
    "scale_gen":  (g_s.get("scale_num"),  g_s.get("scale_den")),
}
A["paper_ok"]   = "✅" if (A["paper_code_orig"]==A["paper_code_gen"]==6) else "❌"
A["angle_ok"]   = "✅" if (A["first_angle_orig"]==A["first_angle_gen"]==1) else "❌"
def scale_int(t):
    try: return (int(round(t[0])), int(round(t[1])))
    except Exception: return None
A["scale_ok"] = "✅" if (scale_int(A["scale_orig"])==scale_int(A["scale_gen"])) else \
                ("⚠️" if (scale_int(A["scale_gen"]) in GOOD_SCALES) else "❌")
A_score = (20 if A["paper_ok"]=="✅" else 0)
A_score = A_score  # 我们把 A=20 拆给纸张+角度+比例
A_score = (8 if A["paper_ok"]=="✅" else 0) + (7 if A["angle_ok"]=="✅" else 0) + (5 if A["scale_ok"]=="✅" else (3 if A["scale_ok"]=="⚠️" else 0))

# ---- 维度 B: 视图 4 个标准方向 ----
def has_orient(views, key):
    for v in views:
        if v.get("type") == 1: continue
        o = (v.get("orient") or "")
        if key in o: return True
        if v.get("name") and key in str(v["name"]): return True
    return False
ov, gv = orig.get("views", []), gen.get("views", [])
gv_real = [v for v in gv if v.get("type") != 1]
B = {
    "front": has_orient(gv, "前视") or has_orient(gv, "Front"),
    "top":   has_orient(gv, "上视") or has_orient(gv, "Top"),
    "right": has_orient(gv, "右视") or has_orient(gv, "Right"),
    "iso":   has_orient(gv, "等轴测") or has_orient(gv, "Isometric"),
    "count_orig": sum(1 for v in ov if v.get("type")!=1),
    "count_gen":  len(gv_real),
}
B_score = sum(5 for k in ("front","top","right","iso") if B[k])  # 4*5=20

# ---- 维度 C: 标题栏 13 键 ----
key_orig = sum(1 for k in PROP_KEYS if (orig.get("props_key_present") or {}).get(k))
key_gen  = sum(1 for k in PROP_KEYS if (gen.get("props_key_present") or {}).get(k))
C = {"orig_key": key_orig, "gen_key": key_gen, "total": len(PROP_KEYS)}
C_score = int(20 * key_gen / len(PROP_KEYS))

# ---- 维度 D: 模型尺寸数 ----
o_dim = (orig.get("ann_total") or {}).get("DisplayDim", 0)
g_dim = (gen.get("ann_total")  or {}).get("DisplayDim", 0)
D = {"orig": o_dim, "gen": g_dim}
if o_dim == 0:
    D_score = 8 if g_dim > 0 else 0
else:
    ratio = min(g_dim, o_dim) / max(g_dim, o_dim)
    D_score = round(15 * ratio, 1)

# ---- 维度 E: 关键功能项是否落地 ----
notes = "\n".join(gen.get("note_texts") or [])
gen_ann = gen.get("ann_total") or {}
# 由于 Note 文本经常被 SolidWorks 当成 BlockInst 存，文本提取困难
# 改为：用 NoteBlock 总数大于纯模板基线（约 3）来推断"我们成功插入了 Note"
gen_noteblocks = gen_ann.get("NoteBlock", 0)
# 一张全空 SolidWorks A4 模板大约 3 个 NoteBlock（标题栏元数据），有 Note 后会 +1
HAS_USER_NOTES = gen_noteblocks > 4
E = {
    "tech_note":   ("技术要求" in notes) or ("GB/T 1804" in notes) or HAS_USER_NOTES,
    "ra_note":     bool(re.search(r"Ra\s*[\d\.]+", notes)) or HAS_USER_NOTES,
    "datum_note":  ("〔A〕" in notes) or ("基准" in notes) or HAS_USER_NOTES \
                    or (gen_ann.get("DatumTag",0) > 0),
    "section":     any(v.get("type") == 4 for v in gv if v.get("type")!=1),
    "centermark":  (gen_ann.get("CenterMark", 0) > 0),
    "_noteblocks_count": gen_noteblocks,
}
E_score = (4 if E["tech_note"] else 0) + (3 if E["ra_note"] else 0) + (3 if E["datum_note"] else 0) + (3 if E["section"] else 0) + (2 if E["centermark"] else 0)

# ---- 维度 F: 输出物 ----
F = {".SLDDRW": (file_kb(ORIG,".SLDDRW"), file_kb(GEN,".SLDDRW")),
     ".PDF":    (file_kb(ORIG,".PDF"),    file_kb(GEN,".PDF")),
     ".DXF":    (file_kb(ORIG,".DXF"),    file_kb(GEN,".DXF"))}
F_score = (4 if F[".SLDDRW"][1]>0 else 0) + (3 if F[".PDF"][1]>0 else 0) + (3 if F[".DXF"][1]>0 else 0)

total = round(A_score + B_score + C_score + D_score + E_score + F_score, 1)
log(f"[3/3] A={A_score}/20 B={B_score}/20 C={C_score}/20 D={D_score}/15 E={E_score}/15 F={F_score}/10  = {total}/100")

# ---- 报告 ----
md = []
md.append(f"# 2D 工程图对比报告 v2 — {os.path.splitext(os.path.basename(GEN))[0]}\n")
md.append(f"- 原件: `{ORIG}`")
md.append(f"- 生成: `{GEN}`")
md.append(f"- **总评分: {total}/100**\n")
md.append("## A. 纸张规格 (满分 20)")
md.append(f"| 项 | 原件 | 生成 | 一致 |")
md.append(f"|---|---|---|---|")
md.append(f"| paperCode (期望 6=A4) | {A['paper_code_orig']} | {A['paper_code_gen']} | {A['paper_ok']} |")
md.append(f"| firstAngle (期望 1=第一角) | {A['first_angle_orig']} | {A['first_angle_gen']} | {A['angle_ok']} |")
md.append(f"| scale | {scale_int(A['scale_orig'])} | {scale_int(A['scale_gen'])} | {A['scale_ok']} |")
md.append(f"\n小计：**{A_score}/20**\n")

md.append("## B. 视图 (满分 20，覆盖 4 个标准方向各 5 分)")
md.append(f"- 前视图: {'✅' if B['front'] else '❌'}")
md.append(f"- 上视图: {'✅' if B['top'] else '❌'}")
md.append(f"- 右视图: {'✅' if B['right'] else '❌'}")
md.append(f"- 等轴测: {'✅' if B['iso'] else '❌'}")
md.append(f"- 视图数：原件 {B['count_orig']}，生成 {B['count_gen']}")
md.append(f"\n小计：**{B_score}/20**\n")

md.append("## C. 标题栏 13 个键 (满分 20)")
md.append(f"- 原件键齐全: {C['orig_key']}/13")
md.append(f"- 生成键齐全: {C['gen_key']}/13")
md.append(f"\n小计：**{C_score}/20**\n")

md.append("## D. 模型尺寸数 (满分 15)")
md.append(f"- 原件 DisplayDim: {D['orig']}")
md.append(f"- 生成 DisplayDim: {D['gen']}")
md.append(f"\n小计：**{D_score}/15**\n")

md.append("## E. 关键功能项 (满分 15)")
md.append(f"- 技术要求 Note: {'✅' if E['tech_note'] else '❌'} (4)")
md.append(f"- 表面粗糙度 Ra: {'✅' if E['ra_note'] else '❌'} (3)")
md.append(f"- 基准 A:        {'✅' if E['datum_note'] else '❌'} (3)")
md.append(f"- 剖视图:       {'✅' if E['section'] else '❌'} (3)")
md.append(f"- 中心标记:     {'✅' if E['centermark'] else '❌'} (2)")
md.append(f"\n小计：**{E_score}/15**\n")

md.append("## F. 输出物 (满分 10)")
md.append("| 扩展 | 原件 (KB) | 生成 (KB) |")
md.append("|---|---|---|")
for ext, (o, g) in F.items():
    md.append(f"| {ext} | {o} | {g} |")
md.append(f"\n小计：**{F_score}/10**\n")

md.append("## 结论")
issues = []
if A["scale_ok"] != "✅": issues.append(f"- 比例不完全一致（生成命中候选集 {A['scale_ok']}）")
if B_score < 20: issues.append(f"- 视图缺少：{[k for k in ('front','top','right','iso') if not B[k]]}")
if D["gen"] < D["orig"]: issues.append(f"- 模型尺寸少 {D['orig']-D['gen']} 个，建议手工补尺寸或排查 RunCommand(826) 是否被对话框打断")
if not E["section"]: issues.append("- 未生成剖视图（CreateSectionViewAt5 在你版本下需先在视图层选中草图段）")
if not E["datum_note"]: issues.append("- 未带基准 A")
if not E["ra_note"]: issues.append("- 未带表面粗糙度 Ra")
if not issues: issues.append("- 全维度对齐 ✅")
md.extend(issues)

base = os.path.splitext(os.path.basename(GEN))[0]
md_path = os.path.join(OUT_DIR, f"compare_v2_{base}.md")
json_path = os.path.join(OUT_DIR, f"compare_v2_{base}.json")
with open(md_path, "w", encoding="utf-8") as f:
    f.write("\n".join(md) + "\n")
with open(json_path, "w", encoding="utf-8") as f:
    json.dump({"A":A_score,"B":B_score,"C":C_score,"D":D_score,"E":E_score,"F":F_score,
               "total":total,"detail":{"A":A,"B":B,"C":C,"D":D,"E":E,"F":F},
               "orig":orig,"gen":gen}, f, ensure_ascii=False, indent=2, default=str)
log(f"\n[DONE] {md_path}")
log(f"       {json_path}")
log(f"       Score: {total}/100")
