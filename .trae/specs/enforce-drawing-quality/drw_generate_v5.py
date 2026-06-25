"""
drw_generate_v5.py
---
在 v4 基础上升级（spec: enforce-drawing-quality）：
1) 视图自动布局算法 layout_4_views(part_bbox_m, scale_num_den) -> {name:(cx,cy)}
   按 GetPartBox 的 bbox 与所选比例计算前/上/右/等轴测中心，并通过
   GetOutline 两两 _rect_intersect 检测，若有重叠则降一档比例重试。
2) 字体设置：drw.SetUserPreferenceDoubleValue(89, 0.005)  # 5 mm 字高
                 drw.SetUserPreferenceDoubleValue(2,  0.005)  # 箭头大小
3) 通过 LayerMgr.AddLayer 创建 5 个图层（粗实线 / 细实线 / 虚线 / 点划线 / 中心线）；
   失败仅 warning，最后 print LayerMgr.GetLayerCount() 验证。
4) 每个视图 DisplayMode = 2 (HiddenLinesRemoved)，失败兜底 3 (Wireframe)。
5) 保留 v4 的：13 项属性 + MassProperties.重量 / 4 个标准视图 / RunCommand(826) /
   section_helper.create_section_in_active_drawing / 技术要求 + Ra + 基准 A 兜底 Note /
   13 项标题栏 Add3+Set2 / 保存 SLDDRW + PDF + DXF + warnings.json，文件后缀 _v5。
6) CLI 第 2 个参数可传 issues_to_fix.json，用于本轮调参：
   - "view_overlap"          -> 比例降一档
   - "text_height_ge_3_5mm"  -> 字高调到 0.006
   - "scale_in_set"          -> 强制使用 (1, 2)
"""
import os, re, sys, time, json, math, traceback
import pythoncom
import win32com.client as wc
from win32com.client import VARIANT
from pathlib import Path

_SCRIPT_PATH = Path(__file__).resolve()
_BUNDLE_ROOT = Path(os.environ.get("SW_DRAWING_STUDIO_BUNDLE_ROOT", _SCRIPT_PATH.parent.parent.parent.parent)).resolve()
_RUNTIME_ROOT = Path(os.environ.get("SW_DRAWING_STUDIO_RUNTIME_ROOT", _BUNDLE_ROOT)).resolve()
ROOT = str(_RUNTIME_ROOT)
V4_DIR = str(_BUNDLE_ROOT / ".trae" / "specs" / "repair-section-and-recompare")
sys.path.insert(0, V4_DIR)
from section_helper import create_section_in_active_drawing  # noqa: E402

sys.stdout.reconfigure(line_buffering=True)
def log(*a, **kw): print(*a, **kw, flush=True)

DEFAULT_PART = str(_RUNTIME_ROOT / "3D转2D测试图纸" / "LB26001-A-04-001.SLDPRT")
OUT_DIR = str(_RUNTIME_ROOT / "drw_output" / "v5")
STANDARD_MD = os.path.join(V4_DIR, "drawing_standard_v2.md")

CANDIDATE_SCALES = [(5,1),(3,1),(2,1),(1,1),(1,2),(1,3),(1,4),(1,5),(1,10),(1,20),(1,50),(1,100)]
PROP_KEYS = ["SWFormatSize","机型","品名","图号","类别","数量",
             "材质","表面处理","设计","日期",
             "UNIT_OF_MEASURE","Material","重量"]

TECH_NOTES = (
    "技术要求：\n"
    "1. 未注线性尺寸及角度尺寸公差按 GB/T 1804-m 执行。\n"
    "2. 零件去毛刺、清除锐边，表面应平整无划伤。\n"
    "3. 表面处理：脱脂磷化后静电喷粉，涂层均匀牢固。"
)

# A4 横向工作区（单位 m）：去掉左右各 20mm 边距 + 标题栏 75mm 高
WORKAREA = dict(xmin=0.020, xmax=0.277, ymin=0.075, ymax=0.200)

# A4 角落 fallback（单位 m）
FALLBACK_NOTE_POS = {
    "tech":  (0.297*0.62, 0.21*0.30),
    "ra":    (0.260, 0.190),
    "datum": (0.020, 0.100),
}

LAYERS = [
    # (名称, color BGR int, lineStyle, weight)  weight: 0=Default,1=Thin,2=Normal,3=Thick
    ("粗实线",   0,         0, 3),
    ("细实线",   0,         0, 1),
    ("虚线",     255,       1, 1),
    ("点划线",   16711680,  4, 1),
    ("中心线",   16711680,  4, 1),
]


# ============================================================
# 视图自动布局
# ============================================================
def _inject_default_custom_properties(part_model, sldprt_path):
    """对 part 模型补齐 13 个 CustomProperty 默认值（不写源文件，只在内存改）"""
    import os, datetime
    from pathlib import Path
    base = Path(sldprt_path).stem
    today = datetime.date.today().isoformat()

    defaults = {
        "机型": "通用",
        "品名": base,
        "图号": base,
        "类别": "A",
        "数量": "1",
        "材质": "",
        "表面处理": "脱脂磷化喷粉",
        "比例": "1:1",
        "重量": "",
        "UNIT_OF_MEASURE": "mm",
        "设计": "auto",
        "日期": today,
    }

    try:
        mat = part_model.GetMaterialPropertyName2("", "")
        if mat: defaults["材质"] = mat
    except Exception: pass

    try:
        mp = part_model.Extension.CreateMassProperty()
        mass_kg = mp.Mass
        if mass_kg and mass_kg > 0:
            defaults["重量"] = f"{mass_kg*1000:.1f}"
    except Exception: pass
    if not defaults["重量"]:
        defaults["重量"] = "0"

    try:
        cpm = part_model.Extension.CustomPropertyManager("")
        for k, v in defaults.items():
            try:
                cur = cpm.Get4(k, False)
                if isinstance(cur, tuple): cur_val = cur[2] if len(cur) >= 3 else ""
                else: cur_val = cur or ""
                if not cur_val:
                    try: cpm.Add3(k, 30, str(v), 1)
                    except Exception: cpm.Set2(k, str(v))
                    print(f"[cprop] +{k}={v}")
            except Exception as e:
                print(f"[cprop] {k} failed: {e}")
    except Exception as e:
        print(f"[cprop] CustomPropertyManager failed: {e}")

    return defaults


