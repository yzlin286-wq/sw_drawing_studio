"""
drw_compare.py
对比"自动生成的 SLDDRW"与"对标原件 SLDDRW"的准确性 / 完整度。

对比维度：
A. 纸张规格：paperCode / firstAngle / scale
B. 视图：数量、类型分布、方向分布
C. 标题栏自定义属性：13 项是否齐全 + 值是否一致
D. 标注体量：尺寸/中心标记/Note/表面粗糙度/形位公差/剖面线计数
E. 输出物大小：SLDDRW / PDF / DXF 文件大小（KB）

输出：
- compare_<base>.json  (结构化数据)
- compare_<base>.md    (人类可读报告，含 ✅/❌ 表)
"""
import os, sys, json, time, traceback
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
os.makedirs(OUT_DIR, exist_ok=True)

PROP_KEYS = ["SWFormatSize","机型","品名","图号","类别","数量",
             "材质","表面处理","设计","日期",
             "UNIT_OF_MEASURE","Material","重量"]

ANN_TYPE_NAME = {
    1:"DisplayDim",2:"Note",3:"GTOL",4:"DatumTag",5:"Balloon",
    6:"NoteBlock",7:"View",8:"WeldSym",9:"SurfFinish",
    10:"DimDot",13:"CenterMark",14:"BlockInst",15:"AreaHatch",
    16:"DimLine",17:"DatumTarget",
}

def call(o, n, *a):
    if o is None: return None
    try: m = getattr(o, n)
    except Exception: return None
    try:
        if callable(m): return m(*a)
    except Exception: pass
    return m

def open_drw(sw, path):
    e = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    w = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    drw = sw.OpenDoc6(path, 3, 1|16|256, "", e, w)
    return drw, e.value, w.value

def collect(sw, path):
    """收集一张 SLDDRW 的对比信息。"""
    if not os.path.exists(path):
        return {"error": f"file not found: {path}"}
    log(f"  打开 {os.path.basename(path)}")
    drw, e, w = open_drw(sw, path)
    if drw is None:
        return {"error": f"open failed errors={e}"}

    info = {"file": path, "title": call(drw, "GetTitle")}

    # Sheet
    sheets = []
    sn = call(drw, "GetSheetNames") or []
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
            "width_m": prop2[5] if len(prop2)>5 else None,
            "height_m": prop2[6] if len(prop2)>6 else None,
        })
    info["sheets"] = sheets

    # 视图与标注
    views, ann_total = [], Counter()
    v = call(drw, "GetFirstView")
    while v is not None:
        types = Counter()
        a = call(v, "GetFirstAnnotation3")
        cnt = 0
        while a is not None:
            cnt += 1
            t = call(a, "GetType")
            tn = ANN_TYPE_NAME.get(t, str(t))
            types[tn] += 1
            ann_total[tn] += 1
            a = call(a, "GetNext3")
        views.append({
            "name": call(v, "GetName2"),
            "type": call(v, "Type"),
            "orient": call(v, "GetOrientationName"),
            "scale": list(call(v, "ScaleRatio") or []),
            "ann_total": cnt,
            "ann_types": dict(types),
        })
        v = call(v, "GetNextView")
    info["views"] = views
    info["ann_total_by_type"] = dict(ann_total)
    info["ann_total"] = sum(ann_total.values())

    # 自定义属性（13 个键名是否存在 + 值是否一致；同时收集所有 manager 的并集）
    props_value = {}
    props_key_present = {}
    try:
        cpm_list = []
        try: cpm_list.append(("", drw.Extension.CustomPropertyManager("")))
        except Exception: pass
        try:
            cfg_names = call(drw, "GetConfigurationNames") or []
            for cn in list(cfg_names):
                try: cpm_list.append((cn, drw.Extension.CustomPropertyManager(cn)))
                except Exception: pass
        except Exception: pass

        all_keys_present = set()
        best_value_filled = -1
        best_value = {k: "" for k in PROP_KEYS}
        info["props_per_manager"] = []
        for cfg_name, cpm in cpm_list:
            try:
                names = list(call(cpm, "GetNames") or [])
            except Exception:
                names = []
            cur_value = {}
            for k in PROP_KEYS:
                if k in names:
                    all_keys_present.add(k)
                try:
                    rv, val, resolved, was = cpm.Get5(k, False)
                    cur_value[k] = (resolved or val or "")
                except Exception:
                    cur_value[k] = ""
            info["props_per_manager"].append({"cfg": cfg_name or "(doc)", "key_count": len(names),
                                              "filled": sum(1 for v in cur_value.values() if v)})
            filled = sum(1 for v in cur_value.values() if v)
            if filled > best_value_filled:
                best_value_filled = filled
                best_value = cur_value
                info["props_source"] = cfg_name or "(doc)"
        for k in PROP_KEYS:
            props_key_present[k] = (k in all_keys_present)
        props_value = best_value
    except Exception as exc:
        info["props_err"] = str(exc)
    info["props"] = props_value
    info["props_key_present"] = props_key_present

    try: sw.CloseDoc(call(drw, "GetTitle"))
    except Exception: pass
    return info

def file_size(p, ext):
    f = os.path.splitext(p)[0] + ext
    return os.path.getsize(f) if os.path.exists(f) else 0

# ---------------- 主流程 ----------------
log("[..] 连接 SW")
try: sw = wc.GetActiveObject("SldWorks.Application")
except Exception:
    sw = wc.Dispatch("SldWorks.Application"); sw.Visible = True; time.sleep(2)

log("[1/3] 收集对标原件信息")
orig_info = collect(sw, ORIG)
log("[2/3] 收集生成图信息")
gen_info  = collect(sw, GEN)

# ---------------- 对比 ----------------
def cmp_value(a, b, eq=lambda x,y: x==y):
    return "✅" if (a is not None and b is not None and eq(a,b)) else "❌"

def cmp_pct(a, b):
    if a in (0, None) or b in (0, None): return 0.0
    return round(min(a, b) / max(a, b), 3)

report = {
    "original": ORIG, "generated": GEN,
    "orig": orig_info, "gen": gen_info,
    "compare": {},
}

# A. 纸张规格
o_s = (orig_info.get("sheets") or [{}])[0]
g_s = (gen_info.get("sheets") or [{}])[0]
report["compare"]["sheet"] = {
    "paper_code":  {"orig": o_s.get("paper_code"),  "gen": g_s.get("paper_code"),
                    "ok": cmp_value(o_s.get("paper_code"),  g_s.get("paper_code"))},
    "first_angle": {"orig": o_s.get("first_angle"), "gen": g_s.get("first_angle"),
                    "ok": cmp_value(o_s.get("first_angle"), g_s.get("first_angle"))},
    "scale": {"orig": f"{o_s.get('scale_num')}:{o_s.get('scale_den')}",
              "gen":  f"{g_s.get('scale_num')}:{g_s.get('scale_den')}",
              "ok": cmp_value(
                  (o_s.get("scale_num"), o_s.get("scale_den")),
                  (g_s.get("scale_num"), g_s.get("scale_den")),
              )},
    "size": {"orig_mm": [int((o_s.get("width_m") or 0)*1000), int((o_s.get("height_m") or 0)*1000)],
             "gen_mm":  [int((g_s.get("width_m") or 0)*1000), int((g_s.get("height_m") or 0)*1000)]},
}

# B. 视图
ov = orig_info.get("views", [])
gv = gen_info.get("views", [])
ov_real = [x for x in ov if x.get("type") != 1]   # 排除图纸本身
gv_real = [x for x in gv if x.get("type") != 1]
report["compare"]["views"] = {
    "count_orig": len(ov_real), "count_gen": len(gv_real),
    "count_match": cmp_value(len(ov_real), len(gv_real)),
    "type_dist_orig": dict(Counter(x.get("type") for x in ov_real)),
    "type_dist_gen":  dict(Counter(x.get("type") for x in gv_real)),
    "orient_orig": dict(Counter((x.get("orient") or "") for x in ov_real)),
    "orient_gen":  dict(Counter((x.get("orient") or "") for x in gv_real)),
}