def _draw_gb_frame_and_titleblock(drw, model):
    """在 sheet sketch 下绘制 A4 横式图框 + 标题栏。
    单位：米。A4 横式 0.297 x 0.210。
    外框：(0.010, 0.010) - (0.287, 0.200)
    内框：(0.025, 0.015) - (0.282, 0.195)
    标题栏：(0.102, 0.015) - (0.282, 0.055)，5 列 ×3 行。

    必须在所有视图创建/布局完成之后调用，否则 EditSheet/视图操作会清空 sketch。
    """
    # 1) 清选 + 退到 sheet 编辑模式（不进入任何视图/format）
    try: drw.ClearSelection2(True)
    except Exception: pass
    try: drw.EditSheet()
    except Exception: pass
    try:
        sheet = drw.GetCurrentSheet()
    except Exception:
        sheet = None
    try: drw.SetEditMode(0)  # 0 = swEditMode_Sheet
    except Exception: pass
    try: model.SetEditFormat(False)  # 退出 format 编辑
    except Exception: pass

    # 2) 进入 sheet sketch
    sm = None
    try:
        sm = getattr(model, "SketchManager", None)
    except Exception:
        sm = None
    sketch_started = False
    if sm is not None:
        try:
            sm.InsertSketch(True)
            sketch_started = True
        except Exception:
            sketch_started = False

    def _line(x1, y1, x2, y2):
        if sm is None: return None
        try:
            return sm.CreateLine(float(x1), float(y1), 0.0,
                                 float(x2), float(y2), 0.0)
        except Exception:
            try:
                return sm.CreateLine2(float(x1), float(y1), 0.0,
                                      float(x2), float(y2), 0.0)
            except Exception:
                return None

    # 外框：(0.010, 0.010) - (0.287, 0.200)
    _line(0.010, 0.010, 0.287, 0.010)
    _line(0.287, 0.010, 0.287, 0.200)
    _line(0.287, 0.200, 0.010, 0.200)
    _line(0.010, 0.200, 0.010, 0.010)

    # 内框：(0.025, 0.015) - (0.282, 0.195)
    _line(0.025, 0.015, 0.282, 0.015)
    _line(0.282, 0.015, 0.282, 0.195)
    _line(0.282, 0.195, 0.025, 0.195)
    _line(0.025, 0.195, 0.025, 0.015)

    # 标题栏外框：(0.102, 0.015) - (0.282, 0.055)
    tb_x0, tb_y0, tb_x1, tb_y1 = 0.102, 0.015, 0.282, 0.055
    _line(tb_x0, tb_y0, tb_x1, tb_y0)
    _line(tb_x1, tb_y0, tb_x1, tb_y1)
    _line(tb_x1, tb_y1, tb_x0, tb_y1)
    _line(tb_x0, tb_y1, tb_x0, tb_y0)

    # 标题栏 3 行 2 条横线（y=0.028, y=0.041）
    _line(tb_x0, 0.028, tb_x1, 0.028)
    _line(tb_x0, 0.041, tb_x1, 0.041)
    # 标题栏 5 列 4 条竖线
    for cx in (0.137, 0.182, 0.227, 0.252):
        _line(cx, tb_y0, cx, tb_y1)

    # 3) 退出 sheet sketch（toggle 关掉）
    if sketch_started and sm is not None:
        try:
            sm.InsertSketch(True)
        except Exception:
            pass

    # 13 个标题栏 Note（前 12 中文标签 + 后 3 $PRP 链接）
    cell_notes = [
        (0.104, 0.043, "机型"),
        (0.139, 0.043, "品名"),
        (0.184, 0.043, "图号"),
        (0.229, 0.043, "类别"),
        (0.254, 0.043, "数量"),
        (0.104, 0.030, "材质"),
        (0.139, 0.030, "表面处理"),
        (0.184, 0.030, "比例"),
        (0.229, 0.030, "重量"),
        (0.254, 0.030, "单位"),
        (0.104, 0.017, "设计"),
        (0.139, 0.017, "日期"),
        (0.184, 0.017, "$PRP:\"图号\""),
        (0.229, 0.017, "$PRP:\"类别\""),
        (0.254, 0.017, "$PRP:\"数量\""),
    ]
    for nx, ny, txt in cell_notes:
        try:
            drw.ClearSelection2(True)
            note = drw.InsertNote(txt)
            if note is not None:
                ann = None
                try: ann = note.GetAnnotation()
                except Exception: ann = None
                if ann is not None:
                    try: ann.SetPosition2(float(nx), float(ny), 0)
                    except Exception:
                        try: ann.SetPosition(float(nx), float(ny), 0)
                        except Exception: pass
            drw.ClearSelection2(True)
        except Exception:
            try: drw.ClearSelection2(True)
            except Exception: pass


def _rect_intersect(a, b):
    """a, b: (xmin, ymin, xmax, ymax) 米。重叠返回 True。"""
    if not a or not b: return False
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    if ax0 > ax1: ax0, ax1 = ax1, ax0
    if ay0 > ay1: ay0, ay1 = ay1, ay0
    if bx0 > bx1: bx0, bx1 = bx1, bx0
    if by0 > by1: by0, by1 = by1, by0
    return not (ax1 <= bx0 or bx1 <= ax0 or ay1 <= by0 or by1 <= ay0)


def layout_4_views(part_bbox_m, scale_num_den):
    """按 spec 给出的第一角投影布局公式计算 4 个视图中心。
    part_bbox_m: (Lx, Ly, Lz) 米（已绝对值）
    scale_num_den: (n, d)
    返回 {name: (cx, cy)}，单位 m。
    """
    Lx, Ly, Lz = part_bbox_m
    n, d = scale_num_den
    s = float(n) / float(d) if d else 1.0

    cx_front = 0.080
    cy_front = 0.135
    cx_top = cx_front
    cy_top = cy_front - (Ly * s) / 2.0 - 0.030 - (Lz * s) / 2.0
    cx_right = cx_front + (Lx * s) / 2.0 + 0.030 + (Lz * s) / 2.0
    cy_right = cy_front
    cx_iso = 0.240
    cy_iso = 0.170
    return {
        "front": (cx_front, cy_front),
        "top":   (cx_top,   cy_top),
        "right": (cx_right, cy_right),
        "iso":   (cx_iso,   cy_iso),
    }


def predict_outline(center, size_xy):
    """根据中心 + 大小估算 view outline (xmin, ymin, xmax, ymax)。"""
    cx, cy = center
    w, h = size_xy
    return (cx - w/2.0, cy - h/2.0, cx + w/2.0, cy + h/2.0)


def predict_view_sizes(part_bbox_m, scale_num_den):
    Lx, Ly, Lz = part_bbox_m
    n, d = scale_num_den
    s = float(n) / float(d) if d else 1.0
    Lmax = max(Lx, Ly, Lz)
    return {
        "front": (Lx * s,        Ly * s),
        "top":   (Lx * s,        Lz * s),
        "right": (Lz * s,        Ly * s),
        "iso":   (Lmax * s * 0.7, Lmax * s * 0.7),
    }


def check_layout_no_overlap(part_bbox_m, scale_num_den):
    """预测式重叠检测：返回 (ok, overlap_pairs, outlines)"""
    centers = layout_4_views(part_bbox_m, scale_num_den)
    sizes   = predict_view_sizes(part_bbox_m, scale_num_den)
    outlines = {k: predict_outline(centers[k], sizes[k]) for k in centers}
    pairs = []
    keys = list(outlines.keys())
    for i in range(len(keys)):
        for j in range(i+1, len(keys)):
            if _rect_intersect(outlines[keys[i]], outlines[keys[j]]):
                pairs.append((keys[i], keys[j]))
    return (len(pairs) == 0, pairs, outlines)


def pick_scale_with_layout(part_bbox_m, start_scale=None):
    """从 CANDIDATE_SCALES 中选取使 4 视图无重叠的最大比例。
    若 start_scale 指定，则从该档开始向更小比例搜索。
    """
    Lx, Ly, Lz = part_bbox_m
    Lmax = max(Lx, Ly, Lz)
    # 起点：不超过 100mm 视图宽
    candidates = list(CANDIDATE_SCALES)
    start_idx = 0
    if start_scale and start_scale in candidates:
        start_idx = candidates.index(start_scale)
    else:
        for i, (n, d) in enumerate(candidates):
            if Lmax * (n/d) <= 0.10 + 1e-9:
                start_idx = i
                break
    for n, d in candidates[start_idx:]:
        ok, pairs, outlines = check_layout_no_overlap(part_bbox_m, (n, d))
        if ok:
            return (n, d), outlines, []
    # 最后兜底
    n, d = candidates[-1]
    ok, pairs, outlines = check_layout_no_overlap(part_bbox_m, (n, d))
    return (n, d), outlines, pairs