# C. 自定义属性
op = orig_info.get("props", {}) or {}
gp = gen_info.get("props", {}) or {}
op_keys = orig_info.get("props_key_present", {}) or {}
gp_keys = gen_info.get("props_key_present", {}) or {}
prop_table = []
for k in PROP_KEYS:
    o, g = op.get(k, ""), gp.get(k, "")
    same = (str(o).strip() == str(g).strip()) if (o and g) else (False if (o or g) else True)
    prop_table.append({
        "key": k, "orig": o, "gen": g,
        "orig_key_present": bool(op_keys.get(k, False)),
        "gen_key_present":  bool(gp_keys.get(k, False)),
        "orig_has_value": bool(o), "gen_has_value": bool(g),
        "same_value": same,
    })
present_orig = sum(1 for r in prop_table if r["orig_has_value"])
present_gen  = sum(1 for r in prop_table if r["gen_has_value"])
key_orig = sum(1 for r in prop_table if r["orig_key_present"])
key_gen  = sum(1 for r in prop_table if r["gen_key_present"])
match_value = sum(1 for r in prop_table if r["same_value"] and r["orig_has_value"])
report["compare"]["properties"] = {
    "total": len(PROP_KEYS),
    "key_orig_present": key_orig,
    "key_gen_present":  key_gen,
    "value_orig_present": present_orig,
    "value_gen_present":  present_gen,
    "value_match": match_value,
    "table": prop_table,
}

# D. 标注体量
o_total = orig_info.get("ann_total_by_type", {}) or {}
g_total = gen_info.get("ann_total_by_type", {}) or {}
all_keys = sorted(set(o_total) | set(g_total))
ann_table = []
for k in all_keys:
    o = o_total.get(k, 0); g = g_total.get(k, 0)
    ann_table.append({"type": k, "orig": o, "gen": g,
                      "ratio_gen_over_orig": round(g/o, 3) if o else None})
report["compare"]["annotations"] = {
    "orig_total": sum(o_total.values()),
    "gen_total": sum(g_total.values()),
    "table": ann_table,
}

# E. 输出物大小
def kb(bytes_): return round(bytes_/1024, 1)
sizes = {}
for ext in (".SLDDRW", ".PDF", ".DXF"):
    sizes[ext] = {
        "orig_kb": kb(file_size(ORIG, ext)),
        "gen_kb":  kb(file_size(GEN, ext)),
    }
report["compare"]["files"] = sizes

# ---------------- 评分 ----------------
score = 0; max_score = 0
def add_score(actual, weight, max_w):
    global score, max_score
    score += actual; max_score += max_w
add_score(weight=20, max_w=20, actual=20 if report["compare"]["sheet"]["paper_code"]["ok"]=="✅" else 0)
add_score(weight=10, max_w=10, actual=10 if report["compare"]["sheet"]["first_angle"]["ok"]=="✅" else 0)
add_score(weight=5,  max_w=5,  actual=5  if report["compare"]["sheet"]["scale"]["ok"]=="✅" else 2)
add_score(weight=15, max_w=15, actual=15 if report["compare"]["views"]["count_match"]=="✅" else max(0, 15 - abs(len(ov_real)-len(gv_real))*3))
# 关键改动：对"键名齐全度"打分（值的填写度作为参考分）
add_score(weight=20, max_w=20, actual=int(20 * key_gen / max(1, len(PROP_KEYS))))
add_score(weight=10, max_w=10, actual=int(10 * (match_value + (key_gen - present_orig if key_gen >= present_orig else 0)) / max(1, len(PROP_KEYS))))
o_ann = report["compare"]["annotations"]["orig_total"] or 1
g_ann = report["compare"]["annotations"]["gen_total"]
add_score(weight=20, max_w=20, actual=int(20 * min(g_ann, o_ann) / o_ann))
report["compare"]["score"] = {"score": score, "max": max_score, "pct": round(score/max_score*100, 1)}

# ---------------- 写报告 ----------------
base = os.path.splitext(os.path.basename(GEN))[0]
json_path = os.path.join(OUT_DIR, f"compare_{base}.json")
md_path   = os.path.join(OUT_DIR, f"compare_{base}.md")
with open(json_path, "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2, default=str)

# Markdown
md = []
md.append(f"# 2D 工程图对比报告 — {base}\n")
md.append(f"- 对标原件: `{ORIG}`")
md.append(f"- 自动生成: `{GEN}`")
md.append(f"- 总评分: **{score}/{max_score} ({report['compare']['score']['pct']}%)**\n")

md.append("## A. 纸张规格")
md.append("| 项 | 对标原件 | 自动生成 | 一致 |")
md.append("|---|---|---|---|")
sh = report["compare"]["sheet"]
md.append(f"| paperCode | {sh['paper_code']['orig']} | {sh['paper_code']['gen']} | {sh['paper_code']['ok']} |")
md.append(f"| firstAngle | {sh['first_angle']['orig']} | {sh['first_angle']['gen']} | {sh['first_angle']['ok']} |")
md.append(f"| scale | {sh['scale']['orig']} | {sh['scale']['gen']} | {sh['scale']['ok']} |")
md.append(f"| 尺寸(mm) | {sh['size']['orig_mm']} | {sh['size']['gen_mm']} | — |\n")

md.append("## B. 视图")
vw = report["compare"]["views"]
md.append(f"- 视图数量：原件 {vw['count_orig']}，生成 {vw['count_gen']}  {vw['count_match']}")
md.append(f"- 类型分布：原件 {vw['type_dist_orig']}，生成 {vw['type_dist_gen']}")
md.append(f"- 方向分布：原件 {vw['orient_orig']}，生成 {vw['orient_gen']}\n")

md.append("## C. 标题栏自定义属性")
pp = report["compare"]["properties"]
md.append(f"- **键名齐全度**：原件 {pp['key_orig_present']}/{pp['total']}，生成 {pp['key_gen_present']}/{pp['total']}")
md.append(f"- **值填写度**：原件 {pp['value_orig_present']}/{pp['total']}（多为空待人工填写），生成 {pp['value_gen_present']}/{pp['total']}")
md.append(f"- 值一致项 {pp['value_match']}\n")
md.append("| 属性 | 原件键 | 原件值 | 生成键 | 生成值 |")
md.append("|---|---|---|---|---|")
for r in pp["table"]:
    o = (r["orig"] or "").replace("|","\\|")
    g = (r["gen"] or "").replace("|","\\|")
    ok_o = "✅" if r["orig_key_present"] else "❌"
    ok_g = "✅" if r["gen_key_present"]  else "❌"
    md.append(f"| {r['key']} | {ok_o} | {o or '(空)'} | {ok_g} | {g or '(空)'} |")
md.append("")

md.append("## D. 标注体量")
an = report["compare"]["annotations"]
md.append(f"- 总标注：原件 {an['orig_total']}，生成 {an['gen_total']}（占比 {round(an['gen_total']/max(1,an['orig_total'])*100,1)}%）")
md.append("\n| 类型 | 原件 | 生成 | 生成/原件 |")
md.append("|---|---|---|---|")
for r in an["table"]:
    md.append(f"| {r['type']} | {r['orig']} | {r['gen']} | {r['ratio_gen_over_orig']} |")
md.append("")

md.append("## E. 输出物大小")
md.append("| 扩展 | 对标 (KB) | 生成 (KB) |")
md.append("|---|---|---|")
for ext, s in report["compare"]["files"].items():
    md.append(f"| {ext} | {s['orig_kb']} | {s['gen_kb']} |")
md.append("")

# 结论
md.append("## 结论")
issues = []
if pp["key_gen_present"] < pp["key_orig_present"]:
    issues.append(f"- 标题栏键齐全度：生成 {pp['key_gen_present']}/{pp['key_orig_present']}，需补齐字段")
if pp["value_gen_present"] < pp["value_orig_present"]:
    issues.append(f"- 标题栏值填写度：生成 {pp['value_gen_present']}/{pp['value_orig_present']}（注意：原件大多也为空，由人工填写）")
if vw["count_gen"] != vw["count_orig"]:
    issues.append(f"- 视图数量不一致：{vw['count_gen']} vs {vw['count_orig']}（原件常含剖视/局部放大）")
if an["gen_total"] < an["orig_total"]:
    issues.append(f"- 标注体量：生成 {an['gen_total']} < 原件 {an['orig_total']}（剖面线/中心标记/注释丰度差异）")
if not issues:
    issues.append("- 全部维度对齐 ✅")
md.extend(issues)

with open(md_path, "w", encoding="utf-8") as f:
    f.write("\n".join(md) + "\n")

log(f"\n[DONE]")
log(f"  JSON: {json_path}")
log(f"  MD  : {md_path}")
log(f"  Score: {score}/{max_score} ({report['compare']['score']['pct']}%)")