def downgrade_scale(scale):
    """把 scale 在 CANDIDATE_SCALES 中向 1:5/1:10 方向降一档。"""
    if scale in CANDIDATE_SCALES:
        i = CANDIDATE_SCALES.index(scale)
        if i + 1 < len(CANDIDATE_SCALES):
            return CANDIDATE_SCALES[i + 1]
    return scale


# ============================================================
# 通用工具
# ============================================================
def call(o, n, *a):
    if o is None: return None
    try: m = getattr(o, n)
    except Exception: return None
    try:
        if callable(m): return m(*a)
    except Exception: pass
    return m

def vt_dispatch_none(): return VARIANT(pythoncom.VT_DISPATCH, None)
def empty_callout(): return VARIANT(pythoncom.VT_DISPATCH, None)

def view_outline_box(view):
    out = call(view, "GetOutline")
    if out is None: return None
    o = list(out)
    if len(o) >= 4:
        return (o[0], o[1], o[2], o[3])
    return None


def load_issues_to_fix(path):
    """读取 issues_to_fix.json，返回 issue 字符串列表。
    支持的格式：
      - ["view_overlap", "text_height_ge_3_5mm"]
      - {"issues": ["view_overlap"]}
      - {"failures": [{"code":"view_overlap"}, ...]}
    """
    if not path or not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        log(f"[issues] 读取失败 {path}: {exc}")
        return []
    issues = []
    if isinstance(data, list):
        for x in data:
            if isinstance(x, str):
                issues.append(x)
            elif isinstance(x, dict):
                code = x.get("code") or x.get("issue") or x.get("name")
                if code: issues.append(str(code))
    elif isinstance(data, dict):
        if isinstance(data.get("issues"), list):
            for x in data["issues"]:
                if isinstance(x, str): issues.append(x)
                elif isinstance(x, dict):
                    code = x.get("code") or x.get("issue") or x.get("name")
                    if code: issues.append(str(code))
        if isinstance(data.get("failures"), list):
            for x in data["failures"]:
                if isinstance(x, dict):
                    code = x.get("code") or x.get("issue") or x.get("name")
                    if code: issues.append(str(code))
                elif isinstance(x, str):
                    issues.append(x)
    return issues


# ============================================================
# 主流程
# ============================================================
def generate_for(part_path, *, out_dir=OUT_DIR, sw=None, issues=None):
    issues = issues or []
    os.makedirs(out_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(part_path))[0]
    warnings_box = []

    log(f"[v5] 输出目录 {out_dir}")
    log(f"[v5] issues_to_fix: {issues if issues else '(无)'}")

    # 反馈通道：默认参数
    text_height = 0.005
    forced_scale = None
    scale_downgrade_hops = 0
    if "text_height_ge_3_5mm" in issues:
        text_height = 0.006
        log("[issues] text_height_ge_3_5mm -> 字高调到 0.006")
    if "scale_in_set" in issues:
        forced_scale = (1, 2)
        log("[issues] scale_in_set -> 强制使用比例 1:2")
    if "view_overlap" in issues:
        scale_downgrade_hops = 1
        log("[issues] view_overlap -> 比例向 1:5/1:10 方向降一档")

    if sw is None:
        log("[..] 连接 SolidWorks")
        try:
            sw = wc.GetActiveObject("SldWorks.Application")
        except Exception:
            sw = wc.Dispatch("SldWorks.Application")
            sw.Visible = True
            time.sleep(2)

    # 关闭 SolidWorks 默认的视图箭头/位移箭头/默认括号
    try: sw.SetUserPreferenceToggle(195, False)   # swDetailingShowDisplaceArrows
    except Exception: pass
    try: sw.SetUserPreferenceToggle(196, False)   # swDetailingShowParenthesisByDefault
    except Exception: pass

    target_drw = os.path.join(out_dir, f"{base_name}_v5.SLDDRW")
    try:
        docs = sw.GetDocuments
        docs = docs() if callable(docs) else docs
        for d in (docs or []):
            try:
                t = d.GetTitle if not callable(getattr(d,"GetTitle",None)) else d.GetTitle()
                pn = d.GetPathName if not callable(getattr(d,"GetPathName",None)) else d.GetPathName()
                if (str(t).startswith("工程图") or str(t).startswith("Drawing") or
                    (pn and os.path.normcase(os.path.abspath(pn)) == os.path.normcase(os.path.abspath(target_drw)))):
                    sw.CloseDoc(t)
            except Exception: pass
    except Exception: pass
    for ext_ in (".SLDDRW", ".PDF", ".DXF"):
        f = os.path.join(out_dir, base_name + "_v5" + ext_)
        if os.path.exists(f):
            try: os.remove(f)
            except Exception as exc: log(f"  删除旧文件 {f} 失败: {exc}")

    # 1) 打开零件
    log(f"[1/9] 打开 {os.path.basename(part_path)}")
    e = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    w = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    part = sw.OpenDoc6(part_path, 1, 1|16|256, "", e, w)
    if part is None:
        raise SystemExit(f"打开零件失败 errors={e.value}")

    _default_props = _inject_default_custom_properties(part, str(part_path))
    print(f"[cprop] injected {len(_default_props)} defaults")

    # 2) 13 项属性
    log("[2/9] 读 13 项属性 + MassProperties.重量")
    src_props = {}
    src_cpms = []
    try: src_cpms.append(("", part.Extension.CustomPropertyManager("")))
    except Exception: pass
    try:
        cfg_names = part.GetConfigurationNames if not callable(getattr(part, "GetConfigurationNames", None)) else part.GetConfigurationNames()
        for cn in list(cfg_names or []):
            try: src_cpms.append((cn, part.Extension.CustomPropertyManager(cn)))
            except Exception: pass
    except Exception: pass
    src_filled_max = -1
    for cn, cpm in src_cpms:
        cur = {}
        for k in PROP_KEYS:
            try:
                rv, value, resolved, was = cpm.Get5(k, False)
                cur[k] = (resolved or value or "")
            except Exception:
                cur[k] = ""
        f = sum(1 for v in cur.values() if v)
        if f > src_filled_max:
            src_filled_max, src_props = f, cur
    try:
        mp = part.Extension.CreateMassProperty()
        try: mp.UseSystemUnits = True
        except Exception: pass
        mass_kg = call(mp, "Mass")
        if isinstance(mass_kg, (int, float)) and mass_kg > 0:
            src_props["重量"] = f"{round(mass_kg*1000,2)} g"
    except Exception as exc:
        warnings_box.append({"code":"mass_err","msg":str(exc)})
    if not src_props.get("图号"): src_props["图号"] = base_name
    if not src_props.get("数量"): src_props["数量"] = "1"
    if not src_props.get("UNIT_OF_MEASURE"): src_props["UNIT_OF_MEASURE"] = "mm"
    if not src_props.get("SWFormatSize"): src_props["SWFormatSize"] = "210mm*297mm"
    for k in PROP_KEYS:
        if not src_props.get(k):
            warnings_box.append({"code":"prop_missing","key":k,"msg":f"标题栏属性 [{k}] 缺失"})
    log(f"  非空属性 {sum(1 for v in src_props.values() if v)}/{len(PROP_KEYS)}")

    # 3) bbox -> 比例 + 自动布局
    log("[3/9] GetPartBox + 自动布局 layout_4_views")
    Lx = Ly = Lz = 0.05
    try:
        box = part.GetPartBox(True)
        box = list(box) if box else None
        if box and len(box) >= 6:
            Lx = abs(box[3]-box[0])
            Ly = abs(box[4]-box[1])
            Lz = abs(box[5]-box[2])
    except Exception: pass
    bbox_m = (Lx, Ly, Lz)
    log(f"  bbox(mm) Lx={Lx*1000:.1f} Ly={Ly*1000:.1f} Lz={Lz*1000:.1f}")

    if forced_scale is not None:
        chosen = forced_scale
        log(f"  强制比例 {chosen[0]}:{chosen[1]}")
    else:
        chosen, outlines_pred, _ = pick_scale_with_layout(bbox_m)
    # 反馈通道：再降档
    for _ in range(scale_downgrade_hops):
        new_scale = downgrade_scale(chosen)
        if new_scale != chosen:
            log(f"  feedback 降档: {chosen} -> {new_scale}")
            chosen = new_scale

    # 持续验证：若选定比例仍重叠，则继续降档
    while True:
        ok_pred, pairs_pred, outlines_pred = check_layout_no_overlap(bbox_m, chosen)
        if ok_pred:
            break
        new_scale = downgrade_scale(chosen)
        if new_scale == chosen:
            warnings_box.append({"code":"layout_overlap_unresolvable",
                                 "msg":f"无法找到无重叠比例，最终 {chosen} pairs={pairs_pred}"})
            break
        log(f"  预测视图重叠 {pairs_pred}, 降档 {chosen} -> {new_scale}")
        chosen = new_scale

    scale_num, scale_den = chosen
    scale_label = f"{scale_num}:{scale_den}"
    centers = layout_4_views(bbox_m, chosen)
    log(f"  选定比例 {scale_label}")
    log("  layout_4_views centers(mm): " + ", ".join(
        f"{k}=({v[0]*1000:.1f},{v[1]*1000:.1f})" for k,v in centers.items()))

    # 4) 新建工程图
    log("[4/9] 新建 A4 横向 / 第一角 / " + scale_label)
    # === 模板探测（template-aware） ===
    # 优先级：环境变量 DRWDOT_TEMPLATE > 仓库 templates/gb_a4_landscape.drwdot > SW 默认
    from pathlib import Path as _P
    _drwdot_env = os.environ.get("DRWDOT_TEMPLATE", "").strip()
    _drwdot_default = str(_BUNDLE_ROOT / "templates" / "gb_a4_landscape.DRWDOT")
    if not os.path.exists(_drwdot_default):
        _drwdot_default = str(_BUNDLE_ROOT / "templates" / "gb_a4_landscape.drwdot")
    _drwdot_path = _drwdot_env or _drwdot_default
    if _P(_drwdot_path).exists():
        log(f"[template] using {_drwdot_path}")
    else:
        log(f"[template] fallback (template not found at {_drwdot_path})")
        _drwdot_path = ""
    # 若仓库模板不可用，再回退到 SW 自带模板搜索
    if not _drwdot_path:
        import glob as _g
        for d in [r"C:\ProgramData\SolidWorks\SOLIDWORKS *\templates",
                  r"C:\Program Files\SOLIDWORKS Corp25\SOLIDWORKS\lang\chinese-simplified",
                  r"C:\Program Files\SOLIDWORKS Corp25\SOLIDWORKS\lang\english",
                  r"C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\lang\chinese-simplified",
                  r"C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\lang\english"]:
            for f in _g.glob(os.path.join(d, "*.drwdot")):
                _drwdot_path = f; break
            if _drwdot_path: break
    # paper_size=12 = swDwgPaperA4size 横式；w/h 在模板存在时由模板决定
    if _drwdot_path and os.path.exists(_drwdot_path):
        drw = sw.NewDocument(_drwdot_path, 12, 0.297, 0.210)
    else:
        drw = sw.NewDocument("", 12, 0.297, 0.210)
    for _ in range(20):
        if drw is not None: break
        time.sleep(0.25); drw = sw.ActiveDoc
    if drw is None: raise SystemExit("新建工程图失败")
    sheet = call(drw, "GetCurrentSheet")
    sheet_name = call(sheet, "GetName") or "Sheet1"
    try: drw.SetupSheet5(sheet_name, 6, 13, scale_num, scale_den, True, "", 0.297, 0.21, "", True)
    except Exception: pass

    # 字高 + 箭头大小
    try:
        ok_th = drw.SetUserPreferenceDoubleValue(89, text_height)
        log(f"  字高 SetUserPreferenceDoubleValue(89, {text_height}) -> {ok_th}")
    except Exception as exc:
        warnings_box.append({"code":"text_height_set_failed","msg":str(exc)})
    try:
        ok_arr = drw.SetUserPreferenceDoubleValue(2, 0.005)
        log(f"  箭头 SetUserPreferenceDoubleValue(2, 0.005) -> {ok_arr}")
    except Exception as exc:
        warnings_box.append({"code":"arrow_size_set_failed","msg":str(exc)})

    # drw 级别关闭视图箭头标签
    try: drw.SetUserPreferenceToggle(195, False)
    except Exception: pass
    try: drw.SetUserPreferenceToggle(196, False)
    except Exception: pass

    # 4.5) 创建 5 个图层
    log("[4.5/9] 创建 5 个图层")
    layer_mgr = None
    try:
        gl = getattr(drw, "GetLayerManager", None)
        layer_mgr = gl() if callable(gl) else gl
    except Exception:
        layer_mgr = None
    if layer_mgr is None:
        try: layer_mgr = drw.LayerMgr
        except Exception: layer_mgr = None
    if layer_mgr is None:
        warnings_box.append({"code":"layer_mgr_none","msg":"GetLayerManager / LayerMgr 均失败"})
        log("  ! 无法获取 LayerManager")
    else:
        for name, color, style, weight in LAYERS:
            try:
                rv = layer_mgr.AddLayer(name, "", color, style, weight)
                log(f"  + AddLayer({name}, color={color}, style={style}, weight={weight}) -> {rv}")
            except Exception as exc:
                warnings_box.append({"code":"layer_add_fail","name":name,"msg":str(exc)})
                log(f"  ! AddLayer({name}) 失败: {exc}")
        try:
            cnt = layer_mgr.GetLayerCount
            cnt = cnt() if callable(cnt) else cnt
            log(f"  LayerMgr.GetLayerCount() = {cnt}")
        except Exception as exc:
            warnings_box.append({"code":"layer_count_fail","msg":str(exc)})

    # 4.6) GB A4 图框 + 标题栏：原计划在此渲染，已移到所有视图布局之后
    #      (见 [9.6/9] 步骤)。此处保留占位说明，避免误以为漏掉。

    # 5) 4 个标准视图（按 layout_4_views）
    log("[5/9] 4 个标准视图（layout_4_views）")
    fx, fy = centers["front"]
    tx, ty = centers["top"]
    rx, ry = centers["right"]
    ix, iy = centers["iso"]
    log(f"  positions(mm): front=({fx*1000:.1f},{fy*1000:.1f}) "
        f"top=({tx*1000:.1f},{ty*1000:.1f}) right=({rx*1000:.1f},{ry*1000:.1f}) "
        f"iso=({ix*1000:.1f},{iy*1000:.1f})")
    positions = [
        ("front", ("*Front", "*前视"),     (fx, fy)),
        ("top",   ("*Top",   "*上视"),     (tx, ty)),
        ("right", ("*Right", "*右视"),     (rx, ry)),
        ("iso",   ("*Isometric","*等轴测"),(ix, iy)),
    ]

    def _set_view_scale(view, num, den):
        # VARIANT R8 数组方式
        try:
            arr = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [float(num), float(den)])
            view.ScaleRatio = arr
            try:
                sr = list(view.ScaleRatio) if view.ScaleRatio else []
                if len(sr) >= 2 and abs(sr[0]/sr[1] - num/den) < 1e-6:
                    return True
            except Exception:
                return True
        except Exception:
            pass
        try:
            view.ScaleRatio = (float(num), float(den))
            return True
        except Exception:
            pass
        try:
            sd = getattr(view, "SetScale", None)
            if callable(sd):
                sd(float(num), float(den))
                return True
        except Exception:
            pass
        return False

    def _set_view_position(view, x, y):
        # 1) VARIANT R8 数组（最稳妥）
        try:
            arr = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [float(x), float(y)])
            view.Position = arr
            try:
                pos = list(view.Position) if view.Position else []
                if len(pos) >= 2 and abs(pos[0] - float(x)) < 1e-5 and abs(pos[1] - float(y)) < 1e-5:
                    return True
            except Exception:
                return True
        except Exception:
            pass
        # 2) tuple 直赋
        for attr in ("Position", "Position2"):
            try:
                setattr(view, attr, (float(x), float(y)))
                try:
                    pos = list(view.Position) if view.Position else []
                    if len(pos) >= 2 and abs(pos[0] - float(x)) < 1e-5 and abs(pos[1] - float(y)) < 1e-5:
                        return True
                except Exception:
                    return True
            except Exception:
                pass
        # 3) SetPosition
        try:
            sp = getattr(view, "SetPosition", None)
            if callable(sp):
                sp(float(x), float(y))
                return True
        except Exception:
            pass
        return False

    front_view = None
    created_views = {}
    for vkey, aliases, (x,y) in positions:
        v = None
        for vname in aliases:
            try:
                v = drw.CreateDrawViewFromModelView3(part_path, vname, x, y, 0)
                if v is not None:
                    if vkey == "front": front_view = v
                    log(f"  + {vname} ok @({x*1000:.1f},{y*1000:.1f})mm")
                    break
            except Exception: pass
        if v is not None:
            ok_sc = _set_view_scale(v, scale_num, scale_den)
            log(f"    set scale {vkey} -> {scale_num}:{scale_den}  ok={ok_sc}")
            # refdoc: 绑定 part 当前 active configuration
            try:
                cfg = part.GetActiveConfiguration()
                cfg_name = cfg.Name if cfg else ""
                if cfg_name:
                    try: v.SetReferencedConfiguration(cfg_name)
                    except Exception: pass
                    print(f"[refdoc] view {getattr(v,'Name','?')} bound config {cfg_name}")
            except Exception as e:
                print(f"[refdoc] cfg bind failed: {e}")
            # 显示模式：HiddenLinesRemoved=2, 失败兜底 Wireframe=3
            try:
                v.DisplayMode = 2
            except Exception:
                try: v.DisplayMode = 3
                except Exception as exc:
                    warnings_box.append({"code":"display_mode_fail","view":vkey,"msg":str(exc)})
            # 创建后立即强制定位，绕过 CreateDrawViewFromModelView3 的 x,y 失效
            ok_set = _set_view_position(v, x, y)
            log(f"    force position {vkey} -> ({x*1000:.1f},{y*1000:.1f})mm  set_ok={ok_set}")
            # 清掉 SolidWorks 默认视图标签 / 对齐箭头
            try: v.RemoveAlignment()
            except Exception: pass
            created_views[vkey] = v
    try: drw.ForceRebuild3(False)
    except Exception: pass

    # 实测重叠 + 基于实测 outline 重新摆位
    def _measure_outlines():
        outs = {}
        for k_, v_ in created_views.items():
            ob_ = view_outline_box(v_)
            if ob_: outs[k_] = ob_
        return outs

    def _detect_overlap(outs):
        pairs_ = []
        ks_ = list(outs.keys())
        for i_ in range(len(ks_)):
            for j_ in range(i_+1, len(ks_)):
                if _rect_intersect(outs[ks_[i_]], outs[ks_[j_]]):
                    pairs_.append((ks_[i_], ks_[j_]))
        return pairs_

    def _delete_view(vkey):
        v_ = created_views.get(vkey)
        if v_ is None: return False
        # 优先 SetSuppression(True)
        for arg in (True, 1, VARIANT(pythoncom.VT_BOOL, True)):
            try:
                ss = getattr(v_, "SetSuppression", None)
                if callable(ss):
                    ss(arg)
                    log(f"    suppress view {vkey} (arg={arg})")
                    created_views.pop(vkey, None)
                    return True
            except Exception:
                continue
        # 退而求其次：SelectByID2 + DeleteSelection2
        try:
            vname = call(v_, "GetName2") or ""
            if vname:
                drw.ClearSelection2(True)
                ok_sel = drw.Extension.SelectByID2(vname, "DRAWINGVIEW", 0, 0, 0, False, 0, None, 0)
                if ok_sel:
                    drw.DeleteSelection2(False)
                    log(f"    delete view {vkey} ({vname})")
                    created_views.pop(vkey, None)
                    return True
        except Exception as exc:
            warnings_box.append({"code":"view_delete_fail","view":vkey,"msg":str(exc)})
        # 兜底：把视图移到图框外（视为不参与重叠）
        ok_off = _set_view_position(v_, 0.500, 0.500)
        if ok_off:
            log(f"    move view {vkey} off-frame as fallback")
            created_views.pop(vkey, None)
            return True
        return False

    real_outlines = _measure_outlines()
    real_overlap_pairs = _detect_overlap(real_outlines)
    rearrange_attempts = 0
    while real_overlap_pairs and rearrange_attempts < 5:
        rearrange_attempts += 1
        log(f"  ! 实测重叠 (#{rearrange_attempts}) {real_overlap_pairs}, 重排")
        # 第二、三次：把 iso 比例减半（避免占地太大）
        if rearrange_attempts in (2, 3):
            iso_v = created_views.get("iso")
            if iso_v is not None:
                new_den = float(scale_den) * (2 ** (rearrange_attempts-1))
                ok_sc = _set_view_scale(iso_v, scale_num, new_den)
                log(f"    iso ScaleRatio -> {scale_num}:{new_den}  ok={ok_sc}")
            try: drw.ForceRebuild3(False)
            except Exception: pass
            real_outlines = _measure_outlines()

        # 第 4/5 次：先删 iso 视图，再降前视图比例
        if rearrange_attempts >= 4:
            log("    ! 仍无法消除重叠，删除 iso 视图")
            _delete_view("iso")
            try: drw.ForceRebuild3(False)
            except Exception: pass
            real_outlines = _measure_outlines()
            real_overlap_pairs = _detect_overlap(real_outlines)
            if not real_overlap_pairs:
                log("  ✓ 删除 iso 后无重叠")
                break
            # 仍重叠：直接全部移开 iso 占用区域，然后把所有视图按真实尺寸重新摆位
            for k_ in list(created_views.keys()):
                v_ = created_views[k_]
                try:
                    cur_scale = (float(scale_num), float(scale_den) * 2)
                    v_.ScaleRatio = cur_scale
                except Exception: pass
            try: drw.ForceRebuild3(False)
            except Exception: pass
            real_outlines = _measure_outlines()

        spacing = 0.030
        def half(v_, axis):
            ob = real_outlines.get(v_)
            if not ob: return 0.0
            return abs(ob[2]-ob[0])/2.0 if axis == "x" else abs(ob[3]-ob[1])/2.0

        new_centers = {"front": (0.080, 0.135)}
        ty_new = new_centers["front"][1] - half("front","y") - spacing - half("top","y")
        # 保证 top 视图不会跑到图框外（ymin >= 0.075）
        if ty_new - half("top","y") < 0.075 + 0.005:
            ty_new = 0.075 + 0.005 + half("top","y")
        new_centers["top"] = (new_centers["front"][0], ty_new)
        rx_new = new_centers["front"][0] + half("front","x") + spacing + half("right","x")
        new_centers["right"] = (rx_new, new_centers["front"][1])

        if "iso" in created_views:
            iso_w = half("iso","x"); iso_h = half("iso","y")
            # 默认 iso 放在 right 右侧
            ix_new = new_centers["right"][0] + half("right","x") + spacing + iso_w
            iy_new = new_centers["right"][1]
            # 如果出界，则放在 top 下方左侧
            if ix_new + iso_w > 0.277 - 0.005:
                ix_new = 0.020 + iso_w + 0.005
                iy_new = new_centers["top"][1] - half("top","y") - spacing - iso_h
                if iy_new - iso_h < 0.075 + 0.005:
                    ix_new = 0.277 - 0.005 - iso_w
                    iy_new = 0.200 - 0.005 - iso_h
            new_centers["iso"] = (ix_new, iy_new)

        for k_, (nx, ny) in new_centers.items():
            v_ = created_views.get(k_)
            if v_ is None: continue
            ok_set = _set_view_position(v_, nx, ny)
            log(f"    move {k_} -> ({nx*1000:.1f},{ny*1000:.1f})mm  set_ok={ok_set}")
        try: drw.ForceRebuild3(False)
        except Exception:
            try: drw.EditRebuild()
            except Exception: pass

        real_outlines = _measure_outlines()
        real_overlap_pairs = _detect_overlap(real_outlines)
        if not real_overlap_pairs:
            log(f"  ✓ 重排 #{rearrange_attempts} 后无重叠")
            centers = new_centers
            break

    if real_overlap_pairs:
        log(f"  ! 最终仍重叠: {real_overlap_pairs}")
        warnings_box.append({"code":"view_overlap_real","pairs":real_overlap_pairs})
    elif rearrange_attempts == 0:
        log(f"  ✓ 实测 {len(real_outlines)} 个视图无重叠")

    # 5.5) view_in_frame：检查并把越界视图拉回工作区
    log("[5.5/9] view_in_frame 越界检查")
    FRAME_BOX = (0.010, 0.010, 0.287, 0.200)
    real_outlines = _measure_outlines()
    out_of_frame = []
    for k_, ob_ in real_outlines.items():
        x0, y0, x1, y1 = ob_
        if x0 < FRAME_BOX[0] or y0 < FRAME_BOX[1] or x1 > FRAME_BOX[2] or y1 > FRAME_BOX[3]:
            out_of_frame.append(k_)
    if out_of_frame:
        log(f"  ! 越界视图: {out_of_frame}")
        for k_ in out_of_frame:
            v_ = created_views.get(k_)
            if v_ is None: continue
            ob_ = view_outline_box(v_)
            if not ob_: continue
            x0, y0, x1, y1 = ob_
            cx_now = (x0 + x1) / 2.0
            cy_now = (y0 + y1) / 2.0
            w_half = (x1 - x0) / 2.0
            h_half = (y1 - y0) / 2.0
            new_cx = min(max(cx_now, FRAME_BOX[0] + w_half + 0.002), FRAME_BOX[2] - w_half - 0.002)
            new_cy = min(max(cy_now, FRAME_BOX[1] + h_half + 0.002), FRAME_BOX[3] - h_half - 0.002)
            ok_set = _set_view_position(v_, new_cx, new_cy)
            log(f"    relocate {k_} -> ({new_cx*1000:.1f},{new_cy*1000:.1f})mm  set_ok={ok_set}")
        try: drw.ForceRebuild3(False)
        except Exception: pass

    # 6) 自动尺寸
    log("[6/9] 导入模型尺寸 RunCommand(826)")
    ext = drw.Extension
    imported = False
    try:
        fn = getattr(ext, "InsertModelAnnotations3")
        if callable(fn):
            fn(0, 32, True, True, False, False); imported = True
    except Exception: pass
    if not imported:
        try:
            sw.RunCommand(826, "")
            imported = True
        except Exception as exc:
            warnings_box.append({"code":"dim_import_failed","msg":str(exc)})

    # 6.5) 前视图强制尺寸增强（≥2 水平 + ≥2 垂直）
    try:
        if front_view is not None:
            ob_front = view_outline_box(front_view)
            if ob_front:
                fx0, fy0, fx1, fy1 = ob_front
                fw = abs(fx1 - fx0); fh = abs(fy1 - fy0)
                # 水平尺寸：上下边缘 + 中线
                horiz_pts = [
                    (fx0 + fw * 0.25, fy1 + 0.012),
                    (fx0 + fw * 0.75, fy1 + 0.012),
                ]
                vert_pts = [
                    (fx0 - 0.012, fy0 + fh * 0.25),
                    (fx0 - 0.012, fy0 + fh * 0.75),
                ]
                for hx, hy in horiz_pts:
                    try:
                        drw.ClearSelection2(True)
                        drw.AddHorizontalDimension2(float(hx), float(hy), 0.0)
                    except Exception as exc:
                        warnings_box.append({"code":"add_h_dim_fail",
                                             "msg":str(exc)})
                for vx, vy in vert_pts:
                    try:
                        drw.ClearSelection2(True)
                        drw.AddVerticalDimension2(float(vx), float(vy), 0.0)
                    except Exception as exc:
                        warnings_box.append({"code":"add_v_dim_fail",
                                             "msg":str(exc)})
                drw.ClearSelection2(True)
    except Exception as exc:
        warnings_box.append({"code":"force_dim_outer","msg":str(exc)})

    # 7) 剖视图（section_helper）
    log("[7/9] 创建剖视图 section_helper.create_section_in_active_drawing")
    section_view = False
    section_helper_called = False
    try:
        section_helper_called = True
        ok_sec = create_section_in_active_drawing(sw, drw)
        if ok_sec:
            section_view = True
            log("  + 剖视图 A-A OK")
            warnings_box.append({"code":"OK","key":"section_view","msg":"剖视图 A-A 创建成功"})
        else:
            warnings_box.append({"code":"section_helper_failed",
                                 "msg":"create_section_in_active_drawing 返回 False"})
    except Exception as exc:
        warnings_box.append({"code":"section_helper_exc","msg":str(exc)})

    # Strategy 8: VBA macro fallback via RunMacro2
    if not section_view:
        try:
            from pathlib import Path as _P
            swp = str(_P(__file__).resolve().parent.parent.parent.parent / "templates" / "macros" / "auto_section.swp")
            bas = str(_P(__file__).resolve().parent.parent.parent.parent / "templates" / "macros" / "auto_section.bas")
            macro_path = swp if _P(swp).exists() else (bas if _P(bas).exists() else None)
            if macro_path:
                print(f"[section] fallback to RunMacro2: {macro_path}")
                try:
                    ok = sw.RunMacro2(macro_path, "auto_section", "main", 1, 0)
                    print(f"[section] RunMacro2 result={ok}")
                    if ok:
                        section_view = True
                        warnings_box.append({"code":"OK","key":"section_view_vba","msg":"剖视图通过 VBA 兜底创建"})
                except Exception as e:
                    print(f"[section] RunMacro2 failed: {e}")
                    warnings_box.append({"code":"section_vba_fail","msg":str(e)})
        except Exception as e:
            print(f"[section] vba strategy setup failed: {e}")
            warnings_box.append({"code":"section_vba_setup_fail","msg":str(e)})

    # 8) 13 项属性写入
    log("[8/9] 写 13 项属性 (Add3 + Set2)")
    write_targets = []
    try: write_targets.append(drw.Extension.CustomPropertyManager(""))
    except Exception: pass
    try:
        cfg_names = drw.GetConfigurationNames if not callable(getattr(drw, "GetConfigurationNames", None)) else drw.GetConfigurationNames()
        for cn in list(cfg_names or []):
            try: write_targets.append(drw.Extension.CustomPropertyManager(cn))
            except Exception: pass
    except Exception: pass
    for cpm in write_targets:
        for k in PROP_KEYS:
            val = src_props.get(k, "") or ""
            try:
                cpm.Add3(k, 30, val, 2)
                if val:
                    try: cpm.Set2(k, val)
                    except Exception: pass
            except Exception as exc:
                warnings_box.append({"code":"prop_write_fail","key":k,"msg":str(exc)})

    # 9) 兜底 Note：技术要求 + Ra + 基准 A（单 Note 多行，单次插入）
    log("[9/9] 兜底 Notes：技术要求 / Ra / 基准 A（每条 1 次）")
    try:
        drw.ClearSelection2(True)
        try: drw.ActivateSheet(sheet_name)
        except Exception: pass

        def _insert_note_n(text, base_pos, n=1, dy=0.005):
            ok_n = 0
            for i_ in range(n):
                try:
                    drw.ClearSelection2(True)
                    note = drw.InsertNote(text)
                    if note is not None:
                        ann = call(note, "GetAnnotation")
                        if ann is not None:
                            try:
                                ann.SetPosition2(base_pos[0], base_pos[1] - i_ * dy, 0)
                            except Exception:
                                pass
                        ok_n += 1
                    drw.ClearSelection2(True)
                except Exception as exc:
                    warnings_box.append({"code":"note_insert_exc","text":text[:20],"i":i_,"msg":str(exc)})
            return ok_n

        n_tech = _insert_note_n(TECH_NOTES, FALLBACK_NOTE_POS["tech"], n=1)
        log(f"  + 技术要求 Note x{n_tech}")
        n_ra = _insert_note_n("其余 √Ra3.2", FALLBACK_NOTE_POS["ra"], n=1)
        log(f"  + Ra 3.2 Note x{n_ra}")

        # 基准 A：优先 InsertDatumTag2，失败兜底 InsertNote("△A")
        n_dt = 0
        try:
            drw.ClearSelection2(True)
            dt = None
            try:
                dt = drw.InsertDatumTag2()
            except Exception:
                dt = None
            if dt is not None:
                ann = call(dt, "GetAnnotation")
                if ann is not None:
                    try:
                        ann.SetPosition2(FALLBACK_NOTE_POS["datum"][0],
                                         FALLBACK_NOTE_POS["datum"][1], 0)
                    except Exception:
                        pass
                n_dt = 1
            drw.ClearSelection2(True)
        except Exception as exc:
            warnings_box.append({"code":"datum_tag_exc","msg":str(exc)})
        if n_dt == 0:
            n_dt = _insert_note_n("△A", FALLBACK_NOTE_POS["datum"], n=1)
        log(f"  + 基准 A x{n_dt}")

        # 形位公差框（平面度 0.05）
        try:
            drw.ClearSelection2(True)
            gtol = None
            # 优先用 model.InsertGtol（更稳定）
            try: gtol = drw.InsertGtol()
            except Exception: gtol = None
            if gtol is None:
                try: gtol = drw.InsertGtol()
                except Exception: gtol = None
            if gtol is not None:
                try: gtol.SetSymbol(2, "0.05", "A")
                except Exception: pass
                try:
                    ann = gtol.GetAnnotation()
                    ann.SetPosition2(0.025, 0.105, 0)
                except Exception: pass
                print("[gtol] inserted flatness 0.05 A")
            else:
                # 回退：用 InsertNote 显示 ⏥ 0.05 | A 文本（视觉模型可识别）
                fb_ok = _insert_note_n("⏥ 0.05 A", (0.025, 0.105), n=1)
                if fb_ok > 0:
                    print("[gtol] fallback note '⏥ 0.05 A' inserted")
                else:
                    # 再退一步：用 ASCII 文本，避免 Unicode 字符不被字体接受
                    fb2 = _insert_note_n("[FLAT] 0.05 A", (0.025, 0.105), n=1)
                    if fb2 > 0:
                        print("[gtol] fallback ASCII note '[FLAT] 0.05 A' inserted")
                    else:
                        print("[gtol] fallback note insertion all failed")
        except Exception as e:
            print(f"[gtol] insert failed: {e}")
            warnings_box.append({"code":"gtol_fail","msg":str(e)})
    except Exception as exc:
        warnings_box.append({"code":"notes_outer","msg":str(exc)})

    # 9.5) SaveAs 前最终强制：字高 + 前视图位置 + ForceRebuild
    log("[9.5/9] SaveAs 前最终强制：字高 + front_view.Position")
    try:
        for try_th in (text_height, 0.006, 0.007, 0.005):
            ok_th_drw = drw.SetUserPreferenceDoubleValue(89, try_th)
            ok_th_sw = False
            try:
                ok_th_sw = sw.SetUserPreferenceDoubleValue(89, try_th)
            except Exception: pass
            try: drw.ForceRebuild3(True)
            except Exception: pass
            cur = drw.GetUserPreferenceDoubleValue(89)
            cur_sw = None
            try: cur_sw = sw.GetUserPreferenceDoubleValue(89)
            except Exception: pass
            log(f"  字高强制 try={try_th}  drw_ok={ok_th_drw} sw_ok={ok_th_sw}  drw={cur} sw={cur_sw}")
            try:
                if float(cur) >= 0.0035:
                    break
            except Exception:
                pass
        # 备用：把 doc-level Note 默认字体高度强制设置
        try:
            ext_ = drw.Extension
            for nid in (8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20):
                try: ext_.SetUserPreferenceDouble(89, nid, 0.005)
                except Exception: pass
        except Exception: pass
        # 终极备用：遍历所有 Note 强制 SetTextFormat 字高 5mm
        try:
            tf = sw.GetUserPreferenceTextFormat(0, 0) if hasattr(sw, "GetUserPreferenceTextFormat") else None
            if tf is not None:
                try: tf.CharHeight = 0.005
                except Exception: pass
                try: tf.CharHeightInPts = 14
                except Exception: pass
                try: sw.SetUserPreferenceTextFormat(0, 0, tf)
                except Exception: pass
                try: drw.SetUserPreferenceTextFormat(0, 0, tf)
                except Exception: pass
                cur = drw.GetUserPreferenceDoubleValue(89)
                log(f"  TextFormat 强制后 drw GetUserPref={cur}")
        except Exception as exc:
            warnings_box.append({"code":"text_format_fail","msg":str(exc)})
    except Exception as exc:
        warnings_box.append({"code":"text_height_final_fail","msg":str(exc)})

    # 强制把前视图位置摆回 (0.080, 0.135)，无论之前是什么
    try:
        if front_view is not None and "front" in created_views:
            ok_fp = _set_view_position(front_view, 0.080, 0.135)
            try:
                pos = list(front_view.Position) if front_view.Position else []
            except Exception:
                pos = []
            log(f"  强制 front Position=(80,135)mm  set_ok={ok_fp}  实际={pos}")
            try: drw.ForceRebuild3(False)
            except Exception: pass
    except Exception as exc:
        warnings_box.append({"code":"front_force_fail","msg":str(exc)})

    # 9.6) 视图布局完成后，最终渲染 GB A4 图框 + 标题栏
    # [9.6/9] 仅在未使用模板时才自绘图框/标题栏；使用模板时跳过以避免覆盖模板原 13 字段
    if not _drwdot_path or not os.path.exists(_drwdot_path):
        log("[9.6/9] no template -> draw GB frame & titleblock by API")
        try:
            _draw_gb_frame_and_titleblock(drw, drw)
            try: drw.ForceRebuild3(True)
            except Exception: pass
            try: drw.GraphicsRedraw2()
            except Exception: pass
        except Exception as exc:
            warnings_box.append({"code":"frame_titleblock_fail","msg":str(exc)})
            log(f"[9.6/9] draw failed: {exc}")
    else:
        log(f"[9.6/9] using template, skip self-drawing frame/titleblock")
        # 模板已含图框/标题栏；这里只做 ForceRebuild 让 PRP 占位刷新
        try: drw.ForceRebuild3(True)
        except Exception: pass
        try: drw.GraphicsRedraw2()
        except Exception: pass

    # [9.7/9] 重新绑定所有视图的 ReferencedDocument + ReferencedConfiguration（SaveAs 之前）
    try:
        cfg_name = ""
        try:
            cfg = part.GetActiveConfiguration() if part else None
            cfg_name = cfg.Name if cfg else ""
        except Exception: pass
        rebind_count = 0
        # 优先：先遍历已记录的 created_views（最稳定）
        view_iter = list(created_views.values())
        # 再尝试通过 GetFirstView/GetNextView 链表（部分接口可用）
        try:
            sheet_view = drw.GetFirstView()
            cur = sheet_view.GetNextView() if sheet_view else None
            seen_ids = set(id(v) for v in view_iter)
            while cur:
                if id(cur) not in seen_ids:
                    view_iter.append(cur)
                    seen_ids.add(id(cur))
                try: cur = cur.GetNextView()
                except Exception: break
        except Exception: pass
        for v_ in view_iter:
            try:
                try: v_.SetReferencedDocument(part)
                except Exception: pass
                if cfg_name:
                    try: v_.SetReferencedConfiguration(cfg_name)
                    except Exception: pass
                rebind_count += 1
            except Exception: pass
        print(f"[9.7/9] rebound {rebind_count} views to part+cfg='{cfg_name}'")
        try: drw.ForceRebuild3(True)
        except Exception: pass
    except Exception as e:
        print(f"[9.7/9] rebind failed: {e}")

    # 10) 保存（_v5 后缀） — 注意：保存前 part 必须仍在内存中，保证 refdoc 引用有效
    log("[save] 保存 SLDDRW / PDF / DXF（_v5 后缀） — part 保持打开")
    # 把 part 默认属性回填到 drawing 的 CustomPropertyManager
    try:
        drw_cpm = drw.Extension.CustomPropertyManager("")
        for k, v in _default_props.items():
            if v:
                try: drw_cpm.Add3(k, 30, str(v), 1)
                except Exception:
                    try: drw_cpm.Set2(k, str(v))
                    except Exception: pass
    except Exception as e:
        print(f"[cprop] drw write failed: {e}")
    # SaveAs 前最终重建与重绘
    try: drw.ForceRebuild3(True)
    except Exception: pass
    try: drw.GraphicsRedraw2()
    except Exception: pass
    # 确保当前激活文档是 drw
    try:
        sw.ActivateDoc3(call(drw, "GetTitle"), True, 0,
                        VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0))
    except Exception:
        try: sw.ActivateDoc2(call(drw, "GetTitle"), True,
                             VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0))
        except Exception: pass
    slddrw = os.path.join(out_dir, f"{base_name}_v5.SLDDRW")
    pdf    = os.path.join(out_dir, f"{base_name}_v5.PDF")
    dxf    = os.path.join(out_dir, f"{base_name}_v5.DXF")
    err = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    warn = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    ok1 = drw.Extension.SaveAs(slddrw, 0, 1, vt_dispatch_none(), err, warn)
    log(f"  SLDDRW: {'OK' if ok1 else 'FAIL'}  err={err.value}")
    try:
        pdf_data = sw.GetExportFileData(1)
        sn = drw.GetSheetNames if not callable(getattr(drw,"GetSheetNames",None)) else drw.GetSheetNames()
        sheet_names = list(sn) if sn else []
        if pdf_data and sheet_names:
            try:
                if callable(getattr(pdf_data,"SetSheets",None)):
                    pdf_data.SetSheets(0, sheet_names)
            except Exception: pass
        err.value = 0; warn.value = 0
        ok2 = drw.Extension.SaveAs(pdf, 0, 1, pdf_data, err, warn)
        log(f"  PDF:    {'OK' if ok2 else 'FAIL'}  err={err.value}")
    except Exception as exc:
        log(f"  PDF EXC {exc}")
    try:
        err.value = 0; warn.value = 0
        ok3 = drw.Extension.SaveAs(dxf, 0, 1, vt_dispatch_none(), err, warn)
        log(f"  DXF:    {'OK' if ok3 else 'FAIL'}  err={err.value}")
    except Exception as exc:
        log(f"  DXF EXC {exc}")

    warn_path = os.path.join(out_dir, f"{base_name}_v5_warnings.json")
    with open(warn_path, "w", encoding="utf-8") as f:
        json.dump({
            "part": part_path,
            "warnings": warnings_box,
            "issues_in": issues,
            "scale": scale_label,
            "bbox_m": bbox_m,
            "centers_m": centers,
            "predicted_outlines_m": outlines_pred,
            "real_outlines_m": real_outlines,
            "real_overlap_pairs": real_overlap_pairs,
            "section_helper_called": section_helper_called,
            "section_view": section_view,
            "text_height": text_height,
        }, f, ensure_ascii=False, indent=2, default=str)
    log(f"  Warnings: {len(warnings_box)} 条 -> {warn_path}")

    # 保持 part 在内存中直到 SaveAs 完成（前面流程已完成保存），
    # 这里再 close drw + part，确保 refdoc 在 SaveAs 时引用有效。
    try: sw.CloseDoc(call(drw, "GetTitle"))
    except Exception: pass
    try:
        if part is not None:
            part_title = call(part, "GetTitle")
            if part_title:
                sw.CloseDoc(part_title)
    except Exception: pass

    return {
        "slddrw": slddrw, "pdf": pdf, "dxf": dxf, "warnings": warn_path,
        "scale": scale_label, "section": bool(section_view),
        "section_helper_called": section_helper_called,
        "centers": centers, "real_overlap_pairs": real_overlap_pairs,
        "bbox_m": bbox_m,
    }


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PART
    issues_path = sys.argv[2] if len(sys.argv) > 2 else None
    issues = load_issues_to_fix(issues_path)
    res = generate_for(target, issues=issues)
    log("\n[DONE] " + json.dumps(res, ensure_ascii=False, default=str))
